import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { checkBackend, checkDatabase } from "./api";
import { LoginPanel } from "./LoginPanel";
import "./style.css";

type Status = "checking" | "ok" | "failed";

function App() {
  const [backend, setBackend] = useState<Status>("checking");
  const [database, setDatabase] = useState<Status>("checking");
  const checking = backend === "checking" || database === "checking";

  async function refresh() {
    setBackend("checking");
    setDatabase("checking");
    await Promise.allSettled([
      checkBackend().then(() => setBackend("ok"), () => setBackend("failed")),
      checkDatabase().then(() => setDatabase("ok"), () => setDatabase("failed")),
    ]);
  }

  useEffect(() => { void refresh(); }, []);

  return (
    <main>
      <header>
        <p className="brand">BUMBUM</p>
        <p className="step">第 3 步 · 芯片登记</p>
        <h1>芯片管理验证</h1>
        <p>先确认运行环境，再使用已创建的管理员账号登录。</p>
      </header>
      <section className="checks" aria-label="运行检查结果" aria-live="polite" aria-busy={checking}>
        <StatusCard title="后端程序" status={backend}
          success="已启动" failure="无法连接"
          help="检查失败时，确认后端服务已启动，再重新检查。" />
        <StatusCard title="测试数据库" status={database}
          success="连接正常" failure={backend === "failed" ? "暂时无法检查" : "尚未就绪"}
          help={backend === "failed" ? "先启动后端，再重新检查数据库。" : "检查失败时，先按启动说明确认测试数据库已启动，再重新检查。"} />
      </section>
      <button type="button" onClick={() => void refresh()} disabled={checking}>
        {checking ? "正在检查…" : "重新检查"}
      </button>
      <LoginPanel />
      <footer>当前可登录、登记和查询芯片，创建和查询物品草稿，编辑服装基础资料及启停；芯片绑定和写卡后续接入。</footer>
    </main>
  );
}

function StatusCard({ title, status, success, failure, help }: {
  title: string; status: Status; success: string; failure: string; help: string;
}) {
  return (
    <article className={`card ${status}`}>
      <h2>{title}</h2>
      <p className="result">{status === "checking" ? "检查中…" : status === "ok" ? success : failure}</p>
      <p>{status === "ok" ? "本项已通过。" : status === "checking" ? "正在连接，请稍等。" : help}</p>
    </article>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
