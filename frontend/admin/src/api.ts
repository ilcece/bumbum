// 所有请求集中在这里；登录Cookie交给浏览器，防冒用口令只保存在内存。
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
let csrfToken: string | null = null;

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public errorId?: string) {
    super(errorId ? `${message}（错误编号：${errorId}）` : message);
  }
}

export type AdminSession = { authenticated: true; expires_at: string; csrf_token: string };

async function request<T>(path: string, body?: Record<string, unknown>, method?: "PUT" | "PATCH"): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    if (csrfToken && path !== "/admin/auth/login") headers["X-CSRF-Token"] = csrfToken;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method: method || (body === undefined ? "GET" : "POST"),
    credentials: "include",
    cache: "no-store",
    signal: AbortSignal.timeout(6000),
    headers,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  let result;
  try {
    result = await response.json();
  } catch {
    throw new ApiError(response.status, "unexpected_response", "无法读取服务结果，请确认后端正在运行。");
  }
  if (!response.ok || result.status !== "ok" || !result.data) {
    const errorId = typeof result.error_id === "string" && /^[a-f0-9]{24}$/.test(result.error_id) ? result.error_id : undefined;
    throw new ApiError(response.status, result.code || "unexpected_response", result.message || "请求未完成，请重试。", errorId);
  }
  return result.data as T;
}

export async function checkBackend(): Promise<void> {
  const data = await request<Record<string, unknown>>("/health");
  if (data.service !== "bumbum" || data.state !== "running") throw new Error("后端返回结果不符合约定");
}

export async function checkDatabase(): Promise<void> {
  const data = await request<Record<string, unknown>>("/ready");
  if (data.database !== "ready") throw new Error("数据库返回结果不符合约定");
}

export async function readSession(): Promise<AdminSession> {
  try {
    const session = await request<AdminSession>("/admin/auth/session");
    if (session.authenticated !== true || !session.expires_at || !/^[0-9a-f]{64}$/.test(session.csrf_token)) {
      throw new Error("登录状态返回结果不符合约定");
    }
    csrfToken = session.csrf_token;
    return session;
  } catch (error) {
    csrfToken = null;
    throw error;
  }
}

export async function signIn(username: string, password: string, code: string): Promise<void> {
  await request("/admin/auth/login", { username, password, code });
  csrfToken = null;
}

export async function signOut(): Promise<void> {
  await request("/admin/auth/logout", {});
  csrfToken = null;
}

export type ChipView = {
  registration_source: "unknown" | "manual" | "nfc_cool";
  id: number; chip_uid: string; project: "fashion" | "jewelry" | null;
  chip_status: "pending" | "bound" | "disabled" | "lost";
  item_id: number | null; item_uid: string | null; batch_no: string | null;
  provisioned_at: string | null; keys_generated: boolean;
  created_at: string; updated_at: string;
};
export type ChipQuery = { page: number; project: string; status: string; keyword: string };
export type ChipList = { items: ChipView[]; total: number; page: number; page_size: number };

export async function listChips(query: ChipQuery): Promise<ChipList> {
  const parameters = new URLSearchParams({ page: String(query.page), page_size: "20" });
  for (const name of ["project", "status", "keyword"] as const) {
    if (query[name]) parameters.set(name, query[name]);
  }
  return request<ChipList>(`/admin/chips?${parameters}`);
}

export async function registerChip(chip_uid: string, project: string | null, batch_no: string | null): Promise<{ chip: ChipView; is_new: boolean }> {
  return request("/admin/chips", { chip_uid, project, batch_no });
}

export function bindChipItem(chipId: number, itemId: number): Promise<ChipView> {
  if (![chipId, itemId].every(id => Number.isSafeInteger(id) && id > 0)) {
    throw new Error("记录编号超出当前页面可处理范围，请反馈，未提交绑定。");
  }
  return request(`/admin/chips/${chipId}/bind-item`, { item_id: itemId });
}

export type ChipKeys = { chip_uid: string; keys: Record<string, string>; sun_url_template: string };
export type SunReading = { picc_data: string; cmac: string };

export function chipKeyRequest<T>(id: number, action: "generate-keys" | "keys" | "confirm-provisioning", body: Record<string, unknown>): Promise<T> {
  if (!Number.isSafeInteger(id) || id <= 0) throw new Error("记录编号超出页面可处理范围，未提交操作。");
  return request(`/admin/chips/${id}/${action}`, body);
}

export type ItemView = {
  id: number; project: "fashion" | "jewelry"; item_uid: string; sku_code: string | null;
  status: "draft" | "active" | "disabled" | "archived";
  created_at: string | null; updated_at: string | null; profile: Record<string, unknown> | null;
};
export type ItemQuery = { page: number; project: string; status: string; keyword: string; unbound_only?: boolean };
export type ItemList = { items: ItemView[]; total: number; page: number; page_size: number };

export async function listItems(query: ItemQuery): Promise<ItemList> {
  const parameters = new URLSearchParams({ page: String(query.page), page_size: "20" });
  if (query.unbound_only !== undefined) parameters.set("unbound_only", String(query.unbound_only));
  for (const name of ["project", "status", "keyword"] as const) {
    if (query[name]) parameters.set(name, query[name]);
  }
  return request(`/admin/items?${parameters}`);
}

export async function createItem(project: string, item_uid: string, sku_code: string | null): Promise<ItemView> {
  return request("/admin/items", { project, item_uid, sku_code });
}

export type FashionProfile = {
  name: string; description: string | null; material: string | null;
  care_instructions: string | null; image_urls: string[];
};

export function readItem(id: number): Promise<ItemView> {
  return request(`/admin/items/${id}`);
}

export function saveFashionProfile(id: number, profile: FashionProfile): Promise<FashionProfile> {
  return request(`/admin/items/${id}/profile`, profile, "PUT");
}

export function changeItemStatus(id: number, status: "active" | "disabled"): Promise<ItemView> {
  return request(`/admin/items/${id}`, { status }, "PATCH");
}

// 统计接口只读；条件与结果一起校验，不能用缺字段或精度丢失的数字充当零。
export type TapStatsQuery = { project: "" | "fashion" | "jewelry"; range: "7d" | "30d" | "all"; q: string; page: number };
export type TapStats = {
  filters: { project: "fashion" | "jewelry" | null; range: TapStatsQuery["range"]; q: string };
  timezone: "Asia/Shanghai"; as_of: string;
  period: { from_date: string | null; to_date: string }; first_recorded_at: string | null;
  summary: { valid_taps: number; touched_items: number };
  daily: { date: string; valid_taps: number }[];
  items: { project: "fashion" | "jewelry"; item_uid: string; name: string | null; valid_taps: number; last_tap_at: string }[];
  total_items: number; page: number; page_size: number; total_pages: number; page_adjusted: boolean;
};

export function normalizeStatsKeyword(value: string): string {
  // Python strip的Unicode空白包含四个额外控制字符，不使用会额外去掉BOM的JS trim。
  return value.replace(/^[\p{White_Space}\u001c-\u001f]+|[\p{White_Space}\u001c-\u001f]+$/gu, "");
}

function validStats(data: unknown, query: TapStatsQuery): data is TapStats {
  const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
  const count = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
  const day = (value: unknown): value is string => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
    && Number.isFinite(Date.parse(value + "T00:00:00Z")) && new Date(value + "T00:00:00Z").toISOString().slice(0, 10) === value;
  const instant = (value: unknown): value is string => typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)
    && day(value.slice(0, 10)) && Number.isFinite(Date.parse(value));
  const beijingDay = (value: string) => new Date(Date.parse(value) + 8 * 3600000).toISOString().slice(0, 10);
  if (!object(data) || !object(data.filters) || !object(data.period) || !object(data.summary) || !instant(data.as_of)
    || data.timezone !== "Asia/Shanghai" || data.filters.project !== (query.project || null) || data.filters.range !== query.range
    || data.filters.q !== normalizeStatsKeyword(query.q) || !day(data.period.to_date) || data.period.to_date !== beijingDay(data.as_of)
    || !(data.period.from_date === null || day(data.period.from_date)) || !(data.first_recorded_at === null || instant(data.first_recorded_at))
    || !count(data.summary.valid_taps) || !count(data.summary.touched_items) || data.summary.touched_items > data.summary.valid_taps
    || !Array.isArray(data.daily) || !Array.isArray(data.items) || !count(data.total_items) || !count(data.page) || data.page < 1
    || data.page_size !== 20 || !count(data.total_pages) || typeof data.page_adjusted !== "boolean") return false;
  if ((data.first_recorded_at === null && data.summary.valid_taps > 0) || (data.first_recorded_at !== null && Date.parse(data.first_recorded_at) > Date.parse(data.as_of))) return false;
  const expectedStart = query.range === "all" ? (data.first_recorded_at ? beijingDay(data.first_recorded_at) : null)
    : new Date(Date.parse(data.period.to_date + "T00:00:00Z") - (query.range === "7d" ? 6 : 29) * 86400000).toISOString().slice(0, 10);
  if (data.period.from_date !== expectedStart) return false;
  const expectedDays = expectedStart ? (Date.parse(data.period.to_date) - Date.parse(expectedStart)) / 86400000 + 1 : 0;
  if (data.daily.length !== expectedDays || data.total_items > data.summary.touched_items
    || (!data.filters.q && data.total_items !== data.summary.touched_items)
    || data.total_pages !== Math.ceil(data.total_items / 20) || data.page !== Math.min(query.page, Math.max(1, data.total_pages))
    || data.page_adjusted !== (data.page !== query.page)
    || data.items.length !== Math.min(20, Math.max(0, data.total_items - (data.page - 1) * 20))) return false;
  let sum = 0;
  for (let index = 0; index < data.daily.length; index++) {
    const point: unknown = data.daily[index];
    const expectedDate = new Date(Date.parse(expectedStart!) + index * 86400000).toISOString().slice(0, 10);
    if (!object(point) || point.date !== expectedDate || !count(point.valid_taps)) return false;
    sum += point.valid_taps;
  }
  if (!count(sum) || sum !== data.summary.valid_taps) return false;
  const seen = new Set<string>();
  let itemSum = 0;
  let previous: { valid_taps: number; last_tap_at: string; item_uid: string } | null = null;
  for (const row of data.items) {
    if (!object(row) || !["fashion", "jewelry"].includes(String(row.project)) || (query.project && row.project !== query.project)
      || typeof row.item_uid !== "string" || !row.item_uid || seen.has(row.item_uid)
      || !(row.name === null || (typeof row.name === "string" && normalizeStatsKeyword(row.name).length > 0))
      || !count(row.valid_taps) || row.valid_taps < 1 || row.valid_taps > data.summary.valid_taps || !instant(row.last_tap_at)
      || Date.parse(row.last_tap_at) > Date.parse(data.as_of) || (expectedStart && beijingDay(row.last_tap_at) < expectedStart)) return false;
    if (previous && (row.valid_taps > previous.valid_taps || (row.valid_taps === previous.valid_taps
      && (Date.parse(row.last_tap_at) > Date.parse(previous.last_tap_at) || (row.last_tap_at === previous.last_tap_at && row.item_uid < previous.item_uid))))) return false;
    seen.add(row.item_uid);
    itemSum += row.valid_taps;
    previous = { valid_taps: row.valid_taps, last_tap_at: row.last_tap_at, item_uid: row.item_uid };
  }
  return Number.isSafeInteger(itemSum) && itemSum <= data.summary.valid_taps
    && (data.filters.q !== "" || data.total_pages > 1 || itemSum === data.summary.valid_taps);
}

export async function listTapStats(query: TapStatsQuery): Promise<TapStats> {
  const parameters = new URLSearchParams({ range: query.range, page: String(query.page), page_size: "20" });
  if (query.project) parameters.set("project", query.project);
  if (query.q) parameters.set("q", query.q);
  const data: unknown = await request(`/admin/stats/taps?${parameters}`);
  if (!validStats(data, query)) throw new ApiError(200, "unexpected_response", "触碰统计返回不完整或不一致，请重试；未用零值替代。");
  return data;
}
