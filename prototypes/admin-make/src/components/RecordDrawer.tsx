import React, { useEffect } from "react";
import { Button, Drawer } from "antd";
import { useLocation } from "@umijs/max";
import ItemDetail from "../pages/ItemDetail";
import ChipDetail from "../pages/ChipDetail";
import { go } from "../ui";

export default function RecordDrawer({ target, onClose }: { target?: { kind: "items" | "chips"; id: number }; onClose: () => void }) {
  const location = useLocation();
  // 跳往关联对象时关闭当前层，避免在不同对象之间累积抽屉。
  useEffect(() => { onClose(); }, [location.pathname]);
  return <Drawer open={!!target} title={target?.kind === "items" ? "数字物品详情" : "芯片详情"} size={900} onClose={onClose} destroyOnHidden extra={<Button onClick={() => target && go(`/${target.kind}/${target.id}`)}>打开完整详情</Button>}>
    {target?.kind === "items" ? <ItemDetail key={target.id} itemId={target.id} embedded onDeleted={onClose} /> : target && <ChipDetail key={target.id} chipId={target.id} embedded onDeleted={onClose} />}
  </Drawer>;
}
