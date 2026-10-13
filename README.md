# bumbum NFC MVP

单项目 TypeScript + Express + MySQL 8.0。根据 [V0.2需求](docs/PRD-V0.2.md) 实现固定随机入口动态映射与一个管理员角色，移动端公开服装详情。没有默认管理员密码，不连接真实云库构建，不提供防伪认证、用户自助认领或真实写卡。

## 本地开发（隔离MySQL）

要求 Node **24.19.0**、npm、Docker+Compose >=2.30；浏览器测试使用已安装Chromium，或安装Playwright配套浏览器后配置其路径。每个云任务已有隔离工作区，直接用现有检出，不需要Git worktree。

```bash
npm ci --cache /tmp/bumbum-npm
npm run build
bash scripts/local-db.sh
```

首次创建持久化测试库 `bumbum_test`，仅绑定127.0.0.1:3307，随机本地密码存于忽略的 `.local` 文件；重复执行不重置数据。脚本创建分离的应用/迁移账号并执行迁移。初始化管理员：

```bash
set -a
source .local/migrate.env
set +a
npm run admin:init
```

输入用户名和12–128位密码两次，密码不回显。启动（另一个终端）：

```bash
bash scripts/dev.sh
```

浏览器在本机打开 `http://localhost:3000/admin/login`；本地地址仅用于开发，不能写进上线标签。健康命令：`curl --fail http://localhost:3000/health`。公开API `/api/public/garments/:id` 只返回白名单字段；入口 `/t/:32位随机码` 302到 `/g/:uuid`，所有动态响应no-store。

停止开发服务器 Ctrl+C；数据库保留：`docker compose -f compose.local.yaml stop`；恢复 `bash scripts/local-db.sh`。不要 `down -v` 或 reset。

## 后台A/B验收操作

1. 登录，点击“新增服装”，录入黑色外套A（ITEM-A001）和白色衬衫B（ITEM-B001），选择“已发布”。草稿默认不公开。
2. 点击“标签 → 登记标签”，软件验证时使用明确标注“模拟测试”的14位十六进制UID；真实阶段必须用回读真实UID重新登记，不直接修改UID。
3. 在标签详情搜索实例编号，选择A/B，填写原因并确认绑定；复制完整入口分别打开，应显示对应服装。
4. 编辑服装名称，刷新入口看到新内容。独立“修改所有者”录入虚拟手机号及原因并最终确认；公开页只显示登记状态，审计列表脱敏、完整详情仅管理员可查看。
5. 先解绑B标签，再把A标签改绑B；A入口不变，显示B。若目标已有标签会拒绝，不挤掉旧绑定。
6. 停用得到410，解绑得到409，草稿/下架得到404；均可读HTML。重新启用后恢复。服装和标签不提供永久删除。
7. 标签写入需外部兼容工具。后台显示URL与NDEF容量估算；**实际回读并打开正确页之后**才点击“标记人工核对”。不要把模拟标签标为真实已核对。
8. 查看审计记录，退出后后台页面和API被拦截。已打开页面不会自动更新，新请求读取最新数据。

并发编辑携带version，旧版本返回409而不覆盖；错误输入保留表单，保存中禁用重复提交。简介/养护纯文本，HTTPS图片浏览器直连，失败占位。手机号只是管理员登记，未认证所有权。

模拟资料见 [DEMO-DATA.json](docs/DEMO-DATA.json)，可按后台步骤逐条录入；自动测试会生成独立的随机模拟数据。

## 自动验证

```bash
bash scripts/test.sh
npm run test:browser
# 可选：专用本地检出验证生产镜像、严格TLS及代理（无已有部署配置）
bash scripts/test-containers.sh
```

测试只允许隔离 `bumbum_test`，会生成虚拟数据和随机测试管理员，不重置数据库。集成测试会短暂撤销本地审计INSERT权限、停止/启动本地数据库来验证回滚和故障恢复，请勿与其他本地写入并行。`.local/browser.json` 是本地测试专用随机账号，集成测试生成后供浏览器测试使用，不提交/打入镜像。

Chromium默认 `/usr/bin/chromium`；通过 `CHROMIUM_PATH=/实际浏览器路径 npm run test:browser` 覆盖。浏览器测试自动启停开发服务器，运行时3000端口应空闲。测试会验证360px完整后台流程、公开响应无手机号、图片占位、XSS纯文本与输入保留。

[测试报告](docs/TEST-REPORT.md) · [生产部署与回滚](docs/DEPLOY.md) · [版本核对](docs/VERSIONS.md) · [真实标签验收表](docs/NFC-ACCEPTANCE.md)

## 主要交付

- `src/`：服务端、校验、数据库事务、会话与限速、独立CLI；`public/`：后台及公开页面资源。
- `migrations/001_initial.sql`：InnoDB/utf8mb4、外键及唯一约束；checksum、锁与中断检测，未使用reset。
- `Dockerfile`、生产 `compose.yaml`、`Caddyfile`；只Caddy开放80/443，app运行账号不含迁移凭证。
- `.env.example`、`.env.migrate.example`、Git/Docker忽略文件；配置内容与账号权限见部署说明。

时间保存UTC、后台按Asia/Shanghai显示。会话闲置30分钟失效；密码scrypt、会话仅保存HMAC散列；Cookie HttpOnly/SameSite Strict，生产Secure；写接口严格Origin检查；失败登录每IP+账号15分钟最多5次，计数保存MySQL。审计与业务同事务，应用账号无审计UPDATE/DELETE权限。`/health`不暴露凭证/配置。
