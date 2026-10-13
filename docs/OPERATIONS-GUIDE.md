# bumbum 部署与测试操作手册（新手版）

版本：1.0；编写日期：2026-10-13。对应已交付的 bumbum NFC MVP。

适用环境：香港 ECS、Ubuntu 22.04、2核4GB、已有同VPC阿里云 MySQL 8.0。数据库控制台部分以 **RDS MySQL** 为例；若实际产品不是RDS，先核对该产品的账号、白名单和TLS方式，不照搬菜单。

请按阶段顺序操作，某阶段失败先排查，不继续下一阶段。本手册没有替你登录ECS、配置真实数据库或写入实体标签；已有自动测试结果见 [TEST-REPORT.md](TEST-REPORT.md)。

## 1. 先分清三个操作位置

| 位置 | 你做什么 | 怎么认出来 |
|---|---|---|
| 电脑浏览器 | GitHub下载、阿里云控制台、后台页面 | 有网页菜单和地址栏 |
| ECS终端 | Linux、Docker、文件配置命令 | Workbench内的终端，提示符一般以 `$` 或 `#` 结束 |
| MySQL客户端 | SQL查询和授权 | 登录后看到 `mysql>` 提示符 |

下面标注“ECS终端”的代码块不要粘贴到 `mysql>`；SQL代码块只在数据库客户端执行。命令里的 `nfc.example.com`、数据库地址等都是占位示例，必须换成你自己的。不要复制 `$`、`#` 或 `mysql>` 提示符。

生产机器不需要额外安装Node、npm、Chromium或第二套MySQL服务器：应用运行在Docker中，数据库使用现有阿里云实例。自动测试用的MySQL容器是独立开发流程，不是生产部署步骤。

## 2. 整体顺序与完成标志

| 阶段 | 工作 | 完成标志 |
|---|---|---|
| A | 收集参数、登录ECS | 能在正确实例执行Linux命令 |
| B | 项目数据库、两个账号、白名单、TLS | ECS能严格校验TLS后连接目标库 |
| C | DNS与80/443 | 正式子域名解析到ECS公网IP |
| D | 检查/安装Docker、下载代码 | 项目目录和Compose插件正确 |
| E | CA与两个配置文件 | 配置完整、不含占位符、权限正确 |
| F | 构建、迁移、表级授权、管理员 | 镜像生成、建表成功、管理员创建成功 |
| G | 启动HTTPS | 健康200、浏览器无证书警告、后台可登录 |
| H | 软件A/B业务验收 | 更新、改绑、所有者、审计和异常场景正确 |
| I | 实体NFC验收 | 两枚真实UID与固定入口逐个回读和触碰通过 |
| J | 备份、重启、更新与回滚 | 恢复演练和运维记录完成 |

首次建议用单独项目测试库上线验收；若使用另一个库名，两账号授权、连接URL和所有SQL都必须一致。不要连接未知已有业务库试迁移。

## 3. 参数清单：先记录，不公开分享

在你自己的受保护记录中填写：

| 参数 | 去哪里找 | 用在什么地方 |
|---|---|---|
| ECS公网IPv4 | ECS实例详情 | DNS A记录 |
| ECS私网IPv4 | ECS实例详情/网络 | 数据库白名单 |
| VPC ID | ECS和数据库实例网络信息 | 核对两个实例同VPC |
| 数据库内网域名 | RDS基本信息/数据库连接 | DATABASE_URL、TLS验证 |
| 数据库端口 | 同上 | 通常3306，以实际为准 |
| 项目库名 | 自己创建/确认 | 默认示例bumbum_mvp |
| 应用账号 | 数据库账号管理 | bumbum_app |
| 迁移账号 | 数据库账号管理 | bumbum_migrate |
| 正式子域名 | DNS服务商 | 例如nfc.你的域名 |
| 证书通知邮箱 | 你的有效邮箱 | ACME_EMAIL |
| 数据库CA文件 | RDS SSL/TLS页面 | secrets/mysql-ca.pem |

数据库密码、网站管理员密码和SESSION_SECRET只放受保护配置/密码管理器。不要发聊天、截图、GitHub或在线URL编码网站。网站管理员账号与数据库账号是两套不同账号。

## 4. 登录ECS并检查机器

**电脑浏览器：** 阿里云ECS控制台 → 实例 → 远程连接 → Workbench → 登录。选择实际系统用户及正确认证方式。若Workbench提示需要安全组规则，可按其当前页面“一键添加”，不要开放SSH给所有来源。

**ECS终端：**

```bash
whoami
pwd
cat /etc/os-release
uname -m
free -h
df -h
```

成功标志：系统是Ubuntu22.04，内存约4GB，磁盘剩余空间足够。`uname -m` 的 `x86_64` 对应amd64，`aarch64` 对应arm64。后面的Docker软件源会自动读取架构。

如果已经有其他网站或服务，不关闭它们、不重装系统。先检查80/443是否占用：

```bash
sudo ss -ltnp
```

若已有Nginx/Caddy/其他容器占用80/443，先确认其用途并制定共存方案，本手册不能直接同时绑定相同端口。不要为部署新站盲目停止旧站。

## 5. 创建数据库与分离账号

**电脑浏览器，RDS控制台：**

1. 确认引擎MySQL8.0、地域香港，记录内网域名和端口。
2. 在数据库管理中创建专用数据库 `bumbum_mvp`，字符集 `utf8mb4`。不要选择其他业务已有库。
3. 在账号管理中创建 `bumbum_migrate` 和 `bumbum_app`，分别设置不同的随机密码并安全保存。
4. 迁移账号仅授予项目库上的建表/结构修改和必要数据操作权限。需要的权限为 `SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES`；初始版本不需要DROP、TRIGGER或SUPER。
5. 应用账号最终使用第12节的表级权限，不用高权限账号跑网站。控制台若仅提供整库读写套餐，不能把它当作最终最小权限；需要建表后由可授权的管理账号调整并验证。

如果已经创建过库/账号，核对后复用，不重复创建同名资源，不改已有用户密码。若实际账号名不同，统一修改连接配置及授权SQL。

### 5.1 白名单与网络

RDS控制台 → 白名单/数据安全性 → 编辑白名单，加入 **ECS私网IP**。仅加入需要的来源，不使用 `0.0.0.0/0`。

确认数据库与ECS实际VPC ID一致；同一地域或都在香港不等于同一VPC。同VPC也仍需要正确账号权限和白名单。

### 5.2 数据库TLS证书

RDS实例 → SSL/TLS相关设置：启用所需SSL，下载官方数据库CA证书。启用/更新证书可能有实例影响，应按控制台提示选择维护窗口。

本应用生产配置强制严格TLS，验证证书链和连接域名。使用数据库**内网域名**，不要擅自换成IP；证书必须覆盖该域名。不要把网站HTTPS证书与数据库CA混为一谈。

下载包若同时有 `.pem`、`.p7b`、`.jks` 等格式，本项目需要PEM CA证书/证书链；不是Java keystore，也不是私钥。具体文件名称以阿里云下载说明为准。暂时无法取得匹配CA或域名时，停在本阶段排查，不关闭校验绕过。

## 6. 验证ECS到数据库的真实连接

本步骤安装**客户端**，不安装第二个数据库服务器。

**ECS终端：**

```bash
sudo apt update
sudo apt install -y mysql-client ca-certificates curl unzip python3 nano
mkdir -p ~/bumbum-ca
chmod 700 ~/bumbum-ca
```

通过Workbench文件管理（如果有）或SFTP/scp将下载的PEM CA放到 `~/bumbum-ca/mysql-ca.pem`。若文件管理不可用，使用你实际的SSH认证方式传输，不把SSH私钥上传GitHub。

把下面主机名替换为真实内网域名，端口替换为实际端口：

```bash
mysql --host=YOUR_RDS_INTERNAL_HOST --port=3306 \
  --user=bumbum_migrate --password \
  --ssl-mode=VERIFY_IDENTITY \
  --ssl-ca="$HOME/bumbum-ca/mysql-ca.pem" \
  bumbum_mvp
```

`--password` 不带值，终端会提示输入密码且不回显。不要使用 `-p真实密码`。

看到 `mysql>` 后执行：

```sql
SELECT VERSION(), DATABASE(), CURRENT_USER();
SHOW GRANTS;
SHOW SESSION STATUS LIKE 'Ssl_cipher';
SHOW TABLES;
EXIT;
```

成功标志：版本8.0、数据库名正确、当前账号为迁移账号、Ssl_cipher有值；首次尚未迁移时没有项目表是正常的。`VERIFY_IDENTITY` 成功才同时验证了加密、CA和主机名。

随后将 `--user` 改为 `bumbum_app` 测试认证和连接；表级权限需第12节建表后补齐。失败时优先检查地址/端口、VPC、白名单、账号、授权和CA。不要通过开放公网3306解决内网问题。

## 7. 域名和安全组

### 7.1 DNS解析

在实际DNS服务商控制台添加：

| 字段 | 内容 |
|---|---|
| 类型 | A |
| 主机记录 | nfc（示例，按你的子域名） |
| 记录值 | ECS公网IPv4 |
| TTL | 默认即可 |

记录里不填私网IP、不填数据库地址、不填 `https://` 或 `/t/`。已有同名记录先确认用途；没有正确IPv6就不要添加AAAA。

**ECS终端，替换域名：**

```bash
getent ahostsv4 nfc.example.com
```

成功标志：返回ECS公网IP。DNS生效不等于网站已上线。

### 7.2 安全组

ECS实例 → 网络与安全组 → 安全组 → 入方向规则：

| 协议 | 端口 | 来源 | 用途 |
|---|---|---|---|
| TCP | 80 | 网站需要的公网来源；公开网站通常0.0.0.0/0 | HTTPS跳转与证书挑战 |
| TCP | 443 | 同上 | HTTPS网站 |
| TCP | 22 | 当前Workbench指定来源或你的可信管理IP/32 | 管理登录 |

**不要添加3000或3306公网入方向规则。** 数据库通过私网访问，3000只在容器网络中被Caddy代理。

如果系统使用UFW，先查看 `sudo ufw status verbose`；已启用时按现有管理规则允许80/443，切勿在SSH会话中贸然启用/重置防火墙导致自己被锁在外面。

## 8. 检查与安装Docker

**ECS终端先检查：**

```bash
docker --version
sudo docker version
sudo docker compose version
```

Docker Engine可用且Compose **>=2.30.0** 就跳过安装，继续第9节。项目使用 `env_file: format: raw`，旧版Compose不能正确解析。

若命令不存在，且确认机器无需保留的冲突Docker软件，按Ubuntu22.04官方APT方式安装：

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

然后整块复制：

```bash
docker_arch=$(dpkg --print-architecture)
cat <<EOF_DOCKER | sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: jammy
Components: stable
Architectures: ${docker_arch}
Signed-By: /etc/apt/keyrings/docker.asc
EOF_DOCKER
```

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
sudo docker run --rm hello-world
```

已有旧 `docker.io` 或 `containerd` 导致冲突时先排查用途，不自动卸载。签名、TLS或镜像校验失败时不能关闭验证。本手册使用sudo执行生产Docker，不要求加入docker用户组。

## 9. 下载和放置代码

**电脑浏览器：** 登录GitHub → 打开 <https://github.com/ilcece/bumbum> → 切换 `main` → 绿色 **Code → Download ZIP**。若仓库私有，必须用有权限的GitHub账号登录。

如果之前下载过旧包，重新下载以包含最新手册。将 `bumbum-main.zip` 上传到ECS用户主目录（`~`）下。Workbench文件管理没有上传功能时，用SFTP/scp。

**ECS终端：**

```bash
cd ~
unzip bumbum-main.zip
```

成功会生成 `bumbum-main` 目录。**仅在没有已有 `~/bumbum` 部署目录时**执行：

```bash
mv bumbum-main bumbum
cd ~/bumbum
pwd
ls -la
```

如果 `~/bumbum` 已存在，不执行上面的mv，不覆盖已有 `.env`、证书或部署；新版本放到不同发布目录，按第19节升级。

成功标志：当前目录有 `Dockerfile`、`compose.yaml`、`Caddyfile`、`package-lock.json`、`.env.example`、`.env.migrate.example`、`migrations`。隐藏文件用 `ls -la` 才看得见。

今后生产Compose命令都在这个目录执行：

```bash
cd ~/bumbum
```

另一种方式是使用你已经配置好的GitHub SSH/HTTPS认证克隆。不要把GitHub令牌写进clone URL；下载ZIP已足够，不需要新手额外配置Git。

## 10. 放入数据库CA

**ECS终端：**

```bash
cd ~/bumbum
mkdir -p secrets
chmod 700 secrets
```

确认目标文件尚未存在，再复制第6节已验证的CA：

```bash
cp ~/bumbum-ca/mysql-ca.pem secrets/mysql-ca.pem
chmod 644 secrets/mysql-ca.pem
openssl x509 -in secrets/mysql-ca.pem -noout -subject -issuer -dates
```

成功标志：能解析PEM证书，未过期，来源与控制台一致。这里展示证书公开信息，不是密钥。CA是公开证书，644让容器node用户可以读取；父目录仍限制访问。**不要将数据库私钥、网站私钥或SSH私钥放进这个文件。**

## 11. 创建应用与迁移配置

有两种方式：建议使用下方交互生成器，避免密码含特殊字符导致URL错误。它只在你自己的ECS上运行，密码不回显，自动进行百分号编码和生成会话密钥，不调用外部服务。

### 11.1 推荐：交互生成配置

确认项目目录还没有 `.env`、`.env.migrate`。下面程序遇到已有文件会拒绝，不覆盖它们。

**ECS终端整块复制：**

```bash
cd ~/bumbum
python3 - <<'PY_CONFIG'
from pathlib import Path
from getpass import getpass
from urllib.parse import quote
import re, secrets, os, sys
# Python程序来自粘贴的代码块，交互输入改从当前终端读取。
sys.stdin=open("/dev/tty", "r")
if any(Path(p).exists() for p in ('.env', '.env.migrate')):
    raise SystemExit('配置文件已存在，请使用nano编辑，不覆盖。')
domain=input('网站完整子域名（只填主机名，如 nfc.example.com）: ').strip()
if not re.fullmatch(r'[A-Za-z0-9.-]+',domain) or '.' not in domain:
    raise SystemExit('域名格式不正确，不填写https://或路径。')
email=input('证书通知邮箱: ').strip()
host=input('MySQL内网域名（不填协议或端口）: ').strip()
if not re.fullmatch(r'[A-Za-z0-9.-]+',host):
    raise SystemExit('数据库域名格式不正确。')
port=input('MySQL端口 [3306]: ').strip() or '3306'
if not port.isdigit() or not 1 <= int(port) <= 65535:
    raise SystemExit('端口不正确。')
database=input('项目数据库名 [bumbum_mvp]: ').strip() or 'bumbum_mvp'
if not re.fullmatch(r'[A-Za-z0-9_]+',database):
    raise SystemExit('请使用字母/数字/下划线库名。')
app_user=input('应用账号 [bumbum_app]: ').strip() or 'bumbum_app'
migrate_user=input('迁移账号 [bumbum_migrate]: ').strip() or 'bumbum_migrate'
app_password=getpass('应用数据库密码（不回显）: ')
migrate_password=getpass('迁移数据库密码（不回显）: ')
if not app_password or not migrate_password or app_user==migrate_user:
    raise SystemExit('密码不能为空；两个数据库账号必须分离。')
if any(c in email for c in '\r\n') or not email:
    raise SystemExit('邮箱不能为空。')
def url(user,password):
    return f'mysql://{quote(user,safe="")}:{quote(password,safe="")}@{host}:{port}/{database}'
os.umask(0o077)
app=(f'APP_IMAGE=bumbum:1.0.0\nSITE_DOMAIN={domain}\nACME_EMAIL={email}\n'
     f'PUBLIC_BASE_URL=https://{domain}\nDATABASE_URL={url(app_user,app_password)}\n'
     f'SESSION_SECRET={secrets.token_hex(32)}\nDB_TLS=true\nDB_CA_FILE=/run/db-ca.pem\n')
migration=f'DATABASE_URL={url(migrate_user,migrate_password)}\nDB_TLS=true\nDB_CA_FILE=/run/db-ca.pem\n'
for name,content in (('.env',app),('.env.migrate',migration)):
    with open(name,'x') as f: f.write(content)
    Path(name).chmod(0o600)
print('配置已生成；未输出密码或会话密钥。')
PY_CONFIG
```

密码中 `@ # % : / ? $` 等字符已编码，不要再人工重复编码。生成器用的是数据库密码，不是网站管理员密码。

### 11.2 已有配置或手工填写

已有文件只编辑，不再复制示例覆盖：

```bash
nano .env
nano .env.migrate
```

nano保存：Ctrl+O → 回车；退出：Ctrl+X。配置含真实密码，不截图、不粘贴到聊天。

| 字段 | 填写内容 |
|---|---|
| APP_IMAGE | 首版bumbum:1.0.0 |
| SITE_DOMAIN | 只域名，例如nfc.example.com |
| ACME_EMAIL | 有效邮箱 |
| PUBLIC_BASE_URL | https://正式域名，与浏览器使用地址完全一致 |
| DATABASE_URL（.env） | 应用账号、编码后密码、内网域名、端口和项目库 |
| SESSION_SECRET | 64位或以上随机字符串；生成器已生成 |
| DB_TLS | true；生产不允许false |
| DB_CA_FILE | /run/db-ca.pem（容器内路径，不是ECS路径） |
| DATABASE_URL（.env.migrate） | 迁移账号URL，不能用应用账号冒充 |

`format: raw` 服务配置的值不要包引号；不要把生产 `.env` 当shell脚本 `source`。Caddyfile本身读取SITE_DOMAIN和ACME_EMAIL，不需要手工改代理地址；保持 `reverse_proxy app:3000`。

只检查权限和语法，不打印完整配置：

```bash
chmod 600 .env .env.migrate
ls -l .env .env.migrate secrets/mysql-ca.pem
sudo docker compose config --quiet
```

成功标志：两份.env显示 `-rw-------`，CA可读，`config --quiet` 没有报错。不要运行完整 `docker compose config` 并将输出发给别人，会包含密码。

## 12. 构建、建表、授权、创建管理员

### 12.1 构建镜像

**ECS终端：**

```bash
cd ~/bumbum
sudo docker compose build app
```

成功标志：命令退出成功并生成 `bumbum:1.0.0`。构建阶段不连接真实数据库。首次下载镜像/依赖需要网络和时间；2核4GB一次只运行一个构建。

```bash
sudo docker image inspect bumbum:1.0.0 --format '{{.Id}}'
```

输出的sha256是本地镜像标识，可以记入部署记录。若OOM/磁盘不足，先查 `free -h`、`df -h`、`sudo docker system df`，不要删除数据库/证书卷。网络或证书失败按错误诊断，不关闭TLS校验。

### 12.2 用迁移账号建表

先核对 `.env.migrate` 指向你专用的项目库；有已有数据先备份。

```bash
sudo docker compose run --rm tools migrate
```

初次预期：

```text
Applied 001_initial.sql
Migrations complete
```

重复运行预期只有 `Migrations complete`，不会重建/重置现有数据。失败不要继续启动，不删除schema_migrations、不修改已应用SQL文件、不用reset/db push。MySQL DDL不是整批事务回滚，中断需要核对实际表结构再修复。

用第6节迁移客户端连接后检查：

```sql
SHOW TABLES;
SELECT name, completed FROM schema_migrations;
EXIT;
```

应有 garments、tags、admins、admin_sessions、audit_logs、login_attempts、schema_migrations；迁移completed=1。

### 12.3 应用账号表级权限

以下SQL需要能授权的数据库管理账号。**迁移账号不一定有GRANT权限，不要为此把高权限管理账号放进.env。** 可在RDS支持的SQL管理界面执行，或用安全客户端连接管理账号。

首先核对实际账号的host授权对象：

```sql
SHOW GRANTS FOR 'bumbum_app'@'%';
```

若实际不是 `%`，下方SQL替换为真实对象，不创建第二个不明同名账号。新建专用账号不得有全局权限、其他库权限；若已授予 `bumbum_mvp.*` 整库读写，先通过控制台/管理者撤销这个账号的整库套餐，再设置表级权限。**增加表级GRANT不会自动降低已有整库权限。**

```sql
GRANT SELECT, INSERT, UPDATE ON bumbum_mvp.garments TO 'bumbum_app'@'%';
GRANT SELECT, INSERT, UPDATE ON bumbum_mvp.tags TO 'bumbum_app'@'%';
GRANT SELECT ON bumbum_mvp.admins TO 'bumbum_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON bumbum_mvp.admin_sessions TO 'bumbum_app'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON bumbum_mvp.login_attempts TO 'bumbum_app'@'%';
GRANT SELECT, INSERT ON bumbum_mvp.audit_logs TO 'bumbum_app'@'%';
GRANT SELECT ON bumbum_mvp.schema_migrations TO 'bumbum_app'@'%';
SHOW GRANTS FOR 'bumbum_app'@'%';
```

核对：应用对audit_logs只有SELECT/INSERT，无UPDATE/DELETE；对admins只有SELECT；无DDL权限、无全局/整库大权限。账号来源仍受VPC/白名单限制。权限无法精确配置时找数据库管理者确认，不把“能登录”当作权限验收完成。

### 12.4 创建网站管理员

**ECS终端，不是在mysql>：**

```bash
sudo docker compose run --rm tools admin
```

依次输入网站管理员用户名、密码、重复密码。密码不回显，12–128位，无默认线上密码。成功提示“管理员创建成功”。请存入密码管理器。

这不是创建数据库账号；不修改.env、不把网站管理员密码注入长期app。重复用户名会拒绝，不覆盖旧管理员。

## 13. 启动HTTPS网站

确认：数据库迁移完成、应用表级权限完成、CA正确、管理员创建成功、DNS和80/443规则正确。

**ECS终端：**

```bash
sudo docker compose up -d --wait app caddy
sudo docker compose ps
sudo docker compose logs --tail=100 app caddy
```

成功标志：app为healthy，caddy运行，无持续数据库/证书错误。Caddy不带应用健康检查，运行中也不等于证书已成功，必须继续访问验证。

生产Compose只有app/caddy长期运行，tools为一次性工具，无第二套MySQL。app监听容器内0.0.0.0:3000，不映射到公网；Caddy代理app:3000，开放80/443。app/caddy有自动重启策略；Caddy/data和/config持久化，容器日志每份10MiB最多3份。

### 13.1 检查健康和浏览器

替换正式域名：

```bash
curl --fail --show-error https://nfc.example.com/health
```

预期：`{"status":"ok"}`，TLS无证书错误。不要用curl -k或浏览器“继续访问”作为通过。

**电脑和iPhone14浏览器：**

1. 打开 `https://正式域名/health`，看见ok。
2. 打开 `https://正式域名/admin/login`。
3. 输入第12.4节的**网站管理员**用户名和密码。
4. 登录进入服装列表；不应该输入数据库账号密码。

手机关闭Wi-Fi改用移动网络再次验证。PUBLIC_BASE_URL必须和浏览器正式HTTPS地址一致；不要用ECS IP登录后台，否则写接口Origin校验可能拒绝。

### 13.2 不公开应用端口

```bash
sudo docker compose ps
sudo ss -ltnp
```

app的 `3000/tcp` 只是容器内部端口声明，不能出现 `0.0.0.0:3000->3000`。数据库不开放3306公网。Caddy应显示80和443的主机端口映射。还需从外部网络核对安全组和防火墙，内部命令不能替代外部检查。

## 14. 软件验收：先不要写实体标签

下面是虚拟资料，只用于软件测试，手机号也不是任何真实所有者认证。示例文件见 [DEMO-DATA.json](DEMO-DATA.json)。

### 14.1 建立服装A/B

后台“服装 → 新增服装”：

| 字段 | A | B |
|---|---|---|
| 名称 | 模拟黑色外套A | 模拟白色衬衫B |
| 实例编号 | DEMO-A001 | DEMO-B001 |
| 颜色 | 黑色 | 白色 |
| 公开状态 | 已发布 | 已发布 |

其余可留空，图片只填可信HTTPS图片网址。保存后记下详情地址中的UUID。默认草稿不公开；要选择已发布才能公共访问。

### 14.2 登记模拟标签

后台“标签 → 登记标签”：

| 字段 | 模拟A | 模拟B |
|---|---|---|
| UID | 04DE0000000001 | 04DE0000000002 |
| 备注 | 模拟测试，不是实体UID | 模拟测试，不是实体UID |

UID是14位十六进制；空格、冒号、短横线会规范化，重复UID会拒绝。以上是**虚拟UID**，不能冒充真实芯片。

创建后进入标签详情，在“按服装名称/实例编号搜索”输入DEMO-A001或DEMO-B001，点查找，选择对应服装，填写原因（例如“软件模拟绑定”），确认。复制每个“固定入口”，记为入口A、入口B。

### 14.3 逐项验收

| 序号 | 操作 | 预期结果 |
|---|---|---|
| 1 | 分别打开入口A、B | 分别显示对应服装，不串号 |
| 2 | 编辑A名称并保存，再打开入口A | 新名称出现；入口URL不变 |
| 3 | 在A“独立修改所有者”填虚拟手机号13800000001及原因，最终确认 | 后台显示登记值；公开页只显示“后台已登记所有者” |
| 4 | 查看A审计记录 | 所有者修改有记录，列表手机号脱敏，管理员可查看完整详情 |
| 5 | 清空A手机号，填原因并确认 | 未登记；审计留痕 |
| 6 | 尝试把标签A绑定B（B已有标签） | 冲突，原A/B绑定不被挤掉 |
| 7 | 先解绑标签B，再把标签A改绑服装B | 原入口A现在显示B；服装所有者不自动转移 |
| 8 | 停用标签A后打开入口A | 可读停用页，410 |
| 9 | 重新启用标签A | 恢复显示B |
| 10 | 解绑标签A | 可读尚未关联页，409 |
| 11 | 再绑定B，将B改草稿/下架 | 入口和直接服装详情均404不可用 |
| 12 | B重新发布 | 正常详情恢复 |
| 13 | 打开未知入口码 | 404，不显示数据库或堆栈 |
| 14 | 保存非法手机号、重复实例编号、非HTTPS图片 | 拒绝并保留表单内容 |
| 15 | 两个浏览器标签页编辑同一记录，先后保存 | 旧version返回冲突，不能无提示覆盖 |
| 16 | 退出登录，再访问管理页面/API | 页面要求登录，API401 |

模拟记录不永久删除，测试完成停用模拟标签并清楚标注。不要在模拟标签上点击“已人工核对写入”，这只应在实体回读和实际打开成功后标记。

### 14.4 用命令验证302/no-store/公开字段

下面先设置**公开地址**，不包含密码。用后台复制的实际URL替换：

```bash
SITE_URL='https://nfc.example.com'
TAG_URL='https://nfc.example.com/t/替换为后台生成入口码'
GARMENT_ID='替换为服装详情UUID'
```

标签必须启用、已绑定、目标已发布。使用GET查看响应头，不用curl -L先跟随跳转：

```bash
curl --silent --show-error --dump-header - --output /dev/null "$TAG_URL"
curl --silent --show-error --dump-header - --output /dev/null "$SITE_URL/g/$GARMENT_ID"
curl --silent --show-error --dump-header - --output /dev/null "$SITE_URL/api/public/garments/$GARMENT_ID"
```

预期入口 `302`、`Location: /g/实际UUID`、`Cache-Control: no-store`；详情及公开API也no-store。不是301/308，不应跳到任意外链。

```bash
curl --fail --show-error "$SITE_URL/api/public/garments/$GARMENT_ID"
curl --silent --show-error --dump-header - "$SITE_URL/api/admin/me"
```

第一项只公开服装白名单和ownerRegistered，不应有手机号、真实UID、entry_code、审计或管理员字段。第二项不带登录Cookie，应401并提示先登录。

匿名访问API的检查不能代替查看公开HTML/手机浏览器网络响应。对包含私人数据的后台响应不要录屏/截图公开分享。

### 14.5 重启验证

```bash
sudo docker compose restart app
sudo docker compose ps
```

等待约30秒或直到healthy，再执行公开健康命令，重新登录看服装/标签/所有者/审计仍在。Docker健康失败不会自动因unhealthy而重启；restart策略处理进程退出，数据库问题应排查并监控告警。

完整ECS重启测试选择维护窗口，先保存所有终端工作：

```bash
sudo systemctl is-enabled docker
sudo reboot
```

Workbench断开是正常的。实例恢复后重新登录，检查 `sudo docker compose ps`、健康接口和固定入口。不要把应用进程重启当作已经验证整台ECS开机恢复。

## 15. 自动测试怎样运行

已有结果：17组MySQL集成测试、2项Chromium浏览器测试通过；生产容器、严格TLS、代理、Secure Cookie、重启和初始化入口验证通过。见 [TEST-REPORT.md](TEST-REPORT.md)。这不是你真实ECS/RDS的验收结果。

**不要在生产目录运行故障注入测试。** 集成测试会停止隔离数据库、临时撤销本地审计写入权限并生成虚拟记录。生产目录只做第14节受控业务验收。

想自己重复自动测试，在独立开发机/隔离工作区准备Node24.19.0、Docker+Compose和Chromium；Linux下运行，无sudo的Docker命令要求该测试用户已具备Docker权限，不要因此改生产服务器权限：

```bash
npm ci --cache /tmp/bumbum-npm
npm run build
bash scripts/local-db.sh
bash scripts/test.sh
npm run test:browser
```

集成测试必须显示17通过0失败0跳过，浏览器测试2通过。使用系统Chromium默认 `/usr/bin/chromium`；不同路径用 `CHROMIUM_PATH=/实际路径 npm run test:browser`。配套Playwright浏览器可用 `npx playwright install chromium` 获取，但需要网络及系统依赖，不忽略安装失败。

可选在**无已有部署配置**的专用本地检出执行：

```bash
bash scripts/test-containers.sh
```

它会建立本地测试CA和受限回环HTTPS，验证生产镜像而不连接云库，结束后停测试app/caddy、保存配置到忽略的.local。测试CA不能上传生产替代阿里云CA。先读README和报告，普通产品验收无需亲自运行这套开发测试。

## 16. 实体NTAG424 DNA验证

软件全部通过后才做。先记录iPhone14实际iOS版本、读写工具版本、两枚完整标签封装/天线、现有NDEF和读写权限。工具必须支持当前NTAG424 DNA配置；未知密钥时找供应商，不试改密钥、不锁卡、不启用SUN/SDM。

一次做一枚标签：

1. 给实体贴A标记，回读**真实7字节UID**，不要把变化的随机读卡ID当真实UID。
2. 在后台用真实UID登记新标签，备注“真实标签A”，绑定已发布的服装A。UID创建后不可改写。
3. 复制正式HTTPS固定入口，先在iPhone Safari手动打开，核对服装。
4. 兼容工具写入单个NDEF URI网址；不写手机号，不截断随机入口码。后台NDEF估算还需按工具实际编码核对容量。
5. 回读标签URL，逐字与后台入口核对。
6. 退出写卡工具的扫描状态，点亮解锁iPhone，顶部靠近标签，点击系统NFC通知。
7. 页面正确后才在后台点“已回读URL并实际打开，标记人工核对”。这个按钮本身不会写卡。
8. A通过再做B，保持UID和网址一一对应。

A/B各独立读取10次，记录出现通知、是否点击、最终服装、网络、耗时；打开的页面必须100%指向正确服装。项目目标每枚至少9/10识别成功，识别失败与网页加载失败分开记录。

然后保持芯片URL不重写，依次修改名称、所有者、绑定和停用，重新触碰验证最新结果。已打开网页不会自动实时刷新，需要新请求。

用 [NFC-ACCEPTANCE.md](NFC-ACCEPTANCE.md) 记录真实结果。普通URL可以复制，不能因读取成功宣称防伪成功或证明所有权。

## 17. 日常操作与排错

所有命令在 `~/bumbum` 运行：

```bash
sudo docker compose ps
sudo docker compose logs --tail=100 app
sudo docker compose logs --tail=100 caddy
df -h
free -h
```

日志发给别人前仍检查并脱敏；只提供相关错误类别/requestId，不发送.env、完整环境输出或数据库密码。

| 现象 | 优先检查 | 正确处理 |
|---|---|---|
| Workbench不能登录 | SSH认证、安全组当前来源 | 按阿里云连接诊断 |
| MySQL超时 | 内网域名/端口、VPC、白名单 | 确认ECS私网IP，不开放全公网 |
| Access denied | 账号密码、账号host、项目授权 | 验证两个账号及实际SHOW GRANTS |
| TLS/主机名错误 | CA来源、有效期、内网域名是否匹配 | 使用官方正确CA/域名，不关闭校验 |
| config报format字段错误 | Compose版本 | 升级到>=2.30.0 |
| tools找不到镜像 | 尚未构建/APP_IMAGE错误 | 先compose build app |
| migration失败/未完成 | 权限、既有表、目标库、连接 | 停止后检查，不删迁移记录重试 |
| app unhealthy/503 | 数据库连接、表和权限 | 先读app日志，再查网络/授权 |
| bind address already in use | 80/443已有站点 | 确认现有服务，制定共存方案 |
| 502 | Caddy到app不可达 | app healthy、app:3000、容器网络、NO_PROXY |
| 公网无法访问 | DNS、安全组、防火墙、容器 | 从移动网络验证，不只看ECS内部 |
| 证书申请失败 | DNS、80/443、AAAA/CAA、ACME外连 | 按Caddy日志排查，不反复删证书卷 |
| 后台来源403 | PUBLIC_BASE_URL与实际访问不一致 | 用正式域名HTTPS，改配置后重建运行容器 |
| 登录429 | 同IP+账号15分钟5次失败 | 等窗口结束并核对密码，不连续尝试 |
| 旧页面数据 | 未发新请求/异常缓存 | 刷新并查302/no-store，不用301固定映射 |
| UID重复/绑定409 | 旧记录或目标已有标签 | 先检查资产和解绑流程，不静默覆盖 |
| 手机无NFC通知 | NDEF、天线、位置、扫描状态 | 回读URL再定位硬件，不直接改AES密钥 |

暂停网站：

```bash
sudo docker compose stop app caddy
```

恢复：

```bash
sudo docker compose up -d --wait app caddy
```

不要日常使用 `down -v`、卷删除或数据库重置。日志有大小限制，磁盘不足先查占用，不清空/var/lib/docker。

## 18. 备份与恢复准备

1. 在RDS控制台开启自动备份，确认备份保留期、成功记录和PITR能力（以具体产品为准）。
2. 第一次正式运营前，以及每次升级前，建立手工备份并记录ID/时间。
3. 真正恢复一次到**新的隔离数据库**，核对服装、标签、所有者和审计；“有备份按钮”不代表已经证明可恢复。
4. 用密码管理器/受保护备份保存.env配置，Caddy证书卷也需运维备份；不要把备份上传公开仓库。
5. 备份包含敏感手机号，限制访问并加密存储。恢复测试不使用原生产库来演练。

若要恢复旧备份，先计算备份后会丢失哪些登记/绑定修改，制定停写、隔离恢复、核对和切换计划；不得直接把线上库覆盖成旧版本。

## 19. 更新与回滚

首次部署不要执行本节。已上线后固定入口域名和/t/路径不能随意更换。

### 19.1 升级前

记录当前代码版本/下载时间、数据库迁移状态、健康和A/B结果，备份数据库/受保护配置。保留旧镜像：

```bash
cd ~/bumbum
sudo docker image inspect bumbum:1.0.0 --format '{{.Id}}'
sudo docker image tag bumbum:1.0.0 bumbum:rollback-1.0.0
```

此例针对首版；后续替换为实际旧镜像，不覆盖之前要保留的rollback标签。

新代码先放独立发布目录，不覆盖旧目录的.env/CA。将旧配置安全复制到新发布目录（只在目标无配置时），CA也复制，编辑APP_IMAGE为新唯一版本标签，例如bumbum:1.0.1。两个目录生产Compose的项目名都是bumbum，所以切换会管理同一组app/caddy和证书卷；不要同时把它们当两个不同网站启动，也不要改变项目名来绕过端口冲突。

### 19.2 升级执行

1. 在独立MySQL8.0验证新代码和迁移，确认与旧镜像的schema兼容性。
2. 在新发布目录构建 `sudo docker compose build app`。
3. 备份并按需要暂停写入，执行 `sudo docker compose run --rm tools migrate`；失败不继续。
4. 执行 `sudo docker compose up -d --wait app caddy`。
5. 重新执行健康、后台、A/B入口、所有者、审计和302/no-store检查；记录实际新版本。

### 19.3 回滚

只有数据库schema仍兼容旧应用时，才能单纯回滚镜像。将当前部署目录.env中的APP_IMAGE改为 `bumbum:rollback-1.0.0`，然后：

```bash
sudo docker compose up -d --no-build --wait app caddy
```

重新验证健康与业务。没有自动回滚数据库迁移；不要为回滚执行旧reset或删表。不兼容时停止写入，由数据库管理者进行前向修复或隔离恢复后受控切换。

## 20. 最终验收打勾表

- [ ] ECS/数据库产品、地域、VPC、内网域名和端口已核对。
- [ ] 两个数据库账号分离，项目专属授权，应用表级权限实际确认。
- [ ] ECS客户端和应用容器严格TLS连接成功，CA/域名有效。
- [ ] DNS正确、80/443外部可达、22限来源、3000/3306不公开。
- [ ] 构建、迁移、网站管理员初始化真实执行成功。
- [ ] 正式HTTPS无警告，健康ok，后台可登录。
- [ ] A/B映射、更新、改绑、停用、解绑、下架、所有者与审计通过。
- [ ] 无会话管理接口401，公开HTML/API无手机号/UID/入口码泄漏。
- [ ] app重启和维护窗口ECS重启后网站与数据恢复。
- [ ] 两个真实UID/NDEF回读一致，iPhone14真实触碰和不重写更新通过。
- [ ] RDS备份恢复已演练，证书续期/监控、费用和到期事项已安排。

遇到问题时提供：当前阶段、操作位置、去掉秘密后的命令、预期/实际结果、相关脱敏日志及requestId。不要提供完整.env、数据库密码、管理员密码或芯片密钥。
