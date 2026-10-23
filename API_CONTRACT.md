# BUMBUM API 契约

更新日期：2026-10-23。本文是接口定义来源，不表示任何接口已经实现。业务规则见 [PRD.md](PRD.md)，安全、事务和状态机见 [TECH_SPEC.md](TECH_SPEC.md)，字段以 [schema](db/schema.sql) 为准。

## 0. 通用约定

### 0.1 地址拼接与输入

本文展示完整路径 `/api/...`。前端 `VITE_API_BASE_URL` 已包含 `/api`，endpoint 字符串必须省略该前缀，并以 `/` 开头；拼接前去除 base 尾部 `/`。

| 环境 | base | endpoint | 实际请求 |
|---|---|---|---|
| 开发 | `http://localhost:5000/api` | `/admin/chips` | `http://localhost:5000/api/admin/chips` |
| 生产管理端 | `/api` | `/admin/chips` | `https://admin.bumbum.cc/api/admin/chips` |
| 生产用户端 | `/api` | `/tap/verify` | `https://nfc.bumbum.cc/api/tap/verify` |

不要拼接 `/api/api/...`。开发管理端请求携带 credentials，管理 API 的 CORS/Origin 仅允许 ADMIN_ORIGIN，不能将 CORS_ORIGINS 总清单中的用户前端也授权给管理 API；生产同域，不设置通配 CORS。示例中的 example token 和密码均是结构占位，不能用于实际认证。

写请求默认 `Content-Type: application/json`，日期为 ISO 8601 UTC，id 为正整数。未声明字段拒绝并返回 invalid_param。枚举使用小写，project 仅 fashion/jewelry。分页 page 默认 1、page_size 默认 20，最大 100；keyword 最长 128 字符。可空字段使用 null，不混用空字符串表示缺失。所有输入长度不得超过 schema 上限；profile.name 等必填文本不得为空白。

### 0.2 返回与错误

成功格式：
```json
{"status":"ok","data":{"id":12}}
```
失败格式：
```json
{"status":"error","code":"invalid_param","message":"参数不合法"}
```
列表 data 固定 `{ "items": [], "total": 0, "page": 1, "page_size": 20 }`。创建也返回 HTTP 200，以保持现有客户端约定；logout 和其他动作返回 `{ "status":"ok", "data":{ "logged_out":true } }` 或该动作明示的 data。

HTTP 200 的 `verified:false` 仅用于已执行的触碰业务验证失败；格式错误、未实现功能或内部故障按错误状态返回，不能伪装成防伪失败。

### 0.3 认证与权限

- Phase 1 管理端使用 `bumbum_admin_session` Cookie；不接受正式 Bearer 会话、不在 JSON 返回会话 token。Cookie 属性、CSRF、Origin 与持久化见 TECH_SPEC 第 4 节。
- 浏览器 POST/PATCH/PUT/DELETE 要求允许的 Origin；有 Cookie 的认证写请求另带 `X-CSRF-Token`。登录和 MFA 的无 Cookie 请求也检查 Origin。
- login、totp/verify、backup-code/verify 不要求正式会话。session、totp/setup、totp/enable、logout 可使用 enroll 会话；其余管理接口必须 full 会话且账号 active。
- Cookie 缺失/过期/已撤销返回 401 unauthorized；enroll 越权返回 403 mfa_required；CSRF/Origin 不符返回 403 csrf_failed/forbidden。
- Webhook 使用 HTTPS Basic Auth，用户名为 WEBHOOK_SHARED_SECRET、密码为空；不接收 URL 中的 token，不写入访问日志。
- Phase 2 只读接口通过 `X-Tap-Token` 传递 tap_token，写接口通过 JSON；不允许 query token。tap_token 不是用户登录或所有者身份证明。

### 0.4 阶段状态

Phase 1 是基础管理与完整管理员认证；真实密钥生成受 SDM 设计阻塞。Phase 2 验证与短信接口是目标契约，选钥、工具兼容性、短信提供商未完成前不能声称可用。Phase 3 运营/养成接口为预留；touch 权限及身份方案未确认。未来服务对尚未启用的功能返回 501 feature_not_ready；当前仓库根本没有运行中的 API。

## 1. 入库与用户触碰

### 1.1 POST /api/webhook/admin/scan（Phase 1）

查询参数 project 可选，默认 fashion，仅允许 fashion/jewelry。以下为待真实 App 核验的目标负载格式，不声称已经采集：
```json
{"identifier":"04:A2:7F:1B:5E:80:00","content":"https://nfc.bumbum.cc/tap?picc_data=...&cmac=...","date":"2026-10-23T08:00:00Z"}
```
identifier 必填，规范化为 7 字节冒号分隔大写 UID；content/date 可选，date 若提供须可解析，目标时间仅作附加输入，不用于信任排序。其他字段按第 0.1 节拒绝；若实测 App 增加字段，先修订契约。不要存储 content 中的动态参数作为认证状态。

验证鉴权与参数后，在数据库事务提交成功才返回 200；重复 UID 同项目幂等返回，跨项目返回 409 project_mismatch，不偷偷改项目。并发重复插入处理 UID 唯一键冲突。数据库失败返回 503 service_unavailable；不因“快速响应”在落库前返回成功。失败应提示管理员重扫，重试行为仍待工具实测。
```json
{"status":"ok","data":{"chip_uid":"04:A2:7F:1B:5E:80:00","is_new":true}}
```
错误：400 invalid_param、401 webhook_auth_failed、409 project_mismatch、503 service_unavailable。

### 1.2 POST /api/tap/verify（Phase 2，选钥方案阻塞）

请求体只接受 picc_data 和 cmac，不含 item_uid。目标格式为 picc_data 32 位十六进制、cmac 16 位十六进制，实际 SDM 编码仍须经单卡核验：
```json
{"picc_data":"FDE4AFA99B5C820A2C1BB0F1C792D0EB","cmac":"C48B89C17A233B2C"}
```
选钥、CMAC 校验、状态资格、防重放和授权签发遵守 TECH_SPEC 第 3、5 节。只接受通过 CMAC 的新计数器；状态不合格不能签发 token。refresh/重复提交旧 URL 返回 replay_suspect，前端提示重新触碰；CMAC 失败不更新计数器。

成功 data：verified=true、project、item_id、item_uid、owner_bound、tap_token、expires_in（300）、item_detail。fashion 的 item_detail 含 profile 字段和 trace 数组、story 对象或 null、channel 数组；jewelry 的 item_detail 含 name/description/material/meaning/image_urls。Phase 2 不返回“当前用户”养成进度。用户侧 channel 不返回 order_no 或个人交易数据。
```json
{"status":"ok","data":{"verified":true,"project":"fashion","item_id":12,"item_uid":"FASH-2026-000012","owner_bound":false,"tap_token":"t_example","expires_in":300,"item_detail":{"name":"外套","description":null,"material":null,"care_instructions":null,"size_chart":null,"image_urls":[],"trace":[],"story":null,"channel":[]}}}
```
验证失败不含 token：
```json
{"status":"ok","data":{"verified":false,"reason":"cmac_fail","message":"防伪验证未通过"}}
```
reason：cmac_fail / decrypt_fail / unknown_chip / replay_suspect / disabled / not_ready。disabled 包括芯片 disabled/lost 或物品 disabled/archived；not_ready 包括未绑定、物品 draft、尚未完成配置。内部 UID、密钥和计数器不向用户返回。格式错误 400、功能阻塞 501、服务故障 503。

### 1.3 POST /api/public/sms/send（Phase 2，提供商待选）

必填 phone、tap_token；phone 暂限中国大陆手机号的 11 位规范格式。需要有效且未消费的 bind 授权；read 授权不能发送绑定短信。
```json
{"phone":"13800138000","tap_token":"t_example"}
```
发送短信不消费 grant。校验 grant 与物品当前仍可绑定、写入挑战和发送限流状态；外部发送失败不能伪报成功，提供商重试/幂等约定待选择服务时补齐。成功 expires_in 为短信与 grant 剩余有效时间的较小值，不超过 300。
```json
{"status":"ok","data":{"sent":true,"expires_in":240}}
```
手机号 60 秒一次、IP 每小时最多 10 次；验证码最多 5 次失败，发新码使旧码失效。错误：400 invalid_param、403 invalid_tap_token、409 already_bound、429 sms_rate_limited、501 feature_not_ready、503 service_unavailable。

### 1.4 POST /api/public/bind（Phase 2）

必填 phone、sms_code（6 位数字字符串）、tap_token，item_id 从授权解析，禁止客户端替换：
```json
{"phone":"13800138000","sms_code":"123456","tap_token":"t_example"}
```
校验状态与 grant、匹配的短信挑战；在一个事务创建/复用 user、写 ownership(bind_source=user_self)、history(action=bind)，消费短信挑战与 bind grant。已绑定不覆盖，失败不消费授权；对错误验证码的失败计数必须持久化。
```json
{"status":"ok","data":{"item_id":12,"user_id":5,"bound":true}}
```
错误：400 invalid_param/invalid_sms_code、403 invalid_tap_token、409 already_bound、429 rate_limited、503 service_unavailable。

## 2. 管理端认证（全部 Phase 1）

### 2.1 POST /api/admin/auth/login

必填 username（1–64）、password（1–128，按原值验证，不 trim）。不得在 URL 或日志记录密码。
```json
{"username":"cece","password":"example-only"}
```
密码通过且已启用 TOTP，返回一次性 mfa_ticket（5 分钟），不签发完整会话：
```json
{"status":"ok","data":{"totp_required":true,"mfa_ticket":"m_example","expires_in":300}}
```
未启用 TOTP，仅设置 enroll Cookie：
```json
{"status":"ok","data":{"totp_required":true,"enrollment_required":true,"scope":"enroll","expires_in":300}}
```
初始管理员创建走后续受控服务器命令，无公开注册和默认密码。enroll 会话必须先 session 获取 CSRF，再 setup/enable。未知账号、禁用账号、密码错误统一 401 unauthorized，避免枚举；锁定 429 rate_limited，其他规则见 TECH_SPEC。

### 2.2 POST /api/admin/auth/totp/verify

必填 mfa_ticket、code（6 位数字字符串）。一次性挑战和 totp_last_step 原子校验/消费。成功设置 full Cookie，不返回正式会话 token：
```json
{"status":"ok","data":{"authenticated":true,"scope":"full","expires_in":28800}}
```
错误：401 invalid_mfa_ticket/invalid_totp_code、409 totp_replay、429 rate_limited。获取 CSRF 后才可调用业务写接口。

### 2.3 POST /api/admin/auth/backup-code/verify

必填 mfa_ticket、backup_code。密码验证后的挑战配合未用备份码才能登录；挑战和备份码同事务消费。成功响应与 2.2 相同。错误：401 invalid_mfa_ticket/invalid_backup_code、429 rate_limited。不能只凭备份码跳过密码。

### 2.4 GET /api/admin/auth/session

需要有效 enroll/full Cookie。返回 scope、expires_at、当前会话的 csrf_token；不返回 Cookie 值，不缓存。读取不轮换 token 或修改会话，生成与校验规则见 TECH_SPEC 第 4.1 节。
```json
{"status":"ok","data":{"scope":"enroll","expires_at":"2026-10-23T08:05:00Z","csrf_token":"c_example"}}
```

### 2.5 POST /api/admin/auth/totp/setup

仅 enroll Cookie + CSRF；请求体为 `{}`。返回 provisioning_uri、secret 和 expires_in（enroll 剩余秒数）。二维码和原始秘密只用于当前设置流程，响应 no-store，不持久保存在浏览器。重复调用复用同一个待绑定秘密；已启用时 409 already_exists，不替换旧因子。

### 2.6 POST /api/admin/auth/totp/enable

仅 enroll Cookie + CSRF，必填 code（6 位数字字符串）。成功撤销旧 enroll 会话、启用 TOTP 并设置 full Cookie；10 个备份码只展示一次，至少各 128 位熵：
```json
{"status":"ok","data":{"enabled":true,"scope":"full","expires_in":28800,"backup_codes":["example-placeholder-not-a-real-code"]}}
```
该示例数组只演示字段结构；实际必须 10 个。不得记录明文备份码，服务端只保存摘要。错误：401 invalid_totp_code、409 already_exists/totp_replay、429 rate_limited。随后重新获取 session/CSRF。

### 2.7 POST /api/admin/auth/logout

有效 enroll/full Cookie + CSRF，请求体 `{}`；撤销 session 并清除相同 Path 的 Cookie。返回 data.logged_out=true，后续旧 Cookie 无效。账号禁用对所有会话即时生效，未来修改账号状态同事务撤销会话及挑战。

## 3. 管理端芯片（Phase 1）

所有接口需要 full Cookie。ChipView：id、chip_uid、project、chip_status、item_id（可空）、item_uid（可空）、batch_no（可空）、provisioned_at（可空）、keys_generated（布尔）、created_at、updated_at。不返回密文、密钥或内部计数器。

| 方法与路径 | 输入 | HTTP 200 的 data |
|---|---|---|
| GET /api/admin/chips | page/page_size、project、status、keyword 可选；keyword 查 UID | 分页 ChipView 列表 |
| GET /api/admin/chips/{id} | 路径 id | ChipView 加 ownership：null 或 item_id/user_id/phone_masked/bound_at |
| POST /api/admin/chips/{id}/generate-keys | JSON `{}` + CSRF；不接受 force | chip_id、generated=true、key_version |
| POST /api/admin/chips/{id}/keys | JSON confirm=true + CSRF | chip_uid、keys、sun_url_template |
| PATCH /api/admin/chips/{id}/status | JSON chip_status 必填 + CSRF | 更新后 ChipView |
| POST /api/admin/chips/{id}/bind-item | JSON item_id 必填 + CSRF | 更新后 ChipView |
| POST /api/admin/chips/{id}/unbind-item | JSON `{}` + CSRF | 更新后 ChipView |

密钥生成暂受设计阻塞，未来启用后仍禁止覆盖已有记录：409 already_exists；传 force 返回 400 invalid_param。查看密钥使用 POST，keys 为 K0–K4 各 32 位十六进制字符串，sun_url_template 引用 TECH_SPEC 第 5.1 节；确认只用于防止误操作，不替代身份与 CSRF。密钥响应 Cache-Control:no-store，先写入审计，密钥不存在返回 404 not_found。

状态转换、恢复和绑定按 TECH_SPEC 第 2.2 节；不允许任意跳转。芯片重复绑定、跨项目、目标已有芯片分别返回 409 already_bound / project_mismatch / item_already_has_chip。状态转换不合法返回 409 invalid_state。密钥方案未完成时 generate-keys 返回 501 feature_not_ready。

## 4. 管理端物品

ItemView：id、project、item_uid、sku_code、status、created_at、updated_at、profile（类型按项目，无记录为 null）。profile 对外不重复暴露其内部自增 id/item_id；时间均按第 0 节。

Phase 1 full Cookie，写请求加 CSRF：

| 方法与路径 | 输入 | HTTP 200 的 data |
|---|---|---|
| GET /api/admin/items | page/page_size、project、status、keyword 可选；keyword 查 item_uid/sku_code | 分页 ItemView 列表 |
| POST /api/admin/items | project、item_uid 必填；sku_code 可空；status 可省略且仅允许 draft | 新 ItemView，profile=null |
| GET /api/admin/items/{id} | 路径 id | ItemView |
| PATCH /api/admin/items/{id} | 至少 sku_code/status 之一；禁止 item_uid/project_id/project | 更新后 ItemView |
| GET /api/admin/items/{id}/profile | 路径 id | profile 对象或 null |
| PUT /api/admin/items/{id}/profile | 按下表，整体替换 | 保存后的 profile 对象 |

| 项目 | profile 输入 |
|---|---|
| fashion | name 必填（1–128）；description/material/care_instructions 可空；size_chart 为对象或 null；image_urls 为 URL 字符串数组，省略默认 [] |
| jewelry | name 必填（1–128）；description/material/meaning 可空；image_urls 同上 |

PUT 省略可选字段即清空为 null 或 []；仅允许 http/https 图片 URL，数组最多 20 项，每项最多 2048 字符；material 最长 256。禁止跨项目字段。item_uid 格式与项目匹配；重复返回 409 already_exists。物品状态机见 TECH_SPEC，缺少 profile 不允许激活；archived 为终态。无物理删除 API，“CRUD”的删除业务以归档代替。

下列为 Phase 3 full Cookie 预留，写请求加 CSRF；只有 fashion 物品可用，否则 409 project_mismatch。PUT 整体替换，数组最多 100 项；每条字段由 schema 限定，无额外字段。完成 Phase 3 契约细化和启用前返回 501 feature_not_ready。

| 方法与路径 | PUT 输入 | GET/PUT 的目标 data |
|---|---|---|
| GET/PUT /api/admin/items/{id}/trace | 数组；每项 stage 必填，event_time/location/operator/detail 可空，sort_order 默认 0 | trace 数组，无记录 [] |
| GET/PUT /api/admin/items/{id}/story | 对象；title/content/media_urls 可空，sort_order 默认 0 | story 对象，无记录 null |
| GET/PUT /api/admin/items/{id}/channel | 数组；每项 channel_type 必填，channel_name/order_no/purchased_at 可空 | channel 数组，无记录 [] |

trace.stage 和 channel_type 枚举、长度以 schema 为准；返回包括记录 id 和上述字段，不包含重复 item_id。channel 在所有返回中都是数组；公开用户视图必须去除订单号等交易信息。

## 5. 管理端所有权（Phase 1）

full Cookie；写请求加 CSRF。OwnershipView：id、item_id、item_uid、user_id、phone_masked、bound_at、unbound_at、is_active、bind_source；列表不展示完整手机号。管理员输入的 phone 按第 1.3 节格式，note 可空且最长 256。

| 方法与路径 | 输入 | HTTP 200 的 data |
|---|---|---|
| GET /api/admin/ownerships | page/page_size、item_id、user_phone（手机号前缀）、is_active（0/1）可选 | 分页 OwnershipView 列表 |
| POST /api/admin/ownerships | item_id、phone 必填；note 可选 | 新 OwnershipView |
| POST /api/admin/ownerships/{id}/unbind | note 可选 | 关闭后的旧 OwnershipView |
| POST /api/admin/ownerships/{id}/transfer | to_phone 必填；note 可选 | 新 OwnershipView |

手动绑定：写 ownership.bind_source=admin，并写 history(action=bind, from_user_id=null, to_user_id=用户)。history 没有 bind_source 字段。仅允许非 archived 物品绑定；已有有效所有者返回 409 already_bound。

解绑/转赠要求对应 ownership 当前有效，否则 409 invalid_state。转给原所有者返回 409 already_bound，不制造新历史。转赠关闭旧绑定、创建新绑定（bind_source=admin），只写一条 history(action=transfer, from/to 用户)；绑定、历史和审计必须同事务提交。用户手机号只用于管理员操作和验证，不写入日志/审计 detail。

## 6. 用户侧详情与养成

Phase 2 GET /api/fashion/items/{item_id}/detail：需要有效 X-Tap-Token，校验其与路径 item_id 和当前状态匹配；读取不消费授权。data 为 item_uid、profile（对象）、trace（数组）、story（对象或 null）、channel（数组）、owner_bound。不返回 UID、计数器、手机号、订单号。项目不符 409 project_mismatch，token 不符/过期/已消费 403 invalid_tap_token。

Phase 2 GET /api/jewelry/items/{item_id}/detail：同样的授权与错误规则；data 为 item_uid、profile（对象）、owner_bound。Phase 2 不返回进度，也不从持有人访问推断“当前用户”。

Phase 3 GET /api/jewelry/items/{item_id}/progress 和 POST /api/jewelry/items/{item_id}/touch：权限/身份、转赠后的进度及冷却维度待产品确认，当前 blocked。未确认前返回 501 feature_not_ready，不实现授权、不为有效 ownership 的用户代加经验。旧版“只凭 tap_token 获取当前用户进度”的描述已替代。

## 7. 错误码与 HTTP 状态

| HTTP | code | 含义 |
|---|---|---|
| 400 | invalid_param | 输入缺失、格式错误、未知字段 |
| 400 | invalid_sms_code | 短信码不匹配/过期，或达到挑战失败次数 |
| 401 | unauthorized | 管理员认证失败或会话不可用 |
| 401 | webhook_auth_failed | Webhook鉴权失败 |
| 401 | invalid_mfa_ticket | MFA挑战过期、已用或不可用 |
| 401 | invalid_totp_code | TOTP验证码错误 |
| 401 | invalid_backup_code | 备份码错误或已用 |
| 403 | forbidden | Origin/权限不允许 |
| 403 | csrf_failed | CSRF token错误 |
| 403 | mfa_required | enroll会话不能访问业务 |
| 403 | invalid_tap_token | 授权无效、过期、已消费、范围或绑定状态不符 |
| 404 | not_found | 资源或密钥记录不存在 |
| 409 | already_exists | UID/物品标识/密钥等已存在 |
| 409 | already_bound | 已绑定或重复绑定不允许 |
| 409 | item_already_has_chip | 物品已绑定其他芯片 |
| 409 | project_mismatch | 芯片/物品/业务类型不匹配 |
| 409 | invalid_state | 当前状态不允许此动作 |
| 409 | totp_replay | TOTP已被使用 |
| 429 | rate_limited | 登录/MFA等触发限流或锁定 |
| 429 | sms_rate_limited | 短信发送过于频繁 |
| 501 | feature_not_ready | 阶段功能未启用或设计仍阻塞 |
| 503 | service_unavailable | 数据库或外部依赖不可用 |
| 500 | internal_error | 未预期内部错误，不泄露堆栈或SQL |

所有管理端接口共享第 0 节的 400/401/403/404/409/429/500/503 规则，具体错误以实际触发条件为准；不通过“统一 HTTP 200”掩盖故障。
