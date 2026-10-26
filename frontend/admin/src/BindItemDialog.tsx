import { useEffect, useRef, useState } from "react";
import { EntryDialog } from "./AdminUI";
import { ApiError, bindChipItem, listChips, listItems } from "./api";
import type { ChipView, ItemList, ItemQuery, ItemView } from "./api";

const PROJECTS = { fashion: "服装", jewelry: "饰品" };
const STATES = {
  draft: "草稿",
  active: "启用",
  disabled: "停用",
  archived: "归档",
};
const safeId = (id: number) => Number.isSafeInteger(id) && id > 0;

export function BindItemDialog({
  chip,
  onClose,
  onBound,
  onSessionExpired,
  onInteraction,
}: {
  chip: ChipView;
  onClose: () => void;
  onBound: (chip: ChipView, recovered: boolean) => void;
  onSessionExpired: () => void;
  onInteraction: (state: { dirty: boolean; busy: boolean }) => void;
}) {
  const [filters, setFilters] = useState({
    project: chip.project || "fashion",
    keyword: "",
  });
  const [query, setQuery] = useState<ItemQuery | null>(null);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<ItemList | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [selected, setSelected] = useState<ItemView | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [sending, setSending] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [unknown, setUnknown] = useState(false);
  const [retryAllowed, setRetryAllowed] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    onInteraction({ dirty: selected !== null, busy: sending || checking });
    return () => onInteraction({ dirty: false, busy: false });
  }, [selected, sending, checking, onInteraction]);

  useEffect(() => {
    if (!query) return;
    let cancelled = false;
    setLoading(true);
    setResult(null);
    setSearchError("");
    listItems(query)
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((failure) => {
        if (cancelled) return;
        if (failure instanceof ApiError && failure.status === 401)
          onSessionExpired();
        else
          setSearchError(
            failure instanceof ApiError
              ? failure.message
              : "候选物品读取失败，请重新查询。",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query, onSessionExpired]);

  function changeFilters(next: typeof filters) {
    setFilters(next);
    setPending(true);
    setSelected(null);
    setConfirmed(false);
    setError("");
  }
  function runQuery(page = 1) {
    setSelected(null);
    setConfirmed(false);
    setPending(false);
    setError("");
    setQuery({ ...filters, status: "", page, unbound_only: true });
  }
  function close() {
    if (inFlight.current) return;
    if (
      selected &&
      !window.confirm(
        unknown
          ? "绑定结果尚未确认，是否关闭并稍后按UID查询？"
          : "已选择物品，是否放弃本次绑定选择？",
      )
    )
      return;
    onClose();
  }
  function reportBusy(busy: boolean) {
    inFlight.current = busy;
    onInteraction({ dirty: selected !== null, busy });
  }
  async function submit() {
    if (
      inFlight.current ||
      !selected ||
      !confirmed ||
      pending ||
      loading ||
      blocked ||
      (unknown && !retryAllowed)
    )
      return;
    if (!safeId(chip.id) || !safeId(selected.id)) {
      setError("记录编号超出当前页面可处理范围，未提交绑定，请反馈。");
      return;
    }
    reportBusy(true);
    setSending(true);
    setError("");
    setRetryAllowed(false);
    try {
      const bound = await bindChipItem(chip.id, selected.id);
      if (mounted.current) {
        onInteraction({ dirty: false, busy: false });
        onBound(bound, false);
      }
    } catch (failure) {
      if (!mounted.current) return;
      if (failure instanceof ApiError && failure.status === 401)
        onSessionExpired();
      else if (failure instanceof ApiError && failure.code === "csrf_failed") {
        setBlocked(true);
        setError("页面防冒用校验失效，请刷新页面后重新核对提交；未自动重发。");
      } else if (
        failure instanceof ApiError &&
        failure.status < 500 &&
        failure.code !== "unexpected_response"
      ) {
        setError(failure.message);
      } else {
        setUnknown(true);
        setConfirmed(false);
        setError(
          `${failure instanceof ApiError ? failure.message + " " : ""}结果尚未确认，请查询此芯片；不会自动重发。`,
        );
      }
    } finally {
      inFlight.current = false;
      if (mounted.current) {
        setSending(false);
        onInteraction({ dirty: selected !== null, busy: false });
      }
    }
  }
  async function verify() {
    if (inFlight.current || !selected) return;
    reportBusy(true);
    setChecking(true);
    setRetryAllowed(false);
    setConfirmed(false);
    try {
      const data = await listChips({
        page: 1,
        project: "",
        status: "",
        keyword: chip.chip_uid,
      });
      if (!mounted.current) return;
      const found = data.items.find(
        (row) => row.id === chip.id && row.chip_uid === chip.chip_uid,
      );
      if (!found) setError("尚未查到该芯片，结果仍未确认，请稍后查询或反馈。");
      else if (found.chip_status === "bound" && found.item_id === selected.id) {
        onInteraction({ dirty: false, busy: false });
        onBound(found, true);
      } else if (found.item_id !== null) {
        setBlocked(true);
        setError(
          `芯片当前关联物品：${found.item_uid || "编号暂不可读"}，状态为${found.chip_status === "bound" ? "已绑定" : "不可绑定"}。与本次目标不符，未覆盖，请反馈。`,
        );
      } else if (found.chip_status !== "pending") {
        setBlocked(true);
        setError("芯片当前已停用或标记丢失，不能提交绑定。");
      } else {
        setRetryAllowed(true);
        setError(
          "目前尚未查到绑定，原请求仍可能处理中。核对原目标并重新勾选后，可手动重试同一目标；不会自动重发。",
        );
      }
    } catch (failure) {
      if (!mounted.current) return;
      if (failure instanceof ApiError && failure.status === 401)
        onSessionExpired();
      else
        setError(
          `${failure instanceof ApiError ? failure.message : "查询失败。"} 绑定结果仍未确认，请稍后再查。`,
        );
    } finally {
      inFlight.current = false;
      if (mounted.current) {
        setChecking(false);
        onInteraction({ dirty: selected !== null, busy: false });
      }
    }
  }

  const busy = sending || checking;
  const canSubmit = Boolean(
    selected &&
      confirmed &&
      !pending &&
      !loading &&
      !busy &&
      !blocked &&
      (!unknown || retryAllowed),
  );
  return (
    <EntryDialog
      open
      title="绑定物品"
      description="绑定只建立关联，不生成密钥或写卡。本版本暂不提供解绑或换绑。"
      onChange={(open) => {
        if (!open) close();
      }}
    >
      <div className="binding-dialog">
        <p>
          芯片UID：<strong>{chip.chip_uid}</strong>
        </p>
        <p>
          当前项目：
          {chip.project
            ? PROJECTS[chip.project]
            : "未分配，绑定时按目标物品确定"}
          ；批次：{chip.batch_no || "未填写"}；状态：待绑定
        </p>
      {!safeId(chip.id) && (
        <p role="alert" className="notice">
          芯片记录编号超出当前页面可处理范围，不能选择物品或提交绑定，请反馈。
        </p>
      )}
        <form
          aria-label="查询绑定候选物品"
          onSubmit={(event) => {
            event.preventDefault();
            if (!busy && !unknown) runQuery();
          }}
        >
          <fieldset disabled={busy || unknown}>
            <label>
              候选项目
              <select
                aria-label="候选项目"
                value={filters.project}
                disabled={chip.project !== null}
                onChange={(event) =>
                  changeFilters({
                    ...filters,
                    project: event.target.value as "fashion" | "jewelry",
                  })
                }
              >
                <option value="fashion">服装</option>
                <option value="jewelry">饰品</option>
              </select>
            </label>
            <label>
              物品关键词
              <input
                maxLength={128}
                value={filters.keyword}
                placeholder="物品编号或款式编号"
                onChange={(event) =>
                  changeFilters({ ...filters, keyword: event.target.value })
                }
              />
            </label>
            <button type="submit">查询物品</button>
          </fieldset>
        </form>
        {pending && (
          <p role="status">条件已改变，请点击“查询物品”；旧结果不可选。</p>
        )}
        {loading && <p role="status">正在查询物品…</p>}
        {searchError && (
          <p role="alert" className="notice">
            {searchError}
          </p>
        )}
        {!query && <p>输入编号或款式后点击查询，也可直接查询所选项目。</p>}
        {result && !searchError && !loading && (
          <>
            <p>共 {result.total} 件未被芯片占用的物品；最终能否绑定以提交时检查为准。</p>
            {result.items.some((item) => !safeId(item.id)) && (
              <p role="alert" className="notice">
                有物品记录编号超出当前页面可处理范围，该行不能选择，请反馈。
              </p>
            )}
            {result.items.length === 0 ? (
              <p>没有符合条件的可绑定物品。</p>
            ) : (
              <div className="table-scroll binding-candidates">
                <table>
                  <caption>绑定候选物品</caption>
                  <thead>
                    <tr>
                      <th>选择</th>
                      <th>项目</th>
                      <th>物品编号</th>
                      <th>款式编号</th>
                      <th>名称</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <input
                            type="radio"
                            name="binding-item"
                            aria-label={`选择物品 ${item.item_uid}`}
                            checked={selected?.id === item.id}
                            disabled={
                              busy ||
                              unknown ||
                              pending ||
                              item.status === "archived" ||
                              !safeId(item.id) ||
                              !safeId(chip.id)
                            }
                            onChange={() => {
                              setSelected(item);
                              setConfirmed(false);
                              setError("");
                            }}
                          />
                          {item.status === "archived"
                            ? "归档不可绑定"
                            : !safeId(item.id)
                              ? "编号无法处理"
                              : ""}
                        </td>
                        <td>{PROJECTS[item.project]}</td>
                        <td>{item.item_uid}</td>
                        <td>{item.sku_code || "—"}</td>
                        <td>
                          {typeof item.profile?.name === "string"
                            ? item.profile.name
                            : "未填写"}
                        </td>
                        <td>{STATES[item.status]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="actions" aria-label="候选物品分页">
              <button
                type="button"
                disabled={
                  busy || unknown || pending || !query || query.page === 1
                }
                onClick={() => runQuery(query!.page - 1)}
              >
                上一页
              </button>
              <span>第 {query?.page} 页</span>
              <button
                type="button"
                disabled={
                  busy ||
                  unknown ||
                  pending ||
                  !query ||
                  query.page * result.page_size >= result.total
                }
                onClick={() => runQuery(query!.page + 1)}
              >
                下一页
              </button>
            </div>
          </>
        )}
        {selected && (
          <div className="binding-confirmation">
            <p>
              核对芯片 <strong>{chip.chip_uid}</strong> →{" "}
              {PROJECTS[selected.project]}物品{" "}
              <strong>{selected.item_uid}</strong>
            </p>
            {chip.project === null && (
              <p>芯片项目将确定为：{PROJECTS[selected.project]}</p>
            )}
            <label>
              <input
                type="checkbox"
                checked={confirmed}
                disabled={busy || blocked || (unknown && !retryAllowed)}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              我已核对芯片与物品编号，理解本版本暂不提供解绑或换绑。
            </label>
          </div>
        )}
        {error && (
          <p role="alert" className="notice">
            {error}
          </p>
        )}
        <div className="actions">
          {unknown && (
            <button type="button" disabled={busy} onClick={() => void verify()}>
              {checking ? "正在查询…" : "查询此芯片"}
            </button>
          )}
          <button
            type="button"
            disabled={!canSubmit}
            onClick={() => void submit()}
          >
            {sending ? "正在绑定…" : unknown ? "重试原目标绑定" : "确认绑定"}
          </button>
          <button type="button" disabled={busy} onClick={close}>
            取消绑定
          </button>
        </div>
      </div>
    </EntryDialog>
  );
}
