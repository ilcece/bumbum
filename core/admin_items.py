"""物品草稿、真实列表和服装基础资料及启停；不进行芯片绑定。"""

import json
import re
from urllib.parse import urlsplit

from flask import Blueprint, g, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, lock_admin_session, request_json
from core.admin_queries import (boolean_parameter, check_parameters, consistent_read, contains,
                                date_conditions, pagination, positive_integer)
from core.auth_settings import client_ip, fingerprint, iso_time
from core.db import get_database
from core.media_assets import map_profile_images

blueprint = Blueprint("admin_items", __name__, url_prefix="/api/admin/items")
PROJECT_PREFIXES = {"fashion": "FASH", "jewelry": "JEW"}
STATUSES = {"draft", "active", "disabled", "archived"}
ITEM_COLUMNS = "i.id,p.code AS project,i.item_uid,i.sku_code,i.status,i.created_at,i.updated_at"
ITEM_JOINS = "FROM item i JOIN project p ON p.id=i.project_id"
ITEM_VIEW = "SELECT " + ITEM_COLUMNS + " " + ITEM_JOINS
ITEM_NAME = "CASE p.code WHEN 'fashion' THEN fp.name WHEN 'jewelry' THEN jp.name END"
READ_JOINS = ITEM_JOINS + """ LEFT JOIN chip c ON c.item_id=i.id
LEFT JOIN chip_key k ON k.chip_id=c.id
LEFT JOIN fashion_item_profile fp ON fp.item_id=i.id AND p.code='fashion'
LEFT JOIN jewelry_item_profile jp ON jp.item_id=i.id AND p.code='jewelry' """
READ_VIEW = "SELECT " + ITEM_COLUMNS + """,c.id AS linked_id,c.chip_uid AS linked_uid,
c.chip_status AS linked_status,(k.chip_id IS NOT NULL) AS linked_keys,c.provisioned_at AS linked_provisioned """
MISSING = object()

PROFILE_FIELDS = {"name", "description", "material", "care_instructions", "image_urls"}


def normalized_profile(data):
    """新普通保存与兼容PUT共用整份资料校验；不接受尺码表。"""
    if not isinstance(data, dict) or "name" not in data or set(data) - PROFILE_FIELDS:
        invalid("资料须包含名称，且仅接受本次五项可编辑字段。")
    result = {}
    for field, limit in (("name", 128), ("description", 4000), ("material", 256), ("care_instructions", 2000)):
        value = data.get(field)
        if value is None and field != "name":
            result[field] = None
            continue
        if not isinstance(value, str) or len(value.strip()) > limit or (field == "name" and not value.strip()):
            invalid(f"{field}须为最多{limit}字符的文字，名称不能为空。")
        result[field] = value.strip() or None
    urls = data.get("image_urls", [])
    if not isinstance(urls, list) or len(urls) > 20:
        invalid("图片地址须为最多20项的列表。")
    result["image_urls"] = []
    if urls:
        raise AuthRequestError(400,'invalid_param','旧单件图片已退役，请在共用款式维护图片。')

    return result


def locked_item(cursor, item_id):
    """先锁物品，普通资料维护不逆向锁关联芯片。"""
    cursor.execute(ITEM_VIEW + " WHERE i.id=%s FOR UPDATE OF i", (item_id,))
    item = cursor.fetchone()
    if item is None:
        raise AuthRequestError(404, "not_found", "该物品不存在。")
    return item


def editable_item(item):
    if item["status"] == "archived":
        raise AuthRequestError(409, "invalid_state", "归档物品本次不可编辑或恢复。")


def locked_fashion_item(cursor, item_id):
    item = locked_item(cursor, item_id)
    if item["project"] != "fashion":
        raise AuthRequestError(409, "project_mismatch", "服装资料和启停仅支持服装物品；饰品可单独维护款式编号。")
    editable_item(item)
    return item


def record_item_change(cursor, item_id, action, detail, project="fashion"):
    cursor.execute(
        "INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,%s,%s,%s,%s)",
        (g.admin_session["admin_id"], action, "item", str(item_id), json.dumps({"project": project, **detail}, ensure_ascii=False), fingerprint("ip", client_ip())),
    )


def write_item(item_id, profile=None, status=None, sku=MISSING, *, profile_only=False):
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            lock_admin_session(cursor)
            item = locked_fashion_item(cursor, item_id) if profile is not None or status is not None else locked_item(cursor, item_id)
            editable_item(item)
            cursor.execute("SELECT issue_id FROM digital_item WHERE item_id=%s", (item_id,))
            digital = cursor.fetchone()
            if digital and digital['issue_id']:
                if profile is not None:
                    raise AuthRequestError(409,"invalid_state","此物品引用共用款式，请从款式维护资料。")
                if status == 'active':
                    cursor.execute("SELECT w.id FROM whole_item w JOIN chip c ON c.id=w.chip_id WHERE w.current_item_id=%s AND w.lost_at IS NULL AND w.loss_evidence IS NULL AND c.chip_status='bound' AND c.item_id=%s AND c.provisioned_at IS NOT NULL", (item_id,item_id))
                    if not cursor.fetchone():
                        raise AuthRequestError(409,"invalid_state","请先准备整套物品并完成有效配置核验。")
            changed = []
            if profile is not None:
                cursor.execute("SELECT * FROM fashion_item_profile WHERE item_id=%s FOR UPDATE", (item_id,))
                previous = cursor.fetchone()
                for field in ("name", "description", "material", "care_instructions", "image_urls"):
                    old = previous[field] if previous else MISSING
                    if field == "image_urls" and previous:
                        old = json.loads(old) if old is not None else []
                    if old != profile[field]:
                        changed.append("profile." + field)
                if changed:
                    # 白名单更新五个字段；已有size_chart原样保留。
                    cursor.execute(
                        "INSERT INTO fashion_item_profile(item_id,name,description,material,care_instructions,image_urls) "
                        "VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name),description=VALUES(description),"
                        "material=VALUES(material),care_instructions=VALUES(care_instructions),image_urls=VALUES(image_urls)",
                        (item_id, profile["name"], profile["description"], profile["material"], profile["care_instructions"], json.dumps(profile["image_urls"], ensure_ascii=False)),
                    )
            detail = {}
            if sku is not MISSING and sku != item["sku_code"]:
                cursor.execute("UPDATE item SET sku_code=%s WHERE id=%s", (sku, item_id))
                changed.append("sku_code")
                detail["sku_code"] = {"from": item["sku_code"], "to": sku}
            if changed:
                cursor.execute("UPDATE item SET updated_at=CURRENT_TIMESTAMP WHERE id=%s", (item_id,))
                record_item_change(cursor, item_id, "item.profile.save" if profile_only else "item.details.update",
                                   {} if profile_only else {"fields": changed, **detail}, item["project"])
            if status is not None and status != item["status"]:
                if status == "disabled" and item["status"] != "active":
                    raise AuthRequestError(409, "invalid_state", "只有启用的物品可以停用。")
                if status == "active":
                    cursor.execute("SELECT name FROM fashion_item_profile WHERE item_id=%s FOR UPDATE", (item_id,))
                    found = cursor.fetchone()
                    if not found or not isinstance(found["name"], str) or not 1 <= len(found["name"].strip()) <= 128:
                        raise AuthRequestError(409, "invalid_state", "请先保存有效的服装名称，再启用物品。")
                cursor.execute("UPDATE item SET status=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s", (status, item_id))
                record_item_change(cursor, item_id, "item.status.change", {"from": item["status"], "to": status})
            if profile_only or status is not None:
                # 保留旧PUT资料及启停的返回形状，新普通PATCH返回完整摘要。
                cursor.execute(ITEM_VIEW + " WHERE i.id=%s", (item_id,))
                result = item_views(cursor, [cursor.fetchone()])[0]
            else:
                cursor.execute(READ_VIEW + READ_JOINS + " WHERE i.id=%s", (item_id,))
                result = item_summaries(cursor, [cursor.fetchone()])[0]
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(status="ok", data=result["profile"] if profile_only else result)


@blueprint.route("/<int:item_id>", methods=["GET", "PATCH"])
def item_detail(item_id):
    if item_id < 1 or item_id > 18446744073709551615 or request.args:
        invalid("物品ID须为有效正整数，此接口不接收查询参数。")
    if request.method == "PATCH":
        data = request_json(set(), {"status", "sku_code", "profile"}, max_bytes=256 * 1024)
        if not data or ("status" in data and len(data) != 1):
            invalid("请提交款式或资料中的至少一项；启停须独立提交。")
        if "status" in data:
            if len(request.get_data(cache=True)) > 8192:
                invalid("启停请求最多8192字节。")
            if not isinstance(data["status"], str) or data["status"] not in {"active", "disabled"}:
                invalid("启停仅允许active或disabled。")
            return write_item(item_id, status=data["status"])
        sku = data.get("sku_code", MISSING)
        if sku is not MISSING and sku is not None:
            if not isinstance(sku, str) or len(sku.strip()) > 64:
                invalid("款式编号须为最多64字符的文字，null或空串表示清空。")
            sku = sku.strip() or None
        profile = normalized_profile(data["profile"]) if "profile" in data else None
        return write_item(item_id, profile=profile, sku=sku)
    with consistent_read() as cursor:
        cursor.execute(READ_VIEW + READ_JOINS + " WHERE i.id=%s", (item_id,))
        found = cursor.fetchone()
        if found is None:
            raise AuthRequestError(404, "not_found", "该物品不存在。")
        result = item_summaries(cursor, [found])[0]
    return jsonify(status="ok", data=result)


@blueprint.put("/<int:item_id>/profile")
def save_profile(item_id):
    if item_id < 1 or item_id > 18446744073709551615:
        invalid("物品ID须为有效正整数。")
    data = request_json({"name"}, PROFILE_FIELDS - {"name"}, max_bytes=256 * 1024)
    return write_item(item_id, profile=normalized_profile(data), profile_only=True)


def invalid(message):
    raise AuthRequestError(400, "invalid_param", message)


def item_views(cursor, rows):
    """每个项目批量读取实际资料，避免逐件查询或把已有资料伪报为空。"""
    profiles = {}
    for project in PROJECT_PREFIXES:
        ids = [row["id"] for row in rows if row["project"] == project]
        if not ids:
            continue
        table = project + "_item_profile"
        cursor.execute(f"SELECT * FROM {table} WHERE item_id IN ({','.join(['%s'] * len(ids))})", ids)
        for profile in cursor.fetchall():
            item_id = profile.pop("item_id")
            profile.pop("id")
            profile.pop("updated_at")
            for field in ("image_urls", "size_chart"):
                if field in profile:
                    profile[field] = json.loads(profile[field]) if profile[field] is not None else ([] if field == "image_urls" else None)
            profiles[item_id] = profile
    map_profile_images(cursor, profiles)
    for row in rows:
        row["profile"] = profiles.get(row["id"])
        for field in ("created_at", "updated_at"):
            row[field] = iso_time(row[field]) if row[field] else None
    return rows


def item_summaries(cursor, rows):
    for row in rows:
        chip_id = row.pop("linked_id")
        chip = {"id": chip_id, "chip_uid": row.pop("linked_uid"), "chip_status": row.pop("linked_status"),
                "keys_generated": bool(row.pop("linked_keys")), "provisioned_at": row.pop("linked_provisioned")}
        if chip["provisioned_at"] is not None:
            chip["provisioned_at"] = iso_time(chip["provisioned_at"])
        row["linked_chip"] = chip if chip_id is not None else None
        row["keyword_matches"] = [field for field in ("item_uid", "sku_code", "name", "chip_uid") if row.pop("match_" + field, False)]
    return item_views(cursor, rows)


def create_item():
    data = request_json({"project", "item_uid"}, {"sku_code", "status"})
    project, uid, sku = data["project"], data["item_uid"], data.get("sku_code")
    if not isinstance(project, str) or project not in PROJECT_PREFIXES:
        invalid("请选择服装fashion或饰品jewelry项目。")
    if not isinstance(uid, str) or not 1 <= len(uid.strip()) <= 32 or any(ord(x) < 32 or ord(x) == 127 for x in uid):
        invalid("物品编号去首尾空白后须为1至32字符，不含控制字符，格式不限且全局唯一。")
    uid = uid.strip()
    if data.get("status", "draft") != "draft":
        invalid("本入口只创建草稿，status只能为draft或省略。")
    if sku is not None:
        if not isinstance(sku, str) or len(sku.strip()) > 64:
            invalid("款式编号须为最多64字符的文字，留空可省略或传null。")
        sku = sku.strip() or None
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            lock_admin_session(cursor)
            cursor.execute("SELECT id FROM project WHERE code=%s", (project,))
            found = cursor.fetchone()
            if found is None:
                raise pymysql.OperationalError("初始项目资料未就绪。")
            try:
                cursor.execute("INSERT INTO item(project_id,item_uid,sku_code) VALUES (%s,%s,%s)", (found["id"], uid, sku))
            except pymysql.IntegrityError as error:
                if error.args[0] == 1062:
                    raise AuthRequestError(409, "already_exists", "该物品编号已存在，未创建或覆盖原记录，请按编号查询。") from None
                raise
            item_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,%s,%s,%s,%s)",
                (g.admin_session["admin_id"], "item.create", "item", str(item_id), json.dumps({"project": project}), fingerprint("ip", client_ip())),
            )
            cursor.execute(ITEM_VIEW + " WHERE i.id=%s", (item_id,))
            item = item_views(cursor, [cursor.fetchone()])[0]
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(status="ok", data=item)


def list_items():
    dates = {"created": "i.created_at", "updated": "i.updated_at"}
    allowed = {"page", "page_size", "project", "status", "keyword", "unbound_only", "has_chip"}
    allowed.update(f"{name}_{suffix}" for name in dates for suffix in ("from", "to"))
    check_parameters(allowed)
    page, size = positive_integer("page", 1, 2147483647), positive_integer("page_size", 20, 100)
    conditions, values = [], []
    unbound_only, has_chip = boolean_parameter("unbound_only"), boolean_parameter("has_chip")
    if unbound_only and has_chip is True:
        invalid("未绑定候选条件不能同时要求已关联芯片。")
    if unbound_only or has_chip is False:
        conditions.append("c.id IS NULL")
    elif has_chip is True:
        conditions.append("c.id IS NOT NULL")
    for name, options, column in (("project", PROJECT_PREFIXES, "p.code"), ("status", STATUSES, "i.status")):
        if name in request.args:
            value = request.args[name]
            if value not in options:
                invalid(f"{name}不在允许范围内。")
            conditions.append(column + "=%s")
            values.append(value)
    date_conditions(dates, conditions, values)
    keyword = request.args.get("keyword", "")
    if len(keyword) > 128:
        invalid("关键词最长128字符。")
    keyword = keyword.strip()
    matches, match_values = "", []
    if keyword:
        expressions = [column + " LIKE %s ESCAPE '!'" for column in ("i.item_uid", "i.sku_code", ITEM_NAME, "REPLACE(c.chip_uid,':','')")]
        match_values = [contains(keyword)] * 3 + [contains(keyword.replace(":", "").upper() or keyword)]
        conditions.append("(" + " OR ".join(expressions) + ")")
        values.extend(match_values)
        matches = "," + ",".join(f"({expression}) AS match_{field}" for expression, field in zip(expressions, ("item_uid", "sku_code", "name", "chip_uid"))) + " "
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with consistent_read() as cursor:
        cursor.execute("SELECT COUNT(*) AS total " + READ_JOINS + where, values)
        total = cursor.fetchone()["total"]
        paging = pagination(total, page, size)
        cursor.execute(READ_VIEW + matches + READ_JOINS + where + " ORDER BY i.id DESC LIMIT %s OFFSET %s", (*match_values, *values, size, (paging["page"] - 1) * size))
        items = item_summaries(cursor, list(cursor.fetchall()))
    return jsonify(status="ok", data={"items": items, **paging})


@blueprint.route("", methods=["GET", "POST"])
def items():
    return list_items() if request.method in {"GET", "HEAD"} else create_item()
