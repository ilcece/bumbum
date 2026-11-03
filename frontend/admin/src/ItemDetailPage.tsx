import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Card, Col, Form, Result, Row, Space, Spin, Typography } from "antd";
import { PageContainer, ProDescriptions, ProForm, ProFormText, ProFormTextArea } from "@ant-design/pro-components";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { ApiError, changeItemStatus, readItem, readSession, safeRecordId, saveItemDetails } from "./api";
import type { FashionProfile, ItemSummary } from "./api";
import { applicableFields, changes, formValues, ITEM_STATUSES, profileIdentity, profileValue, useItemFields, validateItem } from "./itemFields";
import type { ImageFile, ItemForm } from "./itemFields";
import { ItemImages } from "./ItemImages";
import { safeReturn } from "./adminNavigation";
import { useNavigationGuard } from "./NavigationGuard";

type Submission = { kind: "details"; body: { sku_code?: string | null; profile?: FashionProfile } } | { kind: "status"; status: "active" | "disabled" };
function matches(item: ItemSummary, submission: Submission) {
  if (submission.kind === "status") return item.status === submission.status;
  return (!("sku_code" in submission.body) || item.sku_code === submission.body.sku_code)
    && (!submission.body.profile || profileIdentity(profileValue(formValues(item))) === profileIdentity(submission.body.profile));
}
export function ItemDetailPage({ edit = false, onSessionExpired }: { edit?: boolean; onSessionExpired: () => void }) {
  const { id } = useParams();
  const navigate = useNavigate(), location = useLocation();
  const [form] = Form.useForm<ItemForm>();
  const [item, setItem] = useState<ItemSummary | null>(null), [error, setError] = useState(""), [outcome, setOutcome] = useState("");
  const [dirty, setDirty] = useState(false), [busy, setBusy] = useState(false), [unknown, setUnknown] = useState(false), [revision, setRevision] = useState(0);
  const flight = useRef(false), alive = useRef(true), current = useRef<ItemSummary | null>(null), original = useRef<Submission | null>(null);
  const statusConfirmation = useRef<{ destroy: () => void } | null>(null);
  const { update, attempt } = useNavigationGuard();
  const { message, modal } = App.useApp();
  const allFields = useItemFields();
  const files: ImageFile[] = Form.useWatch("image_files", form) || [];
  const uploading = files.some(file => file.status === "uploading"), imageUnknown = files.some(file => file.uncertain);
  const blocked = busy || uploading;
  function accept(value: ItemSummary, reset = true) {
    current.current = value; setItem(value);
    if (edit && reset) form.setFieldsValue(formValues(value));
    if (reset) setDirty(false);
  }
  useEffect(() => { alive.current = true; return () => { alive.current = false; statusConfirmation.current?.destroy(); update({ dirty: false, busy: false }); }; }, [update]);
  useEffect(() => {
    let cancelled = false;
    setItem(null); current.current = null; setError(""); setDirty(false); setUnknown(false); setOutcome("");
    if (!id || !/^[1-9][0-9]*$/.test(id) || !safeRecordId(Number(id))) { setError("物品记录编号无效，未读取其他记录。"); return; }
    readItem(Number(id)).then(value => { validateItem(value, Number(id)); if (!cancelled) accept(value); }).catch(failure => {
      if (cancelled) return;
      if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
      else setError(failure instanceof ApiError ? failure.message : "物品读取失败，请重试或返回。");
    });
    return () => { cancelled = true; };
  }, [id, edit, revision, onSessionExpired, form]);
  async function failed(failure: unknown) {
    if (!alive.current) return;
    if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
    else if (failure instanceof ApiError && failure.code === "csrf_failed") {
      try { await readSession(); if (alive.current) setError("登录状态已更新，输入已保留，请再次明确提交；未自动重发。"); }
      catch (refreshFailure) { if (refreshFailure instanceof ApiError && refreshFailure.status === 401) onSessionExpired(); else if (alive.current) setError("登录状态更新失败，输入已保留。"); }
    } else if (failure instanceof ApiError && failure.status >= 400 && failure.status < 500 && failure.code !== "unexpected_response") setError(failure.message);
    else { setUnknown(true); setError("保存结果尚未确认，请先按物品ID核对；不会自动重发。"); }
  }
  async function save() {
    const baseline = current.current;
    if (!baseline || flight.current || unknown || uploading || imageUnknown || baseline.status === "archived") return false;
    let values: ItemForm;
    try { values = await form.validateFields(); } catch { return false; }
    if (flight.current) return false;
    if ((values.image_files || []).some(file => file.status !== "done" || file.uncertain)) { setError("请先处理或移除未上传成功的图片，再保存资料。"); return false; }
    const changed = changes(baseline, values);
    if (!changed.dirty) { setDirty(false); update({ dirty: false, busy: false }); void message.info("没有需要保存的修改。"); return true; }
    original.current = { kind: "details", body: changed.body };
    flight.current = true; setBusy(true); setError(""); update({ dirty: true, busy: true });
    try {
      const found = validateItem(await saveItemDetails(baseline.id, changed.body), baseline.id);
      if (!matches(found, original.current)) throw new Error("保存回执与提交不符");
      if (!alive.current) return false;
      accept(found); setUnknown(false); update({ dirty: false, busy: false });
      void message.success("修改已保存。返回列表会按原条件重新查询；若不再匹配，可调整查询。"); return true;
    } catch (failure) { await failed(failure); return false; }
    finally { flight.current = false; if (alive.current) setBusy(false); }
  }
  useEffect(() => { update({ dirty: dirty || unknown || imageUnknown, busy: blocked, save: edit && !unknown && !imageUnknown && !uploading && item?.status !== "archived" ? save : undefined }); }, [dirty, unknown, imageUnknown, blocked, item, edit]);
  async function verify() {
    const baseline = current.current, submission = original.current;
    if (!baseline || !submission || flight.current) return;
    flight.current = true; setBusy(true); update({ dirty: true, busy: true });
    try {
      const found = validateItem(await readItem(baseline.id), baseline.id);
      if (!alive.current) return;
      const same = matches(found, submission);
      accept(found, same || submission.kind === "status"); setUnknown(false);
      setDirty(!same && edit && changes(found, form.getFieldsValue(true)).dirty);
      setError(same ? "已确认服务器当前资料与本次提交一致。" : "服务器当前结果与本次提交不同，输入已保留。原请求仍可能处理中，请核对后决定是否明确重试。");
    } catch (failure) { if (failure instanceof ApiError && failure.status === 401) onSessionExpired(); else if (alive.current) setError(failure instanceof ApiError ? failure.message : "核对失败，保存结果仍未确认。"); }
    finally { flight.current = false; if (alive.current) setBusy(false); }
  }
  function back() {
    const point = safeReturn(location.state?.returnTo);
    navigate(point?.path || "/items", { state: { returnTo: point?.parent, restoreScroll: point?.scroll } });
  }
  async function setStatus(target: "active" | "disabled") {
    const baseline = current.current;
    if (!baseline || flight.current || !alive.current) return;
    original.current = { kind: "status", status: target }; flight.current = true; setBusy(true); setError(""); update({ dirty: false, busy: true });
    try {
      const result = await changeItemStatus(baseline.id, target);
      if (result.id !== baseline.id || result.status !== target) throw new Error("状态回执不符");
      if (!alive.current) return;
      accept({ ...baseline, ...result }); setUnknown(false); setOutcome(target === "active" ? "物品已启用。" : "物品已停用，资料和关联保留。");
      try { const found = validateItem(await readItem(baseline.id), baseline.id); if (alive.current) accept(found); }
      catch (refreshFailure) { if (refreshFailure instanceof ApiError && refreshFailure.status === 401) onSessionExpired(); else if (alive.current) setError("状态已成功修改，但最新详情刷新失败，请重新读取；不会重发状态操作。"); }
    } catch (failure) { await failed(failure); }
    finally { flight.current = false; if (alive.current) setBusy(false); }
  }
  function confirmStatus(target: "active" | "disabled") {
    if (statusConfirmation.current) return;
    attempt(() => {
      if (statusConfirmation.current || !alive.current) return;
      if (edit && current.current) { form.setFieldsValue(formValues(current.current)); setDirty(false); update({ dirty: false, busy: false }); }
      statusConfirmation.current = modal.confirm({ title: target === "active" ? "启用此物品？" : "停用此物品？", content: target === "active" ? "须已有有效名称；启用不代表芯片绑定、写卡或防伪验证完成。" : "停止当前用户查看，保留资料与芯片关联；已发送的内容无法追回。", okText: target === "active" ? "确认启用" : "确认停用", cancelText: "取消", onOk: () => setStatus(target), afterClose: () => { statusConfirmation.current = null; } });
    });
  }
  const fields = item ? applicableFields(allFields, item) : [];
  const locked = blocked || unknown;
  function textRule(key: string, limit: number) {
    return { validator: async (_rule: unknown, value: string) => {
      if (key !== "sku_code" && current.current && !changes(current.current, form.getFieldsValue(true)).profileChanged) return;
      if ([...(value?.trim() || "")].length > limit) throw new Error(`最多${limit}个字符。`);
      if (key === "name" && !value?.trim()) throw new Error("修改服装资料时须填写名称。");
    } };
  }
  return <PageContainer title={<Typography.Title level={2} style={{ margin: 0 }}>{edit ? "编辑物品" : "物品详情"}</Typography.Title>} subTitle={item?.item_uid} onBack={back}
    extra={<Space><Button onClick={back}>返回来源</Button>{item && !edit && item.status !== "archived" && <Button type="primary" onClick={() => navigate(`/items/${item.id}/edit`, { state: location.state })}>编辑物品</Button>}</Space>}>
    {!item ? error ? <Result status="warning" title="无法读取物品" subTitle={error} extra={<Button onClick={() => setRevision(value => value + 1)}>重试读取</Button>} /> : <Spin tip="正在读取物品"><div style={{ height: 160 }} /></Spin>
      : <Space direction="vertical" size="large" style={{ width: "100%" }}>
        {outcome && <div role="status"><Alert type="success" showIcon message={outcome} /></div>}
        {error && <Alert type="warning" showIcon message={error} action={unknown && <Button loading={busy} onClick={() => void verify()}>核对保存结果</Button>} />}
        <Card>{edit ? <ProForm<ItemForm> name="item-edit" form={form} layout="vertical" initialValues={formValues(item)}
          onValuesChange={(_, values) => setDirty(changes(current.current!, values).dirty)}
          onFinish={async () => { if (await save()) navigate(`/items/${item.id}`, { replace: true, state: location.state }); }}
          submitter={item.status === "archived" ? false : { searchConfig: { submitText: "保存修改", resetText: "恢复已保存值" }, submitButtonProps: { "aria-label": "保存修改", loading: busy, disabled: locked || imageUnknown }, resetButtonProps: { disabled: locked, onClick: () => { if (current.current) { form.setFieldsValue(formValues(current.current)); setDirty(false); } } } }}>
          <Alert type="info" showIcon message={item.status === "archived" ? "归档物品只读。" : item.project === "fashion" ? "维护款式和服装资料；稳定身份或关联不能在此改写，专用纠错待交付。状态独立确认，尺码只读；仅改款式无需填写名称。" : "饰品仅维护款式，已有资料只读，编辑模板尚未开放；稳定身份或关联错误须专用纠错（待交付）。"} style={{ marginBottom: 24 }} />
          <Row gutter={24}>{fields.map(field => <Col key={field.key} xs={24} md={["description", "care_instructions", "image_urls", "size_chart", "meaning"].includes(field.key) ? 24 : 12}>{(() => {
            const key = field.editable;
            if (item.status === "archived" || !key || item.project !== "fashion" && key !== "sku_code") return <Form.Item key={field.key} label={field.label}>{field.render(item)}</Form.Item>;
            if (key === "image_files") return <Form.Item key={field.key} name={key} label={field.label}><ItemImages itemId={item.id} disabled={busy || unknown} onSessionExpired={onSessionExpired} /></Form.Item>;
            const limit = { sku_code: 64, name: 128, description: 4000, material: 256, care_instructions: 2000 }[key];
            const props = { key: field.key, name: key, label: field.label, disabled: locked, rules: [textRule(key, limit)] };
            return ["description", "care_instructions"].includes(key) ? <ProFormTextArea {...props} /> : <ProFormText {...props} />;
          })()}</Col>)}</Row>
        </ProForm> : <ProDescriptions title={item.item_uid} column={2} dataSource={item} columns={fields.map(field => ({ title: field.label, key: field.key, render: () => field.render(item) }))} />}</Card>
        {!item.profile && <Alert type="info" showIcon message="此物品尚未填写资料；可单独维护款式编号。" />}
        {item.project === "fashion" && item.status !== "archived" && <Card title="状态操作"><Space>
          <Button disabled={locked} onClick={() => confirmStatus(item.status === "active" ? "disabled" : "active")}>{item.status === "active" ? "停用物品" : "启用物品"}</Button>
          <Button disabled={locked} onClick={() => attempt(() => setRevision(value => value + 1))}>重新读取资料</Button>
        </Space></Card>}
      </Space>}
  </PageContainer>;
}
