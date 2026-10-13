# 软件与部署文件验证报告

日期：2026-10-13（北京时间）。实际环境Node24.19.0、Docker28.4.0、Compose2.40.3、Linux amd64；测试数据库为隔离MySQL8.0.45，不是阿里云生产数据库。所有测试使用虚拟服装/手机号/UID；没有实体标签操作。

## 结果

- TypeScript生产编译：通过，`npm run build`。
- 锁文件安装：通过，`npm ci --cache /tmp/bumbum-npm`；全量/生产 `npm audit` 均0已知漏洞。
- MySQL集成：**16组通过、0失败、0跳过**，`bash scripts/test.sh`。
- Chromium浏览器：**2项通过、0失败、0跳过**，`npm run test:browser`；360×800。
- 生产Docker镜像：实际构建成功；云环境容器构建网络受限，使用已核验npm缓存的BuildKit上下文进行离线 `npm ci`，保留lockfile integrity。构建无DATABASE_URL/真实云库访问。
- 生产Compose/Caddy语法：`docker compose config --quiet` 与 `caddy validate` 通过。
- 隔离容器验收：app+ Caddy使用生产镜像/生产运行设置，测试叠加文件仅加入隔离数据库网络、回环测试端口和内部CA证书。严格MySQL TLS、可信HTTPS代理、Secure Cookie、创建服装/标签、302/no-store/公开隐私、真实容器重启后记录/会话保留均通过。
- MySQL TLS负向：错误主机名、错误CA被拒绝；生产禁止明文连接。另验证MySQL服务器默认时区+08:00时，新连接仍设置为UTC，数据库默认时间不会误存北京时间。
- 镜像与运行隔离：node非root、只读文件系统、无发布3000、应用环境仅应用账号，迁移账号未注入；运行镜像无.env、.local、secrets或测试文件。
- 迁移：首次建表和重复执行均通过，无重置；本地与Compose一次性工具入口都执行成功。交互管理员初始化两种入口均通过，密码不回显。

## 对照需求

| 范围 | 已执行的验证 |
|---|---|
| T01–T05 | A/B随机入口、302/相对Location/no-store、新请求读更新、改绑保持所有者、绑定目标冲突不覆盖 |
| T06–T08 | 两次所有者变更对应两条审计、同值不重复、清空登记、列表脱敏、详情受限、公共HTML/API字段白名单 |
| T09–T12 | 停用410/恢复、解绑409、未知404、草稿/下架入口与直接详情404，可读HTML |
| T13–T15 | 所有管理资源无会话401，页面转登录；非法UID/手机号/超长字段、重复UID、脚本转义、禁止绕过owner入口；并发绑定只有一个成功，旧version409 |
| T16 | 撤销本地应用审计INSERT权限；所有者和绑定修改均失败且事务回滚，版本/审计数量不改变；审计DELETE和DDL被应用权限拒绝 |
| T17 | 实际停掉隔离MySQL；health/入口/详情/API503且无内部信息；启动数据库后恢复 |
| T18–T19 | HTTP监听重启及真实app容器重启后持久化、30分钟闲置期限过期模拟、退出令牌撤销、5次错误后第6次429、跨Origin403、Secure/HttpOnly/SameSite Cookie |
| T20 | 360px后台完整操作、公开页无横向滚动、图片失败占位、简介纯文本、错误表单保留输入；移动截图已检查 |
| T21–T22 | **未执行**：真实UID、写卡、iPhone14触碰、不重写后的实体读取需人工验证 |

浏览器测试从登录开始，经页面新增A/B、登记标签、修改所有者、解绑B、A改绑B、打开固定入口、停用、审计与退出，完成端到端流程。第一轮测试发现管理API认证重定向问题、实例编号大小写搜索问题；修复后重跑全部相关验证。生产代理测试还发现平台自动注入代理会影响app内部请求；Caddy设置NO_PROXY后复验通过。

## 可复现命令

在专用本地检出，勿在生产目录运行故障注入测试：

```bash
npm ci --cache /tmp/bumbum-npm
npm run build
bash scripts/local-db.sh
bash scripts/test.sh
npm run test:browser
bash scripts/test-containers.sh
```

容器测试要求没有已有`.env`、`.env.migrate`或`secrets/mysql-ca.pem`，拒绝覆盖部署配置。生成的本地证书/凭证仅存在忽略文件中；结束时停止测试app/caddy并保存测试配置到`.local`，不删数据/证书卷。测试内部CA不能用于生产；生产Caddy使用公网ACME、数据库CA使用阿里云控制台实际证书。测试Docker构建使用主机已核验npm缓存作为额外构建上下文；只在build阶段挂载，运行镜像不保留缓存。

## 必须人工验证

真实ECS/RDS连通、数据库产品及项目权限/白名单、CA与主机名、DNS、安全组、公网ACME签发/续期、系统重启、备份/PITR恢复、真实iPhone14/标签读取及实际网络性能。内部CAHTTPS成功不能代替公网证书验收；本地数据库成功不能代替阿里云连接成功。请使用 `docs/NFC-ACCEPTANCE.md` 逐次记录实体结果。
