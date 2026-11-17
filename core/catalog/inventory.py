"""款式、发行、物品、芯片与整套接续业务；沿用调用方事务。"""

from datetime import datetime, timedelta, timezone
import json
import re

from flask import current_app, g

from core.admin_items import normalized_profile
from core.admin_queries import invalid
from core.auth_settings import iso_time
from core.catalog.common import (
    KINDS,
    STANDARD_RIGHTS,
    account_uid,
    boolean,
    chip_state_before_loss,
    current,
    digital,
    fail,
    field_set,
    integer,
    locked,
    now,
    order_reference,
    project_id,
    renewal_usage,
    revoke,
    row,
    sale_time,
    text,
)
from core.catalog.orders import lock_order_unit, require_order_match
from core.test_batches import lock_batch, mark, require_test_environment, same_source, source


def style_save(cursor, payload):
    field_set(
        payload,
        {"code", "project", "name", "specs", "image_urls"},
        {"id", "description", "material", "care_instructions", "shared_confirmed", "test_batch_id"},
    )
    ident = integer(payload, "id", optional=True)
    old = locked(cursor, "product_style", ident) if ident else None
    if (
        old
        and payload.get("test_batch_id") is not None
        and integer(payload, "test_batch_id") != source(cursor, "style", ident)
    ):
        fail("测试来源固定，不能改写。")
    lock_batch(cursor, source(cursor, "style", ident))
    pid = project_id(cursor, payload["project"])
    code = text(payload, "code", 64, required=True)
    profile = normalized_profile(
        {
            **{
                k: payload[k]
                for k in ("name", "description", "material", "care_instructions")
                if k in payload
            },
            "image_urls": [],
        }
    )
    images = payload["image_urls"]
    if not isinstance(images, list) or len(images) > 20:
        invalid("最多20张共用图片。")
    for url in images:
        match = (
            re.fullmatch(r"/api/admin/catalog/styles/([1-9][0-9]*)/images/([a-f0-9]{32})", url)
            if isinstance(url, str)
            else None
        )
        if (
            not match
            or not ident
            or int(match[1]) != ident
            or not row(
                cursor,
                "SELECT asset_id FROM style_image WHERE style_id=%s AND asset_id=%s AND (expires_at IS NULL OR expires_at>%s)",
                (ident, match[2], now()),
            )
        ):
            invalid("请选择本款式已上传的真实图片。")
    profile["image_urls"] = images
    specs = payload["specs"]
    if (
        not isinstance(specs, list)
        or len(specs) > 100
        or any(not isinstance(x, str) or not x.strip() or len(x) > 128 for x in specs)
    ):
        invalid("规格须为最多100项、每项128字符的列表。")
    if old:
        used = row(cursor, "SELECT COUNT(*) AS n FROM product_issue WHERE style_id=%s", (ident,))[
            "n"
        ]
        if used and (old["project_id"] != pid or old["code"] != code):
            fail("已有引用，类别和款式编号不能普通修改。")
        count = row(
            cursor,
            "SELECT COUNT(*) AS n FROM digital_item d JOIN product_issue r ON r.id=d.issue_id WHERE r.style_id=%s",
            (ident,),
        )["n"]
        if count and payload.get("shared_confirmed") is not True:
            fail("请确认本次共用保存将影响所有引用物品。")
    vals = (
        pid,
        code,
        profile["name"],
        profile["description"],
        profile["material"],
        profile["care_instructions"],
        json.dumps(specs, ensure_ascii=False),
        json.dumps(profile["image_urls"]),
    )
    if ident:
        cursor.execute(
            "UPDATE product_style SET project_id=%s,code=%s,name=%s,description=%s,material=%s,care_instructions=%s,specs=%s,image_urls=%s WHERE id=%s",
            (*vals, ident),
        )
    else:
        cursor.execute(
            "INSERT INTO product_style(project_id,code,name,description,material,care_instructions,specs,image_urls) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            vals,
        )
        ident = cursor.lastrowid
    cursor.execute(
        "UPDATE style_image SET expires_at=COALESCE(expires_at,%s) WHERE style_id=%s",
        (now() + timedelta(hours=24), ident),
    )
    for url in images:
        cursor.execute(
            "UPDATE style_image SET expires_at=NULL WHERE style_id=%s AND asset_id=%s",
            (ident, url.rsplit("/", 1)[-1]),
        )
    if not old and payload.get("test_batch_id") is not None:
        require_test_environment(current_app.config)
        mark(cursor, "style", ident, integer(payload, "test_batch_id"))
    return {"id": ident}


def issue_save(cursor, payload):
    field_set(
        payload,
        {"style_id", "name", "mode", "description"},
        {"id", "series", "total", "starts_at", "ends_at", "counting_rule", "rights"},
    )
    ident = integer(payload, "id", optional=True)
    previous = locked(cursor, "product_issue", ident) if ident else None
    if previous and previous["confirmed_at"]:
        fail("发行已确认，不能普通重写。")
    style = locked(cursor, "product_style", integer(payload, "style_id"))
    if ident:
        same_source(cursor, "issue", ident, "style", style["id"])
    mode = payload["mode"]
    total = integer(payload, "total", optional=True)
    if (
        not isinstance(mode, str)
        or mode not in {"fixed", "period", "unlimited"}
        or (mode == "fixed" and total is None)
    ):
        invalid("请选择发行方式，固定发行须提供总量。")
    # 旧客户端可带该键保存发行草案，新发行一律由物品服务授予标准权益。
    rights = previous["rights"] if previous else None
    start = end = None
    if mode == "period":
        try:
            start = datetime.fromisoformat(payload["starts_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(payload["ends_at"].replace("Z", "+00:00"))
            if not start.tzinfo or not end.tzinfo or start >= end:
                raise ValueError
            start = start.astimezone(timezone.utc).replace(tzinfo=None)
            end = end.astimezone(timezone.utc).replace(tzinfo=None)
        except (KeyError, ValueError, TypeError, AttributeError):
            invalid("限时发行须提供带时区的起止时间。")
    vals = (
        style["id"],
        text(payload, "name", 128, required=True),
        text(payload, "series", 128),
        mode,
        total if mode == "fixed" else None,
        start,
        end,
        text(payload, "counting_rule", 4000),
        text(payload, "description", 4000, required=True),
        json.dumps(rights),
    )
    if ident:
        cursor.execute(
            "UPDATE product_issue SET style_id=%s,name=%s,series=%s,mode=%s,total=%s,starts_at=%s,ends_at=%s,counting_rule=%s,description=%s,rights=%s WHERE id=%s",
            (*vals, ident),
        )
    else:
        cursor.execute(
            "INSERT INTO product_issue(style_id,name,series,mode,total,starts_at,ends_at,counting_rule,description,rights) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            vals,
        )
        ident = cursor.lastrowid
    mark(cursor, "issue", ident, source(cursor, "style", style["id"]))
    return {"id": ident}


def issue_action(cursor, action, payload):
    field_set(payload, {"issue_id"}, {"total", "evidence"})
    r = locked(cursor, "product_issue", integer(payload, "issue_id"))
    if action == "confirmIssue":
        text(payload, "evidence", 1000)
        if r["confirmed_at"]:
            fail("约定已确认，请查询结果。")
        if r["mode"] == "period" and not r["counting_rule"]:
            fail("请填写有效数量核定规则。")
        cursor.execute("UPDATE product_issue SET confirmed_at=%s WHERE id=%s", (now(), r["id"]))
    elif action == "deleteIssue":
        if r["ever_used"] or row(
            cursor, "SELECT item_id FROM digital_item WHERE issue_id=%s LIMIT 1", (r["id"],)
        ):
            fail("发行曾被引用，不能删除。")
        cursor.execute("DELETE FROM product_issue WHERE id=%s", (r["id"],))
    else:
        if r["mode"] != "period" or not r["confirmed_at"] or r["sealed_at"]:
            fail("仅已确认且未核定的限时发行可核定。")
        total = integer(payload, "total")
        evidence = text(payload, "evidence", 1000, required=True)
        # 本机时钟可在独立测试中固定；没有未到期提前封版入口。
        if datetime.fromisoformat(r["ends_at"].replace("Z", "+00:00")).replace(tzinfo=None) > now():
            fail("销售窗口尚未结束，不能确认最终发行量。")
        cursor.execute(
            "SELECT item_id,edition_number FROM digital_item WHERE issue_id=%s ORDER BY item_id FOR UPDATE",
            (r["id"],),
        )
        items = cursor.fetchall()
        if len(items) > total or any(
            x["edition_number"] and x["edition_number"] > total for x in items
        ):
            fail("最终量少于已建身份或已有编号，请先核对冲突。")
        occupied = {x["edition_number"] for x in items if x["edition_number"]}
        number = 1
        for item in items:
            if item["edition_number"]:
                continue
            while number in occupied:
                number += 1
            cursor.execute(
                "UPDATE digital_item SET edition_number=%s WHERE item_id=%s",
                (number, item["item_id"]),
            )
            occupied.add(number)
        cursor.execute(
            "UPDATE product_issue SET total=%s,sealed_at=%s,seal_evidence=%s WHERE id=%s",
            (total, now(), evidence, r["id"]),
        )
    return {"id": r["id"], "issue_snapshot": r if action == "deleteIssue" else None}


def create_item(cursor, payload):
    field_set(payload, {"issue_id", "item_uid"}, {"edition_number", "is_validation"})
    r = locked(cursor, "product_issue", integer(payload, "issue_id"))
    if not r["confirmed_at"]:
        fail("请先确认发行约定。")
    s = locked(cursor, "product_style", r["style_id"])
    pid = s["project_id"]
    project = row(cursor, "SELECT code FROM project WHERE id=%s", (pid,))["code"]
    uid = text(payload, "item_uid", 32, required=True)
    if any(ord(x) < 32 or ord(x) == 127 for x in uid):
        invalid("物品编号不能含控制字符。")
    number = integer(payload, "edition_number", optional=True)
    if r["mode"] == "period" and not r["sealed_at"]:
        if number is not None:
            invalid("限时核定前正式编号待定，不能手填。")
    elif number is None:
        invalid("请填写发行内正式序号。")
    if r["total"] and number and number > r["total"]:
        fail("编号超过已确认总量。")
    count = row(cursor, "SELECT COUNT(*) AS n FROM digital_item WHERE issue_id=%s", (r["id"],))["n"]
    if r["total"] and count >= r["total"]:
        fail("已达到数字身份发行上限。")
    cursor.execute("INSERT INTO item(project_id,item_uid) VALUES (%s,%s)", (pid, uid))
    ident = cursor.lastrowid
    cursor.execute(
        "INSERT INTO digital_item(item_id,issue_id,edition_number,is_validation,quota_year) VALUES (%s,%s,%s,%s,%s)",
        (
            ident,
            r["id"],
            number,
            boolean(payload, "is_validation"),
            (now() + timedelta(hours=8)).year,
        ),
    )
    grant_item_rights(cursor, ident, r)
    mark(cursor, "item", ident, source(cursor, "issue", r["id"]))
    cursor.execute("UPDATE product_issue SET ever_used=1 WHERE id=%s", (r["id"],))
    return {"id": ident}


def grant_item_rights(cursor, ident, issue):
    kinds = STANDARD_RIGHTS if issue["rights"] is None else issue["rights"]
    version = "standard-v1" if issue["rights"] is None else "legacy-issue"
    for kind in kinds:
        cursor.execute(
            "INSERT INTO digital_item_right(item_id,kind,rule_version) VALUES (%s,%s,%s)",
            (ident, kind, version),
        )


def select_physical(cursor, payload, item_id, issue_id, order_unit_id=None):
    if payload.get("installed") is not True:
        invalid("请确认已将所选芯片安装到该实体。")
    physical = locked(cursor, "physical_item", integer(payload, "physical_item_id"))
    same_source(cursor, "item", item_id, "physical", physical["id"])
    reserved = row(
        cursor,
        "SELECT id,item_id FROM sales_order_unit WHERE physical_item_id=%s FOR UPDATE",
        (physical["id"],),
    )
    if reserved and reserved["id"] != order_unit_id and reserved["item_id"] != item_id:
        fail("该实体已为其他订单件准备，请回原订单件处理。")
    issue = row(cursor, "SELECT style_id FROM product_issue WHERE id=%s", (issue_id,))
    if not issue or physical["style_id"] != issue["style_id"]:
        fail("请选择与数字物品同款式的实体。")
    if row(
        cursor,
        "SELECT id FROM whole_item WHERE physical_item_id=%s LIMIT 1 FOR UPDATE",
        (physical["id"],),
    ) or row(
        cursor,
        "SELECT id FROM item_handover WHERE pending_physical_id=%s FOR UPDATE",
        (physical["id"],),
    ):
        fail("实体已用于其他装配，请重新选择。")
    return physical


def resale_accounts(cursor, owner, recipient):
    if owner == recipient:
        fail("请选择不同的接收账户。")
    cursor.execute(
        "SELECT uid,phone_verified_at FROM user WHERE uid IN (%s,%s) ORDER BY uid FOR UPDATE",
        (owner, recipient),
    )
    verified = cursor.fetchall()
    if len(verified) != 2 or not all(u["phone_verified_at"] for u in verified):
        fail("原持有人和接收人均须验证手机号。")


def item_action(cursor, action, payload, order_unit_id=None, *, installed_by=None):
    ident = integer(payload, "item_id")
    i = locked(cursor, "item", ident)
    d = digital(cursor, ident)
    lock_batch(cursor, source(cursor, "item", ident))
    if action == "validationItem":
        field_set(payload, {"item_id", "enabled"})
        cursor.execute(
            "UPDATE digital_item SET is_validation=%s WHERE item_id=%s",
            (boolean(payload, "enabled"), ident),
        )
        return {"id": ident}
    if action == "deleteItem":
        if row(cursor, "SELECT id FROM sales_order_unit WHERE item_id=%s FOR UPDATE", (ident,)):
            fail("该物品关联订单件，请先核对订单分配或使用批次清理。")
        field_set(payload, {"item_id"})
        if not d["is_validation"]:
            fail("仅生产验证物品可以直接删除。")
        cursor.execute("DELETE FROM item_claim_code WHERE item_id=%s", (ident,))
        cursor.execute("DELETE FROM item_handover WHERE item_id=%s", (ident,))
        cursor.execute("DELETE FROM whole_item WHERE item_id=%s", (ident,))
        cursor.execute(
            "UPDATE chip SET item_id=NULL,chip_status=IF(chip_status='bound','pending',chip_status) WHERE item_id=%s",
            (ident,),
        )
        for table, column in [("sms_challenge", "tap_grant_id")]:
            cursor.execute(
                "DELETE FROM sms_challenge WHERE tap_grant_id IN (SELECT id FROM tap_grant WHERE item_id=%s)",
                (ident,),
            )
        for table in (
            "tap_grant",
            "scan_log",
            "ownership_history",
            "ownership",
            "jewelry_task_record",
            "jewelry_user_progress",
            "fashion_item_profile",
            "jewelry_item_profile",
        ):
            cursor.execute(f"DELETE FROM {table} WHERE item_id=%s", (ident,))
        cursor.execute(
            "UPDATE media_asset SET state='retired',expires_at=UTC_TIMESTAMP()+INTERVAL 24 HOUR WHERE item_id=%s AND state='attached'",
            (ident,),
        )
        cursor.execute("DELETE FROM media_asset WHERE item_id=%s", (ident,))
        cursor.execute("DELETE FROM item WHERE id=%s", (ident,))
        return {"id": ident, "deleted_uid": i["item_uid"]}
    if i["status"] == "archived":
        fail("归档物品只读。")
    if action == "legacyProfile":
        field_set(payload, {"item_id", "profile"})
        if d["issue_id"] or i["project_id"] != project_id(cursor, "fashion"):
            fail("已关联款式或非服装旧资料不能从旧入口维护。")
        profile = normalized_profile(payload["profile"])
        cursor.execute(
            "INSERT INTO fashion_item_profile(item_id,name,description,material,care_instructions,image_urls) VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name),description=VALUES(description),material=VALUES(material),care_instructions=VALUES(care_instructions),image_urls=VALUES(image_urls)",
            (
                ident,
                profile["name"],
                profile["description"],
                profile["material"],
                profile["care_instructions"],
                json.dumps(profile["image_urls"]),
            ),
        )
    elif action == "linkIssue":
        field_set(payload, {"item_id", "issue_id", "edition_number", "evidence"})
        same_source(cursor, "item", ident, "issue", integer(payload, "issue_id"))
        if d["issue_id"]:
            fail("已有发行关联不能普通改写。")
        r = locked(cursor, "product_issue", integer(payload, "issue_id"))
        s = locked(cursor, "product_style", r["style_id"])
        if not r["confirmed_at"] or s["project_id"] != i["project_id"]:
            fail("请选择同类别且已确认的发行，先核对原承诺。")
        text(payload, "evidence", 1000, required=True)
        number = integer(payload, "edition_number", optional=True)
        if r["mode"] == "period" and not r["sealed_at"]:
            if number is not None:
                invalid("未核定正式编号待定。")
        elif number is None or (r["total"] and number > r["total"]):
            fail("编号不符合发行约定。")
        if (
            r["total"]
            and row(cursor, "SELECT COUNT(*) AS n FROM digital_item WHERE issue_id=%s", (r["id"],))[
                "n"
            ]
            >= r["total"]
        ):
            fail("发行身份上限已满。")
        cursor.execute(
            "UPDATE digital_item SET issue_id=%s,edition_number=%s WHERE item_id=%s",
            (r["id"], number, ident),
        )
        cursor.execute("UPDATE product_issue SET ever_used=1 WHERE id=%s", (r["id"],))
        if r["rights"] is not None:
            grant_item_rights(cursor, ident, r)
    elif action in {"sale", "orderSale"}:
        if row(
            cursor,
            "SELECT id FROM sales_order_unit WHERE item_id=%s AND id<>%s FOR UPDATE",
            (ident, order_unit_id or 0),
        ):
            fail("该物品已占用，请在对应订单件确认售出。")
        if action == "orderSale":
            from core.public_account import claimable_item

            field_set(payload, {"item_id", "channel", "external_order_no", "first_sold_at"})
            evidence = order_reference(payload)
            if (
                d["sold"]
                or d["first_sold_at"]
                or not d["issue_id"]
                or not claimable_item(cursor, ident)
            ):
                fail("此物品不再满足首次售出条件，请刷新并核对物品档案。")
            if row(
                cursor, "SELECT id FROM ownership WHERE active_item_id=%s FOR UPDATE", (ident,)
            ) or row(
                cursor,
                "SELECT id FROM item_claim_code WHERE item_id=%s LIMIT 1 FOR UPDATE",
                (ident,),
            ):
                fail("此物品已有持有人或交付记录，不能按新库存出售。")
            confirmed = True
        else:
            field_set(payload, {"item_id", "confirmed", "evidence"}, {"first_sold_at"})
            evidence = text(payload, "evidence", 1000, required=True)
            confirmed = boolean(payload, "confirmed")
        sold_at = sale_time(payload)
        if (
            payload.get("first_sold_at") is not None
            and d["first_sold_at"]
            and sold_at != d["first_sold_at"]
        ):
            fail("已有首次售出时间不能通过普通维护改写。")
        cursor.execute(
            "UPDATE digital_item SET sold=%s,first_sold_at=IF(%s,COALESCE(first_sold_at,%s),first_sold_at),sale_evidence=%s WHERE item_id=%s",
            (confirmed, confirmed, sold_at, evidence, ident),
        )
    elif action == "toggleItem":
        field_set(payload, {"item_id", "status"})
        if not isinstance(payload["status"], str) or payload["status"] not in {
            "active",
            "disabled",
        }:
            invalid("只支持启用或停用。")
        if payload["status"] == "active":
            e = current(cursor, ident)
            chip = locked(cursor, "chip", e["chip_id"])
            if (
                not d["issue_id"]
                or not chip["provisioned_at"]
                or chip["chip_status"] != "bound"
                or e["lost_at"]
                or e["loss_evidence"]
            ):
                fail("请先补齐发行、整套物品及有效配置核验。")
        cursor.execute("UPDATE item SET status=%s WHERE id=%s", (payload["status"], ident))
        if payload["status"] == "disabled":
            revoke(cursor, ident)
    elif action in {"bind", "installAssembly"}:
        field_set(
            payload,
            (
                {"item_id", "chip_id", "physical_item_id", "installed"}
                if action == "installAssembly"
                else {"item_id", "chip_id"}
            ),
            {"spec"} if action == "bind" else set(),
        )
        if current(cursor, ident, required=False):
            fail("已有当前整套物品，换新/转售请办理接续。")
        if not d["issue_id"]:
            fail("请先补齐发行约定。")
        physical = (
            select_physical(cursor, payload, ident, d["issue_id"], order_unit_id)
            if action == "installAssembly"
            else None
        )
        if physical and not order_unit_id:
            linked = row(cursor, "SELECT id FROM sales_order_unit WHERE item_id=%s", (ident,))
            if linked:
                unit = lock_order_unit(cursor, linked["id"])
                if unit["physical_item_id"] != physical["id"]:
                    fail("请选择原订单件已准备的实体，或回原订单件纠正分配。")
                require_order_match(unit, physical)
        if not physical and row(
            cursor,
            "SELECT item_id FROM digital_item_right WHERE item_id=%s AND rule_version=%s LIMIT 1",
            (ident, "standard-v1"),
        ):
            fail("请通过安装芯片选择并确认独立编号的实体。")
        chip = locked(cursor, "chip", integer(payload, "chip_id"))
        same_source(cursor, "item", ident, "chip", chip["id"])
        available_chip(cursor, chip, i["project_id"])
        generation = row(
            cursor,
            "SELECT COALESCE(MAX(generation),0)+1 AS n FROM whole_item WHERE item_id=%s",
            (ident,),
        )["n"]
        cursor.execute(
            "UPDATE chip SET project_id=%s,item_id=%s,chip_status='bound' WHERE id=%s",
            (i["project_id"], ident, chip["id"]),
        )
        actor = (installed_by or g.admin_session["admin_id"]) if physical else None
        cursor.execute(
            "INSERT INTO whole_item(item_id,chip_id,generation,spec,started_at,physical_item_id,installed_at,installed_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                ident,
                chip["id"],
                generation,
                physical["spec"] if physical else text(payload, "spec", 256) or "",
                now(),
                physical["id"] if physical else None,
                now() if physical else None,
                actor,
            ),
        )
    elif action == "undoInstall":
        field_set(payload, {"item_id", "whole_id", "evidence", "confirmed"})
        text(payload, "evidence", 1000, required=True)
        if payload["confirmed"] is not True:
            invalid("请确认已核对并拆离该芯片。")
        e = current(cursor, ident)
        if (
            e["id"] != integer(payload, "whole_id")
            or not e["physical_item_id"]
            or i["status"] != "draft"
            or e["lost_at"]
            or e["loss_evidence"]
        ):
            fail("仅可纠正当前草稿、未核验的安装。")
        locked(cursor, "physical_item", e["physical_item_id"])
        chip = locked(cursor, "chip", e["chip_id"])
        if (
            chip["item_id"] != ident
            or chip["chip_status"] != "bound"
            or chip["provisioned_at"]
            or d["sold"]
            or row(cursor, "SELECT chip_id FROM chip_key WHERE chip_id=%s", (chip["id"],))
            or row(cursor, "SELECT id FROM ownership WHERE item_id=%s LIMIT 1", (ident,))
            or row(cursor, "SELECT id FROM item_handover WHERE item_id=%s LIMIT 1", (ident,))
        ):
            fail("该安装已进入配置、持有、售出或接续，请走专用纠错。")
        cursor.execute("DELETE FROM whole_item WHERE id=%s", (e["id"],))
        cursor.execute(
            "UPDATE chip SET item_id=NULL,chip_status='pending' WHERE id=%s", (chip["id"],)
        )
    elif action == "loseItem":
        field_set(payload, {"item_id", "whole_id", "evidence"})
        e = current(cursor, ident)
        if integer(payload, "whole_id") != e["id"]:
            fail("当前物品已变化，请重新核对。")
        chip = locked(cursor, "chip", e["chip_id"])
        if e["lost_at"] or e["loss_evidence"] or chip["chip_status"] not in {"bound", "disabled"}:
            fail("当前物品已挂失或不可挂失。")
        cursor.execute(
            "UPDATE whole_item SET lost_at=%s,loss_evidence=%s WHERE id=%s",
            (now(), text(payload, "evidence", 1000, required=True), e["id"]),
        )
        cursor.execute("UPDATE chip SET chip_status='lost' WHERE id=%s", (chip["id"],))
        cursor.execute(
            "UPDATE item_handover SET kind='loss' WHERE item_id=%s AND completed_at IS NULL AND kind='periodic'",
            (ident,),
        )
        revoke(cursor, ident)
    elif action == "cancelLoss":
        field_set(payload, {"item_id", "whole_id", "lost_at", "evidence"}, {"chip_state"})
        text(payload, "evidence", 1000, required=True)
        e = current(cursor, ident)
        lost_at = iso_time(e["lost_at"]) if e["lost_at"] else None
        if (
            e["id"] != integer(payload, "whole_id")
            or payload["lost_at"] != lost_at
            or not (lost_at or e["loss_evidence"])
        ):
            fail("当前挂失记录已变化，请重新核对。")
        if row(
            cursor, "SELECT id FROM item_handover WHERE pending_item_id=%s FOR UPDATE", (ident,)
        ):
            fail("该物品有未完成的换新或转售，暂不能取消挂失。")
        chip = locked(cursor, "chip", e["chip_id"])
        if (
            chip["chip_status"] != "lost"
            or chip["item_id"] != ident
            or chip["project_id"] != i["project_id"]
        ):
            fail("配套芯片状态或关联已变化，请重新核对。")
        state = chip_state_before_loss(cursor, ident, lost_at)
        if state is None:
            state = payload.get("chip_state")
            if state != "disabled" and (
                state != "bound"
                or not chip["provisioned_at"]
                or chip["last_verified_counter"] is None
            ):
                invalid("原芯片状态未记录，请明确选择保持停用或恢复已核验芯片。")
        elif "chip_state" in payload:
            invalid("已记录挂失前的芯片状态，取消挂失将恢复原状态。")
        cursor.execute(
            "UPDATE whole_item SET lost_at=NULL,loss_evidence=NULL WHERE id=%s", (e["id"],)
        )
        cursor.execute("UPDATE chip SET chip_status=%s WHERE id=%s", (state, chip["id"]))
        revoke(cursor, ident)
        cursor.execute("UPDATE item SET updated_at=CURRENT_TIMESTAMP WHERE id=%s", (ident,))
        return {"id": ident, "cancelled_at": iso_time(now())}
    elif action == "prepare":
        field_set(
            payload,
            {"item_id", "kind", "chip_id", "evidence"},
            {
                "recipient_id",
                "spec",
                "physical_item_id",
                "installed",
                "seller_confirmation",
                "recipient_confirmation",
                "identity_review_required",
                "identity_verification_reference",
            },
        )
        kind = payload["kind"]
        e = current(cursor, ident)
        if not isinstance(kind, str) or kind not in KINDS:
            invalid("办理类型不支持。")
        if not d["issue_id"]:
            fail("请先补齐发行。")
        right = row(
            cursor,
            "SELECT rule_version FROM digital_item_right WHERE item_id=%s AND kind=%s",
            (ident, "resale" if kind == "resale" else "renewal"),
        )
        if not right:
            fail("此数字物品未包含该权益。")
        if kind != "resale" and renewal_usage(cursor, d, (now() + timedelta(hours=8)).year) >= 1:
            fail("本年换新额度已用。")
        if kind != "resale" and ((kind == "loss") != bool(e["lost_at"] or e["loss_evidence"])):
            fail("请选择与整套物品挂失事实一致的换新类型。")
        physical = (
            select_physical(cursor, payload, ident, d["issue_id"])
            if payload.get("physical_item_id") is not None or right["rule_version"] == "standard-v1"
            else None
        )
        chip = locked(cursor, "chip", integer(payload, "chip_id"))
        same_source(cursor, "item", ident, "chip", chip["id"])
        available_chip(cursor, chip, i["project_id"])
        owner = row(cursor, "SELECT * FROM ownership WHERE active_item_id=%s FOR UPDATE", (ident,))
        if not owner:
            fail("尚无正式持有人，不能办理换新/转售。")
        recipient = (
            account_uid(payload.get("recipient_id")) if kind == "resale" else owner["user_id"]
        )
        same_source(cursor, "item", ident, "user", recipient)
        seller_confirmation = recipient_confirmation = identity_ref = None
        if kind == "resale":
            resale_accounts(cursor, owner["user_id"], recipient)
            seller_confirmation = text(payload, "seller_confirmation", 1000, required=True)
            recipient_confirmation = text(payload, "recipient_confirmation", 1000, required=True)
            identity_ref = text(
                payload,
                "identity_verification_reference",
                128,
                required=boolean(payload, "identity_review_required"),
            )
        generation = row(
            cursor, "SELECT MAX(generation)+1 AS n FROM whole_item WHERE item_id=%s", (ident,)
        )["n"]
        actor = (installed_by or g.admin_session["admin_id"]) if physical else None
        cursor.execute(
            "INSERT INTO item_handover(item_id,source_id,chip_id,kind,generation,spec,owner_id,recipient_id,prepare_evidence,created_at,physical_item_id,installed_at,installed_by,seller_confirmation,recipient_confirmation,identity_verification_reference) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                ident,
                e["id"],
                chip["id"],
                kind,
                generation,
                physical["spec"] if physical else text(payload, "spec", 256) or "",
                owner["user_id"],
                recipient,
                text(payload, "evidence", 1000, required=True),
                now(),
                physical["id"] if physical else None,
                now() if physical else None,
                actor,
                seller_confirmation,
                recipient_confirmation,
                identity_ref,
            ),
        )
        work_id = cursor.lastrowid
        cursor.execute("UPDATE chip SET project_id=%s WHERE id=%s", (i["project_id"], chip["id"]))
    else:
        fail("操作不支持。", 404, "not_found")
    cursor.execute("UPDATE item SET updated_at=CURRENT_TIMESTAMP WHERE id=%s", (ident,))
    return {"id": ident, "work_id": work_id} if action == "prepare" else {"id": ident}


def available_chip(cursor, chip, pid):
    if (
        chip["chip_status"] != "pending"
        or chip["item_id"] is not None
        or chip["project_id"] not in {None, pid}
    ):
        fail("芯片已占用、状态不可用或类别不一致。")
    if row(
        cursor, "SELECT id FROM item_handover WHERE pending_chip_id=%s FOR UPDATE", (chip["id"],)
    ):
        fail("芯片已用于其他整套物品准备。")


def complete(cursor, payload):
    field_set(payload, {"work_id", "evidence", "checked"})
    # 先定位物品，再按物品→办理→芯片→持有关系锁定；定位后重查。
    initial = row(
        cursor, "SELECT item_id FROM item_handover WHERE id=%s", (integer(payload, "work_id"),)
    )
    if not initial:
        fail("办理记录不存在。", 404, "not_found")
    i = locked(cursor, "item", initial["item_id"])
    d = digital(cursor, i["id"])
    w = locked(cursor, "item_handover", payload["work_id"])
    if w["completed_at"]:
        return {"id": i["id"], "work_id": w["id"], "already_completed": True}
    e = current(cursor, i["id"])
    if w["source_id"] != e["id"] or i["status"] == "archived":
        fail("原物品已变化，请核对结果。")
    if w["physical_item_id"]:
        locked(cursor, "physical_item", w["physical_item_id"])
        if row(
            cursor,
            "SELECT id FROM whole_item WHERE physical_item_id=%s LIMIT 1 FOR UPDATE",
            (w["physical_item_id"],),
        ):
            fail("候选实体已被其他装配占用。")
    cursor.execute(
        "SELECT * FROM chip WHERE id IN (%s,%s) ORDER BY id FOR UPDATE",
        (e["chip_id"], w["chip_id"]),
    )
    chips = {x["id"]: x for x in cursor.fetchall()}
    old, new = chips[e["chip_id"]], chips[w["chip_id"]]
    owner = row(cursor, "SELECT * FROM ownership WHERE active_item_id=%s FOR UPDATE", (i["id"],))
    if (
        not owner
        or owner["user_id"] != w["owner_id"]
        or old["item_id"] != i["id"]
        or new["item_id"] is not None
        or new["chip_status"] != "pending"
        or new["project_id"] != i["project_id"]
    ):
        fail("物品、持有人或新物品配置已变化，请重新核对。")
    if not new["provisioned_at"]:
        fail("新芯片尚未通过配置核验，办理仍处于准备中。")
    if payload["checked"] is not True:
        invalid("请明确确认整套交付及接收人。")
    evidence = text(payload, "evidence", 1000, required=True)
    effective_at = now()
    quota_year = None
    if w["kind"] == "resale":
        resale_accounts(cursor, w["owner_id"], w["recipient_id"])
        if not w["seller_confirmation"] or not w["recipient_confirmation"]:
            fail("请先核对并记录双方确认依据。")
    else:
        quota_year = (effective_at + timedelta(hours=8)).year
        if renewal_usage(cursor, d, quota_year) >= 1:
            fail("确认生效当年的换新额度已用。")
    cursor.execute("UPDATE chip SET item_id=NULL,chip_status='retired' WHERE id=%s", (old["id"],))
    cursor.execute(
        "UPDATE whole_item SET ended_at=%s,exit_reason=%s WHERE id=%s",
        (effective_at, w["kind"], e["id"]),
    )
    cursor.execute(
        "UPDATE chip SET item_id=%s,chip_status='bound' WHERE id=%s", (i["id"], new["id"])
    )
    cursor.execute(
        "INSERT INTO whole_item(item_id,chip_id,generation,spec,started_at,physical_item_id,installed_at,installed_by) SELECT item_id,chip_id,generation,spec,%s,physical_item_id,installed_at,installed_by FROM item_handover WHERE id=%s",
        (effective_at, w["id"]),
    )
    target = cursor.lastrowid
    if w["kind"] == "resale":
        cursor.execute(
            "UPDATE ownership SET is_active=0,unbound_at=%s WHERE id=%s",
            (effective_at, owner["id"]),
        )
        cursor.execute(
            "INSERT INTO ownership(item_id,user_id,bind_source,bound_at) VALUES (%s,%s,'admin',%s)",
            (i["id"], w["recipient_id"], effective_at),
        )
        cursor.execute(
            "INSERT INTO ownership_history(item_id,from_user_id,to_user_id,action,note) VALUES (%s,%s,%s,'transfer',%s)",
            (
                i["id"],
                w["owner_id"],
                w["recipient_id"],
                "管理员核对整套交付，办理记录" + str(w["id"]),
            ),
        )
    else:
        cursor.execute(
            "UPDATE digital_item SET quota_year=%s,quota_used=1,quota_review=0 WHERE item_id=%s",
            (quota_year, i["id"]),
        )
    cursor.execute(
        "UPDATE item_handover SET target_id=%s,delivery_evidence=%s,completed_at=%s,quota_year=%s WHERE id=%s",
        (target, evidence, effective_at, quota_year, w["id"]),
    )
    revoke(cursor, i["id"])
    return {"id": i["id"], "work_id": w["id"]}


def chip_action(cursor, action, payload):
    ident = integer(payload, "chip_id")
    found = row(
        cursor,
        "SELECT c.item_id,w.item_id AS candidate_item_id FROM chip c LEFT JOIN item_handover w ON w.pending_chip_id=c.id WHERE c.id=%s",
        (ident,),
    )
    if not found:
        fail("芯片不存在。", 404, "not_found")
    if found["item_id"] or found["candidate_item_id"]:
        locked(cursor, "item", found["item_id"] or found["candidate_item_id"])
    chip = locked(cursor, "chip", ident)
    if chip["item_id"] != found["item_id"]:
        fail("关联已变化，请重新查询。")
    if action == "chipBatch":
        field_set(payload, {"chip_id", "batch_no"})
        cursor.execute(
            "UPDATE chip SET batch_no=%s WHERE id=%s", (text(payload, "batch_no", 64), ident)
        )
    elif action == "validationChip":
        field_set(payload, {"chip_id", "enabled"})
        cursor.execute(
            "INSERT INTO chip_validation(chip_id,is_validation) VALUES (%s,%s) ON DUPLICATE KEY UPDATE is_validation=VALUES(is_validation)",
            (ident, boolean(payload, "enabled")),
        )
    elif action == "deleteChip":
        field_set(payload, {"chip_id"})
        if row(
            cursor,
            "SELECT ou.id FROM sales_order_unit ou JOIN whole_item w ON w.id=ou.delivery_whole_id WHERE w.chip_id=%s LIMIT 1 FOR UPDATE",
            (ident,),
        ):
            fail("芯片属于已确认的订单交付，请保留原交付记录。")
        flag = row(cursor, "SELECT is_validation FROM chip_validation WHERE chip_id=%s", (ident,))
        if not flag or not flag["is_validation"]:
            fail("仅生产验证芯片可以直接删除。")
        cursor.execute(
            "DELETE FROM item_handover WHERE chip_id=%s OR source_id IN (SELECT id FROM whole_item WHERE chip_id=%s)",
            (ident, ident),
        )
        cursor.execute("DELETE FROM whole_item WHERE chip_id=%s", (ident,))
        cursor.execute(
            "DELETE FROM sms_challenge WHERE tap_grant_id IN (SELECT id FROM tap_grant WHERE chip_id=%s)",
            (ident,),
        )
        for table in ("tap_grant", "scan_log"):
            cursor.execute(f"DELETE FROM {table} WHERE chip_id=%s", (ident,))
        cursor.execute("DELETE FROM chip WHERE id=%s", (ident,))
    else:
        field_set(payload, {"chip_id", "state", "evidence"})
        text(payload, "evidence", 1000, required=True)
        if chip["chip_status"] in {"lost", "retired"} or row(
            cursor, "SELECT id FROM item_handover WHERE pending_chip_id=%s", (ident,)
        ):
            fail("挂失、退役或候选芯片不能普通恢复或停用。")
        if chip["item_id"]:
            e = current(cursor, chip["item_id"], required=False)
            if e and (e["lost_at"] or e["loss_evidence"]):
                fail("整套物品已挂失，技术恢复不能解除。")
        if payload["state"] == "disabled" and chip["chip_status"] in {"pending", "bound"}:
            state = "disabled"
        elif payload["state"] == "restore" and chip["chip_status"] == "disabled":
            state = "bound" if chip["item_id"] else "pending"
        else:
            fail("当前状态不允许该技术操作。")
        cursor.execute("UPDATE chip SET chip_status=%s WHERE id=%s", (state, ident))
        if chip["item_id"]:
            revoke(cursor, chip["item_id"])
    return {"id": ident, "chip_uid": chip["chip_uid"]}
