import React, { useState, useEffect } from "react";
import {
  PageContainer,
  ProCard,
  ProForm,
  ProFormSelect,
  ProTable,
} from "@ant-design/pro-components";
import {
  Button,
  Statistic,
  Row,
  Col,
  Tabs,
  Space,
  Tag,
  Typography,
  Tooltip,
  Alert,
  Form,
} from "antd";
import {
  ShoppingOutlined,
  CheckCircleOutlined,
  LinkOutlined,
  ToolOutlined,
  ArrowRightOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { history, useLocation } from "@umijs/max";
import {
  list,
  statistics,
  Row as CatalogRow,
  edition,
  time,
  read,
} from "../catalog";
import {
  Copy as CopyValue,
  State as StatusTag,
  RemoteSelect,
} from "../components/CatalogUI";
import UserIdentity from "../components/UserIdentity";
import ItemActivity from "../components/ItemActivity";
import { activityPath } from "../catalog";
export default function Overview() {
  const location = useLocation();
  const q = new URLSearchParams(location.search);
  const [filter, setFilter] = useState<Record<string, any>>({
    scope: q.get("scope") === "all" ? "all" : "sold",
    range: q.get("range") || "7d",
    style_id: q.get("style_id") || undefined,
    issue_id: q.get("issue_id") || undefined,
  });
  const [view, setView] = useState(q.get("view") || "touches"),
    [detailFilter, setDetailFilter] = useState(q.get("detail_filter") || ""),
    [page, setPage] = useState(Number(q.get("page") || 1)),
    [data, setData] = useState<CatalogRow>(),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [filterDirty, setFilterDirty] = useState(false),
    [applied, setApplied] = useState<Record<string, any>>({}),
    [appliedNames, setAppliedNames] = useState<Record<string, string>>({});
  useEffect(() => {
    let live = true;
    setLoading(true);
    statistics({ ...filter, page, detail_filter: detailFilter || undefined })
      .then((result) => {
        if (live) {
          setData(result);
          setApplied({ ...filter });
          setError("");
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [filter, page, detailFilter]);
  useEffect(() => {
    let live = true;
    setAppliedNames({});
    for (const [key, resource] of [
      ["style_id", "styles"],
      ["issue_id", "issues"],
    ]) {
      if (applied[key])
        read(resource, Number(applied[key]))
          .then((r) => {
            if (live) setAppliedNames((v) => ({ ...v, [key]: r.name }));
          })
          .catch(() => {});
    }
    return () => {
      live = false;
    };
  }, [applied]);
  const go = (path: string) => history.push(path);
  const from = "/overview" + location.search;
  const tapDetails = (extra: Record<string, string | number> = {}) => go(activityPath(from, {
    event: "tap", scope: data?.scope, range: data?.range, as_of: data?.as_of,
    style_id: applied.style_id, issue_id: applied.issue_id, ...extra,
  }));
  const saveQuery = (values: Record<string, any>) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(values))
      if (v != null && v !== "") q.set(k, String(v));
    history.replace("/overview?" + q);
  };
  const showTapItems = (value: string) => {
    setDetailFilter(value);
    setView("touches");
    setPage(1);
    saveQuery({ ...filter, view: "touches", detail_filter: value || undefined });
    document.getElementById("overview-tap-items")?.scrollIntoView({ block: "nearest" });
  };
  const changePage = (next: number) => {
    setPage(next);
    saveQuery({ ...filter, view, detail_filter: detailFilter || undefined, page: next });
  };
  const s = {
    total: data?.total,
    touched: data?.touched_items,
    sold: data?.counts.sold_items,
    claimed: data?.counts.claimed_items,
    owners: data?.counts.holders,
    daily: (data?.daily || []).map((x: any) => ({
      date: x.day,
      count: x.total,
    })),
  };
  const max = Math.max(1, ...s.daily.map((x: any) => x.count));
  const inventory = [
    {
      title: "数字物品",
      value: data?.inventory.items ?? "—",
      url: "/items",
      icon: <ShoppingOutlined aria-hidden />,
      tone: "neutral",
      note: "稳定数字身份档案",
    },
    {
      title: "已启用",
      value: data?.inventory.active_items ?? "—",
      url: "/items?status=active",
      icon: <CheckCircleOutlined aria-hidden />,
      tone: "green",
      note: "查看当前启用档案",
    },
    {
      title: "待绑定芯片",
      value: data?.inventory.pending_chips ?? "—",
      url: "/chips?status=pending",
      icon: <LinkOutlined aria-hidden />,
      tone: "blue",
      note: "查看待关联芯片",
    },
    {
      title: "待配置芯片",
      value: data?.inventory.unconfigured_chips ?? "—",
      url: "/chips?configured=no",
      icon: <ToolOutlined aria-hidden />,
      tone: "amber",
      note: "查看待配置芯片",
    },
  ];
  return (
    <PageContainer header={{ title: false, breadcrumb: {} }}>
      <div className="page-stack">
        <ProCard title="待办入口" headerBordered>
          <Space wrap>
            <Button type="primary" onClick={() => go("/orders")}>查看订单</Button>
            {Object.entries({ assembly: "待装配", verification: "待核验", delivery: "待交付", claim: "待认领" }).map(([key, label]) =>
              <Button key={key} onClick={() => go("/items?workflow=" + key)}>{label}</Button>)}
          </Space>
        </ProCard>
        {error && (
          <Alert
            type="error"
            title={error}
            action={
              <Button onClick={() => setFilter({ ...filter })}>重试</Button>
            }
          />
        )}
        <ProCard
          size="small"
          headerBordered
          variant="outlined"
          title="物品与芯片概况"
          extra={<Space><Tag color="blue">点击卡片带条件查看</Tag></Space>}
        >
          <Row gutter={[16, 16]}>
            {inventory.map((card) => (
              <Col xs={12} lg={6} key={card.title}>
                <ProCard
                  size="small"
                  variant="outlined"
                  className={"inventory-card inventory-" + card.tone}
                  role="button"
                  tabIndex={0}
                  aria-label={card.title + " " + card.value + "，查看档案"}
                  onClick={() => go(card.url)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      go(card.url);
                    }
                  }}
                >
                  <Statistic
                    title={
                      <Space size={7}>
                        {card.icon}
                        <span>{card.title}</span>
                      </Space>
                    }
                    value={card.value}
                  />
                  <div className="inventory-caption">
                    <span>{card.note}</span>
                    <ArrowRightOutlined aria-hidden />
                  </div>
                </ProCard>
              </Col>
            ))}
          </Row>
          <div className="workbench-shortcuts">
            <Typography.Text strong>快捷操作</Typography.Text>
            <Button type="primary" onClick={() => go("/catalog/style/new")}>
              新建款式
            </Button>
            <Button onClick={() => go("/catalog/issue/new")}>
              新建发行约定
            </Button>
            <Button onClick={() => go("/items?create=1")}>登记数字物品</Button>
            <Button onClick={() => go("/chips")}>芯片登记与配置</Button>
          </div>
        </ProCard>
        <ProCard
          size="small"
          headerBordered
          variant="outlined"
          title="触碰统计"
          tooltip="只计有效事件，配置核验不计入"
          extra={<Tag>北京时间</Tag>}
        >
          <div className="page-stack">
            <div className="filter-panel">
              <ProForm
                initialValues={filter}
                onValuesChange={() => setFilterDirty(true)}
                layout="vertical"
                onFinish={async (v: any) => {
                  setPage(1);
                  setDetailFilter("");
                  setFilter(v);
                  setFilterDirty(false);
                  saveQuery({ ...v, view });
                }}
                submitter={false}
              >
                <div className="stats-filter-grid">
                  <ProFormSelect
                    name="scope"
                    label="统计口径"
                    options={[
                      { value: "sold", label: "售出后的有效触碰" },
                      { value: "all", label: "全生命周期有效触碰" },
                    ]}
                  />
                  <ProFormSelect
                    name="range"
                    label="时间范围"
                    options={[
                      { value: "7d", label: "近7日（含今天）" },
                      { value: "30d", label: "近30日（含今天）" },
                      { value: "all", label: "累计" },
                    ]}
                  />
                  <Form.Item name="style_id" label="款式">
                    <RemoteSelect resource="styles" />
                  </Form.Item>
                  <Form.Item name="issue_id" label="发行">
                    <RemoteSelect resource="issues" />
                  </Form.Item>
                  <Button
                    htmlType="submit"
                    type="primary"
                    loading={loading}
                    icon={<SearchOutlined aria-hidden />}
                  >
                    应用筛选
                  </Button>
                </div>
              </ProForm>
              <div className="filter-summary">
                <Tag color="blue">已生效</Tag>
                {filterDirty && <Tag color="orange">筛选已修改，尚未应用</Tag>}
                <span>
                  款式：
                  {applied.style_id
                    ? appliedNames.style_id || `款式 ${applied.style_id}`
                    : "全部"}{" "}
                  · 发行：
                  {applied.issue_id
                    ? appliedNames.issue_id || `发行 ${applied.issue_id}`
                    : "全部"}
                </span>
                <span>
                  {data?.scope === "sold"
                    ? "已确认售出身份，且触碰时间不早于首次售出"
                    : "全部身份的全生命周期"}{" "}
                  ·{" "}
                  {data?.range === "all"
                    ? "累计"
                    : data?.range === "7d"
                      ? "近7日"
                      : "近30日"}
                </span>
                <span className="data-asof">
                  截至 {time(data?.as_of)} · 北京时间
                </span>
              </div>
            </div>
            <Row gutter={[16, 16]}>
              {[
                ["有效触碰次数", s.total, "次"],
                ["被触碰物品数", s.touched, "件"],
              ].map(([title, value, unit]) => (
                <Col xs={24} sm={12} key={title}>
                  <ProCard
                    size="small"
                    variant="outlined"
                    className="metric-card metric-primary"
                  >
                    <Statistic
                      title={title}
                      value={value ?? "—"}
                      suffix={unit}
                    />
                    {title === "有效触碰次数" && data ? <Button type="link" onClick={() => tapDetails()}>查看触碰明细</Button> :
                      title === "被触碰物品数" && data ? <Button type="link" onClick={() => showTapItems("touched")}>查看被触碰物品</Button> :
                      <div className="cell-secondary">所选口径与时间范围内</div>}
                  </ProCard>
                </Col>
              ))}
            </Row>
            <Row gutter={[12, 12]}>
              {[
                ["已确认售出物品", s.sold, "件"],
                ["已有持有人物品", s.claimed, "件"],
                ["当前持有人", s.owners, "人"],
              ].map(([title, value, unit]) => (
                <Col flex="1 1 160px" key={title}>
                  <ProCard
                    size="small"
                    variant="outlined"
                    className="metric-card metric-secondary"
                  >
                    <Statistic
                      title={title}
                      value={value ?? "—"}
                      suffix={unit}
                    />
                    <div className="cell-secondary">
                      所选款式/发行的当前关系，不按触碰时间折算
                    </div>
                  </ProCard>
                </Col>
              ))}
            </Row>
            <ProCard
              size="small"
              headerBordered
              variant="outlined"
              title="有效触碰日趋势"
              extra={
                <Typography.Text type="secondary">
                  按北京时间自然日汇总
                </Typography.Text>
              }
            >
              {s.daily.length ? (
                <div
                  className="trend"
                  role="img"
                  aria-label="按北京时间汇总的有效触碰日趋势"
                >
                  {s.daily.map((x: any) => (
                    <Tooltip
                      key={x.date}
                      title={x.date + " · " + x.count + "次"}
                    >
                      <div
                        className="trend-day"
                        role="button"
                        onClick={() => tapDetails({ date_from: x.date, date_to: x.date })}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            tapDetails({ date_from: x.date, date_to: x.date });
                          }
                        }}
                        tabIndex={0}
                        aria-label={x.date + "，有效触碰" + x.count + "次"}
                      >
                        <span>{x.count}</span>
                        <div className="trend-track">
                          <div
                            className="trend-bar"
                            style={{
                              height: Math.max(2, (x.count / max) * 110),
                            }}
                          />
                        </div>
                        <span>{x.date.slice(5)}</span>
                      </div>
                    </Tooltip>
                  ))}
                </div>
              ) : (
                <Typography.Text type="secondary">
                  当前范围暂无有效触碰。
                </Typography.Text>
              )}
            </ProCard>
            <Tabs
              className="section-tabs"
              size="small"
              activeKey={view}
              onChange={(v) => {
                setView(v);
                setPage(1);
                saveQuery({ ...filter, view: v });
              }}
              items={[
                { key: "touches", label: "物品触碰明细" },
                { key: "holders", label: "持有关系明细" },
              ]}
            />
            {view === "touches" ? (
              <div id="overview-tap-items">
              <Space wrap>
                <Button type={!detailFilter ? "primary" : "default"} onClick={() => showTapItems("")}>全部物品</Button>
                <Button type={detailFilter === "touched" ? "primary" : "default"} onClick={() => showTapItems("touched")}>有有效触碰</Button>
                {filter.scope === "sold" && <>
                  <Button type={detailFilter === "zero" ? "primary" : "default"} onClick={() => showTapItems("zero")}>售出后零触碰</Button>
                  <Button type={detailFilter === "missing_sale" ? "primary" : "default"} onClick={() => showTapItems("missing_sale")}>成交时间待核对</Button>
                </>}
              </Space>
              <ProTable
                rowKey="id"
                headerTitle="按稳定数字身份汇总，历史芯片一并累计"
                search={false}
                options={false}
                cardProps={{ ghost: true }}
                size="middle"
                scroll={{ x: "max-content" }}
                dataSource={data?.details.items || []}
                loading={loading}
                pagination={{
                  pageSize: 10,
                  showSizeChanger: false,
                  current: data?.details.page || page,
                  total: data?.details.total || 0,
                  onChange: changePage,
                }}
                columns={[
                  {
                    title: "数字物品",
                    render: (_, r) => (
                      <CopyValue
                        value={r.item_uid}
                        onClick={() => go("/items/" + r.id + "?from=" + encodeURIComponent(from))}
                      />
                    ),
                  },
                  {
                    title: "发行编号",
                    render: (_, r) => <span>{edition(r as CatalogRow)}</span>,
                  },
                  {
                    title: "售出确认",
                    render: (_, r) => (
                      <Tag color={r.sold ? "blue" : "default"}>
                        {r.sold ? "已确认售出" : "未确认售出"}
                      </Tag>
                    ),
                  },
                  {
                    title: "持有人",
                    render: (_, r) =>
                      r.owner_id ? (
                        <Space direction="vertical" size={0}>
                          {r.owner_name && <span>{r.owner_name}</span>}
                          <UserIdentity uid={r.owner_public_uid} />
                        </Space>
                      ) : (
                        <StatusTag value="暂无持有人" />
                      ),
                  },
                  { title: "有效触碰", dataIndex: "tap_count", render: (_, r) => <Button type="link" onClick={() => tapDetails({ item_id: r.id })}>{r.tap_count}</Button> },
                  { title: "最近触碰", render: (_, r) => time(r.last_tap) },
                ]}
              />
              </div>
            ) : (
              <ProTable
                rowKey="id"
                headerTitle="账户与持有关系"
                search={false}
                options={false}
                cardProps={{ ghost: true }}
                size="middle"
                scroll={{ x: "max-content" }}
                dataSource={data?.holders.items || []}
                loading={loading}
                pagination={{
                  pageSize: 10,
                  showSizeChanger: false,
                  current: data?.holders.page || page,
                  total: data?.holders.total || 0,
                  onChange: changePage,
                }}
                columns={[
                  {
                    title: "稳定账户",
                    dataIndex: "id",
                    render: (_, r) => <UserIdentity uid={r.public_uid} />,
                  },
                  { title: "持有人", dataIndex: "nickname" },
                  {
                    title: "当前持有",
                    render: (_, r) => r.held_items + "件",
                  },
                ]}
              />
            )}
            <Typography.Paragraph type="secondary">
              持有指标表示当前关系，时间范围仅筛选触碰。验收样本由设置中的测试数据开关统一控制。匿名触碰不计算独立用户或活跃用户，不把旧事件归给当前持有人。
            </Typography.Paragraph>
          </div>
        </ProCard>
        <ProCard title="最近用户动态" headerBordered extra={<Button onClick={() => go(activityPath(from, {}))}>查看全部</Button>}>
          <ItemActivity />
        </ProCard>
      </div>
    </PageContainer>
  );
}
