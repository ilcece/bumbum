import React, { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Space } from "antd";
import { history, useLocation } from "@umijs/max";
import { useStore } from "./data/store";
export const required = [
  { required: true, whitespace: true, message: "请填写已核对的信息" },
];
export function useAction() {
  const p = useStore(),
    { message } = App.useApp(),
    [error, setError] = useState(""),
    [unknown, setUnknown] = useState(false);
  const run = (type: string, payload: any, success = "已保存") => {
    if (unknown) return false;
    const r = p.run(type, payload);
    if (!r.ok) {
      setError(r.error);
      setUnknown(p.failure === "unknown");
      return false;
    }
    setError("");
    message.success(success);
    return true;
  };
  return {
    run,
    unknown,
    clear: () => {
      setError("");
      setUnknown(false);
    },
    feedback: error ? (
      <Alert
        showIcon
        type="warning"
        title={error}
        action={
          <Button
            onClick={() => {
              p.setFailure("none");
              setUnknown(false);
              setError("已核对：本次演示未写入，输入保留，可明确重试。");
            }}
          >
            核对保存结果
          </Button>
        }
      />
    ) : null,
  };
}
export function useUnsaved(save?: () => Promise<boolean>) {
  const { modal } = App.useApp(),
    dirty = useRef(false),
    saver = useRef(save);
  saver.current = save;
  const [isDirty, setIsDirty] = useState(false);
  const setDirty = (v: boolean) => {
    dirty.current = v;
    setIsDirty(v);
  };
  useEffect(() => {
    let active = true;
    let unblock = () => {};
    const retry = (tx: any) => {
      unblock();
      tx.retry();
      // 保存后的同页地址替换不会卸载组件，继续保护后续编辑。
      queueMicrotask(() => {
        if (active) unblock = history.block(handle);
      });
    };
    const handle = (tx: any) => {
      if (!dirty.current) {
        retry(tx);
        return;
      }
      let popup: any;
      popup = modal.confirm({
        title: "尚有未保存的修改",
        content: "已保存的记录会保留，选择如何离开。",
        footer: () => (
          <Space>
            <Button onClick={() => popup.destroy()}>继续编辑</Button>
            <Button
              onClick={() => {
                setDirty(false);
                popup.destroy();
                retry(tx);
              }}
            >
              放弃并继续
            </Button>
            {saver.current && (
              <Button
                type="primary"
                onClick={async () => {
                  if (await saver.current!()) {
                    setDirty(false);
                    popup.destroy();
                    retry(tx);
                  }
                }}
              >
                保存后继续
              </Button>
            )}
          </Space>
        ),
      });
    };
    unblock = history.block(handle);
    const unload = (e: BeforeUnloadEvent) => {
      if (dirty.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", unload);
    return () => {
      active = false;
      unblock();
      window.removeEventListener("beforeunload", unload);
    };
  }, []);
  return { isDirty, setDirty };
}
export function useReturnPath(fallback: string) {
  const location = useLocation();
  const from = (location.state as any)?.from;
  return typeof from === "string" &&
    from.startsWith("/") &&
    !from.startsWith("//")
    ? from
    : fallback;
}
export const go = (path: string) =>
  history.push(path, {
    from: history.location.pathname + history.location.search,
  });
export const back = (path: string) => history.push(path);
export const localDate = (v?: string) =>
  v ? new Date(Date.parse(v) + 8 * 3600000).toISOString().slice(0, 16) : "";
export const dateISO = (v: any) =>
  !v
    ? undefined
    : typeof v === "string" && !/[zZ]|[+]\d\d:\d\d$/.test(v)
      ? new Date(v.replace(" ", "T") + "+08:00").toISOString()
      : new Date(v).toISOString();
// 仅为合成数据适配官方查询表格；正式整合替换为服务端全量查询。
export function tableRequest<T extends { id: string | number }>(
  rows: T[],
  params: any,
  text: (row: T) => string,
  checks?: (row: T, params: any) => boolean,
) {
  const result = rows.filter(
    (r) =>
      (!params.keyword ||
        text(r).toLowerCase().includes(String(params.keyword).toLowerCase())) &&
      (!checks || checks(r, params)),
  );
  const page = params.current || 1,
    size = Math.min(10, params.pageSize || 10);
  return Promise.resolve({
    data: result.slice((page - 1) * size, page * size),
    total: result.length,
    success: true,
  });
}
export function queryState() {
  const q = new URLSearchParams(history.location.search);
  return Object.fromEntries(q.entries());
}
export function saveQuery(p: any) {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(p))
    if (value != null && value !== "" && !["rev", "pageSize"].includes(key))
      q.set(key, String(value));
  history.replace({
    pathname: history.location.pathname,
    search: q.toString() ? "?" + q : "",
  });
}
export function ErrorState() {
  const p = useStore();
  return (
    <Alert
      type="error"
      showIcon
      title="读取失败，已保存记录仍保留"
      action={<Button onClick={() => p.setReadError(false)}>重试读取</Button>}
    />
  );
}
export function useDataTable() {
  const { data } = useStore();
  const q = queryState();
  return {
    params: { rev: data.revision },
    form: { initialValues: q },
    pagination: {
      defaultCurrent: Number(q.current) || 1,
      pageSize: 10,
      showSizeChanger: false,
    },
    onSubmit: (v: any) =>
      saveQuery({ tab: queryState().tab, ...v, current: 1 }),
    onReset: () => saveQuery({ tab: queryState().tab }),
    onChange: (p: any) => saveQuery({ ...queryState(), current: p.current }),
    search: { labelWidth: "auto" as const },
    options: { density: true, fullScreen: false, reload: true },
  };
}
