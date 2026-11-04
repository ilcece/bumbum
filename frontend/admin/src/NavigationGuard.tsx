import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { Alert, Button, Modal, Space, theme } from "antd";
import { useBlocker } from "react-router-dom";

type Guard = { dirty: boolean; busy: boolean; save?: () => Promise<boolean> };
const EMPTY: Guard = { dirty: false, busy: false };
type Controls = {
  update: (value: Guard) => void;
  attempt: (action: () => void) => void;
};
const Context = createContext<Controls | null>(null);

export function useNavigationGuard() {
  const value = useContext(Context);
  if (!value) throw new Error("页面未接入离开保护。");
  return value;
}

export function NavigationGuard({ children }: { children: ReactNode }) {
  const { token } = theme.useToken();
  const guard = useRef<Guard>(EMPTY);
  const [view, setView] = useState({
    dirty: false,
    busy: false,
    canSave: false,
  });
  const [action, setAction] = useState<(() => void) | null>(null);
  const [saving, setSaving] = useState(false);
  const blocker = useBlocker(
    useCallback(() => {
      return guard.current.dirty || guard.current.busy;
    }, []),
  );
  const update = useCallback((value: Guard) => {
    guard.current = value;
    setView((current) =>
      current.dirty === value.dirty &&
      current.busy === value.busy &&
      current.canSave === !!value.save
        ? current
        : { dirty: value.dirty, busy: value.busy, canSave: !!value.save },
    );
  }, []);
  const attempt = useCallback((next: () => void) => {
    if (guard.current.dirty || guard.current.busy) setAction(() => next);
    else next();
  }, []);
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
      try {
        if (!(await submit())) return;
      } finally {
        setSaving(false);
      }
    }
    if (blocker.state === "blocked") blocker.proceed();
    else action?.();
    setAction(null);
  }
  return (
    <Context.Provider value={{ update, attempt }}>
      {children}
      <Modal
        zIndex={token.zIndexPopupBase + 1000}
        open={
          !!action || (blocker.state === "blocked" && (view.dirty || view.busy))
        }
        title={view.busy ? "操作尚未结束" : "有未保存修改"}
        onCancel={cancel}
        closable={!saving}
        mask={{ closable: false }}
        footer={
          <Space>
            <Button onClick={cancel} disabled={saving}>
              取消
            </Button>
            {!view.busy && (
              <Button onClick={() => void proceed(false)} disabled={saving}>
                放弃继续
              </Button>
            )}
            {!view.busy && view.canSave && (
              <Button
                type="primary"
                loading={saving}
                onClick={() => void proceed(true)}
              >
                保存后继续
              </Button>
            )}
          </Space>
        }
      >
        {view.busy ? (
          <Alert
            type="info"
            showIcon
            title="请等待当前请求结束，再离开页面。"
          />
        ) : (
          "选择保存后继续、放弃当前输入，或取消离开。绑定和配置须在原操作中明确确认。"
        )}
      </Modal>
    </Context.Provider>
  );
}
