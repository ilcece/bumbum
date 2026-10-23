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
- 我的资源：阿里云 ECS（Ubuntu 26.04）、阿里云 RDS MySQL、域名 `bumbum.cc`、iPhone（iOS 14）、台式电脑（Windows 11）、笔记本（MacBook Air 2024）、NFC工具App（NFC.cool）。

## 3. 技术栈（固定，不要随意更换）
- ECS：阿里云 ECS（Ubuntu 26.04）
- 后端：Python 3 + Flask（轻量，AI 生成代码最稳），多项目架构（详见第 10 节）
- 前端：React + Vite + TypeScript（Figma Make 导出）
- 数据库：阿里云 RDS MySQL 8.0
- 代码库：GitHub
- 部署：Gunicorn + Nginx，ECS 上运行
- 可视化：阿里云 DMS
- 芯片：NXP NTAG424 DNA（支持 SDM/SUN 动态加密）
- 写卡：NFC.cool Tools（密钥/SDM 需在 App 内逐枚手动配置，CSV 仅用于批量写链接内容）

### 3.1 环境变量清单（值不写入仓库）

**什么是环境变量**：不写死在代码里的配置参数。敏感信息（密码、密钥）放在服务器上的 `.env` 文件中，代码通过 `os.getenv("变量名")` 读取。`.env` 必须加入 `.gitignore`，永不提交到 GitHub。

**使用方式**：
1. 在项目根目录创建 `.env` 文件，每行一个 `名称=值`。
2. 安装 `python-dotenv`，在 `app.py` 顶部调用 `load_dotenv()`。
3. 代码中用 `os.getenv("DB_PASSWORD")` 读取，不硬编码任何密码。

**变量清单**：
- `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`
- `MASTER_KEY_FASHION` / `MASTER_KEY_JEWELRY`（16 字节十六进制）
- `STORAGE_ENCRYPTION_KEY`（当前阶段用于加密 `chip_key` 落库）
- `WEBHOOK_SHARED_SECRET`（Webhook 鉴权）
- `CORS_ORIGINS`（开发 `http://localhost:5173`，生产 `https://bumbum.cc`）
- `VITE_API_BASE_URL`（前端构建时使用）

### 3.2 命名规范
- `project.code`：固定为 `fashion` / `jewelry`。
- `item_uid`：`FASH-2026-000001` / `JEW-2026-000001`，全局唯一。
- `chip_uid`：NTAG424 DNA 的 7 字节静态硬件 UID，冒号分隔大写十六进制，如 `04:A2:7F:1B:5E:80:00`。
- API 返回统一结构：成功 `{"status":"ok","data":{...}}`；失败 `{"status":"error","code":"...","message":"..."}`。

## 4. 项目简介
- 共两个项目，一个是数字服装，另一个是数字文创饰品，利用加密芯片实现一物一码。
- 数字服装：核心是数字收藏体验，数字权益（可兑新，可流转，可溯源）。
- 数字文创饰品：核心是数字养成与收藏，提供一套有趣的祈福系统。

### 4.1 当前阶段
- 阶段：Phase 1 — 基础闭环验证。
- 目标：跑通“NFC.cool Webhook 芯片入库 → 管理端物品 CRUD → 芯片-物品-所有人绑定，停用启用 → 查看密钥并手动逐一写入芯片”的完整链路。
- 已知限制：NFC.cool 的 CSV 批量写入不支持批量配置 NTAG424 DNA 的密钥和 SDM，密钥/SDM 需在 App 内逐枚手动配置。
- 尚未开始：用户侧 SDM 验证页、饰品养成机制、批量写卡密钥/SDM 能力实测。
- 验收标准：管理员扫描一枚芯片，数据进入 `chip` 表；管理端能看到该芯片、绑定物品、启用停用；管理员能在页面上查看该芯片的 5 个派生密钥，用于后续手动写卡。

## 5. 核心业务简介
### 管理员侧
主要是后台数据管理，包括芯片数据、实体物品（服装、手串、佛牌）等数据的维护，停用启用，绑定修改物品所有人等。

1. 芯片 UID 录入系统。管理员使用手机的 NFC.cool 应用，扫描芯片，通过应用自带的 Webhook 能力，将芯片 UID 发送到服务器。
2. 数据管理后台。管理员登录管理后台，管理芯片、实体物品、维护绑定关系、停用启用等。
3. 管理员将系统生成的密钥写入芯片。通过 NFC.cool Tools 逐枚配置芯片的密钥、SUN 链接模板、SUN 开关。
   - 注意：CSV 批量写入仅用于批量写链接内容，**不支持**批量写入每枚芯片的不同密钥和 SDM 配置；密钥/SDM 需在 App 内逐枚手动处理。
4. 管理端“查看密钥”会临时解密芯片密钥，必须二次确认并写入 `admin_audit`；日常芯片列表不展示密钥明文。

### 用户侧
手机碰一碰 NFC 芯片，跳转对应链接，体验数字服务。

## 6. 文件导航
```text
bumbum/
├── README.md                    ← 项目入口，一句话定位、项目全局约束和简介、文件导航、当前阶段
├── PRD.md                       ← 产品需求：用户故事、功能清单、业务流程
├── TECH_SPEC.md                 ← 技术规格：架构、技术栈、关键决策、避坑清单
├── API_CONTRACT.md              ← 接口契约：每个API的路径、参数、返回结构
├── db/
│   └── schema.sql               ← 数据库DDL，唯一事实来源
├── CHANGELOG.md                 ← 决策日志：每次重要变更记录"为什么"
└── .ai/
    └── SESSION_START.md         ← 每次开AI会话时，粘贴给AI的固定指令
```

## 7. NTAG424 DNA 密钥与 SDM 要点（AI 必须知道）
- NTAG424 DNA 有 **5 个 AES-128 密钥**：`K0` 是 App Master Key，是唯一有权更改其他密钥的密钥；`K1–K4` 是应用密钥。
- **所有密钥从同一个主密钥确定性派生**（per-tag key diversification），而不是给每枚芯片独立随机生成。这样后端按项目保管主密钥。
- **SUN URL 的正确结构**：物品 UID 放在路径中（静态），动态参数由芯片在每次触碰时自动追加。推荐模板：
  `https://bumbum.cc/t/FASH-2026-000001?picc_data={picc}&enc={enc}&cmac={cmac}`
  - `picc_data`：加密的 PICC 数据，解密后包含芯片 UID 和读取计数器。
  - `enc`：加密的文件数据（如果启用了 SDMENCFileData）。
  - `cmac`：AES-CMAC 签名，用于后端验证数据完整性。
  - NXP 官方 SUN 映射示例：`https://my424dna.com/?picc_data=FDE4...&enc=9459...&cmac=C48B...`
- **芯片 UID 是静态的**：NTAG424 DNA 的 7 字节硬件 UID 唯一且不变，NFC.cool Webhook 负载中的 `identifier` 就是它[reference:4]。动态变化的是 SUN URL 中的 `picc_data` / `enc` / `cmac` 参数，每次触碰都不同，但解密后仍能还原出同一个芯片 UID。
- 后端验证逻辑**不要从零手写**。Python 生态已有成熟开源实现：`nfc-developer/sdm-backend`（Flask，直接可跑）和 `pylibsdm`。AI 基于这两个库封装业务路由，而不是让它自己实现 AES-CMAC 细节。
- NFC.cool 的 Webhook 负载中，`identifier` 是标签 UID，`content` 是解码后的 NDEF 负载（即 SUN URL 字符串）。管理员扫描入库时，用 `identifier` 作为芯片 UID。

## 8. 已知约束与避坑清单（AI 生成代码时必须遵守）
- **NFC.cool Webhook 没有重试机制**：服务器返回非 2xx 即视为失败，扫描数据会丢失。管理员扫描入库接口要尽快返回 200，把耗时逻辑放到异步或直接省略。
- **Gunicorn 多进程下不要用内存存状态**：所有待处理/中间状态必须落 MySQL。不要用 Python 全局变量或字典保存“最近一次扫描的 UID”。
- **密钥绝不明文落库**：`chip_key.key_value_encrypted` 必须是应用层加密后的密文。当前阶段加密主密钥放在 ECS 环境变量中，按项目隔离（`MASTER_KEY_FASHION` / `MASTER_KEY_JEWELRY`）；生产前评估阿里云 KMS；绝不放代码仓库。
- **SUN URL 的 `uid` 用 `{picc}` 加密镜像，不要用明文 `{uid}`**：明文 UID 可被任何人读取，`{picc}` 需要密钥才能解密，隐私性更好。
- **阿里云 RDS 默认不开公网**：开发阶段用 DMS 连接，或把 ECS 内网地址加入 RDS 白名单，不要为了图方便把 3306 暴露到 `0.0.0.0/0`。

### 8.1 安全与权限
- 管理后台必须登录后访问；初期可用简单 Token/密码，禁止裸奔。
- NFC.cool Webhook 使用 Basic Auth 或 URL 中的共享 token 鉴权，防止伪造扫描。
- 管理端“查看密钥”会临时解密芯片密钥，必须二次确认并写入 `admin_audit`。
- 生产环境全站 HTTPS；RDS 3306 不对公网开放。

## 9. 前后端分离协作规则（AI 必须遵守）
- **API 契约是唯一事实来源**：项目根目录的 `API_CONTRACT.md` 定义了所有接口。后端 Codex 按它生成路由，前端调用按它拼装参数。任何一方不得自行变更字段名或结构。
- **后端只输出 JSON**：Flask 路由只返回 `jsonify(...)`，不包含任何 `render_template` 或 HTML 字符串。
- **前端使用环境变量**：Figma Make 导出的 React 项目通过 `VITE_API_BASE_URL` 读取后端基础地址，不得硬编码 IP 或端口。
- **CORS 白名单**：Flask 使用 `flask-cors`，`origins` 明确列出 `http://localhost:5173`（开发）和 `https://bumbum.cc`（生产），不使用通配符。
- **联调顺序**：先让 Codex 用 `curl` 测试后端接口可用 → 再让 Figma Make 导出前端代码 → 最后让 Codex 在前端代码中替换 Mock 数据为真实 `fetch` 调用。
- **生产部署**：Nginx 托管前端静态文件，并将 `/api/` 反向代理到 Flask，前后端同域，消除跨域。
- **路径例外**：`GET /t/<item_uid>` 是 NFC 统一入口，作为例外不受 `/api/` 前缀约束。

### 9.1 测试与验收
- 每个后端接口先用 `curl` 测试通过，再交给前端联调。
- 每次让 AI 改代码前，先在 GitHub commit 一次，改坏了可回滚。
- 前端联调时用 Chrome DevTools 的 Network 面板确认请求 URL、状态码、返回 JSON。

## 10. 多项目架构约定
- 本系统包含两个业务项目：fashion（数字服装）和 jewelry（文创饰品）。
- `core/` 目录存放跨项目共享的模型与逻辑（chip、chip_key、item、ownership、ownership_history、scan_log、SDM验证、密钥派生、信封加密）。任何业务模块不得重复定义这些模型。
- `fashion/` 和 `jewelry/` 只存放各自项目的业务表和业务 API。
- 新增业务表时，必须通过 `item_id` 外键关联共享的 `item` 表，不得新建独立的物品身份表。
- 所有 API 路径以 `/api/` 开头，业务模块的 API 用 `/api/fashion/` 和 `/api/jewelry/` 前缀隔离。
- 主密钥按项目隔离：`MASTER_KEY_FASHION` 和 `MASTER_KEY_JEWELRY` 分别从环境变量读取，派生时按芯片的 `project_id` 选择。
- NFC 统一入口为 `GET /t/<item_uid>`，在该路由内根据 item 的 `project_id` 决定渲染哪个项目的 H5。

## 11. 数据库设计原则：核心表共享，业务表隔离

### 设计原则：
1. 芯片、密钥、物品身份、所有权、扫描日志这五类数据是跨项目通用的，必须是同一张表，用 `project_id` 字段区分归属。一枚芯片的 UID 在全局唯一，它属于哪个项目由 `project_id` 标记，绝不能在两个库里各存一份。
2. 业务详情（服装的溯源、故事；饰品的养成进度、任务）按项目拆成独立表，通过 `item_id` 关联到共享的 `item` 表。
3. 用户表共享，以手机号为核心。同一个用户可能同时拥有服装和饰品，共享用户表让未来“跨项目权益打通”（比如买服装送饰品养成积分）成为可能。如果两个项目未来是不同合规主体，再加字段隔离即可。

具体 DDL 见项目根目录 `db/schema.sql`。AI 在生成任何查询/模型时，**必须**以 `db/schema.sql` 为唯一事实来源，不要自行臆造字段，如有修改调整必须声明清楚并维护项目文档。

## 12. 关键接口约定（完整见 API_CONTRACT.md）
| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/webhook/admin/scan` | 接收 NFC.cool 管理员扫描，自动登记芯片 UID |
| GET | `/t/<item_uid>` | 用户触碰 NFC 后的统一 H5 入口（NFC 入口例外，不受 `/api/` 前缀约束） |
| POST | `/api/public/bind` | 用户提交手机号，绑定物品所有者 |
| GET | `/api/admin/chips` | 管理端芯片列表 |
| GET | `/api/admin/items` | 管理端物品列表 |

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
4. 生成代码时，标注“需要我修改的地方”（如数据库密码、域名）。
5. 我是产品经理，不懂代码，请用简洁中文解释关键决策，不要贴大段无关的底层实现。
6. NTAG424 DNA 的 SDM 验证，优先用 `nfc-developer/sdm-backend` 或 `pylibsdm`，不要从零实现 AES-CMAC。
7. SUN URL 的模板为 `https://bumbum.cc/t/<item_uid>?picc_data={picc}&enc={enc}&cmac={cmac}`，物品 UID 在路径中，动态参数由芯片追加。

我当前的任务是：<在这里填入这次要做的事>
