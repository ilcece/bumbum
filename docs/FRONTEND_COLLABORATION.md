# 页面与 Figma 怎么协作

目的：按页面接入Figma外观，同时保留真实接口和安全逻辑。Make管理端以cece上传的bumbum.zip为来源，仅桌面网页，不做移动适配或用户H5。操作见[桌面管理端手册](ADMIN_DESKTOP.md)，任务和验收分别见[TODO](../TODO.md)、[CHANGELOG](../CHANGELOG.md)。

## 当前页面放在哪里

| 文件 | 负责什么 |
|---|---|
| `frontend/admin/src/main.tsx` | 管理端入口，加载桌面样式和登录门禁 |
| `frontend/admin/src/LoginPanel.tsx` | 密码/验证码登录、会话恢复与退出，复用既有认证 |
| `frontend/admin/src/AdminLayout.tsx` | Make桌面框架、工作台全局库存/快捷操作、统计组件入口、所有权页占位、导航和统一未实现提示 |
| `frontend/admin/src/TapStatisticsPanel.tsx`、`TapDailyChart.tsx` | 全项目有效触碰查询、卡片/明细、SVG日柱图及加载/失败状态；不写业务记录 |
| `frontend/admin/src/RuntimeChecks.tsx` | 真实后端/数据库检查，供登录页、顶栏和系统状态复用 |
| `frontend/admin/src/ChipPanel.tsx` | 登记弹窗、真实筛选分页及批次/首次来源，不模拟保存 |
| `frontend/admin/src/ItemPanel.tsx` | 创建弹窗、真实物品列表、筛选分页与资料入口 |
| `frontend/admin/src/ItemProfileEditor.tsx` | 服装资料弹窗、保存/启停、图片与未保存提醒，不含尺码表 |
| `frontend/admin/src/AdminUI.tsx`、`components/ui/` | 复用Make的弹窗/按钮及反馈组件，不提前扩展设计系统 |
| `frontend/admin/src/style.css`、`design.css` | Tailwind入口、Make桌面变量和样式，body禁止滚动、区域内部滚动 |
| `frontend/admin/src/api.ts` | 唯一接口调用层，保留Cookie、内存CSRF及失败处理 |
| `frontend/admin/vite.config.ts` | 保留本机地址和/api代理，仅增加Tailwind构建插件 |

当前功能范围见[接口实现概览](../API_CONTRACT.md#04-当前能做到哪一步)。Figma 调整时保留 LoginPanel 的状态处理及 api.ts 的认证逻辑，不把登录凭证搬到浏览器本地存储。正式管理页面以后仍使用这个 React + Vite + TypeScript 项目；用户侧页面按实际任务再建立，不先堆空目录。Make原有本地样例、定时器成功、所有权和H5演示不接入业务；不复制其pnpm锁、Vite专有插件、AGENTS/CLAUDE或.figma脚本。React/TypeScript/Vite继续仓库固定版本，npm管理并锁定必要新依赖。

## cece 提供什么，AI 怎样接入

1. cece 指明要改哪个页面，提供 Figma 设计或导出内容，说明希望保留的操作与可检查的结果。
2. AI 先列出涉及的组件、样式和资源，再在现有前端中逐页接入；页面多起来时，按需要拆分页面和组件文件。
3. Figma 导出内容按需提取，不整包覆盖仓库，不直接替换依赖、构建配置或后端。
4. 视觉调整保留接口路径、字段、登录状态、防冒用检查和错误处理；如果设计需要改变业务规则或接口，先说明影响，并按 AGENTS 的授权规则同步相关文件。
5. 只有真实请求通过才能显示成功。设计中的模拟数据必须标注，接入时覆盖加载、无内容、失败、成功和桌面矮窗口情况；不把密钥或真实手机号放进设计文件。
6. AI 完成后运行前端构建并核对实际操作；cece 按设计确认外观和交互。说明哪些已接入、哪些仍是模拟或尚未实现。

## 文档怎样保持简洁

产品规则维护在 [PRD](../PRD.md)，接口维护在 [API_CONTRACT](../API_CONTRACT.md)，协作边界维护在 [AGENTS](../AGENTS.md)。本文件只维护页面接入方式，不复制整套业务和安全规则。手册从 [操作入口](op_guide.md) 查找，当前任务统一看 [TODO](../TODO.md)。启动与验证命令集中在 [本地运行说明](LOCAL_DEVELOPMENT.md)。


浏览器回归入口为tests/test_admin_browser.py，安装/运行只维护在[本地运行第9节](LOCAL_DEVELOPMENT.md#9-可重复的桌面浏览器回归)。CI在PR/main推送运行基础和隔离数据库/浏览器层；镜像/TLS层为手动开关。截图不含密码/验证码，不保留认证网络记录；配置存在不代表GitHub运行已通过，须看PR Checks。

手机页后续工程提案为frontend/user，与admin样式及构建入口隔离；前台自动更新、只读Cookie及公网发布尚未实现，先按[技术附录第17节](IMPLEMENTATION_DETAILS.md#17-手机触碰资料页与公网链路技术方案待审核)审核。本表仍只列当前实际存在的组件，不把提案路径当成已接入。
