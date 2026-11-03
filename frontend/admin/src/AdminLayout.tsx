import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Row, Space, Statistic, Typography } from "antd";
import { DashboardOutlined, DatabaseOutlined, LinkOutlined, ShoppingOutlined, LogoutOutlined } from "@ant-design/icons";
import { PageContainer, ProLayout } from "@ant-design/pro-components";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ApiError, listChips, listItems } from "./api";
import { ChipPanel } from "./ChipPanel";
import { ItemPanel } from "./ItemPanel";
import { RuntimeChecks } from "./RuntimeChecks";
import { TapStatisticsPanel } from "./TapStatisticsPanel";
import { NavigationGuard, useNavigationGuard } from "./NavigationGuard";

function Overview({ onSessionExpired }: { onSessionExpired: () => void }) {
  const navigate = useNavigate();
  const [values, setValues] = useState<(number | null | "failed")[]>([null, null, null]);
  const [revision, setRevision] = useState(0);
  const [errors, setErrors] = useState<string[]>([]);
  useEffect(() => {
    let cancelled = false;
    setValues([null, null, null]);
    setErrors([]);
    const base = { page: 1, project: "", status: "", keyword: "" };
    [listChips(base), listChips({ ...base, status: "pending" }), listItems(base)].forEach((promise, index) => {
      promise.then(result => {
        if (!cancelled) setValues(current => current.map((value, i) => i === index ? result.total : value));
      }).catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) onSessionExpired();
        else {
          setValues(current => current.map((value, i) => i === index ? "failed" : value));
          setErrors(current => [...current, error instanceof ApiError ? error.message : "库存概况读取失败，请重试。"]);
        }
      });
    });
    return () => { cancelled = true; };
  }, [revision, onSessionExpired]);
  return <PageContainer title={<Typography.Title level={2} style={{ margin: 0 }}>你好，cece</Typography.Title>} subTitle="查看库存和有效触碰情况，继续处理芯片与物品。"
    extra={<Button onClick={() => setRevision(value => value + 1)}>刷新概况</Button>}>
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {errors.map((error, index) => <Alert key={index} type="error" showIcon message={error} />)}
      <Row gutter={16}>
        {["芯片总数", "待绑定芯片", "数字物品"].map((title, index) => <Col span={8} key={title}>
          <Card><Statistic title={title} value={values[index] === null ? "…" : values[index] === "failed" ? "读取失败" : values[index]!}
            valueRender={node => <output aria-label={title}>{node}</output>} />
            <Typography.Text type="secondary">全局库存，不受触碰筛选影响</Typography.Text></Card>
        </Col>)}
      </Row>
      <Card title="快捷操作"><Space>
        <Button onClick={() => navigate("/chips")}>登记与查询芯片</Button>
        <Button onClick={() => navigate("/items")}>维护物品资料</Button>
        <Button onClick={() => navigate("/checks")}>检查运行环境</Button>
      </Space></Card>
      <div className="legacy-ui"><TapStatisticsPanel onSessionExpired={onSessionExpired} /></div>
      <Alert type="info" showIcon message="物品启用、芯片绑定、写卡完成与真实防伪通过须分别验证。" />
    </Space>
  </PageContainer>;
}

type Props = { expiry: string; busy: boolean; onLogout: () => void; onSessionExpired: () => void; message: string };
function Workspace({ expiry, busy, onLogout, onSessionExpired, message }: Props) {
  const location = useLocation();
  const { attempt } = useNavigationGuard();
  return (
    <ProLayout title="BUMBUM" logo={false} layout="side" fixedHeader fixSiderbar siderWidth={224}
      location={{ pathname: location.pathname }} menuProps={{ selectedKeys: [location.pathname.startsWith("/chips") ? "/chips" : location.pathname.startsWith("/items") ? "/items" : location.pathname === "/checks" ? "/checks" : "/"] }} contentStyle={{ minHeight: "100vh" }}
      route={{ routes: [
        { path: "/", name: "工作台", icon: <DashboardOutlined aria-hidden /> },
        { path: "/chips", name: "芯片管理", icon: <LinkOutlined aria-hidden /> },
        { path: "/items", name: "物品管理", icon: <ShoppingOutlined aria-hidden /> },
        { path: "/checks", name: "系统状态", icon: <DatabaseOutlined aria-hidden /> },
      ] }}
      menuItemRender={(item, dom) => <Link to={item.path || "/"}>{dom}</Link>}
      actionsRender={() => [<Button key="logout" icon={<LogoutOutlined aria-hidden />} disabled={busy} onClick={() => attempt(onLogout)}>退出登录</Button>]}
      menuFooterRender={() => <Typography.Text type="secondary">会话到期：{new Date(expiry).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })}</Typography.Text>}>
      {message && <Alert type="error" showIcon message={message} style={{ marginBottom: 16 }} />}
      <Routes>
        <Route path="/" element={<Overview onSessionExpired={onSessionExpired} />} />
        <Route path="/chips/*" element={<ChipPanel onSessionExpired={onSessionExpired} />} />
        <Route path="/items/*" element={<ItemPanel onSessionExpired={onSessionExpired} />} />
        <Route path="/checks" element={<PageContainer title={<Typography.Title level={2} style={{ margin: 0 }}>系统状态</Typography.Title>} subTitle="检查当前服务连接；业务功能须分别验收。"><RuntimeChecks /></PageContainer>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ProLayout>
  );
}

export function AdminLayout(props: Props) {
  return <NavigationGuard><Workspace {...props} /></NavigationGuard>;
}
