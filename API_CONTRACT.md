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

当前已实现：两个运行检查接口，管理员login/session/logout，GET/POST /api/admin/chips，扫描回调，GET/POST /api/admin/items，GET/PATCH /api/admin/items/{id}及PUT /api/admin/items/{id}/profile。物品资料与启停只开放服装，具体限制见第4节。其余未注册地址返回404；已注册地址使用不支持的方法返回405，例如独立GET /api/admin/items/{id}/profile未开放，应使用物品详情接口。扫描配置缺失或不合法时返回503，不允许空密码访问。后续已接入路由但未开放的业务使用501，不伪造成功。本文其余预留接口不表示已实现；任务进度与验收证据分别在TODO和CHANGELOG维护。

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
| 改状态：PATCH /api/admin/chips/{id}/status | chip_status | 更新后 ChipView |
| 绑定物品：POST /api/admin/chips/{id}/bind-item | item_id | 更新后 ChipView |
| 解除绑定：POST /api/admin/chips/{id}/unbind-item | `{}` | 更新后 ChipView |

当前仅手动登记和列表可用，表中其余接口仍待实现。

手动登记仅接受上述三个JSON字段，请求体最多8192字节，不接收查询参数。UID接受14位连续十六进制或7组冒号格式，去首尾空白并统一为大写冒号格式；project为fashion/jewelry或null，省略同null，空字符串或unassigned不接受。批次去首尾空白后为1–64字符，空字符串不接受。新记录registration_source=manual，由后台设置，不接受请求指定；状态为pending，item_id、provisioned_at为空，keys_generated=false。
```json
{"chip_uid":"04a27f1b5e8010","project":null,"batch_no":"DEMO-01"}
```

返回HTTP200，data固定为chip和is_new。重复UID时is_new=false，返回原记录，项目、批次、状态、首次登记来源、绑定和原更新时间都不覆盖，也不新增变更审计；原项目为空时，本次即使传入项目也不分配，后续走物品绑定。原项目非空且本次明确选择另一个项目才返回409 project_mismatch，message为“该 UID 已登记，所属项目与本次选择不同。原记录未修改，请按 UID 查询。”。其余重复在页面提示“该 UID 已登记，已显示原记录，无需重复登记。”。首次登记与admin_audit一起保存；输入错误400、会话无效401、来源/口令不符403、数据库或审计失败503。登记不代表写卡完成或真伪验证通过。

列表只接受表中5项查询参数，不接受重复键。page为1–2147483647，page_size为1–100；project可为fashion/jewelry/unassigned，unassigned只作筛选值，表示project_id为空，省略表示全部；status沿用既定枚举。keyword最长128字符，匹配UID片段，忽略大小写及冒号，百分号和下划线按普通文字查找。按id倒序；空页仍返回items=[]及真实total，未分配芯片也计入全部列表。摘要不增加密钥密文、读取序号、手机号或订单信息。

密钥功能等实际计算规则、权限和测试完成后才开放，否则 501 feature_not_ready。已有密钥不能覆盖，409 already_exists；传 force 是 400 invalid_param。keys 含 K0–K4 的 32 位十六进制值；K1 是对应版本全局密钥的加密副本，不逐卡生成。查看前确认并保存操作记录，返回 no-store 禁止缓存；不存在为 404 not_found。页面须提醒：查看 K1 涉及该版本所有芯片的秘密，不仅是这一枚。URL 模板见技术规格第 5.1 节。

后续生成密钥接口开放后，项目未分配时返回409 invalid_state，不能猜项目或计算密钥。后续bind-item在事务内：未分配芯片按物品确定项目再绑定；已有项目必须匹配；项目确定、绑定及审计一起保存。解绑不清空项目；当前这些接口仍未实现。

状态转换见技术规格第 2.2 节，不能任意跳转；重复绑定 409 already_bound、跨项目 409 project_mismatch、目标已有芯片 409 item_already_has_chip、非法状态 409 invalid_state。确认按钮不能代替权限或防冒用检查。

## 4. 管理物品

ItemView 是物品摘要：id、project、item_uid、sku_code（款式编号）、status、created_at、updated_at、profile（对应项目的资料，没有为 null）；不额外返回 profile 内部 id/item_id。

第一阶段均须完整登录，写请求加防冒用口令：

| 要做什么及接口 | 要给什么 | 成功返回的 data |
|---|---|---|
| 查列表：GET /api/admin/items | page/page_size、project、status、keyword 可选，keyword 查编号/sku_code | 分页 ItemView |
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

列表只接受page/page_size/project/status/keyword，不接受重复参数；page为1–2147483647，page_size为1–100，默认20。project仅fashion/jewelry，status为draft/active/disabled/archived，省略表示全部。keyword原始长度最多128字符，去首尾空白后对编号或sku_code作包含式模糊查询，按数据库既有排序规则匹配，%和_按普通文字处理；按id倒序，空页保留真实total。ItemView的profile从对应项目资料表组装，没有记录为null，不是item表字段；已有资料不能伪报为null。失败统一status=error/code/message，适用第7节错误码，不伪造空列表。

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
