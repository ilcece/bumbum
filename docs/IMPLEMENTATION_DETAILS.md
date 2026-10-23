# 技术附录：写代码时要遵守的精确规则

这是 [TECH_SPEC](../TECH_SPEC.md) 的组成部分。cece 可以先读正文理解流程，按需查这里；AI 实现数据库、安全、认证和部署时必须读取对应章节。这里保留精确参数，并先解释它们在防什么问题。本次只调整写法和资料位置，没有修改已有业务与安全规则。

## 1. 编号与数据库保存规则

目的是让同一芯片、物品和所有者不会因写法不同或请求同时到达而重复出现。

| 项目 | 精确规则 |
|---|---|
| 项目 | code 仅 fashion/jewelry；业务资料类型须与项目一致，不给 jewelry 写 fashion profile |
| 芯片编号 | chip_uid 为 7 字节，输入统一成冒号分隔的大写十六进制 |
| 物品编号 | item_uid 用 FASH-YYYY-NNNNNN / JEW-YYYY-NNNNNN，创建时提供，前缀匹配项目，之后不可修改 |
| 唯一绑定 | chip.item_id 可空且唯一；复合外键检查项目；已关联物品不物理删除 |
| 当前所有者 | active_item_id 仅在 is_active=1 时映射 item_id，唯一索引限制一条有效绑定；历史可以多条 |
| 解绑 | 同时设置 is_active=0 和 unbound_at；不删除历史、密钥和已接受计数器 |
| 流转 | bind_source 只在 ownership；history 保存 from/to、action、note、时间；转赠只写一条 transfer 历史 |
| 同时修改 | 事务中先锁物品，再锁芯片/有效 ownership；多个物品按 id 升序。检查、修改和审计一起提交；失败全部撤销 |
| 争抢或死锁 | 给出契约错误，不向前端泄露 SQL/堆栈；只有可重试的事务做有次数上限的重试 |
| 存储引擎和版本 | InnoDB，MySQL >= 8.0.16，utf8mb4；实际执行 CHECK 约束 |
| 时间 | 每个数据库连接初始化 time_zone='+00:00'；DATETIME/TIMESTAMP 按 UTC 理解；接口输出 ISO 8601 UTC |
| 建表/升级 | schema 只作空库初始化；已有数据库单独迁移，先备份，说明升级、验证和回滚/恢复，未经授权不执行生产变更 |

锁定记录的意思是：在本次保存结束前，其他要修改同一记录的请求需要等待，避免两个请求各自认为“还没绑定”。

## 2. 芯片密钥与版本

同版本全局共享 K1、单芯片独立 K2 已获确认。K1 负责解密编号，K2 按 SDM 规则参与核验防伪码；K0 管理芯片，K3/K4 预留。项目根密钥只在服务器使用，K0/K2/K3/K4 按项目根密钥、UID、槽位和用途算出；不同项目和用途必须分开计算。具体计算方法称为 KDF，须固定实现、输入编码和正确答案测试，旧版随手写的 CMAC 输入公式不能直接投产。

| 配置或字段 | 如何使用 |
|---|---|
| SDM_META_KEY_V1 | 独立安全随机生成 16 字节，写成 32 位十六进制；同版本跨项目相同。不用全零、项目根密钥或其他用途密钥替代 |
| SDM_META_KEY_VERSION | 初期只支持 v1。缺失、格式错误或不支持版本时，阻止相关功能启用，不能使用默认秘密兜底 |
| K1 加载 | 可在启动时加载只读配置到受控进程内存，不逐请求查库；不写仓库、普通日志；限流和业务变化仍保存到数据库 |
| chip_key.key_version | 不可变的 SDM 配置版本；初始配置 v1 固定对应全局 K1 v1 |
| master_key_version | K0/K2/K3/K4 所属项目根密钥版本，不代表 K1 版本 |
| storage_key_version | 包装数据库秘密所用的存储密钥版本，不代表芯片密钥版本 |
| encrypted_keys | 保存 K0–K4 的加密 JSON。K1 是对应全局版本的加密副本；生成时核对统一来源，不能每枚卡随机生成 K1，也不能读旧卡时偷偷换为新 K1 |

换密钥也叫轮换：必须另定新配置版本、固定的版本对应关系、旧卡更新和恢复办法，必要时另写数据库升级。不能把 v1 的实际密钥换掉还叫 v1；存储密钥旧版本在重新加密完成前也不能丢。初期只有一把 K1；以后若同时支持多个 K1 版本，候选数量必须有限，并核对记录版本、完整防伪码且只接受唯一匹配。不会遍历项目或全部芯片密钥。

SDMMetaRead 应配置为 K1，SDMFileRead 配置为 K2；这些名字分别表示“解密芯片信息”和“读取/核验 SDM 数据所用密钥”。实际管理认证、ChangeKey（换钥匙）、写文件和改设置的权限要查 NXP 资料并实测，不能因为名字是“元数据密钥”就假定 K1 没有其他权限。

全局 K1 泄露影响该版本所有芯片的编号/读数隐私；正确分开的 K2 不应随之泄露。查看密钥要求 full 登录、确认、先保存审计、Cache-Control:no-store（不缓存），界面提醒全局范围。列表不展示密钥，前端不长期保存。禁止 force=true 覆盖已有记录；重复生成返回 already_exists，真正换钥匙另定流程和计数器处理。

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

chip_key 使用 encrypted_keys、nonce、dek_ciphertext、dek_nonce、storage_key_version 分列保存。验证器秘密 totp_secret_encrypted 则保存完整 UTF-8 JSON 信封：format_version=1、algorithm=AES-256-GCM、storage_key_version，以及以 Base64（将二进制转成文字）表示的 dek_ciphertext/dek_nonce/ciphertext/nonce；密文均含 tag，只接受已支持格式。迁移到 KMS（云端托管密钥服务）需另定格式和版本，不能假定当前字段可容纳任意服务返回内容。

## 4. 登录凭证与防冒用检查

凭证是“这次登录通过了”的随机通行证；数据库只保存它的指纹（SHA-256 摘要），不保存原始值。密码另用 Werkzeug 的 scrypt 计算校验指纹，并为每个密码加入不同随机值（加盐），避免保存原密码；运行参数按服务器资源验证，不自创算法。

| 项目 | 精确要求与含义 |
|---|---|
| 会话 | admin_session 保存 token_hash 和 csrf_token_hash；enroll 仅用于首次设置，5 分钟；full 完整权限最长 8 小时 |
| Cookie | 名 bumbum_admin_session；生产 HttpOnly（网页脚本不能读取）、Secure（只经 HTTPS）、SameSite=Strict（限制跨站携带）、Path=/api/admin；不设 Domain |
| 正式凭证位置 | 只用 Cookie；不返回 JSON，不放 URL、本地存储或正式 Bearer 认证 |
| Origin | 请求来自哪个网页；生产管理域名、开发 ADMIN_ORIGIN 精确匹配。登录/MFA 无 Cookie 时也检查，不能因没带 Origin 而跳过；命令行联调也须带合法 Origin |
| 写请求 | JSON，并在已有 Cookie 时要求 X-CSRF-Token；不能仅靠 SameSite |
| CORS | 浏览器允许哪些其他网页读取接口；管理 API 仅 ADMIN_ORIGIN，允许 credentials 携带 Cookie，禁止通配来源，也不能把 CORS_ORIGINS 总清单全部用于管理路由 |
| 本地开发 | 仅明确 localhost 配置可关闭 Cookie Secure；生产不得关闭 |

CSRF 口令是“绑定这次登录、由页面额外提供”的值，用于防止其他网页借登录状态操作。HMAC-SHA256 是用独立秘密计算内容指纹的方法：用 CSRF_HMAC_KEY 对 UTF-8 字符串 `bumbum|csrf|<原始session token>` 计算，结果用小写十六进制表示；签发会话时再将它的 SHA-256 存到 csrf_token_hash。

GET /api/admin/auth/session 用当前 Cookie 重新算出同一个 csrf_token，返回 scope/过期时间，不改会话、不换 token、不缓存；因此页面刷新或多标签页不会因这个 GET 相互挤掉口令。更换 CSRF_HMAC_KEY 必须撤销全部会话。

首次开户没有公开注册和默认密码，用以后实现的受控服务器命令安全输入。未设置验证器时，只允许 session、totp/setup、totp/enable、logout，业务返回 mfa_required。setup 重复调用使用同一待绑定秘密，已启用后不能覆盖。enable 成功时记录验证时段、保存 10 个备份码的摘要，撤销全部 enroll 会话，重新签发 full Cookie。

密码正确且已有 TOTP 时，创建 admin_mfa_challenge，发 5 分钟一次性 mfa_ticket。TOTP 用 pyotp 等成熟实现，时间步长和容差在实现时固定验证；接受的 step 必须大于 totp_last_step，并在事务中更新。同一挑战、验证时段和备份码不能被两个同时到达的请求重复用掉。

每个备份码至少 128 位随机熵（足够长的安全随机数），共 10 个，只显示一次，只保存 SHA-256 摘要。备份码登录也先验证密码，再同事务用掉 mfa_ticket 和备份码。注销撤销当前会话；禁用账号时全部会话和未用挑战失效，每次请求查账号状态。丢失全部恢复因子走受控人工恢复，没有公开绕过接口。

## 5. 限制重试与记录操作

限流就是限制重复请求次数。锁定和已使用标记必须放数据库，多个 Gunicorn 进程才会看到同一份结果。

| 场景 | 固定规则 |
|---|---|
| 密码/登录 | 账号和 IP 分别计数；15 分钟窗口内失败 5 次锁 5 分钟，达到 10 次锁 30 分钟 |
| 锁定期间 | 拒绝但不延长锁期、不增加次数；成功登录清账号失败桶，IP 桶自然过期 |
| MFA 登录挑战 | 最多失败 5 次，同时受账号/IP 限制 |
| 短信发送 | 同手机号 60 秒一次；同 IP 每小时最多 10 次 |
| 短信码 | 最多 5 次错误；新码使同 grant 同手机号旧码失效 |
| 芯片验证 | 多进程共同计数；阈值经负载测试和共享 IP 情况确认，不预先保证每秒固定次数或“零开销” |

security_rate_limit 的 bucket_key 用 IP_HASH_KEY 做 HMAC-SHA256，输入含用途和规范化标识，避免混用计数。创建和更新同一桶必须处理唯一键、锁行及事务，不用进程内字典代替。

admin_login_event 记成功、失败、锁定；未知账号用 username_hash，不编造 admin_id。admin_audit 是“谁在什么时候对什么做了什么”的管理员操作记录。ip_hash 由独立 HMAC 密钥处理规范化 IP；不记密码、密钥、验证码、token 或完整手机号。密钥读取先保存审计再返回，数据库失败时不能声称已经记录；动态链接/请求体不进普通访问日志，保留时长与权限投产前确定。

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

配置名称和非敏感示例集中在 [.env.example](../.env.example)，秘密值留空。项目只定义规则，还没有应用或启动脚本；启动入口、Gunicorn 进程数、托管工具、依赖版本等须加代码后实测。

| 配置 | 用途 |
|---|---|
| DB_* | 数据库连接 |
| MASTER_KEY_FASHION / MASTER_KEY_JEWELRY | 按项目计算 K0/K2/K3/K4 的根材料，不直接写卡 |
| SDM_META_KEY_V1 / SDM_META_KEY_VERSION | 全局 K1 与初始 v1 配置 |
| STORAGE_ENCRYPTION_KEY / STORAGE_KEY_VERSION | 包装 DEK 的独立存储密钥及版本 |
| IP_HASH_KEY | 给 IP/计数桶等标识做带密钥指纹 |
| CSRF_HMAC_KEY | 计算绑定登录状态的防冒用口令 |
| WEBHOOK_SHARED_SECRET | 扫描回调的共享秘密；用作 HTTPS Basic Auth 用户名，密码为空，建议独立 32 字节随机值写成十六进制，不含冒号，不放 query |
| SMS_CODE_HASH_KEY | 第二阶段短信码的独立带密钥指纹 |
| ADMIN_TOTP_ISSUER | 验证器显示的公开发行方名称 |
| CORS_ORIGINS / ADMIN_ORIGIN | 开发来源总清单/单个管理网页地址；后者开发 localhost:5174、生产 https://admin.bumbum.cc |
| VITE_API_BASE_URL | 公开前端配置，已带 /api；endpoint 不重复带 /api，其他 VITE_ 值也不得含秘密 |

各用途密钥独立，不与数据库密码或彼此复用。更换存储密钥/KMS、CSRF 密钥或芯片密钥时，各自按对应的恢复和失效规则执行，不仅改一项环境值就当成轮换完成。

[社区 sdm-backend 示例](https://github.com/nfc-developer/sdm-backend/blob/37585f0c76eded73798b936b17aa5e187075b78f/app.py#L222-L227) 展示先解密编号再取得验签密钥，仅供评估，不是已集成或通过测试的证明。[NXP AN12196](https://www.nxp.com/docs/en/application-note/AN12196.pdf) 是需核验的官方资料；此前研究未直接读取此 PDF，不能声称已按它验证参数。pylibsdm 仍是待评估候选，须核验版本、许可证、兼容性与正确答案。
