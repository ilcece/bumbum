import ReadFailure from "./ReadFailure";
import { useEffect, useState } from "react";
import { Empty, Spin, Timeline } from "antd";
import { history, useLocation } from "@umijs/max";
import { list, Row, time } from "../catalog";
import { Copy } from "./CatalogUI";
import UserIdentity from "./UserIdentity";

export const activityLabels: Record<string, string> = {
  tap: "有效触碰",
  claim: "认领物品",
  first_delivery: "首次交付",
  renewal: "换新交付生效",
  resale: "转售交付生效",
};

export function ActivityItem({ row, currentItem }: { row: Row; currentItem?: number }) {
  const location = useLocation();
  return <Copy value={row.item_uid} onClick={() => {
    if (row.item_id === currentItem) {
      const heading = document.getElementById("item-detail-heading");
      heading?.scrollIntoView({ block: "start" });
      heading?.focus({ preventScroll: true });
    } else {
      history.push(`/items/${row.item_id}?from=${encodeURIComponent(location.pathname + location.search)}`);
    }
  }} />;
}

export function ActivityActor({ row }: { row: Row }) {
  if (row.user_uid) return <UserIdentity uid={row.user_uid} />;
  if (row.event !== "tap") return <>管理员确认</>;
  return <>{row.actor_state === "anonymous" ? "匿名访客" : "身份未记录"}</>;
}

export default function ItemActivity({ itemId, revision }: { itemId?: number; revision?: unknown }) {
  const [rows, setRows] = useState<Row[]>();
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let current = true;
    setRows(undefined);
    setError("");
    list("activity", { item_id: itemId, page_size: itemId ? 10 : 5 }).then(
      (result) => { if (current) setRows(result.items); },
      (failure: Error) => { if (current) setError(failure.message); },
    );
    return () => { current = false; };
  }, [itemId, revision, retry]);
  if (error) return <ReadFailure title="用户动态读取失败" error={error} retry={() => setRetry((value) => value + 1)} />;
  if (!rows) return <Spin />;
  if (!rows.length) return <Empty description="暂无用户动态" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  return <Timeline items={rows.map((row) => ({
    key: row.id, content: <>{time(row.occurred_at)} · {activityLabels[row.event]} · <ActivityItem row={row} currentItem={itemId} /> · <ActivityActor row={row} /></>,
  }))} />;
}
