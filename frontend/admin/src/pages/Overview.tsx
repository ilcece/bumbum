import type { CatalogQuery, CatalogStatistics } from "../types/catalog";
import ReadFailure from "../components/ReadFailure";
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
  Row,
  Col,
  Tabs,
  Space,
  Tag,
  Typography,
  Tooltip,
  Form,
} from "antd";
import {
  SearchOutlined,
} from "@ant-design/icons";
import { history, useLocation } from "@umijs/max";
import {
  activityPath,
  itemWorkflowNames,
  statistics,
  edition,
  time,
  read,
  workbenchWorkflows,
} from "../catalog";
import {
  Copy as CopyValue,
  State as StatusTag,
  RemoteSelect,
} from "../components/CatalogUI";
import UserIdentity from "../components/UserIdentity";
import ItemActivity from "../components/ItemActivity";
import MetricCard from "../components/MetricCard";
export default function Overview() {
  const location = useLocation();
  const q = new URLSearchParams(location.search);
  const [filter, setFilter] = useState<CatalogQuery>({
    scope: q.get("scope") === "all" ? "all" : "sold",
    range: q.get("range") || "7d",
    style_id: q.get("style_id") || undefined,
    issue_id: q.get("issue_id") || undefined,
  });
  const [view, setView] = useState(q.get("view") || "touches"),
    [detailFilter, setDetailFilter] = useState(q.get("detail_filter") || ""),
    [page, setPage] = useState(Number(q.get("page") || 1)),
    [data, setData] = useState<CatalogStatistics>(),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [filterDirty, setFilterDirty] = useState(false),
    [applied, setApplied] = useState<CatalogQuery>({}),
    [appliedNames, setAppliedNames] = useState<Record<string, string>>({}),
    [asOf, setAsOf] = useState(q.get("as_of") || undefined);
  useEffect(() => {
    let live = true;
    setLoading(true);
    statistics({ ...filter, as_of: asOf, page, detail_filter: detailFilter || undefined })
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
  }, [filter, asOf, page, detailFilter]);
  useEffect(() => {
    let live = true;
    setAppliedNames({});
    for (const [key, resource] of [
      ["style_id", "styles"],
      ["issue_id", "issues"],
    ] as const) {
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
    style_id: applied.style_id as string | number | undefined, issue_id: applied.issue_id as string | number | undefined, ...extra,
  }));
  const saveQuery = (values: CatalogQuery) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(values))
      if (v != null && v !== "") q.set(k, String(v));
    history.replace("/overview?" + q);
  };
  const showTapItems = (value: string) => {
    const cutoff = data?.as_of;
    setAsOf(cutoff);
    setDetailFilter(value);
    setView("touches");
    setPage(1);
    saveQuery({ ...filter, as_of: cutoff, view: "touches", detail_filter: value || undefined });
    document.getElementById("overview-details")?.scrollIntoView({ block: "start" });
  };
  const changePage = (next: number) => {
    setPage(next);
    saveQuery({ ...filter, as_of: asOf, view, detail_filter: detailFilter || undefined, page: next });
  };
  const s = {
    total: data?.total,
    touched: data?.touched_items,
    sold: data?.counts.sold_items,
    claimed: data?.counts.claimed_items,
    owners: data?.counts.holders,
    daily: (data?.daily || []).map((x) => ({
      date: x.day,
      count: x.total,
    })),
  };
  const max = Math.max(1, ...s.daily.map((x) => x.count));
  const touchDetailAction = (key: string, label: string) =>
    data && !loading && !error ? { label, run: () => showTapItems(key) } : undefined;
  return (
    <PageContainer header={{ title: false, breadcrumb: {} }}>
      <div className="page-stack">
        {error && (
          <ReadFailure title="工作台统计读取失败" error={error} retry={() => setFilter({ ...filter })} />
        )}
        <ProCard
          size="small"
          headerBordered
          variant="outlined"
          title="待办与可分配库存"
        >
          <Row gutter={[12, 12]}>
            {workbenchWorkflows.map((stage) => (
              <Col flex="1 1 150px" key={stage}>
                <MetricCard title={itemWorkflowNames[stage]} value={data?.workflow_counts[stage]} unit="件"
                  action={data && !error ? { label: "查看物品", run: () => go("/items?workflow=" + stage) } : undefined} />
              </Col>
            ))}
          </Row>
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
                  setAsOf(undefined);
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
                {error && data && <Tag color="orange">上次成功结果</Tag>}
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
            <Typography.Text strong>使用覆盖与频次</Typography.Text>
            <Row gutter={[12, 12]}>
              <Col flex="1 1 180px">
                <MetricCard title="有效触碰次数" value={s.total} unit="次" note="所选口径与时间范围内"
                  action={data && !loading && !error ? { label: "查看触碰明细", run: () => tapDetails() } : undefined} />
              </Col>
              <Col flex="1 1 180px">
                <MetricCard title="被触碰物品数" value={s.touched} unit="件" note="所选口径与时间范围内"
                  action={touchDetailAction("touched", "查看被触碰物品")} />
              </Col>
              <Col flex="1 1 180px">
                <MetricCard title="重复触碰物品" value={data?.touch_item_counts.repeat} unit="件" note="所选范围内至少触碰两次"
                  action={touchDetailAction("repeat", "查看触碰至少两次的物品")} />
              </Col>
            </Row>
            <Typography.Text type="secondary">
              每件被触碰物品平均 {s.touched ? (s.total! / s.touched).toFixed(1) + " 次" : "—"}
            </Typography.Text>
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
                  {s.daily.map((x) => (
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
            {data?.scope === "sold" && <>
              <Typography.Text strong>售出后跟进</Typography.Text>
              <Row gutter={[12, 12]}>
                <Col xs={24} sm={12}>
                  <MetricCard title="所选时段售出后零触碰" value={data.touch_item_counts.zero} unit="件"
                    action={touchDetailAction("zero", "查看零触碰物品")} />
                </Col>
                <Col xs={24} sm={12}>
                  <MetricCard title="成交时间待核对" value={data.touch_item_counts.missing_sale} unit="件"
                    action={touchDetailAction("missing_sale", "查看成交时间缺失物品")} />
                </Col>
              </Row>
            </>}
          </div>
        </ProCard>
        <ProCard title="售出与持有" headerBordered>
          <div className="page-stack">
            <Row gutter={[12, 12]}>
              {[
                { title: "已确认售出物品", value: s.sold, unit: "件" },
                { title: "已有持有人物品", value: s.claimed, unit: "件" },
                { title: "当前持有人", value: s.owners, unit: "人" },
              ].map((metric) => (
                <Col flex="1 1 160px" key={metric.title}>
                  <MetricCard {...metric} note="按所选款式与发行的当前关系统计" />
                </Col>
              ))}
            </Row>
            <Typography.Text type="secondary">时间范围只应用于触碰统计。</Typography.Text>
          </div>
        </ProCard>
        <div id="overview-details">
          <ProCard title="统计明细" headerBordered>
            <Tabs
              className="section-tabs"
              size="small"
              activeKey={view}
              onChange={(v) => {
                setView(v);
                setPage(1);
                saveQuery({ ...filter, as_of: asOf, view: v, detail_filter: detailFilter || undefined });
              }}
              items={[
                { key: "touches", label: "物品触碰明细" },
                { key: "holders", label: "持有关系明细" },
              ]}
            />
            {view === "touches" ? (
              <div>
              <Space wrap>
                {[
                  ["", "全部物品"], ["touched", "有有效触碰"], ["repeat", "重复触碰"],
                  ...(data?.scope === "sold" ? [["zero", "所选时段售出后零触碰"], ["missing_sale", "成交时间待核对"]] : []),
                ].map(([key, label]) => <Button key={key}
                  disabled={!data || loading || !!error} type={detailFilter === key ? "primary" : "default"}
                  onClick={() => showTapItems(key)}>{label}</Button>)}
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
                    render: (_, r) => <span>{edition(r)}</span>,
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
              重复触碰按同一数字物品计算。验收样本由测试数据开关控制。匿名触碰按事件记录。
            </Typography.Paragraph>
          </ProCard>
        </div>
        <ProCard title="最近用户动态" headerBordered extra={<Button onClick={() => go(activityPath(from, {}))}>查看全部</Button>}>
          <ItemActivity />
        </ProCard>
      </div>
    </PageContainer>
  );
}
