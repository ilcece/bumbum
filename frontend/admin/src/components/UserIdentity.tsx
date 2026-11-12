import { useState } from "react";
import { Alert, Button, Descriptions, Modal, Space, Spin, Typography } from "antd";
import { request } from "../api";

type Account = { public_uid: string; nickname?: string; masked_phone?: string };

export function PhoneReveal({ masked, path }: { masked?: string; path: string }) {
  const [result, setResult] = useState<{ phone?: string; error?: string }>();
  if (!masked) return <>手机号未记录</>;
  function reveal() {
    const pending = {};
    setResult(pending);
    request<{ phone: string }>(path, {}).then(
      ({ phone }) => setResult((current) => current === pending ? { phone } : current),
      (error: Error) => setResult((current) => current === pending ? { error: error.message } : current),
    );
  }
  return <Space wrap>
    <span>{masked}</span>
    <Button type="link" onClick={reveal} disabled={!!result}>查看完整手机号</Button>
    {result && <Modal open title="完整手机号" onCancel={() => setResult(undefined)}
      footer={<Button onClick={() => setResult(undefined)}>关闭</Button>}>
      {result.error ? <Alert type="error" title={result.error} />
        : result.phone ? <Typography.Text>{result.phone}</Typography.Text> : <p>正在读取</p>}
    </Modal>}
  </Space>;
}

export default function UserIdentity({ uid }: { uid?: string }) {
  const [card, setCard] = useState<{ account?: Account; error?: string }>();
  if (!uid) return <>未记录</>;
  const path = `/admin/catalog/users/${encodeURIComponent(uid)}`;
  function open() {
    const pending = {};
    setCard(pending);
    request<Account>(`${path}/card`).then(
      (account) => setCard((current) => current === pending ? { account } : current),
      (error: Error) => setCard((current) => current === pending ? { error: error.message } : current),
    );
  }
  return <>
    <Button type="link" onClick={open} style={{ paddingInline: 0 }}>{uid}</Button>
    {card && <Modal open title="账户资料" onCancel={() => setCard(undefined)}
      footer={<Button onClick={() => setCard(undefined)}>关闭</Button>}>
      {card.error ? <Alert type="error" title={card.error} /> : card.account ? (
        <Descriptions column={1}>
          <Descriptions.Item label="账户 UID"><Typography.Text copyable>{card.account.public_uid}</Typography.Text></Descriptions.Item>
          <Descriptions.Item label="昵称">{card.account.nickname || "未设置"}</Descriptions.Item>
          <Descriptions.Item label="手机号"><PhoneReveal masked={card.account.masked_phone} path={`${path}/phone`} /></Descriptions.Item>
        </Descriptions>
      ) : <Spin />}
    </Modal>}
  </>;
}
