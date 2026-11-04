import { useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Layout,
  Menu,
  Row,
  Space,
  Statistic,
  Tag,
  Typography,
} from "antd";
import {
  DashboardOutlined,
  DatabaseOutlined,
  LinkOutlined,
  ShoppingOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import { PageHeading } from "./MakeSurfaces";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { ApiError, listChips, listItems } from "./api";
import { ChipPanel } from "./ChipPanel";
import { ItemPanel } from "./ItemPanel";
import { RuntimeChecks } from "./RuntimeChecks";
import { TapStatisticsPanel } from "./TapStatisticsPanel";
import { NavigationGuard, useNavigationGuard } from "./NavigationGuard";

function Overview({ onSessionExpired }: { onSessionExpired: () => void }) {
  const navigate = useNavigate();
  const [values, setValues] = useState<(number | null | "failed")[]>([
    null,
    null,
    null,
  ]);
  const [revision, setRevision] = useState(0);
  const [errors, setErrors] = useState<string[]>([]);
  useEffect(() => {
    let cancelled = false;
    setValues([null, null, null]);
    setErrors([]);
    const base = { page: 1, project: "", status: "", keyword: "" };
    [
      listChips(base),
      listChips({ ...base, status: "pending" }),
      listItems(base),
    ].forEach((promise, index) => {
      promise
        .then((result) => {
          if (!cancelled)
            setValues((current) =>
              current.map((value, i) => (i === index ? result.total : value)),
            );
        })
        .catch((error: unknown) => {
          if (cancelled) return;
          if (error instanceof ApiError && error.status === 401)
            onSessionExpired();
          else {
            setValues((current) =>
              current.map((value, i) => (i === index ? "failed" : value)),
            );
            setErrors((current) => [
              ...current,
              error instanceof ApiError
                ? error.message
                : "库存概况读取失败，请重试。",
            ]);
          }
        });
    });
    return () => {
      cancelled = true;
    };
  }, [revision, onSessionExpired]);
  return (
    <div className="make-stack">
      <PageHeading
        title="工作台"
        subtitle="查看库存和有效触碰情况，继续处理芯片与物品。"
        extra={
          <Button onClick={() => setRevision((value) => value + 1)}>
            刷新概况
          </Button>
        }
      />
      <Space orientation="vertical" size="large" style={{ width: "100%" }}>
        {errors.map((error, index) => (
          <Alert key={index} type="error" showIcon title={error} />
        ))}
        <Row gutter={16}>
          {["芯片总数", "待绑定芯片", "数字物品"].map((title, index) => (
            <Col span={8} key={title}>
              <Card>
                <Statistic
                  title={title}
                  value={
                    values[index] === null
                      ? "…"
                      : values[index] === "failed"
                        ? "读取失败"
                        : values[index]!
                  }
                  valueRender={(node) => (
                    <output aria-label={title}>{node}</output>
                  )}
                />
                <Typography.Text type="secondary">
                  全局库存，不受触碰筛选影响
                </Typography.Text>
              </Card>
            </Col>
          ))}
        </Row>
        <Card title="快捷操作">
          <Space>
            <Button onClick={() => navigate("/chips")}>登记与查询芯片</Button>
            <Button onClick={() => navigate("/items")}>维护物品资料</Button>
            <Button onClick={() => navigate("/checks")}>检查运行环境</Button>
          </Space>
        </Card>
        <TapStatisticsPanel onSessionExpired={onSessionExpired} />
        <Alert
          type="info"
          showIcon
          title="物品启用、芯片绑定、写卡完成与真实防伪通过须分别验证。"
        />
      </Space>
    </div>
  );
}

type Props = {
  expiry: string;
  busy: boolean;
  onLogout: () => void;
  onSessionExpired: () => void;
  message: string;
};
function Workspace({
  expiry,
  busy,
  onLogout,
  onSessionExpired,
  message,
}: Props) {
  const location = useLocation();
  const { attempt } = useNavigationGuard();
  const active = location.pathname.startsWith("/chips")
    ? "/chips"
    : location.pathname.startsWith("/items")
      ? "/items"
      : location.pathname === "/checks"
        ? "/checks"
        : "/";
  const titles: Record<string, string> = {
    "/": "工作台总览与有效触碰统计",
    "/chips": "芯片管理",
    "/items": "数字物品管理",
    "/checks": "服务与数据库诊断",
  };
  return (
    <Layout className="make-shell">
      <Layout.Sider
        width={248}
        theme="light"
        style={{
          borderRight: "1px solid #e2e8f0",
          position: "sticky",
          top: 0,
          height: "100vh",
          flexShrink: 0,
        }}
      >
        <div
          style={{ display: "flex", flexDirection: "column", height: "100%" }}
        >
          <div className="make-brand">
            <Space size={10}>
              <div className="w-8 h-8 rounded-lg bg-blue-600 text-white font-bold flex items-center justify-center shadow-sm">
                BB
              </div>
              <div>
                <div className="font-bold text-slate-900 text-sm">
                  BUMBUM 管理后台
                </div>
                <div className="text-[11px] text-slate-500">
                  NFC 防伪配卡与数字物品中心
                </div>
              </div>
            </Space>
          </div>
          <div style={{ flex: 1, paddingTop: 12 }}>
            <div className="px-4 py-1.5 text-[11px] font-semibold text-slate-400">
              核心业务管理
            </div>
            <Menu
              mode="inline"
              selectedKeys={[active]}
              style={{ borderInlineEnd: 0 }}
              items={[
                {
                  key: "/",
                  icon: <DashboardOutlined aria-hidden />,
                  label: <Link to="/">工作台</Link>,
                },
                {
                  key: "/chips",
                  icon: <LinkOutlined aria-hidden />,
                  label: <Link to="/chips">芯片管理</Link>,
                },
                {
                  key: "/items",
                  icon: <ShoppingOutlined aria-hidden />,
                  label: <Link to="/items">物品管理</Link>,
                },
                {
                  key: "/checks",
                  icon: <DatabaseOutlined aria-hidden />,
                  label: <Link to="/checks">系统状态</Link>,
                },
              ]}
            />
          </div>
          <div className="make-footer">
            <Space size={6}>
              <Badge status="success" />
              <Typography.Text type="secondary">管理员会话</Typography.Text>
            </Space>
            <div className="make-secondary" style={{ marginTop: 8 }}>
              会话到期：
              {new Date(expiry).toLocaleString("zh-CN", {
                timeZone: "Asia/Shanghai",
                hour12: false,
              })}
            </div>
          </div>
        </div>
      </Layout.Sider>
      <Layout>
        <Layout.Header className="make-header">
          <div>
            <span className="font-semibold text-slate-900 text-base">
              {titles[active]}
            </span>
            <span className="make-header-subtitle text-xs text-slate-400 ml-3">
              库存、资料与实卡配置
            </span>
          </div>
          <Space>
            <Tag color="blue">服装 & 饰品</Tag>
            <Button
              size="small"
              icon={<LogoutOutlined aria-hidden />}
              disabled={busy}
              onClick={() => attempt(onLogout)}
            >
              退出登录
            </Button>
          </Space>
        </Layout.Header>
        <Layout.Content className="make-main">
          <div className="make-content">
            {message && (
              <Alert
                type="error"
                showIcon
                title={message}
                style={{ marginBottom: 16 }}
              />
            )}
            <Routes>
              <Route
                path="/"
                element={<Overview onSessionExpired={onSessionExpired} />}
              />
              <Route
                path="/chips/*"
                element={<ChipPanel onSessionExpired={onSessionExpired} />}
              />
              <Route
                path="/items/*"
                element={<ItemPanel onSessionExpired={onSessionExpired} />}
              />
              <Route
                path="/checks"
                element={
                  <div className="make-stack">
                    <PageHeading title="系统状态" subtitle="检查当前服务连接" />
                    <RuntimeChecks />
                  </div>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </Layout.Content>
      </Layout>
    </Layout>
  );
}

export function AdminLayout(props: Props) {
  return (
    <NavigationGuard>
      <Workspace {...props} />
    </NavigationGuard>
  );
}
