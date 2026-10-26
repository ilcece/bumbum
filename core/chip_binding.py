"""首次绑定芯片与物品；业务变更和操作记录在同一事务中提交。"""

import json

from flask import g
import pymysql

from core.admin_auth import AuthRequestError, lock_admin_session
from core.auth_settings import client_ip, fingerprint
from core.chip_registry import CHIP_VIEW, chip_view
from core.db import get_database

MAX_ID = 18446744073709551615


def valid_id(value):
    """布尔值和浮点数不能冒充JSON整数。"""
    return type(value) is int and 1 <= value <= MAX_ID


def record_binding(cursor, chip_id, item_id, project, previous_project):
    cursor.execute(
        "INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,%s,%s,%s,%s)",
        (g.admin_session["admin_id"], "chip.bind_item", "chip", str(chip_id),
         json.dumps({"item_id": item_id, "project": project, "previous_project": previous_project,
                     "from_status": "pending", "to_status": "bound"}), fingerprint("ip", client_ip())),
    )


def bind_chip_item(chip_id, item_id):
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            lock_admin_session(cursor)
            cursor.execute("SELECT id,project_id,status FROM item WHERE id=%s FOR UPDATE", (item_id,))
            item = cursor.fetchone()
            if item is None:
                raise AuthRequestError(404, "not_found", "目标物品不存在，请重新查询。")
            cursor.execute("SELECT id,project_id,item_id,chip_status FROM chip WHERE id=%s FOR UPDATE", (chip_id,))
            chip = cursor.fetchone()
            if chip is None:
                raise AuthRequestError(404, "not_found", "该芯片不存在，请重新查询。")
            if chip["chip_status"] in {"disabled", "lost"}:
                raise AuthRequestError(409, "invalid_state", "停用或丢失的芯片不能绑定物品。")
            if chip["chip_status"] != "pending" or chip["item_id"] is not None:
                raise AuthRequestError(409, "already_bound", "该芯片已有绑定，原关联未修改，请按UID查询。")
            if item["status"] == "archived":
                raise AuthRequestError(409, "invalid_state", "归档物品不可绑定，请重新选择。")
            if chip["project_id"] is not None and chip["project_id"] != item["project_id"]:
                raise AuthRequestError(409, "project_mismatch", "芯片与物品项目不一致，原资料未修改。")
            cursor.execute("SELECT code FROM project WHERE id=%s", (item["project_id"],))
            project = cursor.fetchone()["code"]
            if project not in {"fashion", "jewelry"}:
                raise AuthRequestError(409, "project_mismatch", "目标物品项目不支持绑定。")
            previous_project = None if chip["project_id"] is None else project
            try:
                cursor.execute(
                    "UPDATE chip SET project_id=%s,item_id=%s,chip_status='bound',updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                    (item["project_id"], item_id, chip_id),
                )
            except pymysql.IntegrityError as error:
                # 仅此UPDATE的唯一冲突代表目标占用，不能误报后面的审计故障。
                if error.args[0] == 1062:
                    raise AuthRequestError(409, "item_already_has_chip", "该物品已关联其他芯片，请重新查询选择。") from None
                raise
            record_binding(cursor, chip_id, item_id, project, previous_project)
            cursor.execute(CHIP_VIEW + " WHERE c.id=%s", (chip_id,))
            result = chip_view(cursor.fetchone())
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except pymysql.MySQLError:
            # 连接已断时保留原异常；不能声称已提交的结果已被撤销。
            pass
        raise
    return result
