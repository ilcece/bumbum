import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, createItem, listItems } from "./api";
import type { ItemList, ItemQuery } from "./api";
import { EntryDialog, PageHeading, UnavailableButton } from "./AdminUI";
import { ItemProfileEditor } from "./ItemProfileEditor";

const INITIAL: ItemQuery = { page: 1, project: "", status: "", keyword: "" };
const PROJECTS = { fashion: "服装", jewelry: "饰品" };
const STATUSES = {
  draft: "草稿",
  active: "启用",
  disabled: "停用",
  archived: "归档",
};

export function ItemPanel({
  onSessionExpired,
  registerLeave,
}: {
  onSessionExpired: () => void;
  registerLeave: (guard: () => boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [project, setProject] = useState("");
  const [uid, setUid] = useState("");
  const [sku, setSku] = useState("");
  const [filters, setFilters] = useState<ItemQuery>(INITIAL);
  const [query, setQuery] = useState<ItemQuery>(INITIAL);
  const [list, setList] = useState<ItemList | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState("");
  const [createError, setCreateError] = useState("");
  const [listError, setListError] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const guard = useRef({ dirty: false, busy: false });
  const onGuard = useCallback((dirty: boolean, busy: boolean) => {
    guard.current = { dirty, busy };
  }, []);
  const onSaved = useCallback(() => {
    setCreated("");
    setQuery((current) => ({ ...current }));
  }, []);

  useEffect(() => {
    registerLeave(() => {
      if (saving || guard.current.busy) return false;
      if (
        (guard.current.dirty || (open && !!(uid || sku))) &&
        !window.confirm("有未保存修改，是否放弃？")
      )
        return false;
      return true;
    });
  }, [saving, open, uid, sku, registerLeave]);
  useEffect(() => {
    if (!open || (!uid && !sku && !saving)) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [open, uid, sku, saving]);
  function closeEntry(next: boolean) {
    if (!next && saving) return;
    if (
      !next &&
      (uid || sku) &&
      !window.confirm("有未保存的物品创建输入，是否放弃？")
    )
      return;
    setOpen(next);
    if (!next) {
      setUid("");
      setSku("");
    }
  }

  function leaveEditor() {
    if (guard.current.busy) return false;
    if (guard.current.dirty && !window.confirm("有未保存修改，是否放弃？"))
      return false;
    setEditing(null);
    guard.current = { dirty: false, busy: false };
    return true;
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setListError("");
    listItems(query)
      .then((result) => {
        if (!cancelled) setList(result);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401)
          onSessionExpired();
        else
          setListError(
            error instanceof ApiError
              ? error.message
              : "物品列表暂时无法读取，请重新查询。",
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
    if (!leaveEditor()) return;
    setSaving(true);
    setCreated("");
    setCreateError("");
    try {
      const item = await createItem(project, uid, sku.trim() || null);
      setCreated(item.item_uid);
      setUid("");
      setSku("");
      setOpen(false);
      // 创建表单与列表筛选独立；成功后清除筛选并刷新第一页。
      setFilters({ ...INITIAL });
      setQuery({ ...INITIAL });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onSessionExpired();
      else if (error instanceof ApiError && error.code === "csrf_failed")
        setCreateError(
          "操作口令已失效，请刷新页面后重新提交；未自动重发创建请求。",
        );
      else
        setCreateError(
          error instanceof ApiError
            ? error.message
            : "创建结果暂时无法确认，请先按物品编号查询，再决定是否重试。",
        );
    } finally {
      setSaving(false);
    }
  }

  const prefix = project === "jewelry" ? "JEW" : "FASH";
  return (
    <section className="item-panel" aria-labelledby="items-title">
      <PageHeading
        title="物品管理"
        subtitle="创建物品身份，维护服装资料及启停。"
        action={
          <button
            className="action action-primary"
            onClick={() => {
              if (leaveEditor()) {
                setCreateError("");
                setOpen(true);
              }
            }}
          >
            创建物品
          </button>
        }
      />
      <h2 id="items-title" className="sr-only">
        物品草稿与服装资料管理
      </h2>
      <p>
        先建立物品编号，再编辑服装资料及启停；芯片绑定和写卡后续接入。草稿或启用均不表示可以出厂。
      </p>
      <EntryDialog
        open={open}
        title="创建物品草稿"
        description="手动填写编号，先建立身份，再补充资料。"
        onChange={closeEntry}
      >
        <form
          onSubmit={(event) => void submit(event)}
          aria-label="创建物品草稿"
        >
          <fieldset disabled={saving}>
            <label>
              所属项目
              <select
                aria-label="所属项目"
                value={project}
                onChange={(event) => setProject(event.target.value)}
                required
              >
                <option value="">请选择</option>
                <option value="fashion">服装</option>
                <option value="jewelry">饰品</option>
              </select>
            </label>
            <label>
              物品编号
              <input
                value={uid}
                onChange={(event) => setUid(event.target.value)}
                placeholder={`${prefix}-2026-000001`}
                maxLength={64}
                required
              />
            </label>
            <p>
              格式：{prefix}
              -YYYY-NNNNNN，ASCII大写前缀、4位年份、6位序号；编号由你填写，全系统不能重复。
            </p>
            <label>
              款式编号（可选，可重复）
              <input
                value={sku}
                onChange={(event) => setSku(event.target.value)}
                maxLength={64}
              />
            </label>
            <button type="submit">{saving ? "正在创建…" : "创建草稿"}</button>
          </fieldset>
        </form>
        {createError && (
          <p className="notice" role="alert">
            {createError}
          </p>
        )}
      </EntryDialog>
      {created && (
        <div className="success-notice" role="status">
          <strong>草稿创建成功：{created}</strong>
          <p>状态为草稿，基础资料未填写。列表已清除筛选并刷新第一页。</p>
        </div>
      )}
      {!open && createError && (
        <p className="notice" role="alert">
          {createError}
        </p>
      )}
      <form
        className="item-filters"
        aria-label="物品列表筛选"
        onSubmit={(event) => {
          event.preventDefault();
          if (leaveEditor()) setQuery({ ...filters, page: 1 });
        }}
      >
        <label>
          物品编号或款式编号关键词
          <input
            value={filters.keyword}
            onChange={(event) =>
              setFilters({ ...filters, keyword: event.target.value })
            }
            maxLength={128}
          />
        </label>
        <label>
          筛选物品项目
          <select
            aria-label="筛选物品项目"
            value={filters.project}
            onChange={(event) =>
              setFilters({ ...filters, project: event.target.value })
            }
          >
            <option value="">全部项目</option>
            <option value="fashion">服装</option>
            <option value="jewelry">饰品</option>
          </select>
        </label>
        <label>
          筛选物品状态
          <select
            aria-label="筛选物品状态"
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
          查询物品
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => {
            if (leaveEditor()) {
              setFilters({ ...INITIAL });
              setQuery({ ...INITIAL });
            }
          }}
        >
          查看全部物品
        </button>
      </form>
      <div className="panel table-panel">
        <div className="panel-head">
          <h2>全部物品</h2>
          <UnavailableButton>导出</UnavailableButton>
        </div>
        {listError && (
          <p className="notice" role="alert">
            {listError}
          </p>
        )}
        {loading ? (
          <p>正在读取物品列表…</p>
        ) : (
          !listError &&
          list && (
            <>
              <p>共 {list.total} 件物品，按创建记录ID从新到旧排列。</p>
              {list.items.length === 0 ? (
                <p>没有符合条件的物品。</p>
              ) : (
                <div className="table-scroll">
                  <table>
                    <caption>物品列表</caption>
                    <thead>
                      <tr>
                        <th scope="col">物品编号</th>
                        <th scope="col">名称</th>
                        <th scope="col">项目</th>
                        <th scope="col">款式编号</th>
                        <th scope="col">状态</th>
                        <th scope="col">创建时间</th>
                        <th scope="col">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {list.items.map((item) => (
                        <tr key={item.id}>
                          <td>{item.item_uid}</td>
                          <td>
                            {typeof item.profile?.name === "string"
                              ? item.profile.name
                              : "未填写"}
                          </td>
                          <td>{PROJECTS[item.project]}</td>
                          <td>{item.sku_code || "—"}</td>
                          <td>{STATUSES[item.status]}</td>
                          <td>
                            {item.created_at
                              ? new Date(item.created_at).toLocaleString(
                                  "zh-CN",
                                  { hour12: false },
                                )
                              : "—"}
                          </td>
                          <td>
                            {item.project === "fashion" &&
                            item.status !== "archived" ? (
                              <button
                                type="button"
                                disabled={saving}
                                onClick={() => {
                                  if (editing !== item.id && leaveEditor())
                                    setEditing(item.id);
                                }}
                              >
                                编辑资料
                              </button>
                            ) : (
                              "—"
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="actions" aria-label="物品分页">
                <button
                  type="button"
                  disabled={query.page === 1}
                  onClick={() => {
                    if (leaveEditor())
                      setQuery({ ...query, page: query.page - 1 });
                  }}
                >
                  上一页
                </button>
                <span>第 {query.page} 页</span>
                <button
                  type="button"
                  disabled={query.page * list.page_size >= list.total}
                  onClick={() => {
                    if (leaveEditor())
                      setQuery({ ...query, page: query.page + 1 });
                  }}
                >
                  下一页
                </button>
              </div>
            </>
          )
        )}
      </div>
      {editing !== null && (
        <ItemProfileEditor
          key={editing}
          id={editing}
          onClose={() => {
            leaveEditor();
          }}
          onGuard={onGuard}
          onSaved={onSaved}
          onSessionExpired={onSessionExpired}
        />
      )}
    </section>
  );
}
