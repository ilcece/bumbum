import { useLayoutEffect, useRef, useState } from "react";
import { PageContainer, ProCard } from "@ant-design/pro-components";
import { history, useLocation, useModel } from "@umijs/max";
import {
  Alert, Button, Checkbox, DatePicker, Descriptions, Form, Input, InputNumber,
  List, Modal, Radio, Space, Steps, Typography,
} from "antd";
import { ApiError } from "../api";
import { inputDate, inputISO } from "../businessTime";
import { command, edition, Row, time, unknown } from "../catalog";
import { Copy, Load, RemoteSelect, required, useRecord } from "../components/CatalogUI";
import KeyConfiguration from "../components/KeyConfiguration";
import { testBatch } from "../testDataMode";

const path = "/overview/order-preparation";
type Draft = {
  id: string;
  route: "new" | "stock";
  channel?: string;
  external_order_no?: string;
  physical_item_id?: number;
  item_id?: number;
  item_uid?: string;
  physical_uid?: string;
  sold?: boolean;
  completed?: boolean;
  values?: Record<string, any>;
  pending?: { action: string; requestId: string; payload: Record<string, any> };
};

function useDraftKey() {
  const { initialState } = useModel("@@initialState");
  const scope = initialState?.session?.draft_scope;
  return scope && /^[a-f0-9]{64}$/.test(scope)
    ? `bumbum-order-preparation-v1:${scope}:${testBatch() ?? "business"}`
    : undefined;
}

function drafts(key: string): Draft[] {
  try {
    const data = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(data) ? data.filter((entry) =>
      entry && typeof entry.id === "string" && ["new", "stock"].includes(entry.route)) : [];
  } catch {
    return [];
  }
}

export function OrderPreparationQueue() {
  const key = useDraftKey();
  const entries = key ? drafts(key).filter((entry) => !entry.completed) : [];
  if (!entries.length) return null;
  return (
    <ProCard title="此浏览器的旧版未办记录" headerBordered>
      <Typography.Text type="secondary">已保存的旧待办可继续。新订单请使用上方订单列表。</Typography.Text>
      {entries.length > 0 && <List dataSource={entries} renderItem={(entry) =>
        <List.Item actions={[<Button key="resume" onClick={() => history.push(`${path}?draft=${entry.id}`)}>继续办理</Button>]}>
          <List.Item.Meta
            title={entry.external_order_no ? `${entry.channel || "待填渠道"} · ${entry.external_order_no}` : "待填写成交来源"}
            description={[entry.item_uid || entry.physical_uid, entry.pending ? "有操作结果待核对" : entry.sold ? "待确认交付" :
              entry.item_id ? "继续核对物品进度" : entry.physical_item_id ? "已登记实体 · 待装配" :
                entry.route === "stock" ? "选用已有库存" : "登记新实物"].filter(Boolean).join(" · ")}
          />
        </List.Item>
      } />}
    </ProCard>
  );
}

export default function OrderPreparation() {
  const key = useDraftKey();
  const id = new URLSearchParams(useLocation().search).get("draft");
  const saved = key && id ? drafts(key).find((draft) => draft.id === id) : undefined;
  return (
    <PageContainer title="准备订单物品" onBack={() => history.push("/overview")}>
      {key && (!id || saved)
        ? <Preparation key={id ?? "new"} storageKey={key} saved={saved} />
        : <Alert type="warning" title="当前登录和数据范围下找不到该待办。请回工作台核对。" />}
    </PageContainer>
  );
}

function Preparation({ storageKey, saved }: { storageKey: string; saved?: Draft }) {
  const [draft, setDraft] = useState<Draft>(() => saved || { id: crypto.randomUUID(), route: "new" });
  const [form] = Form.useForm();
  const [busy, setBusy] = useState(false);
  const active = useRef(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(false);
  const [configuration, setConfiguration] = useState(false);
  const [code, setCode] = useState<Row>();
  const itemState = useRecord("items", draft.item_id);
  const physicalState = useRecord("physical-items", draft.physical_item_id);
  const item = itemState.record;
  const physical = physicalState.record;
  const initialValues = { ...draft.values, channel: draft.channel, external_order_no: draft.external_order_no };
  const styleId = Form.useWatch("style_id", form);
  const selectedIssue = Form.useWatch("issue_id", form);
  const issueState = useRecord("issues", selectedIssue);
  const issue = issueState.record;
  const chosenStock = useRecord("items", Form.useWatch("stock_id", form)).record;
  const chosenChip = useRecord("chips", Form.useWatch("chip_id", form)).record;
  const style = useRecord("styles", styleId).record;
  const step = draft.completed ? 5 : draft.item_id ? !item ? -1 :
    item.owner_id || item.claim_code_status ? 5 : !item.provisioned_at || item.status !== "active" ? 2 :
      item.sold ? 4 : 3 : draft.physical_item_id ? 1 : 0;
  useLayoutEffect(() => {
    form.resetFields();
    form.setFieldsValue(initialValues);
  }, [form, step]);
  const conflict = item && (
    (item.test_batch_id ?? undefined) !== testBatch() ||
    item.lost_at || item.loss_evidence || item.chip_status !== "bound" ||
    !item.physical_item_id || ["archived", "disabled"].includes(item.status) ||
    (!draft.sold && (item.sold || item.owner_id || item.claim_code_status)) ||
    (!item.sold && draft.sold && !draft.completed) ||
    (draft.route === "stock" && step < 3)
  );

  function write(next: Draft) {
    localStorage.setItem(storageKey, JSON.stringify([
      next, ...drafts(storageKey).filter((entry) => entry.id !== next.id),
    ]));
    setDraft(next);
  }

  function source(values: Record<string, any>) {
    return {
      channel: values.channel?.trim() || draft.channel,
      external_order_no: values.external_order_no?.trim() || draft.external_order_no,
    };
  }

  function finish(next: Draft, result: Row) {
    const update: Draft = { ...next, pending: undefined, values: undefined };
    switch (next.pending?.action) {
      case "createPhysicalItem":
        update.physical_item_id = result.id;
        update.physical_uid = result.physical_uid;
        update.values = { issue_id: next.values?.issue_id };
        break;
      case "assembleOrderItem":
        update.item_id = result.id;
        update.item_uid = next.pending.payload.item_uid;
        break;
      case "orderSale": update.sold = true; break;
      case "issueClaimCode":
        update.completed = true;
        setCode(result);
        break;
    }
    write(update);
    itemState.reload();
  }

  async function send(next: Draft, lookup = false) {
    if (active.current || !next.pending) return;
    active.current = true;
    setBusy(true);
    setError("");
    setRetry(false);
    try {
      write(next);
      const { action, requestId, payload } = next.pending;
      let result: Row;
      try {
        result = lookup ? await command("receipt", { request_id: requestId }, crypto.randomUUID()) :
          await command(action, payload, requestId);
      } catch (e) {
        if (lookup && e instanceof ApiError && e.status === 404) setRetry(true);
        if (!lookup && !unknown(e)) write({ ...next, pending: undefined });
        throw e;
      }
      finish(next, result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作未完成，请核对原请求。");
    } finally {
      active.current = false;
      setBusy(false);
    }
  }

  function submit(values: Record<string, any>) {
    if (active.current || conflict) return;
    const next = { ...draft, ...source(values), values: { ...values } };
    delete next.values.installed;
    delete next.values.confirmed;
    let action: string;
    let payload: Record<string, any>;
    if (step === 0 && draft.route === "stock") {
      if (!chosenStock || chosenStock.id !== values.stock_id) return;
      try {
        write({ ...next, item_id: chosenStock.id, item_uid: chosenStock.item_uid, values: undefined });
      } catch {
        setError("浏览器无法保存待办，请检查存储权限。");
      }
      return;
    }
    if (step === 0) {
      action = "createPhysicalItem";
      const { style_id, physical_uid, spec } = values;
      payload = { style_id, physical_uid, spec };
    } else if (step === 1) {
      if (!issue || !physical || !chosenChip) return;
      action = "assembleOrderItem";
      payload = {
        issue_id: issue.id, item_uid: values.item_uid,
        edition_number: values.edition_number, chip_id: chosenChip.id,
        physical_item_id: physical.id, installed: values.installed,
      };
    } else if (step === 3) {
      action = "orderSale";
      payload = { item_id: draft.item_id, ...source(values), first_sold_at: values.first_sold_at };
    } else if (step === 4) {
      action = "issueClaimCode";
      payload = {
        item_id: draft.item_id, channel: draft.channel, external_order_no: draft.external_order_no,
        delivery_reference: values.delivery_reference, confirmed: values.confirmed,
      };
    } else return;
    void send({ ...next, pending: { action, payload, requestId: crypto.randomUUID() } });
  }

  function saveLater() {
    if (active.current) return;
    const { installed, confirmed, ...values } = form.getFieldsValue();
    try {
      write(draft.pending ? draft : { ...draft, ...source(values), values });
      history.push("/overview");
    } catch {
      setError("浏览器无法保存待办，请检查存储权限。");
    }
  }

  function addOrderItem() {
    try {
      const next: Draft = { id: crypto.randomUUID(), route: "new", ...source({}) };
      write(next);
      history.push(`${path}?draft=${next.id}`);
    } catch {
      setError("浏览器无法保存待办，请检查存储权限。");
    }
  }

  const serialPending = issue?.mode === "period" && !issue?.sealed_at;
  const title = ["准备实物", "确认安装", "核验与启用", "确认首次售出", "核对实际交付", "交付结果"][step];
  const locked = busy || !!draft.pending || !!conflict;
  return (
    <div className="page-stack">
      <Steps current={step === 5 ? 4 : Math.min(3, Math.max(0, step))} size="small"
        items={["准备实物", "确认安装", "核验与启用", "售出与交付"].map((text) => ({ title: text }))} />
      {error && <Alert type="error" showIcon title={error} />}
      {draft.pending && <Alert type="warning" showIcon title="先核对上一次操作的结果"
        description="核对回执后恢复进度。已发放时，可在物品档案查看有效认领码。"
        action={<Space wrap>
          <Button loading={busy} onClick={() => void send(draft, true)}>核对回执</Button>
          {retry && <Button loading={busy} onClick={() => void send(draft)}>重试原请求</Button>}
        </Space>} />}
      {conflict && <Alert type="warning" showIcon title="物品状态已变化，请打开档案核对"
        description="如库存已经售出、停用、挂失或跨数据范围，需回工作台重新准备。" />}
      <Load error={itemState.error || physicalState.error} loading={itemState.loading || physicalState.loading}
        retry={() => { itemState.reload(); physicalState.reload(); }}>
        <ProCard title={title || "读取办理进度"} headerBordered>
          {item && <Descriptions size="small" column={{ xs: 1, md: 2 }} bordered>
            <Descriptions.Item label="数字物品"><Copy value={item.item_uid} onClick={() => history.push(`/items/${item.id}`)} /></Descriptions.Item>
            <Descriptions.Item label="发行">{item.issue_name} · {edition(item)}</Descriptions.Item>
            <Descriptions.Item label="实体编号与实际规格">{item.physical_uid} · {item.spec || "规格不适用"}</Descriptions.Item>
            <Descriptions.Item label="配套芯片 UID"><Copy value={item.chip_uid} /></Descriptions.Item>
            {item.sold && <Descriptions.Item label="首次售出（北京时间）">{time(item.first_sold_at)}</Descriptions.Item>}
          </Descriptions>}
          <Form form={form} layout="vertical" initialValues={initialValues}
            disabled={locked} onFinish={submit} style={{ marginTop: 16 }}>
            {[0, 3].includes(step) && <Space wrap align="start">
              <Form.Item name="channel" label="成交渠道" rules={step === 3 ? required : []}>
                <Input maxLength={40} placeholder="例如品牌店铺、电商平台" />
              </Form.Item>
              <Form.Item name="external_order_no" label="外部订单号" rules={step === 3 ? required : []}>
                <Input maxLength={64} placeholder="填写原订单的编号" />
              </Form.Item>
            </Space>}
            {step >= 1 && ![3].includes(step) && <Typography.Paragraph type="secondary">
              成交来源：{[draft.channel, draft.external_order_no].filter(Boolean).join(" · ") || "确认售出时填写"}
            </Typography.Paragraph>}
            {step === 0 && <>
              <Form.Item label="实物来源">
                <Radio.Group value={draft.route} onChange={(e) => { setError(""); setDraft({ ...draft, route: e.target.value }); }}
                  options={[{ value: "new", label: "新登记实物" }, { value: "stock", label: "选用已有库存" }]} />
              </Form.Item>
              {draft.route === "new" ? <>
                <Form.Item name="style_id" label="关联款式" rules={required}
                  getValueFromEvent={(value) => { form.setFieldValue("issue_id", undefined); return value; }}>
                  <RemoteSelect resource="styles" />
                </Form.Item>
                <Form.Item name="physical_uid" label="实体编号" rules={required}><Input maxLength={64} /></Form.Item>
                <Form.Item name="spec" label="实际规格" rules={style?.specs?.length ? required : []}
                  extra={style?.specs?.length ? `款式规格：${style.specs.join("、")}` : "填写实物上的尺码、颜色等信息。"}>
                  <Input maxLength={256} />
                </Form.Item>
                {!!styleId && <Form.Item name="issue_id" label="发行约定" extra="缺少已确认发行时可先保存实物，稍后继续。">
                  <RemoteSelect key={styleId} resource="issues" params={{ style_id: styleId, status: "confirmed" }} />
                </Form.Item>}
              </> : <>
                <Form.Item name="stock_id" label="已核验、已启用的未售库存" rules={required}>
                  <RemoteSelect resource="items" params={{ order_stock: true }}
                    optionLabel={(record) => `${record.item_uid} · ${record.name || record.physical_uid} · ${record.spec || "规格不适用"}`} />
                </Form.Item>
                {chosenStock && <Descriptions size="small" column={1} bordered>
                  <Descriptions.Item label="款式与发行">{chosenStock.name} · {chosenStock.issue_name}</Descriptions.Item>
                  <Descriptions.Item label="实体与规格">{chosenStock.physical_uid} · {chosenStock.spec || "规格不适用"}</Descriptions.Item>
                </Descriptions>}
              </>}
            </>}
            {step === 1 && physical && <>
              <Typography.Paragraph strong>{physical.physical_uid} · {physical.style_name} · {physical.spec || "规格不适用"}</Typography.Paragraph>
              <Form.Item name="issue_id" label="同款已确认发行" rules={required} getValueFromEvent={(value) => {
                form.setFieldsValue({ item_uid: undefined, edition_number: undefined, chip_id: undefined, installed: false });
                return value;
              }}>
                <RemoteSelect resource="issues" params={{ style_id: physical.style_id, status: "confirmed" }} />
              </Form.Item>
              <Load error={issueState.error} loading={issueState.loading} retry={issueState.reload}>
                {issue && <>
                  <Button onClick={() => form.setFieldsValue({
                    item_uid: issue.suggested_item_uid,
                    edition_number: serialPending ? undefined : issue.suggested_edition_number,
                  })}>采用建议编号</Button>
                  <Form.Item name="item_uid" label="数字物品编号" rules={required}><Input maxLength={32} /></Form.Item>
                  {serialPending ? <Typography.Paragraph>正式序号待封版核定。</Typography.Paragraph> :
                    <Form.Item name="edition_number" label="发行内正式序号" rules={required}>
                      <InputNumber min={1} precision={0} max={issue.total || undefined} />
                    </Form.Item>}
                  <Form.Item name="chip_id" label="配套芯片 UID" rules={required} getValueFromEvent={(value) => {
                    form.setFieldValue("installed", false); return value;
                  }}>
                    <RemoteSelect key={issue.id} resource="chips" params={{ available: true, compatible_project: issue.project }} />
                  </Form.Item>
                  {chosenChip && <Alert type="info" title={`请核对 ${physical.physical_uid} · ${physical.spec || "规格不适用"} · ${chosenChip.chip_uid}`} />}
                  <Form.Item name="installed" valuePropName="checked" rules={confirmation}>
                    <Checkbox>已核对实物和芯片，并完成实际安装</Checkbox>
                  </Form.Item>
                </>}
              </Load>
            </>}
            {step === 2 && item && <Space wrap>
              <Typography.Text strong>{item.provisioned_at ? "核验通过 · 待启用" : "已安装 · 待核验"}</Typography.Text>
              {item.provisioned_at
                ? <Button type="primary" disabled={locked} loading={busy} onClick={() => void send({
                  ...draft, pending: { action: "toggleItem", requestId: crypto.randomUUID(), payload: { item_id: item.id, status: "active" } },
                })}>确认启用</Button>
                : <Button type="primary" disabled={locked} onClick={() => setConfiguration(true)}>打开配置核验</Button>}
            </Space>}
            {step === 3 && <Form.Item name="first_sold_at" label="首次成交时间（北京时间）"
              initialValue={inputISO(inputDate())} rules={required}
              getValueProps={(value) => ({ value: value ? inputDate(value) : undefined })}
              normalize={(value) => value ? inputISO(value) : undefined}>
              <DatePicker showTime />
            </Form.Item>}
            {step === 4 && <>
              <Alert type="info" title="实际交付后发码" description="请通过交付渠道把认领码交给接收人。码在首次成功发放时显示，有效期 30 天。" />
              <Form.Item name="delivery_reference" label="首次交付核对依据" rules={required} extra="记录核对事实，无需填写手机号或其他个人资料。">
                <Input maxLength={128} />
              </Form.Item>
              <Form.Item name="confirmed" valuePropName="checked" rules={confirmation}>
                <Checkbox>已核对实际交付与接收对象</Checkbox>
              </Form.Item>
            </>}
            {step === 5 && !conflict && <Alert type="success" showIcon title={item?.owner_id ? "已有持有人" : "已发放认领码 · 待认领"}
              description={item?.claim_code_status?.expires_at
                ? `有效期至 ${time(item.claim_code_status.expires_at)}（北京时间）。需要重新交给接收人时，在物品详情核对后补发。` : undefined} />}
            <Space wrap style={{ marginTop: 16 }}>
              {step !== 5 && <Button disabled={busy} onClick={saveLater}>保存，稍后继续</Button>}
              {step === 5 && <Button onClick={() => history.push("/overview")}>返回工作台</Button>}
              {[0, 1, 3, 4].includes(step) && <Button htmlType="submit" type="primary" loading={busy}
                disabled={locked || (step === 1 && !issue) || (step === 0 && draft.route === "stock" && !chosenStock)}>
                {step === 0 ? (draft.route === "stock" ? "选用此件，进入售出确认" : "保存实物") :
                  step === 1 ? "确认安装" : step === 3 ? "确认售出" : "确认交付并发放认领码"}
              </Button>}
              {step === 5 && !conflict && <Button type="primary" onClick={addOrderItem}>同订单再准备一件</Button>}
            </Space>
          </Form>
        </ProCard>
      </Load>
      {configuration && item?.chip_id && <KeyConfiguration id={item.chip_id}
        onClose={() => { setConfiguration(false); itemState.reload(); }}
        onUpdated={() => itemState.reload()} />}
      {code?.claim_code && <Modal open title="交付认领码" onCancel={() => setCode(undefined)}
        footer={<Button onClick={() => setCode(undefined)}>完成</Button>}>
        <Copy value={code.claim_code} />
        <Typography.Paragraph>有效期至 {time(code.expires_at)}（北京时间）。</Typography.Paragraph>
      </Modal>}
    </div>
  );
}

const confirmation = [{ validator: (_: unknown, value: boolean) =>
  value === true ? Promise.resolve() : Promise.reject(new Error("请先完成核对并勾选确认。")) }];
