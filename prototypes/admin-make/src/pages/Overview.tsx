import React, { useState } from "react";
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
} from "antd";
import {
  ShoppingOutlined,
  CheckCircleOutlined,
  LinkOutlined,
  ToolOutlined,
  ArrowRightOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useStore } from "../data/store";
import {
  statistics,
  StatsFilter,
  edition,
  userName,
  timeText,
} from "../data/domain";
import { go, queryState, saveQuery, ErrorState } from "../ui";
import { CopyValue, EditionValue, StatusTag } from "../components/RecordPresentation";
export default function Overview() {
  const p = useStore(),
    q = queryState();
  const [filter, setFilter] = useState<StatsFilter>({
    scope: q.scope === "all" ? "all" : "sold",
    range: q.range === "all" ? "all" : q.range === "30d" ? "30d" : "7d",
    styleId: q.styleId,
    issueId: q.issueId,
  });
  const [view, setView] = useState(q.view || "touches");
  const d = p.data,
    s = statistics(d, filter),
    max = Math.max(1, ...s.daily.map((x) => x.count));
  if (p.readError)
    return (
      <PageContainer title="工作台">
        <ErrorState />
      </PageContainer>
    );
  const inventory = [
    {
      title: "数字物品",
      value: d.items.length,
      url: "/items",
      icon: <ShoppingOutlined aria-hidden />,
      tone: "neutral",
      note: "稳定数字身份档案",
    },
    {
      title: "已启用",
      value: d.items.filter((i) => i.status === "active").length,
      url: "/items?status=active",
      icon: <CheckCircleOutlined aria-hidden />,
      tone: "green",
      note: "查看当前启用档案",
    },
    {
      title: "待绑定芯片",
      value: d.chips.filter((c) => c.state === "pending" && !c.candidateFor)
        .length,
      url: "/chips?state=pending",
      icon: <LinkOutlined aria-hidden />,
      tone: "blue",
      note: "查看待关联芯片",
    },
    {
      title: "待配置芯片",
      value: d.chips.filter(
        (c) => c.itemId && !c.configuredAt && c.state !== "retired",
      ).length,
      url: "/chips?configured=no",
      icon: <ToolOutlined aria-hidden />,
      tone: "amber",
      note: "查看待配置芯片",
    },
  ];
  return (
    <PageContainer
      header={{ title: false, breadcrumb: {} }}
    >
      <div className="page-stack">
        <ProCard
          size="small"
          headerBordered
          variant="outlined"
          title="物品与芯片概况"
          extra={<Tag color="blue">点击卡片带条件查看</Tag>}
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
          <div className="workbench-shortcuts"><Typography.Text strong>快捷操作</Typography.Text><Button type="primary" onClick={() => go("/catalog/style/new")}>新建款式</Button><Button onClick={() => go("/catalog/issue/new")}>新建发行约定</Button><Button onClick={() => go("/items?create=1")}>登记数字物品</Button><Button onClick={() => go("/chips")}>芯片登记与配置</Button></div>
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
                layout="vertical"
                onFinish={async (v: any) => {
                  setFilter(v);
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
                  <ProFormSelect
                    name="styleId"
                    label="款式"
                    allowClear
                    options={d.styles.map((x) => ({
                      value: x.id,
                      label: x.name,
                    }))}
                  />
                  <ProFormSelect
                    name="issueId"
                    label="发行"
                    allowClear
                    options={d.issues.map((x) => ({
                      value: x.id,
                      label: x.name,
                    }))}
                  />
                  <Button
                    htmlType="submit"
                    type="primary"
                    icon={<SearchOutlined aria-hidden />}
                  >
                    应用筛选
                  </Button>
                </div>
              </ProForm>
              <div className="filter-summary">
                <Tag color="blue">已生效</Tag>
                <span>
                  {filter.scope === "sold"
                    ? "已确认售出身份，且触碰时间不早于首次售出"
                    : "全部身份的全生命周期"}{" "}
                  ·{" "}
                  {filter.range === "all"
                    ? "累计"
                    : filter.range === "7d"
                      ? "近7日"
                      : "近30日"}
                </span>
                <span className="data-asof">
                  截至 {timeText(new Date().toISOString())} · 北京时间
                </span>
              </div>
            </div>
            <Row gutter={[16, 16]}>
              {[
                ["有效触碰次数", s.total, "次"],
                ["被触碰物品数", s.touched, "件"],
              ].map(([title, value, unit]) => <Col xs={24} sm={12} key={title}><ProCard size="small" variant="outlined" className="metric-card metric-primary"><Statistic title={title} value={value} suffix={unit} /><div className="cell-secondary">所选口径与时间范围内</div></ProCard></Col>)}
            </Row>
            <Row gutter={[12, 12]}>
              {[
                ["已确认售出物品", s.sold, "件"],
                ["已认领物品", s.claimed, "件"],
                ["当前持有人", s.owners, "人"],
              ].map(([title, value, unit]) => (
                <Col flex="1 1 160px" key={title}>
                  <ProCard
                    size="small"
                    variant="outlined"
                    className="metric-card metric-secondary"
                  >
                    <Statistic title={title} value={value} suffix={unit} />
                    <div className="cell-secondary">所选款式/发行的当前关系，不按触碰时间折算</div>
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
                  {s.daily.map((x) => (
                    <Tooltip
                      key={x.date}
                      title={x.date + " · " + x.count + "次"}
                    >
                      <div
                        className="trend-day"
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
                saveQuery({ ...filter, view: v });
              }}
              items={[
                { key: "touches", label: "物品触碰明细" },
                { key: "holders", label: "持有关系明细" },
              ]}
            />
            {view === "touches" ? (
              <ProTable
                rowKey="id"
                headerTitle="按稳定数字身份汇总，历史芯片一并累计"
                search={false}
                options={false}
                cardProps={{ ghost: true }}
                size="middle"
                scroll={{ x: "max-content" }}
                dataSource={s.rows.map((r) => ({ id: r.item.id, ...r }))}
                pagination={{ pageSize: 10, showSizeChanger: false }}
                columns={[
                  {
                    title: "数字物品",
                    render: (_, r) => (
                      <CopyValue value={r.item.uid} onClick={() => go("/items/" + r.id)} />
                    ),
                  },
                  {
                    title: "发行编号",
                    render: (_, r) =>
                      <EditionValue value={edition(
                        r.item,
                        d.issues.find((x) => x.id === r.item.issueId),
                      )} />,
                  },
                  {
                    title: "售出确认",
                    render: (_, r) => (
                      <Tag color={r.item.sold ? "blue" : "default"}>
                        {r.item.sold ? "已确认售出" : "未确认售出"}
                      </Tag>
                    ),
                  },
                  {
                    title: "持有人",
                    render: (_, r) => r.item.ownerId ? <Space direction="vertical" size={0}><span>{userName(r.item.ownerId)}</span><CopyValue value={r.item.ownerId} /></Space> : <StatusTag value="未认领" />,
                  },
                  { title: "有效触碰", dataIndex: "count" },
                  { title: "最近触碰", render: (_, r) => timeText(r.last) },
                ]}
              />
            ) : (
              <ProTable
                rowKey="id"
                headerTitle="账户与持有关系 · 仅合成样例"
                search={false}
                options={false}
                cardProps={{ ghost: true }}
                size="middle"
                scroll={{ x: "max-content" }}
                dataSource={[
                  ...new Set(
                    s.items.flatMap((i) => (i.ownerId ? [i.ownerId] : [])),
                  ),
                ].map((id) => ({
                  id,
                  name: userName(id),
                  items: s.items.filter((i) => i.ownerId === id),
                }))}
                pagination={{ pageSize: 10, showSizeChanger: false }}
                columns={[
                  { title: "稳定账户", dataIndex: "id", render: (_, r) => <CopyValue value={r.id} /> },
                  { title: "持有人", dataIndex: "name" },
                  {
                    title: "当前持有",
                    render: (_, r) => r.items.length + "件",
                  },
                  {
                    title: "物品档案",
                    render: (_, r) => (
                      <Space wrap>
                        {r.items.map((i) => (
                          <CopyValue
                            key={i.id}
                            value={i.uid}
                            onClick={() => go("/items/" + i.id)}
                          />
                        ))}
                      </Space>
                    ),
                  },
                ]}
              />
            )}
            <Typography.Paragraph type="secondary">
              持有指标表示当前关系，时间范围仅筛选触碰。用户/认领服务尚未接入，本页账户均为演示样例。匿名触碰不计算独立用户或活跃用户，不把旧事件归给当前持有人。
            </Typography.Paragraph>
          </div>
        </ProCard>
      </div>
    </PageContainer>
  );
}
