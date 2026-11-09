import { useEffect, useState, type FormEvent } from "react";
import { itemFacts } from "../../shared/itemPresentation";
import { accountView, ApiError, ownedItem, publicAccount, type Account, type ItemView, type OwnedItem } from "./api";
import { ImageGallery } from "./ImageGallery";

const errorText = (error: unknown) => error instanceof Error ? error.message : "暂时无法处理，请稍后重试。";
const date = (value: string) => new Date(value).toLocaleDateString("zh-CN", { timeZone: "Asia/Shanghai" });

function Login({ onDone }: { onDone: (account: Account) => void }) {
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
      <h2>手机号登录／注册</h2>
      <label>手机号<input type="tel" inputMode="tel" autoComplete="tel-national" maxLength={11} value={phone} onChange={(event) => { setPhone(event.target.value); setChallenge(""); }} /></label>
      <button type="button" onClick={send} disabled={busy || cooldown > 0 || !/^1[3-9]\d{9}$/.test(phone.trim())}>
        {cooldown ? `${cooldown} 秒后可重发` : "发送短信验证码"}
      </button>
      {challenge && <>
        <label>短信验证码<input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value)} /></label>
        <button disabled={busy || !/^\d{6}$/.test(code)}>验证并继续</button>
      </>}
      {error && <p className="notice" role="alert">{error}</p>}
    </form>
  );
}

function rememberClaim(itemId: number | null) {
  try {
    if (itemId) sessionStorage.setItem("bumbum-claim-item", String(itemId));
    else sessionStorage.removeItem("bumbum-claim-item");
  } catch { /* 隐私模式仍可完成当前页认领。 */ }
}

export function ClaimPanel({ item, tapToken }: { item: ItemView; tapToken?: string }) {
  const [open, setOpen] = useState(() => {
    try { return sessionStorage.getItem("bumbum-claim-item") === String(item.item_id); }
    catch { return false; }
  });
  const [user, setUser] = useState<Account | null>();
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<"mine" | "claimed" | "unknown">();
  const [retap, setRetap] = useState(false);
  useEffect(() => setRetap(false), [tapToken]);
  useEffect(() => {
    if (item.claim_state !== "claimed") return;
    let active = true;
    publicAccount(`/items/${item.item_id}/claim-status`).then((data) => {
      if (active && data.state === "mine") setResult("mine");
    }).catch(() => { /* 访客仍可看到公共已认领状态。 */ });
    return () => { active = false; };
  }, [item.claim_state, item.item_id]);
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
    const recover = () => publicAccount(`/items/${item.item_id}/claim-status`).then((data) => {
      if (!active) return;
      if (data.state === "mine" || data.state === "claimed") {
        setResult(data.state);
        rememberClaim(null);
      } else setResult(undefined);
      setError("");
    }).catch((e) => { if (active) setError(errorText(e)); });
    void recover();
    window.addEventListener("online", recover);
    return () => { active = false; window.removeEventListener("online", recover); };
  }, [item.item_id, result]);
  async function claim(event: FormEvent) {
    event.preventDefault();
    if (!tapToken) return;
    setBusy(true);
    setError("");
    try {
      await publicAccount(`/items/${item.item_id}/claim`, { tap_token: tapToken, claim_code: code.trim() });
      setCode("");
      setResult("mine");
      rememberClaim(null);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 0 || e.status >= 500)) setResult("unknown");
      else if (e instanceof ApiError && e.code === "already_claimed") { setResult("claimed"); rememberClaim(null); }
      else {
        setError(errorText(e));
        if (e instanceof ApiError && e.status === 401) setUser(null);
        if (e instanceof ApiError && e.code === "retap_required") setRetap(true);
      }
    } finally {
      setBusy(false);
    }
  }
  if (result === "mine") return <section className="profile-section" role="status"><h2>已认领到我的数字物品</h2><a href={`/mine/items/${item.item_id}`}>查看我的物品</a></section>;
  if (result === "claimed" || item.claim_state === "claimed") return <section className="profile-section"><h2>已认领</h2><p>如有疑问请联系 BUMBUM。</p><a href="/mine">我的数字物品</a></section>;
  if (item.claim_state !== "available" && result !== "unknown") return item.claim_state ? <p className="profile-section">{item.claim_state === "expired" ? "认领码已过期，请联系 BUMBUM 核对交付后补发。" : "暂未开放认领"}</p> : null;
  if (!open) return <button onClick={() => { rememberClaim(item.item_id); setOpen(true); }}>认领这件物品</button>;
  return (
    <section className="profile-section">
      <h2>认领 {item.profile.name}</h2>
      {result === "unknown" ? <p role="status">正在核对认领结果。网络恢复后会再次查询。</p> : !tapToken || retap ? <p>请重新碰一下物品，再继续认领。</p> :
        user === undefined ? <p role="status">正在读取登录状态</p> : user === null ? <Login onDone={(value) => { setUser(value); setError(""); }} /> : (
          <form className="account-form" onSubmit={claim}>
            <p>认领账户 {user.phone}</p>
            <label>交付认领码<input autoCapitalize="characters" autoComplete="off" maxLength={24} value={code} onChange={(event) => setCode(event.target.value)} /></label>
            <button disabled={busy || !code.trim()}>确认认领</button>
          </form>
        )}
      {error && <p className="notice" role="alert">{error}</p>}
      <button className="text-action" onClick={() => { rememberClaim(null); setOpen(false); setCode(""); setError(""); }}>返回物品资料</button>
    </section>
  );
}

export function MyItemsPage({ itemId }: { itemId?: number }) {
  const [user, setUser] = useState<Account | null>();
  const [items, setItems] = useState<OwnedItem[]>();
  const [error, setError] = useState("");
  const [version, retry] = useState(0);
  useEffect(() => {
    let active = true;
    publicAccount("/account/session").then((data) => { if (active) setUser(accountView(data.account)); })
      .catch((e) => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  }, [version]);
  useEffect(() => {
    if (!user) return;
    let active = true;
    publicAccount(itemId ? `/me/items/${itemId}` : "/me/items").then((data) => {
      if (active) setItems(itemId ? [ownedItem(data.item)] : Array.isArray(data.items) ? data.items.map(ownedItem) : []);
    }).catch((e) => {
      if (active) { setError(errorText(e)); if (e instanceof ApiError && e.status === 401) setUser(null); }
    });
    return () => { active = false; };
  }, [user, itemId]);
  async function logout() {
    try {
      await publicAccount("/account/logout", {});
      setItems(undefined);
      setUser(null);
    } catch (e) { setError(errorText(e)); }
  }
  return (
    <div className="app">
      <header className="brand"><span className="brand-mark">b.</span><strong>BUMBUM</strong><a className="brand-caption" href={itemId ? "/mine" : "/tap"}>{itemId ? "返回我的" : "碰卡查看"}</a></header>
      <main className="profile">
        <h1>{itemId && items?.[0]?.name ? items[0].name : "我的数字物品"}</h1>
        {error && <div className="notice" role="alert"><p>{error}</p><button onClick={() => { setError(""); retry(version + 1); }}>重试</button></div>}
        {user === undefined && !error && <p role="status">正在读取登录状态</p>}
        {user === null && <Login onDone={(account) => { setUser(account); setError(""); }} />}
        {user && <>
          <div className="account-actions"><span>{user.phone}</span><button onClick={logout}>退出登录</button></div>
          {!items && !error && <p role="status">正在读取物品</p>}
          {items?.length === 0 && <p>碰一下你的物品，即可开始认领。</p>}
          {items?.map((item) => itemId ? <article key={item.item_id}>
            <p className="eyebrow">你持有这件物品</p>
            <ImageGallery urls={item.image_urls} name={item.name || item.item_uid} />
            {itemFacts(item).map((fact) => <p key={fact.label}>{fact.label} {fact.value}</p>)}
            <p>认领或接续日期 {date(item.bound_at)}</p>
            {item.generation && <p>当前实体 第 {item.generation} 代 {item.spec}</p>}
            <p>{item.quota_review ? "本年换新用量待核对" : item.quota_year ? `${item.quota_year} 年已换新 ${item.quota_used ?? 0} 次` : "暂无年度换新记录"}</p>
          </article> : <a className="owned-row" key={item.item_id} href={`/mine/items/${item.item_id}`}>
            {item.image_urls[0] && <img src={item.image_urls[0]} alt="" loading="lazy" referrerPolicy="no-referrer" />}
            <span><strong>{item.name || item.item_uid}</strong><br />{itemFacts(item).find((fact) => fact.label === "发行编号")?.value || item.item_uid}</span>
          </a>)}
        </>}
      </main>
    </div>
  );
}
