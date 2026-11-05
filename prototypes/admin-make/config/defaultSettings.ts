// 使用官方布局Token承接附件的浅色侧栏、蓝色选中态和紧凑顶栏。
import type { ProLayoutProps } from "@ant-design/pro-components";
const settings: ProLayoutProps = {
  navTheme: "light",
  colorPrimary: "#1677ff",
  layout: "mix",
  splitMenus: false,
  siderWidth: 248,
  contentWidth: "Fixed",
  fixedHeader: true,
  fixSiderbar: true,
  title: "BUMBUM",
  logo: false,
  token: {
    bgLayout: "#f5f7fa",
    header: {
      colorBgHeader: "#ffffff",
      colorBgScrollHeader: "#ffffff",
      colorHeaderTitle: "#0f172a",
      heightLayoutHeader: 58,
    },
    sider: {
      colorMenuBackground: "#ffffff",
      colorBgMenuItemSelected: "#e6f4ff",
      colorBgMenuItemHover: "#f1f5f9",
      colorTextMenuSelected: "#1677ff",
      colorTextMenu: "#334155",
      colorTextMenuTitle: "#0f172a",
      colorMenuItemDivider: "#e2e8f0",
      menuHeight: 40,
      paddingInlineLayoutMenu: 8,
      paddingBlockLayoutMenu: 12,
    },
    pageContainer: {
      colorBgPageContainer: "#f5f7fa",
      paddingInlinePageContainerContent: 20,
      paddingBlockPageContainerContent: 16,
    },
  },
};
export default settings;
