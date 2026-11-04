# BUMBUM NFC 数字项目

为服装、饰品等实体物品嵌入 NFC 芯片，让用户用手机碰一下，就能查看资料、验证真伪，并逐步体验数字收藏。

**产品愿景：** [让每一件实体产品，都有机会成为一件可以持续体验、长期收藏、可信流转的数字藏品。](PRODUCT.md)

维护人cece是产品经理，尚无代码基础，但理解和学习能力没有问题，能学习技术原理、审查逻辑、操作命令行并完成构建验证。**项目文件以 cece 能读懂、判断、操作为标准：先讲目的、步骤和结果；必要术语用大白话解释。**具体要求见 [文件可读性原则](AGENTS.md#7-文件可读性以-cece-能理解为标准)。

## 现在做到哪一步

- **基础管理已验收并合入main：** 管理员登录、本机运行、芯片登记、物品建档、服装资料维护与桌面后台可用，操作见[管理端手册](docs/ADMIN_DESKTOP.md)。
- **芯片接入与服装触碰闭环已验收并合入main：** 首次绑定、密钥及配置核验、动态验证、有效触碰统计和手机资料持续查看已有交付；[登记与实卡的验收边界](docs/product/chip-lifecycle.md)、[手机体验规则](docs/product/fashion-touch.md)分别查阅。
- **杭州正式入口基础接管已验收：** 香港ECS已释放，生产与测试隔离；[最后已知部署版本及运维验证边界](docs/HANGZHOU_DEPLOYMENT.md#62-杭州基础接管完成范围与后续运维验证)单独记录，合入main不代表服务器已更新。
- **第一阶段尚未整体完成：** 短信认领、试用准备及扩展实卡验证等仍有待办；后台改版在任务分支等待人工验收，手串数字体验处于探索阶段，范围见[产品导航](PRD.md)，进度见TODO。

当前任务、分支和待反馈只看[TODO](TODO.md)；验收日期、提交和历史证据查[CHANGELOG](CHANGELOG.md)；逐接口实现范围集中在[接口实现概览](API_CONTRACT.md#04-当前能做到哪一步)。

产品入口已按“共用规则→现行模块→独立提案→历史归档”整理，先读[PRD导航](PRD.md)。后台统一改版、生产验证清理、专用纠错与挂失换新分别审核，已确认的组件复用原则见[A提案](docs/proposals/admin-management-update.md#31-官方复用定制与迁移约定已确认)。整理文档不代表新增能力已实现、验收或部署。

<a name="先启动这一小步"></a>

## 从哪里开始

先看[TODO的当前安排](TODO.md#当前安排)，再按对应任务进入产品规范、提案或探索说明；具体任务、状态和下一步只在TODO维护。本地运行、管理员登录及芯片登记步骤仍从[操作手册入口](docs/OP_GUIDE.md)查阅，用于启动或回归，不默认作为当前待验收任务。已有配置、账号和数据继续使用。

## cece 怎么读这些文件

1. 判断“要做什么、怎样才算做完”：从[产品导航](PRD.md)进入对应模块；新改动看独立提案。
2. 理解“碰一下后发生什么、怎样防伪和登录”：读 [运行说明](TECH_SPEC.md)。
3. 核对“页面要提交什么、会收到什么”：读 [接口说明](API_CONTRACT.md)。
4. 让AI开始工作：直接说明本次任务、允许修改的范围和可检查的结果。你可先读[协作速览](AGENTS.md#cece速览)；AI必须读取适用的[完整规范](AGENTS.md)，再按任务查定义文件和操作手册。

cece 可以先读正文判断流程，按需查技术附录；AI 写代码时必须读对应的精确规则。需要执行命令时，说明必须包含执行位置、预期结果和失败后的处理方法。

## 选用的工具和业务分工

| 部分 | 使用什么 | 负责什么 |
|---|---|---|
| 用户页、管理页 | React + Vite + TypeScript | 浏览器中看到和操作的页面 |
| 后端 | Python 3 + Flask | 接收页面请求，检查身份，处理业务 |
| 数据库 | MySQL 8.0 | 保存芯片、物品、用户和操作记录 |
| 正式运行 | Gunicorn + Nginx | 分别运行后端、接收网站访问并转交请求 |
| 云服务 | 阿里云 ECS、RDS | 分别提供运行程序的服务器、托管数据库 |

一个仓库；每个环境各有一个后端和业务库，生产与测试可共用RDS实例，但不共用业务库和应用身份。共同功能放在 `core/`；服装 `fashion` 和饰品 `jewelry` 的业务分开组织，避免同一功能写两遍。

分别提供桌面管理端与用户手机端两个网页应用（SPA，主要由浏览器切换页面）；用户端本期只开放触碰验证及服装资料查看，香港历史服装样品验收已通过，当前正式入口由杭州接管；生产库不导入旧样品，新增业务与实卡验收另行执行。`nfc.bumbum.cc`给用户，`admin.bumbum.cc`给管理员，`bumbum.cc`品牌页可选。目标芯片为NXP NTAG424 DNA；NFC.cool的当前单卡配置及核验方式见[真实卡手册](docs/NFC_CARD_VERIFICATION.md)，不承诺其他版本或批量流程已通过。

已有资源记录：杭州ECS（已核对Ubuntu 26.04.1、2核、约1.7GiB内存）、同VPC杭州RDS、已完成ICP备案的bumbum.cc，以及iPhone、Windows 11和MacBook Air 2024。香港ECS已由cece释放，仅保留历史验收证据，不再作为运行或恢复依赖。手机/App版本与实卡证据见[技术附录第14.1节](docs/IMPLEMENTATION_DETAILS.md#141-已有证据与复用来源)，杭州生产/测试入口及隔离规则见[杭州手册](docs/HANGZHOU_DEPLOYMENT.md)，不沿用旧香港地址或把旧实卡验收当作新环境验收。当前不增加微服务、Redis、消息队列等额外运行服务，避免维护负担；改变部署方式前须说明理由并获cece确认。

## 每个文件管什么

| 文件 | 什么时候看 | 注意什么 |
|---|---|---|
| [PRODUCT.md](PRODUCT.md) | 理解 BUMBUM 的长期愿景、统一数字藏品体系与跨业务线原则 | 长期方向不代表功能已实现或当前迭代承诺 |
| [PRD.md](PRD.md) | 按问题进入现行模块、共用规则、后续范围与改动提案 | 详细规范在docs/product/，提案在docs/proposals/；不定义数据库字段或算法 |
| [手串 NFC 数字价值探索](docs/BRACELET_NFC_EXPLORATION.md) | 两版复盘、候选价值与探索边界 | 不是新 PRD；[旧祈愿 PRD](docs/NFC_PRAYER_H5_PRD.md)已废弃，仅供追溯 |
| [TECH_SPEC.md](TECH_SPEC.md) | 理解运行、绑定、密钥、登录和部署流程 | 精确计算和长配置见附录 |
| [技术附录](docs/IMPLEMENTATION_DETAILS.md) | AI 写代码时查固定参数、保存规则和部署示例 | 是技术规范的一部分，不能省略 |
| [API_CONTRACT.md](API_CONTRACT.md) | 核对页面提交内容、后台返回结果、权限和失败原因 | 接口定义不等于接口已经可用 |
| [db/schema.sql](db/schema.sql) | 第一次给空数据库建表；注释说明各表用途 | 不用于已有数据库升级或重复执行 |
| [CHANGELOG.md](CHANGELOG.md) | 查重要改动、原因和历史决策 | 被替代的旧方案不能覆盖当前规则 |
| [AGENTS.md](AGENTS.md) | 让 AI 按统一流程读取、修改和交付 | 详细技术参数在对应技术文件中维护 |
| [.env.example](.env.example) | 查看程序需要哪些配置及各自用途 | 不填写真实密码、密钥或凭证 |
| [.gitignore](.gitignore) | 查看哪些本地文件不应上传到 Git | 不能清除已经进入提交历史的秘密 |
| [操作手册入口](docs/OP_GUIDE.md) | 查本地运行、管理员登录及各功能验收步骤 | 按主题分文件，先选对分支；不把手册存在当成功能完成 |
| [TODO.md](TODO.md) | 看当前优先级、任务状态和完成条件 | 当前任务的唯一清单；历史结果查CHANGELOG |
| [Figma 协作方式](docs/FRONTEND_COLLABORATION.md) | 后续按设计逐页替换简单页面 | 保留接口和权限检查，不整包覆盖项目 |

如果文件说法冲突，AI 应指出位置、影响和建议，再按已确认的决定同步修正；不能悄悄选一份。协作要求见 [AGENTS.md](AGENTS.md)。

## 代码和配置在哪里

后端入口是app.py；手机登记回调在core/scan_webhook.py，共用登记在core/chip_registry.py，首次绑定在core/chip_binding.py，密钥配置在core/chip_keys.py及sdm_derivation.py，秘密加密在core/secret_storage.py，触碰入口在core/tap_grants.py，验证事务在core/tap_verification.py，共用验签在core/sdm_verification.py，管理统计入口在core/admin_stats.py，快照聚合在core/tap_statistics.py。数据库连接在core/db.py，认证及账号命令在core/admin_auth.py、admin_cli.py，管理接口在core/admin_chips.py、admin_items.py，管理前端在frontend/admin/，手机用户前端在frontend/user/，各自构建并使用独立样式。根目录compose.yaml只启动独立测试数据库；首次空库建表用db/schema.sql，已有库升级另走迁移，不能重建数据库；触碰记录升级见[本地运行第11节](docs/LOCAL_DEVELOPMENT.md#11-已有测试库升级触碰记录及后端验收)，持续查看资格004及用户页预览见[第12节](docs/LOCAL_DEVELOPMENT.md#12-已有测试库升级及手机资料页本机验收)。

云测试部署依赖在requirements-deploy.in/txt，通过容器固定版本，不替换Ubuntu系统Python。Python 的本机直接依赖在 `requirements.in`，完整固定版本在 `requirements.txt`；开发检查对应 `requirements-dev.in` 和 `requirements-dev.txt`。前端依赖与固定版本在 `package.json`、`package-lock.json`。更新依赖时同步对应清单，不手工改锁文件凑版本。

`.env.example` 是配置模板，准备脚本生成本机 `.env` 并保留已有文件。`VITE_` 配置会进入网页，只能放公开信息；接口地址拼接规则见 [接口说明](API_CONTRACT.md#01-地址和字段)。云开发环境与生产 ECS/RDS 分开，本轮没有连接生产数据库。

## 后续开发顺序

基础服装触碰查看闭环稳定并完成小范围试用必需准备后，以普通手串探索 NFC 触碰后的数字体验或权益：用户究竟获得什么，才能增加实体产品的拥有、佩戴或保留价值。原“一碰一签”祈愿方案已废弃，复盘与探索边界见[探索说明](docs/BRACELET_NFC_EXPLORATION.md)；祈愿、小世界、收藏和成长均非已确认的新方案。长期跨品类愿景见[PRODUCT](PRODUCT.md)，当前任务及排期见[TODO](TODO.md)。独立商业机会保留在[既有计划](docs/WUTAI_WEDDING_PILOT_PLAN.md)，其具体数字需求另行讨论，不作为普通手串体验的设计前提。
