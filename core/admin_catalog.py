"""数字档案管理路由，以及统一写事务、审计和幂等回执。"""

import hashlib
import json
import re

from flask import Blueprint, current_app, g, jsonify
import pymysql

from core.admin_auth import AuthRequestError, lock_admin_session, request_json
from core.admin_queries import check_parameters, consistent_read, invalid
from core.catalog.audit import audit, audit_detail, audit_item_id, audit_snapshot
from core.catalog.common import (
    ITEM_ACTIONS,
    boolean,
    create_physical,
    current,
    decoded,
    digital,
    fail,
    field_set,
    integer,
    locked,
    now,
    order_reference,
    project_id,
    row,
    sale_time,
    text,
)
from core.catalog.inventory import (
    chip_action,
    complete,
    create_item,
    issue_action,
    issue_save,
    item_action,
    style_save,
)
from core.catalog.media import style_image, style_image_status
from core.catalog.orders import (
    create_order,
    lock_order_unit,
    order_origin,
    order_unit_action,
    require_order_match,
)
from core.catalog.queries import (
    activity,
    audit_actions,
    batch_preview,
    detail,
    h5_preview,
    listing,
    order_detail,
    orders,
    reveal_claim_code,
    reveal_holder_phone,
    reveal_user_phone,
    statistics,
    test_batches,
    user_card,
)
from core.chip_binding import valid_id
from core.chip_registry import normalize_uid, save_chip
from core.db import get_database
from core.test_batches import lock_batch, mark, require_test_environment, source

blueprint = Blueprint("admin_catalog", __name__, url_prefix="/api/admin/catalog")


def command(action):
    check_parameters(set())
    envelope = request_json({"request_id", "payload"}, max_bytes=100000)
    if action == "receipt":
        payload = envelope["payload"]
        if (
            not isinstance(payload, dict)
            or set(payload) != {"request_id"}
            or not isinstance(payload["request_id"], str)
        ):
            invalid("核对须提供原请求编号。")
        with consistent_read() as cursor:
            found = row(
                cursor,
                "SELECT result FROM admin_operation WHERE request_id=%s AND admin_id=%s",
                (payload["request_id"], g.admin_session["admin_id"]),
            )
            if not found:
                fail("尚无已提交回执，请明确重试原请求。", 404, "not_found")
        return jsonify(status="ok", data=decoded(found["result"]))
    token = envelope["request_id"]
    action_payload = envelope["payload"]
    if (
        not isinstance(token, str)
        or not re.fullmatch(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", token)
        or not isinstance(action_payload, dict)
    ):
        invalid("请提供有效请求编号和字段对象。")
    digest = hashlib.sha256(
        json.dumps(
            action_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()
    connection = get_database()
    connection.begin()
    transient = {}
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            lock_admin_session(cursor)
            prior = row(
                cursor, "SELECT * FROM admin_operation WHERE request_id=%s FOR UPDATE", (token,)
            )
            if prior:
                if (
                    prior["admin_id"] != g.admin_session["admin_id"]
                    or prior["action"] != action
                    or prior["payload_hash"] != digest
                ):
                    fail("请求编号已用于其他操作，禁止替换输入重试。")
                result = decoded(prior["result"])
            else:
                audited_item_id = audit_item_id(cursor, action, action_payload)
                if audited_item_id:
                    row(cursor, "SELECT id FROM item WHERE id=%s FOR UPDATE", (audited_item_id,))
                before = audit_snapshot(cursor, audited_item_id)
                if action == "createOrder":
                    result = create_order(cursor, action_payload)
                elif action in {
                    "matchOrderUnit",
                    "orderPhysical",
                    "allocateOrderUnit",
                    "releaseOrderUnit",
                }:
                    result = order_unit_action(cursor, action, action_payload)
                elif action == "clearTestBatch":
                    from core.test_batches import cleanup

                    require_test_environment(current_app.config)
                    field_set(action_payload, {"batch_id", "confirmed"})
                    if action_payload["confirmed"] is not True:
                        invalid("请明确确认整批清理。")
                    result = cleanup(cursor, integer(action_payload, "batch_id"))
                elif action == "register":
                    field_set(
                        action_payload,
                        {"chip_uid"},
                        {"project", "batch_no", "is_validation", "test_batch_id"},
                    )
                    project = action_payload.get("project")
                    if project is not None:
                        project_id(cursor, project)
                    batch = text(action_payload, "batch_no", 64)
                    chip, is_new = save_chip(
                        cursor,
                        normalize_uid(action_payload["chip_uid"]),
                        project=project,
                        batch=batch,
                        admin_id=g.admin_session["admin_id"],
                        source="manual",
                    )
                    if is_new and boolean(action_payload, "is_validation"):
                        cursor.execute(
                            "INSERT INTO chip_validation(chip_id,is_validation) VALUES (%s,1)",
                            (chip["id"],),
                        )
                    if action_payload.get("test_batch_id") is not None:
                        require_test_environment(current_app.config)
                        if not is_new and source(cursor, "chip", chip["id"]) != integer(
                            action_payload, "test_batch_id"
                        ):
                            fail("既有芯片不能改写测试来源。")
                        mark(cursor, "chip", chip["id"], integer(action_payload, "test_batch_id"))
                    result = {"id": chip["id"], "is_new": is_new, "chip_uid": chip["chip_uid"]}
                elif action == "saleBatch":
                    field_set(
                        action_payload, {"item_ids", "confirmed", "evidence"}, {"first_sold_at"}
                    )
                    sale_time(action_payload)
                    ids = action_payload["item_ids"]
                    if (
                        not isinstance(ids, list)
                        or not 1 <= len(ids) <= 100
                        or any(not valid_id(n) or n > 2147483647 for n in ids)
                        or len(set(ids)) != len(ids)
                    ):
                        invalid("请选择1至100个不同的有效物品。")
                    origins = {source(cursor, "item", ident) for ident in ids}
                    if len(origins) != 1:
                        fail("一次操作不能混用业务或不同测试批次对象。")
                    for ident in sorted(ids):
                        row(cursor, "SELECT id FROM item WHERE id=%s FOR UPDATE", (ident,))
                        previous = audit_snapshot(cursor, ident)
                        item_action(
                            cursor,
                            "sale",
                            {
                                "item_id": ident,
                                "confirmed": action_payload["confirmed"],
                                "evidence": action_payload["evidence"],
                                **(
                                    {"first_sold_at": action_payload["first_sold_at"]}
                                    if action_payload.get("first_sold_at") is not None
                                    and not digital(cursor, ident)["first_sold_at"]
                                    else {}
                                ),
                            },
                        )
                        audit(
                            cursor,
                            action,
                            ident,
                            audit_detail(
                                cursor,
                                action,
                                token,
                                action_payload,
                                {"id": ident, "batch_size": len(ids)},
                                previous,
                            ),
                        )
                    result = {"ids": sorted(ids)}
                elif action == "style":
                    result = style_save(cursor, action_payload)
                elif action == "issue":
                    result = issue_save(cursor, action_payload)
                elif action in {"confirmIssue", "deleteIssue", "seal"}:
                    result = issue_action(cursor, action, action_payload)
                elif action == "item":
                    result = create_item(cursor, action_payload)
                elif action == "assembleOrderItem":
                    identity_fields = {"issue_id", "item_uid", "edition_number", "is_validation"}
                    assembly_fields = {"chip_id", "physical_item_id", "installed"}
                    field_set(
                        action_payload,
                        {"issue_id", "item_uid"} | assembly_fields,
                        {"edition_number", "is_validation", "order_unit_id"},
                    )
                    unit_id = integer(action_payload, "order_unit_id", optional=True)
                    if unit_id:
                        unit = lock_order_unit(cursor, unit_id)
                        if unit["item_id"] or unit["physical_item_id"] != integer(
                            action_payload, "physical_item_id"
                        ):
                            fail("订单件的实物已变化，请回原订单件核对。")
                        order_origin(cursor, unit, "issue", integer(action_payload, "issue_id"))
                        require_order_match(
                            unit, locked(cursor, "physical_item", unit["physical_item_id"])
                        )
                    result = create_item(
                        cursor,
                        {
                            key: action_payload[key]
                            for key in identity_fields
                            if key in action_payload
                        },
                    )
                    item_action(
                        cursor,
                        "installAssembly",
                        {
                            "item_id": result["id"],
                            **{key: action_payload[key] for key in assembly_fields},
                        },
                        order_unit_id=unit_id,
                    )
                    if unit_id:
                        cursor.execute(
                            "UPDATE sales_order_unit SET item_id=%s WHERE id=%s",
                            (result["id"], unit_id),
                        )
                        result.update(
                            order_id=unit["order_id"],
                            order_unit_id=unit_id,
                            external_order_no=unit["external_order_no"],
                        )
                elif action == "createPhysicalItem":
                    result = create_physical(cursor, action_payload)
                elif action == "orderSale" and "order_unit_id" in action_payload:
                    field_set(action_payload, {"order_unit_id", "item_id", "first_sold_at"})
                    unit = lock_order_unit(cursor, integer(action_payload, "order_unit_id"))
                    if not unit["allocated_at"] or unit["item_id"] != integer(
                        action_payload, "item_id"
                    ):
                        fail("请先为该件确认数字物品分配。")
                    whole = current(cursor, unit["item_id"])
                    if whole["physical_item_id"] != unit["physical_item_id"]:
                        fail("当前实体与订单分配不一致，请先核对。")
                    require_order_match(
                        unit, locked(cursor, "physical_item", unit["physical_item_id"])
                    )
                    action_payload = {
                        key: action_payload[key] for key in ("item_id", "first_sold_at")
                    }
                    action_payload.update(
                        channel=unit["channel"], external_order_no=unit["external_order_no"]
                    )
                    result = item_action(cursor, action, action_payload, order_unit_id=unit["id"])
                    result.update(
                        order_id=unit["order_id"],
                        order_unit_id=unit["id"],
                        external_order_no=unit["external_order_no"],
                    )
                elif action in {"issueClaimCode", "reissueClaimCode"}:
                    from core.public_account import issue_claim_code

                    field_set(
                        action_payload,
                        {"item_id", "delivery_reference", "confirmed"},
                        {"channel", "external_order_no"} if action == "issueClaimCode" else set(),
                    )
                    if action_payload["confirmed"] is not True:
                        invalid("请确认已核对实际首次交付。")
                    item_id = integer(action_payload, "item_id")
                    lock_batch(cursor, source(cursor, "item", item_id))
                    if "channel" in action_payload or "external_order_no" in action_payload:
                        if not {"channel", "external_order_no"} <= action_payload.keys():
                            invalid("请提供完整成交来源。")
                        sale = row(
                            cursor,
                            "SELECT sold,sale_evidence FROM digital_item WHERE item_id=%s FOR UPDATE",
                            (item_id,),
                        )
                        if (
                            not sale
                            or not sale["sold"]
                            or sale["sale_evidence"] != order_reference(action_payload)
                        ):
                            fail("当前售出记录与本订单不一致，请核对后再确认交付。")
                    linked = row(
                        cursor, "SELECT id FROM sales_order_unit WHERE item_id=%s", (item_id,)
                    )
                    if linked:
                        unit = lock_order_unit(cursor, linked["id"])
                        if not unit["allocated_at"] or not digital(cursor, item_id)["sold"]:
                            fail("请先在对应订单件完成分配及首次成交。")
                    if linked and action == "issueClaimCode":
                        whole = current(cursor, item_id)
                        if whole["physical_item_id"] != unit["physical_item_id"]:
                            fail("实际交付的实体与分配不一致，请核对。")
                        require_order_match(
                            unit, locked(cursor, "physical_item", unit["physical_item_id"])
                        )
                    result = issue_claim_code(
                        cursor,
                        item_id,
                        g.admin_session["admin_id"],
                        text(action_payload, "delivery_reference", 128, required=True),
                        reissue=action == "reissueClaimCode",
                    )
                    if linked and action == "issueClaimCode":
                        cursor.execute(
                            "UPDATE sales_order_unit SET delivered_at=%s,delivery_whole_id=%s,first_claim_code_id=%s WHERE id=%s",
                            (now(), whole["id"], result["claim_code_id"], unit["id"]),
                        )
                        result.update(
                            order_id=unit["order_id"],
                            order_unit_id=unit["id"],
                            external_order_no=unit["external_order_no"],
                        )
                    transient["claim_code"] = result.pop("claim_code")
                elif action == "complete":
                    result = complete(cursor, action_payload)
                elif action in ITEM_ACTIONS:
                    result = item_action(cursor, action, action_payload)
                elif action in {"validationChip", "deleteChip", "chipState", "chipBatch"}:
                    result = chip_action(cursor, action, action_payload)
                else:
                    fail("当前操作尚未开放。", 404, "not_found")
                if action not in {"saleBatch", "register"} and not result.get("already_completed"):
                    audit(
                        cursor,
                        action,
                        result.get("id"),
                        audit_detail(cursor, action, token, action_payload, result, before),
                    )
                cursor.execute(
                    "INSERT INTO admin_operation(request_id,admin_id,action,payload_hash,result) VALUES (%s,%s,%s,%s,%s)",
                    (
                        token,
                        g.admin_session["admin_id"],
                        action,
                        digest,
                        json.dumps(result, ensure_ascii=False),
                    ),
                )
        connection.commit()
    except pymysql.IntegrityError as error:
        connection.rollback()
        if error.args[0] in {1062, 1452}:
            fail("编号已存在、对象已占用或关联已变化，请重新查询。", 409, "conflict")
        raise
    except AuthRequestError as error:
        connection.rollback()
        if action == "complete" and error.status == 409:
            connection.begin()
            try:
                with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    lock_admin_session(cursor)
                    ident = audit_item_id(cursor, action, action_payload)
                    item = audit_snapshot(cursor, ident)
                    audit(
                        cursor,
                        action,
                        ident,
                        {
                            "object_type": "item",
                            "object_code": item["item_uid"] if item else None,
                            "operation": "交付确认受阻",
                            "outcome": "受阻",
                            "summary": error.message,
                            "work_id": action_payload.get("work_id"),
                        },
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        raise
    except Exception:
        connection.rollback()
        raise
    return jsonify(status="ok", data={**result, **transient})


blueprint.add_url_rule("/orders", endpoint="orders", view_func=orders, methods=["GET"])
blueprint.add_url_rule(
    "/orders/<int:ident>", endpoint="order_detail", view_func=order_detail, methods=["GET"]
)
blueprint.add_url_rule(
    "/audit/actions", endpoint="audit_actions", view_func=audit_actions, methods=["GET"]
)
blueprint.add_url_rule("/<resource>", endpoint="listing", view_func=listing, methods=["GET"])
blueprint.add_url_rule(
    "/<resource>/<int:ident>", endpoint="detail", view_func=detail, methods=["GET"]
)
blueprint.add_url_rule(
    "/items/<int:item_id>/owners/<int:ownership_id>/phone",
    endpoint="reveal_holder_phone",
    view_func=reveal_holder_phone,
    methods=["POST"],
)
blueprint.add_url_rule(
    "/users/<string:uid>/card", endpoint="user_card", view_func=user_card, methods=["GET"]
)
blueprint.add_url_rule(
    "/users/<string:uid>/phone",
    endpoint="reveal_user_phone",
    view_func=reveal_user_phone,
    methods=["POST"],
)
blueprint.add_url_rule(
    "/items/<int:item_id>/claim-codes/<int:code_id>/reveal",
    endpoint="reveal_claim_code",
    view_func=reveal_claim_code,
    methods=["POST"],
)
blueprint.add_url_rule("/actions/<action>", endpoint="command", view_func=command, methods=["POST"])
blueprint.add_url_rule("/activity", endpoint="activity", view_func=activity, methods=["GET"])
blueprint.add_url_rule("/statistics", endpoint="statistics", view_func=statistics, methods=["GET"])
blueprint.add_url_rule(
    "/styles/<int:style_id>/images/<asset_id>",
    endpoint="style_image",
    view_func=style_image,
    methods=["GET", "POST"],
)
blueprint.add_url_rule(
    "/styles/<int:style_id>/images/<asset_id>/status",
    endpoint="style_image_status",
    view_func=style_image_status,
    methods=["GET"],
)
blueprint.add_url_rule(
    "/test-batches", endpoint="test_batches", view_func=test_batches, methods=["GET"]
)
blueprint.add_url_rule(
    "/test-batches/<int:batch>/preview",
    endpoint="batch_preview",
    view_func=batch_preview,
    methods=["GET"],
)
blueprint.add_url_rule(
    "/items/<int:item_id>/h5-preview", endpoint="h5_preview", view_func=h5_preview, methods=["GET"]
)
