import React from "react";
import { App, Button, Dropdown, Tag } from "antd";
import { useStore } from "../data/store";
export default function PrototypeToolbar() {
  const p = useStore(),
    { modal } = App.useApp();
  return (
    <Dropdown
      menu={{
        items: [
          { key: "none", label: "恢复正常演示" },
          { key: "save", label: "模拟保存失败" },
          { key: "unknown", label: "模拟保存结果未知" },
          { key: "read", label: "模拟读取失败" },
          { key: "reset", label: "重置合成样例", danger: true },
        ],
        onClick: ({ key }) => {
          if (key === "reset")
            modal.confirm({
              title: "重置本原型合成样例？",
              content: "只重置新版v6演示；旧v5会话不修改，真实系统不受影响。",
              onOk: p.reset,
            });
          else if (key === "read") p.setReadError(true);
          else {
            p.setFailure(key as any);
            p.setReadError(false);
          }
        },
      }}
    >
      <Button type="text">
        <Tag color="purple">原型演示</Tag>样例数据
      </Button>
    </Dropdown>
  );
}
