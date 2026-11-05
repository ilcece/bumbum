// 基于官方Ant Design Pro运行时，保留布局/初始状态/路由组织，移除示例认证与外部API。
import React from "react";
import { App, ConfigProvider, Alert, Button, Space } from "antd";
import zhCN from "antd/locale/zh_CN";
import { history, Link, RequestConfig, RunTimeLayoutConfig } from "@umijs/max";
import { PrototypeProvider, useStore } from "./data/store";
import PrototypeToolbar from "./components/PrototypeToolbar";
import settings from "../config/defaultSettings";
import "./global.css";
export async function getInitialState() {
  return {
    currentUser:
      sessionStorage.getItem("bumbum-pro-demo-auth") === "yes"
        ? { name: "演示管理员" }
        : undefined,
    settings,
  };
}
function Notice() {
  const p = useStore();
  return (
    <>
      {p.storageError && <Alert type="warning" title={p.storageError} />}{" "}
      {p.data.importNote && <Alert type="info" title={p.data.importNote} />}
    </>
  );
}
export const layout: RunTimeLayoutConfig = ({
  initialState,
  setInitialState,
}) => ({
  ...settings,
  logo: <span className="brand-mark">BB</span>,
  menuItemRender: (item, dom) =>
    item.path ? <Link to={item.path}>{dom}</Link> : dom,
  avatarProps: {
    title: initialState?.currentUser?.name || "演示管理员",
    render: () => (
      <Space>
        <span>演示管理员</span>
        <Button
          type="text"
          onClick={() => {
            history.push("/login");
          }}
        >
          退出演示
        </Button>
      </Space>
    ),
  },
  actionsRender: () => [<PrototypeToolbar key="demo" />],
  footerRender: false,
  onPageChange: () => {
    if (!initialState?.currentUser && history.location.pathname !== "/login")
      history.replace("/login");
  },
  childrenRender: (children) => (
    <>
      <Notice />
      {children}
    </>
  ),
});
export const request: RequestConfig = {};
export function rootContainer(container: React.ReactNode) {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#1677ff",
          borderRadius: 8,
          fontFamily:
            '-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif',
        },
      }}
    >
      <App>
        <PrototypeProvider>{container}</PrototypeProvider>
      </App>
    </ConfigProvider>
  );
}
