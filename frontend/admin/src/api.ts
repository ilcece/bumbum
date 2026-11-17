// 所有请求集中在这里；登录Cookie交给浏览器，防冒用口令只保存在内存。
const API_BASE = "/api";
let csrfToken: string | null = null;
let sessionExpired = false;
export const sessionIsExpired = () => sessionExpired;

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public errorId?: string,
  ) {
    super(errorId ? `${message}（错误编号：${errorId}）` : message);
  }
}

export type AdminSession = {
  authenticated: true;
  expires_at: string;
  csrf_token: string;
  draft_scope?: string;
};

export async function request<T>(
  path: string,
  body?: Record<string, unknown>,
  method?: "PUT" | "PATCH",
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    if (csrfToken && path !== "/admin/auth/login")
      headers["X-CSRF-Token"] = csrfToken;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method: method || (body === undefined ? "GET" : "POST"),
    credentials: "include",
    cache: "no-store",
    signal: AbortSignal.timeout(6000),
    headers,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  return responseData<T>(response);
}

async function responseData<T>(response: Response): Promise<T> {
  let result;
  try {
    result = await response.json();
  } catch {
    throw new ApiError(
      response.status,
      "unexpected_response",
      "无法读取服务结果，请确认后端正在运行。",
    );
  }
  if (response.status === 401 && !response.url.endsWith("/auth/login")) {
    sessionExpired = true;
    csrfToken = null;
    window.dispatchEvent(new Event("admin-session-expired"));
  }
  if (!result || !response.ok || result.status !== "ok" || !result.data) {
    const errorId =
      typeof result?.error_id === "string" &&
      /^[a-f0-9]{24}$/.test(result.error_id)
        ? result.error_id
        : undefined;
    throw new ApiError(
      response.status,
      result?.code || "unexpected_response",
      result?.message || "请求未完成，请重试。",
      errorId,
    );
  }
  return result.data as T;
}

export async function checkBackend(): Promise<void> {
  const data = await request<Record<string, unknown>>("/health");
  if (data.service !== "bumbum" || data.state !== "running")
    throw new Error("后端返回结果不符合约定");
}

export async function checkDatabase(): Promise<void> {
  const data = await request<Record<string, unknown>>("/ready");
  if (data.database !== "ready") throw new Error("数据库返回结果不符合约定");
}

export async function readSession(): Promise<AdminSession> {
  try {
    const session = await request<AdminSession>("/admin/auth/session");
    if (
      session.authenticated !== true ||
      !session.expires_at ||
      !/^[0-9a-f]{64}$/.test(session.csrf_token)
    ) {
      throw new Error("登录状态返回结果不符合约定");
    }
    csrfToken = session.csrf_token;
    sessionExpired = false;
    return session;
  } catch (error) {
    csrfToken = null;
    throw error;
  }
}

export async function signIn(
  username: string,
  password: string,
  code: string,
): Promise<void> {
  await request("/admin/auth/login", { username, password, code });
  csrfToken = null;
}

export async function signOut(): Promise<void> {
  await request("/admin/auth/logout", {});
  csrfToken = null;
}

export type ChipView = {
  candidate_id?: number | null;
  candidate_item_id?: number | null;
  candidate_item_uid?: string | null;
  registration_source: "unknown" | "manual" | "nfc_cool";
  id: number;
  chip_uid: string;
  project: "fashion" | "jewelry" | null;
  chip_status: "pending" | "bound" | "disabled" | "lost" | "retired";
  item_id: number | null;
  item_uid: string | null;
  batch_no: string | null;
  provisioned_at: string | null;
  keys_generated: boolean;
  created_at: string;
  updated_at: string;
};
function safeRecordId(id: number): boolean {
  return Number.isSafeInteger(id) && id > 0;
}

export type ChipKeys = {
  chip_uid: string;
  keys: Record<string, string>;
  sun_url_template: string;
};
export type SunReading = { picc_data: string; cmac: string };

export function chipKeyRequest<T>(
  id: number,
  action: "generate-keys" | "keys" | "confirm-provisioning",
  body: Record<string, unknown>,
): Promise<T> {
  if (!Number.isSafeInteger(id) || id <= 0)
    throw new Error("记录编号超出页面可处理范围，未提交操作。");
  return request(`/admin/chips/${id}/${action}`, body);
}

export async function uploadStyleImage(
  styleId: number,
  assetId: string,
  file: File,
): Promise<{ url: string }> {
  const form = new FormData();
  form.append("file", file);
  return responseData(
    await fetch(
      `${API_BASE}/admin/catalog/styles/${styleId}/images/${assetId}`,
      {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfToken || "" },
        body: form,
        signal: AbortSignal.timeout(30000),
      },
    ),
  );
}

// 配卡须同时识别当前关联和已保存的候选关联，不通过关键词猜测对象。
export async function readConfigurationChip(id: number): Promise<ChipView> {
  if (!safeRecordId(id)) throw new Error("芯片记录编号超出页面可处理范围。");
  const chip = await request<ChipView>(`/admin/catalog/chips/${id}`);
  if (chip.candidate_item_id) {
    const item = await request<{ item_uid: string }>(
      `/admin/catalog/items/${chip.candidate_item_id}`,
    );
    chip.candidate_item_uid = item.item_uid;
  }
  return chip;
}
