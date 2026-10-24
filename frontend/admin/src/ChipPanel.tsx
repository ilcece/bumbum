import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, listChips, readSession, registerChip } from "./api";
import type { ChipList, ChipQuery } from "./api";

const INITIAL_QUERY: ChipQuery = { page: 1, project: "", status: "", keyword: "" };
const PROJECTS = { fashion: "服装", jewelry: "饰品" };
const STATUSES = { pending: "待绑定", bound: "已绑定", disabled: "已停用", lost: "已丢失" };

export function ChipPanel({ onSessionExpired }: { onSessionExpired: () => void }) {
  const [query, setQuery] = useState<ChipQuery>(INITIAL_QUERY);
  const [filters, setFilters] = useState(INITIAL_QUERY);
  const [list, setList] = useState<ChipList | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    listChips(query).then(result => {
      if (!cancelled) setList(result);
    }).catch((failure: unknown) => {
      if (cancelled) return;
      if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
      else setError(failure instanceof ApiError ? failure.message : "芯片列表暂时无法读取，请重新查询。");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [query, onSessionExpired]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const batch = String(values.get("batch_no")).trim();
    setSaving(true);
    setNotice("");
    setError("");
    try {
      const result = await registerChip(String(values.get("chip_uid")), String(values.get("project")), batch || null);
      setNotice(result.is_new ? `登记成功：${result.chip.chip_uid}，状态为待绑定。` : "该芯片已经登记，已定位原记录；项目、批次和状态保持不变。");
      const next = { ...INITIAL_QUERY, keyword: result.chip.chip_uid };
      setFilters(next);
      setQuery(next);
      (form.elements.namedItem("chip_uid") as HTMLInputElement).value = "";
      (form.elements.namedItem("batch_no") as HTMLInputElement).value = "";
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) onSessionExpired();
      else if (failure instanceof ApiError && failure.code === "csrf_failed") {
        try {
          await readSession();
          setError("操作口令已更新，请再点一次登记。");
        } catch (refreshFailure) {
          if (refreshFailure instanceof ApiError && refreshFailure.status === 401) onSessionExpired();
          else setError("登录状态暂时无法更新，请稍后重试。");
        }
      } else setError(failure instanceof ApiError ? failure.message : "登记结果暂时无法确认，可先按UID查询，再决定是否重试。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="chip-panel" aria-labelledby="chips-title">
      <h2 id="chips-title">芯片登记与列表</h2>
      <p>先登记UID、项目和可选批次。登记不会生成密钥或向芯片写入内容。</p>
      <form onSubmit={event => void submit(event)} aria-label="芯片登记表单">
        <fieldset disabled={saving}>
          <label>芯片UID<input name="chip_uid" placeholder="04:A2:7F:1B:5E:80:00" maxLength={64} required /></label>
          <label>所属项目<select name="project" aria-label="所属项目"><option value="fashion">服装</option><option value="jewelry">饰品</option></select></label>
          <label>批次（可选）<input name="batch_no" maxLength={64} /></label>
          <button type="submit">{saving ? "正在登记…" : "登记芯片"}</button>
        </fieldset>
      </form>
      {notice && <p className="success-notice" role="status">{notice}</p>}
      <form className="chip-filters" aria-label="芯片筛选" onSubmit={event => { event.preventDefault(); setQuery({ ...filters, page: 1 }); }}>
        <label>UID关键词<input value={filters.keyword} maxLength={128} onChange={event => setFilters({ ...filters, keyword: event.target.value })} /></label>
        <label>筛选项目<select aria-label="筛选项目" value={filters.project} onChange={event => setFilters({ ...filters, project: event.target.value })}><option value="">全部项目</option><option value="fashion">服装</option><option value="jewelry">饰品</option></select></label>
        <label>筛选状态<select aria-label="筛选状态" value={filters.status} onChange={event => setFilters({ ...filters, status: event.target.value })}><option value="">全部状态</option>{Object.entries(STATUSES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <button type="submit" disabled={loading}>查询</button>
        <button type="button" disabled={loading} onClick={() => { setFilters(INITIAL_QUERY); setQuery({ ...INITIAL_QUERY }); }}>查看全部</button>
      </form>
      {error && <p className="notice" role="alert">{error}</p>}
      {loading ? <p>正在读取芯片列表…</p> : !error && list && <>
        <p>共 {list.total} 枚芯片，按登记时间从新到旧排列。</p>
        {list.items.length === 0 ? <p>没有符合条件的芯片。</p> : <div className="table-scroll"><table>
          <caption>芯片列表</caption>
          <thead><tr><th scope="col">芯片UID</th><th scope="col">项目</th><th scope="col">状态</th><th scope="col">批次</th><th scope="col">登记时间</th></tr></thead>
          <tbody>{list.items.map(chip => <tr key={chip.id}><td>{chip.chip_uid}</td><td>{PROJECTS[chip.project]}</td><td>{STATUSES[chip.chip_status]}</td><td>{chip.batch_no || "—"}</td><td>{new Date(chip.created_at).toLocaleString("zh-CN", { hour12: false })}</td></tr>)}</tbody>
        </table></div>}
        <div className="actions" aria-label="芯片分页">
          <button type="button" disabled={query.page === 1} onClick={() => setQuery({ ...query, page: query.page - 1 })}>上一页</button>
          <span>第 {query.page} 页</span>
          <button type="button" disabled={query.page * list.page_size >= list.total} onClick={() => setQuery({ ...query, page: query.page + 1 })}>下一页</button>
        </div>
      </>}
    </section>
  );
}
