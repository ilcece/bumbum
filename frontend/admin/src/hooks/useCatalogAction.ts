import { useEffect, useRef, useState } from "react";
import { history } from "@umijs/max";
import { ApiError, readSession, sessionIsExpired } from "../api";
import { command, unknown } from "../catalog";
import { pickPayload, readActionReceipt } from "../api/catalogActions";
import type {
  ActionPayloadMap,
  ActionResult,
  CatalogAction,
  FormValues,
} from "../types/catalog";

type FormActionOptions<A extends CatalogAction> = {
  action: A;
  execute?: (
    payload: ActionPayloadMap[A],
    token: string,
  ) => Promise<ActionResult>;
  beforeSubmit?: (values: FormValues) => Promise<boolean>;
  onDone: (result: ActionResult) => void;
  onSaved: () => void;
  onReceipt?: (result: ActionResult) => boolean;
  onIncompleteReceipt: () => void;
};

export function useCatalogAction<A extends CatalogAction>(
  options: FormActionOptions<A>,
) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [retryReady, setRetryReady] = useState(false);
  const success = useRef(false);
  const token = useRef(crypto.randomUUID());
  const submitted = useRef<ActionPayloadMap[A] | undefined>(undefined);

  const submit = async (values: FormValues) => {
    setBusy(true);
    setError("");
    let executionStarted = false;
    try {
      if (options.beforeSubmit && !(await options.beforeSubmit(values)))
        return false;
      submitted.current ??= pickPayload(options.action, values);
      executionStarted = true;
      const result = await (options.execute
        ? options.execute(submitted.current, token.current)
        : command(options.action, submitted.current, token.current));
      success.current = true;
      options.onSaved();
      options.onDone(result);
      return true;
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "请求未完成");
      if (!executionStarted) return false;
      if (failure instanceof ApiError && failure.code === "csrf_failed") {
        try {
          await readSession();
          setError("会话口令已更新，请明确重试；未自动重发。");
        } catch {
          setError("登录状态无法更新，请重新登录。");
        }
      }
      if (unknown(failure)) setUncertain(true);
      else {
        token.current = crypto.randomUUID();
        submitted.current = undefined;
      }
      return false;
    } finally {
      setBusy(false);
    }
  };

  const checkReceipt = async () => {
    try {
      const result = await readActionReceipt(token.current);
      if (options.onReceipt && !options.onReceipt(result)) {
        setUncertain(false);
        options.onIncompleteReceipt();
        token.current = crypto.randomUUID();
        submitted.current = undefined;
        setError("已核对款式保存记录，仍有待保存图片，请继续保存共用资料。");
        return;
      }
      success.current = true;
      options.onDone(result);
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 404) {
        setRetryReady(true);
        setError("服务端尚无已提交回执，可以明确重试原请求。");
      } else setError(failure instanceof Error ? failure.message : "核对失败");
    }
  };

  return {
    error,
    busy,
    uncertain,
    retryReady,
    success,
    submit,
    checkReceipt,
    retry: () => {
      const payload = submitted.current;
      return payload ? submit(payload) : Promise.resolve(false);
    },
  };
}

export function useCatalogCommand<A extends CatalogAction>({
  action,
  payload,
  onDone,
}: {
  action: A;
  payload: ActionPayloadMap[A];
  onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [retryReady, setRetryReady] = useState(false);
  const token = useRef(crypto.randomUUID());
  const done = useRef(false);
  const send = async () => {
    done.current = false;
    setBusy(true);
    try {
      await command(action, payload, token.current);
      done.current = true;
      setUncertain(false);
      setError("");
      token.current = crypto.randomUUID();
      onDone();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "操作未完成");
      if (unknown(failure)) setUncertain(true);
      else token.current = crypto.randomUUID();
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    if (!busy && !uncertain) return;
    const unblock = history.block((transition) => {
      if (sessionIsExpired() || done.current) {
        unblock();
        transition.retry();
      }
    });
    return unblock;
  }, [busy, uncertain]);

  const checkReceipt = async () => {
    try {
      await readActionReceipt(token.current);
      done.current = true;
      setUncertain(false);
      onDone();
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 404)
        setRetryReady(true);
      else setError(failure instanceof Error ? failure.message : "核对失败");
    }
  };
  return { busy, error, uncertain, retryReady, send, checkReceipt };
}
