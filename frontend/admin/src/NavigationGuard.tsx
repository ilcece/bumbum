import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Alert, Button, Modal, Space } from "antd";
import { useBlocker } from "react-router-dom";

type Guard = { dirty: boolean; busy: boolean; save?: () => Promise<boolean> };
const EMPTY: Guard = { dirty: false, busy: false };
type Controls = {
  update: (value: Guard) => void;
  attempt: (action: () => void) => void;
  legacy: (check: (() => boolean) | null) => void;
};
const Context = createContext<Controls | null>(null);

export function useNavigationGuard() {
  const value = useContext(Context);
  if (!value) throw new Error("页面未接入离开保护。");
  return value;
}

export function NavigationGuard({ children }: { children: ReactNode }) {
  const guard = useRef<Guard>(EMPTY);
  const legacy = useRef<(() => boolean) | null>(null);
  const [view, setView] = useState({ dirty: false, busy: false, canSave: false });
  const [action, setAction] = useState<(() => void) | null>(null);
  const [saving, setSaving] = useState(false);
  const blocker = useBlocker(useCallback(() => {
    if (legacy.current && !legacy.current()) return true;
    return guard.current.dirty || guard.current.busy;
  }, []));
  const update = useCallback((value: Guard) => {
    guard.current = value;
    setView(current => current.dirty === value.dirty && current.busy === value.busy && current.canSave === !!value.save
      ? current : { dirty: value.dirty, busy: value.busy, canSave: !!value.save });
  }, []);
  const attempt = useCallback((next: () => void) => {
    if (legacy.current && !legacy.current()) return;
    if (guard.current.dirty || guard.current.busy) setAction(() => next);
    else next();
  }, []);
  const setLegacy = useCallback((check: (() => boolean) | null) => { legacy.current = check; }, []);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (guard.current.dirty || guard.current.busy) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);
  // 旧物品流程暂沿用其已有确认；取消后直接撤销本次导航。
  useEffect(() => {
    if (blocker.state === "blocked" && !guard.current.dirty && !guard.current.busy) blocker.reset();
  }, [blocker]);
  function cancel() {
    if (saving) return;
    if (blocker.state === "blocked") blocker.reset();
    setAction(null);
  }
  async function proceed(save: boolean) {
    if (saving || guard.current.busy) return;
    if (save) {
      const submit = guard.current.save;
      if (!submit) return;
      setSaving(true);
      try { if (!await submit()) return; }
      finally { setSaving(false); }
    }
    if (blocker.state === "blocked") blocker.proceed();
    else action?.();
    setAction(null);
  }
  return <Context.Provider value={{ update, attempt, legacy: setLegacy }}>
    {children}
    <Modal open={!!action || (blocker.state === "blocked" && (view.dirty || view.busy))}
      title={view.busy ? "操作尚未结束" : "有未保存修改"} onCancel={cancel} closable={!saving}
      maskClosable={false} footer={<Space>
        <Button onClick={cancel} disabled={saving}>取消</Button>
        {!view.busy && <Button onClick={() => void proceed(false)} disabled={saving}>放弃继续</Button>}
        {!view.busy && view.canSave && <Button type="primary" loading={saving} onClick={() => void proceed(true)}>保存后继续</Button>}
      </Space>}>
      {view.busy ? <Alert type="info" showIcon message="请等待当前请求结束，再离开页面。" />
        : "选择保存后继续、放弃当前输入，或取消离开。绑定和配置须在原操作中明确确认。"}
    </Modal>
  </Context.Provider>;
}
