import { defineConfig } from "vite";

export default defineConfig({
  // 用户页与管理页分开构建，同源代理不放开管理端CORS。
  build: { target: "es2020" },
  server: {
    host: "127.0.0.1",
    port: 5175,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:5000" },
  },
});
