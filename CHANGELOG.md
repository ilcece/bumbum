# CHANGELOG.md — BUMBUM NFC 数字项目决策日志

> 记录已确认的重要决策与原因。历史条目不能覆盖当前 PRD、TECH_SPEC、API、schema 或 AGENTS；明确标注被替代方案。

---

## 2026-10-23 文档审查修订（当前）

用户确认先完成文档、DDL 和协作规范修订，暂不生成业务代码。本次没有迁移现有 RDS、生成真实秘密或写入真实芯片。

- README 收敛为项目入口、实际进度和文件导航；新增 AGENTS.md 统一读取、授权、冲突处理、事实证据与交付规则；会话模板改为引用，减少多份规则漂移。
- 新增 .gitignore 与 .env.example，秘密留空，前端基础地址统一包含 /api，endpoint 不再重复该前缀。
- 目标 DDL 增加芯片唯一物品绑定、跨项目复合外键、唯一有效所有权和状态 CHECK；保留历史记录，日志支持未知 UID。
- 定义管理员 Cookie 会话、CSRF、受限首次 TOTP 设置、备份码登录、多进程持久状态；增加认证/限流/登录事件表。备份码改为高熵随机值，仅保存摘要，替代旧版可解密备份码数组。
- 补充 Phase 2 授权与短信挑战预留表，明确读取/发送短信不消费、成功绑定时事务消费；未决养成权限不签发。
- 修正信封加密的两层流程、独立 nonce/认证标签、AAD 和密钥版本；禁止 force 覆盖已有芯片密钥。
- 修正查看密钥的 GET 请求体为 POST，字段 bind_source 归属、channel 数组、完整 Phase 1 请求/响应与错误规则。
- 管理员认证统一属于 Phase 1；公开用户域名显式拒绝管理 API，明确域名代理边界。
- SDM 首次选钥/槽位/派生方案及真实写卡仍阻塞，养成身份/权限仍待产品确认；第三方能力和价格改为要求提供可复查证据，不假装已经实测。
- schema 仅作空库初始化，已有数据库升级需要独立迁移、备份与验证；新表不表示功能已实现。

### 本轮验证证据

- 在无网络、未映射端口的临时官方 MySQL 8.0.46 容器中执行空库 DDL，26 张表建表成功。
- 29 项数据库检查通过，包括唯一芯片绑定、跨项目拒绝、状态/时间约束、多条历史所有权、解密失败空 UID、凭证摘要唯一，以及两个独立数据库会话并发绑定时只有一条有效所有权提交成功。
- Markdown 本地链接/锚点、JSON 示例、配置秘密留空和 Git 忽略规则已检查；未运行应用、MFA/短信接口或真实芯片测试，不代表生产数据库已升级。

以下旧条目中，“K0–K4 全部按 UID 派生”“最终参数直接可写卡”“NFC.cool 能力已确认”“一次性 token 的所有操作均未区分消费”“密钥可强制覆盖”及认证/加密旧说明，均由当前文件替代。旧 KMS 固定报价没有来源与日期，不作为当前采购依据。

## 2026-10-23 初始讨论记录（历史，部分已被上述修订替代）

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
