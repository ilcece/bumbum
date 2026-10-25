"""物品草稿、真实列表和服装基础资料及启停；不进行芯片绑定。"""

import json
import re
from urllib.parse import urlsplit

from flask import Blueprint, g, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, lock_admin_session, request_json
from core.admin_chips import positive_integer
from core.auth_settings import client_ip, fingerprint, iso_time
from core.db import get_database

blueprint = Blueprint("admin_items", __name__, url_prefix="/api/admin/items")
PROJECT_PREFIXES = {"fashion": "FASH", "jewelry": "JEW"}
STATUSES = {"draft", "active", "disabled", "archived"}
ITEM_VIEW = "SELECT i.id,p.code AS project,i.item_uid,i.sku_code,i.status,i.created_at,i.updated_at FROM item i JOIN project p ON p.id=i.project_id"

PROFILE_FIELDS = {"name", "description", "material", "care_instructions", "image_urls"}


def normalized_profile():
    """整份校验本小步资料；尺码表不接受输入也不参与更新。"""
    data = request_json({"name"}, PROFILE_FIELDS - {"name"}, max_bytes=256 * 1024)
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
    for value in urls:
        if not isinstance(value, str):
            invalid("每个图片地址须为文字。")
        value = value.strip()
        try:
            parsed = urlsplit(value)
            valid = (parsed.scheme in {"http", "https"} and parsed.hostname and parsed.username is None
                     and parsed.password is None and (parsed.port is None or 0 < parsed.port <= 65535))
        except ValueError:
            valid = False
        if not valid or len(value) > 2048 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value) or "\\" in value:
            invalid("图片地址须为最多2048字符的完整HTTP/HTTPS网址，不含账号密码、空白或控制字符。")
        result["image_urls"].append(value)
    return result


def locked_fashion_item(cursor, item_id):
    """先锁定物品再检查项目，串行处理首次资料保存和状态变更。"""
    cursor.execute(ITEM_VIEW + " WHERE i.id=%s FOR UPDATE OF i", (item_id,))
    item = cursor.fetchone()
    if item is None:
        raise AuthRequestError(404, "not_found", "该物品不存在。")
    if item["project"] != "fashion":
        raise AuthRequestError(409, "project_mismatch", "本次编辑和启停仅支持服装物品。")
    if item["status"] == "archived":
        raise AuthRequestError(409, "invalid_state", "归档物品本次不可编辑或恢复。")
    return item


def record_item_change(cursor, item_id, action, detail):
    cursor.execute(
        "INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,%s,%s,%s,%s)",
        (g.admin_session["admin_id"], action, "item", str(item_id), json.dumps({"project": "fashion", **detail}), fingerprint("ip", client_ip())),
    )


def write_item(item_id, profile=None, status=None):
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            lock_admin_session(cursor)
            item = locked_fashion_item(cursor, item_id)
            if profile is not None:
                # 更新列表明确列出的五个字段，已有size_chart完全不触碰。
                cursor.execute(
                    "INSERT INTO fashion_item_profile(item_id,name,description,material,care_instructions,image_urls) "
                    "VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name),description=VALUES(description),"
                    "material=VALUES(material),care_instructions=VALUES(care_instructions),image_urls=VALUES(image_urls)",
                    (item_id, profile["name"], profile["description"], profile["material"], profile["care_instructions"], json.dumps(profile["image_urls"], ensure_ascii=False)),
                )
                cursor.execute("UPDATE item SET updated_at=CURRENT_TIMESTAMP WHERE id=%s", (item_id,))
                record_item_change(cursor, item_id, "item.profile.save", {})
            elif status != item["status"]:
                if status == "disabled" and item["status"] != "active":
                    raise AuthRequestError(409, "invalid_state", "只有启用的物品可以停用。")
                if status == "active":
                    cursor.execute("SELECT name FROM fashion_item_profile WHERE item_id=%s FOR UPDATE", (item_id,))
                    found = cursor.fetchone()
                    if not found or not isinstance(found["name"], str) or not 1 <= len(found["name"].strip()) <= 128:
                        raise AuthRequestError(409, "invalid_state", "请先保存有效的服装名称，再启用物品。")
                cursor.execute("UPDATE item SET status=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s", (status, item_id))
                record_item_change(cursor, item_id, "item.status.change", {"from": item["status"], "to": status})
            cursor.execute(ITEM_VIEW + " WHERE i.id=%s", (item_id,))
            result = item_views(cursor, [cursor.fetchone()])[0]
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(status="ok", data=result["profile"] if profile is not None else result)


@blueprint.route("/<int:item_id>", methods=["GET", "PATCH"])
def item_detail(item_id):
    if item_id < 1 or item_id > 18446744073709551615 or request.args:
        invalid("物品ID须为有效正整数，此接口不接收查询参数。")
    if request.method == "PATCH":
        data = request_json({"status"})
        if not isinstance(data["status"], str) or data["status"] not in {"active", "disabled"}:
            invalid("本次仅允许启用active或停用disabled，不修改款式编号或归档。")
        return write_item(item_id, status=data["status"])
    with get_database().cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute(ITEM_VIEW + " WHERE i.id=%s", (item_id,))
        found = cursor.fetchone()
        if found is None:
            raise AuthRequestError(404, "not_found", "该物品不存在。")
        result = item_views(cursor, [found])[0]
    return jsonify(status="ok", data=result)


@blueprint.put("/<int:item_id>/profile")
def save_profile(item_id):
    if item_id < 1 or item_id > 18446744073709551615:
        invalid("物品ID须为有效正整数。")
    return write_item(item_id, profile=normalized_profile())

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
    for row in rows:
        row["profile"] = profiles.get(row["id"])
        for field in ("created_at", "updated_at"):
            row[field] = iso_time(row[field]) if row[field] else None
    return rows


def create_item():
    data = request_json({"project", "item_uid"}, {"sku_code", "status"})
    project, uid, sku = data["project"], data["item_uid"], data.get("sku_code")
    if not isinstance(project, str) or project not in PROJECT_PREFIXES:
        invalid("请选择服装fashion或饰品jewelry项目。")
    if not isinstance(uid, str) or not re.fullmatch(PROJECT_PREFIXES[project] + r"-[0-9]{4}-[0-9]{6}", uid.strip()):
        invalid("物品编号须匹配所选项目：FASH-YYYY-NNNNNN或JEW-YYYY-NNNNNN；仅接受ASCII大写前缀、4位年份和6位序号。")
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
    allowed = {"page", "page_size", "project", "status", "keyword"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        invalid("查询参数不符合约定，不能重复或增加字段。")
    page, size = positive_integer("page", 1, 2147483647), positive_integer("page_size", 20, 100)
    conditions, values = [], []
    for name, options, column in (("project", PROJECT_PREFIXES, "p.code"), ("status", STATUSES, "i.status")):
        if name in request.args:
            value = request.args[name]
            if value not in options:
                invalid(f"{name}不在允许范围内。")
            conditions.append(column + "=%s")
            values.append(value)
    keyword = request.args.get("keyword", "")
    if len(keyword) > 128:
        invalid("关键词最长128字符。")
    keyword = keyword.strip()
    if keyword:
        keyword = "%" + keyword.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
        conditions.append("(i.item_uid LIKE %s ESCAPE '!' OR i.sku_code LIKE %s ESCAPE '!')")
        values.extend([keyword, keyword])
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with get_database().cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM item i JOIN project p ON p.id=i.project_id" + where, values)
        total = cursor.fetchone()["total"]
        cursor.execute(ITEM_VIEW + where + " ORDER BY i.id DESC LIMIT %s OFFSET %s", (*values, size, (page - 1) * size))
        items = item_views(cursor, list(cursor.fetchall()))
    return jsonify(status="ok", data={"items": items, "total": total, "page": page, "page_size": size})


@blueprint.route("", methods=["GET", "POST"])
def items():
    return list_items() if request.method in {"GET", "HEAD"} else create_item()
