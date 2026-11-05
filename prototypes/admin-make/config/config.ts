// 由官方Ant Design Pro固定工程裁剪，移除示例接口、分析、录制及发布功能。
import { defineConfig } from "@umijs/max";
import defaultSettings from "./defaultSettings";
import routes from "./routes";
export default defineConfig({
  npmClient: "npm",
  hash: true,
  publicPath: process.env.NODE_ENV === "production" ? "./" : "/",
  history: { type: "hash" },
  routes,
  title: "BUMBUM 数字物品管理",
  layout: { locale: false, ...defaultSettings },
  model: {},
  initialState: {},
  access: {},
  antd: {},
  request: {},
  mfsu: false,
  esbuildMinifyIIFE: true,
  devtool: false,
  targets: { chrome: 100 },
  headScripts: [],
  favicons: ["./favicon.svg"],
});
