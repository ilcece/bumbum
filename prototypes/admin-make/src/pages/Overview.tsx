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
import { useStore } from "../data/store";
import {
  statistics,
  StatsFilter,
  edition,
  issueText,
  userName,
  timeText,
  Data,
} from "../data/domain";
import {
  go,
  useDataTable,
  tableRequest,
  queryState,
  saveQuery,
  ErrorState,
} from "../ui";
export default function Overview() {
  const p = useStore(),
    q = queryState(),
    table = useDataTable();
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
  return (
    <PageContainer
      title="工作台"
      subTitle="准备、使用与持有，分别核对"
      extra={
        <Button type="primary" onClick={() => go("/catalog/style/new")}>
          新建款式
        </Button>
      }
    >
      <div className="page-stack">
        <Row gutter={[16, 16]}>
          {[
            ["数字物品", d.items.length, "/items"],
            [
              "已启用",
              d.items.filter((i) => i.status === "active").length,
              "/items?status=active",
            ],
            [
              "待绑定芯片",
              d.chips.filter((c) => c.state === "pending" && !c.candidateFor)
                .length,
              "/chips?state=pending",
            ],
            [
              "待配置芯片",
              d.chips.filter(
                (c) => c.itemId && !c.configuredAt && c.state !== "retired",
              ).length,
              "/chips?configured=no",
            ],
          ].map(([title, value, url]) => (
            <Col span={6} key={title}>
              <ProCard
                variant="outlined"
                onClick={() => go(String(url))}
                className="stat-link"
              >
                <Statistic title={title} value={value} />
              </ProCard>
            </Col>
          ))}
        </Row>
        <ProCard
          title="触碰统计"
          subTitle="只计有效事件，配置核验不计入"
          variant="outlined"
        >
          <ProForm
            initialValues={filter}
            layout="inline"
            onFinish={async (v: any) => {
              setFilter(v);
              saveQuery({ ...v, view });
            }}
            submitter={{
              searchConfig: { submitText: "应用筛选" },
              resetButtonProps: false,
            }}
          >
            <ProFormSelect
              name="scope"
              label="统计口径"
              width={200}
              options={[
                { value: "sold", label: "售出后的有效触碰" },
                { value: "all", label: "全生命周期有效触碰" },
              ]}
            />
            <ProFormSelect
              name="range"
              label="时间范围"
              width={150}
              options={[
                { value: "7d", label: "近7日（含今天）" },
                { value: "30d", label: "近30日（含今天）" },
                { value: "all", label: "累计" },
              ]}
            />
            <ProFormSelect
              name="styleId"
              label="款式"
              width={180}
              allowClear
              options={d.styles.map((x) => ({ value: x.id, label: x.name }))}
            />
            <ProFormSelect
              name="issueId"
              label="发行"
              width={200}
              allowClear
              options={d.issues.map((x) => ({ value: x.id, label: x.name }))}
            />
          </ProForm>
          <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
            已生效：
            {filter.scope === "sold"
              ? "已确认售出身份，且触碰时间不早于首次售出"
              : "全部身份的全生命周期"}{" "}
            ·{" "}
            {filter.range === "all"
              ? "累计"
              : filter.range === "7d"
                ? "近7日"
                : "近30日"}{" "}
            · 北京时间 · 截至{timeText(new Date().toISOString())}
            。售出与认领分别统计。
          </Typography.Paragraph>
          <Row gutter={[24, 16]}>
            {[
              ["已确认售出物品", s.sold],
              ["有效触碰次数", s.total],
              ["被触碰物品数", s.touched],
              ["已认领物品", s.claimed],
              ["当前持有人", s.owners],
            ].map(([title, value]) => (
              <Col flex="1" key={title}>
                <Statistic title={title} value={value} />
              </Col>
            ))}
          </Row>
        </ProCard>
        <ProCard title="有效触碰日趋势" variant="outlined">
          {s.daily.length ? (
            <div
              className="trend"
              role="img"
              aria-label="按北京时间汇总的有效触碰日趋势"
            >
              {s.daily.map((x) => (
                <Tooltip key={x.date} title={x.date + " · " + x.count + "次"}>
                  <div className="trend-day">
                    <span>{x.count}</span>
                    <div
                      className="trend-bar"
                      style={{ height: Math.max(2, (x.count / max) * 110) }}
                    />
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
            dataSource={s.rows.map((r) => ({ id: r.item.id, ...r }))}
            pagination={{ pageSize: 10, showSizeChanger: false }}
            columns={[
              {
                title: "数字物品",
                render: (_, r) => (
                  <Button type="link" onClick={() => go("/items/" + r.id)}>
                    {r.item.uid}
                  </Button>
                ),
              },
              {
                title: "发行编号",
                render: (_, r) =>
                  edition(
                    r.item,
                    d.issues.find((x) => x.id === r.item.issueId),
                  ),
              },
              {
                title: "售出确认",
                render: (_, r) => (
                  <Tag color={r.item.sold ? "blue" : "default"}>
                    {r.item.sold ? "已确认售出" : "未确认售出"}
                  </Tag>
                ),
              },
              { title: "持有人", render: (_, r) => userName(r.item.ownerId) },
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
              { title: "稳定账户", dataIndex: "id" },
              { title: "持有人", dataIndex: "name" },
              { title: "当前持有", render: (_, r) => r.items.length + "件" },
              {
                title: "物品档案",
                render: (_, r) => (
                  <Space wrap>
                    {r.items.map((i) => (
                      <Button
                        key={i.id}
                        type="link"
                        onClick={() => go("/items/" + i.id)}
                      >
                        {i.uid}
                      </Button>
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
    </PageContainer>
  );
}
