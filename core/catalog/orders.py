"""订单逐件匹配、准备与分配；沿用调用方事务。"""

from flask import current_app, g

from core.admin_queries import invalid, positive_integer
from core.catalog.common import (
    create_physical,
    current,
    digital,
    fail,
    field_set,
    integer,
    locked,
    now,
    order_reference,
    row,
    text,
    view,
)
from core.test_batches import filter_source, lock_batch, require_test_environment, source

ORDER_ITEM_JOIN = " LEFT JOIN sales_order_unit ou ON ou.item_id=i.id LEFT JOIN sales_order ouo ON ouo.id=ou.order_id"


HAS_CLAIM_CODE = "EXISTS (SELECT 1 FROM item_claim_code cc WHERE cc.item_id=i.id)"


ORDER_STOCK_FILTER = (
    """i.status='active' AND d.issue_id IS NOT NULL AND d.sold=0 AND d.first_sold_at IS NULL
    AND w.physical_item_id IS NOT NULL AND w.lost_at IS NULL AND w.loss_evidence IS NULL
    AND c.chip_status='bound' AND c.id=w.chip_id AND c.provisioned_at IS NOT NULL
    AND c.last_verified_counter IS NOT NULL AND o.user_id IS NULL AND ou.id IS NULL AND NOT """
    + HAS_CLAIM_CODE
)


PHYSICAL_AVAILABLE = [
    "NOT EXISTS (SELECT 1 FROM whole_item w WHERE w.physical_item_id=ph.id)",
    "NOT EXISTS (SELECT 1 FROM item_handover w WHERE w.pending_physical_id=ph.id)",
    "NOT EXISTS (SELECT 1 FROM sales_order_unit ou WHERE ou.physical_item_id=ph.id)",
]


ORDER_UNIT_SELECT = """SELECT ou.*,so.channel,so.external_order_no,so.test_batch_id,
    ph.physical_uid,ph.spec,ph.style_id,ps.name AS physical_style_name,
    m.style_id AS expected_style_id,m.spec AS expected_spec,ms.name AS expected_style_name,
    CASE WHEN ph.id IS NULL OR m.style_id IS NULL THEN NULL
         ELSE ph.style_id=m.style_id AND (m.spec IS NULL OR BINARY ph.spec=BINARY m.spec) END AS physical_matches,
    i.item_uid,i.status AS item_status,d.sold,d.first_sold_at,
    w.id AS whole_id,w.generation,ch.id AS chip_id,ch.provisioned_at,ch.chip_status,
    w.lost_at,w.loss_evidence,
    old.generation AS delivered_generation,old.spec AS delivered_spec,
    old_ph.physical_uid AS delivered_physical_uid,old_ch.chip_uid AS delivered_chip_uid,
    BIN_TO_UUID(u.public_uid) AS holder_uid,
    first_code.delivery_reference AS first_delivery_reference,cc.id AS claim_code_id,cc.expires_at AS claim_expires_at,cc.consumed_at AS claim_consumed_at,
    cc.revoked_at AS claim_revoked_at
    FROM sales_order_unit ou JOIN sales_order so ON so.id=ou.order_id
    LEFT JOIN physical_item ph ON ph.id=ou.physical_item_id
    LEFT JOIN product_style ps ON ps.id=ph.style_id
    LEFT JOIN sales_order_unit_match m ON m.unit_id=ou.id
    LEFT JOIN product_style ms ON ms.id=m.style_id
    LEFT JOIN item i ON i.id=ou.item_id
    LEFT JOIN digital_item d ON d.item_id=i.id
    LEFT JOIN whole_item w ON w.current_item_id=i.id LEFT JOIN chip ch ON ch.id=w.chip_id
    LEFT JOIN whole_item old ON old.id=ou.delivery_whole_id
    LEFT JOIN physical_item old_ph ON old_ph.id=old.physical_item_id LEFT JOIN chip old_ch ON old_ch.id=old.chip_id
    LEFT JOIN ownership o ON o.active_item_id=i.id LEFT JOIN user u ON u.uid=o.user_id
    LEFT JOIN item_claim_code first_code ON first_code.id=ou.first_claim_code_id
    LEFT JOIN item_claim_code cc ON cc.id=(SELECT MAX(latest.id) FROM item_claim_code latest WHERE latest.item_id=i.id)"""


def item_order(cursor, item_id):
    found = row(cursor, ORDER_UNIT_SELECT + " WHERE ou.item_id=%s", (item_id,))
    return view(found) if found else None


def create_order(cursor, payload):
    field_set(payload, {"channel", "external_order_no", "units"}, {"test_batch_id"})
    order_reference(payload)
    batch = integer(payload, "test_batch_id", optional=True)
    if batch:
        require_test_environment(current_app.config)
        lock_batch(cursor, batch)
    units = payload["units"]
    if (
        not isinstance(units, list)
        or not 1 <= len(units) <= 100
        or any(not isinstance(unit, dict) for unit in units)
    ):
        invalid("每个订单须登记 1 至 100 件。")
    entries = []
    for pos, unit in enumerate(units, 1):
        field_set(unit, {"product_name"}, {"ordered_spec"})
        entries.append(
            (pos, text(unit, "product_name", 128, required=True), text(unit, "ordered_spec", 256))
        )
    channel, number = payload["channel"].strip(), payload["external_order_no"].strip()
    cursor.execute(
        "INSERT INTO sales_order(channel,external_order_no,test_batch_id,created_by) VALUES (%s,%s,%s,%s)",
        (channel, number, batch, g.admin_session["admin_id"]),
    )
    order_id = cursor.lastrowid
    cursor.executemany(
        "INSERT INTO sales_order_unit(order_id,position,product_name,ordered_spec) VALUES (%s,%s,%s,%s)",
        [(order_id, *entry) for entry in entries],
    )
    return {"id": order_id, "order_id": order_id, "external_order_no": number}


def lock_order_unit(cursor, unit_id):
    unit = row(cursor, "SELECT order_id FROM sales_order_unit WHERE id=%s", (unit_id,))
    if not unit:
        fail("订单件不存在。", 404, "not_found")
    order = view(row(cursor, "SELECT * FROM sales_order WHERE id=%s", (unit["order_id"],)))
    lock_batch(cursor, order["test_batch_id"])
    unit = view(row(cursor, "SELECT * FROM sales_order_unit WHERE id=%s FOR UPDATE", (unit_id,)))
    match = row(
        cursor,
        "SELECT style_id AS expected_style_id,spec AS expected_spec FROM sales_order_unit_match WHERE unit_id=%s",
        (unit_id,),
    )
    return {
        **unit,
        **(match or {}),
        "channel": order["channel"],
        "external_order_no": order["external_order_no"],
        "test_batch_id": order["test_batch_id"],
    }


def order_origin(cursor, unit, kind, ident):
    if source(cursor, kind, ident) != unit["test_batch_id"]:
        fail("请选用与订单同一数据范围和验收批次的对象。", 409, "batch_conflict")


def require_order_match(unit, physical):
    if not unit.get("expected_style_id"):
        fail("请先在订单件核对款式和规格。", 409, "order_match_required")
    if (
        not physical
        or physical["style_id"] != unit["expected_style_id"]
        or (unit["expected_spec"] is not None and physical["spec"] != unit["expected_spec"])
    ):
        fail("实物款式或规格与已核对的订单要求不一致。", 409, "order_item_mismatch")


def match_order_unit(cursor, unit, payload):
    field_set(payload, {"order_unit_id", "style_id"}, {"spec"})
    style = locked(cursor, "product_style", integer(payload, "style_id"))
    order_origin(cursor, unit, "style", style["id"])
    spec = text(payload, "spec", 256, required=bool(style["specs"] or unit["ordered_spec"]))
    if style["specs"] and spec not in style["specs"]:
        invalid("请选择款式目录中的实际规格。")
    if unit.get("expected_style_id") and unit["physical_item_id"]:
        fail("请先释放未售占用，再更正订单款式或规格。")
    if unit["item_id"] and digital(cursor, unit["item_id"])["sold"]:
        physical = locked(cursor, "physical_item", unit["physical_item_id"])
        require_order_match({"expected_style_id": style["id"], "expected_spec": spec}, physical)
    cursor.execute(
        """INSERT INTO sales_order_unit_match(unit_id,style_id,spec) VALUES (%s,%s,%s)
                 ON DUPLICATE KEY UPDATE style_id=%s,spec=%s""",
        (unit["id"], style["id"], spec, style["id"], spec),
    )
    return {"style_id": style["id"], "style_name": style["name"], "spec": spec}


def order_candidate_conditions(cursor, resource, conditions, values):
    unit_id = positive_integer("order_unit_id", 1, 2147483647)
    unit = view(
        row(
            cursor,
            """SELECT so.test_batch_id,m.style_id,m.spec
          FROM sales_order_unit ou JOIN sales_order so ON so.id=ou.order_id
          LEFT JOIN sales_order_unit_match m ON m.unit_id=ou.id WHERE ou.id=%s""",
            (unit_id,),
        )
    )
    if not unit["style_id"]:
        fail("请先在订单件核对款式和规格。", 409, "order_match_required")
    conditions.append("ph.style_id=%s")
    values.append(unit["style_id"])
    if unit["spec"] is not None:
        conditions.append("BINARY ph.spec=BINARY %s")
        values.append(unit["spec"])
    if resource == "items":
        conditions.extend([ORDER_STOCK_FILTER, "r.style_id=ph.style_id"])
    else:
        conditions.extend(PHYSICAL_AVAILABLE)
    batch = unit["test_batch_id"]
    clause, args = filter_source(
        "item" if resource == "items" else "physical",
        "i.id" if resource == "items" else "ph.id",
        "business" if batch is None else "test",
        batch,
    )
    conditions.append(clause)
    values.extend(args)


def order_unit_action(cursor, action, payload):
    unit_id = integer(payload, "order_unit_id")
    unit = lock_order_unit(cursor, unit_id)
    if unit["delivered_at"]:
        fail("已经交付，请从物品档案核对历史或办理售后。")
    match = None
    if action == "matchOrderUnit":
        match = match_order_unit(cursor, unit, payload)
    elif action == "orderPhysical":
        field_set(payload, {"order_unit_id"}, {"physical_item_id", "physical"})
        if unit["physical_item_id"] or unit["item_id"]:
            fail("该件已准备物品。请先核对或释放已有占用。")
        if ("physical_item_id" in payload) == ("physical" in payload):
            invalid("请选择已有实物或登记新实物。")
        if "physical" in payload:
            if not isinstance(payload["physical"], dict):
                invalid("请输入实体资料。")
            expected = {
                "style_id": integer(payload["physical"], "style_id"),
                "spec": text(payload["physical"], "spec", 256) or "",
            }
            require_order_match(unit, expected)
            order_origin(cursor, unit, "style", expected["style_id"])
            ident = create_physical(cursor, payload["physical"])["id"]
        else:
            ident = integer(payload, "physical_item_id")
        physical = locked(cursor, "physical_item", ident)
        require_order_match(unit, physical)
        order_origin(cursor, unit, "physical", ident)
        if row(
            cursor,
            "SELECT id FROM whole_item WHERE physical_item_id=%s LIMIT 1 FOR UPDATE",
            (ident,),
        ) or row(
            cursor, "SELECT id FROM item_handover WHERE pending_physical_id=%s FOR UPDATE", (ident,)
        ):
            fail("此实体已用于装配。请选择可用实物或选用对应数字库存。")
        cursor.execute(
            "UPDATE sales_order_unit SET physical_item_id=%s WHERE id=%s", (ident, unit_id)
        )
    elif action == "allocateOrderUnit":
        from core.public_account import claimable_item

        field_set(payload, {"order_unit_id", "item_id"})
        ident = integer(payload, "item_id")
        locked(cursor, "item", ident)
        order_origin(cursor, unit, "item", ident)
        if unit["allocated_at"] or (unit["item_id"] and unit["item_id"] != ident):
            fail("该订单件已有物品或分配记录，请核对后再办理。")
        whole = current(cursor, ident)
        d = digital(cursor, ident)
        if (
            not d["issue_id"]
            or d["sold"]
            or d["first_sold_at"]
            or not claimable_item(cursor, ident)
            or row(cursor, "SELECT id FROM ownership WHERE active_item_id=%s FOR UPDATE", (ident,))
            or row(
                cursor,
                "SELECT id FROM item_claim_code WHERE item_id=%s LIMIT 1 FOR UPDATE",
                (ident,),
            )
        ):
            fail("物品未就绪或已有成交、交付或持有人，不能分配。")
        if unit["physical_item_id"] and unit["physical_item_id"] != whole["physical_item_id"]:
            fail("当前装配与该件已准备的实体不一致。")
        physical = locked(cursor, "physical_item", whole["physical_item_id"])
        require_order_match(unit, physical)
        issue = row(cursor, "SELECT style_id FROM product_issue WHERE id=%s", (d["issue_id"],))
        if issue["style_id"] != physical["style_id"]:
            fail("数字物品与当前实体款式不一致，请先核对装配。")
        cursor.execute(
            "UPDATE sales_order_unit SET item_id=%s,physical_item_id=%s,allocated_at=%s WHERE id=%s",
            (ident, whole["physical_item_id"], now(), unit_id),
        )
    else:
        field_set(payload, {"order_unit_id", "evidence"})
        text(payload, "evidence", 1000, required=True)
        if not unit["physical_item_id"] and not unit["item_id"]:
            fail("该订单件没有待释放的占用。")
        if unit["item_id"]:
            locked(cursor, "item", unit["item_id"])
            d = digital(cursor, unit["item_id"])
            if (
                d["sold"]
                or d["first_sold_at"]
                or row(
                    cursor,
                    "SELECT id FROM item_claim_code WHERE item_id=%s LIMIT 1 FOR UPDATE",
                    (unit["item_id"],),
                )
                or row(
                    cursor,
                    "SELECT id FROM ownership WHERE active_item_id=%s FOR UPDATE",
                    (unit["item_id"],),
                )
            ):
                fail("此物品已成交、交付或归属，须先核对历史，不能释放。")
        cursor.execute(
            "UPDATE sales_order_unit SET item_id=NULL,physical_item_id=NULL,allocated_at=NULL WHERE id=%s",
            (unit_id,),
        )
    return {
        "id": unit["order_id"],
        "order_id": unit["order_id"],
        "order_unit_id": unit_id,
        "external_order_no": unit["external_order_no"],
        "position": unit["position"],
        "match": match,
        "released_item_id": unit["item_id"] if action == "releaseOrderUnit" else None,
        "released_physical_id": unit["physical_item_id"] if action == "releaseOrderUnit" else None,
    }
