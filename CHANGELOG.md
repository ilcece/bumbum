# CHANGELOG.md — BUMBUM NFC 数字项目决策日志

> 记录每次重要变更“改了什么”和“为什么改”。AI 生成代码前应先读本文件，避免重复已经否决的方案。

---

## 2026-10-23

### 项目上下文文档建立

- 新增 `README.md`、`TECH_SPEC.md`、`API_CONTRACT.md`、`db/schema.sql`、`PRD.md`、`CHANGELOG.md`、`.ai/SESSION_START.md`。
- 目的：为 AI 协作提供单一事实来源，避免每次新会话“失忆”。

### 技术栈锁定

- 后端：Python 3 + Flask；数据库：阿里云 RDS MySQL 8.0；前端：React + Vite + TypeScript（Figma Make 导出）；部署：Gunicorn + Nginx。
- 原因：Flask 轻量，AI 生成代码最稳；React + Vite 与 Figma Make 导出格式一致。
- 否决：微服务、消息队列、Redis。原因：当前规模无需，运维复杂度超出产品经理可维护范围。

### 多项目架构：共享内核 + 模块化单体

- 一个仓库、一个 Flask 应用、一个 MySQL 库；内部按 `core/`、`fashion/`、`jewelry/`、`admin/` 划分模块。
- 芯片、密钥、物品身份、所有权、扫描日志、用户六类数据跨项目共享，用 `project_id` 区分。
- 业务详情按项目拆表，通过 `item_id` 关联共享 `item`。
- 原因：避免芯片 UID 重复、SDM 逻辑写两遍；保留未来拆分能力。

### 子域名规划

- `nfc.bumbum.cc`：用户侧 H5；`admin.bumbum.cc`：管理后台；`bumbum.cc`：品牌官网（可选）。
- 不使用 `api.bumbum.cc`：两个前端各自同域 `/api/` 反代到同一 Flask，生产环境天然同域。
- 原因：职责分离，CORS 更干净，SSL 和 DNS 管理简单。

### NFC 入口改为前端 SPA + `POST /api/tap/verify`

- 旧方案：后端 `GET /t/<item_uid>` 渲染 HTML。
- 新方案：`https://nfc.bumbum.cc/tap?picc_data=...&cmac=...` 由 Nginx 返回 React SPA；前端读取参数，调用 `POST /api/tap/verify`。
- 原因：前后端分离要求后端只输出 JSON；NFC 入口是前端路由，不是后端 API。

### SUN URL 去除 `item_uid`，Phase 1 不含 `enc`

- 最终模板：`https://nfc.bumbum.cc/tap?picc_data={picc}&cmac={cmac}`。
- 物品身份由后端解密 `picc_data` 得到的 `chip_uid` 反查；URL 不暴露静态 `item_uid`。
- Phase 1 不启用 SDMENCFileData，模板不含 `enc`；未来启用时追加 `&enc={enc}` 并增加后端解密步骤。
- 原因：减少静态明文暴露；NTAG424 DNA 的 NDEF 容量约 256 字节，当前模板约 140 字符，安全。

### NFC.cool 能力边界确认

- CSV 批量写入**不支持**批量配置 NTAG424 DNA 的每枚芯片不同密钥和 SDM 配置。
- 写卡流程：CSV 批量写链接内容 + 在 App 内逐枚手动配置密钥/SUN 开关。
- Phase 1 目标同步修正为“跑通 Webhook 入库 → 物品 CRUD → 绑定/停用 → 查看密钥 → 手动写卡”。

### 密钥体系

- 主密钥按项目隔离：`MASTER_KEY_FASHION` / `MASTER_KEY_JEWELRY`，存放在 ECS `.env`。
- 每枚芯片的 K0–K4 通过 AES-CMAC 从主密钥确定性派生（per-tag key diversification）。
- `chip_key` 落库使用信封加密：DEK 加密 5 个密钥，`STORAGE_ENCRYPTION_KEY` 加密 DEK。
- 生产前评估阿里云 KMS；当前不采购，用环境变量替代。
- 原因：KMS 3.0 软件实例约 2499 元/月，项目验证期成本过高；信封加密逻辑先跑通，迁移 KMS 时只改“加解密 DEK”这一层。

### 管理后台安全基线

- `admin.bumbum.cc` 公开可访问，采用分层防御：
  1. Nginx / 安全组 IP 白名单（最高优先级）；
  2. 密码 + TOTP 第二因素，非标准登录路径，速率限制，TOTP 重放保护，一次性备份码；
  3. 会话 Cookie `HttpOnly` / `Secure` / `SameSite=Strict`，登录事件审计与陌生 IP 告警。
- 原因：TOTP 不能单独抵御实时钓鱼；IP 白名单成本最低、效果最直接。

### tap_token 机制

- `POST /api/tap/verify` 成功返回一次性、5 分钟有效的 `tap_token`，与 `chip_uid`、`item_id` 绑定。
- 后续 `/api/public/bind`、`/api/jewelry/items/{item_id}/touch` 必须携带。
- 原因：防止验证通过后业务接口被直接刷；绑定手机号需要短信验证码，养成动作需要冷却判断。

### 环境变量机制

- 敏感配置放 `.env`，代码通过 `os.getenv()` 读取；`.env` 写入 `.gitignore`，仓库只保留 `.env.example`。
- 原因：避免数据库密码、主密钥进入 GitHub。

### 待验证事项

- NFC.cool CSV 批量写入的密钥/SDM 能力：已确认不支持，写卡流程改为逐枚手动配置。
- 阿里云 KMS 成本：生产前评估。
- 饰品养成机制细节：Phase 3 细化，`schema.sql` 已预留基础表。
- 批量写卡规模化工具：当前用 NFC.cool 逐枚；产量大时再评估 ixkio 等。
