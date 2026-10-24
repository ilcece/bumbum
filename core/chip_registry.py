"""网页和手机共用芯片编号、去重和保存规则；调用者负责事务及权限锁。"""

import json
import re

import pymysql

from core.admin_auth import AuthRequestError
from core.auth_settings import client_ip, fingerprint, iso_time

CHIP_VIEW = """
SELECT c.id,c.chip_uid,p.code AS project,c.chip_status,c.item_id,i.item_uid,
       c.batch_no,c.provisioned_at,(k.chip_id IS NOT NULL) AS keys_generated,
       c.created_at,c.updated_at
FROM chip c LEFT JOIN project p ON p.id=c.project_id
LEFT JOIN item i ON i.id=c.item_id
LEFT JOIN chip_key k ON k.chip_id=c.id
"""


def normalize_uid(value):
    """只接受完整14位十六进制或7组冒号格式，不随意删除非法字符。"""
    if not isinstance(value, str):
        raise AuthRequestError(400, "invalid_param", "芯片UID须为文字。")
    value = value.strip()
    if not re.fullmatch(r"(?:[0-9A-Fa-f]{14}|(?:[0-9A-Fa-f]{2}:){6}[0-9A-Fa-f]{2})", value):
        raise AuthRequestError(400, "invalid_param", "芯片UID须为14位十六进制，或7组冒号分隔的两位字符。")
    compact = value.replace(":", "").upper()
    return ":".join(compact[index:index + 2] for index in range(0, 14, 2))


def chip_view(row):
    result = dict(row)
    result["keys_generated"] = bool(result["keys_generated"])
    for field in ("provisioned_at", "created_at", "updated_at"):
        result[field] = iso_time(result[field]) if result[field] else None
    return result


def save_chip(cursor, uid, *, admin_id, source, project=None, batch=None):
    """权限锁内调用；新登记和操作记录在同一事务中，重复时不更新原资料。"""
    project_id = None
    if project is not None:
        cursor.execute("SELECT id FROM project WHERE code=%s", (project,))
        project_row = cursor.fetchone()
        if project_row is None:
            raise pymysql.OperationalError("初始项目资料尚未就绪。")
        project_id = project_row["id"]
    cursor.execute(
        "INSERT INTO chip (chip_uid,project_id,batch_no) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)",
        (uid, project_id, batch),
    )
    is_new, chip_id = cursor.rowcount == 1, cursor.lastrowid
    # 当前读避免旧快照漏掉另一事务刚提交的重复UID。
    cursor.execute(CHIP_VIEW + " WHERE c.id=%s FOR UPDATE OF c", (chip_id,))
    chip = chip_view(cursor.fetchone())
    if project is not None and chip["project"] is not None and chip["project"] != project:
        raise AuthRequestError(409, "project_mismatch", "该 UID 已登记，所属项目与本次选择不同。原记录未修改，请按 UID 查询。")
    if is_new:
        cursor.execute(
            "INSERT INTO admin_audit (admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,%s,%s,%s,%s)",
            (admin_id, "chip.register", "chip", str(chip_id),
             json.dumps({"project": project, "source": source}), fingerprint("ip", client_ip())),
        )
    return chip, is_new
