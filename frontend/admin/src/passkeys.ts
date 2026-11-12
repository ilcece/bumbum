import { request } from "./api";

const base = "/admin/auth/passkeys";
export const passkeysEnabled = () => window.location.hostname === "test.bumbum.cc";
export const passkeysSupported = () =>
  window.PublicKeyCredential &&
  typeof PublicKeyCredential.parseCreationOptionsFromJSON === "function" &&
  typeof PublicKeyCredential.parseRequestOptionsFromJSON === "function" &&
  typeof PublicKeyCredential.prototype.toJSON === "function";

export async function usePasskey(mode: "register" | "login") {
  if (!passkeysSupported()) throw new Error("当前浏览器不支持此通行密钥流程，请使用最新版 Edge 或动态码。");
  const { options } = await request<{ options: any }>(`${base}/${mode}/options`, {});
  const credential = mode === "register"
    ? await navigator.credentials.create({ publicKey: PublicKeyCredential.parseCreationOptionsFromJSON(options) })
    : await navigator.credentials.get({ publicKey: PublicKeyCredential.parseRequestOptionsFromJSON(options) });
  if (!(credential instanceof PublicKeyCredential)) throw new Error("通行密钥确认未完成。");
  return request(`${base}/${mode}/finish`, { challenge: options.challenge, credential: credential.toJSON() });
}

export function listPasskeys() {
  return request<{ items: { id: number; created_at: string; last_used_at?: string }[] }>(base);
}

export function revokePasskey(id: number) {
  return request(`${base}/${id}/revoke`, {});
}

export function passkeyMessage(error: unknown) {
  return error instanceof DOMException && error.name === "NotAllowedError"
    ? "通行密钥确认已取消、超时或设备上暂无此站点的密钥。"
    : error instanceof Error ? error.message : "通行密钥操作未完成。";
}
