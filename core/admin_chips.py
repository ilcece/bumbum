"""管理员手动登记与查询芯片；不生成密钥、不写卡、不改绑定。"""

import re

from flask import Blueprint, g, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, lock_admin_session, request_json
from core.chip_registry import CHIP_VIEW, chip_view, normalize_uid, save_chip
from core.db import get_database

blueprint = Blueprint("admin_chips", __name__, url_prefix="/api/admin/chips")
PROJECTS = {"fashion", "jewelry"}
STATUSES = {"pending", "bound", "disabled", "lost"}


def invalid(message):
    raise AuthRequestError(400, "invalid_param", message)


def positive_integer(name, default, maximum):
    value = request.args.get(name, str(default))
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value) or int(value) > maximum:
        invalid(f"{name}须为1到{maximum}之间的整数。")
    return int(value)


def list_chips():
    allowed = {"page", "page_size", "project", "status", "keyword"}
    if set(request.args) - allowed or any(len(request.args.getlist(name)) != 1 for name in request.args):
        invalid("查询参数不符合约定，不能重复或增加字段。")
    page = positive_integer("page", 1, 2147483647)
    page_size = positive_integer("page_size", 20, 100)
    conditions, values = [], []
    for name, allowed_values, column in (("project", PROJECTS, "p.code"), ("status", STATUSES, "c.chip_status")):
        value = request.args.get(name)
        if value is not None:
            if name == "project" and value == "unassigned":
                conditions.append("c.project_id IS NULL")
                continue
            if value not in allowed_values:
                invalid(f"{name}不在允许范围内。")
            conditions.append(column + "=%s")
            values.append(value)
    keyword = request.args.get("keyword", "").strip()
    if len(request.args.get("keyword", "")) > 128:
        invalid("UID关键词最长128个字符。")
    if keyword:
        keyword = keyword.replace(":", "").upper().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        conditions.append("REPLACE(c.chip_uid,':','') LIKE %s ESCAPE '!'")
        values.append("%" + keyword + "%")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with get_database().cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM chip c LEFT JOIN project p ON p.id=c.project_id" + where, values)
        total = cursor.fetchone()["total"]
        cursor.execute(CHIP_VIEW + where + " ORDER BY c.id DESC LIMIT %s OFFSET %s", (*values, page_size, (page - 1) * page_size))
        items = [chip_view(row) for row in cursor.fetchall()]
    return jsonify(status="ok", data={"items": items, "total": total, "page": page, "page_size": page_size})


def register_chip():
    data = request_json({"chip_uid"}, {"project", "batch_no"})
    uid = normalize_uid(data["chip_uid"])
    project, batch = data.get("project"), data.get("batch_no")
    if project is not None and (not isinstance(project, str) or project not in PROJECTS):
        invalid("项目只能为fashion或jewelry，暂不分配请传null或省略。")
    if batch is not None:
        if not isinstance(batch, str) or not batch.strip() or len(batch.strip()) > 64:
            invalid("批次须为1到64个字符，留空请传null或省略。")
        batch = batch.strip()
    connection = get_database()
    connection.begin()
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        lock_admin_session(cursor)
        chip, is_new = save_chip(cursor, uid, project=project, batch=batch,
                                 admin_id=g.admin_session["admin_id"], source="manual")
    connection.commit()
    return jsonify(status="ok", data={"chip": chip, "is_new": is_new})


@blueprint.route("", methods=["GET", "POST"])
def chips():
    if request.method in {"GET", "HEAD"}:
        return list_chips()
    return register_chip()
