import ClaimCodeDialog from "./ClaimCodeDialog";
import { useEffect, useState } from "react";
import { Button, Space, Typography } from "antd";
import { request } from "../api";
import { time } from "../catalog";

type CodeStatus = {
  id: number;
  expires_at: string;
  consumed_at?: string | null;
  revoked_at?: string | null;
};

export default function ClaimCodeStatus({ itemId, status }: { itemId: number; status: CodeStatus }) {
  const [result, setResult] = useState<{ claim_code?: string; error?: string }>();
  const [expired, setExpired] = useState(false);
  const expiry = Date.parse(status.expires_at);
  const usable = !status.consumed_at && !status.revoked_at && !expired && expiry > Date.now();

  useEffect(() => {
    if (status.consumed_at || status.revoked_at) return;
    let timer: ReturnType<typeof setTimeout>;
    function checkExpiry() {
      const remaining = expiry - Date.now();
      if (remaining <= 0) {
        setExpired(true);
        setResult(undefined);
      } else {
        timer = setTimeout(checkExpiry, Math.min(remaining, 2_147_483_647));
      }
    }
    checkExpiry();
    return () => clearTimeout(timer);
  }, [expiry, status.consumed_at, status.revoked_at]);

  function reveal() {
    const pending = {};
    setResult(pending);
    request<{ claim_code: string }>(`/admin/catalog/items/${itemId}/claim-codes/${status.id}/reveal`, {})
      .then((code) => setResult((current) => current === pending ? code : current),
        (error: Error) => setResult((current) => current === pending ? { error: error.message } : current));
  }

  return <Space wrap>
    <Typography.Text type="secondary">{status.consumed_at ? "已核销" : status.revoked_at ? "已撤销" :
      usable ? "有效至 " + time(status.expires_at) : "已过期"}</Typography.Text>
    {usable && <Button type="link" onClick={reveal} disabled={!!result}>查看认领码</Button>}
    {usable && result && <ClaimCodeDialog code={result.claim_code} expiresAt={status.expires_at}
      error={result.error} loading={!result.error && !result.claim_code} onClose={() => setResult(undefined)} />}
  </Space>;
}
