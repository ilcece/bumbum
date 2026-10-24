// 所有请求集中在这里；登录Cookie交给浏览器，防冒用口令只保存在内存。
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
let csrfToken: string | null = null;

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export type AdminSession = { authenticated: true; expires_at: string; csrf_token: string };

async function request<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    if (csrfToken && path !== "/admin/auth/login") headers["X-CSRF-Token"] = csrfToken;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method: body === undefined ? "GET" : "POST",
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
    throw new ApiError(response.status, result.code || "unexpected_response", result.message || "请求未完成，请重试。");
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
