import { useState } from "react";
import { Button, Descriptions, Modal } from "antd";
import { Row, statusNames, time } from "../catalog";

const registrationSources: Record<string, string> = {
  manual: "手工登记", nfc_cool: "NFC.cool", unknown: "历史未记录",
};

const batchObjects: Record<string, string> = {
  style: "款式", issue: "发行", physical: "实体物品", item: "数字物品",
  chip: "芯片", user: "账户", order: "订单",
};

function auditSummary(value: Record<string, any>) {
  return [
    statusNames[value.status], value.generation && `第 ${value.generation} 代`,
    value.physical_uid && `实体 ${value.physical_uid}`, value.chip_uid && `芯片 ${value.chip_uid}`,
    statusNames[value.chip_status] && `芯片状态 ${statusNames[value.chip_status]}`,
    value.user_uid && `持有人 ${value.user_uid}`, value.lost_at && "已挂失",
    value.sold != null && (value.sold ? "已售出" : "未售出"),
    value.first_sold_at && `首次成交 ${time(value.first_sold_at)}`,
    value.quota_review ? "换新额度待核对" : value.quota_year && value.quota_used != null && `${value.quota_year} 年换新已用 ${value.quota_used} 次`,
  ].filter(Boolean).join(" · ") || "档案已记录";
}

export default function AuditDetails({ event }: { event: Row }) {
  const [open, setOpen] = useState(false);
  const detail = event.detail || {};
  return (
    <>
      <Button type="link" onClick={() => setOpen(true)}
        aria-label={`查看详情 · ${event.operation || "历史操作"} · ${event.object_code || "对象未记录"}`}>
        查看详情
      </Button>
      <Modal open={open} title="操作日志详情" width={720} onCancel={() => setOpen(false)}
        footer={<Button onClick={() => setOpen(false)}>关闭</Button>}
        className="audit-detail-modal" destroyOnHidden>
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="操作">{event.operation || "历史操作"}</Descriptions.Item>
          <Descriptions.Item label="对象">{event.object_code || "未记录"}</Descriptions.Item>
          <Descriptions.Item label="操作人">{event.username || "未记录"}</Descriptions.Item>
          <Descriptions.Item label="时间">{time(event.created_at)}（北京时间）</Descriptions.Item>
          <Descriptions.Item label="结果">{event.outcome || "未单独记录"}</Descriptions.Item>
          {event.summary && event.summary !== event.operation && <Descriptions.Item label="摘要">{event.summary}</Descriptions.Item>}
          {detail.evidence && <Descriptions.Item label="核对依据">{detail.evidence}</Descriptions.Item>}
          {detail.external_order_no && <Descriptions.Item label="外部订单号">{detail.external_order_no}</Descriptions.Item>}
          {detail.work_id && <Descriptions.Item label="办理记录">{detail.work_id}</Descriptions.Item>}
          {detail.candidate && <Descriptions.Item label="待交付组合">{auditSummary(detail.candidate)}</Descriptions.Item>}
          {detail.before && <Descriptions.Item label="操作前">{auditSummary(detail.before)}</Descriptions.Item>}
          {detail.after && <Descriptions.Item label="操作后">{auditSummary(detail.after)}</Descriptions.Item>}
          {registrationSources[detail.source] && <Descriptions.Item label="登记来源">{registrationSources[detail.source]}</Descriptions.Item>}
          {detail.key_version && <Descriptions.Item label="密钥版本">{detail.key_version}</Descriptions.Item>}
          {detail.expires_at && <Descriptions.Item label="认领码有效期">{time(detail.expires_at)}</Descriptions.Item>}
          {detail.removed && <Descriptions.Item label="清理数量">{Object.entries(batchObjects)
            .filter(([key]) => detail.removed[key] != null)
            .map(([key, label]) => `${label} ${detail.removed[key]}`).join(" · ")}</Descriptions.Item>}
        </Descriptions>
      </Modal>
    </>
  );
}
