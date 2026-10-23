# TECH_SPEC.md — BUMBUM NFC 数字项目技术规格

> 本文件是技术决策与实现的唯一技术事实来源。`README.md` 定义项目全局约束与协作规则；本文件定义“具体怎么做”。两者冲突时，以本文件的技术细节为准，并同步回 `README.md`。
>
> 最后更新：2026-10-23
> 维护人：cece（产品经理）与 AI 协作

---

## 1. 技术栈锁定

| 层 | 选型 | 说明 |
|---|---|---|
| 操作系统 | 阿里云 ECS，Ubuntu 26.04 64 位 | 已持有 |
| 后端语言 | Python 3 | 与 Flask 生态一致 |
| 后端框架 | Flask | 轻量，AI 生成代码最稳；不使用 Django |
| 数据库 | 阿里云 RDS MySQL 8.0 | 已持有；开发期通过 DMS 或 ECS 内网访问 |
| 后端 WSGI | Gunicorn | 多 worker 运行 Flask |
| 反向代理 | Nginx | 托管前端静态文件 + 反代 `/api/` |
| 前端框架 | React + Vite + TypeScript | Figma Make 导出格式 |
| 前端部署 | Nginx 静态文件 | 两个 SPA：用户侧、管理端 |
| 代码管理 | GitHub（private 仓库） | `.env` 永不入库 |
| 数据库可视化 | 阿里云 DMS | 开发期首选；Navicat Premium Lite 备选 |
| NFC 芯片 | NXP NTAG424 DNA | 支持 SDM/SUN 动态加密 |
| 写卡工具 | NFC.cool Tools | 密钥/SDM 需 App 内逐枚手动配置；CSV 仅批量写链接内容 |
| 域名 | `bumbum.cc`（备案中） | 子域名规划见第 8 节 |

**禁止事项**：不要更换技术栈；不要引入微服务、消息队列、Redis 等未在本文档列出的基础设施，除非先更新本文档并说明理由。

---

## 2. 总体架构：共享内核 + 模块化单体

### 2.1 架构选择

采用 **“共享内核 + 模块化单体”**：

- **一个 GitHub 仓库**
- **一个 Flask 应用**
- **一个 MySQL 数据库**
- 内部按 `core/`、`fashion/`、`jewelry/`、`admin/` 划分模块，用 Flask Blueprint 注册
- 两个前端 SPA（用户侧、管理端）分别构建，由 Nginx 托管

**不采用**：两套独立系统（芯片 UID 会重复、SDM 逻辑写两遍）、微服务（运维复杂度超出产品经理可维护范围）。

### 2.2 共享与隔离的边界

| 数据/能力 | 归属 | 是否跨项目共享 |
|---|---|---|
| 芯片 UID、芯片密钥 | `core/` | 共享，`chip_uid` 全局唯一 |
| 物品身份（`item`） | `core/` | 共享，用 `project_id` 区分 fashion/jewelry |
| 所有权与流转历史 | `core/` | 共享 |
| 扫描日志（SDM 验证） | `core/` | 共享，用 `project_id` 区分 |
| 用户（手机号） | `core/` | 共享 |
| 服装溯源、品牌故事、购买渠道 | `fashion/` | 仅服装 |
| 饰品养成进度、任务、奖励 | `jewelry/` | 仅饰品 |
| 管理后台 API | `admin/` | 跨项目，统一管理 |

**硬规则**：任何业务模块不得重复定义 `item`、`chip`、`chip_key`、`ownership`、`ownership_history`、`scan_log`、`user`。新增业务表必须通过 `item_id` 外键关联共享的 `item` 表。

### 2.3 代码目录结构（建议）

```text
bumbum/
├── app.py                      # 创建 Flask app，注册所有 Blueprint
├── config.py                   # 读取 .env，暴露配置
├── requirements.txt
├── .env.example                # 变量名清单，值留空
├── .gitignore                  # 必须包含 .env、venv、__pycache__
├── core/
│   ├── models/                 # project, user, item, chip, chip_key,
│   │                           # ownership, ownership_history, scan_log
│   ├── crypto/
│   │   ├── key_derivation.py   # 主密钥派生 5 个密钥
│   │   └── envelope.py         # 信封加密/解密
│   ├── sdm/
│   │   └── verifier.py         # SUN URL 的 CMAC 验证（基于 sdm-backend / pylibsdm）
│   └── api/
│       ├── tap.py              # POST /api/tap/verify
│       ├── admin_chip.py       # /api/admin/chip/*
│       ├── admin_item.py       # /api/admin/item/*
│       ├── ownership.py        # /api/public/bind、/api/admin/ownership/*
│       └── webhook.py          # /api/webhook/admin/scan
├── fashion/
│   ├── models/                 # fashion_item_profile/trace/story/channel
│   └── api/                    # /api/fashion/*
├── jewelry/
│   ├── models/                 # jewelry_item_profile/growth/task/reward
│   └── api/                    # /api/jewelry/*
├── admin/
│   └── auth/                   # 管理端登录、TOTP、审计
├── db/
│   └── schema.sql              # 数据库 DDL，唯一事实来源
├── frontend/
│   ├── nfc/                    # 用户侧 SPA（React + Vite）
│   └── admin/                  # 管理端 SPA（React + Vite）
├── README.md
├── PRD.md
├── TECH_SPEC.md
├── API_CONTRACT.md
└── CHANGELOG.md
```

---

## 3. 数据库设计原则

### 3.1 核心原则

1. **芯片、密钥、物品身份、所有权、扫描日志、用户**六类数据跨项目共享，同一张表，用 `project_id` 区分归属。
2. **业务详情**（服装的溯源/故事/渠道；饰品的养成/任务/奖励）按项目拆独立表，通过 `item_id` 关联共享 `item`。
3. `chip_uid` 全局唯一；`item_uid` 全局唯一；手机号在 `user` 表唯一。
4. 所有 DDL 以 `db/schema.sql` 为唯一事实来源。AI 不得臆造字段；任何调整必须先改 `schema.sql` 并在 `CHANGELOG.md` 记录原因。

### 3.2 关键字段约定

| 字段 | 格式 | 示例 |
|---|---|---|
| `project.code` | 固定枚举 | `fashion` / `jewelry` |
| `item_uid` | 项目前缀 + 年份 + 6 位序号 | `FASH-2026-000001` / `JEW-2026-000001` |
| `chip_uid` | NTAG424 DNA 7 字节静态 UID，冒号分隔大写十六进制 | `04:A2:7F:1B:5E:80:00` |
| 密钥 | AES-128，16 字节，十六进制 32 字符 | 派生得到，不手写 |
| 时间 | 统一 UTC 存储，展示时转本地时区 | `DATETIME` |

> `item_uid` 仅用于管理端与数据库内部标识，**不出现在 NFC 触碰 URL 中**。NFC 触碰 URL 中的物品身份完全由 `picc_data` 解密出的 `chip_uid` 反查得到。

### 3.3 所有权流转

- `ownership` 表只保存**当前有效绑定**（`is_active=1`）。
- 每次绑定、解绑、转赠，同时向 `ownership_history` 写入一条记录（`action` = `bind` / `unbind` / `transfer`）。
- 不允许物理删除 `ownership` 历史；解绑用 `unbound_at` + `is_active=0`。

### 3.4 索引与性能

- `chip.chip_uid` 唯一索引；`item.item_uid` 唯一索引；`user.phone` 唯一索引。
- `scan_log` 按 `(chip_uid, created_at)` 建索引，用于防伪审计。
- 管理端列表分页，默认每页 20 条，必须使用 `LIMIT/OFFSET` 或游标分页，禁止全表返回。

---

## 4. 密钥体系

### 4.1 主密钥按项目隔离

- `MASTER_KEY_FASHION`、`MASTER_KEY_JEWELRY` 两个 16 字节十六进制主密钥，分别存放在 ECS 的 `.env` 中。
- 派生时根据芯片所属 `project_id` 选择对应主密钥。
- 主密钥**绝不入库、绝不进 GitHub、绝不写进代码**。
- 生产前评估阿里云 KMS 托管；当前阶段先用环境变量，迁移时业务代码只改“读取主密钥”这一层。

### 4.2 密钥派生（per-tag key diversification）

派生输入：

```text
UID(7字节) ‖ NTAG424_AID(7字节, D2760000850101) ‖ Key Number(1字节, 0x00~0x04) ‖ System Identifier(可变, 如 b"bumbum")
```

使用 AES-CMAC，主密钥为 CMAC 密钥，输出 16 字节即该芯片该槽位的派生密钥。Python 实现使用 `cryptography` 库的 `CMAC(algorithms.AES(master_key))`，不要从零实现 AES-CMAC。

为每枚芯片派生 K0~K4 共 5 个密钥；K0 是 App Master Key，K1–K4 是应用密钥。

### 4.3 落库加密：信封加密

`chip_key` 表中的密钥**不得明文存储**。采用信封加密：

- **加密落库时**：生成数据密钥 DEK（当前阶段可用 `STORAGE_ENCRYPTION_KEY` 派生或直接使用一个 32 字节随机密钥），用 AES-GCM 加密 5 个派生密钥，得到密文；将密文、nonce、密钥版本写入数据库。DEK 明文只在内存中短暂存在。
- **解密使用时**：从数据库读出密文和 nonce，用 `STORAGE_ENCRYPTION_KEY` 解密得到 5 个密钥明文，用于 SDM 验证或管理端“查看密钥”。
- 未来迁移 KMS 时，把“用 `STORAGE_ENCRYPTION_KEY` 加解密 DEK”替换为“调用 KMS GenerateDataKey / Decrypt”，业务代码其余部分不变。

### 4.4 密钥查看与写卡

- 管理端芯片列表**不展示密钥明文**。
- “查看密钥”必须二次确认，并写入 `admin_audit`（操作人、芯片 UID、时间、IP）。
- 写卡流程：管理员在管理端逐枚查看 5 个密钥和 SUN URL 模板 → 在 NFC.cool Tools 中逐枚手动配置密钥、链接、SUN 开关。**CSV 批量写入不支持批量配置每枚芯片的不同密钥和 SDM**，不要设计依赖 CSV 批量密钥的流程。

---

## 5. NTAG424 DNA 与 SUN 验证

### 5.1 SUN URL 最终模板

所有芯片共用同一路径，物品身份由 `picc_data` 解密出的 `chip_uid` 反查得到：

```text
https://nfc.bumbum.cc/tap?picc_data={picc}&cmac={cmac}
```

- `picc_data`：加密的 PICC 数据，解密后包含芯片 UID 和读取计数器。
- `cmac`：AES-CMAC 签名，用于完整性验证。
- **不包含 `item_uid`**：避免静态明文暴露物品标识；物品身份完全由后端解密 `picc_data` 得到 `chip_uid` 后反查。
- **Phase 1 不包含 `enc`**：当前不启用 SDMENCFileData。未来若启用，模板追加 `&enc={enc}`，并在后端增加一步解密。
- URL 长度约 140 字符，NTAG424 DNA 的 NDEF 容量约 256 字节，安全。

### 5.2 静态 UID 与动态参数的区别

- **芯片 UID 是静态的**：7 字节硬件序列号，NFC.cool Webhook 的 `identifier` 就是它。
- **动态变化的是 SUN URL 中的 `picc_data` / `cmac`**：每次触碰不同，但解密后仍能还原出同一个芯片 UID。
- 用户侧验证时，从 `picc_data` 解密出的 UID 必须与入库时的 `chip_uid` 一致，这是防伪校验的关键。

### 5.3 验证实现

- **不要从零实现 AES-CMAC 和 SDM 解密**。优先使用 `nfc-developer/sdm-backend` 或 `pylibsdm`，在 `core/sdm/verifier.py` 中封装成业务函数。
- 验证步骤：
  1. 前端从 URL 读取 `picc_data` 和 `cmac`，调用 `POST /api/tap/verify`，请求体**只含**这两个字段，**不传 `item_uid`**。
  2. 后端解析 `picc_data`，用 `sdm-backend` / `pylibsdm` 解密得到 `chip_uid` 和读取计数器。
  3. 用 `chip_uid` 查 `chip` 表，拿到 `item_id` 和 `project_id`；若芯片不存在，返回 `unknown_chip`。
  4. 从 `chip_key` 解密该芯片的 SDM 密钥，验证 `cmac`；失败返回 `cmac_fail`。
  5. 检查读取计数器是否大于该芯片上次记录（防重放）；异常返回 `replay_suspect`。
  6. 写入 `scan_log`（`verify_result` = `pass` / `cmac_fail` / `decrypt_fail` / `unknown_chip` / `replay_suspect`）。
  7. 根据 `project_id` 返回对应业务数据（服装或饰品）；前端根据 `verified` 渲染物品页或防伪警告页。

### 5.4 SDMENCFileData

- Phase 1 **不启用**，SUN URL 中不出现 `enc`。`picc_data` + `cmac` 已满足防伪验证。
- 未来若有“仅限所有者查看的私密内容”，再启用 `enc`：SUN URL 模板改为 `https://nfc.bumbum.cc/tap?picc_data={picc}&enc={enc}&cmac={cmac}`，后端验证步骤增加一步“用会话密钥解密 `enc`”，再查数据库返回私密内容。
- 不要在没有真实需求前增加复杂度。

---

## 6. 前后端分离协作

### 6.1 契约先行

- `API_CONTRACT.md` 是前后端唯一接口事实来源。
- 后端只输出 JSON：`jsonify(...)`，不返回 `render_template` 或 HTML 字符串。
- 前端通过 `VITE_API_BASE_URL` 读取后端地址；开发环境为 `http://localhost:5000`，生产环境使用同域相对路径 `/api/`，不硬编码。
- CORS：开发环境仅放行 `http://localhost:5173`（用户侧）和 `http://localhost:5174`（管理端，如果分开启动）；生产环境同域，不需要 CORS。
- 联调顺序：先用 `curl` 测通后端 → 再用 Figma Make 导出前端 → 最后让 Codex 把 Mock 替换为真实 `fetch`。

### 6.2 NFC 入口的架构

**NFC 入口不是后端路由，而是前端 SPA 路由。**

- 用户触碰芯片 → 浏览器访问 `https://nfc.bumbum.cc/tap?picc_data=...&cmac=...`
- Nginx 的 `location /` 用 `try_files $uri $uri/ /index.html` 返回 React SPA。
- React 路由捕获 `/tap`，从 `window.location.search` 读取 `picc_data` 和 `cmac`。
- 前端调用 `POST /api/tap/verify`，请求体为 `{ "picc_data": "...", "cmac": "..." }`。
- 后端解密 `picc_data` 得到 `chip_uid`，查 `chip` → `item` → `project`，验证后返回 JSON。
- 前端渲染结果。

**不要再设计 `GET /t/<item_uid>` 的后端 HTML 路由；也不要在 `/api/tap/verify` 请求体中传 `item_uid`。**

---

## 7. 管理后台安全基线

管理后台 `admin.bumbum.cc` 是公开可访问的，必须分层防御，不能只靠 TOTP。

### 7.1 第一层：网络层收敛（最高优先级）

- Nginx 层对 `admin.bumbum.cc` 加 IP 白名单：`allow` 常用出口 IP，`deny all`。
- 如果 IP 不固定，改用阿里云安全组限制源 IP，或通过 VPN / Zero Trust 网关访问。
- 这一层能消除绝大部分自动化扫描和钓鱼暴露面，且不需要写后端代码。

### 7.2 第二层：应用层认证

- 管理员登录：密码 + TOTP 第二因素。
- TOTP 使用 `pyotp` 实现；每个管理员一个 `totp_secret`，**应用层加密存储**（复用第 4.3 节信封加密逻辑）。
- 首次绑定：后端生成 `provisioning_uri`，前端用二维码组件展示，管理员用任意 Authenticator（Google / Microsoft / 1Password 等）扫码，输入一次验证码确认。
- **重放保护**：记录每个管理员最近一次成功验证的 time step，同一个 time step 的验证码只接受一次。
- **速率限制**：登录失败 5 次锁定 5 分钟，10 次锁定 30 分钟；登录端点加 CAPTCHA。
- **备份码**：首次绑定 TOTP 时生成 8–10 个一次性备份码，展示一次后加密入库，每个只能用一次。
- **非标准登录路径**：登录页放在随机字符串路径下（如 `/auth-x7k2m9`），降低被自动化工具发现登录页的概率。这只是辅助，不能替代 IP 白名单和 TOTP。

### 7.3 第三层：会话与审计

- 会话 Cookie 设置 `HttpOnly`、`Secure`、`SameSite=Strict`，有效期短（如 8 小时）。
- 登录事件写入日志：IP、User-Agent、时间、成功/失败。
- 陌生 IP 成功登录时，通过短信或邮件告警。
- 管理端敏感操作（查看密钥、导出、停用芯片、修改绑定）写入 `admin_audit`。

---

## 8. 域名与部署拓扑

### 8.1 域名规划

| 域名 | 用途 | 说明 |
|---|---|---|
| `bumbum.cc` | 品牌官网/落地页 | 可选，Phase 1 可不做 |
| `nfc.bumbum.cc` | 用户侧 H5（服装 + 饰品共用） | React SPA；`/api/` 反代 Flask |
| `admin.bumbum.cc` | 管理后台 | React SPA；`/api/` 反代同一 Flask |

**不需要** `api.bumbum.cc`。两个前端各自用自己的子域 `/api/` 反代到同一个 Flask 进程（`127.0.0.1:5000`），生产环境天然同域。

### 8.2 DNS 与 SSL

- 阿里云 DNS 添加 `nfc`、`admin` 两条 A 记录，指向 ECS 公网 IP。
- SSL：通配符证书 `*.bumbum.cc`，或阿里云免费证书逐个申请。
- 全站 HTTPS；HTTP 301 跳转 HTTPS。

### 8.3 Nginx 配置骨架

```nginx
# nfc.bumbum.cc
server {
    listen 443 ssl;
    server_name nfc.bumbum.cc;

    location / {
        root /var/www/bumbum-frontend/nfc/dist;
        try_files $uri $uri/ /index.html;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# admin.bumbum.cc
server {
    listen 443 ssl;
    server_name admin.bumbum.cc;

    location / {
        allow 你的办公室公网IP;
        allow 你的家庭公网IP;
        deny all;

        root /var/www/bumbum-frontend/admin/dist;
        try_files $uri $uri/ /index.html;
    }
    location /api/ {
        allow 你的办公室公网IP;
        allow 你的家庭公网IP;
        deny all;

        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 8.4 进程管理

- Gunicorn 启动：`gunicorn -w 2 -b 127.0.0.1:5000 app:app`。
- 用 `systemd` 或 `supervisor` 托管，保证开机自启、崩溃重启。
- **Gunicorn 多进程下禁止用内存存状态**：所有待处理/中间状态落 MySQL。

---

## 9. 环境变量与配置

### 9.1 使用方式

- 项目根目录创建 `.env`，每行 `名称=值`。
- `.env` 必须写入 `.gitignore`；仓库只保留 `.env.example`（值留空）。
- 安装 `python-dotenv`，在 `app.py` / `config.py` 顶部 `load_dotenv()`。
- 代码中用 `os.getenv("变量名")` 读取，不硬编码任何密码。

### 9.2 变量清单

```bash
DB_HOST=localhost
DB_PORT=3306
DB_USER=
DB_PASSWORD=
DB_NAME=bumbum_digital

MASTER_KEY_FASHION=
MASTER_KEY_JEWELRY=
STORAGE_ENCRYPTION_KEY=

WEBHOOK_SHARED_SECRET=
ADMIN_TOTP_ISSUER=BUMBUM Admin

CORS_ORIGINS=http://localhost:5173,http://localhost:5174
VITE_API_BASE_URL=http://localhost:5000
```

- `MASTER_KEY_*`：16 字节十六进制。
- `STORAGE_ENCRYPTION_KEY`：32 字节随机十六进制，用于信封加密。
- `WEBHOOK_SHARED_SECRET`：Webhook 鉴权共享密钥。
- 生产环境 `VITE_API_BASE_URL` 使用相对路径 `/api`，由构建时注入。

---

## 10. 安全与权限补充

- NFC.cool Webhook 使用 Basic Auth 或 URL 共享 token 鉴权，防止伪造扫描；失败返回 401。
- Webhook 接口尽快返回 200（NFC.cool 无重试机制，非 2xx 即丢数据）；耗时逻辑异步或省略。
- RDS 3306 不对公网开放；开发期用 DMS，或把 ECS 内网地址加入白名单。
- 管理端“查看密钥”二次确认 + `admin_audit`。
- 用户绑定手机号：校验手机号格式；同一物品同一时间只允许一个 `is_active=1` 的绑定；绑定/解绑写 `ownership_history`。
- 所有 API 返回统一结构：成功 `{"status":"ok","data":{...}}`；失败 `{"status":"error","code":"...","message":"..."}`。

---

## 11. 已知限制与待验证事项

| 事项 | 状态 | 影响 |
|---|---|---|
| NFC.cool CSV 不支持批量配置 NTAG424 密钥/SDM | 已确认 | 写卡必须逐枚手动配置密钥、SUN 开关；CSV 仅批量写链接内容 |
| NFC.cool Webhook 无重试 | 已确认 | 服务器非 2xx 即丢扫描数据；入库接口必须快速返回 |
| SUN URL 不含 `item_uid` | 已决策 | 物品身份由 `picc_data` 解密出的 `chip_uid` 反查；前端不传 `item_uid` |
| SDMENCFileData 配置复杂度 | 已知 | Phase 1 不启用，SUN URL 不含 `enc`；未来启用时模板追加 `&enc={enc}` 并增加后端解密步骤 |
| 阿里云 KMS 成本 | 已知 | 生产前评估；当前用环境变量替代 |
| admin 子域公开暴露 | 已决策 | 采用 IP 白名单 + TOTP + 审计分层防御 |
| 饰品养成机制细节 | 待产品定义 | 表结构可先预留 `jewelry_user_progress` 等 |
| 批量写卡规模化工具 | 待评估 | 当前用 NFC.cool 逐枚；产量大时再评估 ixkio 等 |

---

## 12. 分阶段实施计划

### Phase 1：基础闭环验证（当前）

- Webhook 接收管理员扫描，写入 `chip` 表。
- 管理端物品 CRUD（`item` + `fashion_item_profile` 最小集）。
- 芯片-物品-所有人绑定、停用启用。
- 管理端查看单枚芯片的 5 个派生密钥（二次确认 + 审计）。
- 验收：扫描一枚芯片入库；管理端绑定物品；查看密钥；手动在 NFC.cool 写卡。

### Phase 2：用户侧验证与绑定

- `POST /api/tap/verify` 接入 `sdm-backend` / `pylibsdm`；请求体为 `{picc_data, cmac}`，后端解密得到 `chip_uid` 再反查物品。
- `nfc.bumbum.cc` 用户侧 SPA：`/tap` 路由读取 `picc_data` 和 `cmac`，调用验证接口；验证通过展示物品信息，失败展示防伪警告。
- 未绑定物品展示手机号绑定入口，写入 `ownership` + `ownership_history`。
- 管理端登录 + TOTP + 备份码 + 速率限制。

### Phase 3：业务运营页

- 服装：溯源、品牌故事、购买渠道 CRUD 与 H5 渲染。
- 饰品：养成进度、任务、奖励机制。

### Phase 4：安全与成本优化

- 评估阿里云 KMS 替换环境变量。
- 评估 RDS Serverless 或读写分离（仅在有真实流量数据后）。
- 评估 Passkey（WebAuthn）作为 TOTP 的补充。

---

## 13. 给 AI 的技术指令（每次生成代码时必须遵守）

1. 技术栈固定：Python 3 + Flask + MySQL + React + Vite；不更换、不引入未列出的基础设施。
2. 数据库字段以 `db/schema.sql` 为唯一事实来源；不臆造字段；改表必须先改 DDL 并记录 `CHANGELOG.md`。
3. 共享模型只放在 `core/`；`fashion/` 和 `jewelry/` 不得重复定义 `item`、`chip`、`chip_key`、`ownership`、`ownership_history`、`scan_log`、`user`。
4. 后端只输出 JSON；NFC 入口由 Nginx 返回前端 SPA，前端路由为 `/tap`，调用 `POST /api/tap/verify`，请求体**只含** `picc_data` 和 `cmac`，不含 `item_uid`；不要生成 `GET /t/<item_uid>` 的 HTML 路由。
5. SDM 验证优先用 `nfc-developer/sdm-backend` 或 `pylibsdm`，不要从零实现 AES-CMAC。
6. 密钥不明文落库；使用信封加密；主密钥从 `.env` 读取；不写入代码或仓库。
7. Webhook 接口快速返回 200；不使用内存存状态；多进程安全。
8. 管理端敏感操作写 `admin_audit`；登录实现 TOTP、重放保护、速率限制、备份码。
9. 生成代码时标注“需要 cece 修改的地方”（如数据库密码、域名、IP 白名单）。
10. 用简洁中文解释关键决策，不贴大段无关底层实现。

---

## 14. 变更记录

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-10-23 | 初版 TECH_SPEC.md | 收敛前序讨论中的技术决策 |
| 2026-10-23 | 明确 NFC 入口为前端 SPA + `POST /api/tap/verify` | 前后端分离 + 子域名部署要求 |
| 2026-10-23 | 明确 NFC.cool CSV 不支持批量密钥/SDM | 实际工具限制 |
| 2026-10-23 | 增加管理后台分层安全基线 | admin 子域公开可访问 |
| 2026-10-23 | SUN URL 改为 `https://nfc.bumbum.cc/tap?picc_data={picc}&cmac={cmac}` | 物品身份由 `picc_data` 解密出的 `chip_uid` 反查，URL 不暴露 `item_uid`；Phase 1 不启用 `enc` |
