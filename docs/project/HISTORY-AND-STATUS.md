# 项目决策历史、证据与交接状态

整理日期：2026-10-23（北京时间）。以下按会话和软件基线归档，不代表此刻已远程检查服务器。

## 0. 归档时发现的远端仓库状态

2026-10-23实际git ls-remote/fetch确认，main指向`fdbeb4aa1dd9777993442686621ac2be8d9d737a`（Initial commit），其树只有README，且与本地旧软件历史不同。未推测重新初始化原因，也未强推恢复旧代码。本文的实现事实来自本地保留的6b333f4及原始交付ZIP。

资料单独保存归档分支，避免覆盖main。另附v1.2.1源码包只作备份参考；不包含部署秘密或运行数据。原固定SHA链接可能需要权限，也可能因远端历史改变不可用，本资料包关键结论已自包含。

## 1. 需求演进

| 阶段 | 用户目标/决定 | 当前归档解释 |
|---|---|---|
| 原需求V0.2 | 固定随机NFC网址、服装档案、管理员登记所有者；TypeScript、MySQL8.0、香港Ubuntu22.04 | 原始SUN明确不在第一期，不可因此否定后来扩展 |
| MySQL软件与部署 | 软件和后台先实现验证，交付Docker/Compose/Caddy、独立迁移/管理员CLI与回滚手册 | 已有代码与测试，原云资源后来退出当前执行路径 |
| 数据库排错 | 登录500、安全诊断、权限收敛、识别实际DUCKDB表 | 确认产品与原事务型假设不符，不继续盲目适配生产 |
| 架构讨论 | MySQL Serverless、OSS、大陆ECS/ICP、Ubuntu/Alibaba Cloud Linux | 讨论备选，不代表已购买/备案或迁移完成 |
| 当前基础方案 | **新香港ECS + SQLite**，Ubuntu22.04 LTS 64位 | 与旧香港ECS无旧部署继承；新主机真实目录后续已定位 |
| 动态验真扩展 | 3枚NTAG424 DNA，真正SUN/SDM；不做防拆 | 软件1.2.0增加AES与持久计数验证 |
| 手机工具落地 | iPhone，后补Win11与MacBook信息；最终nfc.cool启用SUN | 不再将USB读卡器视为必需；硬件候选未实测 |
| 参数兼容 | nfc.cool生成picc_data/cmac，原后台只接受p/m | 软件1.2.1增加严格别名，保留原安全检查 |
| 后续产品讨论 | 管理域名分离、批量导入、Figma设计、主密钥派生 | 待实施方案，详见ROADMAP.md |

用户最早引用的ChatGPT讨论与上传PRD/操作手册作为需求背景，不是已经执行完的部署证据。原文件名digital-clothing-prd-v0.1.md内部版本实际为V0.2；原操作手册也明确当时是操作计划，不等于代码已经部署。

## 2. 数据库与云资源决定

### MySQL/InnoDB与DuckDB

用户曾观察到SQL VERSION为8.0.36、default_storage_engine为InnoDB，但7张业务表实际ENGINE=DUCKDB。控制台截图确认是标准版DuckDB分析实例。**连接协议、版本字样和默认引擎不能证明实际业务表具备普通MySQL/InnoDB语义。**

原登录错误出现TypeError，诊断指向登录限速逻辑；代码补过安全日志、显式upsert和缺失行保护。没有完整证明每个云端错误都由同一个DuckDB内部行为导致，不能把“改一条SQL”记录为该产品已适配成功。

为适应DuckDB重写是可研究的另一条路线，但事务、并发、约束和DML语义要重新验证；本会话没有交付该适配。当前采用SQLite先完成MVP。

原RDS运行账号曾有全局/库级宽权限，逐步增加了表级授权并撤去业务库宽权限。历史后续输出仍包含部分全局/系统库授权，不能记录为全部最小权限收敛已完成。当前SQLite不继续执行这些GRANT/REVOKE，不把高权限管理账号放入应用.env。

### 其他讨论

- RDS MySQL Serverless可作为选型方向，但具体普通事务型产品、地区、预算和网络需核实，免费额度不等于长期成本。
- OSS可放图片/加密备份，不替代业务数据库；当前图片只是HTTPS URL，没有OSS上传集成。
- 大陆节点与ICP备案曾讨论，用户最终先选择香港验证；没有已完成购买/备案的确认。
- 最早ECS规格为2核4GB/40GB；新ECS仅系统明确，不能把旧实例资源自动套到新实例。
- Ubuntu22.04是当前确定基线；Ubuntu26.04/Alibaba Cloud Linux没有成为本轮已验证部署环境。
- MySQL PEM CA仅用于旧TLS方案；需要从实际云产品可信渠道获取，~/目录因登录用户而异。SQLite阶段不再需要它，不应为了找旧CA而阻塞本轮部署。

## 3. 版本和证据表

| 标签/版本 | 内容 | 证据范围 |
|---|---|---|
| bumbum:1.0.0 | 原MySQL MVP | 历史软件/部署验证 |
| bumbum:1.0.1-diagnostics | 安全错误类型/位置日志 | 云端日志可显示TypeError，避免输出SQL/密码 |
| bumbum:1.0.2-login | 限速upsert及缺失行防护 | 原问题防护，不表示DuckDB全面兼容 |
| 1.1.0-sqlite | 单机SQLite、持久卷、在线备份恢复、原后台 | SQLite20、浏览器2、MySQL17等历史开发验证 |
| 1.2.0-sdm | 独立目标密钥、AES-SDM、PENDING/ACTIVE、计数导出/合并 | 57项历史测试及容器/Caddy/旧库恢复 |
| 1.2.1-sdm | picc_data/cmac与p/m严格别名 | 39项针对性测试、镜像、别名HTTPS/重启/恢复 |

相关软件提交：2453416（SQLite）、85c53d3（SDM）、2799dbc（旧备份恢复说明）、6b333f4（nfc.cool别名）。本资料基于6b333f4整理；文档提交之后仓库HEAD会改变，不表示应用版本发生变化。

0已知漏洞等审计描述属于历史检测时结果；本次归档没有重新扫描、重跑全部业务测试或调用真实ECS接口。

## 4. 新ECS用户现场证据

### 已收到

- SQLite首次check为ok，schema_migrations=1、admins=0，属于建表成功而非异常；之后需独立创建管理员。
- 原部署目录定位为`/root/bumbum-sqlite-package/bumbum-main`，与Compose标签一致。
- 一次升级误在/root复制源码、查找/root/.env.sqlite，导致配置找不到、镜像未构建；后续定位原目录处理。
- 新版check成功，SQLite3.53.3、schema_migrations=2，某次计数为garments2、tags4、admins1、NFC配置0。**这些是当次快照，不是永远应保持的业务数量。**
- tools运行UID/GID1000，私密目录1000/700，HTTPS origin正常。
- 首次nfc-prepare使用错误UUID，查询标签记录为空；不是权限/数据库损坏。改成正确标签ID后成功PENDING。
- 正确标签ID为dbab7b32-b60e-4cde-ac81-a248240d86cb，配置中UID与实物一致；运行/初始化文件已生成。

### 仍待现场确认

- ECS是否实际启动1.2.1镜像；仅GitHub更新或本地构建成功不是远程部署证据。
- 用户新动态读数在bumbum通过，而不仅App内部显示真实。
- 管理员已启用ACTIVE、再次新触碰正式通过。
- 同链接重放/停用/解绑/下架/重启的现场结果。
- 当前Key0是否最终换为随机十六进制目标值；Key3/4是否写入，均不凭目标JSON推定。
- 另外两枚真实UID、独立密钥、10次触碰和完整验收。
- 离机加密备份、最终水位及恢复演练；公网证书续期、ECS重启、容量和监控。

## 5. 第一枚标签的现场证据

- 稳定UID048681CA842090；TagInfo识别NXP NTAG424 DNA，公钥原厂签名验证通过。
- 初期no ndef records不能证明所有AES钥是默认；未与卖家确认原钥值。
- NFC Tools逐次重新扫描导致续传911C，批量三条GetVersion同会话成功；纠正“有原始命令就自动具备认证工具”的推断。
- nfc.cool支持专用Key0管理。用户用口令模式改Key0成功，App用FaceID解锁本地保存信息。测试口令具体内容不归档。
- 用户确认Key1/2按服务器文件十六进制值设置，nfc.cool后续SUN开启并显示真实；其网址采用picc_data/cmac。
- 只读文件设置确认文件02为256字节、SDM C1、权限00E0、密钥用途Key2/Key1、F121及66/104/104偏移。详细字节与解释见NFC手册。
- 这些证据确认芯片侧配置符合后端profile所需设置；不证明保存的钥值已由服务器独立验签成功，最终闭环仍要现场补齐。

## 6. 统一术语和已纠正误区

| 误区 | 当前结论 |
|---|---|
| 动态映射就是动态防伪 | 原/t是固定网址映射；/v才做芯片SDM校验 |
| UID/入口码就是密钥 | 都不是，不能凭它们证明新读取真伪 |
| 原厂签名通过=默认Key0通过 | 不同检查，不能替代 |
| Key0口令输入等于AES十六进制值 | App有派生转换，具体实现不能猜 |
| 能读版本就能手工完成AES认证 | 还需要同会话随机挑战计算和安全消息 |
| iPhone必须加读卡器才能配置 | 硬件可行，关键是App功能；nfc.cool已有实物配置证据 |
| p/m模板偏移能套用所有App | 参数名和NDEF编码改变位置；本实物66/104/104 |
| nfc.cool真实=服务器已验真 | App与服务器校验独立，仍要后端实际通过 |
| 主密钥讨论过就已部署 | 当前仍随机生成，HKDF未实现 |
| 文件里生成Key0–4=全部已写卡 | 目标值与实际状态分开 |
| 同盘SQLite备份就足够 | 还需钥/配置/最终计数及离机保护 |
| 后台换域名只加DNS即可 | 必须同步路由、Origin、Cookie/权限策略 |

## 7. 验收和资产台账模板（不填写秘密）

### 标签资产

| 标签代号 | 真实UID | 后台标签ID | 服装实例编号 | 密钥来源/版本 | 当前Key0已备份 | Key1/2已写入并服务器校验 | 状态 |
|---|---|---|---|---|---|---|---|
| A | 048681CA842090 | dbab7b32-b60e-4cde-ac81-a248240d86cb | 待补 | 随机，待核对 | 待确认 | 用户报告写入；服务器结果待补 | PENDING最后明确记录，后续待确认 |
| B | 待读 | 待补 | 待补 | 待补 | 待补 | 待补 | 待补 |
| C | 待读 | 待补 | 待补 | 待补 | 待补 | 待补 | 待补 |

不要在台账放keyHex、口令、SESSION_SECRET或可直接打开的动态URL；只记录私密保管位置、指纹/版本和状态。

### 现场测试

| 时间（北京时间） | 标签 | 手机/iOS | 网络 | 独立触碰编号 | 服务器版本 | 结果/状态码 | 正确服装 | requestId/备注 |
|---|---|---|---|---|---|---|---|---|
| 待填 | A | 待填 | 待填 | 01 | 待核对 | 待填 | 待填 | 不放动态参数 |

### 交接待办

- [ ] 负责人记录ECS实际资源、磁盘/账单、DNS/证书和受控管理入口。
- [ ] 开发/运维确认1.2.1现场版本与无公开3000，保留旧镜像。
- [ ] 负责人完成第一枚PENDING→ACTIVE、重放/停用/重启及Key0最终确认。
- [ ] 运维完成受控离机备份和不回退计数的恢复演练。
- [ ] 第一枚通过后再处理B/C，逐枚记录而非复制A的密钥。
- [ ] 下一轮评审主密钥提案、后台隔离、批量导入与Figma稿，不把方案直接当实现。

## 8. 历史资料索引

本包命令以v1.2.1为准。以下为固定软件提交的原文件，便于追溯，不要求顺序全部照做：

- [原始PRD V0.2](https://github.com/ilcece/bumbum/blob/6b333f4/docs/PRD-V0.2.md)
- [旧MySQL部署手册](https://github.com/ilcece/bumbum/blob/6b333f4/docs/OPERATIONS-GUIDE.md)
- [SQLite操作手册](https://github.com/ilcece/bumbum/blob/6b333f4/docs/SQLITE-ECS-GUIDE.md)
- [NTAG424初版手册](https://github.com/ilcece/bumbum/blob/6b333f4/docs/NTAG424-DNA-GUIDE.md)
- [nfc.cool兼容补丁](https://github.com/ilcece/bumbum/blob/6b333f4/docs/NFCCOOL-COMPAT.md)
- [SQLite历史测试报告](https://github.com/ilcece/bumbum/blob/6b333f4/docs/SQLITE-TEST-REPORT.md)
- [SDM历史测试报告](https://github.com/ilcece/bumbum/blob/6b333f4/docs/NTAG424-TEST-REPORT.md)
- [版本与镜像锁定](https://github.com/ilcece/bumbum/blob/6b333f4/docs/VERSIONS.md)

旧对话下载链接不可访问时优先使用本资料包及独立归档分支，而不是重复尝试失效的历史sandbox链接。官方协议NXP AN12196/NT4H2421Gx曾因站点403未能直接获取全文；软件使用公开示例向量交叉验证，不能声称所有App版本都经官方认证。
