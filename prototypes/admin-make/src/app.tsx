// 基于官方Ant Design Pro运行时，保留布局/初始状态/路由组织，移除示例认证与外部API。
import React from "react";
import {
  App,
  ConfigProvider,
  Alert,
  Avatar,
  Badge,
  Button,
  Space,
  Tag,
  Typography,
} from "antd";
import zhCN from "antd/locale/zh_CN";
import {
  history,
  Link,
  RequestConfig,
  RunTimeLayoutConfig,
  useLocation,
} from "@umijs/max";
import { PrototypeProvider, useStore } from "./data/store";
import PrototypeToolbar from "./components/PrototypeToolbar";
import settings from "../config/defaultSettings";
import { LogoutOutlined, UserOutlined } from "@ant-design/icons";
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
function HeaderContext() {
  const { pathname } = useLocation();
  const names: Record<string, string> = {
    overview: "工作台",
    catalog: "款式与发行",
    items: "数字物品",
    chips: "芯片管理",
    system: "系统管理",
  };
  return (
    <div className="header-context">
      <Typography.Text strong>
        {names[pathname.split("/")[1]] || "管理工作区"}
      </Typography.Text>
      <Typography.Text type="secondary">数字物品与芯片管理</Typography.Text>
    </div>
  );
}
function MenuLabel({ path, label }: { path?: string; label: React.ReactNode }) {
  const { data } = useStore();
  const counts: Record<string, number> = {
    "/items": data.items.length,
    "/chips": data.chips.length,
  };
  return (
    <span className="menu-label">
      <span>{label}</span>
      {path && counts[path] != null && (
        <Tag aria-hidden="true" className="menu-count">
          {counts[path]}
        </Tag>
      )}
    </span>
  );
}
export const layout: RunTimeLayoutConfig = ({ initialState }) => ({
  ...settings,
  logo: <span className="brand-mark">BB</span>,
  headerTitleRender: () => (
    <div className="brand-lockup">
      <span className="brand-mark">BB</span>
      <div>
        <strong>BUMBUM 管理后台</strong>
        <small>数字物品档案与芯片关联</small>
      </div>
    </div>
  ),
  headerContentRender: () => <HeaderContext />,
  menuTextRender: (item, dom) => <MenuLabel path={item.path} label={dom} />,
  menuFooterRender: ({ collapsed }: any) =>
    collapsed ? null : (
      <div className="sider-caption">
        <Badge status="processing" />
        交互原型 · 合成数据
      </div>
    ),
  menuItemRender: (item, dom) =>
    item.path ? <Link to={item.path}>{dom}</Link> : dom,
  avatarProps: {
    title: initialState?.currentUser?.name || "演示管理员",
    render: () => (
      <Space className="admin-profile" size={8}>
        <Avatar size={24} icon={<UserOutlined aria-hidden />} />
        <span>演示管理员</span>
        <Badge status="default" text="演示会话" />
        <Button
          type="text"
          size="small"
          icon={<LogoutOutlined aria-hidden />}
          onClick={() => history.push("/login")}
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
          colorBorderSecondary: "#e2e8f0",
          colorBgLayout: "#f5f7fa",
          fontSize: 13,
          controlHeight: 32,
          fontFamily:
            'Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif',
        },
        components: {
          Card: { headerHeight: 42, headerFontSize: 14, paddingLG: 20 },
          Table: {
            headerBg: "#f8fafc",
            headerColor: "#334155",
            rowHoverBg: "#f8fbff",
            cellPaddingBlock: 12,
            cellPaddingInline: 12,
            fontSize: 13,
          },
          Form: {
            labelColor: "#475569",
            labelFontSize: 12,
            itemMarginBottom: 18,
            verticalLabelPadding: "0 0 6px",
          },
          Statistic: { titleFontSize: 12, contentFontSize: 26 },
          Descriptions: {
            labelBg: "#f8fafc",
            labelColor: "#64748b",
            contentColor: "#0f172a",
          },
          Tabs: { horizontalMargin: "0 0 16px 0", titleFontSize: 13 },
        },
      }}
      modal={{
        styles: {
          body: {
            maxHeight: "calc(100dvh - 240px)",
            overflowY: "auto",
            overscrollBehavior: "contain",
          },
        },
      }}
    >
      <App>
        <PrototypeProvider>{container}</PrototypeProvider>
      </App>
    </ConfigProvider>
  );
}
