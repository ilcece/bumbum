import React from "react";
import {
  App,
  ConfigProvider,
  Button,
  Space,
  Typography,
  Avatar,
  Badge,
  Tag,
  Tooltip,
} from "antd";
import zhCN from "antd/locale/zh_CN";
import { history, Link, RunTimeLayoutConfig, useLocation } from "@umijs/max";
import { UserOutlined, LogoutOutlined } from "@ant-design/icons";
import { list } from "./catalog";
import { testBatch } from "./testDataMode";
import settings from "../config/defaultSettings";
import routes from "../config/routes";
import brandSymbol from "../../shared/brand/bumbum-symbol-black.svg";
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
    <Space className="admin-profile" size={8}>
      <Avatar size={24} icon={<UserOutlined aria-hidden />} />
      <span>管理员</span>
      <Button
        type="text"
        size="small"
        icon={<LogoutOutlined aria-hidden />}
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
function HeaderContext() {
  const { pathname } = useLocation();
  const sectionPath = "/" + pathname.split("/")[1];
  const section = routes.find((route) => route.path === sectionPath)?.name;
  return (
    <div className="header-context">
      <Typography.Text strong>
        {section || "管理工作区"}
      </Typography.Text>
      <Typography.Text type="secondary">数字物品与芯片管理</Typography.Text>
    </div>
  );
}
function MenuLabel({ path, label }: { path?: string; label: React.ReactNode }) {
  const { pathname } = useLocation();
  const [count, setCount] = React.useState<number>();
  React.useEffect(() => {
    let live = true;
    if (path === "/items" || path === "/chips")
      list(path === "/items" ? "items" : "chips", { page_size: 1 })
        .then((r) => {
          if (live) setCount(r.total);
        })
        .catch(() => {
          if (live) setCount(undefined);
        });
    return () => {
      live = false;
    };
  }, [path, pathname]);
  return (
    <span className="menu-label">
      <span>{label}</span>
      {count != null && (
        <Tag aria-hidden="true" className="menu-count">
          {count}
        </Tag>
      )}
    </span>
  );
}
export const layout: RunTimeLayoutConfig = ({ initialState }) => ({
  ...settings,
  headerTitleRender: () => (
    <div className="brand-lockup">
      <img className="brand-symbol" src={brandSymbol} alt="" width={32} style={{ height: "auto" }} />
      <div>
        <strong>BUMBUM 管理后台</strong>
        <small>数字物品档案与芯片关联</small>
      </div>
    </div>
  ),
  menuDataRender: (menu) => {
    const digital = menu.find((item) => item.path === "/items");
    const physical = menu.find((item) => item.path === "/physical-items");
    if (!digital || !physical) return menu;
    return menu.flatMap((item) => {
      if (item === physical) return [];
      return item === digital ? [{
        key: "item-management", name: "数字物品管理", icon: digital.icon,
        children: [{ ...digital, icon: undefined }, physical],
      }] : [item];
    });
  },
  menuItemRender: (item, dom) =>
    item.path ? <Link to={item.path}>{dom}</Link> : dom,
  headerContentRender: () => <HeaderContext />,
  menuTextRender: (item, dom) => <MenuLabel path={item.path} label={dom} />,
  menuFooterRender: ({ collapsed }: any) =>
    collapsed ? null : (
      <Tooltip trigger={["hover", "focus"]} title="仅控制验收测试批次的显示范围，与 test／生产环境无关。关闭时显示未归入验收批次的数据；在系统管理的设置中切换。">
        <div className="sider-caption" tabIndex={0}>
          <Badge status={testBatch() ? "warning" : "default"}
            text={testBatch() ? "验收测试数据：已开启" : "验收测试数据：关闭"} />
        </div>
      </Tooltip>
    ),
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
          colorPrimary: settings.colorPrimary,
          borderRadius: 8,
          colorText: "#0f172a",
          colorTextSecondary: "#64748b",
          colorBorder: "#dbe1e8",
          colorBorderSecondary: "#e2e8f0",
          colorBgLayout: "#f5f7fa",
          fontSize: 14,
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
            fontSize: 14,
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
