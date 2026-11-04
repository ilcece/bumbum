# 页面与 Figma 怎么协作

目的：按页面接入Figma外观，同时保留真实接口和安全逻辑。Make管理端以cece本次上传的《设计项目管理后台.zip》为来源，仅桌面网页，不做移动适配或用户H5。操作见[桌面管理端手册](ADMIN_DESKTOP.md)，任务和验收分别见[TODO](../TODO.md)、[CHANGELOG](../CHANGELOG.md)。

## 当前页面放在哪里

后续管理端设计与实现遵守[A提案的官方复用及迁移约定](proposals/admin-management-update.md#31-官方复用定制与迁移约定已确认)，本文件不复制第二套组件/主题/定制规则。A业务规则已审核通过；[已有原型](proposals/admin-management-update.md#32-原型审核入口与交互取舍)仅供参考，不再调整，也不要求复刻。列表筛选查询、详情只读与编辑态等样式和交互优先采用Ant Design 6官方规范；PRD只定义业务要求。依赖、接口及上传存储的批准范围见[附条件批准的技术方案](proposals/admin-management-implementation.md)，已纳入的产品规则及现行界面按[后台规范](product/admin-management.md)。

下表是当前任务分支的真实分工；Ant Design 6已接入，人工验收、合并和部署状态仍见TODO，用户H5独立维护。旧Radix、ProComponents 2、v5补丁及lucide已移除，Tailwind仅编译Make布局样式，不同时维护两套控件。

| 文件 | 负责什么 |
|---|---|
| `frontend/admin/src/main.tsx` | 管理端入口，加载桌面样式和登录门禁 |
| `frontend/admin/src/LoginPanel.tsx` | 密码/验证码登录、会话恢复与退出，复用既有认证 |
| `frontend/admin/src/AdminLayout.tsx` | Layout/Menu桌面框架、真实库存/快捷操作、统计入口及已交付菜单，不列所有权占位 |
| `frontend/admin/src/TapStatisticsPanel.tsx`、`TapDailyChart.tsx` | 全项目有效触碰查询、卡片/明细、SVG日柱图及加载/失败状态；不写业务记录 |
| `frontend/admin/src/RuntimeChecks.tsx` | 真实后端/数据库检查，供登录页、顶栏和系统状态复用 |
| `frontend/admin/src/ChipPanel.tsx`、`CreateChip.tsx` | 官方查询表格、独立详情/批次编辑、登记并继续和精确关联返回；保留受控绑定与密钥规则 |
| `frontend/admin/src/ItemPanel.tsx` | Table物品列表、完整筛选分页、详情/编辑路由 |
| `frontend/admin/src/ItemDetailPage.tsx`、`itemFields.tsx` | 同字段详情/编辑、普通资料原子保存及独立启停；尺码只读保留 |
| `frontend/admin/src/CreateItem.tsx`、`ItemImages.tsx` | 连续创建及确切ID定位、受控Upload暂存/取消/未知结果，不重写上传列表 |
| `frontend/admin/src/MakeSurfaces.tsx`、`InventorySearch.tsx`、`make.css` | 从本次Make提取页面标题、详情/编辑容器、业务筛选分组与布局，不含模拟数据或权限 |
| `frontend/admin/src/NavigationGuard.tsx`、`adminNavigation.ts` | 官方路由阻断及安全返回位置，普通离开三选项 |
| `frontend/admin/src/AdminUI.tsx` | 共享反馈使用官方Alert，不保留旧弹窗/按钮封装 |
| `frontend/admin/src/style.css` | 保留的SVG图表局部样式；管理界面使用官方reset与主题、页面正常滚动 |
| `frontend/admin/src/api.ts` | 唯一接口调用层，保留Cookie、内存CSRF及失败处理 |
| `frontend/admin/vite.config.ts` | 保留本机地址和/api代理，接入Tailwind 4编译本次Make样式 |

当前功能范围见[接口实现概览](../API_CONTRACT.md#04-当前能做到哪一步)。Figma 调整时保留 LoginPanel 的状态处理及 api.ts 的认证逻辑，不把登录凭证搬到浏览器本地存储。正式管理页面以后仍使用这个 React + Vite + TypeScript 项目；现有用户工程位于frontend/user，后续按其实际任务修改，不再创建重复工程。本次Make已使用antd 6，因此复用Layout/Table/Form/Drawer/Modal的展示组合，旧Figma交互原型仍仅供参考；具体字段和交互约束以现行PRD及官方组件为准。Make原有本地样例、定时器成功、所有权和H5演示不接入业务；不复制其pnpm锁、Vite专有插件、AGENTS/CLAUDE或.figma脚本。React/TypeScript/Vite继续仓库固定版本，npm管理并锁定必要新依赖。

## cece 提供什么，AI 怎样接入

1. cece 指明要改哪个页面，提供 Figma 设计或导出内容，说明希望保留的操作与可检查的结果。
2. AI 先列出涉及的组件、样式和资源，再在现有前端中逐页接入；页面多起来时，按需要拆分页面和组件文件。
3. Figma 导出内容按需提取，不整包覆盖仓库，不直接替换依赖、构建配置或后端。
4. 视觉调整保留接口路径、字段、登录状态、防冒用检查和错误处理；如果设计需要改变业务规则或接口，先说明影响，并按 AGENTS 的授权规则同步相关文件。
5. 只有真实请求通过才能显示成功。设计中的模拟数据必须标注，接入时覆盖加载、无内容、失败、成功和桌面矮窗口情况；不把密钥或真实手机号放进设计文件。
6. AI 完成后运行前端构建并核对实际操作；cece 按设计确认外观和交互。说明哪些已接入、哪些仍是模拟或尚未实现。

## 文档怎样保持简洁

产品规则维护在 [PRD](../PRD.md)，接口维护在 [API_CONTRACT](../API_CONTRACT.md)，协作边界维护在 [AGENTS](../AGENTS.md)。本文件只维护页面接入方式，不复制整套业务和安全规则。手册从 [操作入口](OP_GUIDE.md) 查找，当前任务统一看 [TODO](../TODO.md)。启动与验证命令集中在 [本地运行说明](LOCAL_DEVELOPMENT.md)。


浏览器回归入口为tests/test_admin_browser.py，安装/运行只维护在[本地运行第9节](LOCAL_DEVELOPMENT.md#9-可重复的桌面浏览器回归)。CI在PR/main推送运行基础和隔离数据库/浏览器层；镜像/TLS层为手动开关。截图不含密码/验证码，不保留认证网络记录；配置存在不代表GitHub运行已通过，须看PR Checks。

用户手机工程为frontend/user，独立package-lock、Vite及自然页面滚动，不继承管理端的body限制。main.tsx维护触碰入口/资料页/状态与自动查询，ImageGallery.tsx维护图片切换与大图，api.ts集中请求、超时和响应校验；固定版本与admin一致，不引入新的UI或轮询依赖。持续查看、Cookie及公开入口见[技术附录第17节](IMPLEMENTATION_DETAILS.md#17-手机触碰资料页与公网链路技术方案待审核)，本机及公网验收分别取证；代码存在不代表当前杭州服务器已更新；香港部署仅作历史证据。
