import { useState } from "react";
import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { history, useModel } from "@umijs/max";
import { readSession, signIn } from "../api";
import { RuntimeChecks } from "../RuntimeChecks";
import { passkeysEnabled, passkeyMessage, usePasskey } from "../passkeys";
export default function Login() {
  const [form] = Form.useForm(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const { refresh } = useModel("@@initialState");
  const complete = async () => {
    await readSession();
    await refresh();
    history.replace("/overview");
  };
  return (
    <main className="login-frame">
      <Card className="login-card">
        <div className="brand-lockup">
          <span className="brand-mark">BB</span>
        </div>
        <Typography.Title level={3}>BUMBUM</Typography.Title>
        <Typography.Title level={4}>管理员登录</Typography.Title>
        {passkeysEnabled() && <Button block type="primary" disabled={busy} style={{ marginBottom: 16 }}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              await usePasskey("login");
              await complete();
            } catch (failure) {
              setError(passkeyMessage(failure));
            } finally {
              setBusy(false);
            }
          }}>使用通行密钥登录</Button>}
        <Form
          form={form}
          layout="vertical"
          onFinish={async (v) => {
            setBusy(true);
            setError("");
            try {
              await signIn(v.username, v.password, v.code);
              await complete();
            } catch (e) {
              setError(e instanceof Error ? e.message : "登录未完成");
            } finally {
              form.setFieldsValue({ password: "", code: "" });
              setBusy(false);
            }
          }}
        >
          <Form.Item label="账号" name="username" rules={[{ required: true }]}>
            <Input autoComplete="username" maxLength={64} />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true }]}>
            <Input.Password autoComplete="current-password" maxLength={128} />
          </Form.Item>
          <Form.Item
            label="Authenticator 验证码"
            name="code"
            rules={[{ required: true, pattern: /^\d{6}$/ }]}
          >
            <Input
              autoComplete="one-time-code"
              inputMode="numeric"
              maxLength={6}
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={busy}>
            {passkeysEnabled() ? "使用密码和动态码登录" : "登录"}
          </Button>
        </Form>
        {error && <Alert type="error" title={error} />}
      </Card>
    </main>
  );
}
