import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Button, Result, Space, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { PageContainer, ProTable } from "@ant-design/pro-components";
import type { ActionType, ProColumns } from "@ant-design/pro-components";
import { Link, Route, Routes, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, ITEM_FILTERS, listItems, safeRecordId } from "./api";
import type { ItemQuery, ItemSummary } from "./api";
import { sourcePoint } from "./adminNavigation";
import { ITEM_PROJECTS, ITEM_STATUSES, useItemFields, validateItem } from "./itemFields";
import { CreateItem } from "./CreateItem";
import { ItemDetailPage } from "./ItemDetailPage";
const MATCHES: Record<string, string> = { item_uid: "物品编号", sku_code: "款式编号", name: "物品名称", chip_uid: "关联芯片UID" };
const failureText = (error: unknown, fallback: string) => error instanceof ApiError ? error.message : fallback;

function queryFrom(search: URLSearchParams): ItemQuery {
  const integer = (name: string, fallback: number) => /^[1-9][0-9]*$/.test(search.get(name) || "") ? Number(search.get(name)) : fallback;
  const query: ItemQuery = { page: integer("page", 1), page_size: integer("page_size", 20) };
  for (const key of ITEM_FILTERS) if (search.has(key)) query[key] = search.get(key)!;
  return query;
}
function queryString(query: ItemQuery) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value !== "" && value !== undefined && value !== null) search.set(key, String(value));
  return search;
}
function submittedQuery(values: Record<string, unknown>, pageSize: number): ItemQuery {
  const query: ItemQuery = { page: 1, page_size: pageSize };
  for (const key of ITEM_FILTERS) if (!/_(from|to)$/.test(key) && typeof values[key] === "string" && values[key]) query[key] = values[key] as string;
  for (const name of ["created", "updated"] as const) {
    const range = values[`${name}_range`];
    if (Array.isArray(range) && range.length === 2) {
      if (range[0]) query[`${name}_from`] = String(range[0]);
      if (range[1]) query[`${name}_to`] = String(range[1]);
    }
  }
  return query;
}
function ItemListPage({ onSessionExpired }: { onSessionExpired: () => void }) {
  const location = useLocation(), navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const query = useMemo(() => queryFrom(new URLSearchParams(search)), [search]);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const fields = useItemFields().filter(field => !["care_instructions", "meaning", "description", "material", "image_urls", "size_chart"].includes(field.key));
  const sequence = useRef(0);
  const action = useRef<ActionType | undefined>(undefined);
  const initial = useMemo(() => ({ ...Object.fromEntries(ITEM_FILTERS.filter(key => !/_(from|to)$/.test(key)).map(key => [key, query[key]])),
    ...Object.fromEntries(["created", "updated"].map(name => [`${name}_range`, query[`${name}_from` as keyof ItemQuery] || query[`${name}_to` as keyof ItemQuery]
      ? [query[`${name}_from` as keyof ItemQuery], query[`${name}_to` as keyof ItemQuery]] : undefined])),
  }), [query]);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (loaded && typeof location.state?.restoreScroll === "number") window.scrollTo({ top: location.state.restoreScroll });
  }, [loaded, location.key]);
  const common: ProColumns<ItemSummary>[] = fields.map(field => ({ title: field.label, dataIndex: field.key, key: `view_${field.key}`, hideInSearch: true,
    render: (_, row) => field.key === "item_uid" ? row.item_uid : field.render(row), width: field.key === "item_uid" ? 220 : 180 }));
  const columns: ProColumns<ItemSummary>[] = [
    { title: "关键词", dataIndex: "keyword", hideInTable: true, fieldProps: { maxLength: 128, placeholder: "物品编号、款式、名称或关联芯片UID" } },
    { title: "项目", dataIndex: "project", valueEnum: ITEM_PROJECTS, hideInTable: true },
    { title: "状态", dataIndex: "status", valueEnum: ITEM_STATUSES, hideInTable: true },
    { title: "关联芯片", dataIndex: "has_chip", valueEnum: { true: "已关联", false: "未关联" }, hideInTable: true },
    ...["created", "updated"].map((key, index): ProColumns<ItemSummary> => ({ title: ["创建日期（北京时间）", "更新日期（北京时间）"][index], dataIndex: `${key}_range`, valueType: "dateRange", colSize: 2, fieldProps: { allowEmpty: [true, true] }, hideInTable: true })),
    ...common,
    { title: "关键词匹配", dataIndex: "keyword_matches", hideInSearch: true, width: 180, render: (_, row) => row.keyword_matches.map(key => MATCHES[key] || key).join("、") || "—" },
    { title: "操作", valueType: "option", key: "actions", width: 100, fixed: "right", render: (_, row) => <Button type="link" disabled={!safeRecordId(row.id)}
      onClick={() => navigate(`/items/${row.id}`, { state: { returnTo: sourcePoint(location) } })}>查看详情</Button> },
  ];
  return <PageContainer title={<Typography.Title level={2} style={{ margin: 0 }}>物品管理</Typography.Title>} subTitle="查询物品、维护款式与资料；状态、绑定和配置分别处理。">
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {error && <Alert type="error" showIcon message={error} />}
      <ProTable<ItemSummary> key={location.search} rowKey="id" columns={columns} params={query} actionRef={action}
        form={{ name: "item-query", initialValues: initial }} search={{ defaultCollapsed: true, labelWidth: "auto", span: 6 }}
        headerTitle="物品列表" dateFormatter="string" scroll={{ x: 2200 }} options={{ density: true, fullScreen: false, reload: true, setting: true }}
        toolBarRender={() => [<Button key="create" type="primary" icon={<PlusOutlined aria-hidden />} onClick={() => setCreateOpen(true)}>创建物品</Button>]}
        onSubmit={values => { setLoaded(false); setSearch(queryString(submittedQuery(values, query.page_size || 20))); }}
        onReset={() => { setLoaded(false); setSearch(new URLSearchParams()); }}
        pagination={{ current: query.page, pageSize: query.page_size, showSizeChanger: true, pageSizeOptions: [20, 50, 100],
          }}
        onChange={(paging, _filters, _sorter, extra) => { if (extra.action === "paginate") { setLoaded(false); setSearch(queryString({ ...query, page: paging.current || 1, page_size: paging.pageSize || 20 })); } }}
        locale={{ emptyText: error ? "读取失败，请重试查询。" : search.toString() ? "没有符合条件的物品，可重置查询。" : "尚无物品，可创建草稿。" }}
        request={async () => {
          const ticket = ++sequence.current;
          setError(""); setLoaded(false);
          try {
            const result = await listItems(query);
            if (!Array.isArray(result.items) || !Number.isSafeInteger(result.total) || result.total < 0) throw new Error("列表返回异常");
            result.items.forEach(row => validateItem(row, row.id));
            if (ticket === sequence.current) {
              if (result.page_adjusted) setSearch(queryString({ ...query, page: result.page }), { replace: true });
              setLoaded(true);
            }
            return { data: result.items, total: result.total, success: true };
          } catch (failure) {
            if (ticket === sequence.current) {
              if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
              else setError(failureText(failure, "物品列表读取失败，请重试查询。"));
            }
            return { data: [], total: 0, success: false };
          }
        }} />
    </Space>
    {createOpen && <CreateItem onClose={() => { setCreateOpen(false); void action.current?.reload(); }} onSessionExpired={onSessionExpired} />}
  </PageContainer>;
}

export function ItemPanel({ onSessionExpired }: { onSessionExpired: () => void }) {
  return <Routes><Route index element={<ItemListPage onSessionExpired={onSessionExpired} />} />
    <Route path=":id" element={<ItemDetailPage onSessionExpired={onSessionExpired} />} />
    <Route path=":id/edit" element={<ItemDetailPage edit onSessionExpired={onSessionExpired} />} />
    <Route path="*" element={<Result status="404" title="物品页面不存在" extra={<Link to="/items">返回物品列表</Link>} />} /></Routes>;
}
