// 页面统一通过这里调用后端；Figma 调整样式时保留这一层。
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

async function readStatus(path: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    cache: "no-store",
    signal: AbortSignal.timeout(6000),
    headers: { Accept: "application/json" },
  });
  const result = await response.json();
  if (!response.ok || result.status !== "ok" || !result.data) {
    throw new Error("检查未通过");
  }
  return result.data;
}

export async function checkBackend(): Promise<void> {
  const data = await readStatus("/health");
  if (data.service !== "bumbum" || data.state !== "running") {
    throw new Error("后端返回结果不符合约定");
  }
}

export async function checkDatabase(): Promise<void> {
  const data = await readStatus("/ready");
  if (data.database !== "ready") {
    throw new Error("数据库返回结果不符合约定");
  }
}
