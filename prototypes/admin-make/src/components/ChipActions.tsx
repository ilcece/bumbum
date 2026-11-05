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
export function ProvisionPanel({ chipId }: { chipId: number }) {
  const p = useStore(),
    a = useAction(),
    c = p.data.chips.find((c) => c.id === chipId),
    [first, setFirst] = useState(false),
    [second, setSecond] = useState(false);
  useEffect(() => {
    setFirst(false);
    setSecond(false);
    a.clear();
  }, [chipId]);
  if (!c) return null;
  return (
    <ProCard
      size="small"
      headerBordered
      variant="outlined"
      title="芯片准备与配置核验"
      extra={
        <Tag color={c.configuredAt ? "blue" : "default"}>
          {c.configuredAt ? "演示核验就绪" : "待配置"}
        </Tag>
      }
    >
      <div className="page-stack">
        <Alert
          type="info"
          title="以下为明确标记的配卡演示"
          description="不生成真实密钥，不向芯片写入，不验证真实动态链接或凭证。正式整合复用现有受控配卡服务。"
        />
        <Space>
          <Typography.Text>
            密钥状态：{c.keys ? "已记录演示准备标记" : "未准备"}
          </Typography.Text>
          <Button
            data-demo-only
            disabled={c.keys || a.unknown || c.state === "retired"}
            onClick={() => a.run("keys", { chipId }, "仅记录演示密钥标记")}
          >
            〔演示〕准备密钥标记
          </Button>
        </Space>
        <Checkbox checked={first} onChange={(e) => setFirst(e.target.checked)}>
          已核对密钥与模板的演示步骤
        </Checkbox>
        <Checkbox
          checked={second}
          onChange={(e) => setSecond(e.target.checked)}
        >
          已核对两条递增链接的演示步骤
        </Checkbox>
        <Button
          data-demo-only
          type="primary"
          disabled={
            !c.keys || !!c.configuredAt || a.unknown || c.state === "retired"
          }
          onClick={() =>
            a.run(
              "configure",
              { chipId, checked: first, checked2: second },
              "演示配置核验已记录，未验证实卡",
            )
          }
        >
          〔演示〕记录配置核验
        </Button>
        {c.configuredAt && (
          <Typography.Text type="secondary">
            演示记录时间：{timeText(c.configuredAt)}。未校验真实卡片。
          </Typography.Text>
        )}
        {a.feedback}
      </div>
    </ProCard>
  );
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
      title="首次绑定物品与芯片"
      open={open}
      onOpenChange={(v) => {
        a.clear();
        onOpenChange(v);
      }}
      initialValues={{ itemId, chipId }}
      modalProps={{ destroyOnHidden: true }}
      submitter={{
        searchConfig: { submitText: "确认首次绑定" },
        submitButtonProps: { disabled: a.unknown },
      }}
      onFinish={async (v) => {
        const ok = a.run(
          "bind",
          v,
          "首次关联已保存，继续配置核验；未自动启用或认领",
        );
        if (ok) onOpenChange(false);
        return ok;
      }}
    >
      <Alert
        type="info"
        title="建立首次关联，不覆盖历史绑定"
        description="绑定后还须配置核验及按条件启用，持有人关系单独建立。"
      />
      <ProFormSelect
        name="itemId"
        label="目标数字物品"
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
        label="待绑定芯片"
        disabled={!!chipId}
        rules={[{ required: true }]}
        options={p.data.chips
          .filter((c) => c.state === "pending" && !c.itemId && !c.candidateFor)
          .map((c) => ({ value: c.id, label: c.uid }))}
      />
      <ProFormText
        name="spec"
        label="实际实体规格"
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
  action: "disable" | "restore" | "lost";
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const p = useStore(),
    a = useAction(),
    c = p.data.chips.find((c) => c.id === chipId),
    names = {
      disable: "临时停用芯片",
      restore: "恢复当前芯片",
      lost: "挂失当前芯片",
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
