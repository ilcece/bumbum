import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ArchiveDetails, editionLabel, ItemIdentity, ItemMetadata, PageHeader } from "./ArchivePresentation";
import { accountView, ApiError, isLegacyItemRef, ownedItem, publicAccount, readOwnedItem, type Account, type ItemView, type OwnedItem, type LifecycleEvent, type ItemLifecycle } from "./api";
import { ImageGallery } from "./ImageGallery";

const errorText = (error: unknown) => error instanceof Error ? error.message : "暂时无法处理，请稍后重试。";
const date = (value: string) => new Date(value).toLocaleDateString("zh-CN", { timeZone: "Asia/Shanghai" });

function Login({ onDone, forClaim = false }: { onDone: (account: Account) => void; forClaim?: boolean }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!cooldown) return;
    const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);
  async function send() {
    setBusy(true);
    setError("");
    try {
      const result = await publicAccount("/sms/send", { phone: phone.trim() });
      if (typeof result.challenge_id !== "string") throw new Error("短信结果无法确认，请稍后重试。");
      setChallenge(result.challenge_id);
      setCode("");
      setCooldown(60);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!challenge || busy || !/^\d{6}$/.test(code)) return;
    setBusy(true);
    setError("");
    try {
      const account = accountView((await publicAccount("/sms/verify", { challenge_id: challenge, code })).account);
      if (account) onDone(account);
      else setError("登录结果无法确认，请重试。");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="account-form" onSubmit={submit}>
      {!forClaim && <p className="introline">登录后可以查看你当前持有的物品。</p>}
      <label htmlFor="account-phone">手机号</label>
      <div className="fieldline">
        <input id="account-phone" type="tel" inputMode="numeric" autoComplete="tel-national" maxLength={11} value={phone} onChange={(event) => { setPhone(event.target.value); setChallenge(""); }} />
        <button type="button" className="secondary" onClick={send} disabled={busy || cooldown > 0 || !/^1[3-9]\d{9}$/.test(phone.trim())}>
          {cooldown ? `${cooldown} 秒后可重发` : "发送短信验证码"}
        </button>
      </div>
      {challenge && <>
        <label>短信验证码<input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value)} /></label>
        <button className="primary" disabled={busy || !/^\d{6}$/.test(code)}>验证并继续</button>
      </>}
      {error && <p className="field-error" role="alert">{error}</p>}
    </form>
  );
}

function rememberClaim(itemId: string | null) {
  try {
    if (itemId) sessionStorage.setItem("bumbum-claim-item", String(itemId));
    else sessionStorage.removeItem("bumbum-claim-item");
  } catch { /* 隐私模式仍可完成当前页认领。 */ }
}

export function ClaimPanel({ item, tapToken, archive }: { item: ItemView; tapToken?: string; archive: (action?: ReactNode) => ReactNode }) {
  const [open, setOpen] = useState(() => {
    try { return sessionStorage.getItem("bumbum-claim-item") === String(item.public_id); }
    catch { return false; }
  });
  const [user, setUser] = useState<Account | null>();
  const [code, setCode] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<"mine" | "claimed" | "unknown">();
  const [retap, setRetap] = useState(false);
  const [checking, setChecking] = useState(false);
  const retryClaimStatus = useRef<() => void>(() => {});
  useEffect(() => setRetap(false), [tapToken]);
  useEffect(() => {
    if (!open || item.claim_state !== "available") return;
    let active = true;
    publicAccount("/account/session").then((data) => {
      if (active) setUser(accountView(data.account));
    }).catch((e) => { if (active) { setError(errorText(e)); setUser(null); } });
    return () => { active = false; };
  }, [open, item.claim_state]);
  useEffect(() => {
    if (result !== "unknown") return;
    let active = true;
    let inflight = false;
    const recover = async () => {
      if (inflight) return;
      inflight = true;
      setChecking(true);
      setError("");
      try {
        const data = await publicAccount(`/items/${item.public_id}/claim-status`);
        if (!active) return;
        if (data.state === "mine" || data.state === "claimed") {
          setCode("");
          setResult(data.state);
          rememberClaim(null);
        } else { setConfirm(false); setResult(undefined); }
      } catch (e) {
        if (active) setError(errorText(e));
      } finally {
        inflight = false;
        if (active) setChecking(false);
      }
    };
    retryClaimStatus.current = recover;
    void recover();
    window.addEventListener("online", recover);
    return () => {
      active = false;
      retryClaimStatus.current = () => {};
      window.removeEventListener("online", recover);
    };
  }, [item.public_id, result]);
  async function claim(event: FormEvent) {
    event.preventDefault();
    if (!tapToken || !confirm || busy) return;
    setBusy(true);
    setError("");
    try {
      await publicAccount(`/items/${item.public_id}/claim`, { tap_token: tapToken, claim_code: code.trim() });
      setCode("");
      setResult("mine");
      rememberClaim(null);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 0 || e.status >= 500)) setResult("unknown");
      else if (e instanceof ApiError && e.code === "already_claimed") { setResult("claimed"); rememberClaim(null); }
      else {
        setError(errorText(e));
        setConfirm(false);
        if (e instanceof ApiError && e.status === 401) setUser(null);
        if (e instanceof ApiError && e.code === "retap_required") setRetap(true);
      }
    } finally {
      setBusy(false);
    }
  }
  const edition = editionLabel(item);
  const preview = <div className="claim-item">
    {item.profile.image_urls[0] && <img className="product-image-frame" src={item.profile.image_urls[0]} alt="" referrerPolicy="no-referrer" />}
    <div><strong>{item.profile.name}</strong>{edition && <small>发行编号 {edition}</small>}</div>
  </div>;
  if (result === "mine") return <><PageHeader /><main className="profile flow" role="status">
    <p className="identity-status">认领成功</p><h1>已认领到我的数字物品</h1>
    {preview}<a className="primary" href={`/mine/items/${item.public_id}`}>查看我的物品</a>
  </main></>;
  if (result === "claimed" || (result !== "unknown" && item.claim_state === "claimed")) return archive(<section className="notice"><strong>这件物品已认领</strong><p>如有疑问，请联系物品提供方。</p></section>);
  if (item.claim_state !== "available" && result !== "unknown") return archive(item.claim_state ? <p className="notice">{item.claim_state === "expired" ? "认领码已过期，请联系 BUMBUM 核对交付后补发。" : "暂未开放认领"}</p> : null);
  if (!open) return archive(<div className="claim-action">
    <button className="primary" onClick={() => { rememberClaim(item.public_id); setOpen(true); }}>{result === "unknown" ? "查看认领结果" : "认领这件物品"}</button>
    {result !== "unknown" && <p>请准备收到物品时拿到的认领码。</p>}
  </div>);
  const step = !user ? 1 : confirm ? 3 : 2;
  const canProceed = Boolean(tapToken && !retap && result !== "unknown" && user !== undefined);
  return (
    <>
      <PageHeader label={confirm && result !== "unknown" ? "返回输入认领码" : "返回物品资料"} onBack={() => {
        if (confirm && result !== "unknown") { setConfirm(false); setError(""); return; }
        rememberClaim(null);
        setOpen(false);
        if (result !== "unknown") { setCode(""); setError(""); }
      }} />
      <main className="profile flow">
      {canProceed && <div className="claim-steps">
        <div aria-hidden="true">{[1, 2, 3].map((position) => <span key={position} className={position <= step ? "current" : undefined} />)}</div>
        第 {step} 步，共 3 步
      </div>}
      {result === "unknown" ? <>
        <h1>核对认领结果</h1>
        <p role="status">{error ? "暂时无法核对认领结果。" : "正在核对认领结果。网络恢复后会再次查询。"}</p>
        {error && <button className="secondary" onClick={() => retryClaimStatus.current()} disabled={checking}>再次核对认领结果</button>}
      </> : !tapToken || retap ? <><h1>请重新碰一下物品</h1><p className="introline">打开新出现的通知，再继续认领。</p>{preview}</> :
        user === undefined ? <p role="status">正在读取登录状态</p> : user === null ? <>
          <h1>验证手机号</h1><p className="introline">认领成功后，这件物品会归入此账户。</p>{preview}
          <Login forClaim onDone={(value) => { setUser(value); setError(""); }} />
        </> : confirm ? <>
          <h1>确认认领</h1>{preview}
          <dl className="item-metadata"><div><dt>认领账户</dt><dd>{user.phone}</dd></div>{edition && <div><dt>发行编号</dt><dd>{edition}</dd></div>}</dl>
          <form onSubmit={claim}><button className="primary" disabled={busy || !code.trim()}>确认认领</button></form>
        </> : <>
          <h1>输入认领码</h1><p className="introline">请输入收到物品时拿到的认领码。</p>{preview}
          <form className="account-form" onSubmit={(event) => { event.preventDefault(); if (code.trim()) { setError(""); setConfirm(true); } }}>
            <label>交付认领码<input aria-invalid={Boolean(error)} autoCapitalize="characters" autoComplete="off" maxLength={24} value={code} onChange={(event) => { setCode(event.target.value); setError(""); }} /></label>
            {error && <p className="field-error" role="alert">{error}</p>}
            <button className="primary" disabled={!code.trim()}>核对认领信息</button>
          </form>
        </>}
      {error && (!canProceed || !user || confirm) && <p className="field-error" role="alert">{error}</p>}
      </main>
    </>
  );
}

const eventLabels: Record<string, string> = {
  issued: "正式发行", physical_started: "实物启用", physical_ended: "实物退出使用",
  claimed: "认领到我的物品", lost: "实物已挂失", loss_cancelled: "已取消挂失", resale_started: "开始办理转售", renewal_started: "开始办理换新",
  prepared: "新物品已准备好", resold: "转售交付已确认", received: "已接收这件物品", renewed: "换新交付已确认",
};

function Timeline({ title, events, showItem = false }: { title: string; events?: LifecycleEvent[]; showItem?: boolean }) {
  return <section className="profile-section record-section">
    <h2>{title}</h2>
    {events?.length ? <ol className="record-list">{events.map((entry, index) => <li key={`${entry.at}-${entry.event}-${index}`}>
      <time dateTime={entry.at}>{date(entry.at)}</time>
      {showItem && <span>{entry.name || "数字物品"} · {entry.edition_number && entry.issue_total ? `${entry.edition_number} / ${entry.issue_total}` : entry.item_uid}</span>}
      <strong>{eventLabels[entry.event]}{entry.spec ? ` · ${entry.spec}` : ""}</strong>
    </li>)}</ol> : <p>暂无记录。</p>}
  </section>;
}

function itemStage(lifecycle: ItemLifecycle | undefined) {
  if (lifecycle?.stage === "resale") return lifecycle.awaiting_delivery ? "转售待确认交付" : "转售办理中";
  if (lifecycle?.stage === "renewal") return lifecycle.awaiting_delivery ? "换新待确认交付" : "换新办理中";
  return lifecycle?.lost ? "当前实物已挂失" : "";
}

const holderTabs = [["archive", "档案"], ["rights", "权益"], ["records", "记录"]] as const;

function OwnedDetails({ item, phone, onRefresh }: { item: OwnedItem; phone: string; onRefresh: () => void }) {
  const [tab, setTab] = useState<"archive" | "rights" | "records">("archive");
  const [enabled, setEnabled] = useState(Boolean(item.recovery_enabled));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [failure, setFailure] = useState("");
  const [hidden, setHidden] = useState<string>();
  const lifecycle = item.lifecycle;
  const stage = itemStage(lifecycle);
  const notice = lifecycle?.notice;
  const [settings, showSettings] = useState(false);
  const recordHeading = useRef<HTMLDivElement>(null);
  const settingsHeading = useRef<HTMLElement>(null);
  const settingsTrigger = useRef<HTMLButtonElement>(null);
  useEffect(() => { setEnabled(Boolean(item.recovery_enabled)); }, [item.recovery_enabled]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setHidden(notice.token), Math.max(0, Date.parse(notice.expires_at) - Date.now()));
    return () => clearTimeout(timer);
  }, [notice]);
  const visibleNotice = !stage && notice && hidden !== notice.token;
  async function saveRecovery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setFailure(""); setMessage("");
    try {
      const result = await publicAccount(`/me/items/${item.public_id}/recovery`, { enabled });
      setMessage(result.enabled ? "已保存。挂失期间拾到的人可以查看号码。" : "已关闭找回联系。");
      onRefresh();
    } catch (error) { setFailure(errorText(error)); }
    finally { setSaving(false); }
  }
  async function dismiss() {
    if (!notice) return;
    setFailure("");
    try { await publicAccount(`/me/items/${item.public_id}/dismiss-notice`, { notice_token: notice.token }); setHidden(notice.token); }
    catch (error) { setFailure(errorText(error)); }
  }
  function showRecords() {
    setTab("records");
    requestAnimationFrame(() => recordHeading.current?.focus());
  }
  function openSettings() {
    setTab("archive");
    showSettings(true);
    requestAnimationFrame(() => settingsHeading.current?.focus());
  }
  return <article>
    <ItemIdentity name={item.name || item.item_uid} item={item} owned />
    {stage && <section className={lifecycle?.lost ? "holder-stage holder-stage--lost" : "holder-stage"} aria-label="当前状态">
      <h2>{stage}</h2>
      {lifecycle?.stage && lifecycle.lost && <p>原物品已挂失</p>}
      <p>{lifecycle?.stage ? lifecycle.awaiting_delivery ? "新物品已准备好，等待 BUMBUM 确认交付。" : "BUMBUM 正在准备新物品。" : "拾到的人可通过找回页联系你，是否公开号码由你决定。"}</p>
      <div className="stage-actions">
        <button type="button" className="text-action" onClick={showRecords}>查看办理记录 <span aria-hidden="true">→</span></button>
        {lifecycle?.lost && <button ref={settingsTrigger} type="button" className="text-action" onClick={openSettings}>找回设置</button>}
      </div>
    </section>}
    {visibleNotice && <section className="holder-stage holder-stage--complete" aria-label="交付结果">
      <h2>{notice.kind === "received" ? "已接收这件物品" : "换新已完成"}</h2>
      <p>新实物已接入这份档案，发行编号保持不变。</p>
      <div className="stage-actions">
        <button type="button" className="text-action" onClick={showRecords}>查看办理记录</button>
        <button type="button" className="text-action" onClick={dismiss}>收起提示</button>
      </div>
    </section>}
    {failure && <p className="field-error" role="alert">{failure}</p>}
    <div className="holder-nav" role="tablist" aria-label="物品信息" onKeyDown={(event) => {
      const current = holderTabs.findIndex(([value]) => value === tab);
      const next = event.key === "Home" ? 0 : event.key === "End" ? holderTabs.length - 1 :
        event.key === "ArrowLeft" ? (current + holderTabs.length - 1) % holderTabs.length :
        event.key === "ArrowRight" ? (current + 1) % holderTabs.length : null;
      if (next === null) return;
      event.preventDefault();
      const [value] = holderTabs[next];
      setTab(value);
      event.currentTarget.querySelector<HTMLButtonElement>(`#holder-tab-${value}`)?.focus();
    }}>
      {holderTabs.map(([value, label]) =>
        <button type="button" role="tab" id={`holder-tab-${value}`} key={value} aria-controls="holder-panel" aria-selected={tab === value}
          tabIndex={tab === value ? 0 : -1} onClick={() => setTab(value)}>{label}</button>)}
    </div>
    <div className="holder-panel" id="holder-panel" role="tabpanel" aria-labelledby={`holder-tab-${tab}`}>
    {tab === "archive" && <>
      <ImageGallery urls={item.image_urls} name={item.name || item.item_uid} />
      <ItemMetadata item={item} />
      <section className="profile-section"><h2>实物信息</h2>
        {item.spec && <p>{item.spec}</p>}
        <p>认领或接续日期 {date(item.bound_at)}</p>
      </section>
      <ArchiveDetails {...item} />
      {(!lifecycle?.lost || settings) && <details className="tap-help" open={settings} onToggle={(event) => {
        showSettings(event.currentTarget.open);
        if (!event.currentTarget.open) settingsTrigger.current?.focus();
      }}>
        <summary ref={settingsHeading}>找回设置</summary>
        <form onSubmit={saveRecovery}>
          <p>开启后，挂失期间重新碰到这件实物的人可查看并拨打下列手机号。你可以随时关闭。</p>
          <label className="recovery-choice"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />公开已验证的手机号 {phone}</label>
          <button className="primary" type="submit" disabled={saving}>保存设置</button>
          <p role="status">{message}</p>
        </form>
      </details>}
    </>}
    {tab === "rights" && <>
      {item.rights?.some(({kind}) => kind === "renewal") && <section className="right"><h2>换新</h2>
        <p>{item.quota_review ? "本年换新用量待核对" : item.quota_year ? `${item.quota_year} 年已换新 ${item.quota_used ?? 0} 次` : "暂无年度换新记录"}</p>
      </section>}
      {item.rights?.some(({kind}) => kind === "resale") && <section className="right"><h2>转售</h2><p>确认交付后，接收人获得这份档案和原发行编号。</p></section>}
      {item.rights?.some(({kind}) => kind === "renewal" || kind === "resale") ? <details className="tap-help">
        <summary>如何办理</summary><p>请通过交付时的渠道联系 BUMBUM，并告知物品编号 {item.item_uid}。</p>
      </details> : <p>这件物品暂无可查看的数字权益。</p>}
    </>}
    {tab === "records" && <div tabIndex={-1} ref={recordHeading}>
      <Timeline title="我的办理记录" events={item.records} />
      <Timeline title="物品历程" events={item.history} />
    </div>}
    </div>
  </article>;
}

export function MyItemsPage({ itemId, recordsPage = false, initial }: { itemId?: string; recordsPage?: boolean; initial?: { user: Account; item: OwnedItem } }) {
  const [user, setUser] = useState<Account | null | undefined>(initial?.user);
  const [items, setItems] = useState<OwnedItem[] | undefined>(initial ? [initial.item] : undefined);
  const [ref, setRef] = useState(itemId);
  const [records, setRecords] = useState<LifecycleEvent[]>();
  const [error, setError] = useState("");
  const [version, retry] = useState(0);
  const [refresh, refreshItems] = useState(0);
  useEffect(() => {
    if (initial && !version) return;
    let active = true;
    publicAccount("/account/session").then((data) => { if (active) setUser(accountView(data.account)); })
      .catch((e) => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  }, [initial, version]);
  useEffect(() => {
    if (!user || (initial && !version && !refresh)) return;
    let active = true;
    const load = async () => {
      if (ref) {
        const { item } = await readOwnedItem(ref);
        if (!active) return;
        if (isLegacyItemRef(ref)) {
          history.replaceState(null, "", `/mine/items/${item.public_id}`);
          setRef(item.public_id);
        }
        setItems([item]);
      } else {
        const data = await publicAccount(recordsPage ? "/me/records" : "/me/items");
        if (!active) return;
        if (recordsPage) setRecords(Array.isArray(data.records) ? data.records as LifecycleEvent[] : []);
        else setItems(Array.isArray(data.items) ? data.items.map(ownedItem) : []);
      }
      if (!active) return;
      setError("");
    };
    load().catch((e) => {
      if (!active) return;
      setError(errorText(e));
      if (e instanceof ApiError && [401, 404].includes(e.status)) { setItems(undefined); setRecords(undefined); }
      if (e instanceof ApiError && e.status === 401) setUser(null);
    });
    return () => { active = false; };
  }, [user, ref, recordsPage, version, refresh, initial]);
  useEffect(() => {
    const revisit = () => { if (document.visibilityState === "visible") refreshItems((value) => value + 1); };
    document.addEventListener("visibilitychange", revisit);
    window.addEventListener("pageshow", revisit);
    return () => { document.removeEventListener("visibilitychange", revisit); window.removeEventListener("pageshow", revisit); };
  }, []);
  async function logout() {
    try {
      await publicAccount("/account/logout", {});
      setItems(undefined);
      setRecords(undefined);
      setUser(null);
    } catch (e) { setError(errorText(e)); }
  }
  return (
    <div className="app">
      <PageHeader href={itemId || recordsPage ? "/mine" : "/tap"} label={itemId || recordsPage ? "我的数字物品" : "碰卡查看"} />
      <main className={itemId && user && items?.length ? "profile" : "profile flow"}>
        {!(itemId && user && items?.length) && <h1>{user === null ? "手机号登录／注册" : recordsPage ? "我的办理记录" : "我的数字物品"}</h1>}
        {error && <div className="notice" role="alert"><p>{error}</p><button onClick={() => { setError(""); retry(version + 1); }}>重试</button></div>}
        {(user === undefined || (user && !(recordsPage ? records : items))) && !error && <p role="status">正在加载资料</p>}
        {user === null && <Login onDone={(account) => { setUser(account); setError(""); }} />}
        {user && <>
          {!itemId && !recordsPage && <div className="account-actions"><span>{user.phone}</span><button className="text-action" onClick={logout}>退出登录</button></div>}
          {!itemId && !recordsPage && <a className="record-entry" href="/mine?tab=records">我的办理记录 →</a>}
          {recordsPage && records && <Timeline title="与你有关的办理" events={records} showItem />}
          {!recordsPage && items?.length === 0 && <p>碰一下你的物品，即可开始认领。</p>}
          {itemId && items?.[0] && <OwnedDetails key={items[0].public_id} item={items[0]} phone={user.phone} onRefresh={() => refreshItems((value) => value + 1)} />}
          {!itemId && items && <div className="owned-list">{items.map((item) => <a className="owned-row" key={item.public_id} href={`/mine/items/${item.public_id}`}>
            {item.image_urls[0] && <img className="product-image-frame" src={item.image_urls[0]} alt="" loading="lazy" referrerPolicy="no-referrer" />}
            <span><strong>{item.name || item.item_uid}</strong><small>{editionLabel(item) ? `发行编号 ${editionLabel(item)}` : item.item_uid}</small>
              {itemStage(item.lifecycle) && <small className="owned-stage">{itemStage(item.lifecycle)}</small>}</span><span aria-hidden="true">→</span>
          </a>)}</div>}
        </>}
      </main>
    </div>
  );
}
