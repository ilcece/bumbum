import { useEffect, useState } from "react";
import { ApiError, lostContact } from "./api";

export function LostRecovery() {
  const [state, setState] = useState<"loading" | "available" | "private" | "expired" | "error">("loading");
  const [phone, setPhone] = useState("");
  const [revealing, setRevealing] = useState(false);
  function failed(error: unknown) {
    setPhone("");
    setState(error instanceof ApiError && error.status === 403 ? "expired" : "error");
  }
  useEffect(() => {
    let active = true;
    let controller: AbortController | undefined;
    const load = () => {
      setPhone("");
      controller?.abort();
      if (document.visibilityState !== "visible") return;
      const request = new AbortController();
      controller = request;
      lostContact(request.signal).then((data) => {
        if (active && !request.signal.aborted) setState(data.contact_available === true ? "available" : "private");
      }).catch((error) => { if (active && !request.signal.aborted) failed(error); });
    };
    load();
    document.addEventListener("visibilitychange", load);
    return () => { active = false; controller?.abort(); document.removeEventListener("visibilitychange", load); };
  }, []);
  async function reveal() {
    setRevealing(true);
    try {
      const data = await lostContact(new AbortController().signal, true);
      if (document.visibilityState !== "visible") return;
      if (typeof data.phone === "string" && /^1[3-9]\d{9}$/.test(data.phone)) setPhone(data.phone);
      else setState("private");
    } catch (error) { failed(error); }
    finally { setRevealing(false); }
  }
  return <section className="recovery-panel">
    {state === "loading" ? <p role="status">正在打开找回页面</p> : state === "expired" ? <><h1>请重新碰一下这件物品</h1><p>打开新出现的提示，查看是否能联系失主。</p></> :
      state === "error" ? <><h1>暂时打不开找回页面</h1><p>请检查网络后重新碰一下这件物品。</p></> : <>
      <h1>这件物品已挂失</h1>
      {state === "private" ? <p>如果你拾到了这件物品，可交给拾获地点的失物招领处。</p> : <>
        <p>如果你拾到了这件物品，可以联系失主归还。</p>
        {phone ? <div className="notice" role="status" data-private><p>失主电话</p><a href={`tel:${phone}`}>{phone} · 拨打电话</a></div> :
          <button className="primary" disabled={revealing} onClick={reveal}>{revealing ? "正在查看" : "联系失主"}</button>}
      </>}
    </>}
  </section>;
}
