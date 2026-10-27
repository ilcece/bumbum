import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ApiError, readView, verify, type ItemView, type Reading } from "./api";
import { ImageGallery } from "./ImageGallery";
import "./style.css";

// 在加载任何外部图片之前移除触碰参数，只在当前内存中保留到本次请求结束。
function entry(): { reading?: Reading; id?: number; invalid?: boolean } {
  const url = new URL(window.location.href);
  if (url.search) {
    const keys = [...url.searchParams.keys()];
    const picc = url.searchParams.get("picc_data"),
      cmac = url.searchParams.get("cmac");
    history.replaceState(null, "", "/tap");
    if (
      url.pathname !== "/tap" ||
      keys.length !== 2 ||
      new Set(keys).size !== 2 ||
      !keys.every((k) => k === "picc_data" || k === "cmac") ||
      !picc ||
      !cmac ||
      !/^[a-f0-9]{32}$/i.test(picc) ||
      !/^[a-f0-9]{16}$/i.test(cmac)
    )
      return { invalid: true };
    return { reading: { picc_data: picc, cmac } };
  }
  const match = /^\/tap\/items\/([1-9][0-9]*)\/?$/.exec(url.pathname);
  if (match && Number.isSafeInteger(Number(match[1])))
    return { id: Number(match[1]) };
  return {};
}
const initial = entry();
const format = (value: string) =>
  new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
function Help() {
  return (
    <details className="tap-help">
      <summary>怎样重新触碰？</summary>
      <p>将手机离开物品上的 NFC 标签，再靠近，点击新出现的系统通知。</p>
    </details>
  );
}
function App() {
  const [target, setTarget] = useState<number | null>(initial.id || null);
  const [data, setData] = useState<ItemView | null>(null);
  const latest = useRef<ItemView | null>(null);
  const [mode, setMode] = useState<
    "loading" | "entry" | "view" | "error" | "unsupported"
  >(
    initial.invalid
      ? "error"
      : initial.reading || initial.id
        ? "loading"
        : "entry",
  );
  const [error, setError] = useState<ApiError | null>(
    initial.invalid
      ? new ApiError(400, "invalid_param", "链接信息不完整，请重新触碰物品。")
      : null,
  );
  const retry = useRef<() => void>(() => {});
  const [waiting, setWaiting] = useState(false);
  const [rateWaiting, setRateWaiting] = useState(false);
  useEffect(() => {
    if (!initial.reading) return;
    let alive = true;
    const controller = new AbortController();
    const reading = initial.reading;
    delete initial.reading;
    verify(reading, controller.signal)
      .then((result) => {
        if (!alive) return;
        if (result === "unsupported") {
          setMode("unsupported");
          return;
        }
        history.replaceState(null, "", `/tap/items/${result.item_id}`);
        latest.current = result;
        setData(result);
        setMode("view");
        setTarget(result.item_id);
      })
      .catch((reason) => {
        if (alive) {
          setError(reason);
          setMode("error");
        }
      });
    return () => {
      alive = false;
      controller.abort();
    };
  }, []);
  useEffect(() => {
    if (!target) return;
    let alive = true,
      inflight = false,
      timer: ReturnType<typeof setTimeout> | undefined,
      controller: AbortController | undefined;
    let failures = 0,
      notBefore = 0,
      lastStarted = 0;
    const schedule = (delay: number) => {
      clearTimeout(timer);
      if (
        alive &&
        document.visibilityState === "visible" &&
        navigator.onLine !== false
      )
        timer = setTimeout(load, delay);
    };
    const load = async () => {
      if (
        !alive ||
        inflight ||
        document.visibilityState !== "visible" ||
        navigator.onLine === false
      )
        return;
      if (Date.now() < notBefore) {
        schedule(notBefore - Date.now());
        return;
      }
      clearTimeout(timer);
      lastStarted = Date.now();
      setRateWaiting(false);
      inflight = true;
      controller = new AbortController();
      setWaiting(true);
      try {
        const result = await readView(target, controller.signal);
        if (!alive) return;
        latest.current = result;
        setData(result);
        setError(null);
        setMode("view");
        failures = 0;
        notBefore = 0;
        schedule(60000);
      } catch (reason) {
        if (!alive) return;
        const failure =
          reason instanceof ApiError
            ? reason
            : new ApiError(0, "network_error", "资料更新失败，请检查网络。");
        setError(failure);
        setRateWaiting(failure.status === 429);
        if (failure.status === 403 || failure.status === 409) {
          latest.current = null;
          setData(null);
          setMode("error");
          setTarget(null);
        } else {
          failures++;
          const delay = Math.max(
            failure.retryAfter,
            [60000, 120000, 300000][Math.min(failures - 1, 2)],
          );
          notBefore =
            failure.status === 429 ? Date.now() + failure.retryAfter : 0;
          schedule(delay);
        }
      } finally {
        inflight = false;
        if (alive) setWaiting(false);
      }
    };
    const visible = () => {
      if (document.visibilityState !== "visible") {
        clearTimeout(timer);
        return;
      }
      if (Date.now() - lastStarted > 500) void load();
    };
    const online = () => {
      if (Date.now() - lastStarted > 500) void load();
    };
    const offline = () => {
      clearTimeout(timer);
      setError(
        new ApiError(0, "network_error", "网络已断开，当前显示上次内容。"),
      );
    };
    retry.current = () => {
      if (Date.now() >= notBefore) void load();
    };
    document.addEventListener("visibilitychange", visible);
    window.addEventListener("pageshow", visible);
    window.addEventListener("online", online);
    window.addEventListener("offline", offline);
    if (navigator.onLine === false) offline();
    else if (latest.current?.item_id === target) schedule(60000);
    else void load();
    return () => {
      alive = false;
      clearTimeout(timer);
      controller?.abort();
      retry.current = () => {};
      document.removeEventListener("visibilitychange", visible);
      window.removeEventListener("pageshow", visible);
      window.removeEventListener("online", online);
      window.removeEventListener("offline", offline);
    };
  }, [target]);
  const problem = error && (
    <div className="notice" role="alert">
      <strong>
        {data ? "资料更新失败，当前显示上次内容" : "暂时无法读取最新资料"}
      </strong>
      <p>{error.message}</p>
      {error.status === 429 && (
        <p>
          请求较多，请等待约{Math.max(1, Math.ceil(error.retryAfter / 1000))}
          秒后再试。
        </p>
      )}
      {error.errorId && (
        <p>
          错误编号：{error.errorId}{" "}
          <button
            className="text-action"
            onClick={() => {
              navigator.clipboard?.writeText(error.errorId!).catch(() => {});
            }}
          >
            复制编号
          </button>
        </p>
      )}
      {target && (
        <button
          onClick={() => retry.current()}
          disabled={waiting || rateWaiting}
        >
          重试更新
        </button>
      )}
    </div>
  );
  return (
    <div className="app">
      <header className="brand">
        <span className="brand-mark">b.</span>
        <strong>BUMBUM</strong>
        <span className="brand-caption">物品数字档案</span>
      </header>
      <main>
        {mode === "entry" && (
          <section className="state-card">
            <div className="state-icon">◎</div>
            <h1>请触碰物品上的芯片</h1>
            <p>将手机靠近 NFC 标签，点击系统通知，即可验证芯片并查看资料。</p>
            <Help />
          </section>
        )}
        {mode === "loading" && !data && (
          <section className="state-card" aria-live="polite">
            {!error && <div className="loader" />}
            <h1>
              {error
                ? "资料暂未加载完成"
                : target
                  ? "正在读取最新资料"
                  : "正在验证芯片"}
            </h1>
            {!error && <p>请稍候，无需再次点击。</p>}
            {problem}
          </section>
        )}
        {mode === "unsupported" && (
          <section className="state-card">
            <h1>芯片验证通过</h1>
            <p>当前版本暂不支持展示该类物品。</p>
            <Help />
          </section>
        )}
        {mode === "error" && (
          <section className="state-card" role="alert">
            <h1>
              {error?.code === "replay_suspect"
                ? "这次链接已使用"
                : error?.code === "view_unavailable"
                  ? "该物品当前暂不可查看"
                  : error?.code === "invalid_view_session"
                    ? "本次查看资格不可用"
                    : "暂时无法完成验证"}
            </h1>
            <p>{error?.message || "请重新触碰物品上的芯片。"}</p>
            {error?.errorId && (
              <p className="meta">错误编号：{error.errorId}</p>
            )}
            <Help />
          </section>
        )}
        {mode === "view" && data && (
          <>
            <section className="verification">
              <span aria-hidden="true">✓</span>
              <div>
                <strong>芯片验证通过</strong>
                <p>最近验证：{format(data.verified_at)}（北京时间）</p>
              </div>
            </section>
            {problem}
            <ImageGallery
              urls={data.profile.image_urls}
              name={data.profile.name}
            />
            <article className="profile">
              <p className="eyebrow">服装档案</p>
              <h1>{data.profile.name}</h1>
              <p className="item-uid">物品编号 {data.item_uid}</p>
              {(
                [
                  ["材质", data.profile.material],
                  ["介绍", data.profile.description],
                  ["洗护说明", data.profile.care_instructions],
                ] as const
              ).map(
                ([label, value]) =>
                  value?.trim() && (
                    <section className="profile-section" key={label}>
                      <h2>{label}</h2>
                      <p>{value}</p>
                    </section>
                  ),
              )}
              <div className="data-note">
                <p>资料读取：{format(data.retrieved_at)}（北京时间）</p>
                <p>页面前台自动更新，查询资料不会产生新的触碰记录。</p>
              </div>
              <Help />
            </article>
          </>
        )}
      </main>
      <footer>芯片验证反映本次读数结果，不代表访问者身份或所有权。</footer>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
