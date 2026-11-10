import { useEffect, useState } from "react";
import { PageContainer, ProCard } from "@ant-design/pro-components";
import { history, useLocation } from "@umijs/max";
import { Alert, Button, Checkbox, Collapse, Descriptions, Form, Input, InputNumber, Select, Space, Switch, Typography } from "antd";
import { ActionForm, Load, RemoteSelect, required, returnPath, useRecord } from "../components/CatalogUI";
import { ChipRegistrationFields, InstallationConfirmation } from "../components/AssemblyFields";
import StyleEditor from "../components/StyleEditor";
import { IssueFields } from "./Catalog";
import { Row, statusNames } from "../catalog";

type Supplement = "style" | "issue" | "confirm" | "physical" | "chip";

export function PhysicalFields({ nested = false, fixedSpec }: { nested?: boolean; fixedSpec?: string }) {
  const field = (name: string) => nested ? ["physical", name] : name;
  const style = useRecord("styles", Form.useWatch(field("style_id"))).record;
  return <>
    <Form.Item name={field("physical_uid")} label="实体编号" rules={required}><Input maxLength={64} /></Form.Item>
    {fixedSpec ? <Form.Item name={field("spec")} hidden><Input /></Form.Item> : <Form.Item name={field("spec")} label="实际规格" rules={style?.specs?.length ? required : []}>
      {style?.specs?.length ? <Select options={style.specs.map((spec: string) => ({ label: spec, value: spec }))} /> : <Input maxLength={256} placeholder="填写实物尺码、颜色等信息" />}
    </Form.Item>}
    <Form.Item name={field("batch_no")} label="实物批次"><Input maxLength={64} /></Form.Item>
    <Form.Item name={field("supplier_serial")} label="供应商序列号"><Input maxLength={128} /></Form.Item>
  </>;
}

export function RegisterPhysical({ orderUnit, onClose, onDone }: {
  orderUnit?: Row; onClose: () => void; onDone: (r: Row) => void;
}) {
  const [creatingStyle, setCreatingStyle] = useState(false);
  const [form] = Form.useForm();
  const unitId = orderUnit?.id;
  return <>
    <ActionForm title="登记实体物品" submitText={unitId ? "登记并用于本件" : "登记实物"}
      formInstance={form} action={unitId ? "orderPhysical" : "createPhysicalItem"}
      initial={unitId ? { order_unit_id: unitId, physical: { style_id: orderUnit.expected_style_id, spec: orderUnit.expected_spec } } : {}}
      onDone={onDone} onClose={onClose}>
      {orderUnit ? <>
        <Alert type="info" title={orderUnit.expected_style_name + " · " + (orderUnit.expected_spec || "无指定规格")} />
        <Form.Item name="order_unit_id" hidden><InputNumber /></Form.Item>
        <Form.Item name={["physical", "style_id"]} hidden><InputNumber /></Form.Item>
      </> : <>
        <Form.Item name="style_id" label="款式" rules={required}
          extra={<Button type="link" onClick={() => setCreatingStyle(true)}>补建款式</Button>}>
          <RemoteSelect resource="styles" onChange={() => form.setFieldValue("spec", undefined)} />
        </Form.Item>
      </>}
      <PhysicalFields nested={!!unitId} fixedSpec={orderUnit?.expected_spec} />
    </ActionForm>
    {creatingStyle && <StyleEditor page={false} compact returnTo="保存后返回实物登记并选中新款式。" onClose={() => setCreatingStyle(false)} onDone={(r) => {
      form.setFieldsValue({ style_id: r.id, spec: undefined });
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
  const orderId = unitId ? Number(/^\/orders\/(\d+)/.exec(target)?.[1]) || undefined : undefined;
  const order = useRecord("orders", orderId);
  const unit = order.record?.units?.find((u: Row) => u.id === unitId);
  const issue = useRecord("issues", issueId);
  const physical = useRecord("physical-items", physicalId);
  const chip = useRecord("chips", chipId);
  return (
    <PageContainer title={unitId ? "装配订单物品" : "新建数字物品"} onBack={() => history.push(target)}>
      <Load error={issue.error || physical.error || chip.error || order.error} loading={issue.loading || physical.loading || chip.loading || order.loading}
        retry={() => { issue.reload(); physical.reload(); chip.reload(); order.reload(); }}>
        {unit && <Alert type="info" title={unit.external_order_no + " · 第 " + unit.position + " 件"}
          description={unit.product_name + " · " + (unit.ordered_spec || "原单无规格") + " → " + unit.expected_style_name + " · " + (unit.expected_spec || "无指定规格")} />}
        {(!unitId || (unit && unit.physical_matches)) && (!issueId || issue.record) && (!physicalId || physical.record) && (!chipId || chip.record) &&
          <Assembly key={location.search} issue={issue.record} physical={physical.record}
            chip={chip.record} unitId={unitId} target={target} />}
        {unitId && !order.loading && (orderId === undefined || (order.record && !unit?.physical_matches)) &&
          <Alert type="warning" title="请回原订单件核对款式和规格后再装配。" />}
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
  const [initial] = useState({
    issue_id: issue?.id, physical_item_id: physical?.id, chip_id: chip?.id, order_unit_id: unitId,
  });
  useEffect(() => {
    if (chosenIssue && !styleId) setStyleId(chosenIssue.style_id);
  }, [chosenIssue, styleId]);

  function chooseStyle(id: number) {
    setStyleId(id);
    setSelectedIssue(undefined);
    form.setFieldsValue({ issue_id: undefined, physical_item_id: undefined, edition_number: undefined, installed: false });
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
            <Button type="link" onClick={() => setSupplement("style")}>补建款式</Button>
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
        <Form.Item name="issue_id" label="已确认发行" rules={required} extra={styleId && !selectedIssue && <Space wrap>
          <Button type="link" onClick={() => setSupplement("issue")}>新建发行草案</Button>
          <Button type="link" onClick={() => { setDraftIssue(undefined); setSupplement("confirm"); }}>确认已有草案</Button>
        </Space>}>
          <RemoteSelect resource="issues" params={{ style_id: styleId, status: "confirmed" }} onChange={(id) => chooseIssue(Number(id))} />
        </Form.Item>
        <IdentityFields />
        {mode === "assemble" && <>
          <Form.Item name="physical_item_id" label="实体物品" rules={required} preserve={false}
            extra={!physical && styleId && <Button type="link" onClick={() => setSupplement("physical")}>登记新实物</Button>}>
            {physical ? <ReadOnlyValue text={physical.physical_uid + " · " + (physical.spec || "规格不适用")} /> :
              <RemoteSelect resource="physical-items" params={{ style_id: styleId, available: true }} />}
          </Form.Item>
          <Form.Item name="chip_id" label="芯片 UID" rules={required} preserve={false}
            extra={!chip && <Button type="link" onClick={() => setSupplement("chip")}>登记新芯片</Button>}>
            {chip ? <ReadOnlyValue text={chip.chip_uid} /> :
              <RemoteSelect resource="chips" params={{ available: true, compatible_project: chosenIssue?.project || style?.project }} />}
          </Form.Item>
          <InstallationConfirmation />
        </>}
        <Collapse size="small" items={[{ key: "advanced", label: "高级选项",
          children: <Form.Item name="is_validation" label="标记为生产验证对象" valuePropName="checked"><Switch /></Form.Item>,
        }]} />
      </ActionForm>
    </ProCard>
    {supplement === "style" && <StyleEditor page={false} compact returnTo="保存后返回数字物品建档并选中新款式。" onClose={() => setSupplement(undefined)} onDone={(r) => {
      chooseStyle(r.id); setSupplement(undefined);
    }} />}
    {supplement === "issue" && <ActionForm title="发行约定草案" submitText="保存并继续确认" action="issue"
      initial={{ style_id: styleId, mode: "fixed" }} onClose={() => setSupplement(undefined)}
      onDone={(r) => { setDraftIssue(r.id); setSupplement("confirm"); }}>
      <IssueFields />
    </ActionForm>}
    {supplement === "confirm" && <ActionForm title="确认发行约定" submitText="确认并带回" action="confirmIssue"
      initial={{ issue_id: draftIssue }} onClose={() => setSupplement(undefined)}
      onDone={(r) => { chooseIssue(r.id); setSupplement(undefined); }}>
      <Form.Item name="issue_id" label="同款发行草案" rules={required}>
        <RemoteSelect resource="issues" params={{ style_id: styleId, status: "draft" }} />
      </Form.Item>
      <IssueConfirmation />
    </ActionForm>}
    {supplement === "physical" && <ActionForm title="登记实体物品" submitText="登记并带回" action="createPhysicalItem"
      initial={{ style_id: styleId }} onClose={() => setSupplement(undefined)}
      onDone={(r) => { form.setFieldValue("physical_item_id", r.id); setSupplement(undefined); }}>
      <Form.Item name="style_id" hidden><InputNumber /></Form.Item>
      <PhysicalFields />
    </ActionForm>}
    {supplement === "chip" && <ActionForm title="手工登记芯片" submitText="登记并带回" action="register"
      initial={{}} onClose={() => setSupplement(undefined)}
      onDone={(r) => { form.setFieldValue("chip_id", r.id); setSupplement(undefined); }}>
      <ChipRegistrationFields />
    </ActionForm>}
  </>;
}

function ReadOnlyValue({ text }: { text: string; value?: number }) {
  return <Typography.Text>{text}</Typography.Text>;
}

function IssueConfirmation() {
  const form = Form.useFormInstance();
  const issueId = Form.useWatch("issue_id", form);
  const { record } = useRecord("issues", issueId);
  const issue = record?.id === issueId ? record : undefined;
  useEffect(() => { form.setFieldValue("confirmed", false); }, [form, issueId]);
  return <>
    {issue && <Descriptions size="small" bordered column={1}>
      <Descriptions.Item label="款式">{issue.style_name}</Descriptions.Item>
      <Descriptions.Item label="发行方式">{statusNames[issue.mode]}{issue.total ? " · " + issue.total + " 个身份" : ""}</Descriptions.Item>
      <Descriptions.Item label="发行说明与规格承诺">{issue.description || "未填写"}</Descriptions.Item>
      <Descriptions.Item label="序号">{issue.mode === "period" && !issue.sealed_at ? "核定后分配正式序号" : "同一发行的正式序号不可重复"}</Descriptions.Item>
    </Descriptions>}
    <Form.Item name="evidence" label="发行确认依据" rules={required}><Input.TextArea maxLength={1000} /></Form.Item>
    <Form.Item name="confirmed" valuePropName="checked" dependencies={["issue_id"]}
      rules={[{ validator: (_, value) => issue && value === true ? Promise.resolve() : Promise.reject("请先核对当前发行约定") }]}>
      <Checkbox disabled={!issue}>已核对款式、规格承诺、数量和编号规则</Checkbox>
    </Form.Item>
  </>;
}
