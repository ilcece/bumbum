import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { checkBackend, checkDatabase } from "./api";
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
        <p className="step">第 1 步 · 运行检查</p>
        <h1>开发环境检查</h1>
        <p>两个检查都通过，就可以继续下一步的管理员登录开发。</p>
      </header>
      <section className="checks" aria-label="运行检查结果" aria-live="polite" aria-busy={checking}>
        <StatusCard title="后端程序" status={backend}
          success="已启动" failure="无法连接"
          help="检查失败时，确认启动后端的终端仍在运行，再重新检查。" />
        <StatusCard title="测试数据库" status={database}
          success="连接正常" failure={backend === "failed" ? "暂时无法检查" : "尚未就绪"}
          help={backend === "failed" ? "先启动后端，再重新检查数据库。" : "检查失败时，先按启动说明确认测试数据库已启动，再重新检查。"} />
      </section>
      <button type="button" onClick={() => void refresh()} disabled={checking}>
        {checking ? "正在检查…" : "重新检查"}
      </button>
      <footer>当前只检查运行环境，管理员登录和芯片业务尚未接入。</footer>
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
