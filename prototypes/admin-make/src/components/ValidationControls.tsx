import React from "react";
import { Button, Space, Switch, Typography } from "antd";
import { useAction } from "../ui";

export default function ValidationControls({ kind, id, checked, onDeleted }: { kind: "items" | "chips"; id: number; checked?: boolean; onDeleted: () => void }) {
  const a = useAction(), name = kind === "items" ? "物品" : "芯片";
  const target = kind === "items" ? { itemId: id } : { chipId: id };
  return <div className="page-stack" style={{ gap: 8 }}><Space wrap>
    <Typography.Text>生产验证对象</Typography.Text>
    <Switch aria-label={name + "生产验证对象"} checked={!!checked} checkedChildren="是" unCheckedChildren="否" disabled={a.unknown} onChange={enabled => a.run("validation", { kind, ...target, enabled }, enabled ? "已标记为生产验证对象" : "已关闭生产验证标记")} />
    {checked && <Button danger disabled={a.unknown} onClick={() => { if (a.run("deleteValidation", { kind, ...target }, "生产验证对象已删除，另一侧档案保留")) onDeleted(); }}>直接删除验证{name}</Button>}
  </Space>
    {checked && <Typography.Text type="secondary">可直接删除，不受业务状态限制。清理本对象的触碰、接续与关联，另一侧档案及审计保留。</Typography.Text>}
    {a.feedback}
  </div>;
}
