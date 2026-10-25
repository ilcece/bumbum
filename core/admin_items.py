"""物品草稿创建与真实列表；不编辑资料、状态或芯片绑定。"""

import json
import re

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
