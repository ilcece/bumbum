# 香港 ECS 部署与升级手册

日期：2026-10-23；目标软件v1.2.1。先确定是已有部署还是全新安装，不要混用。本文不执行任何服务器操作。

**取源前提：2026-10-23核对时GitHub main仅有初始README。下面命令要求使用保留的v1.2.1完整源码ZIP（本次另附bumbum-source-v1.2.1.zip），不能使用当前main的下载包。源码包不是.env/数据库/芯片密钥备份。**

## 1. 当前已确认位置与前提

| 项目 | 当前记录 |
|---|---|
| 新ECS | 香港，Ubuntu22.04 LTS 64位；与最早的旧ECS不是同一实例 |
| 建议资源 | 单机验证建议2核4GB、足够磁盘；新实例实际CPU/内存/磁盘仍应从控制台核实 |
| 项目目录 | `/root/bumbum-sqlite-package/bumbum-main`，由Compose容器标签确认 |
| 生产配置 | 该目录的`.env.sqlite` |
| 入口域名 | `nfc.bumbum.cc`；后台暂同域名`/admin/login` |
| 镜像 | 目标`bumbum:1.2.1-sdm`，不要覆盖旧版本标签 |
| Compose文件 | compose.sqlite.yaml + compose.nfc.yaml |

`/root`是SSH默认目录，不是项目目录；提示符为`:~#`时尤其要检查。`/run/nfc-keys`和`/provision`是容器路径，不直接当主机路径使用。

只读定位：

```bash
pwd
find /root /home /opt -maxdepth 6 -type f -name '.env.sqlite' -print 2>/dev/null
sudo docker ps -aq --filter label=com.docker.compose.service=app |
  xargs -r sudo docker inspect --format '{{.Name}} 项目目录={{index .Config.Labels "com.docker.compose.project.working_dir"}}'
```

只发送路径和错误，不发送配置内容。

## 2. 推荐统一命令入口

为避免在错误目录执行，每次新SSH终端先粘贴这个函数。它只定义快捷命令，不立即改服务器：

```bash
dc() {
  sudo docker compose \
    --project-directory /root/bumbum-sqlite-package/bumbum-main \
    --env-file /root/bumbum-sqlite-package/bumbum-main/.env.sqlite \
    -f /root/bumbum-sqlite-package/bumbum-main/compose.sqlite.yaml \
    -f /root/bumbum-sqlite-package/bumbum-main/compose.nfc.yaml "$@"
}
```

`dc`不是仓库附带程序，新终端需重新定义。尚未复制新源码、没有compose.nfc.yaml的1.1.0旧环境，先使用第6节的旧版备份命令。

```bash
dc config --quiet
dc ps
```

config成功时没有输出，返回提示符即正常。不要把不带`--quiet`的完整配置发到聊天，它可能展开秘密环境变量。

## 3. 基础网络和运行环境

在ECS检查：

```bash
uname -m
lsb_release -ds
sudo docker --version
sudo docker compose version
df -h
free -h
```

目标amd64/x86_64，Docker可用，Compose至少2.30以支持raw env_file；不能拿`docker-compose`旧命令替代当前语法。缺少插件时按[Docker Ubuntu官方安装说明](https://docs.docker.com/engine/install/ubuntu/)核对现有软件来源后安装，不把“Docker存在”当成“Compose存在”。本资料不替代对具体apt包版本的现场核查。

网络检查：

- 域名A记录指向**新ECS公网IP**。清理错误AAAA记录；HTTPS异常时检查CAA、DNS生效与系统时间。
- 安全组/主机防火墙允许TCP80、443；22只按可信管理来源或Workbench当前提示放行。
- 不开放3000、3306。仅Caddy发布80/443，主机其他服务不要占用端口。
- 正式证书需要DNS正确和ACME出网可达；保留证书卷。不要用curl -k跳过验证。
- 当前SQLite不需要RDS、同VPC、数据库白名单、MySQL账号或数据库PEM CA。

## 4. 全新安装（没有旧配置、旧数据库时才执行）

取得保留的完整v1.2.1源码ZIP，上传成`/root/bumbum-main.zip`。确认解压包内package.json版本1.2.1，且有src、migrations和compose.sqlite.yaml。

```bash
mkdir -p /root/bumbum-sqlite-package
unzip /root/bumbum-main.zip -d /root/bumbum-sqlite-package
cd /root/bumbum-sqlite-package/bumbum-main
ls -l compose.sqlite.yaml compose.nfc.yaml
python3 scripts/configure-sqlite.py
```

输入域名（不含https://或路径）和证书通知邮箱。生成器创建600权限的`.env.sqlite`，随机SESSION_SECRET，拒绝覆盖已有文件。

主要字段：APP_IMAGE镜像标签；SITE_DOMAIN域名；ACME_EMAIL邮箱；PUBLIC_BASE_URL正式HTTPS origin；SESSION_SECRET会话及水位签名秘密；DATABASE_ENGINE=sqlite；SQLITE_FILE默认为/data/bumbum.sqlite。不要把会话秘密当成NFC钥或主密钥。

随后定义第2节dc，再执行：

```bash
sudo install -d -m 700 -o 1000 -g 1000 /root/bumbum-sqlite-package/bumbum-main/secrets/nfc-runtime /root/bumbum-sqlite-package/bumbum-main/secrets/nfc-personalization
dc config --quiet
dc build app
sudo docker image inspect bumbum:1.2.1-sdm --format '{{.Id}}'
dc run --rm permissions
dc run --rm tools migrate
dc run --rm tools check
```

镜像ID应以sha256开头；迁移成功显示SQLite migrations complete；check应status=ok、schema_migrations=2、共9张表计数。新业务计数为0正常。permissions初始化命名卷目录的UID1000权限，不会重置数据库。

创建管理员需要交互终端，不加-T：

```bash
dc run --rm tools admin
```

填写账号、12–128位密码两次，不回显正常，无默认密码。没有成功创建管理员时不能直接靠登录页完成初始化。

```bash
dc up -d --wait app caddy
curl --fail --show-error https://nfc.bumbum.cc/health
dc exec app node -p "require('./package.json').version"
```

替换为你实际域名。预期health=ok、版本1.2.1，浏览器打开`https://nfc.bumbum.cc/admin/login`。后续按[NFC手册](NFC-OPERATIONS.md)处理标签。

## 5. 从1.2.0升级到1.2.1（本项目优先走此路径）

本补丁只新增参数别名，无新数据库迁移。已有密钥、标签与计数必须保留。

1. 按[运维手册](OPERATIONS.md)备份并保存旧镜像；操作前记录当前版本。
2. 取得保留的干净v1.2.1源码ZIP，上传为`/root/bumbum-1.2.1.zip`；不要使用仅有README的当前main。
3. 更新代码到**原部署目录**，不能在/root误执行复制。

```bash
mkdir -p /root/bumbum-update-1.2.1
unzip /root/bumbum-1.2.1.zip -d /root/bumbum-update-1.2.1
ls /root/bumbum-update-1.2.1/bumbum-main/compose.nfc.yaml
cd /root/bumbum-sqlite-package/bumbum-main
pwd
sudo cp -p .env.sqlite .env.sqlite.before-1.2.1
cp -a /root/bumbum-update-1.2.1/bumbum-main/. /root/bumbum-sqlite-package/bumbum-main/
```

如果目标备份名已存在，换一个新名字，不覆盖历史备份。解压目录已存在时不要盲目覆盖提示，确认其中是本次源码。上述复制只适用于干净源码包；它不应包含实际.env.sqlite、secrets、数据卷或数据库。实际包目录不同则使用实际路径。

编辑**原配置**，只改APP_IMAGE：

```bash
nano /root/bumbum-sqlite-package/bumbum-main/.env.sqlite
```

```dotenv
APP_IMAGE=bumbum:1.2.1-sdm
```

保存Ctrl+O、回车，退出Ctrl+X。其余内容保持。重新定义第2节dc后执行：

```bash
dc config --quiet
dc build app
sudo docker image inspect bumbum:1.2.1-sdm --format '{{.Id}}'
```

只有构建成功后再替换应用：

```bash
dc up -d --no-deps --wait app
dc exec app node -p "require('./package.json').version"
curl --fail --show-error https://nfc.bumbum.cc/health
```

仅改镜像标签不构建，会报No such image。仅重新启动旧容器不重建，也可能仍跑旧镜像。此补丁Caddy配置不变，无需重启Caddy；app替换可能短暂不可用，不承诺零停机。

不要重新运行nfc-prepare，不要换芯片Key1/2，不要恢复旧数据库，不要回退计数。确认版本后用新触碰网址验收picc_data/cmac。

## 6. 从1.1.0升级（旧库只有001迁移时）

先在原目录确认旧镜像标签。以下以保留的bumbum:1.1.0-sqlite为例，其他旧标签先核实，不照抄覆盖。

```bash
cd /root/bumbum-sqlite-package/bumbum-main
sudo docker compose --env-file .env.sqlite -f compose.sqlite.yaml stop app
sudo cp -p .env.sqlite .env.sqlite.before-sdm
sudo cp -p Caddyfile Caddyfile.before-sdm
sudo env APP_IMAGE=bumbum:1.1.0-sqlite docker compose --env-file .env.sqlite -f compose.sqlite.yaml run --rm tools backup /backups/before-sdm.sqlite
sudo env APP_IMAGE=bumbum:1.1.0-sqlite docker compose --env-file .env.sqlite -f compose.sqlite.yaml run --rm tools check /backups/before-sdm.sqlite
```

备份输出成功后，按第5节更新干净源码、改APP_IMAGE为1.2.1、创建私密目录、构建；然后定义dc并执行：

```bash
dc run --rm tools migrate
dc run --rm tools check
dc up -d --wait app caddy
```

应新增002迁移、schema_migrations=2，保留原记录。新版Caddyfile包含错误日志请求信息过滤，需让Caddy载入新文件。旧管理员不必重新创建。旧标签不会自动变成SDM标签，仍需单独准备与实物初始化。

## 7. 部署验收与下一步

- [ ] config --quiet正常，运行镜像确为1.2.1。
- [ ] check正常、两次迁移完成，业务数据符合预期。
- [ ] 手机移动网络访问HTTPS与后台成功。
- [ ] app主机无3000端口发布，只有Caddy80/443。
- [ ] 密钥仅runtime只读挂载给app，personalization不挂载给app。
- [ ] 第一枚实物新读取进入服务器PENDING/ACTIVE正确状态。
- [ ] 重放、停用、重启、离机备份和恢复演练完成。

健康检查只证明基础表可读，不代表全部标签密钥或现场验真都成功。上线后的安全日志与排错见[运维手册](OPERATIONS.md)。
