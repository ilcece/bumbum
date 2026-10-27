# BUMBUM 接口说明：页面要给什么，后台会返回什么

更新日期：2026-10-26。**接口**就是网页和后端约定的办事入口，例如“登记芯片”“绑定手机号”。本文定义地址、字段和返回；已实现与预留设计统一看第0.4节。业务看[PRD](PRD.md)，流程看[TECH_SPEC](TECH_SPEC.md)，精确安全参数看[技术附录](docs/IMPLEMENTATION_DETAILS.md)，任务和历史分别见[TODO](TODO.md)、[CHANGELOG](CHANGELOG.md)。

阅读方式：先找想做的事，再看要提供的字段和返回结果。字段名保留原样供 AI 写代码；示例密码、token 都是占位内容，不是真实凭证。GET 表示读取，POST 表示提交操作，PATCH 改指定字段，PUT 整份替换。

## 0. 每个接口都遵守的规则

### 0.1 地址和字段

前端基础地址 VITE_API_BASE_URL 已含 /api，调用时只补后面的部分，不能重复拼出 /api/api。

| 环境 | 基础地址 | 补上的部分 | 最终请求 |
|---|---|---|---|
| 本机开发 | /api | /health | http://localhost:5174/api/health（Vite 转给5000端口） |
| 香港测试管理端 | /api | /admin/chips | https://test.bumbum.cc/api/admin/chips（部署后） |
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

对非预期500及数据库异常503增加可选error_id：服务端生成24位小写十六进制错误编号，页面附在原通俗提示后供反馈。正常校验、重复、登录失败及未注册地址等不增加程序故障日志；不要求每个503都有编号。日志仅包含编号、UTC时间、方法、路由模板、异常类型及项目代码文件/行号，不包含请求/查询正文、认证信息、异常原文、SQL/参数、源代码或局部变量；数据库失败仍回滚。任务与部署状态见[TODO](TODO.md)。

### 0.3 哪些凭证要带上

| 场景 | 需要提供什么 |
|---|---|
| 管理业务 | 浏览器自动携带 bumbum_admin_session Cookie（登录凭证）；必须已通过密码和验证码且账号启用 |
| 修改管理数据 | 另带 X-CSRF-Token（页面取得的防冒用口令），并检查请求来自允许的管理网页；不直接把它写成用户手填项 |
| 登录 | 一次提交账号、密码和验证码；强制检查网页来源 Origin 和 JSON，不依赖现有登录凭证 |
| 扫描回调 | HTTPS Basic Auth：WEBHOOK_ADMIN_USERNAME 指定已有管理员名，WEBHOOK_SHARED_SECRET 作独立扫码密码；不把秘密放链接或日志 |
| 用户查看详情 | 请求头 X-Tap-Token 放触碰后的临时凭证 |
| 用户发短信/绑定 | JSON 中带 tap_token，不放链接参数；它不证明访问者是所有者 |

所有管理写请求（POST/PATCH/PUT/DELETE）都检查允许的 Origin 和 JSON；除 login 外，还必须有有效 Cookie 和额外口令。正式登录凭证只走 Cookie，不作为 Bearer 或 JSON 返回，不放浏览器本地存储。无效登录 401 unauthorized；防冒用口令错误 403 csrf_failed，网页来源不符 403 forbidden。精确检查方式见技术附录第 4 节。

### 0.4 当前能做到哪一步

当前已实现：GET /api/admin/stats/taps、POST /api/tap/verify（含可选browser_view模式）、GET /api/tap/items/{id}/view与GET /api/fashion/items/{id}/detail、两个运行检查接口，管理员login/session/logout，GET/POST /api/admin/chips、POST /api/admin/chips/{id}/bind-item及generate-keys、keys、confirm-provisioning三个POST入口，扫描回调，GET/POST /api/admin/items，GET/PATCH /api/admin/items/{id}及PUT /api/admin/items/{id}/profile。密钥配置入口不连接实卡，配置缺失或密文无法核对返回503；验收和合并状态看TODO。物品资料与启停只开放服装，具体限制见第4节。其余未注册地址返回404；已注册地址使用不支持的方法返回405，例如独立GET /api/admin/items/{id}/profile未开放，应使用物品详情接口。扫描配置缺失或不合法时返回503，不允许空密码访问。后续已接入路由但未开放的业务使用501，不伪造成功。本文其余预留接口不表示已实现；任务进度与验收证据分别在TODO和CHANGELOG维护。

手机页持续查看接口（POST /api/tap/verify 的 browser_view 模式及 GET /api/tap/items/{id}/view）已在功能分支 `feat/mobile-tap-view@143c738` 实现并推送，尚未合入 `main`；该分支的软件回归、跳过项、人工验收及部署状态见 TODO 和 CHANGELOG。不要把功能分支代码当作 main 已开放的接口。

### 0.5 当前已实现的运行检查

用于本机或受管理IP限制的云测试运行检查，不要求登录，不读取或返回密钥、账号资料；香港Nginx不向陌生IP开放。无查询参数，多传返回400 invalid_param，返回禁止缓存。

| 接口 | 检查什么 | 成功结果 |
|---|---|---|
| GET /api/health | 后端进程能处理请求；不依赖数据库 | HTTP 200 |
| GET /api/ready | 数据库可连接、目标表齐全，首次初始化的服装、饰品两个项目存在 | HTTP 200；连接失败、未配置或初始化不完整时503 service_unavailable |

成功内容分别为：
```json
{"status":"ok","data":{"service":"bumbum","state":"running"}}
```
```json
{"status":"ok","data":{"database":"ready"}}
```
不返回数据库地址、密码、SQL 或异常详情。ready检查表清单、初始项目、芯片项目可空所需的字段与约束版本，以及登记来源列的类型、默认值和不可空定义；旧库未升级返回503，不自动改表，也不逐列比对全部数据库结构。不代表全部业务功能已实现或生产可用。不存在的路径返回 JSON 404 not_found；请求方式错误返回 JSON 405 method_not_allowed；意外故障返回 JSON 500 internal_error。

## 1. 登记芯片、验证触碰和绑定手机号

### 1.1 POST /api/webhook/admin/scan：登记芯片（第一阶段）

供NFC.cool扫描后调用，已验收并合入main；cece已通过“批量预写固定文本→批量读卡自动回调”验收，6枚卡后台可查、全部重扫无重复；批量读取自动保存，无需逐张点保存。开启随机UID时的4字节编号仍拒绝，不从content中的SUN参数临时解密登记。只接受identifier、content、date，不从手机接收project或batch_no；新记录一律未分配项目。请求为JSON，最多8192字节。identifier必填，沿用手动登记的7字节UID规则，保存为冒号分隔大写十六进制；content可省略，提供时为最多4096字符的文字；date可省略，提供时为最多64字符且含时区的ISO 8601时间文字，不用于信任排序。content/date不存入业务数据库、不写日常日志；临时监听已移除。后台按入口写入首次registration_source=nfc_cool，不接受客户端指定或覆盖来源。不接受兼容模式的NoIdentifierInCompatibilityMode或QR产生的UUID：
```json
{"identifier":"04:A2:7F:1B:5E:80:00","content":"https://nfc.bumbum.cc/tap?picc_data=...&cmac=...","date":"2026-10-23T08:00:00Z"}
```
使用HTTPS Basic认证：用户名为WEBHOOK_ADMIN_USERNAME指定的已有管理员，密码为独立WEBHOOK_SHARED_SECRET。不使用登录密码、Cookie或网页防冒用口令；管理员须启用且已完成验证器设置。初次缺少Authorization或认证失败返回401，并带`WWW-Authenticate: Basic realm="bumbum-scan"`，让App按官方方式携带凭证重发。真实手机已观察到先401再携带Basic凭证返回200，不把这次认证重发当作业务失败自动重试。

保存成功后才返回成功；新增和admin_audit操作记录一起保存，归属凭证对应的管理员，来源为nfc_cool。重复UID返回原编号和is_new=false，不分配、清空或覆盖任何原资料，也不重复记录新增操作；并发同样处理。失败提示人工重扫，不在数据库保存前先报成功，不把content中的动态参数当认证状态。
```json
{"status":"ok","data":{"chip_uid":"04:A2:7F:1B:5E:80:00","is_new":true}}
```
参数错误仍用400 invalid_param，message说明UID须为7字节真实编号、content类型/长度或date格式的具体要求；不会通过放宽规则接收随机标识。错误：400 invalid_param、401 webhook_auth_failed、503 service_unavailable；香港Nginx对同IP平均每秒5次、突发最多额外10次，超限429 rate_limited。本机直接运行Flask不含该频率限制。额外字段先拒绝，实测App如有新字段先改契约。官方说明无网络/非成功响应时不会自动排队重试，需在App查看失败记录并人工重扫。部署及真实卡限制见[技术说明第2.5节](TECH_SPEC.md#25-手机扫描后自动登记)。

<a name="12-post-apitapverify核验这次触碰第二阶段待实测"></a>

### 1.2 POST /api/tap/verify：核验这次触碰

本小步产品及交互规则见[PRD第4.2.1节](PRD.md#421-本小步触碰验证后端)，技术方案及升级规则见[附录第15节](docs/IMPLEMENTATION_DETAILS.md#15-触碰验证后端技术方案待审核)。共用验证覆盖服装和饰品，工作台全项目统计另按[产品规则](PRD.md#422-工作台有效触碰统计)独立交付；工作台统计查询已接入，见第8节；饰品独立详情、短信与认领接口仍未接入。

只提交picc_data（加密芯片信息，32位十六进制）、cmac（防伪码，16位十六进制）；不增加项目、UID、版本、查找码或item_uid。现有测试卡与配置确认已核对该编码，用户验证入口按附录第15节实现，后台配置核验不替代用户验证、真实卡或公网验收：
```json
{"picc_data":"FDE4AFA99B5C820A2C1BB0F1C792D0EB","cmac":"C48B89C17A233B2C"}
```
服务器按技术规格第 5.1 节：全局 K1 先解出候选编号 → 查库核对项目和配置版本 → 用独立 K2 按 SDM 规则核对防伪码 → 唯一完整通过后确认身份 → 检查状态并一起保存新读数、日志和临时凭证。

不能只看“解密没报错”或“像十六进制编号”。多个版本都完整通过是配置异常，500 internal_error；普通服务故障 503，未开放 501，请求过密429 rate_limited，默认每IP每分钟60次，返回Retry-After秒数，阈值上线前实测。旧链接重试提示重新触碰；失败不能更新读数或发凭证，也不能把系统故障说成假货。

成功返回 verified、project、item_id/item_uid、owner_bound（是否已有所有者）、tap_token、expires_in=300 秒、item_detail（物品资料）。服装含资料字段、trace 数组、story 对象或 null、channel 数组；饰品含 name/description/material/meaning/image_urls。不返回 UID、读数、订单号、手机号或“当前用户养成进度”：
```json
{"status":"ok","data":{"verified":true,"project":"fashion","item_id":12,"item_uid":"FASH-2026-000012","owner_bound":false,"tap_token":"t_example","expires_in":300,"item_detail":{"name":"外套","description":null,"material":null,"care_instructions":null,"size_chart":null,"image_urls":[],"trace":[],"story":null,"channel":[]}}}
```
业务验证失败不发 token：
```json
{"status":"ok","data":{"verified":false,"reason":"cmac_fail","message":"防伪验证未通过"}}
```
本小步服装trace/channel返回[]、story返回null，扩展资料的公开字段在后续维护入口确定时补充。达到三字节计数上限返回not_ready，不清零；所有业务失败不增加有效触碰次数。

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

使用一个表单提交账号、密码和手机 Authenticator 的验证码。TOTP 是这类通常每 30 秒更新的 6 位验证码。账号创建和验证器设置由受控服务器命令完成，不开放网页注册、设置或恢复接口。

### 2.1 POST /api/admin/auth/login：一次完成登录

三个认证接口均不接受查询参数。登录和退出请求体最多 8192 字节，超出返回 400 invalid_param。

必填 username（1–64 字符）、password（1–128 字符，按原值验证，不去掉首尾空格）、code（恰好 6 位数字的文字，保留开头的零）。只接受 JSON，并检查 Origin，不需要先有登录 Cookie 或防冒用口令；这些内容都不放链接或日志：
```json
{"username":"cece","password":"example-only","code":"012345"}
```
账号启用、验证器已设置、密码和验证码都通过后，创建最长 8 小时的登录并设置 bumbum_admin_session Cookie，不返回 Cookie 值或临时登录票据：
```json
{"status":"ok","data":{"authenticated":true,"expires_in":28800}}
```
随后调用 session 取得本次登录的防冒用口令，才能修改数据。重登成功会生成新凭证并撤销浏览器携带的旧会话。相同时段验证码只能成功使用一次；重登应等待下一组有效验证码。

账号不存在、禁用、验证器没设置、密码或验证码错误、验证码已使用，都统一返回 401 unauthorized。连续 5 次失败锁 15 分钟；按 IP 的登录频率另由 Nginx 限制；两者都返回 429 rate_limited。字段格式错误 400 invalid_param，来源不符 403 forbidden，保存失败 503 service_unavailable；失败时不签发新登录 Cookie。详细计数与保存规则见技术附录第 4、5 节。

### 2.2 GET /api/admin/auth/session：查询本次登录

需要有效 Cookie 和启用且已设置验证器的账号。返回到期时间和本次登录已有的随机防冒用口令，不返回 Cookie 值，不缓存，不换口令或延长登录：
```json
{"status":"ok","data":{"authenticated":true,"expires_at":"2026-10-23T16:00:00Z","csrf_token":"c_example"}}
```
示例口令只是占位内容，实际是独立随机生成的 64 位小写十六进制文字。页面在内存中保存，写请求放 X-CSRF-Token，不能长期保存在浏览器。无效或过期登录返回 401 unauthorized。

### 2.3 POST /api/admin/auth/logout：退出

有效 Cookie 加防冒用口令，检查 Origin，请求体 `{}`。撤销当前登录并清除相同 Path 的 Cookie，返回 data.logged_out=true；失败时不伪报已退出。禁用账号或通过服务器重置验证器后，该账号全部旧登录立即失效。

原先的验证码单独验证、备份码验证和网页设置验证器接口不再属于当前方案。验证器丢失且无法迁移时，通过有权限的服务器操作重置，不能从网页跳过验证码。

## 3. 管理芯片（第一阶段）

均须完整登录，写请求加防冒用口令。ChipView 是芯片摘要：id、chip_uid、project（fashion/jewelry或null，null显示“未分配”）、chip_status、item_id/item_uid（可空）、batch_no（可空）、registration_source（manual网页手工／nfc_cool手机扫描／unknown历史未知）、provisioned_at（可空）、keys_generated（是否有密钥）、created_at、updated_at；不展示密钥、密文或读数。

| 要做什么及接口 | 要给什么 | 成功返回的 data |
|---|---|---|
| 手动登记：POST /api/admin/chips | chip_uid必填；project、batch_no可选，空时省略或传null | chip：ChipView、is_new：是否新登记 |
| 查列表：GET /api/admin/chips | page/page_size、project、status、keyword 可选，keyword 查 UID | 分页 ChipView |
| 查详情：GET /api/admin/chips/{id} | 芯片 id | ChipView，加 ownership：null 或 item_id/user_id/phone_masked/bound_at |
| 生成密钥：POST /api/admin/chips/{id}/generate-keys | `{}`，不接受 force | chip_id、generated=true、key_version |
| 查看密钥：POST /api/admin/chips/{id}/keys | confirm=true | chip_uid、keys、sun_url_template |
| 确认配置：POST /api/admin/chips/{id}/confirm-provisioning | readings：恰好两项的数组，各含picc_data/cmac；management_confirmed=true | 更新后的ChipView；不返回密钥或用户凭证 |
| 改状态：PATCH /api/admin/chips/{id}/status | chip_status | 更新后 ChipView |
| 绑定物品：POST /api/admin/chips/{id}/bind-item | item_id | 更新后 ChipView |
| 解除绑定：POST /api/admin/chips/{id}/unbind-item | `{}` | 更新后 ChipView |

当前手动登记、列表、首次绑定及三个密钥配置POST可用，表中详情、状态及解绑仍待实现。

绑定物品的页面与业务规则见[绑定PRD](PRD.md#414-本小步芯片绑定物品)，具体实现见[技术附录](docs/IMPLEMENTATION_DETAILS.md#13-芯片绑定物品实现)。人工验收和合并状态分别看TODO与CHANGELOG；本节不因按钮出现就宣称所有管理能力已开放。

手动登记仅接受上述三个JSON字段，请求体最多8192字节，不接收查询参数。UID接受14位连续十六进制或7组冒号格式，去首尾空白并统一为大写冒号格式；project为fashion/jewelry或null，省略同null，空字符串或unassigned不接受。批次去首尾空白后为1–64字符，空字符串不接受。新记录registration_source=manual，由后台设置，不接受请求指定；状态为pending，item_id、provisioned_at为空，keys_generated=false。
```json
{"chip_uid":"04a27f1b5e8010","project":null,"batch_no":"DEMO-01"}
```

返回HTTP200，data固定为chip和is_new。重复UID时is_new=false，返回原记录，项目、批次、状态、首次登记来源、绑定和原更新时间都不覆盖，也不新增变更审计；原项目为空时，本次即使传入项目也不分配，后续走物品绑定。原项目非空且本次明确选择另一个项目才返回409 project_mismatch，message为“该 UID 已登记，所属项目与本次选择不同。原记录未修改，请按 UID 查询。”。其余重复在页面提示“该 UID 已登记，已显示原记录，无需重复登记。”。首次登记与admin_audit一起保存；输入错误400、会话无效401、来源/口令不符403、数据库或审计失败503。登记不代表写卡完成或真伪验证通过。

列表只接受表中5项查询参数，不接受重复键。page为1–2147483647，page_size为1–100；project可为fashion/jewelry/unassigned，unassigned只作筛选值，表示project_id为空，省略表示全部；status沿用既定枚举。keyword最长128字符，匹配UID片段，忽略大小写及冒号，百分号和下划线按普通文字查找。按id倒序；空页仍返回items=[]及真实total，未分配芯片也计入全部列表。摘要不增加密钥密文、读取序号、手机号或订单信息。

密钥生成只接受空对象，要求项目已确定、芯片已绑定且状态bound、物品非归档；不符合409 invalid_state。已有密钥、配置完成或读数记录不能覆盖，409 already_exists；传force是400 invalid_param。keys只接受confirm=true（不能用1代替），返回K0–K4的32位大写十六进制值；K1是对应版本全局密钥的加密副本，不逐卡生成。查看前保存操作记录，返回no-store禁止缓存；芯片或密钥不存在404 not_found。页面须提醒K1涉及该版本所有芯片的秘密。配置/密文与当前目标密钥不符503 service_unavailable，不返回秘密，不自动重算或覆盖。URL模板见技术规格第5.1节。

confirm-provisioning请求例如：
```json
{"readings":[{"picc_data":"00000000000000000000000000000000","cmac":"0000000000000000"},{"picc_data":"11111111111111111111111111111111","cmac":"1111111111111111"}],"management_confirmed":true}
```
示例只是格式占位，不能验签。每条只接受32位picc_data、16位cmac十六进制文字；额外字段、非布尔确认或数组长度不符400 invalid_param。management_confirmed是管理员确认新K0认证及文件权限已经人工检查，不伪装为系统自动读回。固定AES/C7布局、目标UID和零长度MAC输入均须通过，否则400 verification_failed。不接受客户端密钥、项目或UID。第二条计数须大于第一条，已有基线时第一条也须更新；第二条达到最大计数16777215时拒绝，409 invalid_counter。已配置409 already_configured，不重配或重置计数。成功同事务保存provisioned_at、第二条计数基线及审计，返回ChipView；不返回计数、不发用户凭证、不自动启用物品。三个入口均沿用JSON/Origin/Cookie/CSRF及8192字节限制，存储故障503；未知提交结果须GET列表查询，不自动重发。实现见[技术附录第14节](docs/IMPLEMENTATION_DETAILS.md#14-测试卡密钥与配置方案)，批量导出及完整密钥管理页面另排期。

生成密钥不能猜项目，依赖bind-item在事务内确定项目及关联；已有项目必须匹配。后续解绑不清空项目，解绑仍未实现。

状态转换见技术规格第 2.2 节，不能任意跳转；重复绑定 409 already_bound、跨项目 409 project_mismatch、目标已有芯片 409 item_already_has_chip、非法状态 409 invalid_state。确认按钮不能代替权限或防冒用检查。

<a name="31-绑定物品接口细化待技术方案审核"></a>

### 3.1 绑定物品接口

本节定义首次绑定接口。事务、审计、前端及测试规则集中在[技术附录第13节](docs/IMPLEMENTATION_DETAILS.md#13-芯片绑定物品实现)；所有权、解绑与换绑不属于该入口。

POST /api/admin/chips/{id}/bind-item，必须已有完整管理员会话，通过Origin与CSRF检查；不接收查询参数，只接受JSON对象及唯一必填字段item_id。

```json
{"item_id":23}
```

id与item_id范围1至18446744073709551615；item_id严格为JSON整数，字符串、bool、浮点数、null、数组及多余字段拒绝。数字路径匹配后，0或超过上限返回400；负数、小数和非数字路径不匹配，沿用404。输入、方法与凭证优先级沿用现有管理入口，不新增认证流程。请求体使用既有8192字节应用限制，不单独放宽网关。

成功HTTP 200，返回status=ok及data=完整ChipView，结构沿用本节定义，不新包chip/is_new。芯片项目按目标物品确定或保持原同项目，状态为bound，item_id/item_uid为目标；不改变原登记来源、批次、密钥及写卡/读数记录，也不修改物品身份、资料、状态或更新时间。

| HTTP／code | 触发条件 |
|---|---|
| 400 invalid_param | ID类型/范围、必填/未知字段、应用请求体限制、额外查询参数等不符合约定 |
| 401 unauthorized | 管理员会话无效、撤销、过期或事务内重查失败 |
| 403 forbidden／csrf_failed | 复用现有访问来源或防冒用校验失败 |
| 404 not_found | 匹配路由后芯片或目标物品不存在；不匹配路径仍走既有404 |
| 409 invalid_state | 芯片disabled/lost，或物品archived |
| 409 already_bound | 芯片已绑定，包括重复绑定同一目标；不覆盖或重复记录成功变更 |
| 409 project_mismatch | 芯片已有项目与物品不一致 |
| 409 item_already_has_chip | 目标物品已关联另一芯片，包括对方disabled/lost；或UPDATE时命中绑定唯一约束 |
| 503 service_unavailable | 数据库、锁等待/死锁、审计或提交故障；沿用脱敏错误编号，不自动重发 |

确认记录均存在后，业务检查依次为芯片状态/已有绑定、物品归档、项目匹配、目标占用；只允许pending且未关联的芯片。物品draft/active/disabled均可绑定，不要求资料完整，不自动启用。先锁物品后锁芯片，两个记录均不存在时先报告目标物品不存在；不要从多个业务错误中随机挑提示。

参数和业务拒绝不保存变更。提交阶段的故障可能导致已保存但未收到回执，500/503/超时不能统一解释为未保存。页面复用GET /api/admin/chips按完整UID查询，核对id、item_id及chip_status；不另开放GET芯片详情，不返回成功后自动调用写卡、所有权或其他业务。

## 4. 管理物品

ItemView 是物品摘要：id、project、item_uid、sku_code（款式编号）、status、created_at、updated_at、profile（对应项目的资料，没有为 null）；不额外返回 profile 内部 id/item_id。

第一阶段均须完整登录，写请求加防冒用口令：

| 要做什么及接口 | 要给什么 | 成功返回的 data |
|---|---|---|
| 查列表：GET /api/admin/items | page/page_size、project、status、keyword、unbound_only 可选，keyword 查编号/sku_code | 分页 ItemView |
| 创建：POST /api/admin/items | project、item_uid 必填，sku_code 可空；status 省略或仅 draft | 新 ItemView，profile=null |
| 查详情：GET /api/admin/items/{id} | 物品 id | ItemView |
| 改部分字段：PATCH /api/admin/items/{id} | 当前仅status必填：active/disabled；仅服装，不允许sku_code或其他字段 | 更新后 ItemView |
| 查资料：GET /api/admin/items/{id}/profile（预留未实现，当前使用详情） | 物品 id | profile 或 null |
| 整份存资料：PUT /api/admin/items/{id}/profile | 当前仅服装的name/description/material/care_instructions/image_urls | 保存后的 profile |

| 项目 | 资料字段 |
|---|---|
| fashion（服装） | name（名称）必填，1–128字符；description最多4000、material最多256、care_instructions最多2000，可空；image_urls为URL数组，省略为[]；size_chart仅保留既有返回，本次不展示、不接收、不更新 |
| jewelry（饰品） | name（名称）必填，1–128 字符；description（介绍）、material（材质）、meaning（寓意）可空；image_urls（图片地址）同上 |

PUT只整份替换本次五个可编辑字段，省略可选字段清为null/[]；空白文字归一为null。size_chart不接收，不清空已有值；JSON返回仍沿用既有ItemView结构。长度按去首尾空白后的Unicode字符数计算。图片只用完整http/https，不含账号密码、空白、控制字符或反斜杠，最多20项，每项2048字符；保留顺序，后端不下载。项目/物品编号不可改，款式修改、归档、饰品资料保存均未开放。启用要求有效服装名称，draft/disabled→active，active→disabled；相同状态幂等，不重复状态审计；归档写入409 invalid_state。

GET/POST /api/admin/items已由cece验收并合入main。当前GET详情支持两项目、无资料返回profile=null；PATCH状态与PUT资料仅服装，饰品409 project_mismatch，物品不存在404 not_found。PUT最多262144字节；其余入口仍8192字节，未知字段/查询参数及超限400 invalid_param。PUT与PATCH返回HTTP200，复用登录/Origin/CSRF；写事务先重查管理员/会话，再锁物品，保存业务、item.updated_at及审计一起提交。动作item.profile.save或item.status.change，目标为item ID，detail仅项目及状态前后值，不复制正文；DB/审计失败503并回滚。创建的详细编号格式以[PRD物品草稿规则](PRD.md#411-本小步物品草稿创建与列表)为准：去首尾空白后匹配ASCII `FASH-[0-9]{4}-[0-9]{6}` 或 `JEW-[0-9]{4}-[0-9]{6}`，前缀匹配项目；不接受小写或Unicode数字，允许0000/000000，不自动编号。sku_code省略/null/空字符串及纯空白均存NULL，否则须为去首尾空白后最多64字符的文字；这是本字段的明确空字符串例外。status省略或仅draft，拒绝未知字段及网址参数，请求体最多8192字节。创建返回HTTP200的ItemView，profile=null；重复409 already_exists，原记录不变。

列表只接受page/page_size/project/status/keyword/unbound_only，不接受重复参数；page为1–2147483647，page_size为1–100，默认20。project仅fashion/jewelry，status为draft/active/disabled/archived，省略表示全部。unbound_only仅接受小写文字true/false，其他值或重复400 invalid_param；省略/false保持普通列表，true排除关联任何芯片的物品，包含其芯片为disabled/lost的情况。先过滤后计算total及分页，不改变既有物品状态筛选或ItemView。绑定弹窗固定传true，普通管理列表不传；查询不预占，最终绑定事务仍重查占用。keyword原始长度最多128字符，去首尾空白后对编号或sku_code作包含式模糊查询，按数据库既有排序规则匹配，%和_按普通文字处理；按id倒序，空页保留真实total。ItemView的profile从对应项目资料表组装，没有记录为null，不是item表字段；已有资料不能伪报为null。失败统一status=error/code/message，适用第7节错误码，不伪造空列表。

第三阶段的下列接口仅服装物品可用，否则 409 project_mismatch；未细化开放前 501 feature_not_ready。完整登录，写请求加防冒用口令；PUT 整份替换，数组最多 100 项：

| 接口 | PUT 要给什么 | GET/PUT 返回 |
|---|---|---|
| 溯源记录：GET/PUT /api/admin/items/{id}/trace | 数组：stage 必填，event_time/location/operator/detail 可空，sort_order 默认 0 | trace 数组，空时 [] |
| 品牌故事：GET/PUT /api/admin/items/{id}/story | 对象：title/content/media_urls 可空，sort_order 默认 0 | story 对象，空时 null |
| 购买渠道：GET/PUT /api/admin/items/{id}/channel | 数组：channel_type 必填，channel_name/order_no/purchased_at 可空 | channel 数组，空时 [] |

stage/channel_type 取值和长度按 schema；返回包含记录 id、上述字段，不重复 item_id。购买渠道 channel 始终为数组；用户端去掉订单号和个人交易信息。

## 5. 管理所有权（第一阶段）

完整登录，写请求加防冒用口令。OwnershipView 是绑定记录：id、item_id、item_uid、user_id、phone_masked（隐藏部分数字的手机号）、bound_at、unbound_at、is_active、bind_source。列表不展示完整手机号；输入手机号按 1.3 节，note 可空且最长 256。

| 要做什么及接口 | 要给什么 | 成功返回的 data |
|---|---|---|
| 查列表：GET /api/admin/ownerships | page/page_size、item_id、user_phone（手机号前缀）、is_active=0/1 可选 | 分页 OwnershipView |
| 绑定：POST /api/admin/ownerships | item_id、phone 必填，note 可选 | 新 OwnershipView |
| 解绑：POST /api/admin/ownerships/{id}/unbind | note 可选 | 关闭后的旧 OwnershipView |
| 转赠：POST /api/admin/ownerships/{id}/transfer | to_phone 必填，note 可选 | 新 OwnershipView |

只给非归档物品绑定；已有主人 409 already_bound。管理员绑定写 ownership.bind_source=admin 和 history(action=bind, from_user_id=null, to_user_id=用户)，history 没有 bind_source。

解绑/转赠只操作当前有效记录，否则 409 invalid_state；转给原主人为 409 already_bound，不造新历史。转赠关闭旧绑定、创建新绑定（来源 admin），只写一条 transfer 历史，保存 from/to 用户；绑定、历史、操作记录一起成功。日志和操作记录不保存完整手机号。

## 6. 用户看详情和饰品养成

服装详情GET已接入；饰品详情GET仍预留。下列GET要带X-Tap-Token，核对其对应物品和当前状态，读取不消耗凭证；跨项目 409 project_mismatch，凭证无效/过期/已用掉或不匹配 403 invalid_tap_token：

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
| 401 | unauthorized | 登录检查失败（不细分哪项错误），或本次登录已失效 |
| 401 | webhook_auth_failed | 扫描回调的身份检查失败 |
| 403 | forbidden | 请求网页或操作权限不允许 |
| 403 | csrf_failed | 防冒用口令不正确 |
| 403 | invalid_tap_token | 临时凭证无效、过期、已用掉或不适用于本物品/操作 |
| 404 | not_found | 地址、资源或密钥记录不存在 |
| 405 | method_not_allowed | 此地址不支持该请求方式 |
| 409 | already_exists | UID/物品标识/密钥等已存在 |
| 409 | already_bound | 已绑定或重复绑定不允许 |
| 409 | item_already_has_chip | 物品已绑定其他芯片 |
| 409 | project_mismatch | 芯片/物品/业务类型不匹配 |
| 409 | invalid_state | 当前状态不允许此动作 |
| 429 | rate_limited | 请求太频繁，或登录尝试被暂时锁定 |
| 429 | sms_rate_limited | 短信发送过于频繁 |
| 501 | feature_not_ready | 功能还没开放，或前置设计/测试未完成 |
| 503 | service_unavailable | 数据库或外部依赖不可用 |
| 500 | internal_error | 程序内部异常；不给用户展示代码、SQL或秘密 |


管理接口共同使用第 0 节检查和上述 400/401/403/404/409/429/500/503；按实际原因返回，不泄露程序堆栈、SQL 或秘密。

<a name="8-工作台有效触碰统计技术方案待审核未实现"></a>

## 8. 工作台有效触碰统计

本节定义已接入的查询契约，人工验收及分支状态以TODO为准；页面行为见[PRD第4.2.2节](PRD.md#422-工作台有效触碰统计)，统计与实现细节见[技术附录第16节](docs/IMPLEMENTATION_DETAILS.md#16-工作台有效触碰统计技术方案待审核)。

### 8.1 GET /api/admin/stats/taps

完整管理员登录，沿用管理Origin、Cookie及会话检查。只读GET不要求写操作CSRF，不需要tap_token，也不因查询新增审计或触碰次数。只接受下列参数，未知或重复参数均400 invalid_param：

| 参数 | 规则 |
|---|---|
| project | 省略为全部；仅fashion/jewelry，按code查项目，不接收数字ID、all或空字符串 |
| range | 省略为7d；仅7d、30d、all |
| q | 省略或空白为无关键词；原始文字最多128字符，再去首尾空白；仅筛选明细的当前物品编号或名称，百分号和下划线按普通文字匹配 |
| page | 默认1；1–2147483647的十进制正整数，不接受符号、小数或Unicode数字 |
| page_size | 默认20；1–100的十进制正整数；本期页面固定20，不提供调整入口 |

HTTP200 data的结构如下。示例为虚构的同一天累计数据，不是真实统计：

```json
{
  "status": "ok",
  "data": {
    "filters": {"project": "fashion", "range": "all", "q": ""},
    "timezone": "Asia/Shanghai",
    "as_of": "2026-10-27T04:00:00.000000Z",
    "period": {"from_date": "2026-10-27", "to_date": "2026-10-27"},
    "first_recorded_at": "2026-10-27T03:00:00Z",
    "summary": {"valid_taps": 2, "touched_items": 1},
    "daily": [{"date": "2026-10-27", "valid_taps": 2}],
    "items": [{"project": "fashion", "item_uid": "FASH-2026-000001", "name": "示例外套", "valid_taps": 2, "last_tap_at": "2026-10-27T03:05:00Z"}],
    "total_items": 1,
    "page": 1,
    "page_size": 20,
    "total_pages": 1,
    "page_adjusted": false
  }
}
```

- filters回显服务器规范化的实际条件，project为null表示全部；as_of为本次查询截点，完整时间均为UTC Z，页面统一转北京时间。period的日期及daily.date本身已是北京时间日期，不当作浏览器本地时区再次换日。
- 7d/30d含今天，分别返回7/30个按日期升序、缺日补0的daily点。all从所选项目首条有效记录所在日到今天；从未有记录时from_date=null、daily=[]，to_date仍为查询当天。
- first_recorded_at是所选项目在本次快照内、截至as_of的首条有效记录时间，不受range或q影响；从未有记录为null，不称系统上线时间或交付时间。
- summary和daily只按project/range统计，不受q或分页影响。items只含本范围发生过有效触碰的物品；名称来自当前对应项目资料，没有或空白为null，前端显示“未填写”。不返回内部物品ID、芯片UID、读取计数器、单次动态参数、密钥、手机号或凭证。
- items按valid_taps倒序、last_tap_at倒序、item_uid升序；以发生时项目/物品聚合，停用、归档不排除历史。q只影响items及total_items/total_pages，不因关键词无结果把summary清零。
- total_items是关键词筛选后的物品数，不是事件次数。page超出实际末页时，在同一次快照内调整到末页并设page_adjusted=true，不要求前端再发请求。无明细时items=[]、total_items=0、total_pages=0、page=1；请求原本不是1时page_adjusted=true。
- 各次数、条数和分页值是非负JSON整数，前端必须检查为安全整数再显示，不能四舍五入或用精度丢失的数字充当真实统计。响应各模块必须同时有效，缺字段或格式不符按异常响应处理，不用默认0掩盖。

无登录/会话失效401 unauthorized；不允许的管理来源403 forbidden；参数错误400 invalid_param；数据库不可用、旧库日志结构未就绪503 service_unavailable，故障按已有脱敏规则附error_id；程序错误500 internal_error。失败不返回部分成功数据，不能转成HTTP200空统计。统一Cache-Control:no-store，GET可人工安全重试，不扩大现有跨域来源。

<a name="9-手机页持续查看接口提案待审核"></a>

## 9. 手机页持续查看

本节定义已在功能分支 `feat/mobile-tap-view` 实现的持续查看契约；该接口尚未合入 `main`。实现细节见[技术附录第17节](docs/IMPLEMENTATION_DETAILS.md#17-手机触碰资料页与公网链路技术方案待审核)，软件检查、人工验收与部署状态分别见 TODO 和 CHANGELOG。产品范围及自动更新见[PRD第4.2.4节](PRD.md#424-本小步手机触碰验证与服装资料页)。旧调用不发 view 资格，原五分钟 read/bind 行为保留。

### 9.1 POST /api/tap/verify的可选浏览器模式

在原picc_data/cmac之外可增加browser_view，可省略或为布尔值；省略/false保持现有五分钟凭证和不发查看Cookie的行为。true须Origin精确匹配PUBLIC_ORIGIN，否则403 forbidden；其他字段/类型仍400。现有限流、错误和单次读数接受规则不变。

服装验证通过时同一事务额外发view资格，生产响应设置bumbum_item_view Cookie：HttpOnly、Secure、SameSite=Strict、Path=/api/tap/items/{item_id}，无Domain、无持久Max-Age；仅明确的本机开发HTTP关闭Secure。Cookie原值不放JSON，数据库只存摘要。JSON沿用原成功字段，并增加固定构造的view_path=/tap/items/{item_id}及verified_at/retrieved_at（ISO 8601 UTC），供手机路由和显示时间。tap_token仍五分钟，不当作持续查看凭证；view资格不消费或扩展原短时权限。

业务失败、服务错误和饰品响应不发服装查看Cookie；饰品仍可返回原验证结果，页面显示当前类别暂不支持。不能因为以前有查看Cookie就跳过新的动态读数验证。验证响应丢失不得自动重放；需要新碰卡，已成功事件不回退。

### 9.2 GET /api/tap/items/{id}/view

id为正整数；不接受任何查询参数、请求正文或X-Tap-Token代替Cookie。仅核对对应物品路径的唯一bumbum_item_view Cookie及数据库view类型，不接受read/bind。来源/跨站规则见技术附录；同源Cookie请求，不向管理端或其他网站放开CORS。

成功HTTP 200，返回下列白名单。project始终为fashion，profile只含name/description/material/care_instructions/image_urls；不返回所有权、尺码表、内部芯片信息或未维护扩展资料。verified_at是最近发放该view的真实验证时间，retrieved_at是本次服务器读取时间，不相互替代。

```json
{"status":"ok","data":{"project":"fashion","item_id":12,"item_uid":"FASH-2026-000012","verified_at":"2026-10-27T02:23:00Z","retrieved_at":"2026-10-27T02:31:00Z","profile":{"name":"外套","description":null,"material":"棉","care_instructions":null,"image_urls":[]}}}
```

view为连续24小时无成功查询失效，成功查询滑动续期24小时；原创建时间不变，失败不续期。每次查询重查物品、芯片、原关联和当前配置；不写scan_log/admin_audit，不推进读取计数、不计触碰。原GET /api/fashion/items/{id}/detail继续仅接受五分钟read/bind，不能使用view。

| 响应 | 含义和页面行为 |
|---|---|
| 400 invalid_param | 编号或额外输入不合法，不返回资料 |
| 403 invalid_view_session | Cookie缺失/不合法、非view、过期或撤销；停止自动更新、隐藏资料并提示重新触碰 |
| 403 forbidden | 来源不合法，不返回资料 |
| 409 view_unavailable | 芯片/物品停用、归档、未就绪、原关联改变等当前不可查看；隐藏资料、停止查询，不判定假货 |
| 409 project_mismatch | 不是本期服装查看资格，明确项目暂不支持 |
| 429 rate_limited | 公网查看限频，包含Retry-After；不影响触碰计数，等待后才再查 |
| 503 service_unavailable | 结构/配置/数据库不可用，可能附脱敏error_id；保留上次内容时标旧，不把故障当停用或假货 |
| 500 internal_error | 意外异常，附可用error_id；无资料假成功 |

所有资料响应no-store。GET失败不发清除Cookie指令，避免旧失败响应覆盖新资格；浏览器依据响应停止或退避，Cookie保留不代表后端仍授权。错误文案按“读取资料”场景，不能把可重试查询故障统一提示为重新触碰。未注册/未开放接口仍按当前实现返回404，不把文档中后续需求伪装为已接入。
