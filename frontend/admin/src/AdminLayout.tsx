import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bell,
  Box,
  Database,
  Home,
  Link2,
  LogOut,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { ApiError, listChips, listItems } from "./api";
import { ChipPanel } from "./ChipPanel";
import { ItemPanel } from "./ItemPanel";
import {
  PageHeading,
  UnavailableButton,
  UnavailableContext,
  Notice,
} from "./AdminUI";
import { RuntimeChecks } from "./RuntimeChecks";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./components/ui/dialog";

type Page = "overview" | "chips" | "items" | "owners" | "checks";
const NAV = [
  { id: "overview", label: "工作台", icon: Home },
  { id: "chips", label: "芯片管理", icon: Link2 },
  { id: "items", label: "物品管理", icon: Box },
  { id: "owners", label: "所有权", icon: Users },
] as const;
function Overview({
  onSessionExpired,
  navigate,
}: {
  onSessionExpired: () => void;
  navigate: (page: Page) => void;
}) {
  const [values, setValues] = useState<(number | null | "failed")[]>([
    null,
    null,
    null,
  ]);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setValues([null, null, null]);
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
          else
            setValues((current) =>
              current.map((value, i) => (i === index ? "failed" : value)),
            );
        });
    });
    return () => {
      cancelled = true;
    };
  }, [onSessionExpired, revision]);
  const metrics = [
    { label: "芯片总数", icon: Link2 },
    { label: "待绑定芯片", icon: ShieldCheck },
    { label: "数字物品", icon: Box },
    { label: "有效所有权", icon: Users },
  ];
  return (
    <>
      <PageHeading
        title="你好，cece"
        subtitle="查看真实库存数量，继续处理芯片与物品。"
        action={
          <button className="action" onClick={() => setRevision((v) => v + 1)}>
            刷新概况
          </button>
        }
      />
      <section className="metrics">
        {metrics.map(({ label, icon: Icon }, i) => (
          <article key={label} className="metric-card">
            <div className="metric-top">
              <span>{label}</span>
              <span className="metric-icon">
                <Icon size={18} />
              </span>
            </div>
            <div className="metric-bottom">
              <strong>
                {i === 3
                  ? "—"
                  : values[i] === null
                    ? "…"
                    : values[i] === "failed"
                      ? "读取失败"
                      : values[i]}
              </strong>
              <span className="muted-text">
                {i === 3 ? "暂未提供" : "实时查询"}
              </span>
            </div>
          </article>
        ))}
      </section>
      <section className="dashboard-grid">
        <div className="panel">
          <div className="panel-head">
            <h2>入库趋势</h2>
            <UnavailableButton>查看详情</UnavailableButton>
          </div>
          <div className="placeholder-chart">当前版本暂未提供趋势统计</div>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>快捷操作</h2>
          </div>
          <div className="quick-actions">
            <button className="action" onClick={() => navigate("chips")}>
              <Link2 size={18} />
              登记与查询芯片
            </button>
            <button className="action" onClick={() => navigate("items")}>
              <Box size={18} />
              维护物品资料
            </button>
            <button className="action" onClick={() => navigate("checks")}>
              <Database size={18} />
              检查运行环境
            </button>
          </div>
        </div>
      </section>
      <Notice>
        物品启用、芯片绑定、写卡完成与真实防伪通过是不同结果，须分别验证。
      </Notice>
    </>
  );
}
export function AdminLayout({
  expiry,
  busy,
  onLogout,
  onSessionExpired,
  message,
}: {
  expiry: string;
  busy: boolean;
  onLogout: () => void;
  onSessionExpired: () => void;
  message: string;
}) {
  const [page, setPage] = useState<Page>("overview");
  const [unavailable, setUnavailable] = useState(false);
  const [checks, setChecks] = useState(false);
  const leave = useRef<() => boolean>(() => true);
  const registerLeave = useCallback((guard: () => boolean) => {
    leave.current = guard;
  }, []);
  function navigate(next: Page) {
    if (next === page || !leave.current()) return;
    leave.current = () => true;
    setPage(next);
  }
  return (
    <UnavailableContext.Provider value={() => setUnavailable(true)}>
      <div className="admin-shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-symbol">
              <Sparkles />
            </div>
            <div>
              <strong>BUMBUM</strong>
              <span>管理后台</span>
            </div>
          </div>
          <nav aria-label="基础功能">
            <span className="nav-label">基础</span>
            {NAV.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                className={`nav-item ${page === id ? "active" : ""}`}
                aria-current={page === id ? "page" : undefined}
                onClick={() => navigate(id)}
              >
                <Icon />
                <span>{label}</span>
              </button>
            ))}
            <span className="nav-label nav-label-spaced">系统</span>
            <button
              className={`nav-item ${page === "checks" ? "active" : ""}`}
              onClick={() => navigate("checks")}
            >
              <Database />
              <span>系统状态</span>
            </button>
            <UnavailableButton className="nav-item">
              <Settings />
              <span>设置</span>
            </UnavailableButton>
          </nav>
          <div className="sidebar-footer">
            <p>
              会话到期：
              {new Date(expiry).toLocaleString("zh-CN", { hour12: false })}
            </p>
            <button
              disabled={busy}
              onClick={() => {
                if (leave.current()) onLogout();
              }}
            >
              <LogOut size={18} />
              退出登录
            </button>
          </div>
        </aside>
        <main className="workspace-main">
          <header className="topbar">
            <div className="topbar-status">BUMBUM · 管理工作空间</div>
            <div className="topbar-actions">
              <button className="action" onClick={() => setChecks(true)}>
                <Database size={16} />
                运行检查
              </button>
              <UnavailableButton className="icon-action">
                <span className="sr-only">通知</span>
                <Bell size={18} />
              </UnavailableButton>
              <div className="avatar">CC</div>
            </div>
          </header>
          <div className="page">
            {message && <Notice error>{message}</Notice>}
            {page === "overview" && (
              <Overview
                onSessionExpired={onSessionExpired}
                navigate={navigate}
              />
            )}
            {page === "chips" && (
              <ChipPanel
                onSessionExpired={onSessionExpired}
                registerLeave={registerLeave}
              />
            )}
            {page === "items" && (
              <ItemPanel
                onSessionExpired={onSessionExpired}
                registerLeave={registerLeave}
              />
            )}
            {page === "owners" && (
              <>
                <PageHeading
                  title="所有权管理"
                  subtitle="所有权绑定和流转功能尚未开放。"
                  action={
                    <UnavailableButton>
                      <Users size={18} />
                      绑定所有权
                    </UnavailableButton>
                  }
                />
                <div className="filter-bar">
                  <input
                    aria-label="所有权搜索"
                    placeholder="物品编号或手机号"
                  />
                  <UnavailableButton>查询</UnavailableButton>
                  <UnavailableButton>导出</UnavailableButton>
                </div>
                <div className="panel">
                  <div className="panel-head">
                    <h2>有效所有权</h2>
                    <UnavailableButton>查看流转</UnavailableButton>
                  </div>
                  <div className="placeholder-chart">
                    当前版本暂未实现，尚未读取所有权记录。
                  </div>
                </div>
              </>
            )}
            {page === "checks" && (
              <>
                <PageHeading
                  title="系统状态"
                  subtitle="真实检查后端与数据库，不代表全部业务功能已通过验收。"
                />
                <RuntimeChecks />
              </>
            )}
          </div>
        </main>
      </div>
      <Dialog open={unavailable} onOpenChange={setUnavailable}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>功能暂未开放</DialogTitle>
            <DialogDescription>当前版本暂未实现</DialogDescription>
          </DialogHeader>
          <button
            className="action action-primary"
            onClick={() => setUnavailable(false)}
          >
            知道了
          </button>
        </DialogContent>
      </Dialog>
      <Dialog open={checks} onOpenChange={setChecks}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>运行检查</DialogTitle>
            <DialogDescription>
              检查当前后端程序与数据库连接。
            </DialogDescription>
          </DialogHeader>
          <RuntimeChecks />
        </DialogContent>
      </Dialog>
    </UnavailableContext.Provider>
  );
}
