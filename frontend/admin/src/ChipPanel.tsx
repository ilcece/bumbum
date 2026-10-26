import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { EntryDialog, PageHeading, UnavailableButton } from "./AdminUI";
import { BindItemDialog } from "./BindItemDialog";
import { ChipKeysDialog } from "./ChipKeysDialog";
import { ApiError, listChips, readSession, registerChip } from "./api";
import type { ChipList, ChipQuery, ChipView } from "./api";

const INITIAL_QUERY: ChipQuery = {
  page: 1,
  project: "",
  status: "",
  keyword: "",
};
const PROJECTS = { fashion: "服装", jewelry: "饰品" };
const SOURCES = {
  unknown: "历史未知",
  manual: "网页手工",
  nfc_cool: "手机扫描",
};
const STATUSES = {
  pending: "待绑定",
  bound: "已绑定",
  disabled: "已停用",
  lost: "已丢失",
};

export function ChipPanel({
  onSessionExpired,
  registerLeave,
}: {
  onSessionExpired: () => void;
  registerLeave: (guard: () => boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [query, setQuery] = useState<ChipQuery>(INITIAL_QUERY);
  const [filters, setFilters] = useState(INITIAL_QUERY);
  const [list, setList] = useState<ChipList | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [registerError, setRegisterError] = useState("");
  const [bindingChip, setBindingChip] = useState<ChipView | null>(null);
  const [keyChip, setKeyChip] = useState<ChipView | null>(null);
  const [bindingState, setBindingState] = useState({
    dirty: false,
    busy: false,
  });
  const bindingRef = useRef(bindingState);
  const reportBinding = useCallback(
    (state: { dirty: boolean; busy: boolean }) => {
      bindingRef.current = state;
      setBindingState(state);
    },
    [],
  );
  function openBinding(chip: ChipView) {
    if (saving || bindingRef.current.busy || bindingChip || keyChip) return;
    if (dirty && !window.confirm("有未保存的芯片登记输入，是否放弃？")) return;
    setOpen(false);
    setDirty(false);
    setBindingChip(chip);
  }
  function bound(chip: ChipView, recovered: boolean) {
    reportBinding({ dirty: false, busy: false });
    setBindingChip(null);
    setNotice(
      `${recovered ? "已查询确认绑定结果" : "绑定成功"}：${chip.chip_uid} → ${chip.item_uid}。绑定不代表写卡完成。`,
    );
    const next = { ...INITIAL_QUERY, keyword: chip.chip_uid };
    setFilters(next);
    setQuery(next);
  }

  function closeEntry(next: boolean) {
    if (!next && saving) return;
    if (!next && dirty && !window.confirm("有未保存的芯片登记输入，是否放弃？"))
      return;
    setOpen(next);
    if (!next) setDirty(false);
  }
  useEffect(() => {
    registerLeave(
      () =>
        !saving &&
        !bindingRef.current.busy &&
        (!dirty || window.confirm("有未保存的芯片登记输入，是否放弃？")) &&
        (!bindingRef.current.dirty ||
          window.confirm(
            "有未完成的绑定选择或待确认结果，是否离开并稍后按UID查询？",
          )),
    );
  }, [saving, dirty, registerLeave]);
  useEffect(() => {
    if (!dirty && !saving && !bindingState.dirty && !bindingState.busy) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, saving, bindingState]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    listChips(query)
      .then((result) => {
        if (!cancelled) setList(result);
      })
      .catch((failure: unknown) => {
        if (cancelled) return;
        if (failure instanceof ApiError && failure.status === 401)
          onSessionExpired();
        else
          setError(
            failure instanceof ApiError
              ? failure.message
              : "芯片列表暂时无法读取，请重新查询。",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query, onSessionExpired]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const batch = String(values.get("batch_no")).trim();
    setSaving(true);
    setNotice("");
    setRegisterError("");
    try {
      const result = await registerChip(
        String(values.get("chip_uid")),
        String(values.get("project")) || null,
        batch || null,
      );
      setNotice(
        result.is_new
          ? `登记成功：${result.chip.chip_uid}，状态为待绑定${result.chip.project === null ? "，项目未分配" : ""}。`
          : "该 UID 已登记，已显示原记录，无需重复登记。项目、批次和状态保持不变。",
      );
      const next = { ...INITIAL_QUERY, keyword: result.chip.chip_uid };
      setFilters(next);
      setQuery(next);
      (form.elements.namedItem("chip_uid") as HTMLInputElement).value = "";
      (form.elements.namedItem("batch_no") as HTMLInputElement).value = "";
      setDirty(false);
      setOpen(false);
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401)
        onSessionExpired();
      else if (failure instanceof ApiError && failure.code === "csrf_failed") {
        try {
          await readSession();
          setRegisterError("操作口令已更新，请再点一次登记。");
        } catch (refreshFailure) {
          if (
            refreshFailure instanceof ApiError &&
            refreshFailure.status === 401
          )
            onSessionExpired();
          else setRegisterError("登录状态暂时无法更新，请稍后重试。");
        }
      } else
        setRegisterError(
          failure instanceof ApiError
            ? failure.message
            : "登记结果暂时无法确认，可先按UID查询，再决定是否重试。",
        );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="chip-panel" aria-labelledby="chips-title">
      <PageHeading
        title="芯片管理"
        subtitle="登记、查询芯片并绑定物品，保留首次登记来源。"
        action={
          <button
            className="action action-primary"
            disabled={bindingChip !== null || keyChip !== null || saving}
            onClick={() => {
              setRegisterError("");
              setOpen(true);
            }}
          >
            登记芯片
          </button>
        }
      />
      <h2 id="chips-title" className="sr-only">
        芯片登记与列表
      </h2>
      <p>
        先登记UID，项目和批次可留空。未分配项目的芯片，绑定物品时确定项目；登记不会生成密钥或写卡。
      </p>
      <EntryDialog
        open={open}
        title="登记新芯片"
        description="登记不会写卡，项目和批次可以留空。"
        onChange={closeEntry}
      >
        <form
          onChange={() => setDirty(true)}
          onSubmit={(event) => void submit(event)}
          aria-label="芯片登记表单"
        >
          <fieldset disabled={saving}>
            <label>
              芯片UID
              <input
                name="chip_uid"
                placeholder="04:A2:7F:1B:5E:80:00"
                maxLength={64}
                required
              />
            </label>
            <label>
              所属项目（可选）
              <select name="project" aria-label="所属项目">
                <option value="">暂不分配</option>
                <option value="fashion">服装</option>
                <option value="jewelry">饰品</option>
              </select>
            </label>
            <label>
              批次（可选）
              <input name="batch_no" maxLength={64} />
            </label>
            <button type="submit">{saving ? "正在登记…" : "登记芯片"}</button>
          </fieldset>
        </form>
        {registerError && (
          <p className="notice" role="alert">
            {registerError}
          </p>
        )}
      </EntryDialog>
      {bindingChip && (
        <BindItemDialog
          key={bindingChip.id}
          chip={bindingChip}
          onClose={() => setBindingChip(null)}
          onBound={bound}
          onSessionExpired={onSessionExpired}
          onInteraction={reportBinding}
        />
      )}
      {keyChip && (
        <ChipKeysDialog
          key={keyChip.id}
          chip={keyChip}
          onClose={() => setKeyChip(null)}
          onSessionExpired={onSessionExpired}
          onInteraction={reportBinding}
          onUpdated={(chip) => {
            setFilters({ ...INITIAL_QUERY, keyword: chip.chip_uid });
            setQuery({ ...INITIAL_QUERY, keyword: chip.chip_uid });
          }}
        />
      )}
      {notice && (
        <p className="success-notice" role="status">
          {notice}
        </p>
      )}
      <form
        className="chip-filters"
        aria-label="芯片筛选"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery({ ...filters, page: 1 });
        }}
      >
        <label>
          UID关键词
          <input
            value={filters.keyword}
            maxLength={128}
            onChange={(event) =>
              setFilters({ ...filters, keyword: event.target.value })
            }
          />
        </label>
        <label>
          筛选项目
          <select
            aria-label="筛选项目"
            value={filters.project}
            onChange={(event) =>
              setFilters({ ...filters, project: event.target.value })
            }
          >
            <option value="">全部项目</option>
            <option value="unassigned">未分配</option>
            <option value="fashion">服装</option>
            <option value="jewelry">饰品</option>
          </select>
        </label>
        <label>
          筛选状态
          <select
            aria-label="筛选状态"
            value={filters.status}
            onChange={(event) =>
              setFilters({ ...filters, status: event.target.value })
            }
          >
            <option value="">全部状态</option>
            {Object.entries(STATUSES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={loading}>
          查询
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => {
            setFilters(INITIAL_QUERY);
            setQuery({ ...INITIAL_QUERY });
          }}
        >
          查看全部
        </button>
      </form>
      {error && (
        <p className="notice" role="alert">
          {error}
        </p>
      )}
      <div className="panel table-panel">
        <div className="panel-head">
          <h2>全部芯片</h2>
          <UnavailableButton>导出</UnavailableButton>
        </div>
        {loading ? (
          <p>正在读取芯片列表…</p>
        ) : (
          !error &&
          list && (
            <>
              <p>共 {list.total} 枚芯片，按登记时间从新到旧排列。</p>
              {list.items.length === 0 ? (
                <p>没有符合条件的芯片。</p>
              ) : (
                <div className="table-scroll">
                  <table>
                    <caption>芯片列表</caption>
                    <thead>
                      <tr>
                        <th scope="col">芯片UID</th>
                        <th scope="col">项目</th>
                        <th scope="col">状态</th>
                        <th scope="col">关联物品</th>
                        <th scope="col">批次</th>
                        <th scope="col">登记来源</th>
                        <th scope="col">密钥／配置</th>
                        <th scope="col">登记时间</th>
                        <th scope="col">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {list.items.map((chip) => (
                        <tr key={chip.id}>
                          <td>{chip.chip_uid}</td>
                          <td>
                            {chip.project === null
                              ? "未分配"
                              : PROJECTS[chip.project]}
                          </td>
                          <td>{STATUSES[chip.chip_status]}</td>
                          <td>{chip.item_uid || "未关联"}</td>
                          <td>{chip.batch_no || "—"}</td>
                          <td>{SOURCES[chip.registration_source]}</td>
                          <td>
                            {chip.keys_generated ? "已生成" : "未生成"}／
                            {chip.provisioned_at ? "已核验" : "未核验"}
                          </td>
                          <td>
                            {new Date(chip.created_at).toLocaleString("zh-CN", {
                              hour12: false,
                            })}
                          </td>
                          <td>
                            {chip.chip_status === "pending" &&
                            chip.item_id === null ? (
                              <button
                                type="button"
                                className="action"
                                disabled={
                                  saving ||
                                  bindingChip !== null ||
                                  keyChip !== null
                                }
                                onClick={() => openBinding(chip)}
                              >
                                绑定物品
                              </button>
                            ) : (
                              <span className="muted-text">
                                {chip.item_id !== null
                                  ? "已有绑定"
                                  : "当前状态不可绑定"}
                              </span>
                            )}
                            {chip.chip_status === "bound" &&
                              chip.item_id !== null && (
                                <button
                                  type="button"
                                  className="action"
                                  disabled={
                                    saving ||
                                    bindingChip !== null ||
                                    keyChip !== null
                                  }
                                  onClick={() => {
                                    if (
                                      dirty &&
                                      !window.confirm(
                                        "有未保存的登记输入，是否放弃？",
                                      )
                                    )
                                      return;
                                    setOpen(false);
                                    setDirty(false);
                                    setKeyChip(chip);
                                  }}
                                >
                                  密钥与配置
                                </button>
                              )}
                            <UnavailableButton>更多</UnavailableButton>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="actions" aria-label="芯片分页">
                <button
                  type="button"
                  disabled={query.page === 1}
                  onClick={() => setQuery({ ...query, page: query.page - 1 })}
                >
                  上一页
                </button>
                <span>第 {query.page} 页</span>
                <button
                  type="button"
                  disabled={query.page * list.page_size >= list.total}
                  onClick={() => setQuery({ ...query, page: query.page + 1 })}
                >
                  下一页
                </button>
              </div>
            </>
          )
        )}
      </div>
    </section>
  );
}
