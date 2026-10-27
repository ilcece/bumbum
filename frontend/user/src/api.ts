// 用户接口不读取管理会话，不在浏览器存储凭证或触碰原文。
export type Profile = {
  name: string;
  description: string | null;
  material: string | null;
  care_instructions: string | null;
  image_urls: string[];
};
export type ItemView = {
  project: "fashion";
  item_id: number;
  item_uid: string;
  verified_at: string;
  retrieved_at: string;
  profile: Profile;
};
export type Reading = { picc_data: string; cmac: string };
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public retryAfter = 0,
    public errorId?: string,
  ) {
    super(message);
  }
}
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new ApiError(
      502,
      "unexpected_response",
      "无法读取服务结果，请稍后重试。",
    );
  return value as Record<string, unknown>;
}
function invalid(): never {
  throw new ApiError(
    502,
    "unexpected_response",
    "资料返回不完整，请稍后重试更新。",
  );
}
function profile(value: unknown): Profile {
  const p = object(value);
  if (
    typeof p.name !== "string" ||
    !p.name.trim() ||
    ![p.description, p.material, p.care_instructions].every(
      (x) => x === null || typeof x === "string",
    ) ||
    !Array.isArray(p.image_urls) ||
    !p.image_urls.every((x) => typeof x === "string" && /^https?:\/\//i.test(x))
  )
    invalid();
  return {
    name: p.name as string,
    description: p.description as string | null,
    material: p.material as string | null,
    care_instructions: p.care_instructions as string | null,
    image_urls: p.image_urls as string[],
  };
}
export function itemView(value: unknown): ItemView {
  const d = object(value);
  if (
    d.project !== "fashion" ||
    !Number.isSafeInteger(d.item_id) ||
    Number(d.item_id) <= 0 ||
    typeof d.item_uid !== "string" ||
    !/^FASH-[0-9]{4}-[0-9]{6}$/.test(d.item_uid) ||
    ![d.verified_at, d.retrieved_at].every(
      (x) =>
        typeof x === "string" &&
        /^\d{4}-\d\d-\d\dT.*Z$/.test(x) &&
        Number.isFinite(Date.parse(x)),
    )
  )
    invalid();
  return {
    project: "fashion",
    item_id: Number(d.item_id),
    item_uid: d.item_uid as string,
    verified_at: d.verified_at as string,
    retrieved_at: d.retrieved_at as string,
    profile: profile(d.profile),
  };
}
async function request(
  path: string,
  signal: AbortSignal,
  body?: unknown,
): Promise<Record<string, unknown>> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal.addEventListener("abort", abort, { once: true });
  if (signal.aborted) controller.abort();
  const timer = setTimeout(abort, 6000);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
      headers:
        body === undefined
          ? { Accept: "application/json" }
          : { Accept: "application/json", "Content-Type": "application/json" },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const data = object(await response.json());
    if (!response.ok || data.status !== "ok") {
      const raw = response.headers.get("Retry-After");
      const wait =
        raw && /^\d+$/.test(raw)
          ? Number(raw) * 1000
          : raw
            ? Math.max(0, Date.parse(raw) - Date.now())
            : 0;
      const errorId =
        typeof data.error_id === "string" &&
        /^[a-f0-9]{24}$/.test(data.error_id)
          ? data.error_id
          : undefined;
      throw new ApiError(
        response.status,
        String(data.code || "request_failed"),
        typeof data.message === "string"
          ? data.message
          : "请求未完成，请稍后再试。",
        Number.isFinite(wait) ? wait : 0,
        errorId,
      );
    }
    return object(data.data);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      0,
      "network_error",
      "网络或服务暂不可用，请检查网络后重试。",
    );
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", abort);
  }
}
export async function verify(
  reading: Reading,
  signal: AbortSignal,
): Promise<ItemView | "unsupported"> {
  const d = await request("/api/tap/verify", signal, {
    ...reading,
    browser_view: true,
  });
  if (d.verified !== true)
    throw new ApiError(
      200,
      String(d.reason || "verification_failed"),
      typeof d.message === "string"
        ? d.message
        : "本次验证未通过，请重新触碰。",
    );
  if (d.project === "jewelry") return "unsupported";
  if (d.view_path !== `/tap/items/${d.item_id}`) invalid();
  return itemView({ ...d, profile: d.item_detail });
}
export async function readView(
  id: number,
  signal: AbortSignal,
): Promise<ItemView> {
  const result = itemView(await request(`/api/tap/items/${id}/view`, signal));
  if (result.item_id !== id) invalid();
  return result;
}
