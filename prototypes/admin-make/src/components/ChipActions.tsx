import React, { useEffect, useState } from "react";
import {
  ProCard,
  ModalForm,
  ProFormSelect,
  ProFormText,
  ProFormTextArea,
  ProFormCheckbox,
} from "@ant-design/pro-components";
import { Alert, Button, Checkbox, Space, Tag, Typography } from "antd";
import { useStore } from "../data/store";
import { chipStates, edition, timeText } from "../data/domain";
import { required, useAction } from "../ui";
export { default as KeyConfigDialog } from "./KeyConfigDialog";
import KeyConfigDialog from "./KeyConfigDialog";
import { CopyValue, StatusTag } from "./RecordPresentation";
export function ProvisionPanel({ chipId, title = "芯片密钥与配置" }: { chipId: number; title?: string }) {
  const p = useStore(), c = p.data.chips.find(c => c.id === chipId), [open, setOpen] = useState(false);
  if (!c) return null;
  return <ProCard size="small" headerBordered variant="outlined" title={title} extra={<StatusTag value={c.configuredAt ? "演示核验就绪" : "待配置"} />}>
    <Space direction="vertical" size={12} style={{width: "100%"}}>
      <Space wrap><CopyValue value={c.uid} /><StatusTag value={c.keys ? "已准备演示标记" : "未准备"} /></Space>
      <Typography.Text type="secondary">生成密钥 → 受控查看与配卡 → 双链接动态读数核验。原型仅演示交互。</Typography.Text>
      <Button type="primary" onClick={() => setOpen(true)}>查看密钥与配置</Button>
    </Space>
    {open && <KeyConfigDialog key={chipId} chipId={chipId} onClose={() => setOpen(false)} />}
  </ProCard>;
}
export function BindEditor({
  open,
  onOpenChange,
  itemId,
  chipId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  itemId?: number;
  chipId?: number;
}) {
  const p = useStore(),
    a = useAction();
  return (
    <ModalForm
      title="准备物品（实物＋芯片）"
      open={open}
      onOpenChange={(v) => {
        a.clear();
        onOpenChange(v);
      }}
      initialValues={{ itemId, chipId }}
      modalProps={{ destroyOnHidden: true }}
      submitter={{
        searchConfig: { submitText: "保存物品准备" },
        submitButtonProps: { disabled: a.unknown },
      }}
      onFinish={async (v) => {
        const ok = a.run(
          "bind",
          v,
          "整套物品已准备，继续配置核验；未自动启用或认领",
        );
        if (ok) onOpenChange(false);
        return ok;
      }}
    >
      <Alert
        type="info"
        title="为数字身份准备实物与配套芯片"
        description="实物和芯片作为同一整套物品保存，仍须配置核验及按条件启用，持有人关系单独建立。"
      />
      <ProFormSelect
        name="itemId"
        label="目标数字身份"
        disabled={!!itemId}
        rules={[{ required: true }]}
        options={p.data.items
          .filter(
            (i) =>
              i.issueId &&
              i.status !== "archived" &&
              (!i.entities.some((e) => !e.to) || i.id === itemId),
          )
          .map((i) => ({
            value: i.id,
            label:
              i.uid +
              " · " +
              edition(
                i,
                p.data.issues.find((s) => s.id === i.issueId),
              ),
          }))}
      />
      <ProFormSelect
        name="chipId"
        label="物品所配芯片"
        disabled={!!chipId}
        rules={[{ required: true }]}
        options={p.data.chips
          .filter((c) => c.state === "pending" && !c.itemId && !c.candidateFor)
          .map((c) => ({ value: c.id, label: c.uid }))}
      />
      <ProFormText
        name="spec"
        label="物品实际规格"
        rules={required}
        extra="填写实际适用尺寸/颜色等，不录订单、工厂或物流。"
      />
      {a.feedback}
    </ModalForm>
  );
}
export function StateEditor({
  chipId,
  action,
  open,
  onOpenChange,
}: {
  chipId: number;
  action: "disable" | "restore";
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const p = useStore(),
    a = useAction(),
    c = p.data.chips.find((c) => c.id === chipId),
    names = {
      disable: "临时停用芯片",
      restore: "恢复当前芯片",
    };
  return (
    <ModalForm
      title={names[action]}
      open={open}
      onOpenChange={(v) => {
        a.clear();
        onOpenChange(v);
      }}
      modalProps={{ destroyOnHidden: true }}
      onFinish={async (v) => {
        const ok = a.run("chipState", { chipId, action, evidence: v.evidence });
        if (ok) onOpenChange(false);
        return ok;
      }}
      submitter={{
        searchConfig: { submitText: "确认" + names[action] },
        submitButtonProps: {
          disabled: a.unknown,
          danger: action !== "restore",
        },
      }}
    >
      <Alert
        type="warning"
        title={c?.uid}
        description={
          action === "restore"
            ? "仅临时停用且授权未变的芯片可以普通恢复；挂失解除及退役恢复不在此执行。"
            : "只改变芯片服务状态，保留数字身份、持有人和历史；不自动扣换新次数。"
        }
      />
      <ProFormTextArea name="evidence" label="状态操作依据" rules={required} />
      {a.feedback}
    </ModalForm>
  );
}
