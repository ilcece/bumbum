import { request, ApiError } from "./api";
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
  for (const [k, v] of Object.entries(params))
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  return request(`/admin/catalog/${resource}?${q}`);
}
export const read = (resource: string, id: number): Promise<Row> =>
  request(`/admin/catalog/${resource}/${id}`);
export const command = (
  action: string,
  payload: Record<string, any>,
  requestId: string,
): Promise<Row> =>
  request(`/admin/catalog/actions/${action}`, {
    request_id: requestId,
    payload,
  });
export const statistics = (params: Record<string, any>): Promise<Row> => {
  const q = new URLSearchParams(
    Object.entries(params)
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
    ? `#${String(i.edition_number).padStart(3, "0")}${i.issue_total ? "/" + i.issue_total : ""}`
    : i.issue_id
      ? "正式编号待核定"
      : "未关联发行";
export const wholeStatus = (w: Row) =>
  w.ended_at ? "已替换" : w.lost_at || w.loss_evidence ? "已挂失" : "正常";
