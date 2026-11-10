import { useEffect, useState } from "react";
import { PageContainer, ProCard } from "@ant-design/pro-components";
import { history, useLocation, useParams } from "@umijs/max";
import { Alert, Button, Checkbox, DatePicker, Descriptions, Dropdown, Form, Input, InputNumber, Modal, Select, Space, Typography } from "antd";
import { ActionForm, Load, RemoteSelect, State, required, useRecord } from "../components/CatalogUI";
import KeyConfiguration from "../components/KeyConfiguration";
import StyleEditor from "../components/StyleEditor";
import ServerTable from "../components/ServerTable";
import UserIdentity from "../components/UserIdentity";
import { inputDate, inputISO } from "../businessTime";
import { assemblyPath, orderPath, Row, time } from "../catalog";
import { testBatch } from "../testDataMode";
import { OrderPreparationQueue } from "./OrderPreparation";
import { RegisterPhysical } from "./ItemAssembly";

const titleFor: Record<string, string> = {
  physical: "选用已有实物",
  allocate: "确认分配",
  release: "释放未售占用",
  sale: "确认首次售出",
  delivery: "核对实际交付并发码",
  enable: "启用数字物品",
};

function unitStatus(unit: Row) {
  if (unit.delivered_at) return unit.holder_uid ? "已认领" : "待认领";
  if (!unit.expected_style_id) return "待核对款式规格";
  if (unit.physical_item_id && !unit.physical_matches) return "待纠正实物";
  if (unit.sold) return "待交付";
  if (unit.item_id && unit.whole_id) {
    if (unit.lost_at || unit.loss_evidence || unit.chip_status !== "bound") return "待核对装配";
    if (!unit.provisioned_at) return "待核验";
    return unit.item_status === "active" ? unit.allocated_at ? "待售出" : "待分配" : "待启用";
  }
  return unit.physical_item_id ? "待装配" : "待准备";
}

export default function Orders() {
  const { id } = useParams();
  const [creating, setCreating] = useState(false);
  if (id) return <OrderDetail id={Number(id)} />;
  return <PageContainer title={false}>
    <ServerTable resource="orders" columns={[
      { title: "订单号或渠道", dataIndex: "keyword", hideInTable: true },
      { title: "订单号", dataIndex: "external_order_no", search: false,
        render: (_, r) => <Button type="link" onClick={() => history.push("/orders/" + r.id)}>{r.external_order_no}</Button> },
      { title: "渠道", dataIndex: "channel", search: false },
      { title: "交付进度", search: false, render: (_, r) => r.delivered_count + " / " + r.unit_count + " 件" },
      { title: "登记时间", search: false, render: (_, r) => time(r.created_at) },
    ]} extra={[<Button key="create" type="primary" onClick={() => setCreating(true)}>新建订单</Button>]} />
    <OrderPreparationQueue />
    {creating && <ActionForm title="新建订单" action="createOrder" submitText="保存并打开订单"
      initial={{ units: [{}] }} onClose={() => setCreating(false)} onDone={(r) => history.push("/orders/" + r.id)}>
      <Form.Item name="channel" label="成交渠道" rules={required}><Input maxLength={40} /></Form.Item>
      <Form.Item name="external_order_no" label="外部订单号" rules={required}><Input maxLength={64} /></Form.Item>
      <Typography.Paragraph type="secondary">按订单原文录入，每件单独办理。款式和发行可以在准备时补齐。</Typography.Paragraph>
      <Form.List name="units">
        {(fields, { add, remove }) => <>
          {fields.map((field, index) => <ProCard key={field.key} title={"第 " + (index + 1) + " 件"} size="small"
            extra={fields.length > 1 && <Button onClick={() => remove(field.name)}>移除</Button>}>
            <Form.Item name={[field.name, "product_name"]} label="购买商品" rules={required}><Input maxLength={128} /></Form.Item>
            <Form.Item name={[field.name, "ordered_spec"]} label="购买规格"><Input maxLength={256} /></Form.Item>
          </ProCard>)}
          <Button disabled={fields.length >= 100} onClick={() => add()}>增加一件</Button>
        </>}
      </Form.List>
    </ActionForm>}
  </PageContainer>;
}

function OrderDetail({ id }: { id: number }) {
  const state = useRecord("orders", id);
  const q = new URLSearchParams(useLocation().search);
  const unitId = Number(q.get("unit"));
  const order = state.record;
  useEffect(() => {
    if (order && unitId) document.getElementById("order-unit-" + unitId)?.scrollIntoView({ block: "nearest" });
  }, [order, unitId]);
  const canEdit = (order?.test_batch_id || undefined) === testBatch();
  return <PageContainer title={order?.external_order_no || "订单详情"} subTitle={order?.channel}
    onBack={() => history.push("/orders")}>
    <Load error={state.error} loading={state.loading} retry={state.reload}>
      {order && <div className="page-stack">
        {!canEdit && <Alert type="warning" title="该订单属于另一数据范围，切换到对应范围后可继续办理。" />}
        <Space wrap aria-label="定位订单件">
          {order.units.map((unit: Row) => <Button key={unit.id} type={unitId === unit.id ? "primary" : "default"}
            onClick={() => { history.replace(orderPath(id, unit.id)); document.getElementById("order-unit-" + unit.id)?.scrollIntoView({ block: "nearest" }); }}>
            第 {unit.position} 件 · {unitStatus(unit)}
          </Button>)}
        </Space>
        {order.units.map((unit: Row) => <OrderUnit key={unit.id} unit={unit} active={unitId === unit.id}
          canEdit={canEdit} reload={state.reload} />)}
      </div>}
    </Load>
  </PageContainer>;
}

function OrderUnit({ unit, active, canEdit, reload }: { unit: Row; active: boolean; canEdit: boolean; reload: () => void }) {
  const [dialog, setDialog] = useState<string>();
  const [claim, setClaim] = useState<Row>();
  const [configure, setConfigure] = useState(false);
  const href = orderPath(unit.order_id, unit.id);
  const itemHref = "/items/" + unit.item_id + "?from=" + encodeURIComponent(href);
  const status = unitStatus(unit);
  const action = (name: string, label: string, primary = false) =>
    <Button key={name} type={primary ? "primary" : "default"} onClick={() => setDialog(name)}>{label}</Button>;
  function done() {
    setDialog(undefined);
    setConfigure(false);
    history.replace(href);
    reload();
  }
  return <section id={"order-unit-" + unit.id}>
    <ProCard title={"第 " + unit.position + " 件 · " + unit.product_name} headerBordered
      extra={<Space><State value={status} />{active && <Typography.Text type="secondary">当前办理</Typography.Text>}</Space>}>
      <Descriptions size="small" column={{ xs: 1, md: 2 }}>
        <Descriptions.Item label="购买规格">{unit.ordered_spec || "未提供"}</Descriptions.Item>
        <Descriptions.Item label="核对后要求">{unit.expected_style_name ?
          unit.expected_style_name + " · " + (unit.expected_spec || "无指定规格") : "待核对"}</Descriptions.Item>
        <Descriptions.Item label={unit.delivered_at ? "交付时实物" : "已准备实物"}>
          {(unit.delivered_at ? unit.delivered_physical_uid : unit.physical_uid) || "未选择"}
          {(unit.delivered_at ? unit.delivered_spec : unit.spec) && " · " + (unit.delivered_at ? unit.delivered_spec : unit.spec)}
        </Descriptions.Item>
        <Descriptions.Item label="数字物品">
          {unit.item_id ? <Button type="link" onClick={() => history.push(itemHref)}>{unit.item_uid}</Button> : "未选择"}
        </Descriptions.Item>
        {unit.allocated_at && <Descriptions.Item label="分配时间">{time(unit.allocated_at)}</Descriptions.Item>}
        {unit.sold && <Descriptions.Item label="首次成交">{time(unit.first_sold_at)}</Descriptions.Item>}
        {unit.delivered_at && <>
          <Descriptions.Item label="实际交付时间">{time(unit.delivered_at)}</Descriptions.Item>
          <Descriptions.Item label="交付芯片与代次">第 {unit.delivered_generation} 代 · {unit.delivered_chip_uid}</Descriptions.Item>
          <Descriptions.Item label="首次交付依据">{unit.first_delivery_reference}</Descriptions.Item>
          <Descriptions.Item label="认领码状态">{unit.claim_consumed_at ? "已核销" : unit.claim_revoked_at ? "已撤销" :
            Date.parse(unit.claim_expires_at) <= Date.now() ? "已过期" : "有效至 " + time(unit.claim_expires_at)}</Descriptions.Item>
          <Descriptions.Item label="当前持有人">{unit.holder_uid ? <UserIdentity uid={unit.holder_uid} /> : "待认领"}</Descriptions.Item>
        </>}
      </Descriptions>
      {status === "待纠正实物" && <Alert type="warning" title="已占用实物与核对后的款式或规格不一致"
        description={unit.sold ? "请核对成交和实物记录后再交付。" : "请释放未售占用，再选用与订单要求一致的物品。"} />}
      {canEdit && <Space wrap>
        {status === "待核对款式规格" && action("match", "核对款式与规格", true)}
        {status === "待准备" && <>
          <Dropdown trigger={["click"]} menu={{ items: [
            { key: "allocate", label: "选用已就绪数字库存" },
            { key: "physical", label: "选用已有实物" },
            { key: "new", label: "登记新实物" },
          ], onClick: ({ key }) => setDialog(key) }}>
            <Button type="primary">准备物品</Button>
          </Dropdown>
          {action("match", "更正款式与规格")}
        </>}
        {status === "待装配" && <Button type="primary" onClick={() => history.push(unit.item_id ?
          "/items/" + unit.item_id + "?install=1&from=" + encodeURIComponent(href) :
          assemblyPath(href, { order_unit_id: unit.id, physical_item_id: unit.physical_item_id }))}>开始装配</Button>}
        {status === "待核验" && <Button type="primary" onClick={() => setConfigure(true)}>配置并核验芯片</Button>}
        {status === "待核对装配" && <Button type="primary" onClick={() => history.push(itemHref)}>核对数字物品档案</Button>}
        {status === "待启用" && action("enable", "启用数字物品", true)}
        {status === "待分配" && action("allocate", "确认分配", true)}
        {status === "待售出" && action("sale", "确认首次售出", true)}
        {status === "待交付" && action("delivery", "核对实际交付并发码", true)}
        {!unit.sold && !unit.delivered_at && unit.physical_item_id && action("release", "释放未售占用")}
      </Space>}
    </ProCard>
    {configure && unit.chip_id && <KeyConfiguration id={unit.chip_id} onUpdated={reload} onClose={done} />}
    {dialog === "match" && <OrderMatchDialog unit={unit} onClose={() => setDialog(undefined)} onDone={done} />}
    {dialog === "new" && <RegisterPhysical orderUnit={unit} onClose={() => setDialog(undefined)} onDone={done} />}
    {dialog && dialog !== "new" && dialog !== "match" && <ActionForm title={titleFor[dialog]} submitText={titleFor[dialog]}
      action={({ physical: "orderPhysical", allocate: "allocateOrderUnit", release: "releaseOrderUnit",
        sale: "orderSale", delivery: "issueClaimCode", enable: "toggleItem" } as Record<string, string>)[dialog]}
      initial={{ order_unit_id: unit.id, item_id: unit.item_id || undefined, status: "active", first_sold_at: inputISO(inputDate()) }}
      onClose={() => setDialog(undefined)} onDone={(r) => { if (dialog === "delivery") setClaim(r); done(); }}>
      <OrderFacts unit={unit} actual={unit.physical_uid ? unit : undefined} />
      {dialog === "enable" && <Alert type="info" title="启用后可继续分配，首次售出另行确认。" />}
      {dialog === "release" && <Alert type="warning" title="释放后该件需重新准备物品，已登记的实物和装配记录保留。" />}
      {["physical", "allocate", "release", "sale"].includes(dialog) && <Form.Item name="order_unit_id" hidden><InputNumber /></Form.Item>}
      {dialog === "physical" && <Form.Item name="physical_item_id" label="可用实物" rules={required}>
        <RemoteSelect resource="physical-items" params={{ order_unit_id: unit.id }} placeholder="搜索已核对款式和规格的可用实物" />
      </Form.Item>}
      {dialog === "allocate" && !unit.item_id ?
        <Form.Item name="item_id" label="可分配数字库存" rules={required}>
          <RemoteSelect resource="items" params={{ order_unit_id: unit.id }} placeholder="搜索同款同规格的就绪库存"
            optionLabel={(r) => [r.item_uid, r.name, r.spec].filter(Boolean).join(" · ")} />
        </Form.Item> : ["allocate", "sale", "delivery", "enable"].includes(dialog) &&
        <Form.Item name="item_id" hidden><InputNumber /></Form.Item>}
      {dialog === "release" && <Form.Item name="evidence" label="释放依据" rules={required}><Input.TextArea maxLength={1000} /></Form.Item>}
      {dialog === "sale" && <Form.Item name="first_sold_at" label="实际首次成交（北京时间）" rules={required}
        getValueProps={(v) => ({ value: v ? inputDate(v) : undefined })} normalize={(v) => v ? inputISO(v) : undefined}>
        <DatePicker showTime />
      </Form.Item>}
      {dialog === "delivery" && <>
        <Form.Item name="delivery_reference" label="首次交付核对依据" rules={required}><Input maxLength={128} /></Form.Item>
        <Form.Item name="confirmed" valuePropName="checked"
          rules={[{ validator: (_, v) => v === true ? Promise.resolve() : Promise.reject("请确认实际交付与接收对象") }]}>
          <Checkbox>已核对实际交付与接收对象</Checkbox>
        </Form.Item>
      </>}
      {dialog === "enable" && <Form.Item name="status" hidden><Input /></Form.Item>}
    </ActionForm>}
    {claim && <Modal open title="交付认领码" onCancel={() => setClaim(undefined)}
      footer={<Button onClick={() => setClaim(undefined)}>完成</Button>}>
      {claim.claim_code ? <><Typography.Paragraph copyable>{claim.claim_code}</Typography.Paragraph><p>有效期至 {time(claim.expires_at)}。</p></> :
        <Alert type="info" title="已核对发放记录" description="如需新码，从数字物品档案核对交付后补发。" />}
    </Modal>}
  </section>;
}

function OrderFacts({ unit, actual }: { unit: Row; actual?: Row }) {
  return <Descriptions size="small" bordered column={1} style={{ marginBottom: 16 }}>
    <Descriptions.Item label="订单件">{unit.external_order_no} · 第 {unit.position} 件</Descriptions.Item>
    <Descriptions.Item label="订单原文">{unit.product_name} · {unit.ordered_spec || "未提供购买规格"}</Descriptions.Item>
    {unit.expected_style_name && <Descriptions.Item label="核对后要求">
      {unit.expected_style_name} · {unit.expected_spec || "无指定规格"}
    </Descriptions.Item>}
    {actual && <>
      <Descriptions.Item label="实际分配">{actual.physical_style_name} · {actual.spec || "无规格"}</Descriptions.Item>
      <Descriptions.Item label="数字编号与实体编号">{actual.item_uid || "待装配"} · {actual.physical_uid}</Descriptions.Item>
    </>}
  </Descriptions>;
}

function OrderMatchDialog({ unit, onClose, onDone }: { unit: Row; onClose: () => void; onDone: () => void }) {
  const [form] = Form.useForm();
  const [creatingStyle, setCreatingStyle] = useState(false);
  const styleId = Form.useWatch("style_id", form);
  const style = useRecord("styles", styleId);
  const chosen = style.record?.id === styleId ? style.record : undefined;
  const specs: string[] = chosen?.specs || [];
  const requiredSpec = !!(specs.length || unit.ordered_spec);
  return <>
    <ActionForm title="核对款式与规格" action="matchOrderUnit" submitText="确认款式与规格"
      initial={{ order_unit_id: unit.id, style_id: unit.expected_style_id ?? undefined,
        spec: unit.expected_spec ?? undefined }}
      formInstance={form} onClose={onClose} onDone={onDone} submitDisabled={!chosen || creatingStyle}>
      <OrderFacts unit={unit} actual={unit.physical_uid ? unit : undefined} />
      <Form.Item name="order_unit_id" hidden><InputNumber /></Form.Item>
      <Form.Item name="style_id" label="对应款式" rules={required}
        extra={<Button type="link" onClick={() => setCreatingStyle(true)}>补建款式</Button>}>
        <RemoteSelect resource="styles" onChange={() => form.setFieldValue("spec", undefined)} />
      </Form.Item>
      {style.error && <Alert type="error" title={style.error} action={<Button onClick={style.reload}>重试</Button>} />}
      {chosen && <Form.Item name="spec" label="对应规格" rules={requiredSpec ? required : []}
        extra={requiredSpec ? "按订单原文核对目录规格，之后只显示符合要求的实物。" : "此订单件未指定规格，可按款式筛选。"}>
        {specs.length ? <Select options={specs.map((spec) => ({ value: spec, label: spec }))} /> :
          <Input maxLength={256} />}
      </Form.Item>}
    </ActionForm>
    {creatingStyle && <StyleEditor page={false} compact onClose={() => setCreatingStyle(false)} onDone={(result) => {
      form.setFieldsValue({ style_id: result.id, spec: undefined });
      setCreatingStyle(false);
    }} />}
  </>;
}
