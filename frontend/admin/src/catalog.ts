import { dataScope, testBatch } from "./testDataMode";
import { request, ApiError } from "./api";
import type { ItemFacts } from "../../shared/itemPresentation";
export type Row = { id: number; [key: string]: any };
export type Page = {
  items: Row[];
  total: number;
  page: number;
  page_size: number;
};
export async function list(
  resource: string,
  params: Record<string, any> = {},
): Promise<Page> {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(
    ["styles", "issues", "items", "chips", "users", "physical-items", "activity", "orders"].includes(resource)
      ? { ...params, ...dataScope() }
      : params,
  ))
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  return request(`/admin/catalog/${resource}?${q}`);
}
export const read = (resource: string, id: number): Promise<Row> =>
  request(`/admin/catalog/${resource}/${id}`);
export const h5Preview = (id: number): Promise<Row & ItemFacts> =>
  request(`/admin/catalog/items/${id}/h5-preview`);
export const command = (
  action: string,
  payload: Record<string, any>,
  requestId: string,
): Promise<Row> =>
  request(`/admin/catalog/actions/${action}`, {
    request_id: requestId,
    payload:
      testBatch() && ["style", "register", "createOrder"].includes(action) && !payload.id
        ? { ...payload, test_batch_id: testBatch() }
        : payload,
  });
export const statistics = (params: Record<string, any>): Promise<Row> => {
  const q = new URLSearchParams(
    Object.entries({ ...params, ...dataScope() })
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)]),
  );
  return request(`/admin/catalog/statistics?${q}`);
};
export const unknown = (e: unknown) =>
  !(e instanceof ApiError) ||
  e.status >= 500 ||
  e.code === "unexpected_response";
export const statusNames: Record<string, string> = {
  draft: "草稿",
  active: "启用",
  disabled: "停用",
  archived: "归档",
  pending: "待绑定",
  bound: "已绑定",
  lost: "随物品挂失停用",
  retired: "已退役",
  fixed: "固定总量",
  period: "限时按销量定量",
  unlimited: "非限定",
  periodic: "定期换新",
  loss: "挂失换新",
  resale: "后台转售",
};
export const time = (v?: string | null) =>
  v
    ? new Date(v).toLocaleString("zh-CN", {
        timeZone: "Asia/Shanghai",
        hour12: false,
      })
    : "未记录";
export const edition = (i: Row) =>
  i.edition_number
    ? `#${String(i.edition_number).padStart(i.issue_total ? String(i.issue_total).length : 3, "0")}${i.issue_total ? "/" + i.issue_total : ""}`
    : i.issue_id
      ? "正式编号待核定"
      : "未关联发行";
export const wholeStatus = (w: Row) =>
  w.ended_at ? "已替换" : w.lost_at || w.loss_evidence ? "已挂失" : "正常";

export const validationHelp =
  "用于验证的对象标记，与设置中的验收数据开关独立。标记后可直接删除该对象，保留另一侧档案及操作审计；不表示实卡核验通过。";

export const orderPath = (orderId: number, unitId: number) => "/orders/" + orderId + "?unit=" + unitId;

export function assemblyPath(from: string, fields: Record<string, number | undefined> = {}) {
  const query = new URLSearchParams({ from });
  Object.entries(fields).forEach(([key, id]) => { if (id) query.set(key, String(id)); });
  return "/items/new?" + query;
}


export function itemWorkflow(row: Row) {
  if (row.status === "archived") return "已归档";
  if (row.lost_at || row.loss_evidence) return "已挂失";
  if (row.status === "disabled") return "已停用";
  if (!row.whole_id) return row.issue_id ? "待装配" : "待补发行";
  if (!row.provisioned_at) return "待核验";
  if (row.status !== "active") return "待启用";
  if (row.owner_id) return "已有持有人";
  if (row.has_claim_code || row.claim_code_status) return "待认领";
  if (row.sold) return "待交付";
  const order = row.order || (row.order_unit_id ? row : undefined);
  if (order) return order.allocated_at ? "待售出" : "待分配";
  return row.first_sold_at || !row.physical_item_id ? "待核对" : "可分配";
}

export function activityPath(from: string, params: Record<string, string | number | undefined>) {
  const q = new URLSearchParams({ from });
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined) q.set(key, String(value)); });
  return "/overview/activity?" + q;
}
