import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, readSession, signIn, signOut } from "./api";
import { AdminLayout } from "./AdminLayout";
import { RuntimeChecks } from "./RuntimeChecks";
import { Sparkles } from "lucide-react";

type Phase = "loading" | "out" | "in" | "unavailable";

function explain(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "暂时无法连接，请确认后端正在运行，再重新读取登录状态。";
}

export function LoginPanel() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [expiry, setExpiry] = useState("");
  const expireSession = useCallback(() => {
    setPhase("out");
    setMessage("登录已失效，请重新登录。");
  }, []);

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

  useEffect(() => {
    void refresh();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true);
    setMessage("");
    try {
      await signIn(
        String(fields.get("username")),
        String(fields.get("password")),
        String(fields.get("code")),
      );
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

  if (phase === "in")
    return (
      <AdminLayout
        expiry={expiry}
        busy={busy}
        onLogout={() => void logout()}
        onSessionExpired={expireSession}
        message={message}
      />
    );
  return (
    <main className="login-page">
      <section
        className="login-card"
        aria-labelledby="login-title"
        aria-busy={busy}
      >
        <div className="brand">
          <div className="brand-symbol">
            <Sparkles />
          </div>
          <div>
            <strong>BUMBUM</strong>
            <span>管理后台</span>
          </div>
        </div>
        <div className="eyebrow">BUMBUM OPERATIONS</div>
        <h1 id="login-title">管理员登录</h1>
        <p>使用账号、密码与手机 Authenticator 验证码登录。</p>
        {phase === "loading" && <p role="status">正在读取登录状态…</p>}
        {phase === "out" && (
          <form
            onSubmit={(event) => void submit(event)}
            aria-label="管理员登录表单"
          >
            <fieldset disabled={busy}>
              <label>
                账号
                <input
                  name="username"
                  autoComplete="username"
                  maxLength={64}
                  required
                />
              </label>
              <label>
                密码
                <input
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  maxLength={128}
                  required
                />
              </label>
              <label>
                Authenticator 验证码
                <input
                  name="code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  minLength={6}
                  maxLength={6}
                  required
                />
              </label>
              <button className="action action-primary" type="submit">
                {busy ? "正在登录…" : "登录"}
              </button>
            </fieldset>
          </form>
        )}
        {message && (
          <p className="feedback feedback-danger" role="alert">
            {message}
          </p>
        )}
        {phase === "unavailable" && (
          <button
            className="action"
            onClick={() => void refresh()}
            disabled={busy}
          >
            重新读取登录状态
          </button>
        )}
        <details className="login-checks">
          <summary>检查运行环境</summary>
          <RuntimeChecks />
        </details>
        <p className="login-note">
          账号设置或验证器重置，请按管理员操作手册处理。
        </p>
      </section>
    </main>
  );
}
