import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Alert, App, Button, Card, Form, Result, Space, Spin, Tag, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { PageContainer, ProDescriptions, ProForm, ProFormText, ProTable } from "@ant-design/pro-components";
import type { ActionType, ProColumns } from "@ant-design/pro-components";
import { Link, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError, CHIP_FILTERS, listChips, readChip, readSession, safeRecordId, saveChipBatch } from "./api";
import type { ChipDetail, ChipQuery, ChipView } from "./api";
import { safeReturn, sourcePoint } from "./adminNavigation";
import { useNavigationGuard } from "./NavigationGuard";
import { BindItemDialog } from "./BindItemDialog";
import { ChipKeysDialog } from "./ChipKeysDialog";
import { beijingTime } from "./itemFields";
import { CreateChip } from "./CreateChip";

export const PROJECTS = { fashion: "服装", jewelry: "饰品", unassigned: "未分配" };
const STATUSES = { pending: "待绑定", bound: "已绑定", disabled: "停用", lost: "丢失" };
const SOURCES = { manual: "网页手工", nfc_cool: "手机扫描", unknown: "历史未知" };
const MATCHES: Record<string, string> = { chip_uid: "芯片UID", item_uid: "关联物品编号", item_name: "关联物品名称" };
export const failureText = (error: unknown, fallback: string) => error instanceof ApiError ? error.message : fallback;

type Field = { key: keyof ChipDetail; label: string; render: (chip: ChipDetail) => ReactNode };
function useChipFields(): Field[] {
  const location = useLocation();
  return [
    { key: "chip_uid", label: "芯片UID", render: chip => <Typography.Text copyable>{chip.chip_uid}</Typography.Text> },
    { key: "project", label: "项目", render: chip => PROJECTS[chip.project || "unassigned"] },
    { key: "chip_status", label: "状态", render: chip => <Tag>{STATUSES[chip.chip_status]}</Tag> },
    { key: "batch_no", label: "批次", render: chip => chip.batch_no || "未填写" },
    { key: "registration_source", label: "首次登记来源", render: chip => SOURCES[chip.registration_source] },
    { key: "item_uid", label: "关联物品", render: chip => chip.item_id === null ? "未关联" : safeRecordId(chip.item_id)
      ? <Link to={`/items/${chip.item_id}`} state={{ returnTo: sourcePoint(location) }}>{chip.item_uid || "查看关联物品"}</Link> : "关联编号无法处理，请反馈" },
    { key: "item_name", label: "关联物品名称", render: chip => chip.item_name || (chip.item_id === null ? "未关联" : "未填写") },
    { key: "keys_generated", label: "密钥生成", render: chip => chip.keys_generated ? "已生成" : "未生成" },
    { key: "provisioned_at", label: "配置核验时间（北京时间）", render: chip => chip.provisioned_at ? beijingTime(chip.provisioned_at) : "未核验" },
    { key: "created_at", label: "登记时间（北京时间）", render: chip => beijingTime(chip.created_at) },
    { key: "updated_at", label: "更新时间（北京时间）", render: chip => beijingTime(chip.updated_at) },
  ];
}

function queryFrom(search: URLSearchParams): ChipQuery {
  const integer = (name: string, fallback: number) => /^[1-9][0-9]*$/.test(search.get(name) || "") ? Number(search.get(name)) : fallback;
  const query: ChipQuery = { page: integer("page", 1), page_size: integer("page_size", 20) };
  for (const key of CHIP_FILTERS) if (search.has(key)) query[key] = search.get(key)!;
  return query;
}
function queryString(query: ChipQuery) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value !== "" && value !== undefined && value !== null) search.set(key, String(value));
  return search;
}
function submittedQuery(values: Record<string, unknown>, pageSize: number): ChipQuery {
  const query: ChipQuery = { page: 1, page_size: pageSize };
  for (const key of CHIP_FILTERS) if (!/_(from|to)$/.test(key) && typeof values[key] === "string" && values[key]) query[key] = values[key] as string;
  for (const name of ["created", "updated", "provisioned"] as const) {
    const range = values[`${name}_range`];
    if (Array.isArray(range) && range.length === 2) {
      if (range[0]) query[`${name}_from`] = String(range[0]);
      if (range[1]) query[`${name}_to`] = String(range[1]);
    }
  }
  return query;
}
function validateChip(value: ChipDetail, id: number) {
  if (value.id !== id || typeof value.chip_uid !== "string" || typeof value.keys_generated !== "boolean" || !(value.chip_status in STATUSES)
    || !(value.registration_source in SOURCES) || !(value.project === null || value.project === "fashion" || value.project === "jewelry")
    || !(value.batch_no === null || typeof value.batch_no === "string")) throw new Error("芯片返回资料不符合约定。");
  return value;
}

function ChipListPage({ onSessionExpired }: { onSessionExpired: () => void }) {
  const location = useLocation(), navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const query = useMemo(() => queryFrom(new URLSearchParams(search)), [search]);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const fields = useChipFields();
  const sequence = useRef(0);
  const action = useRef<ActionType | undefined>(undefined);
  const initial = useMemo(() => ({ ...Object.fromEntries(CHIP_FILTERS.filter(key => !/_(from|to)$/.test(key)).map(key => [key, query[key]])),
    ...Object.fromEntries(["created", "updated", "provisioned"].map(name => [`${name}_range`, query[`${name}_from` as keyof ChipQuery] || query[`${name}_to` as keyof ChipQuery]
      ? [query[`${name}_from` as keyof ChipQuery], query[`${name}_to` as keyof ChipQuery]] : undefined])),
  }), [query]);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (loaded && typeof location.state?.restoreScroll === "number") window.scrollTo({ top: location.state.restoreScroll });
  }, [loaded, location.key]);
  const common: ProColumns<ChipDetail>[] = fields.map(field => ({ title: field.label, dataIndex: field.key, key: `view_${field.key}`, hideInSearch: true,
    render: (_, row) => field.render(row), width: field.key === "chip_uid" ? 220 : 180 }));
  const columns: ProColumns<ChipDetail>[] = [
    { title: "关键词", dataIndex: "keyword", hideInTable: true, fieldProps: { maxLength: 128, placeholder: "UID、关联物品编号或名称" } },
    { title: "项目", dataIndex: "project", valueEnum: PROJECTS, hideInTable: true },
    { title: "状态", dataIndex: "status", valueEnum: STATUSES, hideInTable: true },
    { title: "批次", dataIndex: "batch_no", hideInTable: true, fieldProps: { maxLength: 64 } },
    { title: "首次登记来源", dataIndex: "registration_source", valueEnum: SOURCES, hideInTable: true },
    { title: "关联物品", dataIndex: "has_item", valueEnum: { true: "已关联", false: "未关联" }, hideInTable: true },
    { title: "密钥生成", dataIndex: "keys_generated", valueEnum: { true: "已生成", false: "未生成" }, hideInTable: true },
    { title: "配置核验", dataIndex: "provisioned", valueEnum: { true: "已核验", false: "未核验" }, hideInTable: true },
    ...["created", "updated", "provisioned"].map((key, index): ProColumns<ChipDetail> => ({ title: ["登记日期（北京时间）", "更新日期（北京时间）", "核验日期（北京时间）"][index], dataIndex: `${key}_range`, valueType: "dateRange", colSize: 2, fieldProps: { allowEmpty: [true, true] }, hideInTable: true })),
    ...common,
    { title: "关键词匹配", dataIndex: "keyword_matches", hideInSearch: true, width: 180, render: (_, row) => row.keyword_matches.map(key => MATCHES[key] || key).join("、") || "—" },
    { title: "操作", valueType: "option", key: "actions", width: 100, fixed: "right", render: (_, row) => <Button type="link" disabled={!safeRecordId(row.id)}
      onClick={() => navigate(`/chips/${row.id}`, { state: { returnTo: sourcePoint(location) } })}>查看详情</Button> },
  ];
  return <PageContainer title={<Typography.Title level={2} style={{ margin: 0 }}>芯片管理</Typography.Title>} subTitle="查询芯片身份、关联与配置摘要；列表不显示密钥。">
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {error && <Alert type="error" showIcon message={error} />}
      <ProTable<ChipDetail> key={location.search} rowKey="id" columns={columns} params={query} actionRef={action}
        form={{ name: "chip-query", initialValues: initial }} search={{ defaultCollapsed: true, labelWidth: "auto", span: 6 }}
        headerTitle="芯片列表" dateFormatter="string" scroll={{ x: 2200 }} options={{ density: true, fullScreen: false, reload: true, setting: true }}
        toolBarRender={() => [<Button key="create" type="primary" icon={<PlusOutlined aria-hidden />} onClick={() => setCreateOpen(true)}>登记芯片</Button>]}
        onSubmit={values => { setLoaded(false); setSearch(queryString(submittedQuery(values, query.page_size || 20))); }}
        onReset={() => { setLoaded(false); setSearch(new URLSearchParams()); }}
        pagination={{ current: query.page, pageSize: query.page_size, showSizeChanger: true, pageSizeOptions: [20, 50, 100],
          }}
        onChange={(paging, _filters, _sorter, extra) => { if (extra.action === "paginate") { setLoaded(false); setSearch(queryString({ ...query, page: paging.current || 1, page_size: paging.pageSize || 20 })); } }}
        locale={{ emptyText: error ? "读取失败，请重试查询。" : search.toString() ? "没有符合条件的芯片，可重置查询。" : "尚无芯片，可登记真实UID。" }}
        request={async () => {
          const ticket = ++sequence.current;
          setError(""); setLoaded(false);
          try {
            const result = await listChips(query);
            if (!Array.isArray(result.items) || !Number.isSafeInteger(result.total) || result.total < 0) throw new Error("列表返回异常");
            result.items.forEach(row => validateChip(row, row.id));
            if (ticket === sequence.current) {
              if (result.page_adjusted) setSearch(queryString({ ...query, page: result.page }), { replace: true });
              setLoaded(true);
            }
            return { data: result.items, total: result.total, success: true };
          } catch (failure) {
            if (ticket === sequence.current) {
              if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
              else setError(failureText(failure, "芯片列表读取失败，请重试查询。"));
            }
            return { data: [], total: 0, success: false };
          }
        }} />
    </Space>
    {createOpen && <CreateChip onClose={() => { setCreateOpen(false); void action.current?.reload(); }} onSessionExpired={onSessionExpired} />}
  </PageContainer>;
}

function ChipRecord({ edit, onSessionExpired }: { edit?: boolean; onSessionExpired: () => void }) {
  const { id } = useParams();
  const navigate = useNavigate(), location = useLocation();
  const [chip, setChip] = useState<ChipDetail | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [outcome, setOutcome] = useState("");
  const [dirty, setDirty] = useState(false), [busy, setBusy] = useState(false), [unknown, setUnknown] = useState(false);
  const [special, setSpecial] = useState<"bind" | "keys" | null>(null);
  const [interaction, setInteraction] = useState({ dirty: false, busy: false });
  const [form] = Form.useForm();
  const { update } = useNavigationGuard();
  const { message } = App.useApp();
  const fields = useChipFields();
  const inFlight = useRef(false), mounted = useRef(true);
  const originalBatch = useRef<string | null>(null), baseline = useRef<string | null>(null);
  const updateInteraction = useCallback((value: { dirty: boolean; busy: boolean }) => setInteraction(value), []);
  const updateFromKeys = useCallback((value: ChipView) => setChip(current => current ? { ...current, ...value } : current), []);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    let cancelled = false;
    setChip(null); setError(""); setDirty(false); setBusy(false); setUnknown(false); setSpecial(null);
    if (!id || !/^[1-9][0-9]*$/.test(id) || !safeRecordId(Number(id))) { setError("芯片记录编号无效，未读取其他记录。"); return; }
    readChip(Number(id)).then(value => {
      validateChip(value, Number(id));
      if (!cancelled) { setChip(value); baseline.current = value.batch_no; if (edit) form.setFieldsValue({ batch_no: value.batch_no || "" }); }
    }).catch(failure => {
      if (cancelled) return;
      if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
      else setError(failureText(failure, "芯片读取失败，请重试或返回。"));
    });
    return () => { cancelled = true; };
  }, [id, edit, revision, form, onSessionExpired]);
  useEffect(() => () => update({ dirty: false, busy: false }), [update]);
  async function save() {
    if (!chip || inFlight.current || unknown) return false;
    let values;
    try { values = await form.validateFields(); } catch { return false; }
    if (inFlight.current) return false;
    const batch = values.batch_no?.trim() || null;
    originalBatch.current = batch; inFlight.current = true; setBusy(true); setError(""); update({ dirty: true, busy: true });
    try {
      const result = validateChip(await saveChipBatch(chip.id, batch), chip.id);
      if (result.batch_no !== batch) throw new Error("保存回执与提交值不符");
      if (!mounted.current) return false;
      setChip(result); baseline.current = result.batch_no; setDirty(false); setUnknown(false); update({ dirty: false, busy: false });
      void message.success("批次已保存。返回列表会按原条件重新查询；若不再匹配，可调整查询。");
      return true;
    } catch (failure) {
      if (!mounted.current) return false;
      if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
      else if (failure instanceof ApiError && failure.code === "csrf_failed") {
        try { await readSession(); setError("登录状态已更新，输入已保留，请再次明确提交；未自动重发。"); }
        catch (refreshFailure) { if (refreshFailure instanceof ApiError && refreshFailure.status === 401) onSessionExpired(); else setError("登录状态更新失败，输入已保留，请重试。"); }
      } else if (failure instanceof ApiError && failure.status < 500 && failure.code !== "unexpected_response") setError(failure.message);
      else { setUnknown(true); setError("保存结果尚未确认，请先按记录ID核对；不会自动重发。"); }
      return false;
    } finally { inFlight.current = false; if (mounted.current) setBusy(false); }
  }
  useEffect(() => { update({ dirty: dirty || unknown || interaction.dirty, busy: busy || interaction.busy, save: edit && !unknown ? save : undefined }); }, [dirty, busy, unknown, interaction, chip, edit]);
  async function verify() {
    if (!chip || inFlight.current) return;
    inFlight.current = true; setBusy(true);
    try {
      const found = validateChip(await readChip(chip.id), chip.id);
      if (!mounted.current) return;
      setChip(found); baseline.current = found.batch_no; setUnknown(false);
      const matches = found.batch_no === originalBatch.current;
      setDirty(!matches); setError(matches ? "已确认服务器当前批次与本次提交一致。" : "服务器当前批次与本次提交不同，输入已保留。原请求仍可能处理中，请核对后决定是否手动保存。");
      if (matches) form.setFieldsValue({ batch_no: found.batch_no || "" });
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
      else setError(failureText(failure, "读取失败，保存结果仍未确认。"));
    } finally { inFlight.current = false; if (mounted.current) setBusy(false); }
  }
  function back() {
    const point = safeReturn(location.state?.returnTo);
    navigate(point?.path || "/chips", { state: { returnTo: point?.parent, restoreScroll: point?.scroll } });
  }
  function refreshAfterAction(_chip: ChipView, recovered: boolean) {
    setOutcome(recovered ? "已查询确认绑定结果。" : "绑定成功。");
    setSpecial(null); setInteraction({ dirty: false, busy: false }); setRevision(value => value + 1);
  }
  const title = edit ? "编辑芯片" : "芯片详情";
  return <PageContainer title={<Typography.Title level={2} style={{ margin: 0 }}>{title}</Typography.Title>} subTitle={chip?.chip_uid} onBack={back}
    extra={<Space><Button onClick={back}>返回来源</Button>{chip && !edit && <Button type="primary" onClick={() => navigate(`/chips/${chip.id}/edit`, { state: location.state })}>编辑批次</Button>}</Space>}>
    {outcome && <div role="status" style={{ marginBottom: 16 }}><Alert type="success" showIcon message={outcome} /></div>}
    {!chip ? error ? <Result status="warning" title="无法读取芯片" subTitle={error} extra={<Button onClick={() => setRevision(value => value + 1)}>重试读取</Button>} />
      : <Spin tip="正在读取芯片"><div style={{ height: 160 }} /></Spin>
      : <Space direction="vertical" size="large" style={{ width: "100%" }}>
        {error && <Alert type="warning" showIcon message={error} action={unknown && <Button loading={busy} onClick={() => void verify()}>核对保存结果</Button>} />}
        <Card>{edit ? <ProForm name="chip-edit" form={form} layout="vertical" initialValues={{ batch_no: chip.batch_no || "" }}
          onFinish={async () => { if (await save()) navigate(`/chips/${chip.id}`, { replace: true, state: location.state }); }}
          onValuesChange={values => setDirty((values.batch_no?.trim() || null) !== baseline.current)}
          submitter={{ searchConfig: { submitText: "保存批次", resetText: "恢复已保存值" }, submitButtonProps: { "aria-label": "保存批次", loading: busy, disabled: busy || unknown },
            resetButtonProps: { disabled: busy || unknown, onClick: () => { form.setFieldsValue({ batch_no: baseline.current || "" }); setDirty(false); } } }}>
          <Alert type="info" showIcon message="本次仅维护批次。UID是真实芯片身份；项目和关联按首次绑定规则确定。身份或绑定错误走专用纠错；密钥和配置须使用受控操作。" style={{ marginBottom: 24 }} />
          {fields.map(field => field.key === "batch_no" ? <ProFormText key={field.key} name="batch_no" label={field.label} fieldProps={{ maxLength: 64, disabled: busy || unknown }} rules={[{ max: 64, message: "批次最多64个字符。" }]} extra="可以补录、修改或清空，首尾空白会去除。" />
            : <Form.Item key={field.key} label={field.label}>{field.render(chip)}</Form.Item>)}
        </ProForm> : <ProDescriptions column={2} dataSource={chip} columns={fields.map(field => ({ title: field.label, key: field.key, render: () => field.render(chip) }))} />}</Card>
        {!edit && <Card title="受控操作"><Space>
          <Button disabled={chip.chip_status !== "pending" || chip.item_id !== null || !safeRecordId(chip.id)} onClick={() => setSpecial("bind")}>绑定物品</Button>
          <Button disabled={chip.chip_status !== "bound" || chip.item_id === null || !safeRecordId(chip.id)} onClick={() => setSpecial("keys")}>密钥与配置</Button>
        </Space></Card>}
      </Space>}
    {chip && special === "bind" && <BindItemDialog chip={chip} onClose={() => setSpecial(null)} onBound={refreshAfterAction} onSessionExpired={onSessionExpired} onInteraction={updateInteraction} />}
    {chip && special === "keys" && <ChipKeysDialog chip={chip} onClose={() => { setSpecial(null); setRevision(value => value + 1); }} onUpdated={updateFromKeys} onSessionExpired={onSessionExpired} onInteraction={updateInteraction} />}
  </PageContainer>;
}

export function ChipPanel({ onSessionExpired }: { onSessionExpired: () => void }) {
  return <Routes>
    <Route index element={<ChipListPage onSessionExpired={onSessionExpired} />} />
    <Route path=":id" element={<ChipRecord onSessionExpired={onSessionExpired} />} />
    <Route path=":id/edit" element={<ChipRecord edit onSessionExpired={onSessionExpired} />} />
    <Route path="*" element={<Result status="404" title="芯片页面不存在" extra={<Link to="/chips">返回芯片列表</Link>} />} />
  </Routes>;
}
