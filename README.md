# BUMBUM NFC 数字项目

为服装、饰品等实体物品嵌入 NFC 芯片，让用户用手机碰一下，就能查看资料、验证真伪、绑定所有权，并在后续体验数字互动。

维护人cece是产品经理，尚无代码基础，但理解和学习能力没有问题，能学习技术原理、审查逻辑、操作命令行并完成构建验证。**项目文件以 cece 能读懂、判断、操作为标准：先讲目的、步骤和结果；必要术语用大白话解释。**具体要求见 [文件可读性原则](AGENTS.md#7-文件可读性以-cece-能理解为标准)。

## 现在做到哪一步

- 管理员登录、Windows运行工具、芯片手动/手机登记与首次来源、物品草稿、服装基础资料与启停、桌面管理端已由cece验收并合入main。
- 错误编号与脱敏诊断、可重复的桌面浏览器回归及CI已接入；文档按职责分工维护，操作入口不变。
- 芯片首次绑定、排除已占用候选、密钥生成与受控查看、配置核验已由cece验收并合入main；两枚服装测试卡按十六进制目标密钥配置后核验通过。合并记录及当前任务看TODO和CHANGELOG。
- 手机登记通过的流程是“先批量写固定文本，再批量读卡自动回调”；不代表空白卡、随机UID或正式SUN防伪通过。
- 用户触碰验证后端及工作台全项目有效触碰统计已由cece分别验收并合入main；支持有效读数验证、旧读数拒绝、短时资料凭证及按项目/时间查询统计。手机服装资料页及持续查看已由cece验收并合入main，刷新与自动查询读取最新资料、不重复计数；香港服装样品公网部署及本轮整体验收已通过，包含异常场景、重启保留与独立恢复；短信认领、跨项目实卡等仍待完成，第一阶段未整体完成；密钥轮换和批量生产分别取证。
- 仓库版本与服务器部署分开验收，合入main不代表香港已更新。操作见[桌面管理端](docs/ADMIN_DESKTOP.md)及[云测试手册](docs/CLOUD_TEST_DEPLOYMENT.md)。

当前任务、分支和待反馈只看[TODO](TODO.md)；验收日期、提交和历史证据查[CHANGELOG](CHANGELOG.md)；逐接口实现范围集中在[接口实现概览](API_CONTRACT.md#04-当前能做到哪一步)。

## 先启动这一小步

从 [操作手册入口](docs/OP_GUIDE.md) 按顺序选择“本地运行 → 管理员登录 → 芯片登记验收”。先确认两个运行检查通过，再验收本次功能；手册包含各系统命令和失败排查。已有配置、账号和数据继续使用。

## cece 怎么读这些文件

1. 判断“要做什么、怎样才算做完”：读 [产品需求](PRD.md)。
2. 理解“碰一下后发生什么、怎样防伪和登录”：读 [运行说明](TECH_SPEC.md)。
3. 核对“页面要提交什么、会收到什么”：读 [接口说明](API_CONTRACT.md)。
4. 让 AI 开始工作：直接说明本次任务、允许修改的范围和可检查的结果，让 AI 先读 [协作规范](AGENTS.md)，再按任务查对应定义文件和操作手册。

cece 可以先读正文判断流程，按需查技术附录；AI 写代码时必须读对应的精确规则。需要执行命令时，说明必须包含执行位置、预期结果和失败后的处理方法。

## 选用的工具和业务分工

| 部分 | 使用什么 | 负责什么 |
|---|---|---|
| 用户页、管理页 | React + Vite + TypeScript | 浏览器中看到和操作的页面 |
| 后端 | Python 3 + Flask | 接收页面请求，检查身份，处理业务 |
| 数据库 | MySQL 8.0 | 保存芯片、物品、用户和操作记录 |
| 正式运行 | Gunicorn + Nginx | 分别运行后端、接收网站访问并转交请求 |
| 云服务 | 阿里云 ECS、RDS | 分别提供运行程序的服务器、托管数据库 |

一个仓库、一个后端、一个数据库。共同功能放在 `core/`；服装 `fashion` 和饰品 `jewelry` 的业务分开组织，避免同一功能写两遍。

分别提供桌面管理端与用户手机端两个网页应用（SPA，主要由浏览器切换页面）；用户端本期只开放触碰验证及服装资料查看，香港测试站点已公开并通过本轮服装样品验收；其他环境发布另行授权执行。`nfc.bumbum.cc`给用户，`admin.bumbum.cc`给管理员，`bumbum.cc`品牌页可选。目标芯片为NXP NTAG424 DNA；NFC.cool的当前单卡配置及核验方式见[真实卡手册](docs/NFC_CARD_VERIFICATION.md)，不承诺其他版本或批量流程已通过。

已有资源记录：杭州ECS（系统、配置及连接待核验）及香港ECS（cece确认Ubuntu 22.04、2核4GiB）、RDS、已完成ICP备案的bumbum.cc、iPhone、Windows 11和MacBook Air 2024；手机/App本轮版本证据集中在[技术附录第14.1节](docs/IMPLEMENTATION_DETAILS.md#141-已有证据与复用来源)，不沿用早期设备猜测。扫描测试建议使用香港ECS和test.bumbum.cc，域名及HTTPS入口已由cece配置，手机批量扫描已验收；细节见技术说明第2.5节。当前不增加微服务、Redis、消息队列等额外运行服务，避免维护负担。改变所用工具和部署方式前，须说明理由并获cece确认。

## 每个文件管什么

| 文件 | 什么时候看 | 注意什么 |
|---|---|---|
| [PRD.md](PRD.md) | 判断产品规则、阶段范围和完成标准 | 不定义数据库字段或加密算法 |
| [TECH_SPEC.md](TECH_SPEC.md) | 理解运行、绑定、密钥、登录和部署流程 | 精确计算和长配置见附录 |
| [技术附录](docs/IMPLEMENTATION_DETAILS.md) | AI 写代码时查固定参数、保存规则和部署示例 | 是技术规范的一部分，不能省略 |
| [API_CONTRACT.md](API_CONTRACT.md) | 核对页面提交内容、后台返回结果、权限和失败原因 | 接口定义不等于接口已经可用 |
| [db/schema.sql](db/schema.sql) | 第一次给空数据库建表；注释说明各表用途 | 不用于已有数据库升级或重复执行 |
| [CHANGELOG.md](CHANGELOG.md) | 查重要改动、原因和历史决策 | 被替代的旧方案不能覆盖当前规则 |
| [AGENTS.md](AGENTS.md) | 让 AI 按统一流程读取、修改和交付 | 详细技术参数在对应技术文件中维护 |
| [.env.example](.env.example) | 查看程序需要哪些配置及各自用途 | 不填写真实密码、密钥或凭证 |
| [.gitignore](.gitignore) | 查看哪些本地文件不应上传到 Git | 不能清除已经进入提交历史的秘密 |
| [操作手册入口](docs/OP_GUIDE.md) | 查本地运行、管理员登录及各功能验收步骤 | 按主题分文件，先选对分支；不把手册存在当成功能完成 |
| [TODO.md](TODO.md) | 看当前优先级、任务状态和完成条件 | 芯片手动登记已完成，扫描回调已验收，下一步见待办清单 |
| [Figma 协作方式](docs/FRONTEND_COLLABORATION.md) | 后续按设计逐页替换简单页面 | 保留接口和权限检查，不整包覆盖项目 |

如果文件说法冲突，AI 应指出位置、影响和建议，再按已确认的决定同步修正；不能悄悄选一份。协作要求见 [AGENTS.md](AGENTS.md)。

## 代码和配置在哪里

后端入口是app.py；手机登记回调在core/scan_webhook.py，共用登记在core/chip_registry.py，首次绑定在core/chip_binding.py，密钥配置在core/chip_keys.py及sdm_derivation.py，秘密加密在core/secret_storage.py，触碰入口在core/tap_grants.py，验证事务在core/tap_verification.py，共用验签在core/sdm_verification.py，管理统计入口在core/admin_stats.py，快照聚合在core/tap_statistics.py。数据库连接在core/db.py，认证及账号命令在core/admin_auth.py、admin_cli.py，管理接口在core/admin_chips.py、admin_items.py，管理前端在frontend/admin/，手机用户前端在frontend/user/，各自构建并使用独立样式。根目录compose.yaml只启动独立测试数据库；首次空库建表用db/schema.sql，已有库升级另走迁移，不能重建数据库；触碰记录升级见[本地运行第11节](docs/LOCAL_DEVELOPMENT.md#11-已有测试库升级触碰记录及后端验收)，持续查看资格004及用户页预览见[第12节](docs/LOCAL_DEVELOPMENT.md#12-已有测试库升级及手机资料页本机验收)。

云测试部署依赖在requirements-deploy.in/txt，通过容器固定版本，不替换Ubuntu系统Python。Python 的本机直接依赖在 `requirements.in`，完整固定版本在 `requirements.txt`；开发检查对应 `requirements-dev.in` 和 `requirements-dev.txt`。前端依赖与固定版本在 `package.json`、`package-lock.json`。更新依赖时同步对应清单，不手工改锁文件凑版本。

`.env.example` 是配置模板，准备脚本生成本机 `.env` 并保留已有文件。`VITE_` 配置会进入网页，只能放公开信息；接口地址拼接规则见 [接口说明](API_CONTRACT.md#01-地址和字段)。云开发环境与生产 ECS/RDS 分开，本轮没有连接生产数据库。

## 后续开发顺序

产品阶段以[PRD](PRD.md)为准，当前任务和优先级统一看[TODO](TODO.md)。后续任务及优先级只在TODO维护，不在这里再排一套顺序；已完成事项不因重读手册而重复实施。密钥轮换和批量生产仍须满足各自前置条件。
