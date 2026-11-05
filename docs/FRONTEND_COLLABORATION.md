# 后台页面与前端工程怎样协作

<a name="页面与-figma-怎么协作"></a>

目的：在已确认业务范围内使用官方页面模式，保留真实接口和安全逻辑。新版后台定位、字段及审核顺序从[聚合方案](proposals/admin-make-rebuild.md)进入，设计按[统一规范](ADMIN_UI_GUIDELINES.md)，工程路线按[Umi迁移说明](proposals/admin-rebuild-implementation.md)。cece本轮建议完整官方Ant Design Pro工程迁入Umi Max，替代此前保留Vite只接组件的推荐；方案已通过并授权重建隔离原型，正式代码尚未切换。

此前Make、旧Figma和旧长经营原型保留为历史参考。cece本轮提供《设计项目管理后台.zip》作为当前视觉参考，只提取布局、主题和控件交互，以Pro组件适配现有原型，不导入附件旧菜单/字段、登录或业务逻辑。Figma附件按实际页面需要提取，不整包覆盖源码、依赖、认证或后端。当前操作见[桌面管理端手册](ADMIN_DESKTOP.md)，状态只看[TODO](../TODO.md)。

## 独立交互原型与正式工程

本次已授权的高保真交互原型位于[prototypes/admin-make](../prototypes/admin-make/README.md)，可下载[单HTML](../prototypes/admin-make/preview.html)离线核对；当前版本已按收口方案以实际官方Umi/Pro工程重建，旧Make及长经营流程由Git保留。它使用浏览器合成数据，不调用真实API，不是正式后台，也不替代下表工程。原型的构建和业务路径检查不代表正式代码、后端、实卡或人工验收完成。产品和必要技术范围现已通过，新预览采用官方Umi/Pro工程，并复用同套页面接真实服务；交互与正式能力分别验收，不再先重画旧Make再迁移。当前任务状态见TODO。

## 当前页面放在哪里

后续设计与实现以聚合稿、字段表和统一规范为依据；已交付A规则继续由[现行后台规范](product/admin-management.md)及[芯片规范](product/chip-lifecycle.md)维护。旧A/B/C/D路径只留兼容入口，批准的既有能力不被文档重组撤回，未定业务/技术也不因重组获批。

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
| `frontend/admin/src/style.css` | 保留的SVG图表局部样式；当前实现使用官方reset与主题；后续按新规范调整应用壳/内容独立滚动 |
| `frontend/admin/src/api.ts` | 唯一接口调用层，保留Cookie、内存CSRF及失败处理 |
| `frontend/admin/vite.config.ts` | 保留本机地址和/api代理，接入Tailwind 4编译本次Make样式 |

当前功能范围见[接口实现概览](../API_CONTRACT.md#04-当前能做到哪一步)。Figma 调整时保留 LoginPanel 的状态处理及 api.ts 的认证逻辑，不把登录凭证搬到浏览器本地存储。现有正式管理端仍为React + Vite + TypeScript，下一目标推荐完整官方Umi Max/Ant Design Pro工程，迁移落在frontend/admin。具体路由、请求/会话、构建和启动脚本适配见工程说明，不把组件安装等同完整迁入。用户工程frontend/user保持独立Vite，后端与NFC安全方案保留。未实施前不改现行启动命令；实施时用npm锁定核定版本并更新原本地运行说明，不复制官方无关示例/假接口/外部分析或演示发布脚本。

字段展示按[业务字段表](proposals/admin-rebuild-fields.md)承接：界面称“实体”，共用发行约定、数字身份和每次实体交付分开；目标为共用资料统一维护并同步引用，实体交付信息独立保留；当前正式应用仍逐件保存，迁移须另审。重构的物品类别只在款式维护，其他页面按引用展示/筛选，不能保留多处独立“所属项目”输入；隔离原型已按批准架构落实来源与文案；现有正式project接口/数据仍需技术适配。未交付字段在技术实施前补齐契约，不从原型假定后端支持。

独立原型中的〔演示〕Webhook触发/重复/鉴权失败、假登录、密钥占位、样例核验/诊断、故障注入、fixtures和会话样例均不进入正式构建；真实Webhook登记能力继续保留，并接真实接口及认证/幂等规则，不能移植模拟成功处理。原型入口及核对步骤见[原型说明](../prototypes/admin-make/README.md)。

## cece 提供什么，AI 怎样接入

1. cece 指明要改哪个页面，提供 Figma 设计或导出内容，说明希望保留的操作与可检查的结果。
2. AI先读统一规范，列出业务场景、复用的原稿/官方页面模式，以及拟改入口、字段、步骤、容器和必要偏离；与cece对齐后才修改。已批准范围内连续实施，主要信息层级或入口变化先重新对齐。
3. Figma 导出内容按需提取，不整包覆盖仓库，不直接替换依赖、构建配置或后端。
4. 视觉调整保留接口路径、字段、登录状态、防冒用检查和错误处理；如果设计需要改变业务规则或接口，先说明影响，并按 AGENTS 的授权规则同步相关文件。
5. 只有真实请求通过才能显示成功。设计中的模拟数据必须标注，接入时覆盖加载、无内容、失败、成功和桌面矮窗口情况；不把密钥或真实手机号放进设计文件。
6. AI按改动范围做构建、受影响业务与实际视觉核对，覆盖查询返回、详情/编辑、操作栏和矮窗口；cece确认外观和交互。说明复用与定制原因、已接入及模拟范围。React 19独立组件冒烟不默认执行；确有需要先给理由、范围和预计耗时，获cece明确批准后再跑。

## 文档怎样保持简洁

产品规则维护在 [PRD](../PRD.md)，接口维护在 [API_CONTRACT](../API_CONTRACT.md)，协作边界维护在 [AGENTS](../AGENTS.md)。本文件只维护页面接入方式，不复制整套业务和安全规则。手册从 [操作入口](OP_GUIDE.md) 查找，当前任务统一看 [TODO](../TODO.md)。启动与验证命令集中在 [本地运行说明](LOCAL_DEVELOPMENT.md)。


浏览器回归入口为tests/test_admin_browser.py，安装/运行只维护在[本地运行第9节](LOCAL_DEVELOPMENT.md#9-可重复的桌面浏览器回归)。CI在PR/main推送运行基础和隔离数据库/浏览器层；镜像/TLS层为手动开关。截图不含密码/验证码，不保留认证网络记录；配置存在不代表GitHub运行已通过，须看PR Checks。

用户手机工程为frontend/user，独立package-lock、Vite及自然页面滚动，不继承管理端的body限制。main.tsx维护触碰入口/资料页/状态与自动查询，ImageGallery.tsx维护图片切换与大图，api.ts集中请求、超时和响应校验；固定版本与admin一致，不引入新的UI或轮询依赖。持续查看、Cookie及公开入口见[技术附录第17节](IMPLEMENTATION_DETAILS.md#17-手机触碰资料页与公网链路技术方案待审核)，本机及公网验收分别取证；代码存在不代表当前杭州服务器已更新；香港部署仅作历史证据。
