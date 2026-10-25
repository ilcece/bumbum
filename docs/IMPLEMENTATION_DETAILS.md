# 技术附录：写代码时要遵守的精确规则

这是 [TECH_SPEC](../TECH_SPEC.md) 的组成部分。cece 可以先读正文理解流程，按需查这里；AI 实现数据库、安全、认证和部署时必须读取对应章节。这里保留精确参数，并先解释它们在防什么问题。管理员认证按 cece 已确认的 MVP 简化方案执行；芯片密钥、用户触碰和所有权规则保持原有定义。

## 1. 编号与数据库保存规则

目的是让同一芯片、物品和所有者不会因写法不同或请求同时到达而重复出现。

| 项目 | 精确规则 |
|---|---|
| 项目 | code 仅 fashion/jewelry；业务资料类型须与项目一致，不给 jewelry 写 fashion profile |
| 芯片编号 | chip_uid 为7字节；手动入口接受14位连续十六进制或7组冒号格式，去首尾空白，统一成冒号分隔的大写；其他分隔符拒绝 |
| 手动登记 | 新UID设pending，project可省略/null，item_id为空，不写provisioned_at或chip_key。唯一索引去重，重复返回原记录，项目不分配、不清空、不覆盖；原项目非空且本次明确选择另一个项目才409。首次登记与chip.register审计一起提交 |
| 首次登记来源 | chip.registration_source使用ENUM('unknown','manual','nfc_cool')，默认unknown；网页和手机由服务端分别写manual/nfc_cool。来源与首次新增、操作记录一起保存，重复不更新。content/date不新增保存字段 |
| 物品编号 | item_uid 用 FASH-YYYY-NNNNNN / JEW-YYYY-NNNNNN，创建时提供，前缀匹配项目，之后不可修改；ASCII、位数和空值边界以[PRD草稿规则](../PRD.md#411-本小步物品草稿创建与列表)为准 |
| 唯一绑定 | chip.item_id 可空且唯一；复合外键检查项目；ck_chip_project_assignment限制空项目时item_id/provisioned_at/last_verified_counter必须全空，避免NULL跳过复合外键；已关联物品不物理删除 |
| 当前所有者 | active_item_id 仅在 is_active=1 时映射 item_id，唯一索引限制一条有效绑定；历史可以多条 |
| 解绑 | 同时设置 is_active=0 和 unbound_at；不删除历史、密钥和已接受计数器 |
| 流转 | bind_source 只在 ownership；history 保存 from/to、action、note、时间；转赠只写一条 transfer 历史 |
| 同时修改 | 事务中先锁物品，再锁芯片/有效 ownership；多个物品按 id 升序。检查、修改和审计一起提交；失败全部撤销 |
| 争抢或死锁 | 给出契约错误，不向前端泄露 SQL/堆栈；只有可重试的事务做有次数上限的重试 |
| 存储引擎和版本 | InnoDB，MySQL >= 8.0.16，utf8mb4；实际执行 CHECK 约束 |
| 时间 | 每个数据库连接初始化 time_zone='+00:00'；DATETIME/TIMESTAMP 按 UTC 理解；接口输出 ISO 8601 UTC |
| 建表/升级 | schema 只作空库初始化；已有数据库单独迁移，先备份，说明升级、验证和回滚/恢复，未经授权不执行生产变更 |

手动登记先在事务中按账号、会话的顺序锁定并重查登录状态，再保存芯片。`INSERT ... ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)` 只取回重复记录ID，不改项目、批次或状态；使用当前PyMySQL默认连接选项，首次插入的影响行数为1，重复为0。 取回摘要时使用只锁chip表的当前读（FOR UPDATE OF c），避免并发时旧快照读不到另一事务刚提交的记录；不把项目或物品表升级为排他锁。新增时审计仅保存项目和来源manual，目标ID关联芯片，IP沿用指纹规则；重复未修改资料，不新增变更审计。数据库提交失败返回503，不能提前返回成功。

列表使用LEFT JOIN保留空项目记录，project=unassigned筛选c.project_id IS NULL；未分配不是第三个项目。绑定功能后续实现：按既定锁顺序，空项目时在同一事务首次设为目标物品项目，已有项目则严格匹配；解绑保留项目。未分配不能生成chip_key，未来密钥接口必须在写事务内检查，不能只靠页面隐藏；当前没有密钥生成实现。

已有库通过migrate_local.py先完整备份再执行001迁移：使用一条原子ALTER将project_id改可空、添加ck_chip_project_assignment，并用不同名称的_v2外键重建相同关联规则，避免MySQL同一ALTER重用旧外键名失败；不关闭外键检查。回退同样单条ALTER，已有空项目记录时提前拒绝。ready检查本次字段及外键/检查约束版本，未完成升级时503。命令只接受默认本机测试库，备份容器与实际连接须同一server_uuid；不擅自升级生产或导入备份覆盖数据。步骤见[本地运行第7节](LOCAL_DEVELOPMENT.md#7-已有测试库升级允许芯片暂不分配项目)。

锁定记录的意思是：在本次保存结束前，其他要修改同一记录的请求需要等待，避免两个请求各自认为“还没绑定”。

## 2. 芯片密钥与版本

同版本全局共享 K1、单芯片独立 K2 已获确认。K1 负责解密编号，K2 按 SDM 规则参与核验防伪码；K0 管理芯片，K3/K4 预留。项目根密钥只在服务器使用，K0/K2/K3/K4 按项目根密钥、UID、槽位和用途算出；不同项目和用途必须分开计算。具体计算方法称为 KDF，须固定实现、输入编码和正确答案测试，旧版随手写的 CMAC 输入公式不能直接投产。

芯片尚未分配项目时，不能选择根密钥、生成芯片密钥或写卡；验证入口也不能替它猜项目、尝试其他项目根密钥或签发tap_token。项目确定后才允许进入仍待核验的密钥流程，全局K1/独立K2的分工不变。

| 配置或字段 | 如何使用 |
|---|---|
| SDM_META_KEY_V1 | 独立安全随机生成 16 字节，写成 32 位十六进制；同版本跨项目相同。不用全零、项目根密钥或其他用途密钥替代 |
| SDM_META_KEY_VERSION | 初期只支持 v1。缺失、格式错误或不支持版本时，阻止相关功能启用，不能使用默认秘密兜底 |
| K1 加载 | 可在启动时加载只读配置到受控进程内存，不逐请求查库；不写仓库、普通日志；账号失败次数和业务变化仍保存到数据库；登录的 IP 频率限制由 Nginx 共用计数 |
| chip_key.key_version | 不可变的 SDM 配置版本；初始配置 v1 固定对应全局 K1 v1 |
| master_key_version | K0/K2/K3/K4 所属项目根密钥版本，不代表 K1 版本 |
| storage_key_version | 包装数据库秘密所用的存储密钥版本，不代表芯片密钥版本 |
| encrypted_keys | 保存 K0–K4 的加密 JSON。K1 是对应全局版本的加密副本；生成时核对统一来源，不能每枚卡随机生成 K1，也不能读旧卡时偷偷换为新 K1 |

换密钥也叫轮换：必须另定新配置版本、固定的版本对应关系、旧卡更新和恢复办法，必要时另写数据库升级。不能把 v1 的实际密钥换掉还叫 v1；存储密钥旧版本在重新加密完成前也不能丢。初期只有一把 K1；以后若同时支持多个 K1 版本，候选数量必须有限，并核对记录版本、完整防伪码且只接受唯一匹配。不会遍历项目或全部芯片密钥。

SDMMetaRead 应配置为 K1，SDMFileRead 配置为 K2；这些名字分别表示“解密芯片信息”和“读取/核验 SDM 数据所用密钥”。实际管理认证、ChangeKey（换钥匙）、写文件和改设置的权限要查 NXP 资料并实测，不能因为名字是“元数据密钥”就假定 K1 没有其他权限。

全局 K1 泄露影响该版本所有芯片的编号/读数隐私；正确分开的 K2 不应随之泄露。查看密钥要求完整登录、确认、先保存审计、Cache-Control:no-store（不缓存），界面提醒全局范围。列表不展示密钥，前端不长期保存。禁止 force=true 覆盖已有记录；重复生成返回 already_exists，真正换钥匙另定流程和计数器处理。

## 3. 秘密如何加密保存

目的：拿到数据库文件的人，不能直接读出芯片密钥和验证器秘密；加密内容被移动或修改时，程序也能发现。

| 名称 | 大白话解释 | 固定要求 |
|---|---|---|
| DEK | 每条秘密各用的一把临时钥匙 | 独立随机 32 字节 |
| AES-256-GCM | 同时加密、检查内容有没有被改的算法 | 使用成熟库，不自己实现 |
| nonce | 每次加密新生成的随机数 | 数据层和包装 DEK 层各用独立随机 12 字节，不复用、不用固定常量 |
| tag | 检查密文是否被改过的验证标记 | 16 字节，放在密文末尾，即 ciphertext || tag |
| STORAGE_ENCRYPTION_KEY | 加密临时钥匙的服务器存储密钥 | 独立 32 字节，不能复用项目根密钥或 K1 |
| AAD | 把密文和它所属记录绑定的信息 | 两层都按下方固定格式生成；不能拿其他记录的密文替换 |

解密顺序：根据 storage_key_version 找包装密钥 → 解密并验证 DEK → 用 DEK 解密并验证数据。任一验证失败立即停止，不把损坏内容当明文使用。

两层 AAD 为下列字符串的 UTF-8 字节：
```text
bumbum|<entity>|<id>|<field>|<storage_key_version>|<layer>
```
entity 为 chip_key/admin_user；chip_key 的 id 使用 chip_id，admin_user 使用 admin_id；field 为 keys/totp_secret；layer 为 data/dek。解密时从预期记录重新生成，不能盲信密文附带的值。

当前只实现验证器秘密的加解密，使用 cryptography 50.0.2；芯片秘密存储尚未接入。

chip_key 使用 encrypted_keys、nonce、dek_ciphertext、dek_nonce、storage_key_version 分列保存。验证器秘密 totp_secret_encrypted 则保存完整 UTF-8 JSON 信封：format_version=1、algorithm=AES-256-GCM、storage_key_version，以及以 Base64（将二进制转成文字）表示的 dek_ciphertext/dek_nonce/ciphertext/nonce；密文均含 tag，只接受已支持格式。迁移到 KMS（云端托管密钥服务）需另定格式和版本，不能假定当前字段可容纳任意服务返回内容。

## 4. 登录凭证与防冒用检查

目标：管理员一次提交账号、密码、Authenticator 验证码后登录；退出和重置后旧登录立即失效。密码用 Werkzeug 的 scrypt 保存校验指纹，每个密码带独立随机值（加盐），不保存原密码。当前使用 Werkzeug 3.1.9 的默认 scrypt 参数（32768:8:1），生产资源与容量仍需验证。服务器创建新密码要求12–128字符；登录按接口原值验证，不改成注册长度限制。

| 项目 | 精确要求与含义 |
|---|---|
| 登录 | POST /api/admin/auth/login 一次接收 username、password、code；只有账号启用、验证器已设置、密码和验证码均正确才成功；不发临时登录票据 |
| 验证器 | 使用 pyotp 2.10.0；使用标准 HMAC-SHA1 的 TOTP，6 位、30 秒一个时段，容差为当前时段前后各 1 个；秘密独立安全随机生成至少 160 位，以 Base32 表示并通过二维码设置；服务器校时。接受的时段必须大于 totp_last_step |
| 会话 | 使用密码学安全随机数生成至少 256 位登录 token；admin_session 仅保存其 SHA-256 指纹 token_hash，最长 8 小时，不滚动续期；没有设置阶段的临时权限或 scope 字段 |
| Cookie | 名 bumbum_admin_session；生产 HttpOnly（网页脚本不能读取）、Secure（只经 HTTPS）、SameSite=Strict（限制跨站携带）、Path=/api/admin；不设 Domain |
| 正式凭证位置 | 登录 token 只放 Cookie，不返回 JSON，不放 URL、本地存储或正式 Bearer 认证 |
| Origin | 管理请求写入数据时，精确匹配生产管理域名或开发 ADMIN_ORIGIN；缺失或不符返回 403 forbidden；命令行联调也须带合法 Origin |
| 写请求 | 只接受 JSON；除 login 外都需要有效登录 Cookie 和 X-CSRF-Token。login 不依赖已有 Cookie 或口令，但仍强制检查 Origin 和 JSON，避免跨站登录 |
| CORS | 开发环境管理 API 仅允许 ADMIN_ORIGIN，允许 credentials 携带 Cookie；生产同域调用不加跨域放行头，不套用 CORS_ORIGINS 总清单 |
| 本地开发 | 仅 APP_ENV=development 且 ADMIN_ORIGIN 明确为本机 HTTP 来源时可关闭 Cookie Secure；生产必须 HTTPS，缺省环境按 production 处理 |

**随机防冒用口令怎么处理：**采用成熟 CSRF 组件支持的“令牌随服务器会话保存”模式。创建登录时，独立随机生成 32 字节、写成 64 位小写十六进制，存到 admin_session.csrf_token。它和登录 token 各自生成，不从 token 推导，不额外使用 CSRF 密钥或手写签名公式。此口令单独不能登录，因此数据库可保存原值；正式登录 token 仍只保存指纹。现由 WTForms 3.3.0 的 CSRF 扩展点适配 MySQL 会话：secrets 生成令牌，组件校验格式并用 compare_digest 比较。未启用 Flask 签名会话或另配 CSRF 密钥；已验证缺失、错误及另一会话的令牌均被拒绝。

GET /api/admin/auth/session 检查有效登录及账号状态，返回 authenticated、expires_at 和同一 csrf_token，不返回 Cookie 值，不缓存，也不换口令或修改登录状态。页面只在内存中持有口令，写请求放 X-CSRF-Token；后端恒定时间比较（避免比较耗时泄露内容）。这样刷新页面或多个标签页能共用现有登录，不需要自定义 HMAC 密钥。

登录时锁定 admin_user 对应行，重查账号、锁定截止时间、密码和验证码。验证成功后，在同一事务内更新 totp_last_step、last_login_at、清失败次数、创建新会话并保存成功记录。并发请求不能用同一验证码拿到两次登录；重登成功时撤销浏览器携带的旧会话，生成新的 token 和防冒用口令，避免沿用旧凭证。失败计数和失败记录也必须保存，不能随错误响应回滚；保存失败按服务故障处理，不能先发 Cookie。

账号不存在、禁用、验证器未设置、密码或验证码错误、验证码已使用，对外统一为 401 unauthorized，不暴露具体哪项正确。字段缺失或格式不合法仍为 400 invalid_param；临时锁定为 429 rate_limited。注销撤销当前会话并清 Cookie；禁用或重置验证器时撤销该账号全部会话，每次管理请求都重查账号启用和验证器已设置状态。

**首次设置和丢失后的恢复：**已实现 admin create、reset-totp 和 disable，操作步骤见 [管理员登录](ADMIN_LOGIN.md)。设置页面不发网络请求、不新增网页设置接口；优先在本机浏览器打开，失败时只向终端显示临时文件路径。文件由系统临时目录保存，在支持权限位的系统中目录权限700、文件600；确认、失败或Ctrl+C退出时清理，不写普通日志。没有桌面的服务器需操作者通过受控方式打开临时文件。命令安全输入密码，生成验证器秘密，用 qrcode 的白底SVG在本机临时HTML中显示二维码并提供手动添加资料，输入验证码确认后，才加密保存秘密并设 totp_enabled=1；记录确认时段。重置先将 totp_enabled=0、清除旧验证器秘密和撤销全部会话一起保存，再确认新验证器；失败时维持不可登录。重置还清账号失败计数和锁定时间。受限文件 logs/admin-operations.jsonl 记录服务器操作者、目标账号、时间、动作、固定原因（首次设置、更换或恢复验证器、停用账号）及 started/committed/incomplete 结果。文件以仅操作者可读写的权限新建；不能记录密码、二维码内容、秘密或验证码。不增加网页注册、验证器设置接口、备份码或恢复绕过接口；真正创建或重置账号需要授权。

## 5. 限制重试与记录操作

第一阶段只用现有 MySQL 和 Nginx，不引入 Redis。账号失败计数与登录会话放数据库，多个 Gunicorn 进程看到同一份结果；Nginx 的共享计数区负责 IP 频率限制。

| 场景 | 固定规则 |
|---|---|
| 账号登录失败 | admin_user.failed_login_attempts 每次加 1；密码错、验证码错或重复使用均计数，连续 5 次设置 locked_until 为当前时间后 15 分钟 |
| 已锁定 | 返回 429，不增加次数、不延长锁期；到期后的首次尝试先清旧计数和锁定时间，再按新尝试判断；成功登录也清零 |
| 未知账号 | 不创建管理员或账号计数记录；返回同样的 unauthorized，并记录经指纹处理的账号标识；IP 频率限制仍有效 |
| 同一 IP 登录频率 | Nginx 仅对准确的登录路径限制，平均每分钟 5 次、允许瞬时额外 4 次；超过返回 429 rate_limited。阈值上线前联调验证，不用于整个管理后台 |
| 第二阶段短信发送 | 同手机号 60 秒一次；同 IP 每小时最多 10 次，仍需多进程共用计数 |
| 第二阶段短信码 | 最多 5 次错误；新码使同 grant 同手机号旧码失效 |
| 第二阶段芯片验证 | 多进程共用计数；阈值经负载测试和共享 IP 情况确认，不预先保证固定次数或零开销 |

账号失败计数更新时锁定 admin_user 行，在事务内检查和更新；不再为登录维护多种计数桶或分级锁期。security_rate_limit 仅作第二阶段短信、芯片验证的预留表，不参与第一阶段登录；其 bucket_key 仍用 IP_HASH_KEY 对用途和统一格式的标识计算 HMAC-SHA256。第二阶段开发时处理唯一键、锁行与保存，不能用单个进程内存代替。

记录范围限定为：

- admin_login_event 保存登录成功、失败、锁定，不区分密码或验证码哪项错误；未知账号用 username_hash，不编造 admin_id。
- admin_audit 保存查看/生成芯片密钥、所有权绑定/解绑/转赠、芯片绑定及状态修改、物品创建与修改等关键变更；不为每次列表查询和页面访问另做全链路记录。
- 服务器创建账号、重置验证器和停用账号另记受限的操作结果；不把服务器操作者伪装成某个网页登录管理员。

ip_hash 仍用独立 IP_HASH_KEY 处理规范化 IP，不记录原始 IP、密码、密钥、二维码、验证码、token 或完整手机号。业务变更与关键操作记录一起保存；查看密钥先保存记录再返回，失败不能声称已记录。动态链接和请求体不进入普通访问日志，日志保留时长及权限投产前确定。

## 6. 芯片验证与临时凭证

SDM 是芯片生成动态信息和防伪码的机制。PICC 数据是其中包含芯片编号、读数的部分；CMAC 是用秘密密钥核对消息的防伪码。NDEF 是芯片里保存链接的数据格式，偏移就是参数在这些字节中的起始位置。

- picc_data/cmac 输入先严格验格式。AES-CBC 解密不自带“密钥正确”证明；按配置检查 PICCDataTag 的 UID 长度、UID/读数镜像标志、布局。任意 7 字节都能转成 14 位十六进制，不能据此相信身份。
- 初期只尝试 K1 v1；按候选 UID 查库确定项目，检查 key_version 对应的 K1 版本；再按项目和根密钥版本取得独立 K2。客户端不提供项目/版本，不能增加静态查找标识，也不启用 enc。
- 用 K2、UID、SDM 读取计数器等规定输入派生本次会话 MAC 密钥，按照写卡配置的 MAC 覆盖范围、截断规则核对 cmac，保留所需原始编码，采用恒定时间比较（避免通过比较耗时逐字猜结果）。不能只对解密明文做通用 CMAC。
- 多版本时检查所有受限候选，唯一完整通过才接受；多个完整通过属配置错误，500 internal_error 且不发凭证。解析/验签不符可继续，配置缺失/数据库故障按服务错误返回，不用裸 except 吞掉全部错误。
- 检查 bound/active、密钥和写卡完成；事务里先锁物品后锁芯片，重查绑定、配置版本和状态；只接受大于 last_verified_counter 的读数，写成功日志并创建 tap_grant 一起提交。旧读数、错误防伪码、未提交事务都不能推进计数器。解绑不清零；计数器耗尽、换卡换钥的恢复另定。
- 失败日志另记；没得到 UID 时用 NULL，不造 UID，未验签的候选 UID 不视为认证身份。旧 URL/乱序读数返回 replay_suspect 并提示重触碰；服务故障和过密请求不假装成假货。

临时凭证 tap_token 至少 256 位安全随机数、5 分钟有效，在 tap_grant 只存摘要，绑定芯片、物品和 allowed_action。未绑定给 bind，已绑定给 read。允许重复查看，发短信不消耗；仅成功绑定时事务内设 consumed_at。失败不消耗；过期、用掉、停用或原绑定改变均不能继续使用。读请求用 X-Tap-Token，写请求用 JSON，不用 query 参数，不在浏览器长期保存。它不是用户登录或所有者身份，也不能阻止未用链接被转发抢先消费。

短信挑战保存到 sms_challenge，以独立 SMS_CODE_HASH_KEY 对 grant、手机号和用途做 HMAC-SHA256。有效期不超过 5 分钟且不超过 grant 剩余时间。绑定时同事务用掉挑战与 bind 凭证、创建/复用 user、写 ownership/history；处理 phone 唯一键争抢，错误验证码的失败计数仍须保存。服务商未选，重试/幂等和外部发送失败办法待补，不伪报发送成功。养成身份与权限未定，不签发 touch，不从 ownership 推断操作者。

## 7. 网站入口配置

Nginx 是网站的接待入口：用户和管理网站各自限定能转交哪些地址。安全组按端口/IP 限制，不能在共享 443 端口上按域名单独拦管理网站，所以管理域名必须另配站点 IP 白名单。

下面只是骨架，真实证书、目录和 IP 需替换；不是完整可运行配置。上线前运行 nginx -t 检查。TLS 是 HTTPS 的加密连接，下面由 Nginx 接收它，再转交本机后端。

```nginx
# 置于 http {} 内；真实证书指令在 server 中另配。
# 同一 IP 的登录请求共享计数，平均每分钟5次；不限制整个管理后台。
limit_req_zone $binary_remote_addr zone=admin_login:1m rate=5r/m;
server {
    listen 443 ssl;
    server_name nfc.bumbum.cc;
    root /var/www/bumbum-frontend/nfc/dist;

    location = /api/admin { return 404; }
    location ^~ /api/admin/ { return 404; }
    location = /api/webhook/admin/scan {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location ~ ^/api/(tap|public|fashion|jewelry)/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /api/ { return 404; }
    location / { try_files $uri $uri/ /index.html; }
}
server {
    listen 443 ssl;
    server_name admin.bumbum.cc;
    root /var/www/bumbum-frontend/admin/dist;
    allow 192.0.2.10; # 文档示例地址，必须改成真实管理出口IP
    deny all;

    location = /api/admin/auth/login {
        limit_req zone=admin_login burst=4 nodelay;
        limit_req_status 429;
        error_page 429 = @login_rate_limited;
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location @login_rate_limited {
        default_type application/json;
        return 429 '{"status":"error","code":"rate_limited","message":"登录尝试过于频繁，请稍后重试"}';
    }
    location ^~ /api/admin/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /api/ { return 404; }
    location / { try_files $uri $uri/ /index.html; }
}
```

还要拒绝未知 Host、HTTP 跳转 HTTPS、配真实证书和请求体大小限制。应用只绑定回环地址，不能让外部绕过 Nginx 直连 Gunicorn；RDS 3306 不对公网开放。真实来源只信任这层 Nginx 覆写的 X-Real-IP，不能直接相信客户端自报的 X-Forwarded-For；示例也覆写 X-Forwarded-Proto。生产同域不启用 CORS。

NFC 页/API 不在日志记录完整 picc_data、cmac、token URL 或请求体；Referrer-Policy:no-referrer 表示跳转第三方时不告诉它原页面地址，防止泄露动态参数。

## 8. 配置与资料来源

配置名称和非敏感示例集中在 [.env.example](../.env.example)，秘密值留空。本机最小运行步骤见 [本地运行说明](LOCAL_DEVELOPMENT.md)。入口为 app:create_app，依赖固定版本在根目录 requirements 文件和前端 package-lock.json；main已包含云测试requirements-deploy.in/txt及Docker构建，固定Python 3.12.14、Node 24.19.0、Gunicorn 26.2.0（两个进程，关闭未使用的控制socket）和MySQL 8.0.46；不代表正式部署已验收。香港配置、证书及操作见[云测试手册](CLOUD_TEST_DEPLOYMENT.md)，不复制到本机启动说明。

| 配置 | 用途 |
|---|---|
| APP_ENV | 本机配置明确为 development；正式环境用 production（缺省值），强制管理来源为 HTTPS |
| DB_* | 数据库连接；本机默认127.0.0.1:33306，使用普通测试账号 |
| DEV_DB_ROOT_PASSWORD | 仅供本机Compose首次初始化，准备脚本生成，不交给后端 |
| CLOUD_DB_ROOT_PASSWORD | 独立云测试库的初始化管理密码；只给数据库容器，运行后端用普通测试账号 |
| MASTER_KEY_FASHION / MASTER_KEY_JEWELRY | 按项目计算 K0/K2/K3/K4 的根材料，不直接写卡 |
| SDM_META_KEY_V1 / SDM_META_KEY_VERSION | 全局 K1 与初始 v1 配置 |
| STORAGE_ENCRYPTION_KEY / STORAGE_KEY_VERSION | 包装 DEK 的独立存储密钥及版本 |
| IP_HASH_KEY | 给日志中的 IP、未知账号及第二阶段计数标识做带密钥指纹 |
| WEBHOOK_ADMIN_USERNAME | 扫描回调的Basic认证用户名，指定已有、启用且完成验证器设置的管理员；不是单独创建的默认账号 |
| WEBHOOK_SHARED_SECRET | 扫描回调的独立Basic认证密码，32字节随机值写成64位十六进制；不复用管理员密码，不放query或日志 |
| SMS_CODE_HASH_KEY | 第二阶段短信码的独立带密钥指纹 |
| ADMIN_TOTP_ISSUER | 验证器显示的公开发行方名称 |
| CORS_ORIGINS / ADMIN_ORIGIN | 开发来源总清单/单个管理网页地址；后者本机http://localhost:5174、香港测试https://test.bumbum.cc、正式https://admin.bumbum.cc，各自配置 |
| VITE_API_BASE_URL | 当前为 /api；开发由 Vite 转到本机5000端口，生产由 Nginx 转交；调用不重复带 /api，所有 VITE_ 值不得含秘密 |

各用途密钥独立，不与数据库密码或彼此复用。更换存储密钥/KMS 或芯片密钥时，各自按对应的恢复和失效规则执行，不仅改一项环境值就当成轮换完成。

云测试启动时，将BUILD_CA_BUNDLE指定的正常CA包（默认/etc/ssl/certs/ca-certificates.crt）校验并暂存为项目内.cloud-test/build-ca.crt，再由BuildKit临时挂载到依赖安装步骤，兼容Compose/Bake对目录外文件读取的限制。保留原CA信任和HTTPS校验；该目录排除Git及构建上下文，不将CA写入镜像。此证书包用于验证下载来源，与网站HTTPS私钥及业务密钥不同，不修改.env.cloud-test。

NFC.cool官方资料于2026-10-24读取：[开发说明](https://nfc.cool/developers/)确认identifier/date/content字段、真实NFC UID、兼容模式占位值、Basic认证先401挑战再携带凭证重发，以及失败后不自动重试；[Webhook功能说明](https://nfc.cool/features/webhooks/)说明NDEF读取触发、NFC/QR分别开关及Platinum订阅要求。cece提供版本7.30和可见配置项，当时尚无真实目标卡、订阅可用性及手机请求的测试记录；后续实测补充如下，官方说明不能替代实测。

2026-10-25最新实测：完全空白卡无回调后，cece同意先用NFC.cool批量写固定文本再扫描登记。6枚卡content均为cece，identifier为7字节冒号格式，均先401后200；最后一枚据cece确认已启用随机UID和SUN，提交4字节随机编号及带picc_data/cmac的内容，返回400。登记接口不解密SUN，不把随机编号当永久UID。随后cece提供后台6条记录截图并确认全部6枚重扫后无新增，明确验收通过；批量读卡会自动保存并回调，无需逐张点保存。验收不声称6次都是首次新增，也未测性能指标；原始卡号与动态参数不复制进文档。官方来源NFC scans (NDEF reads)，不能承诺完全空白卡触发；此前错误归属证据已撤回。

用户报告iOS 27.0.1；2026-10-25重新核对官方开发及Webhook说明，仍要求401与WWW-Authenticate的Basic认证挑战。已收到的服务器响应符合此约定；[App Store公开查询](https://itunes.apple.com/lookup?id=1249686798&country=cn)显示商店版本7.3.0，最低iOS 17，最低版本不代表所有新系统均已验证。用户版本口述7.30，尚无确切构建号；不能仅凭缺少认证头或版本号断言App缺陷。新旧请求按时间区分，后端警告也不能代替完整访问日志。

临时请求结构/原文监听及认证匹配诊断已按cece确认的收尾方案删除，不保留入口或挂载，不自动删除服务器旧Docker日志。日常只保留访问状态、业务审计和必要异常信息。来源升级先暂停登记写入并完整备份，002迁移增加字段；仅从唯一一条chip.register操作记录的合法source补齐历史来源，歧义或无证据保持unknown，显式保留原updated_at。DDL提交后若补齐失败，可重跑完成；不自动删除列或恢复备份覆盖后来数据。已有测试库升级命令只在对应操作手册维护。


[社区 sdm-backend 示例](https://github.com/nfc-developer/sdm-backend/blob/37585f0c76eded73798b936b17aa5e187075b78f/app.py#L222-L227) 展示先解密编号再取得验签密钥，仅供评估，不是已集成或通过测试的证明。[NXP AN12196](https://www.nxp.com/docs/en/application-note/AN12196.pdf) 是需核验的官方资料；此前研究未直接读取此 PDF，不能声称已按它验证参数。pylibsdm 仍是待评估候选，须核验版本、许可证、兼容性与正确答案。


## 9. 服装资料与启停实现（任务分支）

feat/fashion-item-profile基于main d3449d9；实现范围以[PRD](../PRD.md#412-本小步服装基础资料编辑与启停)、字段/返回以[契约](../API_CONTRACT.md#4-管理物品)为准，待人工验收未合并。新增GET物品详情、PUT服装资料、PATCH服装状态；无数据库迁移或新依赖，不创建用户端。

写入依次锁定管理员、会话和目标item，仅在服装非归档时继续。资料INSERT/重复键UPDATE仅列出五项字段，既有size_chart不读取回传、不比较、不改动；ItemView为兼容原返回结构仍可包含该既有属性，前端不展示。status检查有效名称，幂等重复不新增状态审计；业务修改、item.updated_at和审计一起commit，异常rollback。串行物品锁防止首次保存竞争，最后提交的整份可编辑资料为准，不实现编辑版本冲突检查。

前端api.ts保留默认GET/POST，显式扩展PUT/PATCH，继续Cookie/Origin/内存CSRF与超时。ItemProfileEditor独立维护加载、编辑基准、保存与故障，忽略已卸载组件的迟到读取；父组件在切换/查询/翻页/创建前确认未保存修改。保存后刷新当前列表筛选，列表错误不改报保存失败。图片只由浏览器按HTTP/HTTPS预览、referrerPolicy=no-referrer，不走后端下载。

request_json默认8192字节不变，仅PUT资料262144；云测试Nginx用准确路径正则对应256k，并继承管理IP限制，通用/api/admin/改普通前缀以允许该正则匹配，其余管理路由仍受原限制。以真实TLS网关测试允许/拒绝管理IP和长资料边界，不仅检查模板字符串。回退代码保留已保存资料，不能以整库恢复代替代码回退；已保存状态可能保留为active，但现阶段仍无用户验证入口。


## 10. 桌面管理端接入（任务分支）

feat/fashion-item-profile在1d897ad后复用cece上传Make源码的桌面框架、CSS变量和按钮/弹窗组件。仅管理端桌面，不包含手机H5或移动断点；登录页按同一视觉补建。保留现有React、TypeScript、Vite和npm，按package.json/lock固定Tailwind、Radix弹窗、Lucide及实际使用的辅助依赖；不复制Make专用Vite插件、pnpm锁、AI规则或部署脚本，不读取其站点配置或注入演示认证。

AdminLayout负责导航、真实total数量和未实现提示，LoginPanel继续持有登录状态，api.ts接口保护不变。RuntimeChecks复用health/ready；不把检查结果当业务或正式部署通过。ChipPanel和ItemPanel使用独立弹窗，保留原服务端分页/查询；服装编辑复用现有字段、权限和保存语义。登记错误与列表错误分别维护，打开登记弹窗不能清除列表失败。所有权等未实现操作仅展示提示，不发送业务请求。

body保留overflow:hidden，桌面内容区、侧栏、登录页、表格和弹窗内部滚动；导航及退出通过离开检查，保存中不切换，未保存修改先确认，登录失效直接隐藏管理数据。原有数据库和后端未改，字段/API定义仍以既有契约为准，人工步骤见[桌面管理端](ADMIN_DESKTOP.md)。回退可回到1d897ad并按其锁文件安装依赖，业务数据保留。
