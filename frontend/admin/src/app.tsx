import React from "react";
import { App, ConfigProvider, Button, Space, Typography } from "antd";
import zhCN from "antd/locale/zh_CN";
import { history, Link, RunTimeLayoutConfig } from "@umijs/max";
import settings from "../config/defaultSettings";
import { ApiError, readSession, signOut } from "./api";
import "./global.css";
export async function getInitialState() {
  try {
    return { session: await readSession() };
  } catch (e) {
    if (e instanceof ApiError && e.status === 401)
      return { session: undefined };
    return {
      session: undefined,
      sessionError: e instanceof Error ? e.message : "读取会话失败",
    };
  }
}
function Account() {
  const { message } = App.useApp();
  return (
    <Space>
      <Typography.Text>管理会话</Typography.Text>
      <Button
        type="text"
        onClick={async () => {
          try {
            await signOut();
            if (window.location.pathname !== "/login")
              window.location.replace("/login");
          } catch (e) {
            message.error(
              e instanceof Error ? e.message : "退出失败，请核对登录状态。",
            );
          }
        }}
      >
        退出登录
      </Button>
    </Space>
  );
}
export const layout: RunTimeLayoutConfig = ({ initialState }) => ({
  ...settings,
  headerTitleRender: () => (
    <div className="brand-lockup">
      <span className="brand-mark">BB</span>
      <div>
        <strong>BUMBUM 管理后台</strong>
        <small>数字物品档案与芯片关联</small>
      </div>
    </div>
  ),
  menuItemRender: (item, dom) =>
    item.path ? <Link to={item.path}>{dom}</Link> : dom,
  avatarProps: { render: () => <Account /> },
  footerRender: false,
  onPageChange: () => {
    if (!initialState?.session && history.location.pathname != "/login")
      if (window.location.pathname !== "/login")
        window.location.replace("/login");
  },
});
export function rootContainer(container: React.ReactNode) {
  return (
    <ConfigProvider
      locale={zhCN}
      getPopupContainer={(trigger) =>
        trigger?.closest<HTMLElement>(".ant-modal-content") || document.body
      }
      theme={{
        token: {
          colorPrimary: "#1677ff",
          borderRadius: 8,
          colorText: "#0f172a",
          colorTextSecondary: "#64748b",
          colorBorder: "#dbe1e8",
          colorBgLayout: "#f5f7fa",
          fontSize: 14,
          controlHeight: 32,
        },
        components: {
          Table: { headerBg: "#f8fafc", cellPaddingBlock: 12 },
          Descriptions: { labelBg: "#f8fafc" },
          Form: { labelFontSize: 12 },
        },
      }}
      modal={{
        styles: {
          body: { maxHeight: "calc(100dvh - 240px)", overflowY: "auto" },
        },
      }}
    >
      <App>
        <SessionBoundary />
        {container}
      </App>
    </ConfigProvider>
  );
}
function SessionBoundary() {
  React.useEffect(() => {
    const expired = () => {
      if (window.location.pathname !== "/login")
        window.location.replace("/login");
    };
    window.addEventListener("admin-session-expired", expired);
    return () => window.removeEventListener("admin-session-expired", expired);
  }, []);
  return null;
}
