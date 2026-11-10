import { useEffect, useState } from "react";
import { Alert, Button, Empty, Spin, Timeline } from "antd";
import { list, Row, time } from "../catalog";
import UserIdentity from "./UserIdentity";

export const activityLabels: Record<string, string> = {
  tap: "有效触碰",
  claim: "认领物品",
  renewal: "换新交付生效",
  resale: "转售交付生效",
};

export default function ItemActivity({ itemId, revision }: { itemId: number; revision: unknown }) {
  const [rows, setRows] = useState<Row[]>();
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let current = true;
    setRows(undefined);
    setError("");
    list("activity", { item_id: itemId, page_size: 10 }).then(
      (result) => { if (current) setRows(result.items); },
      (failure: Error) => { if (current) setError(failure.message); },
    );
    return () => { current = false; };
  }, [itemId, revision, retry]);
  if (error) return <Alert type="error" title={error} action={<Button onClick={() => setRetry(retry + 1)}>重试</Button>} />;
  if (!rows) return <Spin />;
  if (!rows.length) return <Empty description="暂无用户动态" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  return <Timeline items={rows.map((row) => ({
    key: row.id, content: <>{time(row.occurred_at)} · {activityLabels[row.event]} · {row.user_uid ? <UserIdentity uid={row.user_uid} /> : "匿名访客"}</>,
  }))} />;
}
