# BUMBUM 接口说明：页面要给什么，后台会返回什么

更新日期：2026-10-24。**接口**就是网页和后端约定的办事入口，例如“登记芯片”“绑定手机号”。本文是接口地址、字段和返回结果的定义，不表示已经实现。业务看 [PRD](PRD.md)，流程看 [TECH_SPEC](TECH_SPEC.md)，精确安全参数看 [技术附录](docs/IMPLEMENTATION_DETAILS.md)。

阅读方式：先找想做的事，再看要提供的字段和返回结果。字段名保留原样供 AI 写代码；示例密码、token 都是占位内容，不是真实凭证。GET 表示读取，POST 表示提交操作，PATCH 改指定字段，PUT 整份替换。

## 0. 每个接口都遵守的规则

### 0.1 地址和字段

前端基础地址 VITE_API_BASE_URL 已含 /api，调用时只补后面的部分，不能重复拼出 /api/api。

| 环境 | 基础地址 | 补上的部分 | 最终请求 |
|---|---|---|---|
| 开发 | http://localhost:5000/api | /admin/chips | http://localhost:5000/api/admin/chips |
| 生产管理端 | /api | /admin/chips | https://admin.bumbum.cc/api/admin/chips |
| 生产用户端 | /api | /tap/verify | https://nfc.bumbum.cc/api/tap/verify |

提交内容默认用 JSON，即按字段名组织的数据，标明 Content-Type:application/json。只接受声明过的字段；多传、漏传必填或格式不对，返回 400 invalid_param。id 是正整数，项目只用 fashion/jewelry；时间为 ISO 8601 UTC。可空字段用 null，不拿空字符串代替；长度不超过 [schema](db/schema.sql)，必填文本不能只有空格。

列表每页默认 20 条：page 从 1 开始，page_size 最多 100，keyword 最长 128 字符。开发管理网页只能用 ADMIN_ORIGIN，浏览器须允许携带登录 Cookie（credentials）；生产同域调用。不把用户网页加入管理端允许来源，详见技术规格第 4、6 节。

### 0.2 怎么看返回结果

成功看 status=ok 和 data 中的结果；失败看 code 和给人看的 message：
```json
{"status":"ok","data":{"id":12}}
```
```json
{"status":"error","code":"invalid_param","message":"参数不合法"}
```
列表 data 固定为 items、total、page、page_size；空列表 items=[]。创建成功也返回 HTTP 200，保留已有约定。仅芯片验证的业务失败允许 200 加 verified=false；参数错误、系统故障、功能没开放使用对应错误状态，不能假装正常。

### 0.3 哪些凭证要带上

| 场景 | 需要提供什么 |
|---|---|
| 管理业务 | 浏览器自动携带 bumbum_admin_session Cookie（登录凭证）；必须是 full 完整登录且账号启用 |
| 修改管理数据 | 另带 X-CSRF-Token（页面取得的防冒用口令），并检查请求来自允许的管理网页；不直接把它写成用户手填项 |
| 登录/验证器验证/备份码验证 | 不要求完整登录，但仍检查网页来源 Origin；已带 Cookie 的写请求仍按规则检查额外口令 |
| 首次设置验证器 | enroll 临时权限，只能 session、totp/setup、totp/enable、logout，不能操作业务 |
| 扫描回调 | HTTPS Basic Auth：WEBHOOK_SHARED_SECRET 作用户名，密码为空；不把秘密放链接或日志 |
| 用户查看详情 | 请求头 X-Tap-Token 放触碰后的临时凭证 |
| 用户发短信/绑定 | JSON 中带 tap_token，不放链接参数；它不证明访问者是所有者 |

网页提交数据时（POST/PATCH/PUT/DELETE）都检查允许的 Origin；已有 Cookie 的认证写请求另检查额外口令。正式登录凭证只走 Cookie，不作为 Bearer 或 JSON 返回，不放浏览器本地存储。无效登录 401 unauthorized；设置阶段越权 403 mfa_required；防冒用口令错误 403 csrf_failed，网页来源不符 403 forbidden。精确检查方式见技术附录第 4 节。

### 0.4 当前能做到哪一步

当前没有运行中的 API。第一阶段做管理认证与基础管理；全局 K1 方案已定，真实密钥/写卡还等计算规则、权限和测试。第二阶段做用户验证与短信；第三阶段做运营和养成。未开放的功能返回 501 feature_not_ready；不能用文档存在证明接口可用。

## 1. 登记芯片、验证触碰和绑定手机号

### 1.1 POST /api/webhook/admin/scan：登记芯片（第一阶段）

供 NFC.cool 扫描后调用。project 可选，默认 fashion，也可 jewelry。identifier 是必填芯片编号，统一为 7 字节、冒号分隔大写十六进制；content/date 可选，date 须能解析但不用于信任排序。真实 App 格式与重试行为仍待核验：
```json
{"identifier":"04:A2:7F:1B:5E:80:00","content":"https://nfc.bumbum.cc/tap?picc_data=...&cmac=...","date":"2026-10-23T08:00:00Z"}
```
保存成功后才返回成功；同 UID 同项目重复扫描不新增，项目不同返回 409 project_mismatch，不能偷偷换项目。同时扫描造成唯一键冲突也按此处理；失败提示重扫，不在数据库保存前先报成功，不把 content 中动态参数当认证状态。
```json
{"status":"ok","data":{"chip_uid":"04:A2:7F:1B:5E:80:00","is_new":true}}
```
错误：400 invalid_param、401 webhook_auth_failed、409 project_mismatch、503 service_unavailable。额外字段先拒绝，实测 App 如有新字段先改契约。

### 1.2 POST /api/tap/verify：核验这次触碰（第二阶段，待实测）

只提交 picc_data（加密芯片信息，32 位十六进制）、cmac（防伪码，16 位十六进制）；不增加项目、UID、版本、查找码或 item_uid，实际编码仍待单卡确认：
```json
{"picc_data":"FDE4AFA99B5C820A2C1BB0F1C792D0EB","cmac":"C48B89C17A233B2C"}
```
服务器按技术规格第 5.1 节：全局 K1 先解出候选编号 → 查库核对项目和配置版本 → 用独立 K2 按 SDM 规则核对防伪码 → 唯一完整通过后确认身份 → 检查状态并一起保存新读数、日志和临时凭证。

不能只看“解密没报错”或“像十六进制编号”。多个版本都完整通过是配置异常，500 internal_error；普通服务故障 503，未开放 501，请求过密 429 rate_limited（次数待实测）。旧链接重试提示重新触碰；失败不能更新读数或发凭证，也不能把系统故障说成假货。

成功返回 verified、project、item_id/item_uid、owner_bound（是否已有所有者）、tap_token、expires_in=300 秒、item_detail（物品资料）。服装含资料字段、trace 数组、story 对象或 null、channel 数组；饰品含 name/description/material/meaning/image_urls。不返回 UID、读数、订单号、手机号或“当前用户养成进度”：
```json
{"status":"ok","data":{"verified":true,"project":"fashion","item_id":12,"item_uid":"FASH-2026-000012","owner_bound":false,"tap_token":"t_example","expires_in":300,"item_detail":{"name":"外套","description":null,"material":null,"care_instructions":null,"size_chart":null,"image_urls":[],"trace":[],"story":null,"channel":[]}}}
```
业务验证失败不发 token：
```json
{"status":"ok","data":{"verified":false,"reason":"cmac_fail","message":"防伪验证未通过"}}
```
reason 可为 cmac_fail（防伪码错误）、decrypt_fail（芯片信息无法解析）、unknown_chip（未登记）、replay_suspect（旧读数）、disabled（芯片停用/丢失，或物品停用/归档）、not_ready（未绑定、物品草稿或未配置好）。格式错误仍为 400。

### 1.3 POST /api/public/sms/send：发绑定短信（第二阶段）

必填 phone（中国大陆 11 位手机号）、tap_token；仅未用掉的 bind 凭证可用，read 不能绑定：
```json
{"phone":"13800138000","tap_token":"t_example"}
```
先确认凭证与物品仍允许绑定，再保存短信验证记录和发送次数；发送失败不能报成功。提供商及失败重试办法待选。发送不消耗凭证；expires_in 不超过短信和凭证剩余有效期，最大 300 秒：
```json
{"status":"ok","data":{"sent":true,"expires_in":240}}
```
同手机号 60 秒一次，同 IP 每小时最多 10 次，短信码最多错 5 次；发新码让同凭证同手机号旧码失效。错误：400 invalid_param、403 invalid_tap_token、409 already_bound、429 sms_rate_limited、501 feature_not_ready、503 service_unavailable。

### 1.4 POST /api/public/bind：绑定所有者（第二阶段）

必填 phone、sms_code（6 位数字文字）、tap_token；物品从凭证中确定，不能由客户端替换：
```json
{"phone":"13800138000","sms_code":"123456","tap_token":"t_example"}
```
校验凭证、状态和匹配的短信码；一起完成创建/复用用户、保存 ownership(bind_source=user_self) 和 history(action=bind)、用掉短信码与 bind 凭证。有主人不覆盖，失败不消耗凭证，错码次数仍要保存：
```json
{"status":"ok","data":{"item_id":12,"user_id":5,"bound":true}}
```
错误：400 invalid_param/invalid_sms_code、403 invalid_tap_token、409 already_bound、429 rate_limited、503 service_unavailable。

## 2. 管理员登录（第一阶段）

TOTP 是验证器 App 的短时验证码；mfa_ticket 是“密码通过后、还需完成验证码检查”的 5 分钟一次性凭证。enroll 只能设置验证器，full 才能管理业务。

### 2.1 POST /api/admin/auth/login：先验密码

必填 username（1–64 字符）、password（1–128 字符，按原值验证，不去掉首尾空格）；密码不放 URL 或日志：
```json
{"username":"cece","password":"example-only"}
```
已设置验证器时，返回 mfa_ticket，不给完整权限：
```json
{"status":"ok","data":{"totp_required":true,"mfa_ticket":"m_example","expires_in":300}}
```
还没设置时，只给 enroll Cookie：
```json
{"status":"ok","data":{"totp_required":true,"enrollment_required":true,"scope":"enroll","expires_in":300}}
```
随后先调用 session 取得防冒用口令，再 setup/enable。初始管理员通过以后实现的受控服务器命令创建，无公开注册和默认密码。账号不存在、禁用或密码错都返回 401 unauthorized，不帮助外人猜账号；锁定返回 429 rate_limited。

### 2.2 POST /api/admin/auth/totp/verify：再验验证码

必填 mfa_ticket、code（6 位数字文字）。登录挑战和同一时段验证码只能一起成功使用一次；通过后设置 full Cookie，不返回正式登录 token：
```json
{"status":"ok","data":{"authenticated":true,"scope":"full","expires_in":28800}}
```
错误：401 invalid_mfa_ticket/invalid_totp_code、409 totp_replay、429 rate_limited；之后获取 session 的额外口令才能修改数据。

### 2.3 POST /api/admin/auth/backup-code/verify：用备份码恢复登录

必填 mfa_ticket、backup_code；仍先验密码。挑战和备份码一起用掉，成功结果同 2.2；错误 401 invalid_mfa_ticket/invalid_backup_code、429 rate_limited。

### 2.4 GET /api/admin/auth/session：查询本次登录

有效 enroll/full Cookie 可用；返回权限、到期时间和本次登录的防冒用口令，不返回 Cookie 值，不缓存，不换口令或修改登录状态：
```json
{"status":"ok","data":{"scope":"enroll","expires_at":"2026-10-23T08:05:00Z","csrf_token":"c_example"}}
```

### 2.5 POST /api/admin/auth/totp/setup：获取验证器二维码

仅 enroll Cookie 加防冒用口令，请求体 `{}`。返回 provisioning_uri（二维码内容）、secret（验证器设置秘密）、expires_in（剩余设置秒数）。不缓存或长期保存在浏览器；重复调用复用同一待设置秘密，已启用则 409 already_exists，不覆盖旧秘密。

### 2.6 POST /api/admin/auth/totp/enable：确认验证码并启用

仅 enroll Cookie 加防冒用口令，必填 code（6 位数字文字）。成功后撤销所有旧 enroll 登录，换为 full Cookie；10 个备份码仅显示一次，服务端只存指纹，每个至少 128 位安全随机数：
```json
{"status":"ok","data":{"enabled":true,"scope":"full","expires_in":28800,"backup_codes":["example-placeholder-not-a-real-code"]}}
```
示例仅展示数组结构，实际必须 10 个。错误：401 invalid_totp_code、409 already_exists/totp_replay、429 rate_limited；随后重新获取 session。

### 2.7 POST /api/admin/auth/logout：退出

有效 enroll/full Cookie 加防冒用口令，请求体 `{}`；撤销当前登录并清除相同 Path 的 Cookie，返回 data.logged_out=true。禁用账号时所有登录和未用挑战立即失效。

## 3. 管理芯片（第一阶段）

均须 full 登录，写请求加防冒用口令。ChipView 是芯片摘要：id、chip_uid、project、chip_status、item_id/item_uid（可空）、batch_no（可空）、provisioned_at（可空）、keys_generated（是否有密钥）、created_at、updated_at；不展示密钥、密文或读数。

| 要做什么及接口 | 要给什么 | 成功返回的 data |
|---|---|---|
| 查列表：GET /api/admin/chips | page/page_size、project、status、keyword 可选，keyword 查 UID | 分页 ChipView |
| 查详情：GET /api/admin/chips/{id} | 芯片 id | ChipView，加 ownership：null 或 item_id/user_id/phone_masked/bound_at |
| 生成密钥：POST /api/admin/chips/{id}/generate-keys | `{}`，不接受 force | chip_id、generated=true、key_version |
| 查看密钥：POST /api/admin/chips/{id}/keys | confirm=true | chip_uid、keys、sun_url_template |
| 改状态：PATCH /api/admin/chips/{id}/status | chip_status | 更新后 ChipView |
| 绑定物品：POST /api/admin/chips/{id}/bind-item | item_id | 更新后 ChipView |
| 解除绑定：POST /api/admin/chips/{id}/unbind-item | `{}` | 更新后 ChipView |

密钥功能等实际计算规则、权限和测试完成后才开放，否则 501 feature_not_ready。已有密钥不能覆盖，409 already_exists；传 force 是 400 invalid_param。keys 含 K0–K4 的 32 位十六进制值；K1 是对应版本全局密钥的加密副本，不逐卡生成。查看前确认并保存操作记录，返回 no-store 禁止缓存；不存在为 404 not_found。页面须提醒：查看 K1 涉及该版本所有芯片的秘密，不仅是这一枚。URL 模板见技术规格第 5.1 节。

状态转换见技术规格第 2.2 节，不能任意跳转；重复绑定 409 already_bound、跨项目 409 project_mismatch、目标已有芯片 409 item_already_has_chip、非法状态 409 invalid_state。确认按钮不能代替权限或防冒用检查。

## 4. 管理物品

ItemView 是物品摘要：id、project、item_uid、sku_code（款式编号）、status、created_at、updated_at、profile（对应项目的资料，没有为 null）；不额外返回 profile 内部 id/item_id。

第一阶段均须 full 登录，写请求加防冒用口令：

| 要做什么及接口 | 要给什么 | 成功返回的 data |
|---|---|---|
| 查列表：GET /api/admin/items | page/page_size、project、status、keyword 可选，keyword 查编号/sku_code | 分页 ItemView |
| 创建：POST /api/admin/items | project、item_uid 必填，sku_code 可空；status 省略或仅 draft | 新 ItemView，profile=null |
| 查详情：GET /api/admin/items/{id} | 物品 id | ItemView |
| 改部分字段：PATCH /api/admin/items/{id} | 至少 sku_code/status 之一，不许改 item_uid/project_id/project | 更新后 ItemView |
| 查资料：GET /api/admin/items/{id}/profile | 物品 id | profile 或 null |
| 整份存资料：PUT /api/admin/items/{id}/profile | 下表字段 | 保存后的 profile |

| 项目 | 资料字段 |
|---|---|
| fashion（服装） | name（名称）必填，1–128 字符；description（介绍）、material（材质）、care_instructions（洗护）可空；size_chart（尺码表）为对象或 null；image_urls（图片地址）为 URL 数组，省略为 [] |
| jewelry（饰品） | name（名称）必填，1–128 字符；description（介绍）、material（材质）、meaning（寓意）可空；image_urls（图片地址）同上 |

PUT 省略可选字段就清为 null/[]，不能当“保留原值”。图片只用 http/https，最多 20 项，每项最多 2048 字符；material 最长 256，其他不超 schema，不接收另一项目字段。item_uid 前缀必须匹配项目，重复 409 already_exists；无 profile 不可启用，归档不直接恢复。删除业务使用归档，不真删记录。

第三阶段的下列接口仅服装物品可用，否则 409 project_mismatch；未细化开放前 501 feature_not_ready。full 登录，写请求加防冒用口令；PUT 整份替换，数组最多 100 项：

| 接口 | PUT 要给什么 | GET/PUT 返回 |
|---|---|---|
| 溯源记录：GET/PUT /api/admin/items/{id}/trace | 数组：stage 必填，event_time/location/operator/detail 可空，sort_order 默认 0 | trace 数组，空时 [] |
| 品牌故事：GET/PUT /api/admin/items/{id}/story | 对象：title/content/media_urls 可空，sort_order 默认 0 | story 对象，空时 null |
| 购买渠道：GET/PUT /api/admin/items/{id}/channel | 数组：channel_type 必填，channel_name/order_no/purchased_at 可空 | channel 数组，空时 [] |

stage/channel_type 取值和长度按 schema；返回包含记录 id、上述字段，不重复 item_id。购买渠道 channel 始终为数组；用户端去掉订单号和个人交易信息。

## 5. 管理所有权（第一阶段）

full 登录，写请求加防冒用口令。OwnershipView 是绑定记录：id、item_id、item_uid、user_id、phone_masked（隐藏部分数字的手机号）、bound_at、unbound_at、is_active、bind_source。列表不展示完整手机号；输入手机号按 1.3 节，note 可空且最长 256。

| 要做什么及接口 | 要给什么 | 成功返回的 data |
|---|---|---|
| 查列表：GET /api/admin/ownerships | page/page_size、item_id、user_phone（手机号前缀）、is_active=0/1 可选 | 分页 OwnershipView |
| 绑定：POST /api/admin/ownerships | item_id、phone 必填，note 可选 | 新 OwnershipView |
| 解绑：POST /api/admin/ownerships/{id}/unbind | note 可选 | 关闭后的旧 OwnershipView |
| 转赠：POST /api/admin/ownerships/{id}/transfer | to_phone 必填，note 可选 | 新 OwnershipView |

只给非归档物品绑定；已有主人 409 already_bound。管理员绑定写 ownership.bind_source=admin 和 history(action=bind, from_user_id=null, to_user_id=用户)，history 没有 bind_source。

解绑/转赠只操作当前有效记录，否则 409 invalid_state；转给原主人为 409 already_bound，不造新历史。转赠关闭旧绑定、创建新绑定（来源 admin），只写一条 transfer 历史，保存 from/to 用户；绑定、历史、操作记录一起成功。日志和操作记录不保存完整手机号。

## 6. 用户看详情和饰品养成

第二阶段下列 GET 要带 X-Tap-Token，核对其对应物品和当前状态，读取不消耗凭证；跨项目 409 project_mismatch，凭证无效/过期/已用掉或不匹配 403 invalid_tap_token：

| 接口 | 返回的 data |
|---|---|
| 服装详情：GET /api/fashion/items/{item_id}/detail | item_uid、profile 对象、trace 数组、story 对象或 null、channel 数组、owner_bound |
| 饰品详情：GET /api/jewelry/items/{item_id}/detail | item_uid、profile 对象、owner_bound |

不返回芯片 UID、读取序号、手机号或订单号；第二阶段也不返回进度。第三阶段 GET /api/jewelry/items/{item_id}/progress 和 POST /api/jewelry/items/{item_id}/touch 还需确认谁可操作、怎样认人、转赠后进度及冷却规则，当前不开放，返回 501 feature_not_ready；不能把登记所有者当作访问者替他加经验。

## 7. 失败时怎样理解

HTTP 状态码是这次请求的大类结果，code 是具体原因，message 是给人看的解释。创建/普通成功仍是 200；不能把故障统一改成 200。

| HTTP | code | 含义 |
|---|---|---|
| 400 | invalid_param | 输入缺失、格式错误、未知字段 |
| 400 | invalid_sms_code | 短信码不匹配/过期，或达到挑战失败次数 |
| 401 | unauthorized | 账号/密码检查失败，或本次登录已失效 |
| 401 | webhook_auth_failed | 扫描回调的身份检查失败 |
| 401 | invalid_mfa_ticket | 密码通过后的临时凭证过期、已用或无效 |
| 401 | invalid_totp_code | 验证器验证码错误 |
| 401 | invalid_backup_code | 备份码错误或已用 |
| 403 | forbidden | 请求网页或操作权限不允许 |
| 403 | csrf_failed | 防冒用口令不正确 |
| 403 | mfa_required | 仅设置验证器的临时登录不能操作业务 |
| 403 | invalid_tap_token | 临时凭证无效、过期、已用掉或不适用于本物品/操作 |
| 404 | not_found | 资源或密钥记录不存在 |
| 409 | already_exists | UID/物品标识/密钥等已存在 |
| 409 | already_bound | 已绑定或重复绑定不允许 |
| 409 | item_already_has_chip | 物品已绑定其他芯片 |
| 409 | project_mismatch | 芯片/物品/业务类型不匹配 |
| 409 | invalid_state | 当前状态不允许此动作 |
| 409 | totp_replay | 同一时段的验证器验证码已经用过 |
| 429 | rate_limited | 请求太频繁，或登录尝试被暂时锁定 |
| 429 | sms_rate_limited | 短信发送过于频繁 |
| 501 | feature_not_ready | 功能还没开放，或前置设计/测试未完成 |
| 503 | service_unavailable | 数据库或外部依赖不可用 |
| 500 | internal_error | 程序内部异常；不给用户展示代码、SQL或秘密 |


管理接口共同使用第 0 节检查和上述 400/401/403/404/409/429/500/503；按实际原因返回，不泄露程序堆栈、SQL 或秘密。
