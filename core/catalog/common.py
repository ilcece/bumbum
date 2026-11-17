"""输入校验、时间与共用记录操作；事务由调用方管理。"""

from datetime import datetime, timezone
import json
import re

from core.account_uid import ACCOUNT_UID
from core.admin_auth import AuthRequestError
from core.admin_queries import invalid
from core.auth_settings import iso_time, utc_now
from core.chip_binding import valid_id
from core.test_batches import mark, source

KINDS = {"periodic", "loss", "resale"}


STANDARD_RIGHTS = ("renewal", "resale")


ITEM_ACTIONS = {
    "linkIssue",
    "validationItem",
    "deleteItem",
    "sale",
    "orderSale",
    "toggleItem",
    "bind",
    "installAssembly",
    "undoInstall",
    "loseItem",
    "cancelLoss",
    "prepare",
    "legacyProfile",
    "issueClaimCode",
    "reissueClaimCode",
}


def fail(message, status=409, code="invalid_state"):
    raise AuthRequestError(status, code, message)


def text(data, name, limit, *, required=False):
    value = data.get(name)
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        invalid(f"{name}须为最多{limit}字符的文字。")
    return value.strip() or None


def integer(data, name, *, optional=False):
    value = data.get(name)
    if optional and value is None:
        return None
    if not valid_id(value) or value > 2147483647:
        invalid(f"{name}须为有效正整数。")
    return value


def boolean(data, name, default=False):
    value = data.get(name, default)
    if type(value) is not bool:
        invalid(f"{name}须为布尔值。")
    return value


def account_uid(value):
    if not isinstance(value, str) or not ACCOUNT_UID.fullmatch(value):
        invalid("账户 UID 须为有效的 UUIDv7。")
    return value


def public_account_uid(value):
    if not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value
    ):
        invalid("账户 UID 须为有效的 UUIDv4。")
    return value


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


def view(row):
    if row is None:
        fail("记录不存在，请重新查询。", 404, "not_found")
    return {
        k: (
            iso_time(v)
            if isinstance(v, datetime)
            else (
                decoded(v)
                if k in {"specs", "image_urls", "rights", "detail", "result", "manifest"}
                else v
            )
        )
        for k, v in row.items()
    }


def row(cursor, sql, args=()):
    cursor.execute(sql, args)
    return cursor.fetchone()


def locked(cursor, table, ident):
    if table not in {
        "product_style",
        "product_issue",
        "item",
        "chip",
        "item_handover",
        "physical_item",
    }:
        raise ValueError("不支持的锁目标")
    return view(row(cursor, f"SELECT * FROM {table} WHERE id=%s FOR UPDATE", (ident,)))


def field_set(data, required=(), optional=()):
    if set(data) - set(required) - set(optional) or set(required) - set(data):
        invalid("字段不符合当前操作约定。")


def now():
    return utc_now()


def sale_time(data):
    """解析有依据的成交时间；操作审计仍独立记录后台处理时刻。"""
    if data.get("first_sold_at") is None:
        return now()
    try:
        value = datetime.fromisoformat(data["first_sold_at"].replace("Z", "+00:00"))
        if value.tzinfo is None or value.year < 1000:
            raise ValueError()
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError, AttributeError, OverflowError):
        invalid("首次售出时间须为数据库支持范围内、带时区的有效时间。")
    if value > now():
        invalid("首次售出时间不能晚于当前时间。")
    return value


def order_reference(payload):
    channel = text(payload, "channel", 40, required=True)
    order_no = text(payload, "external_order_no", 64, required=True)
    if any(ord(char) < 32 or ord(char) == 127 for char in channel + order_no) or "｜" in channel:
        invalid("成交渠道和订单号不能包含控制字符，渠道不能包含全角竖线。")
    return f"成交渠道：{channel}｜外部订单号：{order_no}"


def project_id(cursor, project):
    if not isinstance(project, str) or project not in {"fashion", "jewelry"}:
        invalid("类别仅支持fashion或jewelry。")
    return row(cursor, "SELECT id FROM project WHERE code=%s", (project,))["id"]


def current(cursor, item_id, *, required=True):
    found = row(
        cursor,
        "SELECT * FROM whole_item WHERE item_id=%s AND ended_at IS NULL FOR UPDATE",
        (item_id,),
    )
    if not found and required:
        fail("当前整套物品缺失，请核对历史后补齐。")
    return found


def chip_state_before_loss(cursor, item_id, lost_at):
    record = row(
        cursor,
        """SELECT detail FROM admin_audit WHERE target_type='item' AND target_id=%s
                          AND action='catalog.loseItem' ORDER BY id DESC LIMIT 1""",
        (str(item_id),),
    )
    if not record or not lost_at:
        return None
    detail = decoded(record["detail"]) or {}
    if (detail.get("after") or {}).get("lost_at") != lost_at:
        return None
    state = (detail.get("before") or {}).get("chip_status")
    return state if state in {"bound", "disabled"} else None


def digital(cursor, item_id):
    cursor.execute(
        "INSERT INTO digital_item(item_id) VALUES (%s) ON DUPLICATE KEY UPDATE item_id=item_id",
        (item_id,),
    )
    return row(cursor, "SELECT * FROM digital_item WHERE item_id=%s FOR UPDATE", (item_id,))


def revoke(cursor, item_id):
    # 永久撤销现有短许可与持续查看，后续恢复也不能复活旧资格。
    cursor.execute(
        "UPDATE tap_grant SET consumed_at=COALESCE(consumed_at,%s) WHERE item_id=%s",
        (now(), item_id),
    )


def create_physical(cursor, payload):
    field_set(payload, {"style_id", "physical_uid"}, {"spec", "batch_no", "supplier_serial"})
    style = locked(cursor, "product_style", integer(payload, "style_id"))
    uid = text(payload, "physical_uid", 64, required=True)
    if any(ord(x) < 32 or ord(x) == 127 for x in uid):
        invalid("实体编号不能含控制字符。")
    spec = text(payload, "spec", 256, required=bool(style["specs"])) or ""
    cursor.execute(
        "INSERT INTO physical_item(physical_uid,style_id,spec,batch_no,supplier_serial) VALUES (%s,%s,%s,%s,%s)",
        (
            uid,
            style["id"],
            spec,
            text(payload, "batch_no", 64),
            text(payload, "supplier_serial", 128),
        ),
    )
    ident = cursor.lastrowid
    mark(cursor, "physical", ident, source(cursor, "style", style["id"]))
    return {"id": ident, "physical_uid": uid}


def renewal_usage(cursor, d, year):
    if d["quota_review"] or d["quota_year"] is None:
        fail("年度用量待核对，暂不能办理换新。")
    if row(
        cursor,
        "SELECT id FROM item_handover WHERE item_id=%s AND quota_year=%s LIMIT 1",
        (d["item_id"], year),
    ):
        return 1
    return d["quota_used"] if d["quota_year"] == year else 0
