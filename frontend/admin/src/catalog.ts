import { dataScope, testBatch } from "./testDataMode";
import { request, ApiError } from "./api";
import type {
  ActionPayloadMap, ActionResult, CatalogAction, CatalogQuery, CatalogResource,
  CatalogRow, CatalogStatistics, DetailMap, DetailResource, H5Preview, Page, ResourceMap,
} from "./types/catalog";
export type { CatalogResource, CatalogQuery, Page } from "./types/catalog";
export type Row = CatalogRow;
export async function list<R extends CatalogResource>(
  resource: R,
  params: CatalogQuery = {},
): Promise<Page<ResourceMap[R]>> {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(
    ["styles", "issues", "items", "chips", "users", "physical-items", "activity", "orders"].includes(resource)
      ? { ...params, ...dataScope() }
      : params,
  ))
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  return request(`/admin/catalog/${resource}?${q}`);
}
export const read = <R extends DetailResource>(resource: R, id: number): Promise<DetailMap[R]> =>
  request(`/admin/catalog/${resource}/${id}`);
export const h5Preview = (id: number): Promise<H5Preview> =>
  request(`/admin/catalog/items/${id}/h5-preview`);
export const command = <A extends CatalogAction>(
  action: A,
  payload: ActionPayloadMap[A],
  requestId: string,
): Promise<ActionResult> =>
  request(`/admin/catalog/actions/${action}`, {
    request_id: requestId,
    payload:
      testBatch() && ["style", "register", "createOrder"].includes(action) && !("id" in payload && payload.id)
        ? { ...payload, test_batch_id: testBatch() }
        : payload,
  });
export const statistics = (params: CatalogQuery): Promise<CatalogStatistics> => {
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
export const edition = (i: { edition_number?: number | null; issue_total?: number | null; issue_id?: number | null }) =>
  i.edition_number
    ? `#${String(i.edition_number).padStart(i.issue_total ? String(i.issue_total).length : 3, "0")}${i.issue_total ? "/" + i.issue_total : ""}`
    : i.issue_id
      ? "正式编号待核定"
      : "未关联发行";
export const wholeStatus = (w: { ended_at?: string | null; lost_at?: string | null; loss_evidence?: string | null }) =>
  w.ended_at ? "已替换" : w.lost_at || w.loss_evidence ? "已挂失" : "正常";

export const validationHelp =
  "用于验证的对象标记，与设置中的验收数据开关独立。标记后可直接删除该对象，保留另一侧档案及操作审计；不表示实卡核验通过。";

export function fromPath(path: string, from: string) {
  return from ? path + (path.includes("?") ? "&" : "?") + "from=" + encodeURIComponent(from) : path;
}

export function orderPath(orderId: number, unitId?: number, from = "") {
  return fromPath("/orders/" + orderId + (unitId ? "?unit=" + unitId : ""), from);
}

export function assemblyPath(from: string, fields: Record<string, number | undefined> = {}) {
  const query = new URLSearchParams({ from });
  Object.entries(fields).forEach(([key, id]) => { if (id) query.set(key, String(id)); });
  return "/items/new?" + query;
}


export const itemWorkflowNames: Record<string, string> = {
  assembly: "待装配", verification: "待核验", available: "可分配",
  delivery: "待交付", claim: "待认领", activation: "待启用",
  allocation: "待分配", sale: "待售出", held: "已有持有人",
  missing_issue: "待补发行", review: "待核对",
  archived: "已归档", lost: "已挂失", disabled: "已停用",
};

export const workbenchWorkflows = ["assembly", "verification", "delivery", "claim", "available"] as const;

export function itemWorkflow(row: Pick<CatalogRow, "workflow">) {
  return (row.workflow && itemWorkflowNames[row.workflow]) || "—";
}

export function activityPath(from: string, params: Record<string, string | number | undefined>) {
  const q = new URLSearchParams({ from });
  Object.entries(params).forEach(([key, value]) => { if (value !== undefined) q.set(key, String(value)); });
  return "/overview/activity?" + q;
}
