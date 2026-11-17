---
doc_type: archive
status: archived
date: 2026-11-17
reason: 旧Vite及React Router后台接入约束迁入历史，当前后台已采用Umi
superseded_by: ../FRONTEND_COLLABORATION.md
---

> 以下保留技术附录原第10节原文，描述原Vite/React Router管理端的迁移背景，不代表当前目录或构建方式。原交付证据仍按CHANGELOG日期查阅。

## 10. 桌面管理端接入

本节保留原Vite/React Router管理端的迁移历史与交互保护依据，不是当前目录结构；正式管理端现采用Umi Max，组件与构建入口见FRONTEND_COLLABORATION及后台工程迁移说明。

管理端保留React、TypeScript、Vite和npm，锁定依赖以package.json/lock为准。共享入口使用antd 6原生React 19支持，ConfigProvider/App统一中文和主题；AdminLayout采用Layout/Menu及React Router的数据路由，LoginPanel仍持有会话。工作台保留原统计聚合及SVG图表，RuntimeChecks复用health/ready；不将连接检查视为业务或部署验收。

ChipPanel使用官方Table与Form查询、Descriptions详情及Form批次编辑；详情/编辑共用业务字段定义，CreateChip使用Modal/Form登记并继续。已提交查询及页码在URL，安全返回位置与滚动在站内路由state；未提交草稿、密钥及凭证不进入URL或浏览器持久存储。表单只在URL条件变化时初始化，不能用外部同步覆盖未提交输入；分页回调读取最新URL而非旧渲染闭包，以免快速翻页丢失刚提交条件；查询用Form.getFieldsValue(true)保留未挂载的高级字段，日期框回车不触发整张表单提交；列表、详情与关联通过真实ID/API读取。ItemPanel以Table/Form承接URL条件，CreateItem以Modal/Form连续创建并定位确切ID，ItemDetailPage与itemFields共用详情/编辑字段；ItemImages负责受控Upload适配，不维护第二套表单/文件列表。新普通保存一次PATCH，只提交变化的款式和profile，无变化不发写请求；只读尺码与饰品资料不写回。

NavigationGuard结合useBlocker及beforeunload保护普通编辑；保存后继续/放弃继续/取消分别处理，提交中拒绝离开；绑定/密钥保留专用确认及未知结果核对。记录切换重置表单，卸载/新请求后旧响应不可回填；401隐藏全部管理资料，CSRF更新不自动重放写请求。采用官方布局的页面滚动、侧栏及弹窗滚动，不依赖旧body禁止滚动规则；旧物品编辑器、Radix控件及无引用依赖已移除，管理端使用官方reset；工作台筛选、卡片和明细采用同一Ant Design组件体系；SVG图表保留局部样式，本次Make展示组合通过make.css及Tailwind编译，避免覆盖官方控件行为。人工步骤见[桌面管理端](../ADMIN_DESKTOP.md)、[物品手册](../ITEM_DRAFTS.md)及[芯片手册](../CHIP_REGISTRATION.md)。代码回退到本步之前的已提交版本并按对应锁文件安装，不能撤销已保存批次/关联或代替数据库恢复。
