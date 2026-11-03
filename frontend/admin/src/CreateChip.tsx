import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Form } from "antd";
import { ModalForm, ProFormSelect, ProFormText } from "@ant-design/pro-components";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError, listChips, readSession, registerChip, safeRecordId } from "./api";
import type { ChipView } from "./api";
import { sourcePoint } from "./adminNavigation";
import { useNavigationGuard } from "./NavigationGuard";

const PROJECTS = { fashion: "服装", jewelry: "饰品", unassigned: "未分配" };
export function CreateChip({ onClose, onSessionExpired }: { onClose: () => void; onSessionExpired: () => void }) {
  const [form] = Form.useForm();
  const [dirty, setDirty] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState(""), [unknown, setUnknown] = useState(false);
  const [created, setCreated] = useState<{ chip: ChipView; is_new: boolean } | null>(null);
  const { update, attempt } = useNavigationGuard();
  const { message } = App.useApp();
  const navigate = useNavigate(), location = useLocation();
  const inFlight = useRef(false), mounted = useRef(true);
  const original = useRef<{ uid: string; project: string | null; batch: string | null } | null>(null);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function submit() {
    if (inFlight.current || unknown) return false;
    let values;
    try { values = await form.validateFields(); } catch { return false; }
    if (inFlight.current) return false;
    const input = { uid: values.chip_uid.trim(), project: values.project === "unassigned" ? null : values.project, batch: values.batch_no?.trim() || null };
    original.current = input; inFlight.current = true; setBusy(true); setError(""); setCreated(null);
    update({ dirty: true, busy: true });
    try {
      const result = await registerChip(input.uid, input.project, input.batch);
      if (!safeRecordId(result.chip.id) || result.chip.chip_uid.replace(/:/g, "") !== input.uid.replace(/:/g, "").toUpperCase()) throw new Error("登记回执异常");
      if (!mounted.current) return false;
      setCreated(result); setDirty(false); update({ dirty: false, busy: false });
      form.setFieldsValue({ chip_uid: "", batch_no: "" });
      return true;
    } catch (failure) {
      if (!mounted.current) return false;
      if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
      else if (failure instanceof ApiError && failure.code === "csrf_failed") {
        try { await readSession(); setError("登录状态已更新，请核对输入后再次提交；未自动重发。"); }
        catch (refreshFailure) { if (refreshFailure instanceof ApiError && refreshFailure.status === 401) onSessionExpired(); else setError("登录状态读取失败，输入已保留，请重试。"); }
      } else if (failure instanceof ApiError && failure.status < 500 && failure.code !== "unexpected_response") setError(failure.message);
      else { setUnknown(true); setError("登记结果尚未确认，请先按本次完整UID查询；不会自动重发。"); }
      return false;
    } finally { inFlight.current = false; if (mounted.current) setBusy(false); }
  }
  useEffect(() => { update({ dirty, busy, save: unknown ? undefined : submit }); }, [dirty, busy, unknown]);
  useEffect(() => () => update({ dirty: false, busy: false }), [update]);
  async function verify() {
    const input = original.current;
    if (!input || inFlight.current) return;
    inFlight.current = true; setBusy(true);
    try {
      const compact = input.uid.replace(/:/g, "").toUpperCase();
      const result = await listChips({ page: 1, keyword: compact });
      if (!mounted.current) return;
      const found = result.items.find(row => row.chip_uid.replace(/:/g, "") === compact);
      if (found) {
        setCreated({ chip: found, is_new: false }); setUnknown(false); setDirty(false); form.setFieldsValue({ chip_uid: "", batch_no: "" });
        setError(""); void message.info("已找到确切UID，请查看原记录；未覆盖其资料。");
      } else { setUnknown(false); setError("尚未查到该UID，原请求可能仍在处理。可核对原输入后手动提交；重复登记不会覆盖原记录。"); }
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
      else if (mounted.current) setError(failure instanceof ApiError ? failure.message : "查询失败，登记结果仍未确认。");
    } finally { inFlight.current = false; if (mounted.current) setBusy(false); }
  }
  return <ModalForm name="chip-register" title="登记芯片" open form={form} initialValues={{ project: "unassigned" }}
    onOpenChange={open => { if (!open) attempt(onClose); }} onFinish={async () => { await submit(); return false; }}
    onValuesChange={() => setDirty(true)} modalProps={{ maskClosable: false, destroyOnClose: true, closable: !busy }}
    submitter={{ searchConfig: { submitText: "登记并继续" }, submitButtonProps: { "aria-label": "登记并继续", loading: busy, disabled: busy || unknown }, resetButtonProps: { disabled: busy } }}>
    <ProFormText name="chip_uid" label="芯片UID" fieldProps={{ maxLength: 32, disabled: busy || unknown, autoComplete: "off" }}
      rules={[{ required: true, message: "请填写真实芯片UID。" }, { pattern: /^\s*(?:[0-9A-Fa-f]{14}|(?:[0-9A-Fa-f]{2}:){6}[0-9A-Fa-f]{2})\s*$/, message: "请输入14位十六进制或7组冒号格式。" }]} />
    <ProFormSelect name="project" label="项目" valueEnum={PROJECTS} allowClear={false} disabled={busy || unknown} />
    <ProFormText name="batch_no" label="批次" fieldProps={{ maxLength: 64, disabled: busy || unknown }} />
    {error && <Alert type="warning" showIcon message={error} />}
    {unknown && <Button loading={busy} onClick={() => void verify()}>按本次UID核对结果</Button>}
    {created && <Alert type="success" showIcon message={created.is_new ? "登记成功，可以继续登记下一枚芯片。" : "该UID已有记录，请查看原资料。"}
      action={<Button onClick={() => attempt(() => navigate(`/chips/${created.chip.id}`, { state: { returnTo: sourcePoint(location) } }))}>查看该芯片</Button>} />}
  </ModalForm>;
}
