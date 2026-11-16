import { type ComponentRef, type KeyboardEvent, useRef, useState } from "react";
import { Alert, Button, Descriptions, Modal, Popover, Space, Spin, Tooltip, Typography } from "antd";
import { CloseOutlined, EyeOutlined } from "@ant-design/icons";
import { request } from "../api";

type Account = { public_uid: string; nickname?: string; masked_phone?: string };

export function PhoneReveal({ masked, path, onOpenChange }: {
  masked?: string; path: string; onOpenChange?: (open: boolean) => void;
}) {
  const [result, setResult] = useState<{ phone?: string; error?: string }>();
  if (!masked) return <>手机号未记录</>;
  function reveal() {
    const pending = {};
    setResult(pending);
    onOpenChange?.(true);
    request<{ phone: string }>(path, {}).then(
      ({ phone }) => setResult((current) => current === pending ? { phone } : current),
      (error: Error) => setResult((current) => current === pending ? { error: error.message } : current),
    );
  }
  function close() {
    setResult(undefined);
    onOpenChange?.(false);
  }
  return <Space size={4} align="center">
    <span>{masked}</span>
    <Tooltip title="查看完整手机号">
      <Button type="text" size="small" icon={<EyeOutlined />} aria-label="查看完整手机号"
        onClick={reveal} disabled={!!result} />
    </Tooltip>
    {result && <Modal open title="完整手机号" onCancel={close}
      footer={<Button onClick={close}>关闭</Button>}>
      {result.error ? <Alert type="error" title={result.error} />
        : result.phone ? <Typography.Text data-private="true">{result.phone}</Typography.Text> : <p>正在读取</p>}
    </Modal>}
  </Space>;
}

export default function UserIdentity({ uid }: { uid?: string }) {
  const [card, setCard] = useState<{ account?: Account; error?: string }>();
  const trigger = useRef<ComponentRef<typeof Button>>(null);
  const closeButton = useRef<ComponentRef<typeof Button>>(null);
  const viewingPhone = useRef(false);
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
  function close() {
    setCard(undefined);
    trigger.current?.focus({ preventScroll: true });
  }
  function escape(event: KeyboardEvent<HTMLElement>) {
    if (card && event.key === "Escape" && !viewingPhone.current &&
        event.currentTarget.contains(event.target as Node)) {
      event.stopPropagation();
      close();
    }
  }
  return <Popover trigger="click" placement="bottomLeft" open={!!card}
    onOpenChange={(next) => {
      if (next && !card) open();
      else if (!next && !viewingPhone.current) setCard(undefined);
    }}
    afterOpenChange={(visible) => {
      if (visible && !viewingPhone.current) closeButton.current?.focus({ preventScroll: true });
    }}
    content={<div className="account-summary" role="region" aria-label="账户资料"
      onKeyDown={escape}>
      <div className="account-summary-heading">
        <Typography.Text strong>账户资料</Typography.Text>
        <Button ref={closeButton} type="text" size="small" icon={<CloseOutlined />} aria-label="关闭账户资料" onClick={close} />
      </div>
      {card?.error ? <Alert type="error" title={card.error} /> : card?.account ? (
        <Descriptions column={1} size="small" styles={{ label: { width: 72, flexShrink: 0 }, content: { minWidth: 0, overflowWrap: "anywhere" } }}>
          <Descriptions.Item label="账户 UID"><Typography.Text copyable>{card.account.public_uid}</Typography.Text></Descriptions.Item>
          <Descriptions.Item label="昵称">{card.account.nickname || "未设置"}</Descriptions.Item>
          <Descriptions.Item label="手机号">
            <PhoneReveal masked={card.account.masked_phone} path={path + "/phone"}
              onOpenChange={(next) => { viewingPhone.current = next; }} />
          </Descriptions.Item>
        </Descriptions>
      ) : <Spin />}
    </div>}>
    <Button ref={trigger} type="link" aria-expanded={!!card} onKeyDown={escape} style={{ paddingInline: 0 }}>{uid}</Button>
  </Popover>;
}
