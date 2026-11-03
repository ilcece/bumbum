import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Collapse, Form, Input, Space, Spin, Typography } from "antd";
import { ApiError, readSession, signIn, signOut } from "./api";
import { AdminLayout } from "./AdminLayout";
import { RuntimeChecks } from "./RuntimeChecks";

type Phase = "loading" | "out" | "in" | "unavailable";

function explain(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "暂时无法连接，请确认后端正在运行，再重新读取登录状态。";
}

export function LoginPanel() {
  const [form] = Form.useForm();
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

  async function submit(fields: { username: string; password: string; code: string }) {
    setBusy(true);
    setMessage("");
    try {
      await signIn(
        fields.username,
        fields.password,
        fields.code,
      );
      await refresh();
    } catch (error) {
      setMessage(explain(error));
      if (!(error instanceof ApiError)) setPhase("unavailable");
    } finally {
      // 密码和验证码不进入浏览器存储，提交后清空输入框。
      form.setFieldsValue({ password: "", code: "" });
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
  return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
    <Card style={{ width: 460, maxWidth: "100%" }} aria-labelledby="login-title" aria-busy={busy}>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <div><Typography.Title level={3}>BUMBUM</Typography.Title><Typography.Title level={4} id="login-title">管理员登录</Typography.Title>
          <Typography.Text type="secondary">使用账号、密码与手机 Authenticator 验证码登录。</Typography.Text></div>
        {phase === "loading" && <Spin tip="正在读取登录状态…"><div style={{ height: 80 }} /></Spin>}
        {phase === "out" && <Form form={form} layout="vertical" name="admin-login" aria-label="管理员登录表单" disabled={busy} onFinish={submit}>
          <Form.Item name="username" label="账号" rules={[{ required: true, message: "请输入账号。" }]}><Input name="username" autoComplete="username" maxLength={64} /></Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码。" }]}><Input.Password name="password" autoComplete="current-password" maxLength={128} /></Form.Item>
          <Form.Item name="code" label="Authenticator 验证码" rules={[{ required: true, message: "请输入验证码。" }, { pattern: /^[0-9]{6}$/, message: "请输入6位数字。" }]}>
            <Input name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={busy}>登录</Button>
        </Form>}
        {message && <Alert type="error" showIcon message={message} />}
        {phase === "unavailable" && <Button loading={busy} onClick={() => void refresh()}>重新读取登录状态</Button>}
        <Collapse items={[{ key: "checks", label: "检查运行环境", children: <RuntimeChecks /> }]} />
        <Typography.Text type="secondary">账号设置或验证器重置，请按管理员操作手册处理。</Typography.Text>
      </Space>
    </Card>
  </main>;
}
