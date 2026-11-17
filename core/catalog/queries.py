"""管理目录的列表、详情、动态与统计接口实现。"""

from datetime import datetime, timedelta, timezone
import re

from flask import current_app, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, lock_admin_session, request_json
from core.admin_queries import (
    check_parameters,
    consistent_read,
    contains,
    date_conditions,
    invalid,
    pagination,
    positive_integer,
)
from core.auth_settings import iso_time
from core.catalog.audit import AUDIT_ACTIONS, AUDIT_LABELS, audit, audit_event
from core.catalog.common import (
    account_uid,
    chip_state_before_loss,
    fail,
    now,
    project_id,
    public_account_uid,
    row,
    text,
    view,
)
from core.catalog.orders import (
    HAS_CLAIM_CODE,
    ORDER_ITEM_JOIN,
    ORDER_STOCK_FILTER,
    ORDER_UNIT_SELECT,
    PHYSICAL_AVAILABLE,
    item_order,
    order_candidate_conditions,
)
from core.chip_binding import valid_id
from core.db import get_database
from core.test_batches import filter_source, require_test_environment, select_source, source


def list_page(cursor, select, joined, conditions, values, *, order="id DESC", select_values=()):
    page, size = positive_integer("page", 1, 2147483647), positive_integer("page_size", 10, 100)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    total = row(cursor, "SELECT COUNT(*) AS total " + joined + where, values)["total"]
    paging = pagination(total, page, size)
    cursor.execute(
        select + " " + joined + where + " ORDER BY " + order + " LIMIT %s OFFSET %s",
        (*select_values, *values, size, (paging["page"] - 1) * size),
    )
    return {"items": [view(x) for x in cursor.fetchall()], **paging}


STYLE_SELECT = (
    "SELECT "
    + select_source("style", "s")
    + ",s.*,p.code AS project,(SELECT COUNT(*) FROM product_issue r WHERE r.style_id=s.id) AS issue_count,(SELECT COUNT(*) FROM digital_item d JOIN product_issue r ON r.id=d.issue_id WHERE r.style_id=s.id) AS item_count,(SELECT COUNT(*) FROM digital_item d JOIN product_issue r ON r.id=d.issue_id JOIN item i ON i.id=d.item_id WHERE r.style_id=s.id AND i.status='active') AS active_item_count"
)


STYLE_JOIN = "FROM product_style s JOIN project p ON p.id=s.project_id"


ISSUE_SELECT = (
    "SELECT "
    + select_source("issue", "r")
    + ",r.*,s.name AS style_name,s.code AS style_code,p.code AS project,(SELECT COUNT(*) FROM digital_item d WHERE d.issue_id=r.id) AS item_count"
)


ISSUE_JOIN = "FROM product_issue r JOIN product_style s ON s.id=r.style_id JOIN project p ON p.id=s.project_id"


ITEM_SELECT = (
    "SELECT "
    + select_source("item", "i")
    + """,i.*,p.code AS project,d.issue_id,d.edition_number,d.sold,d.first_sold_at,d.sale_evidence,d.is_validation,d.quota_year,d.quota_used,d.quota_review,
 r.name AS issue_name,r.mode AS issue_mode,r.total AS issue_total,r.style_id,s.name,s.material,s.image_urls,
 w.physical_item_id,ph.physical_uid,w.installed_at,
 (SELECT nickname FROM user WHERE uid=o.user_id) AS owner_name,(SELECT phone_verified_at IS NOT NULL FROM user WHERE uid=o.user_id) AS owner_phone_verified,
 (SELECT BIN_TO_UUID(public_uid) FROM user WHERE uid=o.user_id) AS owner_public_uid,
 w.id AS whole_id,w.generation,w.spec,w.lost_at,w.loss_evidence,c.id AS chip_id,c.chip_uid,c.chip_status,c.provisioned_at,
 (k.chip_id IS NOT NULL) AS keys_generated,o.user_id AS owner_id"""
)


ITEM_JOIN = """FROM item i JOIN project p ON p.id=i.project_id LEFT JOIN digital_item d ON d.item_id=i.id
 LEFT JOIN product_issue r ON r.id=d.issue_id LEFT JOIN product_style s ON s.id=r.style_id
 LEFT JOIN whole_item w ON w.current_item_id=i.id LEFT JOIN physical_item ph ON ph.id=w.physical_item_id
 LEFT JOIN chip c ON c.item_id=i.id LEFT JOIN chip_key k ON k.chip_id=c.id
 LEFT JOIN ownership o ON o.active_item_id=i.id"""


CHIP_SELECT = (
    "SELECT "
    + select_source("chip", "c")
    + """,c.*,p.code AS project,i.item_uid,(k.chip_id IS NOT NULL) AS keys_generated,
 COALESCE(v.is_validation,0) AS is_validation,w.id AS candidate_id,w.item_id AS candidate_item_id"""
)


CHIP_JOIN = """FROM chip c LEFT JOIN project p ON p.id=c.project_id LEFT JOIN item i ON i.id=c.item_id
 LEFT JOIN chip_key k ON k.chip_id=c.id LEFT JOIN chip_validation v ON v.chip_id=c.id
 LEFT JOIN item_handover w ON w.pending_chip_id=c.id"""


ITEM_WORKFLOW_RULES = (
    ("archived", "i.status='archived'"),
    ("lost", "w.lost_at IS NOT NULL OR w.loss_evidence IS NOT NULL"),
    ("disabled", "i.status='disabled'"),
    ("missing_issue", "d.issue_id IS NULL"),
    ("assembly", "w.id IS NULL"),
    ("review", "c.id IS NULL OR c.id<>w.chip_id OR c.chip_status<>'bound'"),
    ("verification", "c.provisioned_at IS NULL OR c.last_verified_counter IS NULL"),
    ("activation", "i.status<>'active'"),
    ("held", "o.user_id IS NOT NULL"),
    ("claim", HAS_CLAIM_CODE),
    ("delivery", "d.sold=1"),
    ("review", "d.first_sold_at IS NOT NULL OR w.physical_item_id IS NULL"),
    ("sale", "ou.allocated_at IS NOT NULL"),
    ("allocation", "ou.id IS NOT NULL"),
    ("available", ORDER_STOCK_FILTER),
)


ITEM_WORKFLOW_STAGES = {stage for stage, _ in ITEM_WORKFLOW_RULES}


ITEM_WORKFLOW = (
    "CASE "
    + " ".join(f"WHEN {condition} THEN '{stage}'" for stage, condition in ITEM_WORKFLOW_RULES)
    + " ELSE 'review' END"
)


def orders():
    check_parameters({"page", "page_size", "keyword", "data_scope", "test_batch_id"})
    scope = request.args.get("data_scope", "business")
    _, args = filter_source("item", "so.id", scope, request.args.get("test_batch_id"))
    conditions, values = [], []
    if scope != "all":
        conditions.append("so.test_batch_id IS " + ("NOT NULL" if scope == "test" else "NULL"))
    if request.args.get("test_batch_id") is not None:
        conditions.append("so.test_batch_id=%s")
        values.append(args[-1])
    keyword = text(request.args, "keyword", 128)
    if keyword:
        conditions.append(
            "(so.external_order_no LIKE %s ESCAPE '!' OR so.channel LIKE %s ESCAPE '!')"
        )
        values.extend([contains(keyword)] * 2)
    select = """SELECT so.id,so.channel,so.external_order_no,so.created_at,so.test_batch_id,
        (SELECT COUNT(*) FROM sales_order_unit ou WHERE ou.order_id=so.id) AS unit_count,
        (SELECT COUNT(*) FROM sales_order_unit ou WHERE ou.order_id=so.id AND ou.delivered_at IS NOT NULL) AS delivered_count"""
    with consistent_read() as cursor:
        return jsonify(
            status="ok",
            data=list_page(
                cursor, select, "FROM sales_order so", conditions, values, order="so.id DESC"
            ),
        )


def order_detail(ident):
    check_parameters(set())
    with consistent_read() as cursor:
        order = view(row(cursor, "SELECT * FROM sales_order WHERE id=%s", (ident,)))
        cursor.execute(ORDER_UNIT_SELECT + " WHERE ou.order_id=%s ORDER BY ou.position", (ident,))
        order["units"] = [view(unit) for unit in cursor.fetchall()]
        return jsonify(status="ok", data=order)


def audit_actions():
    check_parameters(set())
    return jsonify(
        status="ok",
        data=[{"value": action, "label": label} for action, label in AUDIT_ACTIONS.items()],
    )


def listing(resource):
    allowed = {
        "styles": {"project"},
        "issues": {"project", "style_id", "status", "mode"},
        "items": {
            "project",
            "status",
            "issue_id",
            "is_validation",
            "sold",
            "whole_status",
            "style_id",
            "owner",
            "bindable",
            "order_stock",
            "order_unit_id",
            "workflow",
        },
        "chips": {
            "project",
            "status",
            "is_validation",
            "available",
            "configured",
            "registration_source",
            "compatible_project",
        },
        "users": {"exclude_id", "verified"},
        "physical-items": {"style_id", "available", "order_unit_id"},
        "audit": {"action", "operator", "date_from", "date_to", "item_id"},
    }
    if resource not in allowed:
        fail("未知查询资源。", 404, "not_found")
    check_parameters(
        {"page", "page_size", "keyword", "data_scope", "test_batch_id"} | allowed[resource]
    )
    keyword = request.args.get("keyword", "").strip()
    if len(keyword) > 128:
        invalid("关键词最长128字符。")
    conditions, values, select_values = [], [], []
    if resource == "styles":
        select, joined, order = STYLE_SELECT, STYLE_JOIN, "s.id DESC"
        if keyword:
            conditions.append("(s.name LIKE %s ESCAPE '!' OR s.code LIKE %s ESCAPE '!')")
            values.extend([contains(keyword)] * 2)
    elif resource == "issues":
        select, joined, order = ISSUE_SELECT, ISSUE_JOIN, "r.id DESC"
        if keyword:
            conditions.append(
                "(r.name LIKE %s ESCAPE '!' OR s.name LIKE %s ESCAPE '!' OR r.series LIKE %s ESCAPE '!' OR s.code LIKE %s ESCAPE '!')"
            )
            values.extend([contains(keyword)] * 4)
        if request.args.get("style_id"):
            conditions.append("r.style_id=%s")
            values.append(positive_integer("style_id", 1, 2147483647))
        if request.args.get("status"):
            if request.args["status"] not in {"draft", "confirmed"}:
                invalid("发行状态只支持draft或confirmed。")
            conditions.append(
                "r.confirmed_at IS "
                + ("NOT NULL" if request.args["status"] == "confirmed" else "NULL")
            )
        if request.args.get("mode"):
            if request.args["mode"] not in {"fixed", "period", "unlimited"}:
                invalid("发行方式不支持。")
            conditions.append("r.mode=%s")
            values.append(request.args["mode"])
    elif resource == "items":
        select, joined, order = ITEM_SELECT, ITEM_JOIN, "i.id DESC"
        select += ",ou.id AS order_unit_id,ou.allocated_at,ou.delivered_at,ouo.id AS order_id,ouo.external_order_no"
        select += f",{HAS_CLAIM_CODE} AS has_claim_code,{ITEM_WORKFLOW} AS workflow"
        joined += ORDER_ITEM_JOIN
        if keyword:
            columns = [
                "i.item_uid",
                "s.name",
                "c.chip_uid",
                "ph.physical_uid",
                "r.name",
                "ouo.external_order_no",
                "d.sale_evidence",
            ]
            conditions.append(
                "(" + " OR ".join(f"{column} LIKE %s ESCAPE '!'" for column in columns) + ")"
            )
            values.extend([contains(keyword)] * len(columns))
        for name, column in [
            ("status", "i.status"),
            ("issue_id", "d.issue_id"),
            ("style_id", "r.style_id"),
        ]:
            if request.args.get(name):
                if name == "status" and request.args[name] not in {
                    "draft",
                    "active",
                    "disabled",
                    "archived",
                }:
                    invalid("档案状态不支持。")
                conditions.append(column + "=%s")
                values.append(
                    positive_integer(name, 1, 2147483647)
                    if name in {"issue_id", "style_id"}
                    else request.args[name]
                )
        for name, column in [("is_validation", "d.is_validation"), ("sold", "d.sold")]:
            if name in request.args:
                if request.args[name] not in {"true", "false"}:
                    invalid("布尔筛选须为true或false。")
                conditions.append("COALESCE(" + column + ",0)=%s")
                values.append(request.args[name] == "true")
        if "bindable" in request.args:
            if request.args["bindable"] != "true":
                invalid("bindable仅接受true。")
            conditions.extend(
                ["i.status!='archived'", "d.issue_id IS NOT NULL", "w.id IS NULL", "c.id IS NULL"]
            )
        workflow = request.args.get("workflow")
        if workflow:
            if workflow not in ITEM_WORKFLOW_STAGES:
                invalid("办理阶段不支持。")
            conditions.append(f"({ITEM_WORKFLOW})=%s")
            values.append(workflow)
        if "order_stock" in request.args:
            if request.args["order_stock"] != "true":
                invalid("order_stock 仅接受 true。")
            conditions.append(ORDER_STOCK_FILTER)
        state = request.args.get("whole_status")
        if state:
            if state not in {"lost", "normal", "missing"}:
                invalid("整套物品状态不支持。")
            conditions.append(
                {
                    "lost": "w.id IS NOT NULL AND (w.lost_at IS NOT NULL OR w.loss_evidence IS NOT NULL)",
                    "normal": "w.id IS NOT NULL AND w.lost_at IS NULL AND w.loss_evidence IS NULL",
                    "missing": "w.id IS NULL",
                }[state]
            )
        if request.args.get("owner"):
            if request.args["owner"] not in {"yes", "no"}:
                invalid("持有筛选须为yes或no。")
            conditions.append(
                "o.user_id IS " + ("NOT NULL" if request.args["owner"] == "yes" else "NULL")
            )
    elif resource == "chips":
        select, joined, order = CHIP_SELECT, CHIP_JOIN, "c.id DESC"
        if keyword:
            conditions.append(
                "(c.chip_uid LIKE %s ESCAPE '!' OR i.item_uid LIKE %s ESCAPE '!' OR c.batch_no LIKE %s ESCAPE '!')"
            )
            values.extend([contains(keyword)] * 3)
        if request.args.get("status"):
            if request.args["status"] not in {"pending", "bound", "disabled", "lost", "retired"}:
                invalid("芯片状态不支持。")
            conditions.append("c.chip_status=%s")
            values.append(request.args["status"])
        if request.args.get("compatible_project"):
            if request.args["compatible_project"] not in {"fashion", "jewelry"}:
                invalid("类别不支持。")
            conditions.append("(p.code=%s OR c.project_id IS NULL)")
            values.append(request.args["compatible_project"])
        if "available" in request.args:
            if request.args["available"] != "true":
                invalid("available仅接受true。")
            conditions.extend(["c.chip_status='pending'", "c.item_id IS NULL", "w.id IS NULL"])
        if "is_validation" in request.args:
            if request.args["is_validation"] not in {"true", "false"}:
                invalid("验证筛选须为布尔值。")
            conditions.append("COALESCE(v.is_validation,0)=%s")
            values.append(request.args["is_validation"] == "true")
        if request.args.get("configured"):
            if request.args["configured"] not in {"yes", "no"}:
                invalid("配置筛选须为yes或no。")
            conditions.append(
                "c.provisioned_at IS "
                + ("NOT NULL" if request.args["configured"] == "yes" else "NULL")
            )
        if request.args.get("registration_source"):
            if request.args["registration_source"] not in {"manual", "nfc_cool", "unknown"}:
                invalid("登记来源不支持。")
            conditions.append("c.registration_source=%s")
            values.append(request.args["registration_source"])
    elif resource == "physical-items":
        select = "SELECT ph.*,s.name AS style_name,CASE WHEN EXISTS (SELECT 1 FROM whole_item w WHERE w.current_physical_id=ph.id) THEN 'installed' WHEN EXISTS (SELECT 1 FROM item_handover w WHERE w.pending_physical_id=ph.id) THEN 'prepared' WHEN EXISTS (SELECT 1 FROM whole_item w WHERE w.physical_item_id=ph.id) THEN 'replaced' ELSE 'available' END AS assembly_status"
        select += ",(SELECT order_id FROM sales_order_unit ou WHERE ou.physical_item_id=ph.id) AS order_id"
        joined, order = (
            "FROM physical_item ph JOIN product_style s ON s.id=ph.style_id",
            "ph.id DESC",
        )
        if keyword:
            conditions.append("(ph.physical_uid LIKE %s ESCAPE '!' OR ph.spec LIKE %s ESCAPE '!')")
            values.extend([contains(keyword)] * 2)
        if "style_id" in request.args:
            conditions.append("ph.style_id=%s")
            values.append(positive_integer("style_id", 1, 2147483647))
        if "available" in request.args:
            if request.args["available"] != "true":
                invalid("available仅接受true。")
            conditions.extend(PHYSICAL_AVAILABLE)
    elif resource == "users":
        if "verified" in request.args:
            if request.args["verified"] != "true":
                invalid("verified仅接受true。")
            conditions.append("u.phone_verified_at IS NOT NULL")
        if request.args.get("exclude_id"):
            conditions.append("u.uid<>%s")
            values.append(account_uid(request.args["exclude_id"]))
        select, joined, order = (
            "SELECT "
            + select_source("user", "u")
            + ",u.uid AS id,BIN_TO_UUID(u.public_uid) AS public_uid,u.nickname,CONCAT(LEFT(u.phone,3),'****',RIGHT(u.phone,4)) AS phone,(SELECT COUNT(*) FROM ownership o WHERE o.user_id=u.uid AND o.is_active=1) AS held_items",
            "FROM user u",
            "u.created_at DESC,u.uid DESC",
        )
        held_filter, held_args = filter_source(
            "item",
            "o.item_id",
            request.args.get("data_scope", "business"),
            request.args.get("test_batch_id"),
        )
        select = select.replace("o.is_active=1)", "o.is_active=1 AND " + held_filter + ")")
        select_values = held_args
        if keyword:
            conditions.append(
                "(u.nickname LIKE %s ESCAPE '!' OR u.uid=%s OR BIN_TO_UUID(u.public_uid)=%s)"
            )
            values.extend([contains(keyword), keyword, keyword])
    elif resource == "audit":
        # 审计的对象编号按原值匹配，不依赖连接与历史表的排序规则。
        select = """SELECT a.id,a.action,a.target_type,a.target_id,a.detail,a.created_at,u.username,
                         i.id IS NOT NULL AS object_exists,COALESCE(i.item_uid,ch.chip_uid) AS linked_code"""
        joined = """FROM admin_audit a LEFT JOIN admin_user u ON u.id=a.admin_id
                  LEFT JOIN item i ON a.target_type='item' AND i.id=CASE WHEN a.target_id REGEXP '^[1-9][0-9]{0,18}$' THEN CAST(a.target_id AS UNSIGNED) END
                  LEFT JOIN chip ch ON a.target_type='chip' AND ch.id=CASE WHEN a.target_id REGEXP '^[1-9][0-9]{0,18}$' THEN CAST(a.target_id AS UNSIGNED) END"""
        order = "a.id DESC"
        if keyword:
            conditions.append("""(a.action LIKE %s ESCAPE '!' OR a.target_id=%s
                OR JSON_UNQUOTE(JSON_EXTRACT(a.detail,'$.object_code')) LIKE %s ESCAPE '!'
                OR JSON_UNQUOTE(JSON_EXTRACT(a.detail,'$.summary')) LIKE %s ESCAPE '!'
                OR JSON_UNQUOTE(JSON_EXTRACT(a.detail,'$.external_order_no'))=%s
                OR i.item_uid LIKE %s ESCAPE '!' OR ch.chip_uid LIKE %s ESCAPE '!')""")
            values.extend(
                [
                    contains(keyword),
                    keyword,
                    contains(keyword),
                    contains(keyword),
                    keyword,
                    contains(keyword),
                    contains(keyword),
                ]
            )
        for name, column in [("action", "a.action"), ("operator", "u.username")]:
            if request.args.get(name):
                conditions.append(column + "=%s")
                values.append(request.args[name])
        if "item_id" in request.args:
            conditions.append("a.target_type='item' AND a.target_id=%s")
            values.append(str(positive_integer("item_id", 1, 2147483647)))
        date_conditions({"date": "a.created_at"}, conditions, values)
    else:
        fail("未知查询资源。", 404, "not_found")
    if resource != "audit":
        kind, alias = {
            "styles": ("style", "s"),
            "issues": ("issue", "r"),
            "items": ("item", "i"),
            "chips": ("chip", "c"),
            "users": ("user", "u"),
            "physical-items": ("physical", "ph"),
        }[resource]
        clause, args = filter_source(
            kind,
            alias + (".uid" if kind == "user" else ".id"),
            request.args.get("data_scope", "business"),
            request.args.get("test_batch_id"),
        )
        conditions.append(clause)
        values.extend(args)
    if request.args.get("project"):
        if resource not in {"styles", "issues", "items", "chips"}:
            invalid("此资源不支持类别。")
        if request.args["project"] not in {"fashion", "jewelry", "unassigned"}:
            invalid("类别不支持。")
        if request.args["project"] == "unassigned":
            if resource != "chips":
                invalid("只有芯片可暂不分配类别。")
            conditions.append("p.id IS NULL")
        else:
            conditions.append("p.code=%s")
            values.append(request.args["project"])
    with consistent_read() as cursor:
        if "order_unit_id" in request.args:
            order_candidate_conditions(cursor, resource, conditions, values)
        result = list_page(
            cursor, select, joined, conditions, values, order=order, select_values=select_values
        )
    if resource == "audit":
        for event in result["items"]:
            audit_event(event, event.pop("linked_code"))
    elif resource == "issues":
        for issue in result["items"]:
            issue.pop("rights", None)
    return jsonify(status="ok", data=result)


def detail(resource, ident):
    check_parameters(set())
    if not valid_id(ident) or ident > 2147483647:
        invalid("记录ID超出当前页面可处理范围。")
    with consistent_read() as cursor:
        if resource == "styles":
            result = view(row(cursor, STYLE_SELECT + " " + STYLE_JOIN + " WHERE s.id=%s", (ident,)))
        elif resource == "issues":
            result = view(row(cursor, ISSUE_SELECT + " " + ISSUE_JOIN + " WHERE r.id=%s", (ident,)))
            result.pop("rights", None)
            # 建议不预占身份或序号，事务提交仍检查唯一性与数量。
            cursor.execute(
                "SELECT edition_number FROM digital_item WHERE issue_id=%s AND edition_number IS NOT NULL",
                (ident,),
            )
            occupied = {x["edition_number"] for x in cursor.fetchall()}
            number = 1
            while number in occupied:
                number += 1
            result["suggested_edition_number"] = number
            prefix = (
                ("FASH" if result["project"] == "fashion" else "JEW")
                + "-"
                + str((now() + timedelta(hours=8)).year)
                + "-"
            )
            cursor.execute("SELECT item_uid FROM item WHERE item_uid LIKE %s", (prefix + "%",))
            used = {x["item_uid"].casefold() for x in cursor.fetchall()}
            candidate = 1
            while (prefix + str(candidate).zfill(6)).casefold() in used:
                candidate += 1
            while row(
                cursor, "SELECT id FROM item WHERE item_uid=%s", (prefix + str(candidate).zfill(6),)
            ):
                candidate += 1
            result["suggested_item_uid"] = prefix + str(candidate).zfill(6)
        elif resource == "chips":
            result = view(row(cursor, CHIP_SELECT + " " + CHIP_JOIN + " WHERE c.id=%s", (ident,)))
        elif resource == "physical-items":
            result = view(
                row(
                    cursor,
                    """SELECT ph.*,s.name AS style_name,
                w.item_id,ou.order_id,ou.id AS order_unit_id,
                CASE WHEN w.id IS NOT NULL THEN 'installed'
                WHEN EXISTS (SELECT 1 FROM item_handover h WHERE h.pending_physical_id=ph.id) THEN 'prepared'
                WHEN EXISTS (SELECT 1 FROM whole_item h WHERE h.physical_item_id=ph.id) THEN 'replaced'
                ELSE 'available' END AS assembly_status
                FROM physical_item ph JOIN product_style s ON s.id=ph.style_id
                LEFT JOIN whole_item w ON w.current_physical_id=ph.id
                LEFT JOIN sales_order_unit ou ON ou.physical_item_id=ph.id WHERE ph.id=%s""",
                    (ident,),
                )
            )
            result["test_batch_id"] = source(cursor, "physical", ident)
        elif resource == "items":
            result = view(
                row(
                    cursor,
                    f"{ITEM_SELECT},{ITEM_WORKFLOW} AS workflow {ITEM_JOIN}{ORDER_ITEM_JOIN} WHERE i.id=%s",
                    (ident,),
                )
            )
            result["order"] = item_order(cursor, ident)
            owners_sql = """SELECT o.id,o.user_id,o.bound_at,o.unbound_at,o.is_active,u.nickname,BIN_TO_UUID(u.public_uid) AS public_uid,
                                   CASE WHEN u.phone REGEXP '^[0-9]{11}$'
                                   THEN CONCAT(LEFT(u.phone,3),'****',RIGHT(u.phone,4)) END AS masked_phone
                            FROM ownership o JOIN user u ON u.uid=o.user_id
                            WHERE o.item_id=%s ORDER BY o.id DESC"""
            for key, sql in [
                (
                    "wholes",
                    "SELECT w.*,c.chip_uid,c.chip_status,ph.physical_uid FROM whole_item w JOIN chip c ON c.id=w.chip_id LEFT JOIN physical_item ph ON ph.id=w.physical_item_id WHERE w.item_id=%s ORDER BY w.generation DESC",
                ),
                (
                    "handovers",
                    "SELECT w.*,c.chip_uid,c.provisioned_at,ph.physical_uid,(SELECT nickname FROM user WHERE uid=w.owner_id) AS owner_name,(SELECT nickname FROM user WHERE uid=w.recipient_id) AS recipient_name,(SELECT BIN_TO_UUID(public_uid) FROM user WHERE uid=w.owner_id) AS owner_public_uid,(SELECT BIN_TO_UUID(public_uid) FROM user WHERE uid=w.recipient_id) AS recipient_public_uid FROM item_handover w JOIN chip c ON c.id=w.chip_id LEFT JOIN physical_item ph ON ph.id=w.physical_item_id WHERE w.item_id=%s ORDER BY w.id DESC",
                ),
                ("owners", owners_sql),
                (
                    "rights",
                    "SELECT kind,rule_version FROM digital_item_right WHERE item_id=%s ORDER BY kind",
                ),
            ]:
                cursor.execute(sql, (ident,))
                result[key] = [view(x) for x in cursor.fetchall()]
            if result["lost_at"] or result["loss_evidence"]:
                result["chip_state_before_loss"] = chip_state_before_loss(
                    cursor, ident, result["lost_at"]
                )
            year = (now() + timedelta(hours=8)).year
            if result["quota_year"] and result["quota_year"] < year and not result["quota_review"]:
                result.update(quota_year=year, quota_used=0)
            cursor.execute(
                "SELECT a.id,a.action,a.target_id,a.created_at,a.detail,u.username FROM admin_audit a LEFT JOIN admin_user u ON u.id=a.admin_id WHERE a.target_type='item' AND a.target_id=%s ORDER BY a.id DESC LIMIT 10",
                (str(ident),),
            )
            result["audit"] = [audit_event(view(x), result["item_uid"]) for x in cursor.fetchall()]
            code = row(
                cursor,
                "SELECT id,issued_at,expires_at,consumed_at,revoked_at FROM item_claim_code WHERE item_id=%s ORDER BY id DESC LIMIT 1",
                (ident,),
            )
            result["claim_code_status"] = view(code) if code else None
            if result["style_id"]:
                result["style"] = view(
                    row(
                        cursor,
                        STYLE_SELECT + " " + STYLE_JOIN + " WHERE s.id=%s",
                        (result["style_id"],),
                    )
                )
            if result["issue_id"]:
                result["issue"] = view(
                    row(
                        cursor,
                        ISSUE_SELECT + " " + ISSUE_JOIN + " WHERE r.id=%s",
                        (result["issue_id"],),
                    )
                )
                result["issue"].pop("rights", None)
            if not result.get("style"):
                table = (
                    "fashion_item_profile"
                    if result["project"] == "fashion"
                    else "jewelry_item_profile"
                )
                legacy = row(cursor, f"SELECT * FROM {table} WHERE item_id=%s", (ident,))
                if legacy:
                    from core.media_assets import map_profile_images

                    legacy = view(legacy)
                    map_profile_images(cursor, {ident: legacy}, context="admin")
                result["legacy_profile"] = legacy
        else:
            fail("未知查询资源。", 404, "not_found")
    return jsonify(status="ok", data=result)


def reveal_holder_phone(item_id, ownership_id):
    return reveal_phone(
        """SELECT i.item_uid, BIN_TO_UUID(u.public_uid) AS public_uid, u.phone
           FROM ownership o JOIN user u ON u.uid=o.user_id JOIN item i ON i.id=o.item_id
           WHERE o.id=%s AND o.item_id=%s FOR SHARE""",
        (ownership_id, item_id),
        item_id=item_id,
        ownership_id=ownership_id,
    )


def user_card(uid):
    check_parameters(set())
    with consistent_read() as cursor:
        profile = view(
            row(
                cursor,
                """SELECT BIN_TO_UUID(public_uid) AS public_uid,nickname,
                                      CASE WHEN phone REGEXP '^[0-9]{11}$'
                                      THEN CONCAT(LEFT(phone,3),'****',RIGHT(phone,4)) END AS masked_phone
                                      FROM user WHERE public_uid=UUID_TO_BIN(%s)""",
                (public_account_uid(uid),),
            )
        )
        return jsonify(status="ok", data=profile)


def reveal_user_phone(uid):
    return reveal_phone(
        "SELECT BIN_TO_UUID(public_uid) AS public_uid,phone FROM user WHERE public_uid=UUID_TO_BIN(%s) FOR SHARE",
        (public_account_uid(uid),),
    )


def reveal_phone(query, args, *, item_id=None, ownership_id=None):
    request_json(set(), max_bytes=1024)
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            lock_admin_session(cursor)
            holder = row(cursor, query, args)
            if not holder or not re.fullmatch(r"[0-9]{11}", holder["phone"]):
                fail("该账户没有可查看的手机号。", 404, "not_found")
            action = "viewHolderPhone" if item_id is not None else "viewUserPhone"
            audit(
                cursor,
                action,
                item_id if item_id is not None else holder["public_uid"],
                {
                    "object_type": "item" if item_id is not None else "user",
                    "object_code": holder.get("item_uid") or holder["public_uid"],
                    "operation": AUDIT_LABELS[action],
                    "outcome": "已查看",
                    "summary": f"查看了账户 {holder['public_uid']} 的完整手机号。",
                    "user_uid": holder["public_uid"],
                    "ownership_id": ownership_id,
                },
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return jsonify(status="ok", data={"phone": holder["phone"]})


def reveal_claim_code(item_id, code_id):
    from core.public_account import claim_code_for_admin, transaction

    check_parameters(set())
    request_json(set(), max_bytes=1024)
    with transaction() as cursor:
        lock_admin_session(cursor)
        item = view(row(cursor, "SELECT item_uid FROM item WHERE id=%s FOR UPDATE", (item_id,)))
        result = claim_code_for_admin(cursor, item_id, code_id)
        audit(
            cursor,
            "viewClaimCode",
            item_id,
            {
                "object_type": "item",
                "object_code": item["item_uid"],
                "operation": AUDIT_LABELS["viewClaimCode"],
                "outcome": "已查看",
                "summary": "查看了有效期内的交付认领码。",
                "claim_code_id": code_id,
            },
        )
    return jsonify(status="ok", data=result)


def tap_window(timestamp, scope, period):
    if scope not in {"sold", "all"} or period not in {"7d", "30d", "all"}:
        invalid("统计口径或时间范围不支持。")
    conditions, values = ["s.verify_result='pass'", "s.created_at<=%s"], [timestamp]
    if scope == "sold":
        conditions.extend(
            ["d.sold=1", "d.first_sold_at IS NOT NULL", "s.created_at>=d.first_sold_at"]
        )
    if period != "all":
        day = (timestamp + timedelta(hours=8)).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=6 if period == "7d" else 29, hours=8)
        conditions.append("s.created_at>=%s")
        values.append(day)
    return conditions, values


def tap_cutoff(timestamp):
    cutoff = request.args.get("as_of")
    if not cutoff:
        return timestamp
    try:
        value = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        if value.tzinfo is not None and value.year >= 1000:
            return min(timestamp, value.astimezone(timezone.utc).replace(tzinfo=None))
    except (ValueError, OverflowError):
        pass
    invalid("统计截止时间须为带时区的有效时间。")


def activity():
    check_parameters(
        {
            "item_id",
            "item_uid",
            "issue_id",
            "style_id",
            "chip_id",
            "event",
            "date_from",
            "date_to",
            "page",
            "page_size",
            "data_scope",
            "test_batch_id",
            "scope",
            "range",
            "as_of",
        }
    )
    tap_keys = {"scope", "range", "as_of", "chip_id"}
    if tap_keys.intersection(request.args) and request.args.get("event") != "tap":
        invalid("触碰统计口径仅用于有效触碰明细。")
    tap_args = []
    tap_filter = ["s.verify_result='pass'"]
    if request.args.get("event") == "tap":
        timestamp = tap_cutoff(datetime.now(timezone.utc).replace(tzinfo=None))
        tap_filter, tap_args = tap_window(
            timestamp, request.args.get("scope", "all"), request.args.get("range", "all")
        )
        if request.args.get("chip_id"):
            tap_filter.append("s.chip_id=%s")
            tap_args.append(positive_integer("chip_id", 1, 2147483647))
    event = request.args.get("event")
    sources = {
        "tap": (
            "SELECT s.id,s.item_id,s.created_at AS occurred_at,'tap' AS event,BIN_TO_UUID(u.public_uid),s.actor_state FROM scan_log s JOIN items i ON i.id=s.item_id LEFT JOIN digital_item d ON d.item_id=i.id LEFT JOIN user u ON u.uid=s.actor_user_uid WHERE "
            + " AND ".join(tap_filter)
        ),
        "claim": (
            "SELECT o.id,o.item_id,o.bound_at,'claim',BIN_TO_UUID(u.public_uid),NULL FROM ownership o JOIN items i ON i.id=o.item_id JOIN user u ON u.uid=o.user_id WHERE o.bind_source='user_self'"
        ),
        "first_delivery": (
            "SELECT ou.id,ou.item_id,ou.delivered_at,'first_delivery',NULL,NULL FROM sales_order_unit ou JOIN items i ON i.id=ou.item_id WHERE ou.delivered_at IS NOT NULL"
        ),
        "delivery": (
            "SELECT h.id,h.item_id,h.completed_at,IF(h.kind='resale','resale','renewal'),BIN_TO_UUID(u.public_uid),NULL FROM item_handover h JOIN items i ON i.id=h.item_id JOIN user u ON u.uid=h.recipient_id WHERE h.completed_at IS NOT NULL"
        ),
    }
    if event not in {None, "tap", "claim", "first_delivery", "resale", "renewal"}:
        invalid("未知用户动态类型。")
    if event:
        sources = {key: sources[key] for key in (event if event in sources else "delivery",)}
    clause, values = filter_source(
        "item",
        "i.id",
        request.args.get("data_scope", "business"),
        request.args.get("test_batch_id"),
    )
    conditions = [clause]
    for key, column in [("item_id", "i.id"), ("issue_id", "d.issue_id")]:
        if key in request.args:
            conditions.append(column + "=%s")
            values.append(positive_integer(key, 1, 2147483647))
    if "style_id" in request.args:
        conditions.append("(SELECT style_id FROM product_issue WHERE id=d.issue_id)=%s")
        values.append(positive_integer("style_id", 1, 2147483647))
    if "item_uid" in request.args:
        conditions.append("i.item_uid=%s")
        values.append(text(request.args, "item_uid", 32, required=True))
    event_conditions, event_values = [], []
    date_conditions({"date": "e.occurred_at"}, event_conditions, event_values)
    if event in {"resale", "renewal"}:
        event_conditions.append("e.event=%s")
        event_values.append(event)
    cte = (
        "WITH items AS (SELECT i.id,i.item_uid,d.issue_id FROM item i LEFT JOIN digital_item d ON d.item_id=i.id WHERE "
        + " AND ".join(conditions)
        + "), events(id,item_id,occurred_at,event,user_uid,actor_state) AS ("
        + " UNION ALL ".join(sources.values())
        + ") "
    )
    joined = " FROM events e JOIN items i ON i.id=e.item_id"
    if event_conditions:
        joined += " WHERE " + " AND ".join(event_conditions)
    params = (*values, *tap_args, *event_values)
    page, size = positive_integer("page", 1, 2147483647), positive_integer("page_size", 10, 100)
    with consistent_read() as cursor:
        total = row(cursor, cte + "SELECT COUNT(*) AS total" + joined, params)["total"]
        paging = pagination(total, page, size)
        cursor.execute(
            cte
            + "SELECT CONCAT(e.event,'-',e.id) AS id,e.event,e.occurred_at,e.user_uid,e.actor_state,i.id AS item_id,i.item_uid,i.issue_id"
            + joined
            + " ORDER BY e.occurred_at DESC,e.event,e.id DESC LIMIT %s OFFSET %s",
            (*params, size, (paging["page"] - 1) * size),
        )
        return jsonify(status="ok", data={"items": [view(x) for x in cursor.fetchall()], **paging})


def statistics():
    check_parameters(
        {
            "scope",
            "range",
            "as_of",
            "project",
            "item_id",
            "chip_id",
            "data_scope",
            "test_batch_id",
            "style_id",
            "issue_id",
            "page",
            "page_size",
            "detail_filter",
        }
    )
    scope = request.args.get("scope", "sold")
    period = request.args.get("range", "30d")
    if scope not in {"sold", "all"} or period not in {"7d", "30d", "all"}:
        invalid("统计口径或时间范围不支持。")
    detail_filter = request.args.get("detail_filter")
    detail_filters = {"touched": "events.tap_count>0", "repeat": "events.tap_count>=2"}
    if scope == "sold":
        detail_filters.update(
            zero="d.first_sold_at IS NOT NULL AND events.tap_count IS NULL",
            missing_sale="d.first_sold_at IS NULL",
        )
    if detail_filter is not None and detail_filter not in detail_filters:
        invalid("所选明细筛选与触碰口径不一致。")
    with consistent_read() as cursor:
        timestamp = tap_cutoff(row(cursor, "SELECT UTC_TIMESTAMP(6) AS t")["t"])
        conditions, values = tap_window(timestamp, scope, period)
        data_scope = request.args.get("data_scope", "business")
        batch = request.args.get("test_batch_id")
        clause, args = filter_source("item", "s.item_id", data_scope, batch)
        conditions.append(clause)
        values.extend(args)
        for key, column in [("item_id", "s.item_id"), ("chip_id", "s.chip_id")]:
            if request.args.get(key):
                conditions.append(column + "=%s")
                values.append(positive_integer(key, 1, 2147483647))
        if request.args.get("project"):
            conditions.append("i.project_id=%s")
            values.append(project_id(cursor, request.args["project"]))
        for key, column in [
            ("style_id", "(SELECT style_id FROM product_issue WHERE id=d.issue_id)"),
            ("issue_id", "d.issue_id"),
        ]:
            if request.args.get(key):
                conditions.append(column + "=%s")
                values.append(positive_integer(key, 1, 2147483647))
        joined = (
            " FROM scan_log s JOIN item i ON i.id=s.item_id LEFT JOIN digital_item d ON d.item_id=s.item_id WHERE "
            + " AND ".join(conditions)
        )
        cursor.execute(
            "SELECT DATE(s.created_at+INTERVAL 8 HOUR) AS day,COUNT(*) AS total"
            + joined
            + " GROUP BY day ORDER BY day",
            values,
        )
        daily = [{"day": str(x["day"]), "total": x["total"]} for x in cursor.fetchall()]
        today = (timestamp + timedelta(hours=8)).date()
        first = (
            today - timedelta(days=6 if period == "7d" else 29)
            if period != "all"
            else datetime.fromisoformat(daily[0]["day"]).date() if daily else None
        )
        if first:
            counts_by_day = {x["day"]: x["total"] for x in daily}
            daily = [
                {
                    "day": (first + timedelta(days=n)).isoformat(),
                    "total": counts_by_day.get((first + timedelta(days=n)).isoformat(), 0),
                }
                for n in range((today - first).days + 1)
            ]
        cursor.execute(
            "SELECT s.chip_id,s.chip_uid,COUNT(*) AS total"
            + joined
            + " GROUP BY s.chip_id,s.chip_uid ORDER BY s.chip_id",
            values,
        )
        by_chip = cursor.fetchall()
        item_filter, item_args = filter_source("item", "i.id", data_scope, batch)
        inventory = row(
            cursor,
            "SELECT COUNT(*) AS items,COALESCE(SUM(i.status='active'),0) AS active_items FROM item i WHERE "
            + item_filter,
            item_args,
        )
        cursor.execute(
            f"SELECT {ITEM_WORKFLOW} AS workflow,COUNT(*) AS total {ITEM_JOIN}{ORDER_ITEM_JOIN}"
            " WHERE " + item_filter + " GROUP BY workflow",
            item_args,
        )
        workflow_counts = dict.fromkeys(ITEM_WORKFLOW_STAGES, 0)
        workflow_counts.update(
            {record["workflow"]: record["total"] for record in cursor.fetchall()}
        )
        chip_filter, chip_args = filter_source("chip", "x.id", data_scope, batch)
        inventory.update(
            row(
                cursor,
                "SELECT COALESCE(SUM(x.chip_status='pending' AND x.item_id IS NULL AND NOT EXISTS(SELECT 1 FROM item_handover h WHERE h.pending_chip_id=x.id)),0) AS pending_chips,COALESCE(SUM(x.item_id IS NOT NULL AND x.provisioned_at IS NULL AND x.chip_status<>'retired'),0) AS unconfigured_chips FROM chip x WHERE "
                + chip_filter,
                chip_args,
            )
        )
        item_conditions = [item_filter]
        for key, column in [
            ("style_id", "r.style_id"),
            ("issue_id", "d.issue_id"),
            ("item_id", "i.id"),
        ]:
            if request.args.get(key):
                item_conditions.append(column + "=%s")
                item_args.append(positive_integer(key, 1, 2147483647))
        if request.args.get("project"):
            item_conditions.append("i.project_id=%s")
            item_args.append(project_id(cursor, request.args["project"]))
        item_join = " FROM item i LEFT JOIN digital_item d ON d.item_id=i.id LEFT JOIN product_issue r ON r.id=d.issue_id LEFT JOIN ownership o ON o.active_item_id=i.id LEFT JOIN user u ON u.uid=o.user_id"
        item_where = " AND ".join(item_conditions)
        counts = row(
            cursor,
            "SELECT COUNT(*) AS items,COALESCE(SUM(COALESCE(d.sold,0)),0) AS sold_items,COUNT(o.user_id) AS claimed_items,COUNT(DISTINCT o.user_id) AS holders"
            + item_join
            + " WHERE "
            + item_where,
            item_args,
        )
        event_query = (
            "SELECT s.item_id,COUNT(*) AS tap_count,MAX(s.created_at) AS last_tap"
            + joined
            + " GROUP BY s.item_id"
        )
        eligible = item_conditions + (["d.sold=1"] if scope == "sold" else [])
        page, size = positive_integer("page", 1, 2147483647), positive_integer("page_size", 10, 100)
        detail_join = (
            item_join + " LEFT JOIN (" + event_query + ") events ON events.item_id=i.id WHERE "
        )
        detail_aggregates = ",".join(
            f"COUNT(CASE WHEN {condition} THEN 1 END) AS `{key}`"
            for key, condition in detail_filters.items()
        )
        detail_counts = row(
            cursor,
            "SELECT COUNT(*) AS all_items,COALESCE(SUM(events.tap_count),0) AS event_total,"
            + detail_aggregates
            + detail_join
            + " AND ".join(eligible),
            (*values, *item_args),
        )
        event_total = int(detail_counts.pop("event_total"))
        all_items = detail_counts.pop("all_items")
        if detail_filter:
            eligible.append(detail_filters[detail_filter])
        total = detail_counts[detail_filter] if detail_filter else all_items
        paging = pagination(total, page, size)
        cursor.execute(
            "SELECT i.id,i.item_uid,d.edition_number,d.issue_id,d.sold,r.total AS issue_total,u.uid AS owner_id,BIN_TO_UUID(u.public_uid) AS owner_public_uid,u.nickname AS owner_name,COALESCE(events.tap_count,0) AS tap_count,events.last_tap"
            + detail_join
            + " AND ".join(eligible)
            + " ORDER BY i.id DESC LIMIT %s OFFSET %s",
            (*values, *item_args, size, (paging["page"] - 1) * size),
        )
        details = {"items": [view(x) for x in cursor.fetchall()], **paging}
        holder_filter, holder_args = filter_source("user", "u.uid", data_scope, batch)
        holder_query = (
            "SELECT u.uid AS id,BIN_TO_UUID(u.public_uid) AS public_uid,u.nickname,COUNT(*) AS held_items"
            + item_join
            + " WHERE "
            + item_where
            + " AND u.uid IS NOT NULL AND "
            + holder_filter
            + " GROUP BY u.uid,u.public_uid,u.nickname"
        )
        holder_total = row(
            cursor,
            "SELECT COUNT(*) AS total FROM (" + holder_query + ") holder_groups",
            (*item_args, *holder_args),
        )["total"]
        holder_paging = pagination(holder_total, page, size)
        cursor.execute(
            holder_query + " ORDER BY u.uid DESC LIMIT %s OFFSET %s",
            (*item_args, *holder_args, size, (holder_paging["page"] - 1) * size),
        )
        holders = {"items": cursor.fetchall(), **holder_paging}
        for kind in ("chip", "user"):
            clause, args = filter_source(
                kind, "x.uid" if kind == "user" else "x.id", data_scope, batch
            )
            counts[kind + "s"] = row(
                cursor, "SELECT COUNT(*) AS n FROM " + kind + " x WHERE " + clause, args
            )["n"]
    return jsonify(
        status="ok",
        data={
            "total": event_total,
            "touched_items": detail_counts["touched"],
            "touch_item_counts": detail_counts,
            "workflow_counts": workflow_counts,
            "daily": daily,
            "by_chip": by_chip,
            "counts": counts,
            "inventory": inventory,
            "details": details,
            "holders": holders,
            "as_of": iso_time(timestamp),
            "scope": scope,
            "range": period,
            "timezone": "Asia/Shanghai",
            "claim_service_available": False,
        },
    )


def test_batches():
    check_parameters({"page", "page_size", "keyword", "data_scope"})
    with consistent_read() as cursor:
        result = list_page(cursor, "SELECT b.*", "FROM test_batch b", [], [], order="b.id DESC")
    try:
        require_test_environment(current_app.config)
        result["writable"] = True
    except AuthRequestError:
        result["writable"] = False
    return jsonify(status="ok", data=result)


def batch_preview(batch):
    from core.test_batches import preview

    check_parameters(set())
    require_test_environment(current_app.config)
    with consistent_read() as cursor:
        result = preview(cursor, batch)
    return jsonify(status="ok", data=result)


def h5_preview(item_id):
    from core.public_account import item_metadata

    check_parameters(set())
    with consistent_read() as cursor:
        item = view(
            row(
                cursor,
                """SELECT i.id,i.item_uid,s.name,s.description,s.material,s.care_instructions,s.image_urls,w.generation,w.spec,d.quota_year,d.quota_used,d.quota_review
                           FROM item i LEFT JOIN digital_item d ON d.item_id=i.id LEFT JOIN product_issue r ON r.id=d.issue_id
                           LEFT JOIN product_style s ON s.id=r.style_id LEFT JOIN whole_item w ON w.current_item_id=i.id
                           WHERE i.id=%s""",
                (item_id,),
            )
        )
        item.update(item_metadata(cursor, item_id))
        item["image_urls"] = [
            url
            for url in item["image_urls"] or []
            if re.fullmatch(r"/api/admin/catalog/styles/[1-9][0-9]*/images/[a-f0-9]{32}", url)
        ]
    return jsonify(status="ok", data=item)
