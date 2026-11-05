import React, { useEffect, useState } from "react";
import { ModalForm, ProFormSelect, ProFormDependency, ProFormText, ProFormTextArea, ProCard, ProDescriptions } from "@ant-design/pro-components";
import { Alert, Button, Checkbox, Form, Input, Modal, Row, Col, Space, Steps, Typography } from "antd";
import { useStore } from "../data/store";
import { Handover, kindNames, userName, users, timeText, wholeName, wholeState } from "../data/domain";
import { required, useAction } from "../ui";
import { ProvisionPanel } from "./ChipActions";
import { CopyValue, StatusTag, HolderValue } from "./RecordPresentation";

export default function HandoverEditor({ itemId, workId, initialKind = "periodic", open, onOpenChange }: { itemId: number; workId?: string; initialKind?: Handover["kind"]; open: boolean; onOpenChange: (v: boolean) => void }) {
  const p = useStore(), a = useAction(), [saved, setSaved] = useState(workId), [evidence, setEvidence] = useState(""), [checked, setChecked] = useState(false);
  const i = p.data.items.find(x => x.id === itemId), w = p.data.handovers.find(x => x.id === saved);
  useEffect(() => { if (open) { setSaved(workId); setEvidence(""); setChecked(false); a.clear(); } }, [open, workId]);
  if (!i) return null;
  const current = i.entities.find(e => !e.to), source = w ? i.entities.find(e => e.id === w.sourceEntityId) : current;
  const sourceChip = p.data.chips.find(c => c.id === source?.chipId), candidate = p.data.chips.find(c => c.id === w?.chipId), replacement = i.entities.find(e => e.id === w?.entityId);
  const kind = initialKind === "periodic" && current?.lost ? "loss" : initialKind;
  if (w) return <Modal title={kindNames[w.kind] + " · 整套物品办理"} open={open} onCancel={() => onOpenChange(false)} width={900} footer={<Button onClick={() => onOpenChange(false)}>关闭，保留办理记录</Button>} destroyOnHidden>
    <div className="page-stack">
      <Steps size="small" current={w.completedAt ? 2 : 1} items={[{ title: "准备替换物品" }, { title: "确认交付与生效" }]} />
      <Space wrap><Typography.Text strong>沿用数字身份</Typography.Text><CopyValue value={i.uid} /><Typography.Text type="secondary">发行编号、首次售出时间与历史继续保留</Typography.Text></Space>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}><ProCard size="small" headerBordered variant="outlined" title="原物品（实物＋芯片）" extra={<StatusTag value={wholeState(source)} />}>
          <ProDescriptions size="small" column={1} columns={[
            { title: "物品代次", render: () => wholeName(source) },
            { title: "实物规格", render: () => source?.spec || "旧记录待核对" },
            { title: "配套芯片", render: () => <CopyValue value={sourceChip?.uid} /> },
            { title: "原持有人", render: () => <HolderValue id={w.ownerId} name={userName(w.ownerId)} /> },
            ...(source?.lost ? [{ title: "挂失记录", render: () => <Space><StatusTag value="曾挂失" />{source.lostAt ? timeText(source.lostAt) : "旧记录未记时间"}</Space> }] : []),
          ]} />
        </ProCard></Col>
        <Col xs={24} md={12}><ProCard size="small" headerBordered variant="outlined" title="新物品（实物＋芯片）" extra={<StatusTag value={w.completedAt ? wholeState(replacement) : "待生效"} />}>
          <ProDescriptions size="small" column={1} columns={[
            { title: "物品代次", render: () => wholeName({ generation: w.generation }) },
            { title: "实物规格", render: () => w.spec },
            { title: "配套芯片", render: () => <CopyValue value={candidate?.uid} /> },
            { title: "接收账户", render: () => <HolderValue id={w.recipientId} name={userName(w.recipientId)} /> },
          ]} />
        </ProCard></Col>
      </Row>
      <Typography.Paragraph type="secondary">准备依据：{w.evidence} · {timeText(w.createdAt)}</Typography.Paragraph>
      {w.legacy ? <Alert type="warning" title="旧版记录仅供核对" description="不推定旧记录已经满足整套物品的实际交付条件。" /> : w.completedAt ? <Alert type="success" showIcon title="整套新物品已生效，数字身份及发行编号沿用" description={`完成于 ${timeText(w.completedAt)}。原物品退出当前授权，历史与挂失记录保留。${w.kind === "resale" ? "新整套物品交给新持有人，年度额度不重置。" : "持有人不变；计次仍待核对。"}`} /> : <>
        <Alert type={source?.lost ? "warning" : "info"} title={source?.lost ? "原整套物品已挂失，新物品尚未生效" : "准备期间原物品与持有人保持，替换尚未生效"} description="新物品作为整套准备，芯片配置是其中一步。核对实际交付后再明确生效；挂失的原物品不会因准备或关闭窗口恢复服务。" />
        {candidate && <ProvisionPanel chipId={candidate.id} title="新物品的芯片配置" />}
        <ProCard size="small" headerBordered variant="outlined" title="确认整套新物品的交付">
          <Form layout="vertical"><Form.Item label="实际交付核验依据" htmlFor="handover-delivery-evidence"><Input.TextArea id="handover-delivery-evidence" value={evidence} onChange={e => setEvidence(e.target.value)} /></Form.Item></Form>
          <Checkbox checked={checked} onChange={e => setChecked(e.target.checked)}>已核对整套新物品的实际交付、配套芯片和接收账户</Checkbox>
          <div style={{ marginTop: 16 }}><Button type="primary" disabled={!candidate?.configuredAt || a.unknown} onClick={() => a.run("complete", { workId: w.id, evidence, checked }, "整套新物品已生效，旧物品退出当前授权；身份与历史延续")}>确认交付并生效</Button></div>
          {a.feedback}
        </ProCard>
      </>}
    </div>
  </Modal>;
  return <ModalForm title="准备替换物品" open={open} onOpenChange={onOpenChange} modalProps={{ destroyOnHidden: true }} initialValues={{ kind }} submitter={{ searchConfig: { submitText: "保存新物品准备" }, submitButtonProps: { disabled: a.unknown } }} onFinish={async values => {
    if (!a.run("prepare", { itemId, ...values }, "整套新物品准备已保存，尚未替换原物品")) return false;
    setSaved(p.getData().handovers.find(x => x.itemId === itemId && !x.completedAt && !x.legacy)?.id);
    return false;
  }}>
    <Alert type="info" title="换新、转售都准备一整套新物品" description="实物＋芯片共同准备，沿用原数字身份，不新增发行名额。换新保持持有人；转售按约定向新持有人交付新实物与新芯片。" />
    <ProDescriptions size="small" column={1} columns={[
      { title: "原物品", render: () => `${wholeName(current)} · ${current?.spec || "待核对"}` },
      { title: "物品状态", render: () => <StatusTag value={wholeState(current)} /> },
    ]} />
    <ProFormSelect name="kind" label="业务类型" rules={[{ required: true }]} options={Object.entries(kindNames).filter(([value]) => value === "resale" || (current?.lost ? value === "loss" : value === "periodic")).map(([value, label]) => ({ value, label }))} />
    <ProFormDependency name={["kind"]}>{({ kind }) => kind === "resale" ? <ProFormSelect name="recipientId" label="转售接收账户（仅转售必填）" rules={[{ required: true }]} options={users.filter(u => u.value !== i.ownerId)} /> : null}</ProFormDependency>
    <ProFormText name="spec" label="新物品实际规格" rules={required} extra="填写这件新实物的尺寸、颜色等，不改变原物品或发行约定。" />
    <ProFormSelect name="chipId" label="新物品所配芯片" rules={[{ required: true }]} options={p.data.chips.filter(c => c.state === "pending" && !c.itemId && !c.candidateFor).map(c => ({ value: c.id, label: c.uid }))} />
    <ProFormTextArea name="evidence" label="资格及接收对象核对依据" rules={required} />
    {a.feedback}
  </ModalForm>;
}
