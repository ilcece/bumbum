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

列表使用LEFT JOIN保留空项目记录，project=unassigned筛选c.project_id IS NULL；未分配不是第三个项目。首次绑定按既定锁顺序，空项目时在同一事务设为目标物品项目，已有项目严格匹配；后续解绑保留项目。未分配或未绑定不能生成chip_key，生成入口在事务内重查；密钥与配置实现见第14节，实际接口范围见API第0.4节。

已有库通过migrate_local.py先完整备份再执行001迁移：使用一条原子ALTER将project_id改可空、添加ck_chip_project_assignment，并用不同名称的_v2外键重建相同关联规则，避免MySQL同一ALTER重用旧外键名失败；不关闭外键检查。回退同样单条ALTER，已有空项目记录时提前拒绝。ready检查本次字段及外键/检查约束版本，未完成升级时503。命令只接受默认本机测试库，备份容器与实际连接须同一server_uuid；不擅自升级生产或导入备份覆盖数据。步骤见[本地运行第7节](LOCAL_DEVELOPMENT.md#7-已有测试库升级允许芯片暂不分配项目)。

锁定记录的意思是：在本次保存结束前，其他要修改同一记录的请求需要等待，避免两个请求各自认为“还没绑定”。

## 2. 芯片密钥与版本

同版本全局共享 K1、单芯片独立 K2 已获确认。K1 负责解密编号，K2 按 SDM 规则参与核验防伪码；K0 管理芯片，K3/K4 预留。项目根密钥只在服务器使用，K0/K2/K3/K4 按项目根密钥、UID、槽位和用途算出；不同项目和用途必须分开计算。具体计算方法称为 KDF，须固定实现、输入编码和正确答案测试，旧版随手写的 CMAC 输入公式不能直接投产。

芯片尚未分配项目时，不能选择根密钥、生成芯片密钥或写卡；未来用户验证入口也不能替它猜项目、尝试其他项目根密钥或签发tap_token。当前密钥流程要求项目确定且已绑定物品，见第14节；全局K1/独立K2的分工不变。

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

验证器及芯片秘密均使用cryptography 50.0.2；芯片使用分列信封格式，验证器原有JSON信封及函数保持兼容。

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
| CORS_ORIGINS / ADMIN_ORIGIN | 前者为预留总清单，当前未读取；后者为实际生效的管理网页地址，本机http://localhost:5174、香港测试https://test.bumbum.cc、正式https://admin.bumbum.cc，各自配置 |
| VITE_API_BASE_URL | 当前为 /api；开发由 Vite 转到本机5000端口，生产由 Nginx 转交；调用不重复带 /api，所有 VITE_ 值不得含秘密 |

各用途密钥独立，不与数据库密码或彼此复用。更换存储密钥/KMS 或芯片密钥时，各自按对应的恢复和失效规则执行，不仅改一项环境值就当成轮换完成。

云测试启动时，将BUILD_CA_BUNDLE指定的正常CA包（默认/etc/ssl/certs/ca-certificates.crt）校验并暂存为项目内.cloud-test/build-ca.crt，再由BuildKit临时挂载到依赖安装步骤，兼容Compose/Bake对目录外文件读取的限制。保留原CA信任和HTTPS校验；该目录排除Git及构建上下文，不将CA写入镜像。此证书包用于验证下载来源，与网站HTTPS私钥及业务密钥不同，不修改.env.cloud-test。

NFC.cool官方资料于2026-10-24读取：[开发说明](https://nfc.cool/developers/)确认identifier/date/content字段、真实NFC UID、兼容模式占位值、Basic认证先401挑战再携带凭证重发，以及失败后不自动重试；[Webhook功能说明](https://nfc.cool/features/webhooks/)说明NDEF读取触发、NFC/QR分别开关及Platinum订阅要求。cece提供版本7.30和可见配置项，当时尚无真实目标卡、订阅可用性及手机请求的测试记录；后续实测补充如下，官方说明不能替代实测。

2026-10-25最新实测：完全空白卡无回调后，cece同意先用NFC.cool批量写固定文本再扫描登记。6枚卡content均为cece，identifier为7字节冒号格式，均先401后200；最后一枚据cece确认已启用随机UID和SUN，提交4字节随机编号及带picc_data/cmac的内容，返回400。登记接口不解密SUN，不把随机编号当永久UID。随后cece提供后台6条记录截图并确认全部6枚重扫后无新增，明确验收通过；批量读卡会自动保存并回调，无需逐张点保存。验收不声称6次都是首次新增，也未测性能指标；原始卡号与动态参数不复制进文档。官方来源NFC scans (NDEF reads)，不能承诺完全空白卡触发；此前错误归属证据已撤回。

用户报告iOS 27.0.1；2026-10-25重新核对官方开发及Webhook说明，仍要求401与WWW-Authenticate的Basic认证挑战。已收到的服务器响应符合此约定；[App Store公开查询](https://itunes.apple.com/lookup?id=1249686798&country=cn)显示商店版本7.3.0，最低iOS 17，最低版本不代表所有新系统均已验证。用户版本口述7.30，尚无确切构建号；不能仅凭缺少认证头或版本号断言App缺陷。新旧请求按时间区分，后端警告也不能代替完整访问日志。

临时请求结构/原文监听及认证匹配诊断已按cece确认的收尾方案删除，不保留入口或挂载，不自动删除服务器旧Docker日志。日常只保留访问状态、业务审计和必要异常信息。来源升级先暂停登记写入并完整备份，002迁移增加字段；仅从唯一一条chip.register操作记录的合法source补齐历史来源，歧义或无证据保持unknown，显式保留原updated_at。DDL提交后若补齐失败，可重跑完成；不自动删除列或恢复备份覆盖后来数据。已有测试库升级命令只在对应操作手册维护。


[社区 sdm-backend 示例](https://github.com/nfc-developer/sdm-backend/blob/37585f0c76eded73798b936b17aa5e187075b78f/app.py#L222-L227) 展示先解密编号再取得验签密钥。后续已核对其派生代码、固定答案和MIT许可，并读取[NXP AN12196](https://www.nxp.com/docs/en/application-note/AN12196.pdf)核对公开向量及真实测试卡样本；复用决定及证据见[第14节](#14-测试卡密钥与配置方案)，不代表已经集成或完成服务端验收。pylibsdm不纳入本小步，避免与已有NFC.cool读写流程重叠。


<a name="9-服装资料与启停实现任务分支"></a>

## 9. 服装资料与启停实现

实现范围以[PRD](../PRD.md#412-本小步服装基础资料编辑与启停)、字段/返回以[契约](../API_CONTRACT.md#4-管理物品)为准；任务与历史分别见[TODO](../TODO.md)、[CHANGELOG](../CHANGELOG.md)。新增GET物品详情、PUT服装资料、PATCH服装状态；无数据库迁移或新依赖，不创建用户端。

写入依次锁定管理员、会话和目标item，仅在服装非归档时继续。资料INSERT/重复键UPDATE仅列出五项字段，既有size_chart不读取回传、不比较、不改动；ItemView为兼容原返回结构仍可包含该既有属性，前端不展示。status检查有效名称，幂等重复不新增状态审计；业务修改、item.updated_at和审计一起commit，异常rollback。串行物品锁防止首次保存竞争，最后提交的整份可编辑资料为准，不实现编辑版本冲突检查。

前端api.ts保留默认GET/POST，显式扩展PUT/PATCH，继续Cookie/Origin/内存CSRF与超时。ItemProfileEditor独立维护加载、编辑基准、保存与故障，忽略已卸载组件的迟到读取；父组件在切换/查询/翻页/创建前确认未保存修改。保存后刷新当前列表筛选，列表错误不改报保存失败。图片只由浏览器按HTTP/HTTPS预览、referrerPolicy=no-referrer，不走后端下载。

request_json默认8192字节不变，仅PUT资料262144；云测试Nginx用准确路径正则对应256k，并继承管理IP限制，通用/api/admin/改普通前缀以允许该正则匹配，其余管理路由仍受原限制。以真实TLS网关测试允许/拒绝管理IP和长资料边界，不仅检查模板字符串。回退代码保留已保存资料，不能以整库恢复代替代码回退；已保存状态可能保留为active，但现阶段仍无用户验证入口。


<a name="10-桌面管理端接入任务分支"></a>

## 10. 桌面管理端接入

桌面管理端复用cece上传Make源码的桌面框架、CSS变量和按钮/弹窗组件。仅管理端桌面，不包含手机H5或移动断点；登录页按同一视觉补建。保留现有React、TypeScript、Vite和npm，按package.json/lock固定Tailwind、Radix弹窗、Lucide及实际使用的辅助依赖；不复制Make专用Vite插件、pnpm锁、AI规则或部署脚本，不读取其站点配置或注入演示认证。

AdminLayout负责导航、真实total数量和未实现提示，LoginPanel继续持有登录状态，api.ts接口保护不变。RuntimeChecks复用health/ready；不把检查结果当业务或正式部署通过。ChipPanel和ItemPanel使用独立弹窗，保留原服务端分页/查询；服装编辑复用现有字段、权限和保存语义。登记错误与列表错误分别维护，打开登记弹窗不能清除列表失败。所有权等未实现操作仅展示提示，不发送业务请求。

body保留overflow:hidden，桌面内容区、侧栏、登录页、表格和弹窗内部滚动；导航及退出通过离开检查，保存中不切换，未保存修改先确认，登录失效直接隐藏管理数据。原有数据库和后端未改，字段/API定义仍以既有契约为准，人工步骤见[桌面管理端](ADMIN_DESKTOP.md)。回退可回到1d897ad并按其锁文件安装依赖，业务数据保留。


## 11. 最小脱敏诊断

诊断采用core/diagnostics.py，以专用Python日志器输出单行JSON到标准错误，不加日志服务或依赖。记录允许字段，路径用路由模板不带实际ID/查询参数；仅项目内Python文件相对路径和行号，最多12个位置，不调用str(error)、exc_info或格式化堆栈正文。编号由服务端生成、每请求复用，忽略客户端自报编号；日志器失败仍保留错误响应编号且不改变事务结果。通用500、MySQL异常503及ready捕获的数据库异常使用此机制；预期失败不作为程序异常重复记录。接口见[错误结构](../API_CONTRACT.md#02-怎么看返回结果)。

前端ApiError接收合法24位十六进制编号，拼入原消息；运行检查和概况失败也显示编号。没有编号时保持原提示，不猜测请求是否保存成功。记录编号不等于有权分享原始日志，提交/部署及人工验收状态见TODO。

## 12. 产品规则的技术对应位置

PRD第4.1节只维护操作、业务限制和验收结果；移出表名、字段名和状态编码不改变现有实现或接口。技术实现仍须读取下面的定义，不依据中文页面文字猜字段或删除兼容规则。

| PRD中的业务概念 | 技术对应及定义位置 |
|---|---|
| 芯片编号、物品编号、款式编号 | chip_uid、item_uid、sku_code；类型、长度及格式见[接口说明](../API_CONTRACT.md#3-管理芯片第一阶段)、[物品接口](../API_CONTRACT.md#4-管理物品)和schema对应表 |
| 待绑定、已绑定、停用、丢失 | pending、bound、disabled、lost；转换规则见[技术说明第2.2节](../TECH_SPEC.md#22-芯片什么时候可用)，枚举及关联约束见schema |
| 草稿、启用、停用、归档 | draft、active、disabled、archived；本轮已实现的服装转换范围见[物品接口](../API_CONTRACT.md#4-管理物品)和本附录第9节，不能把长期允许的转换都当成已开放 |
| 草稿创建及未填写资料 | 只创建item；不创建fashion_item_profile/jewelry_item_profile资料行，接口profile组装为null。item.create审计与业务同事务；编号冲突的HTTP/code见物品接口，不能沿用芯片重复返回原记录的策略 |
| 可空款式及资料清空 | sku_code省略/null/去空白后空字符串统一存NULL；资料可选文字清空为NULL、图片为空数组，整份资料PUT省略可选项会清除对应值。具体输入与字段以物品接口为准 |
| 服装编辑及状态记录 | 保存仅涉及本次五项资料，不读取回传、不比较、不改size_chart；业务修改、item.updated_at及审计一起提交。字段和锁顺序见第9节，既有ItemView兼容属性保留 |
| 列表最新在前、工作台真实统计、内部滚动 | 物品列表按id倒序；概况使用接口total，不用当前页计数；body保留overflow:hidden，各内容区独立滚动。实现说明见物品接口及第10节，不因PRD去掉代码写法改变界面行为 |

首次绑定沿用POST /api/admin/chips/{id}/bind-item及item_id；路径与目标ID为正整数，拒绝以业务编号代替内部ID，不接收额外项目/状态/来源。精确类型边界、上限、锁顺序和错误优先级见API第3.1节及本附录第13节。项目分配、chip.item_id、chip_status与审计必须同事务，依托uk_chip_item及项目复合外键防止冲突；是否需迁移须核对实际旧库，不重建数据库。

两项目共用绑定规则、非归档物品可绑定、本步不提供解绑/换绑的范围已由cece确认；具体页面和验收以[绑定PRD](../PRD.md#414-本小步芯片绑定物品)为准。这里不定义解绑或换绑的新接口，也不把用户对范围的确认等同于已授权业务开发。

<a name="13-芯片绑定物品技术方案待审核"></a>

## 13. 芯片绑定物品实现

本节定义[已确认绑定PRD](../PRD.md#414-本小步芯片绑定物品)的实现：首次绑定及查询反馈。只包含首次绑定，不包含解绑、换绑、芯片启停、密钥、写卡或所有权，不增加运行服务、依赖或配置。任务与验收状态分别见TODO和CHANGELOG。

### 13.1 最小方案及实际依据

已有字段和唯一约束足以表达绑定：chip保存关联和状态，item保存物品身份，admin_audit保存操作。现有ChipView已含item_id/item_uid，物品列表已有项目、状态、编号及资料。仅开放已设计的一个POST入口，复用两个现有GET列表；不用新增候选专用接口、芯片详情页或新的关联表。

| 现有证据 | 本步怎样复用 |
|---|---|
| core/admin_chips.py及core/chip_registry.py | 沿用芯片Blueprint、CHIP_VIEW与chip_view序列化；不复制登记和UID归一化逻辑 |
| core/admin_auth.py | 复用请求来源、JSON、Cookie、CSRF以及lock_admin_session；不加认证步骤 |
| core/admin_items.py | 沿用GET物品列表及现有分页/关键词，不改变创建、资料及启停 |
| schema的uk_chip_item、项目复合外键和CHECK | 与事务内行锁共同保证唯一绑定及项目一致；不靠页面隐藏或只做一次普通查询 |
| frontend/admin/src/ChipPanel.tsx、AdminUI.tsx | 使用现有桌面表格、EntryDialog及离开检查；新增单一职责绑定弹窗，登记保持原行为 |

取舍：候选列表可能包含已被其他芯片占用的物品，本步不新增“仅可绑定”查询参数或改列表结构；归档行不可选，实际占用与并发仍在POST时重新检查并明确提示。这样少改一个接口，代价是有些冲突在确认时才发现，符合已确认PRD。

### 13.2 接口与输入

POST /api/admin/chips/{id}/bind-item，仅接收一个必填JSON字段item_id。成功HTTP 200，data直接为更新后的ChipView，不另包chip/is_new，不新增返回属性。精确请求、返回及错误表集中见[绑定接口](../API_CONTRACT.md#31-绑定物品接口)；本节只维护实现顺序。

后端沿用现有数字路径路由：可匹配数字路径但id为0或超过BIGINT UNSIGNED范围返回400；负数、小数或非数字路径不匹配，沿用404，不新增通用路由解析器。item_id严格要求JSON整数，范围1至18446744073709551615；bool、浮点数、字符串、null、缺字段、未知字段、重复查询参数或额外查询参数拒绝。请求上限沿用8192字节，无force、confirm、project、chip_status或来源字段；页面勾选确认只作界面防误操作，服务端靠规则检查。

当前前端ID类型为number，绑定提交前额外检查芯片和候选物品ID为正的Number.isSafeInteger。超出精确范围明确阻止操作并反馈，不四舍五入、不猜ID；本步不把全项目ID契约改为字符串。后端独立校验，不因页面已检查就信任输入。

### 13.3 后端保存顺序与并发

新增core/chip_binding.py承载绑定事务，在core/admin_chips.py增加一个路由并调用；服务返回ChipView，由路由组装JSON。新模块不导入admin_items，避免现有admin_items导入admin_chips分页函数形成循环。物品只读取必要身份/状态，不复制资料定义。

1. 完成现有请求保护，校验路径及JSON后显式begin。
2. 复用lock_admin_session，按“管理员 → 会话”锁定并重查有效性。
3. 以目标item_id锁定item单行，读取id/project_id/status；不存在404。只锁物品行，不把项目或资料表一起锁住。
4. 以芯片id锁定chip单行，读取绑定、项目、状态等必要列；不存在404。
5. 在锁内检查芯片：disabled/lost返回invalid_state；bound或已有item_id返回already_bound；仅pending且未关联可继续。再检查物品不是archived、项目匹配；使用项目code解释业务，不硬编码项目数字ID。
6. 一条UPDATE同时写入芯片project_id、item_id、chip_status='bound'及chip.updated_at。目标物品占用由uk_chip_item唯一索引在UPDATE时最终裁决，包括其他disabled/lost芯片保留的关联；命中冲突回滚并报item_already_has_chip，不能用旧列表判定未占用。
7. 原项目为空才首次确定，非空且相同则保留；不改物品行、资料、item.updated_at、登记来源、批次、密钥、provisioned_at或计数器。在同一事务写chip.bind_item审计，并读取/组装更新后的ChipView。
8. 响应内容准备好后commit，提交确认成功才返回200。

整体锁顺序为“管理员 → 会话 → 目标物品 → 芯片”，与既有物品修改顺序一致。目标占用不额外做“查空即锁”的索引范围查询，减少无关物品因索引间隙锁相互等待；以单行物品锁及唯一索引检查保证结果。相同物品的绑定在物品行串行，相同芯片的绑定在芯片行串行；唯一索引与复合外键提供最终保护。一次只操作一个物品，不锁全表，不引入分布式锁或Redis。

仅在这条chip UPDATE发生1062唯一冲突时映射为409 item_already_has_chip；不能把事务内任意1062（例如审计写入故障）都误报成物品占用。非预期约束/数据库异常沿用503及脱敏错误编号，记录失败时也不打印SQL或参数。死锁/锁等待超时先撤销本事务，返回503，不在服务端或浏览器自动重试写操作。

提交前异常执行rollback，不返回成功、不写孤立成功审计。commit阶段若连接断开或回执丢失，数据库可能已提交，rollback不能保证撤销已提交结果；此时返回失败或客户端超时都属于“结果尚未确认”，必须查询。测试须单独覆盖这个情况，不能断言每个503都未保存。

### 13.4 操作记录与保留

admin_audit.action为chip.bind_item，target_type为chip，target_id为芯片内部ID字符串，admin_id来自当前管理员；ip_hash复用现有指纹。detail最小保存item_id、project（目标code）、previous_project（原code或null）和from_status/to_status，不保存请求正文、Cookie、秘密或原始IP。项目code通过现有项目记录读取，不由客户端决定。

每次真正建立关联只有一条成功审计；重复或业务拒绝不新增变更审计。不写ownership或ownership_history，因为此操作不产生或转移所有权。原登记审计、来源、资料及其他历史保留；本步不增加操作记录页面或物理删除入口。

### 13.5 前端组件与状态

| 改动位置 | 具体改动 |
|---|---|
| api.ts | 新增bindChipItem(chipId,itemId)，复用现有request、Cookie/CSRF和错误编号；不改其他接口 |
| ChipPanel.tsx | 显示已绑定物品编号；符合条件的行提供“绑定物品”，其他行显示状态原因；保持登记入口及导出/更多等未实现提示的边界 |
| 新增BindItemDialog.tsx | 自己管理候选查询、单选、确认、提交和结果未确认状态；使用现有EntryDialog，无移动端或新视觉系统 |
| 现有局部样式 | 只补候选表格、确认区和内部滚动；保留body overflow:hidden，不恢复已撤销的全局交互修改 |

弹窗接收当前ChipView。项目已确定则固定该项目，未分配可选择服装/饰品；GET /admin/items每页20条，沿用编号/款式包含式查询，不新增名称搜索。绑定查询固定unbound_only=true；admin_items.list_items使用关联chip.item_id的NOT EXISTS，在COUNT和分页SELECT中复用相同条件，不按芯片状态放回已占用物品。普通物品列表不传该参数；无新表、字段、标志或逐件查芯片请求。归档未占用行仍显示原因并禁选，其余状态规则不变；候选名称未填则明确标注。筛选只是当前查询结果，不预占；查询后竞争仍由原绑定事务和唯一约束拒绝，不能去掉提交时检查。

区分编辑中的筛选、已提交查询和所选目标。修改条件立即清除选择/勾选并禁止确认，直到点击查询取得对应结果；换页同样清除选择。请求用递增序号或effect清理忽略旧响应，防止慢请求覆盖新查询；401统一隐藏管理数据，查询错误不伪装空列表，旧候选不继续可选。

只有候选已选、状态可选、确认框勾选、没有待查询改动且未提交时才允许确认。点击后立即设忙，禁用字段、重复提交、关闭、Escape和页面导航；客户端状态之外还用请求中的引用标记防止同一渲染周期连点。页面一次只开登记或绑定一个弹窗，不能叠开。

登记和绑定的忙/未保存状态汇总到ChipPanel既有registerLeave及beforeunload检查；绑定仅在已选择目标时提示放弃，不因只输入查询文字就强制确认。复用父级统一离开检查，不让两个子组件相互覆盖registerLeave。现有登记的CSRF刷新行为不顺带重写；本绑定按已确认PRD提示刷新页面后重新核对，不自动刷新并重发。

绑定200后关闭弹窗，把响应中的UID与物品编号写入父组件成功卡片；重置芯片筛选项目/状态，以完整UID查询第一页。卡片不依赖列表刷新成功；查询失败单独显示，不能再次写入“补偿”。成功卡片不新增Toast基础设施。

### 13.6 不确定结果的恢复

- 400/404/409等明确业务拒绝显示原通俗消息，保留选择供核对；冲突提示重新查询，禁止凭旧结果覆盖已有关系。
- 401按既有流程回登录；csrf_failed提示刷新后重新核对，不自动重发。
- 超时、网络中断、不可读响应、500/503统一不宣称“未保存”，显示错误编号（若有）和“结果尚未确认，请查询此芯片”；冻结原目标，不自动改选或重试。
- “查询此芯片”复用GET /admin/chips，关键词为完整UID；核对返回id、UID、状态及item_id。bound且目标相同，显示已查到保存结果；目标不同，显示当前真实关联并提示冲突，不称本次绑定成功。
- pending只代表当前可见尚未绑定，不证明原请求已经终止。继续提示原请求可能处理中；由管理员重新核对后才可手动重试同一目标，不自动放开换绑。重复请求由服务端拒绝且不新增成功审计。
- 查询失败继续保持“未确认”；查询读到disabled/lost则禁止提交。没有结果时不擅自解锁、改库、回滚其他操作或生成新的写请求。

### 13.7 数据库、旧库及部署

本方案不改表、不写新迁移、不重建数据库。依托现有chip.item_id全局唯一、item项目组合键、项目复合外键、状态CHECK及admin_audit；现有001/002升级后应保留这些定义。实施时在专属临时MySQL验证空库和旧库升级结果；若约束缺失或定义不符，暂停受影响验证并说明，不用删库或关闭外键解决。

当前ready检查表、项目及既有两次升级条件，但不等同于完整绑定约束检查；不能只凭ready=200断言所有约束均已核验。部署现有环境时须按授权只读核对约束和升级记录，本轮不连接该环境。发现确需新增迁移时重新对齐。

沿用8192字节请求限制、现有管理员Nginx路径、日志和部署方式；不改env、依赖、Dockerfile或域名。绑定只保存后台关系，能在合成账号/临时库验收，不依赖真实卡核验。用户端停用效果、真实写卡和动态验证均不属于本步通过范围。

### 13.8 测试、交付与回退

| 检查组 | 技术通过条件 |
|---|---|
| 输入与权限 | JSON类型/边界/额外字段、未登录/失效/撤销会话、Origin/CSRF；打开弹窗后的旧登录权限不能继续写入；错误结构和编号符合契约 |
| 正常与业务拒绝 | 两项目、空/已定项目、非归档三状态正常；缺记录、归档、跨项目、disabled/lost、重复同目标、已占用均拒绝；列表可查且物品状态不变 |
| 独立管理员并发 | 至少两个不同管理员/会话、独立连接同时争抢同芯片或同物品，只有一个成功及一条审计；不能仅以同账号被管理员行锁串行的结果证明并发保护 |
| 原子保存和故障 | 审计/提交前写入失败全撤销，唯一索引竞争正确映射，死锁/锁等待失败不重发；注入“已提交但回执丢失”并查询到实际绑定，证明失败不等于没保存 |
| 保留与升级 | 首次来源、批次、物品资料/状态/时间、原密钥、写卡时间/计数器不改；空库与已有迁移结果约束一致；不写所有权历史 |
| 浏览器 | 选择/分页/旧响应、确认重置、防连点、关闭/离开保护、成功与列表失败分离、超时查询及同目标/异目标结果、401隐藏、CSRF不重发、矮桌面滚动 |

新增tests/test_chip_binding.py，扩展现有tests/test_admin_browser.py，不新建另一套浏览器框架或工作流。并发屏障设在发请求前，不放在已经持有互斥物品锁的位置，以免测试人为制造死锁。只清理测试自己创建的数据库、账号及样例；不连接现有业务库，不要求cece伪造状态或停库。实施前核对现有“未实现地址”断言，只更新新开放入口对应断言。

完成后跑绑定专项、全量独立MySQL及浏览器回归、前端类型/构建、文档链接与差异检查；具体每次检查结果在CHANGELOG记录，不把配置和测试存在当作检查通过。人工验收沿用PRD五组，准确步骤补进现有CHIP_REGISTRATION/ADMIN_DESKTOP手册，不为本步另建操作记录文件；命令仍只维护在LOCAL_DEVELOPMENT。API第0.4节记录实际可用范围，TODO与CHANGELOG分别记录任务状态和证据。

业务实现从最新main建立任务分支，按已确认需求和方案交付。交付后按cece授权提交/推送，验收与合并分开；不自动部署。没有表变更时，代码问题用反向提交回退代码，不恢复整库；已保存绑定保留且旧版ChipView兼容，不因回退解除绑定或覆盖后来资料。业务误绑定不能用代码回退纠正，受限解绑另立小步。

## 14. 测试卡密钥与配置方案

本节定义已确认方案及实现规则；当前任务和验收状态只看TODO，接口可用范围看API第0.4节。本小步完成“已绑定芯片→生成并加密保存→受控查看→NFC.cool配置→读数核验→记录配置完成”。不包含用户触碰接口、手机资料页、批量生产、密钥轮换或多版本兼容。批量导出及完整密钥管理页面已保留为后续待排期需求，不因本步未做而删除。

### 14.1 已有证据与复用来源

以下A/B字母及读数是目标配置前的信息收集记录；后续修正与验收证据见CHANGELOG，当前状态见TODO，不以早期代号替代实际UID核对。

- cece提供设备为iPhone 14 Plus、iOS 27.0.1、NFC.cool 7.3.0及Platinum全部功能，无其他读写工具；提供两枚NTAG424 DNA。NTAG213/215只用于登记回调对照，不能替代SUN测试。
- A卡两条截图读数经独立解密/验签，真实UID与导出一致，计数1→2；先通过NXP AN12196公开答案核对计算方法。错误防伪码及错误K2对照未通过。七张截图全部属于A卡；卡上版本字节00不等于密钥仍为出厂值。
- B卡由cece自行配置目标域名及/tap、加密SUN、Key 1/2和五个槽位密钥后提供CSV及读数；独立验签通过，计数12→13。cece确认后一条来自系统触碰通知打开浏览器，随机UID未开启。A卡随机UID已开启。两卡分别通过不等于共享K1通过：现有两卡K1不同、K2不同，尚未采用系统目标密钥。
- App能配置文件权限及简化SUN选项，没有找到完整SDM偏移显示。现有样本匹配AES模式、UID/计数镜像和零长度MAC输入规则；并未读回底层偏移。CSV有旧地址或缺少SUN/URL列的情况，原因未证实，不直接断言App故障，不当完整恢复备份。失败次数限制的实际生效值仍未确认。
- 以上是本地离线计算及cece操作证据，不是已部署的服务端或手机资料页闭环。秘密、完整动态链接及附件原文不入源码、手册或测试夹具；合成向量另建测试。

复用来源固定为[sdm-backend提交37585f0c76eded73798b936b17aa5e187075b78f](https://github.com/nfc-developer/sdm-backend/tree/37585f0c76eded73798b936b17aa5e187075b78f)：[libsdm/derive.py](https://github.com/nfc-developer/sdm-backend/blob/37585f0c76eded73798b936b17aa5e187075b78f/libsdm/derive.py)的derive_tag_key及[tests/test_kdf.py](https://github.com/nfc-developer/sdm-backend/blob/37585f0c76eded73798b936b17aa5e187075b78f/tests/test_kdf.py)固定答案。保留MIT版权和许可、来源提交与修改说明；不使用legacy派生。它是社区具体实现，不称为NXP官方标准KDF。

保留上游HMAC-SHA256、槽位区分常量、字节顺序、截断及AES-CMAC步骤，使用现有cryptography 50.0.2和标准库适配，不新增PyCryptodome。正常输入结果须与上游公开答案完全一致；生成入口拒绝全零根密钥，不沿用全零输入返回全零卡密钥的兼容分支。K1不用上游derive_undiversified_key，仍独立安全随机生成。现有secret_storage.py的两层AES-GCM方式可复用，但芯片AAD及分列保存另做适配，不改变验证器信封格式。

### 14.2 生成、保存与最小页面

沿用第2、3节：项目根密钥分别独立，K0/K2/K3/K4按真实7字节UID及槽位派生；同版本全局K1共享。带冒号UID文字先规范化为二进制，不直接将展示文字送入算法。16字节根密钥/K1使用独立长度校验，不套用认证模块要求32字节秘密的读取函数；缺失、格式错误或不合格配置只关闭密钥功能，不影响已实现的登录/登记/查询。

本步从已有绑定进入；未分配项目、未绑定或不可用状态不得生成。芯片密钥存在则409 already_exists，不覆盖、不自动重算；不接受force。生成与审计同事务，返回结果不含秘密，不能同时标记写卡完成。查看须有效登录、CSRF和confirm=true，先保存审计再返回K0–K4及URL模板，禁止缓存；页面提醒K1涉及同版本所有卡，关闭弹窗/退出清除内存，不进localStorage或日志。

本机首次空配置准备及重启步骤只在LOCAL_DEVELOPMENT第10节维护；云Compose显式传递可选项目根密钥/全局K1及版本，云准备脚本不生成它们，未配置时只关闭密钥功能。云环境启用、备份和容器重新加载按CLOUD_TEST_DEPLOYMENT第11节另行授权，不能复制本机.env或用初始化代替恢复。

芯片列表仅增加生成、受控查看、配置确认的必要弹窗，不扩展完整管理页面；批量导出另排期。复用现有ChipView的keys_generated及provisioned_at区分已生成与已核验。项目配置版本v1与芯片版本字节00分别解释，本步不为显示一致而改写卡上版本。

### 14.3 配置确认与数据库

已有chip_key加密字段/版本、chip.provisioned_at、last_verified_counter及admin_audit足够，本步不改表、不迁移。接口路径、精确JSON和错误结构以API_CONTRACT为准；confirm-provisioning提交两条读数及management_confirmed=true。chip_keys.py共用事务，sdm_derivation.py保留上游正常输入计算；secret_storage.py增加芯片分列信封及AAD适配。当前项目根密钥重新派生结果与保存的五项秘密逐一恒定时间核对，K1/根密钥被替换或密文损坏时503，不返回秘密。生成、查看、确认审计分别为chip.generate_keys、chip.view_keys、chip.confirm_provisioning。

两条读数都使用保存的目标K1/K2核验，检查PICC布局、UID等于目标芯片、计数递增；不接受客户端传密钥。确认过程中按管理员→会话→物品→芯片锁定重查，核对原关联、项目、状态和密钥版本未变；完成时间、第二条读数作为计数基线及审计一起提交。失败不留半完成；重复确认不重置计数、不成为重配入口。确认不发tap_token、不自动启用物品；后续用户验证必须使用更大的计数。审计只记录必要身份、配置版本、工具及固定核验结果，不保存密钥、读数正文或完整URL。

当前确认审计固定标注system_checks=two_sun_readings、management_confirmed_by_admin=true，不伪造工具版本自动读回；工具及手工步骤按本手册记录。读数计数可跳号，第二条若已达到最大值则拒绝，避免配置完成后无新读数可用。重复确认409已配置；提交回执丢失后查询ChipView的keys_generated/provisioned_at，不能声称回滚已提交结果。

ChipKeysDialog与绑定弹窗互斥，复用父级离开/忙碌保护；写入或查询时禁止关闭。接口超时/503/坏响应冻结写入，须先查询实际记录，再由人决定是否重试；403口令失效提示刷新，不自动换口令重发；401清除内容并隐藏管理端。新读数填写或发起请求时清除展示密钥，关闭/离开不持久保存；页面拒绝非目标域名/tap或重复参数链接。失败截图额外隐藏data-private中的密钥和动态链接，不能保存网络trace或原文。

SUN读数只证明相关K1/K2和消息匹配，不证明K0/K3/K4或全部管理权限正确。K0认证及权限需cece按操作说明确认；记录中区分系统验签与人工确认，不能把操作者确认伪装成硬件自动读回。基础加密/事务规则沿用第3、5、6节，不将离线样本或生成记录当作provisioned_at。

### 14.4 NFC.cool操作与恢复边界

基础地址固定https://nfc.bumbum.cc/tap，SUN加密、元数据Key 1、文件Key 2、不启用enc；工具自动计算偏移，再以独立读数核验。CC/NDEF免费读取，写入及修改设置由K0管理；专有文件本步不用，权限收至K0，避免预留K3实际获得额外文件权限。保留AES，不切换LRP，不改永久性设置；随机UID保留各卡现状，不为本步统一。App失败次数限制显示值不视为生效读回，不通过故意错误认证测试。

A/B都已经修改过密钥，不按出厂卡处理。先安全保存当前有效凭证、现有配置及通过的读数；先一枚后另一枚，以UID核对，字母和批次只作标签，保留未操作卡作对照。NFC.cool选择十六进制方式原样输入后台32位密钥，不用会转换密钥的口令方式；换钥时当前认证值与目标新值分开。逐步确认操作，K0最后更换，并确认新K0可认证；中途失败停止，不盲重跑整个CSV、不猜默认密钥。数据库和芯片不能原子提交，代码回退不能恢复实卡；只有各步结果和恢复凭证清楚才安排改写。具体改卡步骤另行确认，本方案不授权立即写卡。

### 14.5 验证、文档与交付

五组验收：生成/重复保护及无明文保存；受控查看/审计/退出清理；B卡系统触碰的两条正确读数；错误卡/防伪码/计数/数据库故障及重复确认保护；A/B共享K1、独立K2对照及已有功能回归。只有两枚卡时不宣称跨项目三卡硬件对照完成；其余组合先由合成测试覆盖，硬件证据另列。

构建时用上游公开答案及合成密钥、独立临时库验证派生、加密防篡改、权限和事务；补充浏览器检查，检查结果按实际记录。接口精确请求/返回在API维护，技术在本节，人工步骤补进现有真实卡手册，状态只在TODO，重要决定与证据在CHANGELOG。更新受影响的配置说明，不读取真实.env；无schema、运行服务或第二套加密依赖变更。构建从实际main和绑定验收状态核对基线，不默认待验收功能已合main；提交、推送、合并和部署各按授权执行。
