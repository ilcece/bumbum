# BUMBUM NFC数字项目 — 项目上下文文档

## 0. 一句话定位
为物理世界的实体（服装、饰品等）嵌入一枚NFC芯片，创造有趣的数字互动体验。

## 1. 我是谁
- 我是初创人员，代号cece，需要借助AI工具来完成项目的从0到1。
- 我的背景：产品经理，技术小白，不懂代码，但能看懂逻辑、能操作命令行、能照着AI生成的步骤完成代码构建与项目验证。

## 2. 项目协作与分工
- cece：承担所有项目工作与AI工具协作。所有代码由AI生成，cece负责部署、验收、测试和提出修改需求。
- AI工具：ChatGPT / Codex / Figma Make / DeepSeek / Workbuddy。
- 代码管理工具：GitHub
- 设计软件：Figma
- 我的资源：阿里云 ECS（Ubuntu 26.04）、阿里云 RDS MySQL、域名 `bumbum.cc`（备案中）、iPhone（iOS 14）、台式电脑（Windows 11）、笔记本（MacBook Air 2024）、NFC工具App（NFC.cool）。

## 3. 技术栈（固定，不要随意更换）
- ECS：阿里云 ECS（Ubuntu 26.04）
- 后端：Python 3 + Flask（轻量，AI 生成代码最稳），多项目架构（详见第 10 节）
- 前端：React + Vite + TypeScript（Figma Make 导出），两个 SPA：用户侧、管理端
- 数据库：阿里云 RDS MySQL 8.0
- 代码库：GitHub（private）
- 部署：Gunicorn + Nginx，ECS 上运行
- 可视化：阿里云 DMS
- 芯片：NXP NTAG424 DNA（支持 SDM/SUN 动态加密）
- 写卡：NFC.cool Tools（密钥/SDM 需在 App 内逐枚手动配置，CSV 仅用于批量写链接内容）

技术细节与架构决策见 `TECH_SPEC.md`；接口细节见 `API_CONTRACT.md`；数据库以 `db/schema.sql` 为唯一事实来源。

### 3.1 环境变量清单（值不写入仓库）

**什么是环境变量**：不写死在代码里的配置参数。敏感信息（数据库密码、主密钥）放在服务器上的 `.env` 文件中，代码通过 `os.getenv("变量名")` 读取。`.env` 必须加入 `.gitignore`，永不提交到 GitHub。仓库中只保留 `.env.example`（值留空）作为变量说明书。

**使用方式**：
1. 在项目根目录创建 `.env`，每行一个 `名称=值`。
2. 安装 `python-dotenv`，在 `app.py` / `config.py` 顶部调用 `load_dotenv()`。
3. 代码中用 `os.getenv("DB_PASSWORD")` 读取，不硬编码任何密码。

**变量清单**：
- `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`
- `MASTER_KEY_FASHION` / `MASTER_KEY_JEWELRY`（16 字节十六进制）
- `STORAGE_ENCRYPTION_KEY`（用于信封加密 `chip_key` 落库）
- `WEBHOOK_SHARED_SECRET`（Webhook 鉴权）
- `ADMIN_TOTP_ISSUER`（管理端 TOTP 发行方名称）
- `CORS_ORIGINS`（开发环境 `http://localhost:5173,http://localhost:5174`；生产环境同域，不需要）
- `VITE_API_BASE_URL`（前端构建时使用；生产环境用相对路径 `/api`）

完整示例见 `TECH_SPEC.md` 第 9 节。

### 3.2 命名规范
- `project.code`：固定为 `fashion` / `jewelry`。
- `item_uid`：`FASH-2026-000001` / `JEW-2026-000001`，全局唯一，用于管理端与数据库内部标识；**不出现在 NFC 触碰 URL 中**。
- `chip_uid`：NTAG424 DNA 的 7 字节**静态**硬件 UID，冒号分隔大写十六进制，如 `04:A2:7F:1B:5E:80:00`。
- API 返回统一结构：成功 `{"status":"ok","data":{...}}`；失败 `{"status":"error","code":"...","message":"..."}`。

## 4. 项目简介
- 共两个项目，一个是数字服装，另一个是数字文创饰品，利用加密芯片实现一物一码。
- 数字服装：核心是数字收藏体验，数字权益（可兑新，可流转，可溯源）。
- 数字文创饰品：核心是数字养成与收藏，提供一套有趣的祈福系统。

### 4.1 当前阶段
- 阶段：Phase 1 — 基础闭环验证。
- 目标：跑通“NFC.cool Webhook 芯片入库 → 管理端物品 CRUD → 芯片-物品-所有人绑定，停用启用 → 查看密钥并手动逐一写入芯片”的完整链路。
- 已知限制：NFC.cool 的 CSV 批量写入**不支持**批量配置 NTAG424 DNA 的密钥和 SDM；密钥/SDM 需在 App 内逐枚手动配置。
- 尚未开始：用户侧 SDM 验证页、饰品养成机制、批量写卡密钥/SDM 能力实测。
- 验收标准：管理员扫描一枚芯片，数据进入 `chip` 表；管理端能看到该芯片、绑定物品、启用停用；管理员能在页面上查看该芯片的 5 个派生密钥（二次确认 + 审计），用于后续手动写卡。

## 5. 核心业务简介
### 管理员侧
主要是后台数据管理，包括芯片数据、实体物品（服装、手串、佛牌）等数据的维护，停用启用，绑定修改物品所有人等。

1. 芯片 UID 录入系统。管理员使用手机的 NFC.cool 应用，扫描芯片，通过应用自带的 Webhook 能力，将芯片 UID 发送到服务器。
2. 数据管理后台。管理员登录管理后台（`admin.bumbum.cc`），管理芯片、实体物品、维护绑定关系、停用启用等。
3. 管理员将系统生成的密钥写入芯片。通过 NFC.cool Tools 逐枚配置芯片的密钥、SUN 链接模板、SUN 开关。
   - 注意：CSV 批量写入仅用于批量写链接内容，**不支持**批量写入每枚芯片的不同密钥和 SDM 配置；密钥/SDM 需在 App 内逐枚手动处理。
4. 管理端“查看密钥”会临时解密芯片密钥，必须二次确认并写入 `admin_audit`；日常芯片列表不展示密钥明文。

### 用户侧
手机碰一碰 NFC 芯片，跳转 `https://nfc.bumbum.cc/tap?picc_data=...&cmac=...`，由前端 SPA 读取动态参数并调用 `POST /api/tap/verify`；后端解密 `picc_data` 得到 `chip_uid`，关联出对应物品与项目，再返回前端渲染服装信息页或饰品养成页。

## 6. 文件导航

项目根目录下每个文件的用途、读者、更新时机和 AI 是否必读如下。**开新 AI 会话时，优先读标了“AI 必读”的文件；只做某一类任务时，按“主要读者”和“更新时机”判断该看哪些，不必全部喂给 AI。**

```text
bumbum/
├── README.md
├── PRD.md
├── TECH_SPEC.md
├── API_CONTRACT.md
├── CHANGELOG.md
├── db/
│   └── schema.sql
├── .env.example
├── .gitignore
└── .ai/
    └── SESSION_START.md
```

| 文件 | 用途 | 主要读者 | 更新时机 | AI 必读 |
|---|---|---|---|---|
| `README.md` | 项目入口：一句话定位、我是谁、协作分工、技术栈、环境变量、命名规范、项目简介、当前阶段、核心业务、文件导航、NTAG424 与 SDM 要点、避坑清单、安全与权限、前后端分离规则、多项目架构、域名与部署拓扑、数据库设计原则、关键接口、AI 会话启动指令 | cece、所有 AI 工具 | 项目阶段变化、技术栈调整、协作规则变化、新增全局约束时 | 是（每次新会话） |
| `PRD.md` | 产品需求：目标用户与角色、核心业务流程、功能需求清单（按 Phase 拆分）、用户故事与验收标准、页面清单、非功能需求、术语表、Phase 1 范围声明 | cece、负责生成页面的 AI（Figma Make / Codex） | 产品需求变化、新增功能、调整验收标准时 | 做产品功能、页面、业务逻辑时必读 |
| `TECH_SPEC.md` | 技术规格：技术栈锁定、总体架构（共享内核 + 模块化单体）、数据库设计原则、密钥体系（派生 + 信封加密）、NTAG424 DNA 与 SUN 验证、前后端分离协作、管理后台安全基线、域名与部署拓扑、环境变量、安全与权限、已知限制与待验证事项、分阶段实施计划、给 AI 的技术指令、变更记录 | cece、Codex（后端）、Figma Make（前端）、运维相关 AI | 技术决策变化、架构调整、部署方式变化、新增安全要求时 | 做后端、部署、安全、架构相关任务时必读 |
| `API_CONTRACT.md` | 接口契约：通用约定（基础路径、返回结构、认证、tap_token、时间与分页）、Webhook 与用户触碰、管理端认证、管理端芯片、管理端物品、管理端所有权、服装用户侧、饰品用户侧、错误码总表 | Codex（后端）、Figma Make（前端）、联调时的 cece | 新增或修改接口、调整字段名或返回结构时 | 做任何前后端接口相关任务时必读；后端和前端都不得自行偏离 |
| `CHANGELOG.md` | 决策日志：每次重要变更“改了什么 + 为什么改”，包括技术栈、架构、SUN URL、密钥体系、安全基线、tap_token、环境变量、待验证事项等 | cece、所有 AI 工具 | 每次做出重要技术或产品决策后追加一条 | 开新会话或做与历史决策相关的任务时建议读，避免重复已否决方案 |
| `db/schema.sql` | 数据库 DDL，**唯一事实来源**：项目表、用户表、物品身份表、芯片表、芯片密钥表、所有权表、流转历史表、扫描日志表、管理端用户表、审计表、服装业务表、饰品业务表 | Codex（后端）、cece（通过 DMS 执行） | 任何表结构变更时；必须先改本文件，再在 `CHANGELOG.md` 记录原因 | 做任何涉及数据库查询、模型、迁移的任务时必读 |
| `.env.example` | 环境变量清单模板，值留空，作为“需要填哪些变量”的说明书；真实的 `.env` 永不入库 | cece、部署时的 AI | 新增或删除环境变量时 | 部署、配置相关任务时读 |
| `.gitignore` | Git 忽略规则，至少包含 `.env`、`venv/`、`__pycache__/`、`node_modules/`、`dist/` | cece | 新增需要忽略的文件类型时 | 一般不需要 AI 读，但生成代码时不得把敏感文件加入版本控制 |
| `.ai/SESSION_START.md` | AI 会话启动指令：每次开新会话时第一段粘贴给 AI 的内容，包含必读文件列表、固定规则、SUN URL 最终模板、当前任务占位 | cece、所有 AI 工具 | 协作规则变化、SUN URL 模板变化、新增全局约束时 | 是（每次新会话由 cece 粘贴） |

**使用建议**：

- **开新会话**：先粘贴 `.ai/SESSION_START.md`，让 AI 读 `README.md` + `PRD.md` + `TECH_SPEC.md` + `API_CONTRACT.md` + `db/schema.sql`。
- **只改后端某个接口**：读 `TECH_SPEC.md` 相关章节 + `API_CONTRACT.md` 对应接口 + `db/schema.sql` 相关表，不必重读 `PRD.md` 全文。
- **只改前端某个页面**：读 `PRD.md` 对应用户故事 + `API_CONTRACT.md` 对应接口 + `README.md` 第 9 节协作规则，不必读 `db/schema.sql`。
- **改数据库表**：先改 `db/schema.sql`，再在 `CHANGELOG.md` 记一笔，然后同步 `API_CONTRACT.md` 和 `TECH_SPEC.md` 中受影响的字段描述。

## 7. NTAG424 DNA 密钥与 SDM 要点（AI 必须知道）
- NTAG424 DNA 有 **5 个 AES-128 密钥**：`K0` 是 App Master Key，是唯一有权更改其他密钥的密钥；`K1–K4` 是应用密钥。
- **所有密钥从同一个主密钥确定性派生**（per-tag key diversification），而不是给每枚芯片独立随机生成。主密钥按项目隔离（`MASTER_KEY_FASHION` / `MASTER_KEY_JEWELRY`）。
- **SUN URL 的最终模板**（所有芯片共用同一路径）：
  `https://nfc.bumbum.cc/tap?picc_data={picc}&cmac={cmac}`
  - `picc_data`：加密的 PICC 数据，解密后包含芯片 UID 和读取计数器。
  - `cmac`：AES-CMAC 签名，用于后端验证数据完整性。
  - **不包含 `item_uid`**：物品身份完全由 `picc_data` 解密出的 `chip_uid` 反查得到，避免静态明文暴露物品标识。
  - **Phase 1 不启用 `enc`**：未来若启用 SDMENCFileData，再在模板中追加 `&enc={enc}`，并在后端增加对应解密步骤。
  - URL 长度约 140 字符，NTAG424 DNA 的 NDEF 容量约 256 字节，安全。
- **芯片 UID 是静态的**：NTAG424 DNA 的 7 字节硬件 UID 唯一且不变，NFC.cool Webhook 负载中的 `identifier` 就是它。动态变化的是 SUN URL 中的 `picc_data` / `cmac` 参数，每次触碰都不同，但解密后仍能还原出同一个芯片 UID。
- 后端验证逻辑**不要从零手写**。Python 生态已有成熟开源实现：`nfc-developer/sdm-backend`（Flask，直接可跑）和 `pylibsdm`。AI 基于这两个库封装业务路由，而不是让它自己实现 AES-CMAC 细节。
- NFC.cool 的 Webhook 负载中，`identifier` 是标签 UID，`content` 是解码后的 NDEF 负载（即 SUN URL 字符串）。管理员扫描入库时，用 `identifier` 作为芯片 UID。

## 8. 已知约束与避坑清单（AI 生成代码时必须遵守）
- **NFC.cool Webhook 没有重试机制**：服务器返回非 2xx 即视为失败，扫描数据会丢失。管理员扫描入库接口要尽快返回 200，把耗时逻辑放到异步或直接省略。
- **Gunicorn 多进程下不要用内存存状态**：所有待处理/中间状态必须落 MySQL。不要用 Python 全局变量或字典保存“最近一次扫描的 UID”。
- **密钥绝不明文落库**：`chip_key` 中存储的必须是信封加密后的密文。主密钥放在 ECS 环境变量中，按项目隔离；生产前评估阿里云 KMS；绝不放代码仓库。
- **SUN URL 的 `uid` 用 `{picc}` 加密镜像，不要用明文 `{uid}`**：明文 UID 可被任何人读取，`{picc}` 需要密钥才能解密，隐私性更好。
- **阿里云 RDS 默认不开公网**：开发阶段用 DMS 连接，或把 ECS 内网地址加入 RDS 白名单，不要为了图方便把 3306 暴露到 `0.0.0.0/0`。
- **NFC 入口不是后端路由**：`https://nfc.bumbum.cc/tap?picc_data=...&cmac=...` 由 Nginx 返回前端 SPA；前端读取两个 query 参数后调用 `POST /api/tap/verify`。不要生成 `GET /t/<item_uid>` 或任何后端 HTML 路由。
- **`/api/tap/verify` 的请求体只含 `picc_data` 和 `cmac`**：不要在前端传 `item_uid`；物品身份由后端解密 `picc_data` 得到的 `chip_uid` 反查。

### 8.1 安全与权限
- 管理后台 `admin.bumbum.cc` 采用**分层防御**，不能只靠 TOTP：
  1. **网络层**：Nginx 或安全组 IP 白名单，限制可到达登录页的来源（最高优先级）；
  2. **应用层**：密码 + TOTP 第二因素，非标准登录路径，登录速率限制与渐进式锁定，TOTP 重放保护，一次性备份码；
  3. **会话与审计**：Cookie 设 `HttpOnly` / `Secure` / `SameSite=Strict`，短有效期；登录事件日志与陌生 IP 告警；敏感操作写 `admin_audit`。
- NFC.cool Webhook 使用 Basic Auth 或 URL 中的共享 token 鉴权，防止伪造扫描。
- 生产环境全站 HTTPS；RDS 3306 不对公网开放。
- 详细实现见 `TECH_SPEC.md` 第 7 节。

## 9. 前后端分离协作规则（AI 必须遵守）
- **API 契约是唯一事实来源**：`API_CONTRACT.md` 定义了所有接口。后端按它生成路由，前端按它拼装参数。任何一方不得自行变更字段名或结构。
- **后端只输出 JSON**：Flask 路由只返回 `jsonify(...)`，不包含任何 `render_template` 或 HTML 字符串。
- **前端使用环境变量**：Figma Make 导出的 React 项目通过 `VITE_API_BASE_URL` 读取后端基础地址，不得硬编码 IP 或端口；生产环境用相对路径 `/api`。
- **CORS 白名单**：Flask 使用 `flask-cors`，`origins` 明确列出 `http://localhost:5173` 和 `http://localhost:5174`（开发），不使用通配符；生产环境同域，不需要 CORS。
- **联调顺序**：先让 Codex 用 `curl` 测试后端接口可用 → 再让 Figma Make 导出前端代码 → 最后让 Codex 在前端代码中替换 Mock 数据为真实 `fetch` 调用。
- **生产部署**：Nginx 托管两个前端 SPA 的静态文件，并分别将 `/api/` 反向代理到 Flask，前后端同域，消除跨域。

### 9.1 测试与验收
- 每个后端接口先用 `curl` 测试通过，再交给前端联调。
- 每次让 AI 改代码前，先在 GitHub commit 一次，改坏了可回滚。
- 前端联调时用 Chrome DevTools 的 Network 面板确认请求 URL、状态码、返回 JSON。

## 10. 多项目架构约定
- 本系统包含两个业务项目：fashion（数字服装）和 jewelry（文创饰品）。
- `core/` 目录存放跨项目共享的模型与逻辑（chip、chip_key、item、ownership、ownership_history、scan_log、user、SDM验证、密钥派生、信封加密）。任何业务模块不得重复定义这些模型。
- `fashion/` 和 `jewelry/` 只存放各自项目的业务表和业务 API。
- 新增业务表时，必须通过 `item_id` 外键关联共享的 `item` 表，不得新建独立的物品身份表。
- 所有 API 路径以 `/api/` 开头，业务模块的 API 用 `/api/fashion/` 和 `/api/jewelry/` 前缀隔离。
- 主密钥按项目隔离：`MASTER_KEY_FASHION` 和 `MASTER_KEY_JEWELRY` 分别从环境变量读取，派生时按芯片的 `project_id` 选择。
- NFC 统一入口为 `https://nfc.bumbum.cc/tap?picc_data={picc}&cmac={cmac}`，由 Nginx 返回前端 SPA；前端读取 `picc_data` 和 `cmac`，调用 `POST /api/tap/verify`。后端解密 `picc_data` 得到 `chip_uid`，再查 `chip` → `item` → `project`，决定返回服装还是饰品业务数据。后端不直接渲染该路径，也不依赖 URL 中的 `item_uid`。

### 10.1 域名与部署拓扑
- `bumbum.cc`：品牌官网/落地页（可选，Phase 1 可不做）。
- `nfc.bumbum.cc`：用户侧 H5，React SPA；`/api/` 反代到 Flask。
- `admin.bumbum.cc`：管理后台，React SPA；`/api/` 反代到同一 Flask。
- 后端只有一个 Flask 进程（Gunicorn，`127.0.0.1:5000`），两个子域共享。
- SSL：通配符证书 `*.bumbum.cc` 或阿里云免费证书逐个申请。
- DNS：阿里云 DNS 添加 `nfc` 和 `admin` 两条 A 记录，指向 ECS 公网 IP。
- 生产环境同域调用 `/api/`，不需要 CORS；开发环境仅放行 `localhost:5173` / `localhost:5174`。
- Nginx 配置骨架见 `TECH_SPEC.md` 第 8.3 节。

## 11. 数据库设计原则：核心表共享，业务表隔离

### 设计原则：
1. 芯片、密钥、物品身份、所有权、扫描日志、用户这六类数据是跨项目通用的，必须是同一张表，用 `project_id` 字段区分归属。一枚芯片的 UID 在全局唯一，它属于哪个项目由 `project_id` 标记，绝不能在两个库里各存一份。
2. 业务详情（服装的溯源、故事；饰品的养成进度、任务）按项目拆成独立表，通过 `item_id` 关联到共享的 `item` 表。
3. 用户表共享，以手机号为核心。同一个用户可能同时拥有服装和饰品，共享用户表让未来“跨项目权益打通”成为可能。如果两个项目未来是不同合规主体，再加字段隔离即可。

具体 DDL 见项目根目录 `db/schema.sql`。AI 在生成任何查询/模型时，**必须**以 `db/schema.sql` 为唯一事实来源，不要自行臆造字段；如有修改调整必须声明清楚，同步更新 `db/schema.sql` 并在 `CHANGELOG.md` 记录原因。

## 12. 关键接口约定（完整见 API_CONTRACT.md）
| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/webhook/admin/scan` | 接收 NFC.cool 管理员扫描，自动登记芯片 UID |
| POST | `/api/tap/verify` | 用户触碰后，前端提交 `picc_data` 和 `cmac`；后端解密得到 `chip_uid`，验证 SDM，返回对应物品与项目数据 |
| POST | `/api/public/bind` | 用户提交手机号，绑定物品所有者 |
| GET | `/api/admin/chips` | 管理端芯片列表 |
| GET | `/api/admin/items` | 管理端物品列表 |

> 注：`https://nfc.bumbum.cc/tap?picc_data=...&cmac=...` 是前端路由，不是后端 API；它由 Nginx 返回 SPA，再由 SPA 调用 `POST /api/tap/verify`。`POST /api/tap/verify` 的请求体**只含** `picc_data` 和 `cmac`，不含 `item_uid`。

## 13. AI 会话启动指令
你正在协助开发 BUMBUM NFC 数字项目（含数字服装与数字文创饰品）。请先阅读：
- `README.md`（项目定位与全局约束）
- `PRD.md`（产品需求）
- `TECH_SPEC.md`（技术栈和架构约定）
- `API_CONTRACT.md`（接口契约）
- `db/schema.sql`（数据库唯一事实来源）

规则：
1. 不要更换技术栈（Python 3 + Flask + MySQL + React + Vite）。
2. 不要臆造数据库字段，一切以 `db/schema.sql` 为准。
3. 不要自行修改 `API_CONTRACT.md` 中的字段名；如果发现需要改，先告诉我并说明理由。
4. 生成代码时，标注“需要我修改的地方”（如数据库密码、域名、IP 白名单）。
5. 我是产品经理，不懂代码，请用简洁中文解释关键决策，不要贴大段无关的底层实现。
6. NTAG424 DNA 的 SDM 验证，优先用 `nfc-developer/sdm-backend` 或 `pylibsdm`，不要从零实现 AES-CMAC。
7. SUN URL 的最终模板为 `https://nfc.bumbum.cc/tap?picc_data={picc}&cmac={cmac}`；URL 中不包含 `item_uid`，物品身份由后端解密 `picc_data` 得到的 `chip_uid` 反查。NFC 入口由 Nginx 返回前端 SPA，前端调用 `POST /api/tap/verify`，请求体只含 `picc_data` 和 `cmac`；不要生成 `GET /t/<item_uid>` 或任何依赖路径参数的后端路由。

我当前的任务是：<在这里填入这次要做的事>
