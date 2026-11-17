# 后台页面与前端工程怎样协作

<a name="页面与-figma-怎么协作"></a>

本文说明当前前端如何组织、怎样接入设计。业务规则从[后台管理](product/admin-management.md)、[数字档案](product/digital-catalog.md)及[用户 H5](product/user-h5.md)进入；字段在[业务字段](product/admin-fields.md)，共用界面规则在[后台设计规范](ADMIN_UI_GUIDELINES.md)。当前任务及人工验收只看 [TODO](../TODO.md)，实际发布从[杭州发布入口](HANGZHOU_DEPLOYMENT.md#current-releases)核对。

## 独立交互原型与正式工程

[prototypes/admin-make](../prototypes/admin-make/README.md)及其[单 HTML](../prototypes/admin-make/preview.html)保留2026年11月5–6日的已评审原型和当时证据。它使用浏览器合成数据，不调用真实API；其中当时的菜单、版本、演示认证和未接入说明不能覆盖后来正式系统。页面对照按现行设计规范和对应历史截图判断，不把旧原型当作需要同步维护的另一套应用。

Umi迁移的官方来源、版本冲突和当时验证记录见[历史工程说明](archive/admin-rebuild-implementation-2026-11-17.md)。正式后台已使用Umi Max/Ant Design Pro；保留真实会话、接口及安全保护。Make、Figma及上传附件只按本次页面需要提取视觉和交互，不能整包覆盖依赖、菜单、登录或业务。

## 当前页面放在哪里

下表对应正式工程。管理端使用AntD/Pro组件、主题Token和必要局部CSS，没有另行维护Make或Tailwind布局编译链；Umi锁文件中的传递工具包不代表项目采用了另一套样式体系。固定版本分别以各工程的package.json及package-lock.json为准。

| 文件 | 负责什么 |
|---|---|
| `frontend/admin/src/app.tsx`、`config/` | Umi运行时、真实会话、路由、菜单与官方布局；没有演示登录 |
| `frontend/admin/src/pages/` | 工作台、订单、数字/实体物品、款式与发行、芯片、用户及系统页面；详情按真实ID和来源路由进入 |
| `frontend/admin/src/components/` | 共用表格、读取失败、资料展示、表单、装配、发码、接续与受控查看；复杂业务区域按对象组织子组件 |
| `frontend/admin/src/hooks/`、`types/` | 共用记录读取/业务动作状态和接口类型；写入未知结果、失效会话及错误语义仍沿用原接口约定 |
| `frontend/admin/src/catalog.ts`、`api/` | 数字档案请求、响应及业务动作入口，统一服务端范围、分页及写回执；不复制原型数组作为正式查询 |
| `frontend/admin/src/api.ts`、`ChipKeysDialog.tsx` | Cookie、内存CSRF、登录/退出及密钥/配置安全流程 |
| `frontend/admin/src/testDataMode.ts`、`components/TestBatches.tsx` | 仅设置中的全局验收数据开关、统一请求范围和批次维护 |
| `frontend/admin/src/global.css` | 业务所需局部样式；布局、控件和滚动优先使用官方组件 |
| `frontend/user/src/` | 独立Vite手机应用：碰卡、档案、账户、认领、找回、图集及持有记录 |
| `frontend/shared/` | 两个正式应用共同使用的展示规则和品牌资源，不承担认证或业务写入 |

同一业务内容只维护一处。类别和共用名称、介绍、图片在款式维护，物品与实体按引用展示，实际交付规格另存。旧单件接口只在已说明的历史兼容范围读取和维护。页面中的字段、只读状态、权限与错误码以现行产品和[接口契约](../API_CONTRACT.md)为准。

独立原型的假登录、Webhook模拟、密钥占位、假核验、故障注入和样本会话不进入正式工程。真实Webhook、认领、受控查看及密钥流程必须使用相应接口和认证。正式登录凭证不放浏览器本地存储；请求入口不得自动重放危险写操作。

## cece 提供什么，AI 怎样接入

1. cece指明要改的页面，提供设计或说明需要保留的操作与可检查结果。
2. AI按[项目后台UI Skill](../.agents/skills/bumbum-admin-ui/SKILL.md)与现行规范清点入口和同类调用点，说明复用模式及拟改字段、步骤和容器；已批准范围内连续实现，主要入口或信息层级变化按AGENTS对齐。
3. Figma或附件内容按需提取，保留真实接口、登录、防冒用、加载/空态/失败/处理中及未知结果恢复；需改变业务规则时先同步相应定义。
4. 按1920×1080同尺寸对照同类界面，再核对较小桌面窗口、焦点、键盘、表单离开、返回及失败恢复。使用模拟数据时明确标注，截图避开秘密、完整号码及认领码。
5. 按影响范围进行类型、构建、业务及实际浏览器检查，分别说明源码核对、入口实测、完整流程和视觉覆盖；cece确认外观与交互。独立React19组件冒烟不作为例行检查，确需执行时仍按AGENTS取得对应批准。

## 文档怎样保持简洁

产品与字段只在对应现行规范维护，接口在API_CONTRACT，执行边界在AGENTS。本文件不再维护另一套状态、规则或版本表。启动、构建及浏览器回归命令集中在[本地运行](LOCAL_DEVELOPMENT.md)，操作从[手册入口](OP_GUIDE.md)选择，CI配置存在不代表该轮Checks已经通过。

用户H5独立构建，采用自然页面滚动，不继承后台布局限制。账户、碰卡及认领留在用户流程，共用层只提取确有两个调用方的展示；图片、品牌及自动查询按现行产品规范和锁定依赖维护，不因后台换组件引入新运行服务。持续查看与账户登录的权限各自核对；本机、浏览器、真实短信、实卡及公网验收分别取证。
