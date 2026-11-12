import React, { createContext, useContext, useRef, useState } from "react";
import { seed, migrateV5, normalizeWholeItems, operate, Data, Command } from "./domain";
const STORAGE = "bumbum-pro-prototype-v6";
function initial(): Data {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE) || "null");
    if (
      saved?.version === 6 &&
      Array.isArray(saved.items) &&
      Array.isArray(saved.touches)
    )
      return normalizeWholeItems(saved);
    const old = JSON.parse(
      sessionStorage.getItem("bumbum-make-prototype-v5") || "null",
    );
    if (old?.version === 5) return migrateV5(old);
  } catch {}
  return seed();
}
type Result = { ok: true } | { ok: false; error: string };
interface Store {
  data: Data;
  getData: () => Data;
  run: (type: string, payload?: any) => Result;
  failure: "none" | "save" | "unknown";
  setFailure: (x: "none" | "save" | "unknown") => void;
  readError: boolean;
  setReadError: (x: boolean) => void;
  reset: () => void;
  storageError: string;
}
const Context = createContext<Store | null>(null);
export const useStore = () => {
  const v = useContext(Context);
  if (!v) throw Error("缺少原型上下文");
  return v;
};
export function PrototypeProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState(initial),
    ref = useRef(data),
    [failure, setFailure] = useState<Store["failure"]>("none"),
    [readError, setReadError] = useState(false),
    [storageError, setStorageError] = useState("");
  const save = (next: Data) => {
    ref.current = next;
    setData(next);
    try {
      sessionStorage.setItem(STORAGE, JSON.stringify(next));
      setStorageError("");
    } catch {
      setStorageError(
        "浏览器空间不足，当前页面仍保留数据，刷新可能丢失；请先导出或处理存储。",
      );
    }
  };
  const run = (type: string, payload: any = {}): Result => {
    if (failure !== "none")
      return {
        ok: false,
        error:
          failure === "unknown"
            ? "保存结果未知：本次演示未写入。请核对结果后明确重试。"
            : "模拟保存失败：输入及原记录保留。",
      };
    try {
      save(operate(ref.current, { type, payload } as Command));
      return { ok: true };
    } catch (e) {
      return {
        ok: false,
        error: e instanceof Error ? e.message : "操作未完成",
      };
    }
  };
  return (
    <Context.Provider
      value={{
        data,
        getData: () => ref.current,
        run,
        failure,
        setFailure,
        readError,
        setReadError,
        storageError,
        reset: () => {
          save(seed());
          setFailure("none");
          setReadError(false);
        },
      }}
    >
      {children}
    </Context.Provider>
  );
}
