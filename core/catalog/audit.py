"""管理动作名称、业务快照与审计明细。"""

from datetime import datetime, timedelta, timezone
import json

from flask import g

from core.auth_settings import client_ip, fingerprint
from core.catalog.common import ITEM_ACTIONS, now, order_reference, renewal_usage, row, view
from core.chip_binding import valid_id

AUDIT_LABELS = {
    "style": "保存款式",
    "issue": "保存发行约定",
    "confirmIssue": "确认发行规则",
    "deleteIssue": "删除发行草案",
    "seal": "核定发行量",
    "item": "建立数字物品",
    "linkIssue": "补齐发行关联",
    "validationItem": "更新物品验证标记",
    "deleteItem": "清理数字物品",
    "sale": "确认售出状态",
    "saleBatch": "批量确认售出状态",
    "toggleItem": "变更物品启用状态",
    "bind": "配套芯片",
    "installAssembly": "确认安装",
    "createPhysicalItem": "登记实体物品",
    "assembleOrderItem": "新建数字物品并确认安装",
    "orderSale": "确认订单首次售出",
    "loseItem": "登记挂失",
    "cancelLoss": "取消挂失",
    "prepare": "准备替换物品",
    "complete": "确认交付与生效",
    "register": "登记芯片",
    "chipState": "调整芯片服务",
    "chipBatch": "修改芯片批次",
    "validationChip": "更新芯片验证标记",
    "deleteChip": "清理芯片",
    "clearTestBatch": "清理验收批次",
    "legacyProfile": "保存物品资料",
    "issueClaimCode": "首次发放认领码",
    "reissueClaimCode": "核对后补发认领码",
    "viewHolderPhone": "查看持有人完整手机号",
    "viewUserPhone": "查看账户完整手机号",
    "viewClaimCode": "查看交付认领码",
    "undoInstall": "纠正未配置的安装",
    "createOrder": "登记订单",
    "matchOrderUnit": "核对订单款式与规格",
    "orderPhysical": "为订单件准备实体",
    "allocateOrderUnit": "确认订单件分配",
    "releaseOrderUnit": "释放订单件占用",
    "image.upload": "上传款式图片",
    "test_seed": "导入验收数据",
    "legacy_cleanup": "清理旧测试数据",
}


AUDIT_ACTIONS = {
    **{"catalog." + action: label for action, label in AUDIT_LABELS.items()},
    "chip.register": "登记芯片",
    "chip.batch.update": "修改芯片批次",
    "chip.bind_item": "关联芯片与物品",
    "chip.generate_keys": "生成芯片密钥",
    "chip.view_keys": "查看芯片密钥",
    "chip.confirm_provisioning": "确认芯片配置核验",
    "item.create": "建立物品",
    "item.profile.save": "保存物品资料",
    "item.details.update": "更新物品资料",
    "item.status.change": "变更物品启用状态",
    "auth.passkey.register": "登记通行密钥",
    "auth.passkey.revoke": "撤销通行密钥",
    "maintenance.test_uuid_reset": "重置测试认领数据",
    "maintenance.business_reset": "重置业务数据",
}


def audit(cursor, action, target, detail):
    cursor.execute(
        "INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,%s,%s,%s,%s)",
        (
            g.admin_session["admin_id"],
            "catalog." + action,
            detail.pop("object_type", "digital_catalog"),
            str(target) if target is not None else None,
            json.dumps(detail, ensure_ascii=False),
            fingerprint("ip", client_ip()),
        ),
    )


def audit_event(event, linked_code=None):
    detail = event.get("detail") or {}
    label = AUDIT_ACTIONS.get(event["action"])
    summary = detail.get("summary")
    if not summary and event["action"] == "chip.register":
        summary = {"manual": "手工登记芯片。", "nfc_cool": "通过 NFC.cool 登记芯片。"}.get(
            detail.get("source")
        )
    event.update(
        operation=detail.get("operation") or label or "历史操作",
        object_code=detail.get("object_code") or linked_code or event["target_id"],
        summary=summary,
        outcome=detail.get("outcome"),
    )
    return event


def audit_item_id(cursor, action, payload):
    if action in ITEM_ACTIONS and valid_id(payload.get("item_id")):
        return payload["item_id"]
    if action == "complete" and valid_id(payload.get("work_id")):
        work = row(cursor, "SELECT item_id FROM item_handover WHERE id=%s", (payload["work_id"],))
        return work["item_id"] if work else None
    return None


def audit_snapshot(cursor, ident):
    if ident is None:
        return None
    record = row(
        cursor,
        """SELECT i.item_uid,i.status,d.sold,d.first_sold_at,d.quota_used,d.quota_year,d.quota_review,
                    w.generation,w.lost_at,w.loss_evidence,ph.physical_uid,ch.chip_uid,ch.chip_status,o.bound_at AS holder_bound_at,
                    BIN_TO_UUID(u.public_uid) AS user_uid
                    FROM item i LEFT JOIN digital_item d ON d.item_id=i.id
                    LEFT JOIN whole_item w ON w.current_item_id=i.id
                    LEFT JOIN physical_item ph ON ph.id=w.physical_item_id
                    LEFT JOIN chip ch ON ch.id=w.chip_id
                    LEFT JOIN ownership o ON o.active_item_id=i.id
                    LEFT JOIN user u ON u.uid=o.user_id WHERE i.id=%s""",
        (ident,),
    )
    return view(record) if record else None


def audit_detail(cursor, action, token, payload, result, before):
    is_item = action in ITEM_ACTIONS or action in {
        "complete",
        "item",
        "assembleOrderItem",
        "saleBatch",
    }
    after = audit_snapshot(cursor, result.get("id")) if is_item else None
    current_item = after or before or {}
    code = (
        current_item.get("item_uid")
        or result.get("physical_uid")
        or result.get("deleted_uid")
        or result.get("chip_uid")
    )
    work_id = result.get("work_id")
    operation = AUDIT_LABELS.get(action, "处理业务记录")
    summary = operation
    candidate = None
    if work_id and action in {"prepare", "complete"}:
        work = row(
            cursor,
            """SELECT w.kind,w.generation,ph.physical_uid,ch.chip_uid FROM item_handover w
                      LEFT JOIN physical_item ph ON ph.id=w.physical_item_id
                      JOIN chip ch ON ch.id=w.chip_id WHERE w.id=%s""",
            (work_id,),
        )
    else:
        work = None
    if action in {"installAssembly", "assembleOrderItem"}:
        summary = f"确认将芯片 {after['chip_uid']} 安装到实体 {after['physical_uid']}，待配置核验。"
    if action == "prepare" and work:
        operation = {"periodic": "准备换新", "loss": "准备挂失换新", "resale": "准备转售"}[
            work["kind"]
        ]
        summary = f"已{operation}，第 {work['generation']} 代整套物品待交付。"
        candidate = {key: work[key] for key in ("generation", "physical_uid", "chip_uid")}
    if action == "complete" and after and work:
        operation = "确认转售交付" if work["kind"] == "resale" else "确认换新交付"
        summary = f"第 {after['generation']} 代已交付生效，原芯片已退役。"
        if work["kind"] == "resale":
            summary += f"持有人由 {before['user_uid']} 变更为 {after['user_uid']}。"
            if row(
                cursor,
                "SELECT 1 FROM digital_item_right WHERE item_id=%s AND kind='renewal'",
                (result["id"],),
            ):
                if after["quota_review"] or after["quota_year"] is None:
                    summary += "本年换新额度待核对。"
                else:
                    used = renewal_usage(
                        cursor,
                        {**after, "item_id": result["id"]},
                        (now() + timedelta(hours=8)).year,
                    )
                    summary += f"本年换新剩余 {max(0,1-used)} 次。"
        else:
            summary += f"本年换新已用 {after['quota_used']} 次。"
    if action in {"sale", "orderSale", "saleBatch"} and after:
        sold_at = (
            datetime.fromisoformat(after["first_sold_at"]).astimezone(timezone(timedelta(hours=8)))
            if after["sold"]
            else None
        )
        summary = (
            f"确认已售出，首次成交时间 {sold_at:%Y-%m-%d %H:%M}（北京时间）。"
            if sold_at
            else "撤销售出标记。"
        )
    if action == "loseItem" and after:
        summary = f"第 {after['generation']} 代整套物品已挂失，配套芯片停止服务。"
    if action == "cancelLoss" and after:
        chip_result = (
            "配套芯片保持停用。"
            if after["chip_status"] == "disabled"
            else "配套芯片恢复至已关联状态。"
        )
        summary = f"已取消第 {after['generation']} 代整套物品的挂失。{chip_result}"
    if action == "saleBatch":
        summary = f"批量办理（共 {result['batch_size']} 件）。{summary}"
    detail = {
        "request_id": token,
        "object_type": "item" if is_item else "digital_catalog",
        "object_code": code,
        "operation": operation,
        "summary": summary,
        "outcome": "待交付" if candidate else "已完成",
        "before": before,
        "after": after,
        "work_id": work_id,
    }
    if candidate:
        detail["candidate"] = candidate
    if payload.get("evidence"):
        detail["evidence"] = payload["evidence"]
    if action == "cancelLoss":
        detail["cancelled_at"] = result["cancelled_at"]
    if action == "orderSale":
        detail.update(
            channel=payload["channel"].strip(),
            external_order_no=payload["external_order_no"].strip(),
            evidence=order_reference(payload),
        )
    if result.get("claim_code_id"):
        detail.update(
            claim_code_id=result["claim_code_id"],
            expires_at=result["expires_at"],
            evidence=payload.get("delivery_reference"),
        )
    if result.get("order_id"):
        detail.update(
            order_id=result["order_id"],
            order_unit_id=result.get("order_unit_id"),
            external_order_no=result["external_order_no"],
        )
        if not is_item:
            detail.update(object_type="order", object_code=result["external_order_no"])
            if result.get("position"):
                detail["summary"] = f"{operation}，订单第 {result['position']} 件。"
            if action == "matchOrderUnit":
                detail["expected"] = result["match"]
            if result.get("released_item_id") or result.get("released_physical_id"):
                detail.update(
                    released_item_id=result["released_item_id"],
                    released_physical_id=result["released_physical_id"],
                )
    if result.get("deleted_uid"):
        detail["deleted_uid"] = result["deleted_uid"]
    if action == "style":
        detail.update(object_type="style", object_code=payload["code"].strip())
    if action in {"issue", "confirmIssue", "deleteIssue", "seal"}:
        issue = result.get("issue_snapshot") or row(
            cursor, "SELECT name FROM product_issue WHERE id=%s", (result["id"],)
        )
        detail.update(object_type="issue", object_code=issue["name"])
    if action == "createPhysicalItem":
        detail["object_type"] = "physical"
    if action in {"chipBatch", "chipState", "validationChip", "deleteChip"}:
        detail["object_type"] = "chip"
    if action == "clearTestBatch":
        detail.update(
            object_type="test_batch",
            object_code=f"验收批次 {result['id']}",
            removed=result.get("removed"),
            summary=f"已清理验收批次 {result['id']}。",
        )
    return detail
