import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss()],
  // 只把 VITE_ 开头的公开配置交给网页；数据库密码不进入前端。
  envDir: "../..",
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    // 网页访问自己的 /api，再由开发服务器转给后端，不另开跨域入口。
    proxy: { "/api": "http://127.0.0.1:5000" },
  },
});
