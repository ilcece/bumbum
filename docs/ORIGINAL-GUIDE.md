# bumbum 数字服装项目：从云资源到 NFC 测试的操作手册

版本：V1.0　日期：2026-10-13
适用环境：iPhone 14；香港 ECS，Ubuntu 22.04 64 位，2 核 4 GB、40 GB 系统盘；香港 MySQL 8.0，与 ECS 同 VPC。
配套需求：digital-clothing-prd-v0.1.md（文档内部版本 V0.2）。

这是一份操作计划，不代表网站已经开发或服务器已经配置。你可以先完成阶段 1–4 的准备；阶段 5 以后需要 Codex 先交付实际代码与部署文件。以下 MySQL 控制台步骤按“云数据库 RDS MySQL”说明；如果控制台产品名称是 PolarDB、云数据库其他产品或自行安装的 MySQL，请先核对，不能直接套用菜单。

## 0. 先理解要搭建什么

- NFC 标签：存一个固定 HTTPS 网址，像打开网站的快捷入口。
- 域名解析：让这个网址找到你的 ECS 公网 IP。
- ECS：运行网页与后台程序。
- Caddy：接收外部访问、管理 HTTPS 证书，再把请求交给应用。
- MySQL：保存服装资料、芯片 UID、入口与服装的对应关系、所有者和修改记录。
- Docker：把程序和依赖打包运行；Compose 是统一启动这些服务的工具。

NFC 标签入口示例：`https://nfc.example.com/t/随机入口码`。`example.com` 只是示例，必须替换为你自己的域名。数据库内网地址与 ECS 公网 IP 是不同东西：前者填进应用配置，后者填进域名解析。

第一版所有者由管理员登记，不做用户自助认领；普通 URL 不提供芯片防伪。不要把手机号或数据库密码写入标签。

| 阶段 | 你操作的地方 | 完成标志 |
| --- | --- | --- |
| 1 整理参数 | 阿里云控制台 | 地址、端口、VPC、子域名已记录 |
| 2 准备数据库 | 数据库控制台 | 建库、建账号、白名单完成 |
| 3 连接 ECS | ECS 控制台 / Workbench | 能看到服务器命令行 |
| 4 验证基础环境 | ECS 命令行、DNS 控制台 | 数据库能连接，域名解析正确 |
| 5 开发软件 | Codex 工作区 | 代码、迁移和测试报告已交付 |
| 6 部署应用 | ECS 命令行 | 应用运行，数据持久化 |
| 7 HTTPS 和网页验收 | 浏览器 / 手机 | 正式 HTTPS 域名能登录后台与查看详情 |
| 8 写入 NFC | 手机读写工具 / 实体标签 | 两标签分别打开正确服装 |
| 9 更新与维护 | ECS、数据库控制台 | 能备份、更新、排错与恢复 |

## 1. 建一份自己的配置记录

在本地笔记中记录下表；密码存在密码管理器，不需要发给 Codex。

| 名称 | 到哪里找 | 用途 |
| --- | --- | --- |
| ECS 公网 IP | ECS 实例详情 → 基本信息 | DNS A 记录 |
| ECS 私网 IP | ECS 实例详情 → 网络与安全组或基本信息 | 数据库白名单 |
| ECS 登录用户名 | 创建实例时的登录设置 | Workbench 登录；不要猜一定是 root |
| VPC ID | ECS、数据库实例详情 | 比对网络 |
| 数据库具体产品名 | 控制台产品标题 | 确认是否 RDS |
| MySQL 内网连接地址 | 数据库实例 → 数据库连接 | 应用连接数据库 |
| MySQL 端口 | 同上 | 通常 3306，以控制台为准 |
| 项目数据库名 | 后面创建 | 建议 bumbum_mvp |
| 应用数据库账号 | 后面创建 | 建议 bumbum_app |
| 迁移账号 | 后面创建 | 建议 bumbum_migrate |
| 网站域名 | 自己选择 | 建议 nfc.你的域名 |
| iOS 版本 | iPhone 设置 → 通用 → 关于本机 | 实体测试记录 |

不要把内网连接地址误写成 `localhost`：在 ECS 上，localhost 指 ECS 自己；在容器里则指该容器自己。

## 2. 配置数据库

### 2.1 确认产品与连接地址

操作位置：阿里云控制台 → 云数据库 RDS → 地域选中国香港 → 点击你的 MySQL 实例。

1. 查看数据库版本为 MySQL 8.0、实例运行正常。
2. 查看专有网络 VPC，与 ECS 对照。
3. 找“数据库连接”或“连接信息”。
4. 复制内网连接地址及端口。程序要使用可读写的主实例连接地址，不选只读实例地址。
5. 不需要为了让手机访问网站而申请数据库公网地址；手机只访问 ECS 上的网站。

成功标志：你拿到类似 `……mysql.rds.aliyuncs.com` 的内网主机名和端口。

### 2.2 创建项目数据库

操作位置：实例 → 数据库管理 → 创建数据库。

建议填写：

| 字段 | 内容 |
| --- | --- |
| 数据库名 | bumbum_mvp |
| 字符集 | utf8mb4 |
| 描述 | bumbum NFC MVP 测试数据库 |

如果页面要求先选账号，可先完成下一节创建普通账号，再回来创建并授权。不要改名或删除已有数据库。

这一步只是创建数据存放的空间，不用你手工创建 garments、tags 等表。表结构应由 Codex 交付的迁移命令建立。

成功标志：数据库列表中出现 `bumbum_mvp`，状态正常。

### 2.3 创建两个项目账号

操作位置：实例 → 账号管理 → 创建账号。

| 账号 | 类型 | 授权范围 | 建议权限 |
| --- | --- | --- | --- |
| bumbum_app | 普通账号 | 仅 bumbum_mvp | 仅 DML，用于读写业务数据 |
| bumbum_migrate | 普通账号 | 仅 bumbum_mvp | 读写（DDL + DML），用于建表、迁移、初始化 |

注意，“仅 DML”与控制台“读写”权限不同：普通读写往往含修改表结构权限。应用账号不应默认使用实例高权限账号。具体 ORM 如果需要额外权限，由 Codex依据报错核对最小必要权限，不直接扩大到全实例。

分别设置强密码并保存。数据库账号和网站管理员账号是两类账号，后者等应用部署后用初始化命令创建。

成功标志：两个账号均已授权给正确数据库，其他业务库未授权。

### 2.4 设置白名单

操作位置：数据库实例 → 数据安全性 / 白名单与安全组 → IP 白名单。

1. 新建白名单分组，例如 `bumbum_ecs`。
2. 填 ECS 的私网 IP，不是公网 IP，也不是你电脑的 IP。
3. 如果支持“加载 ECS 内网 IP”，选择当前 ECS，并核对地址。
4. 保存，保留原有默认和系统分组。
5. 不填写 `0.0.0.0/0`；不把全 VPC 网段作为起步默认范围。

成功标志：分组显示正确 ECS 私网 IP。Docker 应用通常通过 ECS 主机地址访问 RDS；部署后还要从应用实际运行环境复验连接。

### 2.5 查看备份与数据库加密连接

- 找“备份恢复”，确认自动备份策略、时间与保留期限；实际可选值和费用以实例页面为准。
- 上线和每次表结构升级前创建可恢复备份，记录时间。
- 找 SSL / TLS 设置；记录是否已启用，以及是否有 CA 证书可下载。
- 如果启用数据库 TLS，把对应 CA 证书提供给服务端配置；网站 HTTPS 与数据库 TLS 是两段不同的连接。

不要自行关闭已有 TLS 来解决连接报错。证书、域名匹配与驱动配置由 Codex 配合检查。

## 3. 登录 ECS 并检查系统

### 3.1 使用浏览器登录

操作位置：ECS 控制台 → 实例 → 你的服务器 → 远程连接 → Workbench。

1. 选择登录方式，填写实际用户名及密码或密钥。
2. 首次使用可能出现 Workbench 角色授权或专用 SSH 来源安全组提示，按阿里云提示配置。
3. 忘记密码时，使用控制台“重置密码”；注意控制台是否要求重启才能生效，先确认服务器暂无需保持运行的业务。
4. 登录后看到命令行提示符，说明你正在 ECS 上操作。

终端输入密码通常不显示星号，正常输入并按回车即可。不要把密码放在命令文字后面。

### 3.2 基础检查

以下在 ECS 的 Workbench 终端执行，一条一条运行；不要在数据库 SQL 编辑器里运行。

```bash
whoami
cat /etc/os-release
uname -m
free -h
df -h
```

预期：系统是 Ubuntu 22.04，架构应与实例一致，内存约 4 GB、系统盘约 40 GB。显示值略小于购买值正常。`whoami` 显示当前登录用户。

检查现有软件和端口：

```bash
docker --version
docker compose version
sudo ss -lntp
sudo ufw status
```

提示 command not found 代表 Docker 尚未安装。若 Docker 已存在或 80/443 已被服务占用，先让 Codex核对，不要删除现有软件。不要仅因为 UFW 未启用就直接开启，避免断开 SSH；当前先用阿里云安全组控制入口。

### 3.3 安装基础工具与 MySQL 客户端

```bash
sudo apt update
sudo apt install -y ca-certificates curl git unzip mysql-client
```

这只安装数据库连接工具，不是在 ECS 上再安装 MySQL 服务。出现网络、软件源或锁占用错误时，记录原始错误后排查，不连续重试安装或随意换未知软件源。

## 4. 安全组、数据库连接与域名

### 4.1 配置 ECS 安全组

操作位置：ECS 实例 → 网络与安全组 → 点击实际绑定的安全组 → 入方向 → 添加规则。

| 协议与端口 | 来源 | 用途 |
| --- | --- | --- |
| TCP 80 | 0.0.0.0/0 | HTTP 跳转与证书验证 |
| TCP 443 | 0.0.0.0/0 | HTTPS 网站 |
| TCP 22 | Workbench 指定服务来源，或你的可信管理公网 IP | SSH 管理 |

不需要对公网放行 3000、3306、Docker 管理端口或宝塔端口。规则中填写单个来源 IP 时，控制台可能要求 `/32`。如已有宽泛规则，增加限制规则并不会自动取消旧规则，需核对所有入方向规则。

如果出方向受限制，应核对 DNS、HTTPS 软件下载和 MySQL 内网端口允许情况。不要一次修改全部出方向策略。

成功标志：80/443 允许公网访问，远程管理仍能登录；此时没有网站程序，浏览器仍打不开网页也正常。

### 4.2 在 ECS 上验证 MySQL

将下方示例主机名替换成自己的内网地址，端口替换为实际值：

```bash
mysql -h YOUR_RDS_INTERNAL_HOST -P 3306 -u bumbum_app -p bumbum_mvp
```

`-p` 后不写密码。按回车后输入数据库账号密码。若数据库强制 TLS，先按实际配置追加证书与校验参数；例如 CA 已保存到指定路径、证书支持主机名校验时：

```bash
mysql -h YOUR_RDS_INTERNAL_HOST -P 3306 -u bumbum_app -p --ssl-mode=VERIFY_IDENTITY --ssl-ca=/实际路径/rds-ca.pem bumbum_mvp
```

不要在未准备证书时直接复制第二条。普通连接命令用于初步诊断，不等于已验证 TLS 证书。

进入 `mysql>` 后执行以下 SQL：

```sql
SELECT VERSION(), DATABASE(), CURRENT_USER();
SHOW TABLES;
SHOW SESSION STATUS LIKE 'Ssl_cipher';
EXIT;
```

预期：MySQL 8.0、数据库名 bumbum_mvp；现在还没有建表，空结果正常；Ssl_cipher 非空说明会话使用了加密，但不单独证明服务器证书身份校验已完成。

再用迁移账号测试登录。SQL 在 `mysql>` 里执行；Ubuntu 命令在系统提示符执行，不要混用。

失败时按顺序检查：主机名和端口 → VPC → 白名单私网 IP → 账号和密码 → 该库权限 → TLS。不要用“开放公网全部访问”替代排错。

### 4.3 配置域名解析

建议使用 `nfc.你的域名`，这样不会影响已有主站。

操作位置：实际 DNS 服务商的解析控制台。如果域名 DNS 托管在阿里云：云解析 DNS → 公网权威解析 → 主域名 → 解析设置 → 添加记录。

| 字段 | 示例 |
| --- | --- |
| 记录类型 | A |
| 主机记录 | nfc |
| 记录值 | ECS 公网 IPv4 |
| 解析线路 | 默认 |
| TTL | 默认 |

主机记录通常只填 `nfc`，系统会拼成 `nfc.example.com`。不要填私网 IP、数据库地址、`https://` 前缀或 `/t/` 路径。已有同名 CNAME/A 记录先核对用途，不盲目删除；不要额外添加不正确的 AAAA 记录。

域名购买在阿里云不代表 DNS 必然由阿里云托管，先确认权威 DNS；为本项目添加记录通常不需要修改整套 DNS 服务器。

在 ECS 终端验证：

```bash
getent ahostsv4 nfc.example.com
```

替换域名后，返回地址应含 ECS 公网 IP。解析缓存可能导致不同设备生效时间不同。此时只能证明“域名指向服务器”，不能证明网站已上线。

## 5. 让 Codex 交付可部署项目

把需求文档和本手册交给 Codex。你不需要自己编写业务代码。要求先完成软件，再部署；不能把空服务器当成网站。

可复制指令：

> 请依据需求文档 V0.2 和操作手册实现 bumbum NFC MVP。使用单项目 TypeScript Web 应用、MySQL 8.0，本地隔离数据库测试；部署目标为香港 Ubuntu 22.04 ECS，2 核 4 GB，已有同 VPC 阿里云 MySQL。请先完成软件与管理后台并验证，再交付 Dockerfile、生产 compose.yaml、Caddyfile、.dockerignore、.gitignore、.env.example、独立迁移/管理员初始化入口、部署与回滚说明。生产 Compose 不部署第二套 MySQL，不公开应用 3000 端口，只让 Caddy 暴露 80/443；应用监听容器内 0.0.0.0:3000，Caddy 使用 app:3000 代理。配置自动重启、日志大小限制和证书持久化卷。镜像及依赖锁定经核对的版本。应用运行账号与迁移账号分离，迁移凭证不注入长期运行的应用。构建时无需访问真实云数据库。提供实际可执行的建表、创建管理员、健康检查命令，不使用数据库重置命令。不要将真实密钥提交仓库或打入镜像。报告测试结果和仍需人工验证项。

Codex 交付后，应能看到：

| 文件/交付 | 内容 |
| --- | --- |
| 应用源码与依赖锁文件 | 网页、接口、后台 |
| Dockerfile | 生产构建和运行方式 |
| compose.yaml | app、caddy 服务；生产环境不含本地 MySQL |
| Caddyfile | 实际域名、HTTPS 与 app:3000 转发 |
| .env.example | 字段说明，无真实密码 |
| 数据库迁移 | 版本化创建与升级表结构 |
| 管理员初始化入口 | 交互输入密码，不使用线上默认密码 |
| README / DEPLOY | 精确部署命令和失败处理 |
| 测试报告 | 需求中的权限、事务、映射、缓存等软件验收 |

阶段通过条件：浏览器打开模拟 A/B 入口显示正确服装；后台能修改并留审计；公开响应无手机号；停用和下架有效。

## 6. 在 ECS 安装 Docker

只在确认没有需要保留的现有 Docker 安装或冲突服务后进行。使用官方 APT 源路径，以下针对 Ubuntu 22.04：

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

添加软件源（这是多行命令，需整块粘贴）：

```bash
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<'DOCKER_SOURCE'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: jammy
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
DOCKER_SOURCE
```

上面固定 amd64，仅在 `uname -m` 为 x86_64 时使用；如果是 ARM，需调整，不直接复制。

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker --version
sudo docker compose version
sudo docker run --rm hello-world
```

成功标志：Docker 与 Compose 输出版本，hello-world 输出成功提示。软件源或镜像下载失败时检查网络和错误，不执行未知的一键脚本。若发现旧 docker.io、containerd 等软件，先让 Codex判断冲突处理，不自动卸载。

本手册统一使用 sudo docker，不要求你改 Docker 用户组。应用、Caddy 镜像版本在交付时锁定；不把这里的工具安装步骤当作已完成部署。

## 7. 上传代码与填写配置

### 7.1 建立项目目录

在 ECS 终端：

```bash
mkdir -p ~/bumbum
cd ~/bumbum
pwd
```

记住 pwd 输出的完整路径；今后所有 Compose 命令都在该目录执行。

### 7.2 上传项目

首版可让 Codex交付无密钥的 ZIP 项目包，通过 Workbench 文件管理上传至该目录，再按交付说明解压。Workbench 是否显示文件管理取决于连接方式；如果没有，使用本机 SFTP / scp。压缩包应包含源码和锁文件，不包含 .env、node_modules、数据库数据目录或证书私钥。

另一方式是从 Git 仓库下载。私有仓库使用受限的认证方式；不要把访问令牌写进 `git clone` URL。根据自己实际可用的方式选择其一，不必同时使用。

成功标志：项目根目录中能看到 compose.yaml、Dockerfile、Caddyfile 和交付说明。若解压后多了一层文件夹，要先 cd 到实际根目录。

### 7.3 填写环境变量

以下假设项目按约定交付 .env.example；若文件名不同，遵循实际 README。

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

nano 未安装时可 `sudo apt install -y nano`。编辑保存：Ctrl+O，回车；退出：Ctrl+X。

| 配置 | 填写原则 |
| --- | --- |
| PUBLIC_BASE_URL | 完整 HTTPS 网站地址，例如 https://nfc.example.com，无 /t/ 后缀 |
| DATABASE_URL 或独立数据库字段 | MySQL 内网主机、实际端口、bumbum_mvp、bumbum_app 及密码 |
| SESSION_SECRET | 长随机字符串 |
| 数据库 CA / TLS 参数 | 按真实数据库与驱动配置 |
| 其他字段 | 严格依照 Codex交付的配置说明 |

生成会话密钥，可在 ECS 执行：

```bash
openssl rand -hex 32
```

把输出复制到受保护配置，不发到聊天。数据库 URL 中密码如果有 @、#、%、: 等字符，需要正确编码；Compose 的 $ 也有插值规则。让 Codex提供避免错误的配置方式与校验，不把原始密码发给它排错。不要自行把同一条 URL 的 TLS 查询参数套给所有驱动。

迁移凭证应使用单独的受保护配置，例如 .env.migrate，权限同样 600，只供一次性迁移和初始化。网站管理员密码通过初始化入口输入，不放在长期应用环境中。

成功标志：本地文件不再有占位符；真实 .env 已被 .gitignore 与 .dockerignore 排除。不要运行会完整打印密钥的配置/调试命令并把结果截图上传。

## 8. 构建、建表与启动

以下通用命令假设交付的 Compose 服务叫 app、caddy，实际服务名不同需按 README 调整。

### 8.1 构建

```bash
sudo docker compose build app
```

预期：无构建错误，生成应用镜像。构建阶段不应依赖真实云数据库。如果报内存不足，让 Codex评估构建优化或在匹配架构环境构建镜像；不要马上升级套餐或无依据清理数据。

### 8.2 执行迁移

这是“把数据库表建立起来”的步骤。具体命令取决于项目实际 ORM，必须使用交付 README 中的一次性迁移入口。

不要自行执行示例 `db push`、`migrate reset` 或未知 SQL。迁移使用 bumbum_migrate 账号；开始前核对目标库确实是 bumbum_mvp，后续升级前先备份。

让 Codex给出的命令需满足：失败即停止、不启动网站冒充成功、日志不输出密码、应用容器内能连接 RDS。一次性迁移账号不进入长期应用进程。

成功标志：迁移成功，可用迁移账号执行 SHOW TABLES 查看 garments、tags、admins、admin_sessions、audit_logs 等实际交付表。

### 8.3 创建网站管理员

执行交付的管理员初始化命令，交互输入用户名与强密码；可以使用 bumbum_migrate 完成必要初始化。不要通过手工写明文 password 字段来创建账号。

成功标志：命令提示创建成功。管理员账号用于 /admin/login，和数据库账号不同。

### 8.4 启动

在 DNS、Caddy 域名配置、迁移和管理员初始化均准备好后：

```bash
sudo docker compose up -d app caddy
sudo docker compose ps
sudo docker compose logs --tail=100 app
sudo docker compose logs --tail=100 caddy
```

预期：服务运行中；配置健康检查的服务应变为 healthy；Caddy 无持续证书申请失败；应用无持续数据库或迁移错误。日志需要在代码中脱敏，发给 Codex之前仍要检查是否含密码、手机号等。

Compose 应设置 restart: unless-stopped 等重启策略，Caddy /data 和 /config 保存到持久化卷，日志设置上限。关闭 Workbench 浏览器后，容器仍应运行。

## 9. HTTPS 配置与上线检查

推荐由 Caddy 在容器内管理 HTTPS，不额外同时安装 Nginx、宝塔或第二套证书工具。

Caddyfile 的基本结构示例：

```caddyfile
nfc.example.com {
    reverse_proxy app:3000
}
```

替换自己的域名；app 是同一个 Compose 网络内的服务名。不是 localhost:3000，因为 Caddy 容器里的 localhost 指它自己。具体交付文件可加必要限制与日志配置。

自动签发与续期的前提：域名指向 ECS、80/443 可达、没有错误 AAAA/CAA 或其他证书限制，服务器能访问证书机构。证书数据卷应保留，避免每次重建重复申请。发生错误时查看日志原因，不反复删除证书卷。

完成后在手机上用移动网络打开：

- https://你的子域名/health
- https://你的子域名/admin/login

成功标志：浏览器无证书警告；健康接口返回成功且不泄露配置；后台能登录。不要对证书警告选择“继续访问”作为通过。

在 ECS 上可用以下命令查看公开健康响应（替换域名）：

```bash
curl -i https://nfc.example.com/health
```

此后后台复制出来的标签入口应以正式 HTTPS 域名开头，不能含 localhost、私网 IP 或临时域名。

## 10. 软件验收：先别写芯片

1. 登录后台，创建服装 A、B，使用虚拟资料并发布。
2. 软件阶段可使用明确标记为模拟的 UID；硬件阶段必须换成真实回读 UID，按需求规则重新登记，不将模拟值标为真实标签。
3. 建两个测试标签，分别绑定 A、B；复制入口到浏览器，确认页面。
4. 改 A 名称，再次打开 A 入口，确认新资料出现。
5. 修改 A 所有者，确认后台留审计，公开页只显示登记状态。
6. 解绑 B，再将标签 A 改绑到 B，确认原 A 入口现在显示 B。
7. 测试停用、解绑、草稿、下架、未知入口。
8. 退出后台，直接访问管理页/接口应被拦截。
9. 重启应用后确认数据保留：

```bash
sudo docker compose restart app
```

10. 用手机移动网络再次访问，避免只在电脑或 Wi-Fi 上测试。

Codex 应验证 /t/ 使用 302 和 Cache-Control: no-store，公开 HTML/API 无手机号与 UID。健康检查成功不能代替完整业务验收。

完成软件测试后清楚区分虚拟记录和真实记录；后台无永久删除功能时可停用测试标签，不继续把它当真实资产。

## 11. 两个 NTAG424 DNA 的真实测试

### 11.1 先准备工具，不急着改卡

确认是带天线的完整 NFC 标签；记录供应商、工具版本与标签当前权限。iPhone 14 能读取符合要求的网址标签，但不意味着任意工具都能写当前 NTAG424 DNA。具体写入工具需确认支持该标签及其配置；不在未知密钥时试改密钥。

读写工具可能返回随机读卡 ID，要确认真实 7 字节 UID。记录 14 位十六进制值。不能把“浏览器打开的网址”当作浏览器读取到了真实 UID。

### 11.2 标签 A

1. 给实体标签贴 A 标记。
2. 回读真实 UID、现有 NDEF 与权限。
3. 后台按真实 UID 建标签，绑定已发布的服装 A。
4. 复制固定入口，先在 iPhone Safari 手动打开。
5. 确认正式域名和正确服装后，用兼容工具写入单个 HTTPS NDEF URI。
6. 回读并逐字核对 URL，避免写错入口或串卡。
7. 退出读写扫描状态，点亮解锁 iPhone，将手机顶部靠近标签。
8. 点击系统 NFC 通知，确认服装 A。
9. 后台标记“已人工核对写入”。

不锁死标签，不启用 SUN/SDM，不改 AES 密钥。URL 太长时检查实际 NDEF 编码容量，不直接截断随机入口码。

### 11.3 标签 B 与动态修改

A 成功后再做 B，相同流程绑定服装 B。

两个标签各做 10 次独立读取，记录 iOS 版本、网络、是否识别、是否点击通知、最终页面和耗时。然后不重写标签，依次修改资料、改所有者、改绑、停用，重新触碰核对结果。

目标：已打开网页必须显示正确服装；识别失败、网页加载失败分别记录。当前版 URL 可复制，不以这些测试宣布“防伪成功”。

## 12. 后续更新与回滚

首次上线后，不要随意换入口域名或 /t/ 路径，否则已写标签会受影响。

每次更新顺序：

1. 记录当前代码版本和镜像标识。
2. 创建数据库备份，确认备份可恢复。
3. 备份服务器受保护配置，备份不上传公共仓库。
4. 在隔离 MySQL 8.0 验证新迁移与代码。
5. 上传新版本、构建；使用交付迁移入口执行必要迁移。
6. 启动新版，验证健康接口、后台、两个真实入口。
7. 如失败，根据交付回滚说明恢复旧应用；表结构变更不能仅靠旧镜像自动回滚。

不要把整套线上数据库直接覆盖成旧备份，否则会丢掉备份后的所有者与绑定修改。恢复先在隔离数据库验证，再决定切换。

常用只读排查命令：

```bash
sudo docker compose ps
sudo docker compose logs --tail=100 app
sudo docker compose logs --tail=100 caddy
df -h
free -h
```

停止整个网站：`sudo docker compose stop`；恢复：`sudo docker compose up -d`。执行前确认当前目录与项目正确。

不要执行 `docker compose down -v` 或带卷清理的命令来日常排错，这可能删除证书等持久化数据。磁盘满时先查看日志与镜像占用，不直接清空 /var/lib/docker。

检查服务器试用/到期时间、数据库账单、域名到期日和公网流量。带宽峰值不是免费流量额度。

## 13. 常见错误对照

| 现象 | 含义或优先检查 | 下一步 |
| --- | --- | --- |
| Workbench 无法登录 | 用户名、密码/密钥、SSH、来源规则 | 按控制台连接诊断 |
| MySQL 连接超时 | 地址、VPC、白名单或网络 | 核对私网 IP 和内网主机 |
| Access denied | 登录凭证或主机授权 | 核对账号、密码与错误全文 |
| Unknown database | 数据库名不对或未建库 | 回数据库管理检查 |
| Table doesn't exist | 迁移未执行或连错库 | 核对目标库与迁移状态 |
| TLS 证书错误 | CA、主机名、驱动设置 | 核对真实证书，不关闭校验糊弄通过 |
| 域名找不到 | DNS 未生效或加在错误服务商 | 核对权威 DNS 与 A 记录 |
| 浏览器连接超时 | 80/443 未放行、服务未监听 | 安全组、容器状态、端口 |
| 502 | Caddy 能接收，但 app 不可达 | 检查 app:3000、应用日志和监听地址 |
| 证书申请失败 | DNS、端口、AAAA、CAA 或外连问题 | 查看 Caddy 具体错误 |
| command not found | 软件未安装或运行位置错误 | 核对是在 ECS 终端执行 |
| Docker permission denied | 普通用户权限不足 | 按手册使用 sudo |
| 芯片无通知 | NDEF、扫描状态、天线、位置 | 先回读 URL，再检查实体条件 |
| 修改后旧数据 | 未重新请求或错误缓存 | 刷新、检查 302/no-store |
| 系统重启网站未恢复 | 重启策略或 Docker 未自启 | 核对 systemctl 和 Compose 配置 |

给 Codex排错的格式：当前阶段、在哪个页面/终端、执行命令（去除密码）、预期结果、实际结果、脱敏错误及 requestId。只提供相关日志，不上传整份 .env。

## 14. 最终验收清单

- [ ] 数据库具体产品已确认；项目库与普通账号建立。
- [ ] ECS 内网可连接 RDS，应用容器也可连接。
- [ ] 80/443 已放行，管理端口仅允许需要的来源。
- [ ] MySQL 不对全公网开放。
- [ ] 源码、锁文件、迁移、初始化、部署和回滚说明齐全。
- [ ] 真实密码不在仓库、镜像、公开响应或调试日志里。
- [ ] HTTPS 正常；证书可续期且数据持久化。
- [ ] 管理后台可以录入服装、标签、绑定与所有者。
- [ ] 页面更新、改绑、停用、下架、异常场景正确。
- [ ] 公开页面不显示手机号，管理接口必须登录。
- [ ] 重启后网站与数据恢复正常。
- [ ] 两个真实 UID 与入口逐一核对，实际触碰通过。
- [ ] 备份策略与费用、试用到期提醒已检查。

## 15. 官方资料与核对日期

核对日期：2026-10-13。控制台名称可能调整，以实际产品界面为准。

1. RDS 内网连接条件与命令：https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/use-a-client-or-cli-to-connect-to-an-apsaradb-rds-for-mysql-instance
2. RDS 白名单：https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/configure-an-ip-address-whitelist-for-an-apsaradb-rds-for-mysql-instance
3. RDS 数据库与账号入门：https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/step-1-create-an-apsaradb-rds-for-mysql-instance-and-configure-databases/
4. RDS 账号权限：https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/create-an-account-on-an-apsaradb-rds-for-mysql-instance
5. Workbench：https://help.aliyun.com/zh/ecs/user-guide/workbench-overview
6. ECS 安全组：https://help.aliyun.com/zh/ecs/user-guide/start-using-security-groups
7. 网站 A 记录：https://help.aliyun.com/zh/dns/pubz-add-website-parsing
8. Docker Ubuntu 安装：https://docs.docker.com/engine/install/ubuntu/
9. Caddy HTTPS：https://caddyserver.com/docs/quick-starts/https
10. Caddy 容器运行：https://caddyserver.com/docs/running
11. MySQL TLS：https://dev.mysql.com/doc/refman/8.0/en/using-encrypted-connections.html
12. NXP 标签能力：见配套需求文档参考资料。

本文的命名、部署组织与验收顺序为本项目建议；尚未访问你的云资源、执行这些命令或实测芯片。迁移和初始化命令必须以实际代码交付为准。
