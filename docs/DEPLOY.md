# 香港 ECS 部署与回滚（V1.0）

适用：Ubuntu 22.04、2核4GB、同VPC阿里云 MySQL 8.0。请先在独立测试库验证，再操作指定生产项目库。本文命令在项目根目录运行，例子中的域名/数据库地址必须替换。本站仅展示服装档案；固定 URL 不防复制，不验证标签真伪或所有权。

## 1. 云资源确认

1. 核对具体数据库产品及 MySQL 8.0、ECS架构（`uname -m`）、项目库 `bumbum_mvp`，不要接入未知业务库。
2. 数据库使用内网域名；同 VPC，并在数据库白名单允许 **ECS 私网 IP**。不要开放公网3306。
3. 域名 A 记录指向 **ECS 公网 IP**，无错误 AAAA/CAA。安全组允许80/443；SSH22限可信来源。确认公网带宽和资源到期费用。
4. 从 RDS 控制台获取实际 CA，确认开启 SSL/TLS、内网域名与证书匹配。驱动同时验证证书链和主机名；不能关闭校验。CA轮换前更新文件并验证。
5. 安装官方 Docker Engine 和 Compose 插件；已有安装先核对不重复覆盖。要求 Compose **>=2.30.0**（raw env_file），BuildKit 支持构建上下文。`sudo docker version`、`sudo docker compose version`。旧版插件先升级。

基础依赖镜像已锁定到版本和 manifest digest，见 `docs/VERSIONS.md`。应用两阶段构建，运行时 non-root、只读文件系统；构建不读取数据库配置、不连接数据库。2核4GB机器建议一次一个构建；app内存限制768MiB，Caddy256MiB，MySQL在云端。可以在同架构机器构建后使用 `docker save/load` 传输镜像以减少ECS构建负载。

## 2. 建库、分离数据库账号

在数据库控制台创建 `bumbum_mvp`（utf8mb4），创建普通账号 `bumbum_app` 与 `bumbum_migrate`，使用不同的随机密码。限制账号允许来源到ECS；不用root跑应用。

初始化阶段仅授予迁移账号此项目库上的 `SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES`。如果阿里云控制台仅提供权限套餐，使用项目库上的读写+DDL权限并核对实际 `SHOW GRANTS`，不要扩大到其他数据库。初始迁移不需要 DROP / TRIGGER / SUPER。MySQL DDL自动提交，失败迁移不能假装全部回滚；迁移表会标记未完成并阻止盲目重跑，需要人工检查后进行前向修复。

应用账号在建表后按以下表级权限授权（用具备授权能力的云数据库管理账号，绝不能把它注入应用）。账号主机部分应按实际授权设置；以下 `%` 仅作账号主机示例，仍必须通过 VPC/白名单限制来源：

```sql
GRANT SELECT, INSERT, UPDATE ON bumbum_mvp.garments TO 'bumbum_app'@'%';
GRANT SELECT, INSERT, UPDATE ON bumbum_mvp.tags TO 'bumbum_app'@'%';
GRANT SELECT ON bumbum_mvp.admins TO 'bumbum_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON bumbum_mvp.admin_sessions TO 'bumbum_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON bumbum_mvp.login_attempts TO 'bumbum_app'@'%';
GRANT SELECT, INSERT ON bumbum_mvp.audit_logs TO 'bumbum_app'@'%';
GRANT SELECT ON bumbum_mvp.schema_migrations TO 'bumbum_app'@'%';
```

应用无DDL权限、无服装/标签永久删除、无审计修改/删除权限；审计写入和业务修改同事务。管理员初始化只用一次性迁移账号，应用对 admins 仅 SELECT。

## 3. 配置文件（真实值仅保存在ECS）

```bash
cd ~/bumbum
umask 077
cp .env.example .env
cp .env.migrate.example .env.migrate
mkdir -p secrets
chmod 700 secrets
chmod 600 .env .env.migrate
nano .env
nano .env.migrate
```

- `.env`：仅应用账号 DATABASE_URL、PUBLIC_BASE_URL、SESSION_SECRET、SITE_DOMAIN、ACME_EMAIL、APP_IMAGE及TLS配置。PUBLIC_BASE_URL必须完整HTTPS origin，不带路径/尾部查询，如 `https://nfc.example.com`。SITE_DOMAIN只填 `nfc.example.com`。
- `.env.migrate`：仅迁移账号 DATABASE_URL 和TLS配置。禁止放迁移账号到 `.env`，禁止管理员密码长期注入应用。
- 用 `openssl rand -hex 32` 私下生成 SESSION_SECRET；至少64字符随机值，不使用示例。变更密钥会使旧会话失效。
- URL中的用户名/密码必须百分号编码，尤其 `@ # % : / ? $`；Compose服务 env_file使用 `format: raw`，**不要给值包引号**。避免在命令行输入带密码的URL。可以在本地离线编码密码后填文件，勿将密码交给在线编码网站。
- 将控制台下载的真实CA复制为 `secrets/mysql-ca.pem`，`chmod 644 secrets/mysql-ca.pem`（CA是公开证书，容器node用户需可读；不要放私钥）。RDS CA必须匹配域名、处于有效期内。应用固定挂载到 `/run/db-ca.pem`，严格校验。
- `APP_IMAGE=bumbum:1.0.0` 是当前本地构建标签，升级必须换不可重复的版本标签。若推送镜像仓库，改成 `registry/...@sha256:实际推送digest`。

真实 `.env*`、secrets、.local、备份全部被 Git 和 Docker 构建上下文排除。勿运行/分享完整 `docker compose config` 或容器 inspect 环境输出；仅 `config --quiet` 校验。

## 4. 构建（不需云数据库）

```bash
sudo docker compose config --quiet
sudo docker compose build app
```

成功时生成 APP_IMAGE 指定镜像，构建内不包含 `.env` 或数据库 CA/密码。如果机器需要可信HTTPS代理，BuildKit支持 `--build-arg HTTPS_PROXY --build-arg HTTP_PROXY --secret id=build_ca,src=/可信代理CA路径`，仅临时使用，不能用 `strict-ssl=false`。受限制的离线环境可在主机先用 `npm ci --cache /受保护npm缓存路径` 获取锁文件包，再 `docker build --build-context npm_cache=/受保护npm缓存路径 -t bumbum:1.0.0 .`；npm仍按lockfile integrity校验，缓存不进入运行镜像。

## 5. 建表与创建管理员

先确认目标库，并为已有数据建立备份。以下工具服务只读取 `.env.migrate`，不读取应用 `.env` 服务环境；两个服务的配置不合并。

```bash
sudo docker compose run --rm tools migrate
```

初次输出 `Applied 001_initial.sql` 和 `Migrations complete`。重复运行只校验已有迁移checksum并跳过，不重置数据。失败必须停止并排查地址、白名单、TLS、权限、未完成迁移；不要手动删迁移记录重试或使用 reset/db push。账号应只能看到项目库。

授予上面的应用表级权限后，交互创建管理员：

```bash
sudo docker compose run --rm tools admin
```

在终端输入账号、密码两次（不回显，12–128位，无默认线上密码）。显示“管理员创建成功”。重复用户名拒绝且不覆盖。管理员密码使用 scrypt，数据库不保存明文。初始化失败不会启动网站假装完成。

可在安全数据库客户端只读核对：

```sql
SELECT VERSION(), DATABASE(), CURRENT_USER();
SHOW TABLES;
SELECT name, completed FROM schema_migrations;
SHOW SESSION STATUS LIKE 'Ssl_cipher';
```

Ssl_cipher非空只证明连接加密；应用使用CA+域名校验进一步确认身份。测试库成功不代表云端连通已成功。

## 6. 启动与检查

```bash
sudo docker compose up -d --wait app caddy
sudo docker compose ps
sudo docker compose logs --tail=100 app caddy
```

app健康检查使用容器内 `127.0.0.1:3000/health`，实际检查数据库和迁移表；app监听 `0.0.0.0:3000`。外部只开放Caddy80/443，代理目标 `app:3000`。Caddy设置内部地址NO_PROXY，避免环境HTTPS代理接管容器间请求。生产Compose没有第二套MySQL、不发布3000。Caddy证书 `/data` 和 `/config` 使用持久化卷，日志每个容器最多3个10MiB文件。app/caddy `restart: unless-stopped`，Docker还需系统开机启动。Caddy公网证书自动签发需要DNS正确、80/443可达和ACME外连可用。

```bash
curl --fail --show-error https://nfc.example.com/health
```

替换为正式域名，期待 `{"status":"ok"}`；数据库不可用为503最小响应。不能以PID/端口或健康检查代替业务验收。

打开 `https://正式域名/admin/login`，按 README 完成A/B模拟闭环，然后从手机移动网络验证。浏览器不得有证书警告。数据库凭证、手机号、UID不应出现在公开HTML/API或应用日志。

应用健康不会自动触发Docker重启：`restart` 处理进程退出，数据库故障应先排查，恢复后健康自动恢复。部署监控对 `/health` 的非200发告警。可定期在受控维护窗口检查重启：

```bash
sudo docker compose restart app
sudo docker compose ps
curl --fail --show-error https://nfc.example.com/health
```

重新登录读取服装、标签与审计，确认数据保留。Caddy访问日志未启用，避免记录公众IP和入口码；错误日志仅输出requestId与错误类别。不得添加会记录请求体/完整手机号的调试中间件。

## 7. 备份、升级与回滚

采用 RDS控制台自动备份/PITR，设置保留期并检查备份成功。升级前建立手工备份，**先在隔离MySQL8.0恢复验证**；备份含手机号，应限制访问、加密存储，不放仓库。独立备份账号至少所需SELECT/SHOW VIEW等权限按云产品文档设置，不给应用增加备份权限。配置文件及Caddy卷也须受保护备份。

每次升级记录旧镜像ID/版本、代码SHA、迁移状态与备份ID：

```bash
sudo docker image inspect bumbum:1.0.0 --format '{{.Id}}'
sudo docker image tag bumbum:1.0.0 bumbum:rollback-1.0.0
```

1. 在隔离数据库验证新迁移+代码，与旧应用是否兼容。
2. 更新APP_IMAGE到新版本标签（如bumbum:1.0.1），构建新镜像；保留旧标签，不运行镜像/卷清理。
3. 建立备份，必要时暂停写入；执行 `docker compose run --rm tools migrate`，失败不继续。
4. `docker compose up -d --wait app caddy`，检查健康、登录、两个固定入口、no-store、所有者与审计。
5. 若数据库仍兼容旧版：将 `.env` 中 APP_IMAGE 改回 `bumbum:rollback-1.0.0`，执行以下命令（不构建、不执行旧迁移）：

```bash
sudo docker compose up -d --no-build --wait app caddy
curl --fail --show-error https://nfc.example.com/health
```

再次核对A/B入口及后台。表结构变更不会随镜像回滚；不兼容时停止写入并由数据库管理者制定前向修复/恢复切换方案。不得直接覆盖线上库为旧备份，否则丢失备份后的绑定与所有者修改。恢复到新隔离库，核对后有计划地切换连接并保留原库。

停止与恢复：`sudo docker compose stop app caddy`、`sudo docker compose up -d --wait app caddy`。不要执行 `down -v`；会删除证书持久卷。入口域名和 `/t/` 路径在写入实体标签后保持稳定。

## 8. 尚需人工验收

- ECS到真实RDS的白名单、两账号权限、TLS CA/主机名及从应用容器实际连接。
- 正式DNS/HTTPS签发与续期、80/443外部可达、3000/3306不公开、服务器重启恢复。
- 使用iPhone14移动网络与真实IOS版本；两枚NTAG424 DNA真实UID回读、URL NDEF写入/回读、各10次触碰及不重写下的修改/改绑/停用。
- 手机长资料和真实图片观感/性能、备份恢复、账单与到期提醒。

项目没有操作真实云资源、真实标签、SUN/SDM或AES密钥。普通URL可复制，后台“人工核对”只记人工操作，不实施芯片写入。
