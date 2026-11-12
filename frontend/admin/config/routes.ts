// 菜单和页面共用官方Umi配置路由，不保留订单/工厂/物流工作区。
export default [
  { path: "/login", layout: false, component: "./Login" },
  { path: "/", redirect: "/overview" },
  {
    path: "/overview",
    name: "工作台",
    icon: "dashboard",
    component: "./Overview",
  },
  { path: "/overview/activity", component: "./Activity", hideInMenu: true },
  {
    path: "/catalog",
    name: "款式与发行",
    icon: "appstore",
    component: "./Catalog",
  },
  { path: "/catalog/style/:id", component: "./StyleEditor", hideInMenu: true },
  { path: "/catalog/issue/:id", component: "./IssueEditor", hideInMenu: true },
  { path: "/items", name: "数字物品", icon: "inbox", component: "./Items" },
  { path: "/items/:id", component: "./ItemDetail", hideInMenu: true },
  { path: "/chips", name: "芯片管理", icon: "qrcode", component: "./Chips" },
  { path: "/chips/:id", component: "./ChipDetail", hideInMenu: true },
  { path: "/system", name: "系统管理", icon: "setting", component: "./System" },
  { path: "/*", component: "./NotFound" },
];
