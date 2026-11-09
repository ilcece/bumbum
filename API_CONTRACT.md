# BUMBUM 接口说明：页面要给什么，后台会返回什么

当前分支按已确认原型构建正式数字档案服务，新增接口见第11节；人工验收与环境部署另计。实现范围以[第0.4节](#04-当前能做到哪一步)为准，预留首次认领接口不等于交付，既有首次绑定接口不能用于换新。

**接口**就是网页和后端约定的办事入口，例如“登记芯片”“绑定手机号”。本文定义地址、字段和返回；业务看[PRD](PRD.md)，流程看[TECH_SPEC](TECH_SPEC.md)，精确安全参数看[技术附录](docs/IMPLEMENTATION_DETAILS.md)，任务和历史分别见[TODO](TODO.md)、[CHANGELOG](CHANGELOG.md)。

阅读方式：先找想做的事，再看要提供的字段和返回结果。字段名保留原样供 AI 写代码；示例密码、token 都是占位内容，不是真实凭证。GET 表示读取，POST 表示提交操作，PATCH 改指定字段，PUT 整份替换。

## 0. 每个接口都遵守的规则

### 0.1 地址和字段

管理端Umi使用同源/api；用户端原VITE_API_BASE_URL仍含/api。调用时只补后面的部分，不能重复拼出/api/api。

| 环境 | 基础地址 | 补上的部分 | 最终请求 |
|---|---|---|---|
| 本机开发 | /api | /health | http://localhost:5174/api/health（Umi开发代理转给5000端口） |
| 杭州测试管理端（域名可用性另验收） | /api | /admin/chips | https://test.bumbum.cc/api/admin/chips（部署后） |
| 生产管理端 | /api | /admin/chips | https://admin.bumbum.cc/api/admin/chips |
| 生产用户端 | /api | /tap/verify | https://nfc.bumbum.cc/api/tap/verify |

提交内容默认用JSON，标明Content-Type:application/json；图片上传例外仅为第11.3节声明的精确multipart/form-data入口。只接受声明过的字段；多传、漏传必填或格式不对，返回 400 invalid_param。id 是正整数，项目只用 fashion/jewelry；时间为 ISO 8601 UTC。可空字段用 null，不拿空字符串代替；长度不超过 [schema](db/schema.sql)，必填文本不能只有空格。

列表每页默认 20 条：page 从 1 开始，page_size 最多 100，keyword 最长 128 字符。开发管理网页只能用 ADMIN_ORIGIN，浏览器须允许携带登录 Cookie（credentials）；生产同域调用。不把用户网页加入管理端允许来源，详见技术规格第 4、6 节。

### 0.2 怎么看返回结果

成功看 status=ok 和 data 中的结果；失败看 code 和给人看的 message：
```json
{"status":"ok","data":{"id":12}}
```
```json
{"status":"error","code":"invalid_param","message":"参数不合法"}
```
列表data包含items、total、page、page_size；芯片/物品扩展查询另返回total_pages/page_adjusted，具体见对应节。空列表items=[]。创建成功也返回 HTTP 200，保留已有约定。仅芯片验证的业务失败允许 200 加 verified=false；参数错误、系统故障、功能没开放使用对应错误状态，不能假装正常。

对非预期500及数据库异常503增加可选error_id：服务端生成24位小写十六进制错误编号，页面附在原通俗提示后供反馈。正常校验、重复、登录失败及未注册地址等不增加程序故障日志；不要求每个503都有编号。日志仅包含编号、UTC时间、方法、路由模板、异常类型及项目代码文件/行号，不包含请求/查询正文、认证信息、异常原文、SQL/参数、源代码或局部变量；数据库失败仍回滚。任务与部署状态见[TODO](TODO.md)。

### 0.3 哪些凭证要带上

| 场景 | 需要提供什么 |
|---|---|
| 管理业务 | 浏览器自动携带 bumbum_admin_session Cookie（登录凭证）；必须已通过密码和验证码且账号启用 |
| 修改管理数据 | 另带 X-CSRF-Token（页面取得的防冒用口令），并检查请求来自允许的管理网页；不直接把它写成用户手填项 |
| 登录 | 一次提交账号、密码和验证码；强制检查网页来源 Origin 和 JSON，不依赖现有登录凭证 |
| 扫描回调 | HTTPS Basic Auth：WEBHOOK_ADMIN_USERNAME 指定已有管理员名，WEBHOOK_SHARED_SECRET 作独立扫码密码；不把秘密放链接或日志 |
| 兼容详情接口 | 请求头 X-Tap-Token 放触碰后的临时凭证，沿用原五分钟规则 |
| 手机资料持续查看 | 浏览器自动携带持续查看Cookie，具体契约见第9节；不使用管理会话，也不要求用户手填凭证 |
| 用户账户及首次认领 | 短信验证建立独立用户会话。认领时在 JSON 中提交 `tap_token` 和交付认领码，见[用户账户及认领](#用户账户及认领) |

所有管理写请求（POST/PATCH/PUT/DELETE）都检查允许的Origin；默认只接受JSON，第11.3节的精确上传入口仅接受multipart/form-data。除login外，还必须有有效Cookie和额外口令。正式登录凭证只走 Cookie，不作为 Bearer 或 JSON 返回，不放浏览器本地存储。无效登录 401 unauthorized；防冒用口令错误 403 csrf_failed，网页来源不符 403 forbidden。精确检查方式见技术附录第 4 节。

### 0.4 当前能做到哪一步

本节是逐接口实现范围的唯一索引；代码已实现不等于人工验收、合入main或当前线上部署，证据分别看TODO、CHANGELOG及环境手册。以下路由已有实现：

| 用途 | 当前已实现入口 | 详细契约 |
|---|---|---|
| 运行检查 | GET /api/health、GET /api/ready | 第0.5节；公开用户域名不因此开放内部检查 |
| 管理认证 | POST /api/admin/auth/login、GET /api/admin/auth/session、POST /api/admin/auth/logout | 第2节 |
| 芯片登记/查询/批次 | GET/POST /api/admin/chips、GET/PATCH /api/admin/chips/{id}、POST /api/webhook/admin/scan | 第1.1、3节；PATCH仅批次，回调与网页认证不同 |
| 首次绑定 | POST /api/admin/chips/{id}/bind-item | 第3.1节；不含解绑或换新 |
| 密钥及配置核验 | POST /api/admin/chips/{id}/generate-keys、keys、confirm-provisioning | 第3节；不连接或改写实卡 |
| 物品 | GET/POST /api/admin/items、GET/PATCH /api/admin/items/{id}、PUT /api/admin/items/{id}/profile | 第4节；普通保存支持款式，状态及profile仍仅服装 |
| 动态验证与短许可 | POST /api/tap/verify、GET /api/fashion/items/{id}/detail | 第1.2、6节；不证明所有权 |
| 持续查看 | POST /api/tap/verify可选browser_view模式、GET /api/tap/items/{id}/view | 第9节 |
| 款式图片 | POST/GET /api/admin/catalog/styles/{id}/images/{asset_id}及状态；GET /api/tap/items/{id}/style-images/{asset_id}、GET /api/fashion/items/{id}/style-images/{asset_id} | 第11.3节；旧单件图片入口已退役 |
| 有效触碰统计 | GET /api/admin/stats/taps | 第8节 |
| 数字档案重构 | GET /api/admin/catalog/{styles,issues,items,chips,users,audit}、各受支持详情，POST /api/admin/catalog/actions/{action}及款图入口 | 第11节；当前分支构建，验收/部署见TODO |

第10节集中保留短信/认领、所有权、芯片状态/解绑、详情所有权扩展、独立GET物品profile、服装扩展和饰品旧接口设计，均不因文档存在成为可用能力。物品扩展查询、普通保存及款式图片后端已接入，旧单件图片Upload/读取已退役，人工验收见TODO；生产验证清理与整套物品接续已按确认范围在第11节提供；C纠错及未定政策不因此开放，媒体到期技术资源维护不替代B。

未注册地址返回404；已有地址的不支持方法返回405，例如独立GET /api/admin/items/{id}/profile未开放，当前使用物品详情。未来若注册但未开放的业务可按明确契约返回501，不能据旧预留文字声称当前已返回501。扫描配置缺失/非法或密钥配置/密文无法核对时503，不以空密码、默认秘密或假成功凑通过。

### 0.5 当前已实现的运行检查

用于本机或受管理IP限制的云环境运行检查，不要求登录，不读取或返回密钥、账号资料；用户公开域名不因此开放管理/内部检查。现行网关看杭州手册，香港仅是历史环境。无查询参数，多传返回400 invalid_param，返回禁止缓存。

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

媒体005纳入完整识别：列类型/默认值/字符集、InnoDB、主键/索引/外键及生效CHECK不符合已知定义时ready拒绝，MEDIA_ENABLED=false也不跳过。旧库先按[本地升级说明](docs/LOCAL_DEVELOPMENT.md#14-物品与私有图片后端升级)或[杭州媒体准备](docs/HANGZHOU_DEPLOYMENT.md#10-私有图片的升级与持久目录准备)处理；ready不证明目录、配套备份或生产启用前提已满足。

<a name="1-登记芯片验证触碰和绑定手机号"></a>

## 1. 登记芯片与动态验证（已实现）

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

本小步产品及交互规则见[PRD第4.2.1节](docs/product/fashion-touch.md#1-动态验证与短时许可)，技术方案及升级规则见[附录第15节](docs/IMPLEMENTATION_DETAILS.md#15-触碰验证后端技术方案待审核)。共用验证覆盖服装和饰品，工作台全项目统计另按[产品规则](docs/product/admin-management.md#4-工作台有效触碰统计)独立交付；工作台统计查询已接入，见第8节；饰品独立手机体验仍按独立范围推进。用户账户与认领接口在本分支见第11节。

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

短信与首次认领在测试分支接入，见[用户账户及认领](#用户账户及认领)。

<a name="2-管理员登录第一阶段"></a>

## 2. 管理员登录（已实现）

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

<a name="3-管理芯片第一阶段"></a>

## 3. 管理芯片（已实现）

均须完整登录，写请求加防冒用口令。ChipView 是芯片摘要：id、chip_uid、project（fashion/jewelry或null，null显示“未分配”）、chip_status、item_id/item_uid（可空）、batch_no（可空）、registration_source（manual网页手工／nfc_cool手机扫描／unknown历史未知）、provisioned_at（可空）、keys_generated（是否有密钥）、created_at、updated_at；不展示密钥、密文或读数。

| 要做什么及接口 | 要给什么 | 成功返回的 data |
|---|---|---|
| 手动登记：POST /api/admin/chips | chip_uid必填；project、batch_no可选，空时省略或传null | chip：ChipView、is_new：是否新登记 |
| 查列表：GET /api/admin/chips | 下文完整查询条件 | 分页 ChipSummary，含total_pages/page_adjusted |
| 查详情：GET /api/admin/chips/{id} | 有效芯片ID，无查询参数 | ChipSummary，无记录404 |
| 修改批次：PATCH /api/admin/chips/{id} | 仅batch_no，文字或null | 最新ChipSummary |
| 生成密钥：POST /api/admin/chips/{id}/generate-keys | `{}`，不接受 force | chip_id、generated=true、key_version |
| 查看密钥：POST /api/admin/chips/{id}/keys | confirm=true | chip_uid、keys、sun_url_template |
| 确认配置：POST /api/admin/chips/{id}/confirm-provisioning | readings：恰好两项的数组，各含picc_data/cmac；management_confirmed=true | 更新后的ChipView；不返回密钥或用户凭证 |
| 绑定物品：POST /api/admin/chips/{id}/bind-item | item_id | 更新后 ChipView |

ChipSummary保留ChipView全部字段，另有item_name（所属项目已有资料名称，无资料为null）及keyword_matches（chip_uid/item_uid/item_name字段名数组，无关键词为空）。列表、详情和批次保存返回同源摘要；原登记、绑定及密钥写接口的ChipView返回形状保持。第10.2节的状态/解绑及详情所有权扩展仍预留，不能据其定义调用。

绑定物品的页面与业务规则见[绑定PRD](docs/product/chip-lifecycle.md#2-首次绑定物品)，具体实现见[技术附录](docs/IMPLEMENTATION_DETAILS.md#13-芯片绑定物品实现)。人工验收和合并状态分别看TODO与CHANGELOG；本节不因按钮出现就宣称所有管理能力已开放。

手动登记仅接受上述三个JSON字段，请求体最多8192字节，不接收查询参数。UID接受14位连续十六进制或7组冒号格式，去首尾空白并统一为大写冒号格式；project为fashion/jewelry或null，省略同null，空字符串或unassigned不接受。批次去首尾空白后为1–64字符，空字符串不接受。新记录registration_source=manual，由后台设置，不接受请求指定；状态为pending，item_id、provisioned_at为空，keys_generated=false。
```json
{"chip_uid":"04a27f1b5e8010","project":null,"batch_no":"DEMO-01"}
```

返回HTTP200，data固定为chip和is_new。重复UID时is_new=false，返回原记录，项目、批次、状态、首次登记来源、绑定和原更新时间都不覆盖，也不新增变更审计；原项目为空时，本次即使传入项目也不分配，后续走物品绑定。原项目非空且本次明确选择另一个项目才返回409 project_mismatch，message为“该 UID 已登记，所属项目与本次选择不同。原记录未修改，请按 UID 查询。”。其余重复在页面说明该UID已有记录，提供查看确切原记录的入口。首次登记与admin_audit一起保存；输入错误400、会话无效401、来源/口令不符403、数据库或审计失败503。登记不代表写卡完成或真伪验证通过。

列表拒绝未知或重复参数，仅接受以下条件，全部先过滤/计数再分页：

- page为1–2147483647，page_size默认20、范围1–100；固定id倒序。总数与页面在同一只读一致性快照读取。超范围页回最后有效页，空结果为第1页；data为items、total、page、page_size、total_pages（至少1）、page_adjusted（是否修正请求页）。
- project为fashion/jewelry/unassigned，unassigned表示project_id为空；status为pending/bound/disabled/lost；registration_source为manual/nfc_cool/unknown。省略表示不限。
- keyword最多128字符，去首尾空白，覆盖芯片UID及关联物品编号/名称；UID比较单独忽略冒号和大小写，其他字段保留既有排序规则。batch_no去首尾空白后最多64字符，独立包含查询；所有LIKE转义!/%/_，不作为通配指令，不搜索秘密或长正文。
- has_item、keys_generated、provisioned仅接受文字true/false，分别按真实关联、密钥记录存在和provisioned_at非空判断。停用/丢失芯片仍保留关联。
- created_from/to、updated_from/to、provisioned_from/to为YYYY-MM-DD，可单边指定；按北京时间起日00:00至末日次日00:00转换到UTC半开区间。非法日期、逆序、转换溢出或provisioned=false混用核验日期返回400。

详情不接收查询参数，不包含ownership、密钥、计数或认证材料。批次PATCH要求唯一字段batch_no：null或去空白后空串清空，文字最多64字符；拒绝UID、项目、关联、状态或其他字段，沿用8192字节JSON限制。事务先锁管理员/会话重查，再锁目标芯片；批次、updated_at及chip.batch.update审计（仅批次from/to）一起提交，相同值不改时间/不新增审计，失败回滚。普通编辑不改变实卡或关联。错误沿用400/401/403/404/503。

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

参数和业务拒绝不保存变更。提交阶段的故障可能导致已保存但未收到回执，500/503/超时不能统一解释为未保存。页面复用GET /api/admin/chips按完整UID查询，核对id、item_id及chip_status；使用第3节GET芯片详情可按确切ID核对；不返回成功后自动调用写卡、所有权或其他业务。

## 4. 管理物品

ItemView保留id、project、item_uid、sku_code、status、created_at、updated_at、profile；没有对应项目资料为null，不返回profile内部id/item_id。扩展ItemSummary另含linked_chip和keyword_matches：关联为真实芯片的id、chip_uid、chip_status、keys_generated、provisioned_at，无关联为null；关键词匹配字段为item_uid/sku_code/name/chip_uid数组，没有关键词或独立详情读取时为[]，不返回秘密。

| 接口 | 输入及成功data |
|---|---|
| GET /api/admin/items | 下列条件过滤后的分页ItemSummary，含total_pages/page_adjusted |
| POST /api/admin/items | project/item_uid必填，sku_code可空，status省略或仅draft；返回原ItemView，profile=null |
| GET /api/admin/items/{id} | 按确切正整数ID读取ItemSummary，无记录404 |
| PATCH /api/admin/items/{id} | 普通分支接受sku_code/profile中至少一项，返回ItemSummary；status单独提交时保留原服装启停和ItemView返回，不能混合 |
| PUT /api/admin/items/{id}/profile | 保留原服装五项资料整份替换，返回profile；与普通PATCH复用同一校验和写事务 |

创建编号去首尾空白后为1至32字符、不含控制字符、全局唯一，不限制格式，FASH/JEW-YYYY-NNNNNN仅为建议；项目独立选择，不按编号推断。编号重复409 already_exists且不覆盖。sku_code创建和普通保存均最多64字符，可重复，省略创建为空，null/空串/纯空白表示清空；普通PATCH省略表示不改。项目、物品编号、关联、时间及其他只读字段不能写入。饰品可单独改款式，不接受服装profile或启停；归档物品不可维护。

列表只接受page/page_size/project/status/keyword/unbound_only/has_chip，以及created_from/created_to/updated_from/updated_to；未知和重复参数400。分页默认20、上限100，page为1–2147483647；project仅fashion/jewelry，status为draft/active/disabled/archived。布尔仅小写true/false；has_chip判断实际关联，disabled/lost芯片仍占用。unbound_only=true用于绑定候选并排除所有占用，与has_chip=true同时使用400；候选不预占目标，最终绑定仍独立重查。

关键词原文最多128字符，去首尾空白后查物品编号、款式、所属项目资料名称和关联芯片UID；UID比较去冒号并大写，!/%/_按普通文字处理，固定id倒序。日期与第3节相同：YYYY-MM-DD、北京时间包含起止日，允许单边，非法日期/逆序/换算溢出拒绝。查询、总数及profile批量读取位于同一只读一致性快照；超页调整到末页，空结果page=1、total_pages=0，page_adjusted说明是否调整，不返回伪空页。

| profile字段 | 规则 |
|---|---|
| fashion | name必填1–128字符；description最多4000、material256、care_instructions2000，可空；旧单件image_urls只接受[]，款式图片见第11.3节 |
| jewelry | 只读返回已有name/description/material/meaning/image_urls，不新增编辑模板 |
| size_chart | 只读保留既有返回；普通PATCH和兼容PUT均不接收、不更新或清空 |

profile提交时整份替换五个可编辑字段，省略可选项清为null/[]；不提交profile则不改资料，允许无资料时只改款式。文字去首尾空白，按Unicode字符数校验，保留内部换行；介绍等按普通文字展示。旧单件图片仅接受空数组；管理读取与用户详情不回退旧外链或文件。新版共用款图按第11.3节读取，不在旧单件profile中保存。

普通PATCH与兼容PUT上限256KiB，status单独请求及创建仍8KiB，超限400 invalid_param；Nginx同步放行两个准确资料入口。所有写入复用Origin/Cookie/CSRF，锁顺序管理员→会话→物品→相关媒体，实际资料/款式、updated_at、图片状态及审计一起提交；失败回滚，相同值不重复更新时间或审计。普通动作item.details.update仅记项目、变更字段及款式前后值；原item.profile.save/item.status.change返回和最小审计保持，不复制长正文/URL。500/503/超时可能为成功回执丢失，先按确切IDGET核对，不自动重发。

启用仍须先保存有效服装名称；draft/disabled可启用，active可停用，相同状态幂等，不开放回到draft、归档或恢复归档。不改变绑定/写卡/用户验证条件。服装扩展资料维护仍未开放，见[预留设计](#104-服装扩展资料预留)。管理端详情与编辑共用适用业务字段，使用官方Upload、ProForm及ProDescriptions；人工验收/合并状态见TODO。

### 4.1 私有图片上传、暂存与读取

旧单件图片服务已退役：POST /api/admin/items/{id}/images、GET图片/status及用户端旧/images路径不再注册，返回404/405；旧单件profile只接受空image_urls，不再接收外链或上传结果。旧数据图片引用和文件由测试环境清理工具在备份后清理，不在启动/请求时自动删除。

当前图片全部在款式维护，接口见第11.3节。单张最多8MiB，静态JPEG/PNG最多1600万像素、WebP最多800万像素；完整解码、修正方向、缩小至2048边界并重编码WebP、去元数据，拒绝动画/损坏输入；保存款式最多20张。不绕过Cookie/Origin/CSRF和当前用户查看资格。

## 6. 兼容服装详情（已实现）

GET要带X-Tap-Token，核对对应物品和当前状态；读取不消耗凭证。跨项目409 project_mismatch；凭证无效/过期/已使用或不匹配403 invalid_tap_token。此处是短凭证兼容接口；手机持续查看使用第9节，不混用两种资格。

| 接口 | 返回的 data |
|---|---|
| 服装详情：GET /api/fashion/items/{item_id}/detail | item_uid、profile 对象、trace 数组、story 对象或 null、channel 数组、owner_bound |

不返回芯片UID、读取序号、手机号或订单号。饰品详情和旧成长接口见[预留与历史边界](#105-饰品详情预留及旧成长接口候选)，不表示已开放。

## 7. 失败时怎样理解

本表包含已实现和预留业务的错误码集合；短信等预留错误码不证明对应接口已开放。HTTP 状态码是这次请求的大类结果，code 是具体原因，message 是给人看的解释。创建/普通成功仍是 200；不能把故障统一改成 200。

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

本节定义已接入的查询契约，人工验收及分支状态以TODO为准；页面行为见[PRD第4.2.2节](docs/product/admin-management.md#4-工作台有效触碰统计)，统计与实现细节见[技术附录第16节](docs/IMPLEMENTATION_DETAILS.md#16-工作台有效触碰统计技术方案待审核)。

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

本节定义已接入的持续查看契约；实现细节见[技术附录第17节](docs/IMPLEMENTATION_DETAILS.md#17-手机触碰资料页与公网链路技术方案待审核)，软件检查、人工验收与部署状态分别见TODO。产品范围及自动更新见[PRD第4.2.4节](docs/product/fashion-touch.md#2-手机资料页与持续查看)。旧调用不发view资格，原五分钟read/bind行为保留。

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

## 10. 预留设计与未开放能力

本区不是可调用接口清单。下述地址、字段及返回仅保存尚未实施的契约设计；当前未注册仍按第0.4节返回404。旧文中的“501”属于拟开放后的约定，不能当作当前运行证据。产品规则、授权及技术方案须先审核；不凭预留ownership表、状态枚举或组件按钮开始开发。

### 10.1 短信与首次认领（预留）

下方是早期预留，保留供追溯。测试分支请使用[已接入的用户账户及认领接口](#用户账户及认领)及 [H5 首版产品规格](docs/proposals/digital-item-h5-mvp.md)。

<a name="13-post-apipublicsmssend发绑定短信第二阶段"></a>

#### 发送短信：POST /api/public/sms/send（预留）

必填 phone（中国大陆 11 位手机号）、tap_token；仅未用掉的 bind 凭证可用，read 不能绑定：
```json
{"phone":"13800138000","tap_token":"t_example"}
```
先确认凭证与物品仍允许绑定，再保存短信验证记录和发送次数；发送失败不能报成功。提供商及失败重试办法待选。发送不消耗凭证；expires_in 不超过短信和凭证剩余有效期，最大 300 秒：
```json
{"status":"ok","data":{"sent":true,"expires_in":240}}
```
同手机号 60 秒一次，同 IP 每小时最多 10 次，短信码最多错 5 次；发新码让同凭证同手机号旧码失效。错误：400 invalid_param、403 invalid_tap_token、409 already_bound、429 sms_rate_limited、501 feature_not_ready、503 service_unavailable。

<a name="14-post-apipublicbind绑定所有者第二阶段"></a>

#### 首次认领：POST /api/public/bind（预留）

必填 phone、sms_code（6 位数字文字）、tap_token；物品从凭证中确定，不能由客户端替换：
```json
{"phone":"13800138000","sms_code":"123456","tap_token":"t_example"}
```
校验凭证、状态和匹配的短信码；一起完成创建/复用用户、保存 ownership(bind_source=user_self) 和 history(action=bind)、用掉短信码与 bind 凭证。有主人不覆盖，失败不消耗凭证，错码次数仍要保存：
```json
{"status":"ok","data":{"item_id":12,"user_id":5,"bound":true}}
```
错误：400 invalid_param/invalid_sms_code、403 invalid_tap_token、409 already_bound、429 rate_limited、503 service_unavailable。

### 10.2 管理基础入口（预留）

芯片状态、解绑及详情的所有权扩展（基础详情已见第3节）：

| 要做什么及接口 | 要给什么 | 拟返回的 data |
|---|---|---|
| 详情扩展（尚未实现） | 复用第3节详情 | 基础摘要外增加ownership；当前不返回该字段 |
| 改状态：PATCH /api/admin/chips/{id}/status | chip_status | 更新后 ChipView |
| 解除绑定：POST /api/admin/chips/{id}/unbind-item | `{}` | 更新后 ChipView |

物品独立资料读取：

| 要做什么及接口 | 要给什么 | 拟返回的 data |
|---|---|---|
| 查资料：GET /api/admin/items/{id}/profile（预留未实现，当前使用详情） | 物品 id | profile 或 null |

状态与解绑必须按独立产品/技术方案确认；现行首次绑定不因此允许解除或改绑，挂失换新也不能借这些旧入口实现。

<a name="5-管理所有权第一阶段"></a>

### 10.3 管理所有权（预留）

完整登录，写请求加防冒用口令。OwnershipView 是绑定记录：id、item_id、item_uid、user_id、phone_masked（隐藏部分数字的手机号）、bound_at、unbound_at、is_active、bind_source。列表不展示完整手机号；输入手机号按第10.1节预留定义，note 可空且最长 256。

| 要做什么及接口 | 要给什么 | 成功返回的 data |
|---|---|---|
| 查列表：GET /api/admin/ownerships | page/page_size、item_id、user_phone（手机号前缀）、is_active=0/1 可选 | 分页 OwnershipView |
| 绑定：POST /api/admin/ownerships | item_id、phone 必填，note 可选 | 新 OwnershipView |
| 解绑：POST /api/admin/ownerships/{id}/unbind | note 可选 | 关闭后的旧 OwnershipView |
| 转赠：POST /api/admin/ownerships/{id}/transfer | to_phone 必填，note 可选 | 新 OwnershipView |

只给非归档物品绑定；已有主人 409 already_bound。管理员绑定写 ownership.bind_source=admin 和 history(action=bind, from_user_id=null, to_user_id=用户)，history 没有 bind_source。

解绑/转赠只操作当前有效记录，否则 409 invalid_state；转给原主人为 409 already_bound，不造新历史。转赠关闭旧绑定、创建新绑定（来源 admin），只写一条 transfer 历史，保存 from/to 用户；绑定、历史、操作记录一起成功。日志和操作记录不保存完整手机号。

### 10.4 服装扩展资料（预留）

第三阶段的下列接口仅服装物品可用，否则 409 project_mismatch；未细化开放前 501 feature_not_ready。完整登录，写请求加防冒用口令；PUT 整份替换，数组最多 100 项：

| 接口 | PUT 要给什么 | GET/PUT 返回 |
|---|---|---|
| 溯源记录：GET/PUT /api/admin/items/{id}/trace | 数组：stage 必填，event_time/location/operator/detail 可空，sort_order 默认 0 | trace 数组，空时 [] |
| 品牌故事：GET/PUT /api/admin/items/{id}/story | 对象：title/content/media_urls 可空，sort_order 默认 0 | story 对象，空时 null |
| 购买渠道：GET/PUT /api/admin/items/{id}/channel | 数组：channel_type 必填，channel_name/order_no/purchased_at 可空 | channel 数组，空时 [] |

stage/channel_type 取值和长度按 schema；返回包含记录 id、上述字段，不重复 item_id。购买渠道 channel 始终为数组；用户端去掉订单号和个人交易信息。

### 10.5 饰品详情预留及旧成长接口候选

| 接口 | 拟返回的 data |
|---|---|
| 饰品详情：GET /api/jewelry/items/{item_id}/detail | item_uid、profile 对象、owner_bound |

饰品详情预留白名单不包含芯片UID、读取序号、手机号、订单号或成长进度。旧progress/touch接口候选及权限风险已移入[历史归档](docs/archive/legacy-growth-candidate.md#旧接口候选与权限风险)，当前未注册，不作为获批需求或可用接口。新体验须从探索重新评审，不能从旧契约恢复开发。

## 11. 数字档案管理与整套物品（当前分支）

测试分支从物品档案读取换新与转售权益，发行读接口省略 `rights`。旧发行客户端的同名输入仅用于兼容解析。新物品的标准权益由服务端授予。业务规则见 [数字物品权益](docs/proposals/admin-make-rebuild.md#item-rights)，上线和人工验收见 [验收清单](docs/DIGITAL_ITEM_ASSEMBLY_H5_ACCEPTANCE.md)。

### 实体装配、发码与预览

| 入口 | 条件与返回 |
|---|---|
| `GET /api/admin/catalog/physical-items` | 管理登录后按 `style_id`、`available`、编号关键词和批次筛选；详情按 ID 查看。实体包含编号、实际规格及装配状态。 |
| `actions/createPhysicalItem` | 传 `style_id`、`physical_uid`、适用的 `spec`，可选 `batch_no`、`supplier_serial`。返回实体 ID 及编号。 |
| `actions/installAssembly`、`actions/undoInstall` | 安装传 `item_id`、`physical_item_id`、`chip_id`、`installed=true`。纠正限未配置草稿，传 `item_id`、`whole_id`、`evidence`、`confirmed=true`。 |
| `actions/prepare`、`actions/complete` | 新版准备含 `physical_item_id` 和 `installed=true`，转售含接收账户和双方确认依据。有争议时提交核验结果引用。确认换新交付时按北京时间生效日计次。 |
| `actions/issueClaimCode`、`actions/reissueClaimCode` | 传 `item_id`、`delivery_reference`、`confirmed=true`。首次成功响应展示原码一次。回执只返回发放记录和有效期。 |
| `GET /api/admin/catalog/items/{id}/h5-preview` | 读取指定物品已保存的展示资料，预设视角在后台界面切换。 |
| `GET /api/admin/catalog/audit` | 支持 `keyword`、`action`、`operator`、`date_from`、`date_to`、`item_id`。返回动作说明、对象、结果和必要前后值。 |

### 用户账户及认领

用户端从指定同源发起写请求。账户使用独立 HttpOnly Cookie。碰卡短时资格、持续查看 Cookie 和用户会话分别校验。

| 入口 | 条件与返回 |
|---|---|
| `POST /api/public/sms/send` | 传 `phone`，成功返回 `challenge_id` 和重发间隔。单一手机号至少间隔 60 秒，网关不可用时返回 503。 |
| `POST /api/public/sms/verify` | 传 `challenge_id`、`code`。成功建立会话，返回稳定账户 UID 和脱敏手机号。 |
| `GET /api/public/account/session`、`POST /api/public/account/logout` | 读取本人会话，或用空 JSON 对象注销当前会话。 |
| `POST /api/public/items/{id}/claim` | 传 `tap_token`、`claim_code`，同时验证用户会话及当前装配。成功建立持有关系、记录历史并核销凭证。旧碰卡返回 `retap_required`，旧码或过期按状态提示。 |
| `GET /api/public/items/{id}/claim-status` | 登录后核对本人已持有、他人已认领或待认领，用于未知结果恢复。 |
| `GET /api/public/me/items`、`GET /api/public/me/items/{id}` | 读取本人当前持有列表与详情。关联图片走同样的归属检查。 |

当前正式管理端使用此服务。复用管理Cookie/Origin/CSRF和禁缓存，任何写入先重查管理员与会话。没有原型会话导入、演示触碰、演示认领、默认持有人或模拟成功入口。旧认证、密钥、图片及用户触碰契约继续适用；数据库先升级006，工具默认只检查，缺失/部分结构时ready拒绝。

### 11.1 分页与详情

GET /api/admin/catalog/{resource}，resource为styles/issues/items/chips/users/audit。page默认1，page_size默认10、最大100，实际页面每页10条；keyword最多128字符。服务端在同一只读快照计算过滤、总数和本页，越界页收回最后有效页，返回items/total/page/page_size/total_pages/page_adjusted。默认按内部ID倒序。物品关键词覆盖编号/款式名/当前芯片，芯片覆盖UID/物品编号/批次；查询不是前端截取本页后再过滤。

| 资源 | 筛选与返回补充 |
|---|---|
| styles | project；返回code/name/description/material/care_instructions/specs/image_urls及引用计数 |
| issues | project/style_id/status=confirmed；返回mode/total/starts_at/ends_at/counting_rule/confirmed_at/sealed_at/ever_used |
| items | project/status/issue_id/is_validation/sold/whole_status/bindable=true；bindable仅未归档、已关联发行且未准备整套的对象；whole_status为normal/lost/missing，布尔筛选仅true/false；返回稳定身份、发行序号、当前整套/芯片、售出、归属与验证摘要 |
| chips | project/status/is_validation/available=true/compatible_project；compatible_project只筛该类别或未预设类别；available只取未占用且可准备的pending芯片，不将候选当当前；status新增retired，lost表示随整套挂失停用 |
| users | keyword按昵称或ID，exclude_id可排除当前持有人；仅真实账户，联系方式脱敏，返回持有数量，不是CRM或认领接口 |
| audit | keyword按动作/对象ID；管理操作及必要依据只向管理员开放 |

GET /api/admin/catalog/{styles,issues,items,chips}/{id}读取确切记录；issues另返回suggested_item_uid与suggested_edition_number，仅作未预占的建议；items.handovers另带owner_name/recipient_name及候选provisioned_at只读核对摘要；id为页面可安全处理的正整数（当前新增服务上限2147483647），缺失404。items详情另外返回style/issue、wholes、handovers、owners及缺发行时的legacy_profile。所有者只读；无所有者显示暂无持有人，有当前关系显示已有持有人，不推断首次认领，不猜购买人/碰卡人。旧单件资料不自动归并到款式，已有正确发行不允许普通更换。

### 11.2 事务操作与字段

POST /api/admin/catalog/actions/{action}只接受request_id和payload。request_id是36位小写UUID，payload为下表声明的字段对象；未知/漏必填字段400，资格或状态冲突409，缺失404。新建成功返回真实id；不伪造业务成功。所有普通文本边界继续原契约，新增核对依据最多1000字符、实际规格256字符、款式编号64字符，发行/款式名称128字符。

| action | payload及关键条件 |
|---|---|
| style | project/code/name/specs/image_urls必填；id、description/material/care_instructions/shared_confirmed选填。specs最多100项，每项128字符；引用后类别/编号保护，共用保存须明确确认影响；读取返回item_count与active_item_count，保存前展示引用总数及已启用数 |
| issue | style_id/name/mode/description；id/series/total/starts_at/ends_at/counting_rule可选或按模式必填。mode=fixed/period/unlimited；固定总量正整数，限时提供带时区的起止时间及核定规则 |
| confirmIssue/deleteIssue/seal | issue_id；seal另需total/evidence，必须窗口已结束、已确认、未封版且不小于已建身份/已有序号。删除仅从未引用约定并留快照审计 |
| item | issue_id/item_uid；edition_number按模式要求、is_validation默认false。必须已确认发行，项目由款式确定，item_uid去首尾空白后1–32字符、不含控制字符、全局唯一，不限制格式，FASH/JEW仅作建议；固定/封版总量与发行内编号唯一由服务端及数据库保护 |
| register | chip_uid，project/batch_no/is_validation可选。复用真实登记与UID规范，重复返回原id/is_new=false，不改批次/来源/验证标记 |
| linkIssue | item_id/issue_id/edition_number/evidence；只补确实缺失的同类别发行，不改稳定编号、实体、归属和年度事实 |
| bind | item_id/chip_id，spec选填（不适用时空）；准备首套或补齐当前物品，不用于换新。有效发行、未占用可用芯片及类别校验后追加当代，配置仍独立 |
| saleBatch | item_ids/confirmed/evidence，first_sold_at可选（带时区ISO8601、不晚于当前）；1–100个不同物品，不能跨数据来源；固定顺序锁定，在同一事务内维护售出事实、审计和回执，任一失败整体回滚 |
| sale | item_id/confirmed/evidence，first_sold_at可选（带时区ISO8601、不晚于当前）；首次登记使用所填成交时间或当前时间，已有首次时间拒绝不同值；显式维护售出事实，操作时间与依据留审计，首次成交时间只记一次；撤销不删除首次时间、持有人及触碰历史 |
| toggleItem | item_id/status，status仅active/disabled；新档案启用检查发行、当前整套、有效芯片与真实核验；停用永久撤销现有查看资格 |
| loseItem | item_id/whole_id/evidence；固定本次当代ID，挂失写入当代并同步停芯片、撤销资格；准备中的普通换新转为挂失换新，已准备的新整套保留 |
| prepare | item_id/kind/chip_id/evidence，spec选填（不适用时空），转售另需recipient_id；kind=periodic/loss/resale。检查真实持有人、已约定权益、年度/待核事实、接收账户及芯片占用；保存原代ID与新代规格/芯片，尚不切换归属/授权 |
| complete | work_id/evidence/checked=true；重查原代及当前持有人，候选必须真实核验。一起结束旧代、退役旧卡、追加新代、必要转移持有人、保存历史并撤销旧短许可/持续查看。新代正常，不继承旧代挂失；身份/编号/首次售出保留，换新计次待核，转售不重置余额 |
| chipBatch/chipState | chip_id/batch_no；或chip_id/state/evidence，state仅disabled/restore；挂失、退役或候选不可普通恢复，芯片页无独立挂失 |
| validationItem/validationChip | item_id或chip_id及enabled布尔值；标记不改变统计 |
| deleteItem/deleteChip | item_id或chip_id；必须已标生产验证，此后不按启用/绑定/配置/持有人/触碰/历史设资格。只删除目标及对应触碰、办理和关联，另一侧、审计保留；事件清理后退出统计。内部ID不复用；旧单件图片文件不在此立即覆盖或清盘 |
| legacyProfile | item_id/profile；仅缺发行的历史服装档案保留原资料/私有图片维护，复用原白名单/暂存保存机制；已引用共用款式时此入口拒绝 |
| receipt | payload仅原request_id；同一管理员读取已提交回执，未查到404，不因此断言原请求永远不会提交 |

请求和payload摘要、业务结果与审计在同一事务提交。相同管理员、action、payload与request_id重试返回原结果；编号已用于其他请求则409。网络/503/坏响应时页面冻结写入并查询回执，仍须明确重试相同输入/编号，不自动重发，不允许改输入复用旧编号。普通4xx保留输入并由人修正。提交回执不含密钥或会话凭证。

### 11.3 共用图片与统计

POST /api/admin/catalog/styles/{id}/images/{asset_id}为精确multipart入口，只收一个file；asset_id为32位小写随机十六进制。上传API要求款式已保存并取得id；界面允许先在浏览器选图预览，明确保存时依次保存资料、上传并关联，部分失败不冒称全部完成。JPEG/PNG/WebP和大小/解码边界沿第4.1节，复用重编码；返回url。GET同地址由管理会话读取，GET后缀/status核对上传是否已提交，未知先核对、明确重试同一文件/标识，不盲目换ID。保存款式才关联图片，最多20张；服务不接受dataURL或其他物品私有图片作为共用图片。

当前共用图以受控二进制保存于style_image并随数据库转储，容量与到期暂存受限；旧图片已停止在线服务，清理前仍须原生SQL与文件配套备份；清理后新增款图仅依赖数据库。用户GET /api/tap/items/{item_id}/style-images/{asset_id}复用同一有效view Cookie、物品/芯片/配置检查，且图片必须属于当前已保存共用款式；旧持有者/失效资格不能读取，不返回内部备注或账户。兼容GET /api/fashion/items/{item_id}/style-images/{asset_id}使用原X-Tap-Token短资格；返回图片地址按对应资格族映射，不要求旧短资格客户端持有view Cookie。用户资料只按原公开白名单读取共用字段，旧未关联档案仅保留文字资料，图片为空。

GET /api/admin/catalog/statistics支持scope=sold/all、range=7d/30d/all及project/item_id/chip_id/style_id/issue_id。明细支持page/page_size（默认10、最多100），返回details与holders的items及分页元数据；details按稳定身份汇总tap_count/last_tap，包含符合售出口径但零触碰的身份。inventory提供独立于触碰筛选的当前数据范围概况；counts中的物品/售出/持有按款式、发行等已生效条件统计，时间仅限制触碰。仅统计可信pass事件；sold额外要求显式售出、首次售出时间及事件不早于首次售出，不按owner是否存在推算售出。按稳定item_id跨历代芯片聚合，返回total/touched_items/daily/by_chip及真实档案/账户/持有counts、as_of和Asia/Shanghai。核验读数、失败、重放和普通查看均不新增事件。首次认领服务未开放须明示，不以空模拟用户统计冒充已接入。


### 11.4 验收批次与数据范围

007新增test_batch、test_batch_object，来源不可由生产验证开关重写。正式后台只在“系统管理→设置”提供一个“开启测试数据”开关，默认关闭；开启后使用活动验收批次，列表、统计、候选和新增对象统一继承，关闭回业务数据，不删除样本。无活动批次时明确说明并禁用开启，开关不自动生成样例；读取失败单独报错，不能当作空库。完整批次清单确认旧选择已不存在或被清理时，提示关闭失效模式，不自动换到其他批次。该偏好仅存当前浏览器标签页，不是权限或后端业务状态；切换重新读取页面，URL旧筛选不能覆盖它。普通页面不提供测试范围/批次筛选、来源列或手填批次。后端参数保留用于受控工具和兼容，并不要求日常页面暴露。发行列表另支持mode=fixed/period/unlimited及status=draft/confirmed；物品支持style_id和owner=yes/no；芯片支持configured=yes/no及registration_source=manual/nfc_cool/unknown。styles/issues/items/chips/users及statistics支持data_scope=business/test/all（默认business）、test_batch_id可选正整数；business与指定批次冲突400。各列表/指标/趋势/明细应用相同来源，详情返回test_batch_id；历史未标记对象属于业务范围。发行继承款式、身份继承发行，新配芯片/接收账户须同来源，不允许业务/测试或跨批次混用。

GET /api/admin/catalog/test-batches返回分页批次，manifest含场景/合成说明/初始预期统计，writable表示当前配置是否允许测试写入。GET /api/admin/catalog/test-batches/{id}/preview在明确测试环境返回counts/objects/conflicts；POST actions/clearTestBatch采用第11.2节相同request_id+payload，payload={batch_id,confirmed:true}。写入口及预览只允许固定杭州test或原本机开发目标，生产/未知配置403；没有公开seed接口。

清理仅删除该批拥有的对象及其关联历史/图片/合成账户；审计、回执与来源摘要保留。跨批次引用409并整体回滚；同一回执重试不重复执行；已清理批次保持摘要。单条验证对象删除仍只删除当前对象、另一侧保留。

合成配置/持有/触碰仅由受控命令导入，虚拟芯片不导入密钥，不能通过真实验签；后续实际产生事件按稳定物品来源自然归组。真实卡不作为合成样本自动标记或重置计数。
