# BUMBUM NFC 数字项目

为服装、饰品等实体物品嵌入 NFC 芯片，让用户用手机碰一下，就能验证芯片读数、查看物品资料，并逐步体验数字收藏。

**产品愿景：** [让每一件实体产品，都有机会成为一件可以持续体验、长期收藏、可信流转的数字藏品。](PRODUCT.md)

[项目能力总览](PRD.md#0-项目能力总览)汇总用户端、运营后台、部署和探索能力，并标明生产与测试状态。

维护人cece是产品经理，尚无代码基础，但理解和学习能力没有问题，能学习技术原理、审查逻辑、操作命令行并完成构建验证。**项目文件以 cece 能读懂、判断、操作为标准：先讲目的、步骤和结果；必要术语用大白话解释。**具体要求见 [文件可读性原则](AGENTS.md#7-文件可读性以-cece-能理解为标准)。

## 现在做到哪一步

- **基础管理已验收并合入main：** 管理员登录、本机运行、芯片登记、物品建档、服装资料维护与桌面后台可用，操作见[管理端手册](docs/ADMIN_DESKTOP.md)。
- **芯片接入与服装触碰闭环已验收并合入main：** 首次绑定、密钥及配置核验、动态验证、有效触碰统计和手机资料持续查看已有交付；[登记与实卡的验收边界](docs/product/chip-lifecycle.md)、[手机体验规则](docs/product/fashion-touch.md)分别查阅。
- **杭州正式入口基础接管已验收：** 香港ECS已释放，生产与测试隔离；[当前发布记录](docs/HANGZHOU_DEPLOYMENT.md#当前发布记录)及[接管历史与运维验证边界](docs/HANGZHOU_DEPLOYMENT.md#62-杭州基础接管完成范围与后续运维验证)单独记录，合入main不代表服务器已更新。
- **第一阶段处于试用准备：** 杭州 test 已完成实卡认领、Windows Hello 登录和用户动态等验收；后台装配、权益/转售、手机预览及普通芯片停用恢复收到“基本都验收通过了”的总体反馈，不等同全部细项逐项通过。可用范围见[项目能力总览](PRD.md#0-项目能力总览)，后续安排见 [TODO](TODO.md)。
- **项目结构与维护整改已审核通过：** 后端职责、前端类型与组件、结构检查及 cece/AI 阅读入口已梳理，相关自动检查和隔离回归通过；[原实施方案](docs/archive/project-maintenance-2026-11-17.md)已归档。本次不部署，生产与 test 仍以[当前发布记录](docs/HANGZHOU_DEPLOYMENT.md#当前发布记录)为准。

当前任务、分支和待反馈只看[TODO](TODO.md)；验收日期、提交和历史证据查[CHANGELOG](CHANGELOG.md)；逐接口实现范围集中在[接口实现概览](API_CONTRACT.md#04-当前能做到哪一步)。

产品入口按用途分开。业务规则和改动方案从 [PRD 导航](PRD.md) 查阅，长期方向见 [PRODUCT](PRODUCT.md)，历史提案和复盘集中在 [历史归档](docs/archive/README.md)。

<a name="先启动这一小步"></a>

## 从哪里开始

先看[TODO的当前安排](TODO.md#当前安排)，再按对应任务进入产品规范、提案或探索说明；具体任务、状态和下一步只在TODO维护。本地运行、管理员登录及芯片登记步骤仍从[操作手册入口](docs/OP_GUIDE.md)查阅，用于启动或回归，不默认作为当前待验收任务。已有配置、账号和数据继续使用。

<a name="cece-怎么读这些文件"></a>

## cece 与 AI 怎么读这些文件

- **cece 日常阅读：**先看[TODO](TODO.md#当前安排)了解当前任务，从[产品导航](PRD.md)进入本次相关规则或提案；需要操作、验收时，从[操作手册入口](docs/OP_GUIDE.md)选择对应手册。了解协作方式可读[cece速览](AGENTS.md#cece速览)。
- **AI 执行阅读：**先读适用的[完整协作规范](AGENTS.md)，核对TODO及实际文件，再按任务读取对应产品、技术、接口定义与精确附录；实现和验证位置从[代码地图](#代码和配置在哪里)定位。

cece 学习或审查技术时，可按需阅读[运行说明](TECH_SPEC.md)、[接口说明](API_CONTRACT.md)及[技术附录](docs/IMPLEMENTATION_DETAILS.md)。AI执行时必须完整读取本次相关的精确规则，不能只凭摘要实现；双方使用同一份规范。

让AI开始工作时，直接说明本次目标、允许修改的范围和可检查的结果。需要执行命令时，说明必须包含执行位置、预期结果和失败后的处理方法。

## 选用的工具和业务分工

| 部分 | 使用什么 | 负责什么 |
|---|---|---|
| 用户页、管理页 | React + TypeScript；用户端Vite、管理端Umi Max/Ant Design Pro | 浏览器中看到和操作的页面 |
| 后端 | Python 3 + Flask | 接收页面请求，检查身份，处理业务 |
| 数据库 | MySQL 8.0 | 保存芯片、物品、用户和操作记录 |
| 正式运行 | Gunicorn + Nginx | 分别运行后端、接收网站访问并转交请求 |
| 云服务 | 阿里云 ECS、RDS | 分别提供运行程序的服务器、托管数据库 |

一个仓库；每个环境各有一个后端和业务库，生产与测试可共用RDS实例，但不共用业务库和应用身份。共同功能放在 `core/`；服装 `fashion` 和饰品 `jewelry` 的业务分开组织，避免同一功能写两遍。

分别提供桌面管理端与用户手机端两个网页应用（SPA，主要由浏览器切换页面）。`nfc.bumbum.cc` 给用户，`admin.bumbum.cc` 给管理员，`bumbum.cc` 品牌页可选。目标芯片为 NXP NTAG424 DNA，当前单卡配置、实卡核验及适用范围见[真实卡手册](docs/NFC_CARD_VERIFICATION.md)。

已有资源记录：杭州ECS（已核对Ubuntu 26.04.1、2核、约1.7GiB内存）、同VPC杭州RDS、已完成ICP备案的bumbum.cc，以及iPhone、Windows 11和MacBook Air 2024。香港ECS已由cece释放，仅保留历史验收证据，不再作为运行或恢复依赖。手机/App版本与实卡证据见[技术附录第14.1节](docs/IMPLEMENTATION_DETAILS.md#141-已有证据与复用来源)，杭州生产/测试入口及隔离规则见[杭州手册](docs/HANGZHOU_DEPLOYMENT.md)，不沿用旧香港地址或把旧实卡验收当作新环境验收。当前不增加微服务、Redis、消息队列等额外运行服务，避免维护负担；改变部署方式前须说明理由并获cece确认。

## 每个文件管什么

| 文件 | 什么时候看 | 注意什么 |
|---|---|---|
| [PRODUCT.md](PRODUCT.md) | 理解 BUMBUM 的长期愿景、统一数字藏品体系与跨业务线原则 | 长期方向不代表功能已实现或当前迭代承诺 |
| [PRD.md](PRD.md) | 查看项目能力总览，再按问题进入现行模块、共用规则和改动提案 | 详细规范在 `docs/product/`，提案在 `docs/proposals/` |
| [手串 NFC 数字价值探索](docs/BRACELET_NFC_EXPLORATION.md) | 核对手串价值问题、候选体验及验证边界 | 探索范围，待选出具体产品方案 |
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

先按业务定位入口和验证，再阅读对应规范。路由负责请求与事务协调，共同业务不反向依赖页面或管理路由。

| 业务模块 | 实现位置 | 规则与验证入口 |
|---|---|---|
| 应用与数据库 | [app.py](app.py)、[core/db.py](core/db.py)、[结构检查](core/schema_checks.py) | [技术规范](TECH_SPEC.md)、[数据库检查](tests/test_database.py)、[迁移结构检查](tests/test_migration_readiness.py) |
| 管理登录与审计 | [admin_auth](core/admin_auth.py)、[admin_passkeys](core/admin_passkeys.py)、[catalog/audit](core/catalog/audit.py) | [登录手册](docs/ADMIN_LOGIN.md)、[认证安全回归](tests/test_auth_security.py) |
| 芯片登记、绑定与密钥 | [登记](core/chip_registry.py)、[扫码回调](core/scan_webhook.py)、[绑定](core/chip_binding.py)、[密钥](core/chip_keys.py) | [芯片规范](docs/product/chip-lifecycle.md)、[绑定回归](tests/test_chip_binding.py)、[密码学向量](tests/test_sdm_crypto.py) |
| 数字物品与订单 | [管理路由](core/admin_catalog.py)、[物品办理](core/catalog/inventory.py)、[订单履约](core/catalog/orders.py)、[读查询](core/catalog/queries.py) | [数字物品规范](docs/product/digital-catalog.md)、[订单回归](tests/test_sales_orders.py)、[后台回归](tests/test_admin_catalog.py) |
| 用户碰卡、认领与持有 | [触碰入口](core/tap_grants.py)、[验签事务](core/tap_verification.py)、[账户认领](core/public_account.py)、[持有体验](core/holder_lifecycle.py) | [用户H5规范](docs/product/user-h5.md)、[认领回归](tests/test_h5_claim.py)、[挂失找回回归](tests/test_holder_lifecycle.py) |
| 图片与验收批次 | [共用图片](core/catalog/media.py)、[离线备份](core/media_backup.py)、[批次](core/test_batches.py) | [媒体恢复回归](tests/test_media_backup.py)、[验收批次回归](tests/test_acceptance_data.py) |
| 管理端页面 | [路由](frontend/admin/config/routes.ts)、[页面](frontend/admin/src/pages/)、[共用组件](frontend/admin/src/components/)、[接口类型](frontend/admin/src/types/catalog.ts)、[请求hooks](frontend/admin/src/hooks/) | [后台设计规范](docs/ADMIN_UI_GUIDELINES.md)、[桌面验收](docs/ADMIN_DESKTOP.md)、[浏览器回归](tests/test_admin_review_browser.py) |
| 用户手机页 | [用户工程](frontend/user/src/)、[共用展示](frontend/shared/itemPresentation.ts) | [H5验收](docs/DIGITAL_ITEM_ASSEMBLY_H5_ACCEPTANCE.md)、[手机浏览器回归](tests/test_mobile_browser.py) |
| 数据结构与升级 | [空库schema](db/schema.sql)、[历史迁移](db/migrations/)、[本地升级工具](scripts/migrate_local.py) | [本地运行说明](docs/LOCAL_DEVELOPMENT.md)；已有库先核对缺失迁移，不能重建 |
| 部署与历史基准 | [杭州工具](scripts/hangzhou.py)、[共享部署模板](deploy/cloud_test/)、[冻结原型](prototypes/admin-make/README.md) | [当前发布记录](docs/HANGZHOU_DEPLOYMENT.md#当前发布记录)；原型只作既有回归基准 |

默认 `rg` 检索遵循 [.ignore](.ignore)，跳过生成HTML及历史证据；需要追溯时显式指定历史目录检索，例如 `rg --no-ignore '关键词' docs/archive/`。这只减少检索噪声，不删除文件，不影响构建和测试。根目录 `compose.yaml` 只启动本机独立测试数据库；日常命令统一从[操作手册](docs/OP_GUIDE.md)进入。

Python 依赖集中在 [`requirements/`](requirements/)。`base.in` 定义后端共用的直接依赖。安装时按用途选用 [`dev.txt`](requirements/dev.txt)、[`browser.txt`](requirements/browser.txt) 或 [`deploy.txt`](requirements/deploy.txt)，分别对应本地开发、浏览器回归和 Docker 部署。启用杭州 test 短信的镜像额外安装 [`hangzhou-test-sms.txt`](requirements/hangzhou-test-sms.txt)。更新直接依赖后，重新生成对应的固定版本清单。

前端依赖与固定版本分别维护在 `package.json` 和 `package-lock.json`。

`.env.example` 是配置模板，准备脚本生成本机 `.env` 并保留已有文件。`VITE_` 配置会进入网页，只能放公开信息；接口地址拼接规则见 [接口说明](API_CONTRACT.md#01-地址和字段)。云开发环境与生产 ECS/RDS 分开，本轮没有连接生产数据库。

## 后续开发顺序

基础服装触碰查看闭环稳定并完成小范围试用必需准备后，以普通手串探索 NFC 触碰后的数字体验或权益：用户究竟获得什么，才能增加实体产品的拥有、佩戴或保留价值。原“一碰一签”祈愿方案已废弃，复盘与探索边界见[探索说明](docs/BRACELET_NFC_EXPLORATION.md)；祈愿、小世界、收藏和成长均非已确认的新方案。长期跨品类愿景见[PRODUCT](PRODUCT.md)，当前任务及排期见[TODO](TODO.md)。独立商业机会保留在[既有计划](docs/WUTAI_WEDDING_PILOT_PLAN.md)，其具体数字需求另行讨论，不作为普通手串体验的设计前提。
