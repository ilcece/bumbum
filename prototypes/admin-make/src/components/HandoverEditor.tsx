import React, { useEffect, useState } from "react";
import {
  ModalForm,
  ProFormSelect,
  ProFormDependency,
  ProFormText,
  ProFormTextArea,
  ProCard,
  ProDescriptions,
} from "@ant-design/pro-components";
import {
  Alert,
  Button,
  Checkbox,
  Form,
  Input,
  Modal,
  Space,
  Steps,
} from "antd";
import { useStore } from "../data/store";
import { kindNames, userName, users, timeText } from "../data/domain";
import { required, useAction } from "../ui";
import { ProvisionPanel } from "./ChipActions";
import { CopyValue, StatusTag, HolderValue } from "./RecordPresentation";
export default function HandoverEditor({
  itemId,
  workId,
  open,
  onOpenChange,
}: {
  itemId: number;
  workId?: string;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const p = useStore(),
    a = useAction(),
    [saved, setSaved] = useState(workId),
    [evidence, setEvidence] = useState(""),
    [checked, setChecked] = useState(false),
    i = p.data.items.find((x) => x.id === itemId)!;
  useEffect(() => {
    if (open) {
      setSaved(workId);
      setEvidence("");
      setChecked(false);
      a.clear();
    }
  }, [open, workId]);
  const w = p.data.handovers.find((x) => x.id === saved),
    candidate = p.data.chips.find((c) => c.id === w?.chipId),
    old = i.entities.find((e) => !e.to),
    oldChip = p.data.chips.find((c) => c.id === old?.chipId);
  if (w)
    return (
      <Modal
        title={kindNames[w.kind] + " · " + i.uid}
        open={open}
        onCancel={() => onOpenChange(false)}
        width={820}
        footer={
          <Button onClick={() => onOpenChange(false)}>
            关闭，保留接续记录
          </Button>
        }
        destroyOnHidden
      >
        <div className="page-stack">
          <Steps
            size="small"
            current={w.completedAt ? 2 : 1}
            items={[
              { title: "准备新绑定" },
              { title: "确认接续" },
              { title: "完成" },
            ]}
          />
          <ProDescriptions
            size="small"
            bordered
            column={2}
            dataSource={w}
            columns={[
              { title: "数字物品编号", render: () => <CopyValue value={i.uid} /> },
              { title: "当前芯片", render: () => <CopyValue value={oldChip?.uid} /> },
              { title: "原持有人", render: () => <HolderValue id={w.ownerId} name={userName(w.ownerId)} /> },
              { title: "接收账户", render: () => <HolderValue id={w.recipientId} name={userName(w.recipientId)} /> },
              { title: "新实体规格", dataIndex: "spec" },
              { title: "候选芯片", render: () => <CopyValue value={candidate?.uid} /> },
              { title: "接续状态", render: () => <StatusTag value={w.legacy ? "旧版记录待核对" : w.completedAt ? "已完成" : "待确认接续"} /> },
              { title: "准备依据", dataIndex: "evidence" },
              { title: "准备时间", render: () => timeText(w.createdAt) },
            ]}
          />
          {w.legacy ? (
            <Alert
              type="warning"
              title="旧版记录仅供核对"
              description="保留原记录，不能推定旧履约步骤已满足新版实际交付条件。"
            />
          ) : w.completedAt ? (
            <Alert
              type="success"
              title="接续已完成，数字身份及发行编号沿用"
              description={`完成于 ${timeText(w.completedAt)}。旧卡退役、历史触碰保留。${w.kind === "resale" ? "持有人已更换，年度额度不重置。" : "计次待核对，未自行扣减年度额度。"}`}
            />
          ) : (
            <>
              <Alert
                type="info"
                title="准备阶段保留原关联与原持有人"
                description={`当前芯片 ${oldChip?.uid || "待核对"}；候选芯片在确认接续前不能提供物品服务。关闭后可从物品详情继续。`}
              />
              {candidate && <ProvisionPanel chipId={candidate.id} />}
              <ProCard
                size="small"
                headerBordered
                variant="outlined"
                title="确认实际交付与接续"
              >
                <Form layout="vertical">
                  <Form.Item
                    label="实际交付核验依据"
                    htmlFor="handover-delivery-evidence"
                  >
                    <Input.TextArea
                      id="handover-delivery-evidence"
                      value={evidence}
                      onChange={(e) => setEvidence(e.target.value)}
                    />
                  </Form.Item>
                </Form>
                <Checkbox
                  checked={checked}
                  onChange={(e) => setChecked(e.target.checked)}
                >
                  已核对实际交付、接收账户及新旧实体的对应关系
                </Checkbox>
                <div style={{ marginTop: 16 }}>
                  <Button
                    type="primary"
                    disabled={!candidate?.configuredAt || a.unknown}
                    onClick={() =>
                      a.run(
                        "complete",
                        { workId: w.id, evidence, checked },
                        "接续已完成，旧卡退役，身份及历史保留",
                      )
                    }
                  >
                    确认接续
                  </Button>
                </div>
                {a.feedback}
              </ProCard>
            </>
          )}
        </div>
      </Modal>
    );
  return (
    <ModalForm
      title="准备换新或转售"
      open={open}
      onOpenChange={onOpenChange}
      modalProps={{ destroyOnHidden: true }}
      initialValues={{ kind: "periodic" }}
      submitter={{
        searchConfig: { submitText: "保存准备，继续配置候选芯片" },
        submitButtonProps: { disabled: a.unknown },
      }}
      onFinish={async (v) => {
        if (!a.run("prepare", { itemId, ...v }, "准备已保存，原关联仍有效"))
          return false;
        const result = p
          .getData()
          .handovers.find(
            (x) => x.itemId === itemId && !x.completedAt && !x.legacy,
          );
        setSaved(result?.id);
        return false;
      }}
    >
      <Alert
        type="info"
        title="同一数字身份换新实体和芯片"
        description="不创建新发行名额。换新保持持有人；转售需核对不同的接收账户，完成时才变更持有人。费用与计次争议不在原型中自行裁定。"
      />
      <ProFormSelect
        name="kind"
        label="业务类型"
        rules={[{ required: true }]}
        options={Object.entries(kindNames).map(([value, label]) => ({
          value,
          label,
        }))}
      />
      <ProFormDependency name={["kind"]}>
        {({ kind }) =>
          kind === "resale" ? (
            <ProFormSelect
              name="recipientId"
              label="转售接收账户（仅转售必填）"
              rules={[{ required: true }]}
              options={users.filter((u) => u.value !== i.ownerId)}
            />
          ) : null
        }
      </ProFormDependency>
      <ProFormSelect
        name="chipId"
        label="新实体候选芯片"
        rules={[{ required: true }]}
        options={p.data.chips
          .filter((c) => c.state === "pending" && !c.itemId && !c.candidateFor)
          .map((c) => ({ value: c.id, label: c.uid }))}
      />
      <ProFormText name="spec" label="新实体实际规格" rules={required} />
      <ProFormTextArea
        name="evidence"
        label="资格及接收对象核对依据"
        rules={required}
      />
      {a.feedback}
    </ModalForm>
  );
}
