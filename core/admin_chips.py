"""管理员手动登记与查询芯片；不生成密钥、不写卡、不改绑定。"""

import json
import re

from flask import Blueprint, g, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, lock_admin_session, request_json
from core.auth_settings import client_ip, fingerprint, iso_time
from core.db import get_database

blueprint = Blueprint("admin_chips", __name__, url_prefix="/api/admin/chips")
PROJECTS = {"fashion", "jewelry"}
STATUSES = {"pending", "bound", "disabled", "lost"}
CHIP_VIEW = """
SELECT c.id,c.chip_uid,p.code AS project,c.chip_status,c.item_id,i.item_uid,
       c.batch_no,c.provisioned_at,(k.chip_id IS NOT NULL) AS keys_generated,
       c.created_at,c.updated_at
FROM chip c LEFT JOIN project p ON p.id=c.project_id
LEFT JOIN item i ON i.id=c.item_id
LEFT JOIN chip_key k ON k.chip_id=c.id
"""


def invalid(message):
    raise AuthRequestError(400, "invalid_param", message)


def normalize_uid(value):
    """只接受完整14位十六进制或7组冒号格式，不随意删除非法字符。"""
    if not isinstance(value, str):
        invalid("芯片UID须为文字。")
    value = value.strip()
    if not re.fullmatch(r"(?:[0-9A-Fa-f]{14}|(?:[0-9A-Fa-f]{2}:){6}[0-9A-Fa-f]{2})", value):
        invalid("芯片UID须为14位十六进制，或7组冒号分隔的两位字符。")
    compact = value.replace(":", "").upper()
    return ":".join(compact[index:index + 2] for index in range(0, 14, 2))


def chip_view(row):
    result = dict(row)
    result["keys_generated"] = bool(result["keys_generated"])
    for field in ("provisioned_at", "created_at", "updated_at"):
        result[field] = iso_time(result[field]) if result[field] else None
    return result


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
        project_id = None
        if project is not None:
            cursor.execute("SELECT id FROM project WHERE code=%s", (project,))
            project_row = cursor.fetchone()
            if project_row is None:
                raise pymysql.OperationalError("初始项目资料尚未就绪。")
            project_id = project_row["id"]
        # 唯一索引负责并发去重；重复时只取回原ID，不覆盖项目、批次或状态。
        cursor.execute(
            "INSERT INTO chip (chip_uid,project_id,batch_no) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)",
            (uid, project_id, batch),
        )
        is_new, chip_id = cursor.rowcount == 1, cursor.lastrowid
        # 当前读避免项目查询建立的旧快照漏掉另一事务刚提交的重复UID。
        cursor.execute(CHIP_VIEW + " WHERE c.id=%s FOR UPDATE OF c", (chip_id,))
        chip = chip_view(cursor.fetchone())
        if project is not None and chip["project"] is not None and chip["project"] != project:
            raise AuthRequestError(409, "project_mismatch", "该 UID 已登记，所属项目与本次选择不同。原记录未修改，请按 UID 查询。")
        if is_new:
            cursor.execute(
                "INSERT INTO admin_audit (admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,%s,%s,%s,%s)",
                (g.admin_session["admin_id"], "chip.register", "chip", str(chip_id),
                 json.dumps({"project": project, "source": "manual"}), fingerprint("ip", client_ip())),
            )
    connection.commit()
    return jsonify(status="ok", data={"chip": chip, "is_new": is_new})


@blueprint.route("", methods=["GET", "POST"])
def chips():
    if request.method in {"GET", "HEAD"}:
        return list_chips()
    return register_chip()
