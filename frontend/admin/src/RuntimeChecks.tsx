import { useEffect, useState } from "react";
import { checkBackend, checkDatabase } from "./api";
import { RefreshCw } from "lucide-react";

type State = "checking" | "ok" | "failed";
export function RuntimeChecks() {
  const [states, setStates] = useState<State[]>(["checking", "checking"]);
  async function refresh() {
    setStates(["checking", "checking"]);
    await Promise.allSettled(
      [checkBackend, checkDatabase].map((check, index) =>
        check().then(
          () =>
            setStates((current) =>
              current.map((value, i) => (i === index ? "ok" : value)),
            ),
          () =>
            setStates((current) =>
              current.map((value, i) => (i === index ? "failed" : value)),
            ),
        ),
      ),
    );
  }
  useEffect(() => {
    void refresh();
  }, []);
  return (
    <section aria-label="运行检查结果">
      <div className="checks-grid">
        {["后端程序", "测试数据库"].map((title, index) => (
          <div className="panel check-card" key={title}>
            <h3>{title}</h3>
            <p className={`check-result ${states[index]}`}>
              {states[index] === "ok"
                ? "检查通过"
                : states[index] === "failed"
                  ? "检查失败"
                  : "检查中…"}
            </p>
            <p>
              {states[index] === "failed"
                ? "请按本地运行手册核对服务，再重新检查。"
                : "本项只代表当前运行检查结果。"}
            </p>
          </div>
        ))}
      </div>
      <button
        className="action"
        disabled={states.includes("checking")}
        onClick={() => void refresh()}
      >
        <RefreshCw size={16} />
        重新检查
      </button>
    </section>
  );
}
