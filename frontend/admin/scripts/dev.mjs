// Windows和命令行共用Umi启动方式；只监听本机固定测试端口。
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
const child = spawn(
  process.execPath,
  [
    fileURLToPath(
      new URL("../node_modules/@umijs/max/bin/max.js", import.meta.url),
    ),
    "dev",
  ],
  {
    cwd: new URL("..", import.meta.url),
    stdio: "inherit",
    env: { ...process.env, HOST: "127.0.0.1", PORT: "5174", BROWSER: "none" },
  },
);
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => child.kill(signal));
child.on("exit", (code) => process.exit(code ?? 1));
