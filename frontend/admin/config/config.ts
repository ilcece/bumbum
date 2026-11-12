// 基于已验收官方Pro工程；仅管理端迁入Umi，用户端仍独立运行。
import { defineConfig } from "@umijs/max";
import settings from "./defaultSettings";
import routes from "./routes";
export default defineConfig({
  npmClient: "npm",
  hash: true,
  publicPath: "/",
  history: { type: "browser" },
  routes,
  title: "BUMBUM 数字物品管理",
  layout: { locale: false, ...settings },
  model: {},
  initialState: {},
  antd: {},
  mfsu: false,
  esbuildMinifyIIFE: true,
  devtool: false,
  targets: { chrome: 100 },
  proxy: { "/api": { target: "http://127.0.0.1:5000", changeOrigin: false } },
  favicons: ["/favicon.svg"],
});
