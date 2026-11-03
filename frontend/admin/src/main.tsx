import "@ant-design/v5-patch-for-react-19";
import "antd/dist/reset.css";
import { createRoot } from "react-dom/client";
import { App, ConfigProvider } from "antd";
import zhCN from "antd/es/locale/zh_CN";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { LoginPanel } from "./LoginPanel";
import "./style.css";

const router = createBrowserRouter([{ path: "*", element: <LoginPanel /> }]);
createRoot(document.getElementById("root")!).render(
  <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: "#2563eb", fontFamily: 'Inter, "Microsoft YaHei", system-ui, sans-serif' } }}>
    <App><RouterProvider router={router} /></App>
  </ConfigProvider>,
);
