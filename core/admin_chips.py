"""管理员芯片登记、绑定、密钥和配置核验；不连接卡片或换绑。"""

import json

from flask import Blueprint, g, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, lock_admin_session, request_json
from core.chip_registry import CHIP_COLUMNS, CHIP_JOINS, chip_view, normalize_uid, save_chip
from core.chip_binding import bind_chip_item, valid_id
from core.chip_keys import ChipKeyUnavailable, key_operation
from core.db import get_database
from core.auth_settings import client_ip, fingerprint
from core.admin_queries import (boolean_parameter, check_parameters, consistent_read, contains,
                                date_conditions, invalid, pagination, positive_integer)

blueprint = Blueprint("admin_chips", __name__, url_prefix="/api/admin/chips")
PROJECTS = {"fashion", "jewelry"}
STATUSES = {"pending", "bound", "disabled", "lost", "retired"}
ITEM_NAME = "CASE ip.code WHEN 'fashion' THEN fp.name WHEN 'jewelry' THEN jp.name END"
READ_JOINS = CHIP_JOINS + """ LEFT JOIN project ip ON ip.id=i.project_id
LEFT JOIN fashion_item_profile fp ON fp.item_id=i.id AND ip.code='fashion'
LEFT JOIN jewelry_item_profile jp ON jp.item_id=i.id AND ip.code='jewelry' """
READ_VIEW = "SELECT " + CHIP_COLUMNS + "," + ITEM_NAME + " AS item_name "


@blueprint.errorhandler(ChipKeyUnavailable)
def keys_unavailable(_error):
    return jsonify(status="error", code="service_unavailable", message="密钥配置或加密记录无法验证，请按真实卡核验手册检查；不要覆盖原记录或重新配卡。"), 503


def read_view(row):
    result = chip_view(row)
    result["keyword_matches"] = [field for field in ("chip_uid", "item_uid", "item_name") if result.pop("match_" + field, False)]
    return result


def list_chips():
    dates = {"created": "c.created_at", "updated": "c.updated_at", "provisioned": "c.provisioned_at"}
    allowed = {"page", "page_size", "project", "status", "keyword", "batch_no", "registration_source", "has_item", "keys_generated", "provisioned"}
    allowed.update(f"{name}_{suffix}" for name in dates for suffix in ("from", "to"))
    check_parameters(allowed)
    page = positive_integer("page", 1, 2147483647)
    page_size = positive_integer("page_size", 20, 100)
    conditions, values = [], []
    for name, allowed_values, column in (("project", PROJECTS, "p.code"), ("status", STATUSES, "c.chip_status"),
                                          ("registration_source", {"manual", "nfc_cool", "unknown"}, "c.registration_source")):
        value = request.args.get(name)
        if value is not None:
            if name == "project" and value == "unassigned":
                conditions.append("c.project_id IS NULL")
                continue
            if value not in allowed_values:
                invalid(f"{name}不在允许范围内。")
            conditions.append(column + "=%s")
            values.append(value)
    for name, column in (("has_item", "c.item_id"), ("keys_generated", "k.chip_id"), ("provisioned", "c.provisioned_at")):
        flag = boolean_parameter(name)
        if flag is not None:
            conditions.append(column + (" IS NOT NULL" if flag else " IS NULL"))
    if boolean_parameter("provisioned") is False and any(request.args.get("provisioned_" + suffix) is not None for suffix in ("from", "to")):
        invalid("未核验条件不能同时指定核验日期。")
    date_conditions(dates, conditions, values)
    batch = request.args.get("batch_no", "").strip()
    if len(batch) > 64:
        invalid("批次关键词最长64个字符。")
    if batch:
        conditions.append("c.batch_no LIKE %s ESCAPE '!'")
        values.append(contains(batch))
    keyword = request.args.get("keyword", "")
    if len(keyword) > 128:
        invalid("关键词最长128个字符。")
    keyword = keyword.strip()
    matches, match_values = "", []
    if keyword:
        expressions = ["REPLACE(c.chip_uid,':','') LIKE %s ESCAPE '!'", "i.item_uid LIKE %s ESCAPE '!'", ITEM_NAME + " LIKE %s ESCAPE '!'"]
        match_values = [contains(keyword.replace(":", "").upper() or keyword), contains(keyword), contains(keyword)]
        conditions.append("(" + " OR ".join(expressions) + ")")
        values.extend(match_values)
        matches = "," + ",".join(f"({expression}) AS match_{field}" for expression, field in zip(expressions, ("chip_uid", "item_uid", "item_name"))) + " "
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with consistent_read() as cursor:
        cursor.execute("SELECT COUNT(*) AS total " + READ_JOINS + where, values)
        total = cursor.fetchone()["total"]
        paging = pagination(total, page, page_size)
        cursor.execute(READ_VIEW + matches + READ_JOINS + where + " ORDER BY c.id DESC LIMIT %s OFFSET %s", (*match_values, *values, page_size, (paging["page"] - 1) * page_size))
        items = [read_view(row) for row in cursor.fetchall()]
    return jsonify(status="ok", data={"items": items, **paging})


@blueprint.route("/<int:chip_id>", methods=["GET", "PATCH"])
def chip_detail(chip_id):
    if not valid_id(chip_id) or request.args:
        invalid("芯片ID须为有效正整数，此接口不接收查询参数。")
    if request.method == "PATCH":
        data = request_json({"batch_no"})
        batch = data["batch_no"]
        if batch is not None and (not isinstance(batch, str) or len(batch.strip()) > 64):
            invalid("批次须为最多64字符的文字，null或空串表示清空。")
        batch = batch.strip() or None if batch is not None else None
        connection = get_database()
        connection.begin()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                lock_admin_session(cursor)
                cursor.execute("SELECT batch_no FROM chip WHERE id=%s FOR UPDATE", (chip_id,))
                previous = cursor.fetchone()
                if previous is None:
                    raise AuthRequestError(404, "not_found", "该芯片不存在。")
                if previous["batch_no"] != batch:
                    cursor.execute("UPDATE chip SET batch_no=%s,updated_at=CURRENT_TIMESTAMP WHERE id=%s", (batch, chip_id))
                    cursor.execute("INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,%s,%s,%s,%s)",
                                   (g.admin_session["admin_id"], "chip.batch.update", "chip", str(chip_id),
                                    json.dumps({"from": previous["batch_no"], "to": batch}, ensure_ascii=False), fingerprint("ip", client_ip())))
                cursor.execute(READ_VIEW + READ_JOINS + " WHERE c.id=%s", (chip_id,))
                result = read_view(cursor.fetchone())
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    else:
        with consistent_read() as cursor:
            cursor.execute(READ_VIEW + READ_JOINS + " WHERE c.id=%s", (chip_id,))
            row = cursor.fetchone()
            if row is None:
                raise AuthRequestError(404, "not_found", "该芯片不存在。")
            result = read_view(row)
    return jsonify(status="ok", data=result)


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


@blueprint.post("/<int:chip_id>/bind-item")
def bind_item(chip_id):
    data = request_json({"item_id"})
    if not valid_id(chip_id) or not valid_id(data["item_id"]):
        invalid("芯片和物品ID须为有效正整数。")
    return jsonify(status="ok", data=bind_chip_item(chip_id, data["item_id"]))


@blueprint.post("/<int:chip_id>/generate-keys")
def generate_keys(chip_id):
    request_json(set())
    if not valid_id(chip_id):
        invalid("芯片ID须为有效正整数。")
    return jsonify(status="ok", data=key_operation(chip_id, "generate"))


@blueprint.post("/<int:chip_id>/keys")
def view_keys(chip_id):
    data = request_json({"confirm"})
    if not valid_id(chip_id) or data["confirm"] is not True:
        invalid("请明确确认查看密钥。")
    return jsonify(status="ok", data=key_operation(chip_id, "view"))


@blueprint.post("/<int:chip_id>/confirm-provisioning")
def confirm_provisioning(chip_id):
    data = request_json({"readings", "management_confirmed"})
    if not valid_id(chip_id) or data["management_confirmed"] is not True or not isinstance(data["readings"], list) or len(data["readings"]) != 2:
        invalid("请提供两条读数，并确认K0认证及文件权限已人工核对。")
    return jsonify(status="ok", data=key_operation(chip_id, "confirm", data["readings"]))
