import { useEffect, useState } from "react";
import { Alert, Button, List, Popconfirm, Space, Typography } from "antd";
import { history } from "@umijs/max";
import { time } from "../catalog";
import { listPasskeys, passkeyMessage, revokePasskey, usePasskey } from "../passkeys";

export default function AdminPasskeys() {
  const [items, setItems] = useState<Awaited<ReturnType<typeof listPasskeys>>["items"]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const reload = () => listPasskeys().then(({ items }) => setItems(items));
  useEffect(() => { void reload().catch((failure) => setError(passkeyMessage(failure))); }, []);

  async function act(id?: number) {
    setBusy(true);
    setError("");
    try {
      if (id === undefined) {
        await usePasskey("register");
        await reload();
      } else {
        await revokePasskey(id);
        history.replace("/login");
      }
    } catch (failure) {
      setError(passkeyMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return <Space orientation="vertical" style={{ width: "100%" }}>
    <Typography.Paragraph>用现有方式登录后 10 分钟内登记或撤销。登记时在 Edge 的提示中选择 Windows Hello。原动态码登录可继续使用。</Typography.Paragraph>
    <Button type="primary" loading={busy} onClick={() => void act()}>登记通行密钥</Button>
    {error && <Alert type="error" title={error} />}
    <List dataSource={items} locale={{ emptyText: "暂无通行密钥" }} renderItem={(item) => (
      <List.Item actions={[<Popconfirm key="revoke" title="撤销后会退出当前账户的所有管理会话" okText="确认撤销" onConfirm={() => act(item.id)}>
        <Button danger type="link" disabled={busy}>撤销</Button>
      </Popconfirm>]}>
        <List.Item.Meta title={`登记于 ${time(item.created_at)}`} description={`最近使用 ${time(item.last_used_at)}`} />
      </List.Item>
    )} />
  </Space>;
}
