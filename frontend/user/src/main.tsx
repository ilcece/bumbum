import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ApiError, isLegacyItemRef, isPublicId, readOwnedItem, readView, verify, type ItemView, type Reading } from "./api";
import { ImageGallery } from "./ImageGallery";
import { LostRecovery } from "./LostRecovery";
import { ClaimPanel, MyItemsPage } from "./AccountPages";
import { itemFacts } from "../../shared/itemPresentation";
import { ArchiveDetails, ItemIdentity, ItemMetadata, PageHeader } from "./ArchivePresentation";
import "./style.css";

// 在加载任何外部图片之前移除触碰参数，只在当前内存中保留到本次请求结束。
function entry(): { reading?: Reading; id?: string; invalid?: boolean } {
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
  const match = /^\/tap\/items\/([^/]+)\/?$/.exec(url.pathname);
  if (match && (isPublicId(match[1]) || isLegacyItemRef(match[1])))
    return { id: match[1] };
  return {};
}
const mine = /^\/mine(?:\/items\/([^/]+))?\/?$/.exec(location.pathname);
const openingRecovery = location.pathname === "/tap" && location.hash === "#recovery" && !location.search;
const initial = mine ? {} : entry();
try {
  const savedClaim = sessionStorage.getItem("bumbum-claim-item");
  if (savedClaim && isLegacyItemRef(savedClaim)) sessionStorage.removeItem("bumbum-claim-item");
} catch { /* 隐私模式无需保存认领进度。 */ }
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

async function holderView(item: ItemView, signal: AbortSignal) {
  if (item.claim_state !== "claimed") return;
  try {
    return await readOwnedItem(item.public_id, signal);
  } catch {
    // 公共档案仍可显示，持有人资料必须由服务端确认权限。
  }
}

function App() {
  const [recovery, setRecovery] = useState(false);
  const [target, setTarget] = useState<string | null>(initial.id || null);
  const [data, setData] = useState<ItemView | null>(null);
  const [owned, setOwned] = useState<Awaited<ReturnType<typeof readOwnedItem>>>();
  const [showLoader, setShowLoader] = useState(false);
  const [tapToken, setTapToken] = useState<string>();
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
    if (mode !== "loading" || recovery || owned) return;
    const timer = setTimeout(() => setShowLoader(true), 180);
    return () => clearTimeout(timer);
  }, [mode, recovery, owned]);
  useEffect(() => {
    if (!initial.reading) return;
    let alive = true;
    const controller = new AbortController();
    const reading = initial.reading;
    delete initial.reading;
    verify(reading, controller.signal)
      .then(async (result) => {
        if (!alive) return;
        if (result === "recovery") {
          history.replaceState(null, "", "/tap#recovery");
          setRecovery(true);
          return;
        }
        if (result === "unsupported") {
          setMode("unsupported");
          return;
        }
        const holder = await holderView(result, controller.signal);
        if (!alive) return;
        if (holder) {
          history.replaceState(null, "", `/mine/items/${result.public_id}`);
          setOwned(holder);
          return;
        }
        history.replaceState(null, "", `/tap/items/${result.public_id}`);
        latest.current = result;
        setData(result);
        setTapToken(result.tapToken);
        setMode("view");
        setTarget(result.public_id);
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
    if (!target || owned) return;
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
        if (!latest.current) {
          const holder = await holderView(result, controller.signal);
          if (!alive) return;
          if (holder) {
            history.replaceState(null, "", `/mine/items/${result.public_id}`);
            setOwned(holder);
            return;
          }
        }
        latest.current = result;
        setData(result);
        setError(null);
        setMode("view");
        failures = 0;
        notBefore = 0;
        if (target === result.public_id) schedule(60000);
        else {
          history.replaceState(null, "", `/tap/items/${result.public_id}`);
          setTarget(result.public_id);
        }
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
        new ApiError(0, "network_error", "网络已断开，请检查连接。"),
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
    else if (latest.current?.public_id === target) schedule(60000);
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
  }, [target, owned]);
  const problem = error && (
    <div className="notice" role="alert">
      <strong>
        {data ? "资料更新失败，当前显示上次内容" : "暂时无法读取最新资料"}
      </strong>
      {data && <p>上次更新于 {format(data.retrieved_at)}（北京时间）</p>}
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
  const rights = data && itemFacts(data).find(({ label }) => label === "数字权益")?.value;
  if (owned) return <MyItemsPage itemId={owned.item.public_id} initial={owned} />;
  if (recovery || openingRecovery) return <div className="app">
    <PageHeader />
    <main>{recovery ? <LostRecovery /> : <section className="recovery-panel"><h1>请重新碰一下这件物品</h1><p>打开新出现的提示，查看是否能联系失主。</p></section>}</main>
  </div>;
  if (mode === "view" && data) return <div className="app">
    <ClaimPanel key={data.public_id} item={data} tapToken={tapToken} archive={(action) => <>
      <PageHeader />
      <main className="profile">
        {problem}
        <ImageGallery urls={data.profile.image_urls} name={data.profile.name} />
        <ItemIdentity name={data.profile.name} item={data} />
        {action}
        <ItemMetadata item={data} />
        <ArchiveDetails {...data.profile} />
        {rights && <details className="tap-help">
          <summary>物品权益</summary><p>这件物品支持{rights}。认领后可查看用量和办理方式。</p>
        </details>}
        <details className="tap-help">
          <summary>识别记录</summary>
          <p>上次识别 {format(data.verified_at)}<br />上次读取资料 {format(data.retrieved_at)}<br />时间均为北京时间。认领后，物品才会进入你的账户。</p>
        </details>
      </main>
    </>} />
  </div>;
  return (
    <div className="app">
      <PageHeader />
      <main>
        {mode === "entry" && (
          <section className="state-card">
            <h1>请触碰物品上的芯片</h1>
            <p>将手机靠近物品上的感应位置，打开新出现的通知查看物品。</p>
            <Help />
          </section>
        )}
        {mode === "loading" && !data && (showLoader || error) && (
          <section className={error ? "state-card" : "state-card loading-view"} aria-live="polite">
            <h1>
              {error
                ? "资料暂未加载完成"
                : target
                  ? "正在读取最新资料"
                  : "正在识别这件物品"}
            </h1>
            {!error && <div className="loading-line" aria-hidden="true" />}
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
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(mine ? <MyItemsPage itemId={mine[1]} recordsPage={!mine[1] && location.search === "?tab=records"} /> : <App />);
