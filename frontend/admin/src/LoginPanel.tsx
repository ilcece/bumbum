import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, readSession, signIn, signOut } from "./api";
import { ChipPanel } from "./ChipPanel";
import { ItemPanel } from "./ItemPanel";

type Phase = "loading" | "out" | "in" | "unavailable";

function explain(error: unknown): string {
  return error instanceof ApiError ? error.message : "暂时无法连接，请确认后端正在运行，再重新读取登录状态。";
}

export function LoginPanel() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [expiry, setExpiry] = useState("");
  const expireSession = useCallback(() => { setPhase("out"); setMessage("登录已失效，请重新登录。"); }, []);

  async function refresh() {
    setBusy(true);
    try {
      const session = await readSession();
      setExpiry(session.expires_at);
      setPhase("in");
      setMessage("");
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setPhase("out");
        setMessage("");
      } else {
        setPhase("unavailable");
        setMessage(explain(error));
      }
      return false;
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true);
    setMessage("");
    try {
      await signIn(String(fields.get("username")), String(fields.get("password")), String(fields.get("code")));
      await refresh();
    } catch (error) {
      setMessage(explain(error));
      if (!(error instanceof ApiError)) setPhase("unavailable");
    } finally {
      // 密码和验证码不进入浏览器存储，提交后清空输入框。
      for (const name of ["password", "code"]) {
        const field = form.elements.namedItem(name);
        if (field instanceof HTMLInputElement) field.value = "";
      }
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setMessage("");
    try {
      await signOut();
      setPhase("out");
      setExpiry("");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setPhase("out");
        setMessage("登录已失效，请重新登录。");
      } else if (error instanceof ApiError && error.code === "csrf_failed") {
        if (await refresh()) setMessage("登录状态已更新，请再点一次退出登录。");
      } else {
        setMessage(explain(error));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="auth-panel" aria-labelledby="login-title" aria-busy={busy}>
      <h2 id="login-title">管理员登录</h2>
      {phase === "loading" && <p>正在读取登录状态…</p>}
      {phase === "out" && <>
        <p>填写账号、密码和手机 Authenticator 验证码。同一组验证码只能成功登录一次。</p>
        <form onSubmit={event => void submit(event)} aria-label="管理员登录表单">
          <label>账号<input name="username" autoComplete="username" maxLength={64} required /></label>
          <label>密码<input name="password" type="password" autoComplete="current-password" maxLength={128} required /></label>
          <label>Authenticator 验证码<input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} required /></label>
          <button disabled={busy} type="submit">{busy ? "正在登录…" : "登录"}</button>
        </form>
      </>}
      {phase === "in" && <>
        <p className="signed-in">管理员已登录</p>
        <p>本次登录到期时间：{new Date(expiry).toLocaleString("zh-CN", { hour12: false })}</p>
        <div className="actions">
          <button type="button" onClick={() => void refresh()} disabled={busy}>重新读取登录状态</button>
          <button type="button" onClick={() => void logout()} disabled={busy}>退出登录</button>
        </div>
        <ChipPanel onSessionExpired={expireSession} />
        <ItemPanel onSessionExpired={expireSession} />
      </>}
      {phase === "unavailable" && <button type="button" onClick={() => void refresh()} disabled={busy}>重新读取登录状态</button>}
      {message && <p className="notice" role="alert">{message}</p>}
    </section>
  );
}
