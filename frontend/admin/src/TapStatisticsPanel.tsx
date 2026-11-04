import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  ApiError,
  listTapStats,
  normalizeStatsKeyword,
  type TapStats,
  type TapStatsQuery,
} from "./api";
import { TapDailyChart } from "./TapDailyChart";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Typography,
} from "antd";

const DEFAULT: TapStatsQuery = { project: "", range: "7d", q: "", page: 1 };
type Kind = "initial" | "scope" | "search" | "clear" | "page" | "refresh";
type Intent = { query: TapStatsQuery; kind: Kind };
const PROJECT = { fashion: "服装", jewelry: "饰品" };
const RANGE = { "7d": "近7天", "30d": "近30天", all: "累计" };
const projectText = (project: TapStatsQuery["project"]) =>
  project ? PROJECT[project] : "全部项目";
const label = (query: TapStatsQuery) =>
  `${projectText(query.project)}／${RANGE[query.range]}${query.q ? `／明细关键词：${query.q}` : ""}／第${query.page}页`;
const timeText = (value: string) =>
  new Date(value).toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour12: false,
  });

export function TapStatisticsPanel({
  onSessionExpired,
}: {
  onSessionExpired: () => void;
}) {
  const id = useId();
  const [project, setProject] = useState<TapStatsQuery["project"]>("");
  const [range, setRange] = useState<TapStatsQuery["range"]>("7d");
  const [keyword, setKeyword] = useState("");
  const [data, setData] = useState<TapStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [failure, setFailure] = useState<{
    intent: Intent;
    message: string;
  } | null>(null);
  const [inputError, setInputError] = useState("");
  const busy = useRef(false);
  const mounted = useRef(false);
  const sequence = useRef(0);
  const load = useCallback(
    async (intent: Intent) => {
      if (busy.current) return;
      const ticket = ++sequence.current;
      busy.current = true;
      setLoading(true);
      setFailure(null);
      setInputError("");
      try {
        const result = await listTapStats(intent.query);
        if (!mounted.current || ticket !== sequence.current) return;
        setData(result);
        if (intent.kind === "initial" || intent.kind === "scope") {
          setProject(result.filters.project || "");
          setRange(result.filters.range);
          setKeyword("");
        } else if (intent.kind === "search" || intent.kind === "clear")
          setKeyword(result.filters.q);
      } catch (error) {
        if (!mounted.current || ticket !== sequence.current) return;
        if (error instanceof ApiError && error.status === 401) {
          setData(null);
          setFailure(null);
          onSessionExpired();
        } else
          setFailure({
            intent,
            message:
              error instanceof Error
                ? error.message
                : "触碰统计读取失败，请重试。",
          });
      } finally {
        if (mounted.current && ticket === sequence.current) {
          busy.current = false;
          setLoading(false);
        }
      }
    },
    [onSessionExpired],
  );
  useEffect(() => {
    mounted.current = true;
    void load({ query: { ...DEFAULT }, kind: "initial" });
    return () => {
      mounted.current = false;
      sequence.current++;
      busy.current = false;
    };
  }, [load]);
  const applied: TapStatsQuery = data
    ? {
        project: data.filters.project || "",
        range: data.filters.range,
        q: data.filters.q,
        page: data.page,
      }
    : { ...DEFAULT };
  const scopeDirty =
    !!data &&
    ((project !== data.filters.project &&
      !(project === "" && data.filters.project === null)) ||
      range !== data.filters.range);
  const keywordDirty =
    !!data && normalizeStatsKeyword(keyword) !== data.filters.q;
  function search() {
    if (Array.from(keyword).length > 128) {
      setInputError("关键词最多128个字符。");
      return;
    }
    void load({
      query: { ...applied, q: normalizeStatsKeyword(keyword), page: 1 },
      kind: "search",
    });
  }
  return (
    <section aria-label="有效触碰统计" aria-busy={loading}>
      <Card
        title="有效触碰统计"
        extra={
          <Button
            disabled={loading || !data}
            onClick={() => void load({ query: applied, kind: "refresh" })}
          >
            刷新统计
          </Button>
        }
      >
        <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
          <Form
            layout="inline"
            disabled={loading}
            onFinish={() =>
              void load({
                query: { project, range, q: "", page: 1 },
                kind: "scope",
              })
            }
            style={{ rowGap: 12 }}
          >
            <Form.Item label="统计项目" htmlFor={`${id}-project`}>
              <Select
                id={`${id}-project`}
                value={project}
                onChange={setProject}
                style={{ width: 180 }}
                options={[
                  { value: "", label: "全部项目" },
                  { value: "fashion", label: "服装" },
                  { value: "jewelry", label: "饰品" },
                ]}
              />
            </Form.Item>
            <Form.Item label="统计时间" htmlFor={`${id}-range`}>
              <Select
                id={`${id}-range`}
                value={range}
                onChange={setRange}
                style={{ width: 180 }}
                options={[
                  { value: "7d", label: "近7天" },
                  { value: "30d", label: "近30天" },
                  { value: "all", label: "累计" },
                ]}
              />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit">
                查询统计
              </Button>
            </Form.Item>
          </Form>
          {scopeDirty && (
            <Typography.Text type="warning">
              筛选条件已修改，点击查询统计生效。
            </Typography.Text>
          )}
          {loading && (
            <div role="status">
              正在读取触碰统计；已有内容仍为上次成功结果。
            </div>
          )}
          {failure && (
            <Alert
              type="error"
              showIcon
              title="触碰统计读取失败"
              description={
                <>
                  {failure.message}
                  <br />
                  失败请求：{label(failure.intent.query)}
                </>
              }
              action={
                <Button
                  disabled={loading}
                  onClick={() => void load(failure.intent)}
                >
                  重试
                </Button>
              }
            />
          )}
          {data ? (
            <>
              <div aria-label="当前统计条件">
                <Typography.Paragraph style={{ marginBottom: 4 }}>
                  当前统计：{projectText(applied.project)}／
                  {RANGE[applied.range]}／
                  {data.period.from_date
                    ? `${data.period.from_date} 至 ${data.period.to_date}`
                    : "尚无起始记录"}
                </Typography.Paragraph>
                <Typography.Text type="secondary">
                  {failure || loading ? "上次成功结果；" : ""}数据截至：
                  {timeText(data.as_of)}（北京时间）
                </Typography.Text>
              </div>
              {data.page_adjusted && (
                <div role="status">结果页数已变化，已调整到当前有效页。</div>
              )}
              <Row gutter={16}>
                <Col span={12}>
                  <Card size="small">
                    <Statistic
                      title="有效触碰次数"
                      value={data.summary.valid_taps}
                      valueRender={(node) => (
                        <output aria-label="有效触碰次数">{node}</output>
                      )}
                    />
                  </Card>
                </Col>
                <Col span={12}>
                  <Card size="small">
                    <Statistic
                      title="被触碰物品数"
                      value={data.summary.touched_items}
                      valueRender={(node) => (
                        <output aria-label="被触碰物品数">{node}</output>
                      )}
                    />
                  </Card>
                </Col>
              </Row>
              <Typography.Text type="secondary">
                仅统计已记录的有效验证，非独立用户数、非售后专属统计。
              </Typography.Text>
              <TapDailyChart
                key={`${data.filters.project}-${data.filters.range}-${data.as_of}`}
                daily={data.daily}
                today={data.period.to_date}
              />
              <Typography.Title level={5} style={{ margin: 0 }}>
                物品触碰明细
              </Typography.Title>
              <Typography.Text type="secondary">
                关键词仅筛选下方明细，不影响上方指标与趋势；本表只列发生过有效触碰的物品。
              </Typography.Text>
              <Form
                layout="inline"
                disabled={loading}
                onFinish={search}
                style={{ rowGap: 12 }}
              >
                <Form.Item
                  label="物品编号或名称"
                  htmlFor={`${id}-q`}
                  validateStatus={inputError ? "error" : undefined}
                  help={
                    inputError ? (
                      <span role="alert">{inputError}</span>
                    ) : undefined
                  }
                >
                  <Input
                    id={`${id}-q`}
                    value={keyword}
                    placeholder="输入编号或当前名称"
                    style={{ width: 280 }}
                    onChange={(event) => {
                      setKeyword(event.target.value);
                      setInputError("");
                    }}
                  />
                </Form.Item>
                <Form.Item>
                  <Space>
                    <Button htmlType="submit">查询物品</Button>
                    <Button
                      onClick={() =>
                        void load({
                          query: { ...applied, q: "", page: 1 },
                          kind: "clear",
                        })
                      }
                    >
                      清空
                    </Button>
                  </Space>
                </Form.Item>
              </Form>
              {keywordDirty && (
                <Typography.Text type="warning">
                  明细关键词已修改，尚未查询。
                </Typography.Text>
              )}
              {data.filters.q && (
                <Typography.Text>
                  当前明细关键词：{data.filters.q}
                </Typography.Text>
              )}
              <Table
                rowKey="item_uid"
                size="middle"
                dataSource={data.items}
                pagination={false}
                scroll={{ x: 900 }}
                locale={{
                  emptyText: data.filters.q
                    ? "没有匹配的物品"
                    : "所选时间没有被有效触碰的物品",
                }}
                columns={[
                  {
                    title: "项目",
                    dataIndex: "project",
                    width: 90,
                    render: (value: keyof typeof PROJECT) => PROJECT[value],
                  },
                  { title: "物品编号", dataIndex: "item_uid", width: 200 },
                  {
                    title: "名称",
                    dataIndex: "name",
                    render: (value: string | null) => value || "未填写",
                  },
                  {
                    title: "有效触碰次数",
                    dataIndex: "valid_taps",
                    width: 130,
                    render: (value: number) => value.toLocaleString("zh-CN"),
                  },
                  {
                    title: "最近触碰时间（北京时间）",
                    dataIndex: "last_tap_at",
                    width: 230,
                    render: timeText,
                  },
                ]}
              />
              <Space wrap>
                <Typography.Text>
                  共{data.total_items.toLocaleString("zh-CN")}件
                  {data.total_pages
                    ? `／第${data.page}页，共${data.total_pages}页`
                    : ""}
                </Typography.Text>
                <Button
                  disabled={loading || data.page <= 1}
                  onClick={() =>
                    void load({
                      query: { ...applied, page: data.page - 1 },
                      kind: "page",
                    })
                  }
                >
                  上一页
                </Button>
                <Button
                  disabled={loading || data.page >= data.total_pages}
                  onClick={() =>
                    void load({
                      query: { ...applied, page: data.page + 1 },
                      kind: "page",
                    })
                  }
                >
                  下一页
                </Button>
              </Space>
              <Typography.Text type="secondary">
                {data.first_recorded_at
                  ? `所选项目首条有效记录时间：${timeText(data.first_recorded_at)}（北京时间）。`
                  : "所选项目尚无有效记录。"}
                首条记录不代表上线或交付时间；更早行为不推算。
              </Typography.Text>
            </>
          ) : (
            <Typography.Text type="secondary">
              {loading
                ? "指标、趋势和明细正在读取…"
                : "尚未获得有效统计结果，请查询或重试。"}
            </Typography.Text>
          )}
          <Typography.Text type="secondary">
            不含后台配置核验、重复请求及失败；重复查看资料不增加次数。项目和物品归属按触碰发生时保留。
          </Typography.Text>
        </Space>
      </Card>
    </section>
  );
}
