import { useEffect, useState } from "react";
import { PageContainer, ProCard } from "@ant-design/pro-components";
import { history, useLocation } from "@umijs/max";
import { Alert, Button, Checkbox, Form, Input, InputNumber, Select, Space, Typography } from "antd";
import { ActionForm, Load, RemoteSelect, required, returnPath, useRecord } from "../components/CatalogUI";
import StyleEditor from "../components/StyleEditor";
import { IssueFields } from "./Catalog";
import { Row } from "../catalog";

type Supplement = "style" | "issue" | "confirm" | "physical" | "chip";

export function PhysicalFields({ nested = false }: { nested?: boolean }) {
  const field = (name: string) => nested ? ["physical", name] : name;
  const style = useRecord("styles", Form.useWatch(field("style_id"))).record;
  return <>
    <Form.Item name={field("physical_uid")} label="实体编号" rules={required}><Input maxLength={64} /></Form.Item>
    <Form.Item name={field("spec")} label="实际规格" rules={style?.specs?.length ? required : []}>
      {style?.specs?.length ? <Select options={style.specs.map((spec: string) => ({ label: spec, value: spec }))} /> : <Input maxLength={256} placeholder="填写实物尺码、颜色等信息" />}
    </Form.Item>
    <Form.Item name={field("batch_no")} label="实物批次"><Input maxLength={64} /></Form.Item>
    <Form.Item name={field("supplier_serial")} label="供应商序列号"><Input maxLength={128} /></Form.Item>
  </>;
}

export function RegisterPhysical({ styleId, unitId, onClose, onDone }: {
  styleId?: number; unitId?: number; onClose: () => void; onDone: (r: Row) => void;
}) {
  const [creatingStyle, setCreatingStyle] = useState(false);
  const [form] = Form.useForm();
  const styleField = unitId ? ["physical", "style_id"] : "style_id";
  return <>
    <ActionForm title="登记实体物品" submitText="保存实体"
      formInstance={form} action={unitId ? "orderPhysical" : "createPhysicalItem"}
      initial={unitId ? { order_unit_id: unitId, physical: { style_id: styleId } } : { style_id: styleId }}
      onDone={onDone} onClose={onClose}>
      {unitId && <Form.Item name="order_unit_id" hidden><InputNumber /></Form.Item>}
      <Form.Item name={styleField} label="款式" rules={required}>
        <RemoteSelect resource="styles" onChange={() => form.setFieldValue(unitId ? ["physical", "spec"] : "spec", undefined)} />
      </Form.Item>
      <Button onClick={() => setCreatingStyle(true)}>新建款式</Button>
      <PhysicalFields nested={!!unitId} />
    </ActionForm>
    {creatingStyle && <StyleEditor page={false} onClose={() => setCreatingStyle(false)} onDone={(r) => {
      form.setFieldValue(styleField, r.id);
      form.setFieldValue(unitId ? ["physical", "spec"] : "spec", undefined);
      setCreatingStyle(false);
    }} />}
  </>;
}

function IdentityFields() {
  const form = Form.useFormInstance();
  const issue = useRecord("issues", Form.useWatch("issue_id", form)).record;
  const pending = issue?.mode === "period" && !issue.sealed_at;
  useEffect(() => {
    if (!issue) return;
    if (!form.getFieldValue("item_uid")) form.setFieldValue("item_uid", issue.suggested_item_uid);
    if (pending) form.setFieldValue("edition_number", undefined);
    else if (!form.getFieldValue("edition_number")) form.setFieldValue("edition_number", issue.suggested_edition_number);
  }, [issue, form, pending]);
  return <>
    <Form.Item name="item_uid" label="数字物品编号" rules={required}><Input maxLength={32} /></Form.Item>
    {pending ? <Typography.Text>本件正式编号待发行核定</Typography.Text> :
      <Form.Item name="edition_number" label="本件正式序号" rules={required}>
        <InputNumber min={1} max={issue?.total || undefined} precision={0} />
      </Form.Item>}
  </>;
}

export default function ItemAssembly() {
  const location = useLocation();
  const q = new URLSearchParams(location.search);
  const issueId = Number(q.get("issue_id")) || undefined;
  const physicalId = Number(q.get("physical_item_id")) || undefined;
  const chipId = Number(q.get("chip_id")) || undefined;
  const unitId = Number(q.get("order_unit_id")) || undefined;
  const target = returnPath("/items");
  const issue = useRecord("issues", issueId);
  const physical = useRecord("physical-items", physicalId);
  const chip = useRecord("chips", chipId);
  return (
    <PageContainer title="新建数字物品" onBack={() => history.push(target)}>
      <Load error={issue.error || physical.error || chip.error} loading={issue.loading || physical.loading || chip.loading}
        retry={() => { issue.reload(); physical.reload(); chip.reload(); }}>
        {(!issueId || issue.record) && (!physicalId || physical.record) && (!chipId || chip.record) &&
          <Assembly key={location.search} issue={issue.record} physical={physical.record}
            chip={chip.record} unitId={unitId} target={target} />}
      </Load>
    </PageContainer>
  );
}

function Assembly({ issue, physical, chip, unitId, target }: {
  issue?: Row; physical?: Row; chip?: Row; unitId?: number; target: string;
}) {
  const [form] = Form.useForm();
  const [styleId, setStyleId] = useState<number | undefined>(physical?.style_id || issue?.style_id);
  const [selectedIssue, setSelectedIssue] = useState<number | undefined>(issue?.id);
  const [supplement, setSupplement] = useState<Supplement>();
  const [draftIssue, setDraftIssue] = useState<number>();
  const [mode, setMode] = useState<"assemble" | "draft">("assemble");
  const chosenIssue = useRecord("issues", selectedIssue).record;
  const style = useRecord("styles", styleId).record;
  const currentPhysical = useRecord("physical-items", Form.useWatch("physical_item_id", form) || physical?.id).record;
  const currentChip = useRecord("chips", Form.useWatch("chip_id", form) || chip?.id).record;
  const [initial] = useState({
    issue_id: issue?.id, physical_item_id: physical?.id, chip_id: chip?.id, order_unit_id: unitId,
  });
  useEffect(() => {
    if (chosenIssue && !styleId) setStyleId(chosenIssue.style_id);
  }, [chosenIssue, styleId]);

  function chooseStyle(id: number) {
    setStyleId(id);
    setSelectedIssue(undefined);
    form.setFieldsValue({ issue_id: undefined, physical_item_id: undefined, edition_number: undefined });
  }

  function chooseIssue(id: number) {
    setSelectedIssue(id);
    form.setFieldsValue({ issue_id: id, edition_number: undefined });
  }

  return <>
    <ProCard variant="outlined">
      <Space direction="vertical" className="page-stack">
        <Typography.Text strong>款式</Typography.Text>
        {physical ? <Typography.Text>{physical.style_name} · 实体 {physical.physical_uid}</Typography.Text> :
          <Space wrap>
            <RemoteSelect resource="styles" value={styleId} onChange={(id) => chooseStyle(Number(id))} />
            <Button onClick={() => setSupplement("style")}>新建款式</Button>
          </Space>}
        {!unitId && <Select value={mode} options={[
          { value: "assemble", label: "建档并确认安装" },
          { value: "draft", label: "只建档，稍后装配" },
        ]} onChange={setMode} />}
      </Space>
      <ActionForm page formInstance={form} title="物品资料与装配" submitText={mode === "assemble" ? "确认安装" : "保存数字档案"}
        action={mode === "assemble" ? "assembleOrderItem" : "item"} initial={initial}
        onClose={() => history.push(target)}
        onDone={(r) => history.push(target.split("?")[0] === "/items" ? "/items/" + r.id + "?from=" + encodeURIComponent(target) : target)}>
        {unitId && <Form.Item name="order_unit_id" hidden><InputNumber /></Form.Item>}
        <Form.Item name="issue_id" label="已确认发行" rules={required}>
          <RemoteSelect resource="issues" params={{ style_id: styleId, status: "confirmed" }} onChange={(id) => chooseIssue(Number(id))} />
        </Form.Item>
        <Space wrap>
          <Button disabled={!styleId} onClick={() => setSupplement("issue")}>新建发行草案</Button>
          <Button disabled={!styleId} onClick={() => { setDraftIssue(undefined); setSupplement("confirm"); }}>确认已有草案</Button>
        </Space>
        <IdentityFields />
        <Form.Item name="is_validation" valuePropName="checked"><Checkbox>标记为生产验证对象</Checkbox></Form.Item>
        {mode === "assemble" && <>
          <Form.Item name="physical_item_id" label="实体物品" rules={required} preserve={false}>
            {physical ? <ReadOnlyValue text={physical.physical_uid + " · " + (physical.spec || "规格不适用")} /> :
              <RemoteSelect resource="physical-items" params={{ style_id: styleId, available: true }} />}
          </Form.Item>
          {!physical && <Button disabled={!styleId} onClick={() => setSupplement("physical")}>登记新实物</Button>}
          <Form.Item name="chip_id" label="芯片 UID" rules={required} preserve={false}>
            {chip ? <ReadOnlyValue text={chip.chip_uid} /> :
              <RemoteSelect resource="chips" params={{ available: true, compatible_project: chosenIssue?.project || style?.project }} />}
          </Form.Item>
          {!chip && <Button onClick={() => setSupplement("chip")}>登记新芯片</Button>}
          {currentPhysical && currentChip && <Alert type="info" title={
            "请核对 " + currentPhysical.physical_uid + " · " + (currentPhysical.spec || "规格不适用") + " · " + currentChip.chip_uid
          } />}
          <Form.Item name="installed" valuePropName="checked" preserve={false}
            rules={[{ validator: (_, value) => value === true ? Promise.resolve() : Promise.reject("请先确认实际安装") }]}>
            <Checkbox>已将所选芯片安装到这件实物</Checkbox>
          </Form.Item>
        </>}
      </ActionForm>
    </ProCard>
    {supplement === "style" && <StyleEditor page={false} onClose={() => setSupplement(undefined)} onDone={(r) => {
      chooseStyle(r.id); setSupplement(undefined);
    }} />}
    {supplement === "issue" && <ActionForm title="发行约定草案" submitText="保存草案" action="issue"
      initial={{ style_id: styleId, mode: "fixed" }} onClose={() => setSupplement(undefined)}
      onDone={(r) => { setDraftIssue(r.id); setSupplement("confirm"); }}>
      <IssueFields />
    </ActionForm>}
    {supplement === "confirm" && <ActionForm title="确认发行约定" submitText="确认发行" action="confirmIssue"
      initial={{ issue_id: draftIssue }} onClose={() => setSupplement(undefined)}
      onDone={(r) => { chooseIssue(r.id); setSupplement(undefined); }}>
      <Form.Item name="issue_id" label="同款发行草案" rules={required}>
        <RemoteSelect resource="issues" params={{ style_id: styleId, status: "draft" }} />
      </Form.Item>
      <Form.Item name="evidence" label="发行确认依据" rules={required}><Input.TextArea maxLength={1000} /></Form.Item>
      <Form.Item name="confirmed" valuePropName="checked" rules={[{ validator: (_, value) => value === true ? Promise.resolve() : Promise.reject("请先核对发行承诺") }]}><Checkbox>已核对款式、规格承诺、数量和编号规则</Checkbox></Form.Item>
    </ActionForm>}
    {supplement === "physical" && <ActionForm title="登记新实物" submitText="保存实体" action="createPhysicalItem"
      initial={{ style_id: styleId }} onClose={() => setSupplement(undefined)}
      onDone={(r) => { form.setFieldValue("physical_item_id", r.id); setSupplement(undefined); }}>
      <Form.Item name="style_id" hidden><InputNumber /></Form.Item>
      <PhysicalFields />
    </ActionForm>}
    {supplement === "chip" && <ActionForm title="登记新芯片" submitText="登记芯片" action="register"
      initial={{}} onClose={() => setSupplement(undefined)}
      onDone={(r) => { form.setFieldValue("chip_id", r.id); setSupplement(undefined); }}>
      <Form.Item name="chip_uid" label="芯片 UID" rules={required}><Input maxLength={32} /></Form.Item>
      <Form.Item name="batch_no" label="芯片批次"><Input maxLength={64} /></Form.Item>
    </ActionForm>}
  </>;
}

function ReadOnlyValue({ text }: { text: string; value?: number }) {
  return <Typography.Text>{text}</Typography.Text>;
}
