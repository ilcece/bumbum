import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  ApiError,
  listTapStats,
  normalizeStatsKeyword,
  type TapStats,
  type TapStatsQuery,
} from "./api";
import { TapDailyChart } from "./TapDailyChart";
import { Notice } from "./AdminUI";

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
    <section
      className="panel tap-statistics"
      aria-label="有效触碰统计"
      aria-busy={loading}
    >
      <div className="panel-head">
        <h2>有效触碰统计</h2>
        <button
          className="action"
          disabled={loading || !data}
          onClick={() => void load({ query: applied, kind: "refresh" })}
        >
          刷新统计
        </button>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void load({
            query: { project, range, q: "", page: 1 },
            kind: "scope",
          });
        }}
      >
        <fieldset disabled={loading} className="tap-filter-row">
          <legend className="sr-only">触碰统计范围</legend>
          <div className="tap-filter-field">
            <label htmlFor={`${id}-project`}>统计项目</label>
            <select
              id={`${id}-project`}
              value={project}
              onChange={(event) =>
                setProject(event.target.value as TapStatsQuery["project"])
              }
            >
              <option value="">全部项目</option>
              <option value="fashion">服装</option>
              <option value="jewelry">饰品</option>
            </select>
          </div>
          <div className="tap-filter-field">
            <label htmlFor={`${id}-range`}>统计时间</label>
            <select
              id={`${id}-range`}
              value={range}
              onChange={(event) =>
                setRange(event.target.value as TapStatsQuery["range"])
              }
            >
              <option value="7d">近7天</option>
              <option value="30d">近30天</option>
              <option value="all">累计</option>
            </select>
          </div>
          <button className="action action-primary" type="submit">
            查询统计
          </button>
        </fieldset>
      </form>
      {scopeDirty && (
        <p className="tap-pending">筛选条件已修改，点击查询统计生效。</p>
      )}
      {loading && (
        <p role="status">正在读取触碰统计；已有内容仍为上次成功结果。</p>
      )}
      {failure && (
        <Notice error>
          触碰统计读取失败。{failure.message}
          <br />
          失败请求：{label(failure.intent.query)}
          <button
            className="action"
            disabled={loading}
            onClick={() => void load(failure.intent)}
          >
            重试
          </button>
        </Notice>
      )}
      {data ? (
        <>
          <div className="tap-applied" aria-label="当前统计条件">
            <p>
              当前统计：{projectText(applied.project)}／{RANGE[applied.range]}／
              {data.period.from_date
                ? `${data.period.from_date} 至 ${data.period.to_date}`
                : "尚无起始记录"}
            </p>
            <p>
              {failure || loading ? "上次成功结果；" : ""}数据截至：
              {timeText(data.as_of)}（北京时间）
            </p>
          </div>
          {data.page_adjusted && (
            <p role="status">结果页数已变化，已调整到当前有效页。</p>
          )}
          <div className="tap-summary">
            <article>
              <span>有效触碰次数</span>
              <output aria-label="有效触碰次数">
                {data.summary.valid_taps.toLocaleString("zh-CN")}
              </output>
            </article>
            <article>
              <span>被触碰物品数</span>
              <output aria-label="被触碰物品数">
                {data.summary.touched_items.toLocaleString("zh-CN")}
              </output>
            </article>
          </div>
          <p className="muted-text">
            仅统计已记录的有效验证，非独立用户数、非售后专属统计。
          </p>
          <TapDailyChart
            key={`${data.filters.project}-${data.filters.range}-${data.as_of}`}
            daily={data.daily}
            today={data.period.to_date}
          />
          <h3>物品触碰明细</h3>
          <p className="muted-text">
            关键词仅筛选下方明细，不影响上方指标与趋势；本表只列发生过有效触碰的物品。
          </p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              search();
            }}
          >
            <fieldset className="tap-keyword-row" disabled={loading}>
              <legend className="sr-only">明细关键词查询</legend>
              <label htmlFor={`${id}-q`}>
                物品编号或名称
                <input
                  id={`${id}-q`}
                  value={keyword}
                  placeholder="输入编号或当前名称"
                  onChange={(event) => {
                    setKeyword(event.target.value);
                    setInputError("");
                  }}
                />
              </label>
              <button className="action" type="submit">
                查询物品
              </button>
              <button
                className="action"
                type="button"
                onClick={() =>
                  void load({
                    query: { ...applied, q: "", page: 1 },
                    kind: "clear",
                  })
                }
              >
                清空
              </button>
            </fieldset>
          </form>
          {keywordDirty && (
            <p className="tap-pending">明细关键词已修改，尚未查询。</p>
          )}
          {inputError && (
            <p role="alert" className="notice">
              {inputError}
            </p>
          )}
          {data.filters.q && <p>当前明细关键词：{data.filters.q}</p>}
          <div className="tap-table-scroll">
            <table>
              <caption className="sr-only">物品触碰明细</caption>
              <thead>
                <tr>
                  <th>项目</th>
                  <th>物品编号</th>
                  <th>名称</th>
                  <th>有效触碰次数</th>
                  <th>最近触碰时间（北京时间）</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.item_uid}>
                    <td>{PROJECT[item.project]}</td>
                    <td>{item.item_uid}</td>
                    <td>{item.name || "未填写"}</td>
                    <td>{item.valid_taps.toLocaleString("zh-CN")}</td>
                    <td>{timeText(item.last_tap_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!data.items.length && (
            <p>
              {data.filters.q
                ? "没有匹配的物品"
                : "所选时间没有被有效触碰的物品"}
            </p>
          )}
          <div className="tap-pagination">
            <span>
              共{data.total_items.toLocaleString("zh-CN")}件
              {data.total_pages
                ? `／第${data.page}页，共${data.total_pages}页`
                : ""}
            </span>
            <button
              className="action"
              disabled={loading || data.page <= 1}
              onClick={() =>
                void load({
                  query: { ...applied, page: data.page - 1 },
                  kind: "page",
                })
              }
            >
              上一页
            </button>
            <button
              className="action"
              disabled={loading || data.page >= data.total_pages}
              onClick={() =>
                void load({
                  query: { ...applied, page: data.page + 1 },
                  kind: "page",
                })
              }
            >
              下一页
            </button>
          </div>
          <p className="muted-text">
            {data.first_recorded_at
              ? `所选项目首条有效记录时间：${timeText(data.first_recorded_at)}（北京时间）。`
              : "所选项目尚无有效记录。"}
            首条记录不代表上线或交付时间；更早行为不推算。
          </p>
        </>
      ) : (
        <div className="tap-initial">
          {loading
            ? "指标、趋势和明细正在读取…"
            : "尚未获得有效统计结果，请查询或重试。"}
        </div>
      )}
      <p className="muted-text">
        不含后台配置核验、重复请求及失败；重复查看资料不增加次数。项目和物品归属按触碰发生时保留。
      </p>
    </section>
  );
}
