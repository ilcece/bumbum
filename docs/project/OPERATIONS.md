# 运维、备份恢复与排错手册

日期：2026-10-23；适用v1.2.1 SQLite。故障时先保留数据、旧镜像、密钥与安全日志，不执行reset或down -v。

## 1. 每次新终端先定义命令

```bash
dc() {
  sudo docker compose \
    --project-directory /root/bumbum-sqlite-package/bumbum-main \
    --env-file /root/bumbum-sqlite-package/bumbum-main/.env.sqlite \
    -f /root/bumbum-sqlite-package/bumbum-main/compose.sqlite.yaml \
    -f /root/bumbum-sqlite-package/bumbum-main/compose.nfc.yaml "$@"
}
```

它使用绝对路径，不依赖当前pwd。未定义时dc command not found，重新粘贴即可。

## 2. 日常只读检查

```bash
dc ps
dc exec app node -p "require('./package.json').version"
curl --fail --show-error https://nfc.bumbum.cc/health
dc run --rm tools check
dc logs --since=5m --tail=50 app
sudo docker system df
df -h
```

check成功应为status=ok、engine=SQLite、schema_migrations=2并显示9表计数。它检查完整性、外键和迁移checksum；不证明所有标签密钥匹配。/health也不等于实物验真通过。

不要发送.env、完整docker inspect环境变量、非quiet的展开配置、芯片密钥JSON、真实动态URL或手机敏感截图。安全错误日志可发送requestId、错误类型/代码及已过滤位置。

## 3. 原生CLI命令表

以下均为`dc run --rm tools <命令>`：

| 命令 | 用途/限制 |
|---|---|
| migrate | 应用未执行的增量迁移，检查历史checksum，不重置 |
| admin | 交互创建管理员，密码不回显，不能在非TTY直接使用 |
| check [file] | 检查当前库或指定备份 |
| backup new-file | 在线一致性备份，目标必须不存在 |
| restore source new-file | 恢复到新文件，不覆盖当前生产库 |
| nfc-prepare tag-uuid | 生成目标密钥和PENDING配置；不写卡，重复准备拒绝 |
| nfc-counter-export new-file | 用SESSION_SECRET签名的计数水位导出 |
| nfc-counter-merge signed-file | 验签及身份匹配后只提高计数，不自动启用标签 |

内部`/data`是SQLite数据卷，`/backups`是备份卷，不等于宿主机根目录。备份卷仍在同台机器，不能防整机/磁盘丢失。

## 4. 在线备份与维护窗口

可以在应用运行时在线备份：

```bash
dc run --rm tools backup /backups/online-snapshot.sqlite
dc run --rm tools check /backups/online-snapshot.sqlite
```

每次换唯一新名字。不能直接复制运行中的主.sqlite文件而忽略WAL，不能把备份等同于已保存全部最新计数。

**若要升级、恢复或保留最终防重放状态，先停应用，再导出最终水位和备份。** 以下为同一次维护窗口的例子，需替换为未使用的文件名：

```bash
dc stop app
dc run --rm tools nfc-counter-export /backups/maintenance-floors.json
dc run --rm tools backup /backups/maintenance.sqlite
dc run --rm tools check /backups/maintenance.sqlite
```

应用停止期间用户可能看到Caddy502，属于维护中断；不要声称此方案无停机。维护窗口内也不并行执行nfc-prepare、换钥或其他维护写入。停写后没有新验真时，这份水位才覆盖全部已接受读数。

仅定时导出不能保证灾难发生前最后几次计数不丢。导出后若恢复运行又有新验真，旧水位不再是最终水位。

## 5. 同时备份私密文件

数据库不含NFC钥值；需同时保存：

- `.env.sqlite`（SESSION_SECRET也用于水位文件验签）。
- `secrets/nfc-runtime`与`secrets/nfc-personalization`。
- 实际写卡状态/当前Key0的受保护备份；生成的目标Key0不一定已应用。
- Compose、Caddy配置、版本/镜像记录、证书恢复计划。

下面只在自己的可信ECS执行，创建私密归档，不打印内容。文件名已存在会拒绝重定向，不要覆盖：

```bash
sudo install -d -m 700 /root/bumbum-private-backups
sudo sh -c '
set -eu
umask 077
set -C
cd /root/bumbum-sqlite-package/bumbum-main
tar -czf - .env.sqlite compose.sqlite.yaml compose.nfc.yaml Caddyfile secrets > /root/bumbum-private-backups/private-settings-unique.tar.gz
'
```

这个归档只是权限受限，**tar.gz本身没有加密**。使用受控加密的离机存储，不进Git、镜像、公开网盘或聊天。不要把本项目未创建的“主密钥”误以为已经保存在其中。

## 6. 从命名卷导出备份到主机

用临时工具容器读取备份卷；它不是生产app。按下列一整组执行：

```bash
sudo install -d -m 700 /root/bumbum-private-backups
BUMBUM_COPY_CONTAINER="$(dc run -d --entrypoint sh tools -c 'sleep 300')"
sudo docker cp "$BUMBUM_COPY_CONTAINER:/backups/maintenance.sqlite" /root/bumbum-private-backups/maintenance.sqlite
sudo docker cp "$BUMBUM_COPY_CONTAINER:/backups/maintenance-floors.json" /root/bumbum-private-backups/maintenance-floors.json
sudo docker rm -f "$BUMBUM_COPY_CONTAINER"
sudo chmod 600 /root/bumbum-private-backups/maintenance.sqlite /root/bumbum-private-backups/maintenance-floors.json
```

确认主机目标不存在或使用新名字，docker cp不会替你保留历史版本。再通过SFTP等可信传输离机；不要只保存在这台ECS。

证书卷`bumbum_caddy_data`和`bumbum_caddy_config`也需要运维保管，不能执行down -v删除。证书重新签发和额度/网络条件应纳入恢复演练，不能保证删卷后立即恢复TLS。

## 7. 恢复到新文件，不回退验真计数

### 7.1 恢复已在/backups的v1.2.x备份

保持app停止，先核实备份版本、密钥、SESSION_SECRET和最终水位配套：

```bash
dc stop app
dc run --rm tools check /backups/maintenance.sqlite
dc run --rm tools restore /backups/maintenance.sqlite /data/restored-maintenance.sqlite
dc run --rm tools check /data/restored-maintenance.sqlite
```

编辑原.env.sqlite，仅把SQLITE_FILE切到新文件：

```bash
nano /root/bumbum-sqlite-package/bumbum-main/.env.sqlite
```

```dotenv
SQLITE_FILE=/data/restored-maintenance.sqlite
```

然后对当前指向的新库合并最终可信水位、检查、启动：

```bash
dc run --rm tools nfc-counter-merge /backups/maintenance-floors.json
dc run --rm tools check
dc up -d --force-recreate --wait app
curl --fail --show-error https://nfc.bumbum.cc/health
```

merge校验HMAC、域名、UID和密钥指纹及记录匹配；只增加计数。恢复副本如果缺少水位文件里的NFC记录，会整体失败，不删水位条目绕过。旧数据库文件保留。

如果恢复运行后已有新验真，不可再随意切回旧文件。若拿不到覆盖全部已接受读数的最终可信水位，暂停动态验真，不能宣称完整恢复防重放；不要手动把last_counter清零。

### 7.2 离机备份重新导入/backups

示例将主机上的文件以新名字写进备份卷，不覆盖已有文件：

```bash
dc run --rm -T --entrypoint node tools --input-type=module -e 'import {createWriteStream} from "node:fs";import {pipeline} from "node:stream/promises";await pipeline(process.stdin,createWriteStream("/backups/imported.sqlite",{flags:"wx",mode:0o600}));' < /root/bumbum-private-backups/maintenance.sqlite
```

签名水位也可按相同方式导入独立文件名：

```bash
dc run --rm -T --entrypoint node tools --input-type=module -e 'import {createWriteStream} from "node:fs";import {pipeline} from "node:stream/promises";await pipeline(process.stdin,createWriteStream("/backups/imported-floors.json",{flags:"wx",mode:0o600}));' < /root/bumbum-private-backups/maintenance-floors.json
```

之后用imported名称执行检查/恢复/合并。只有可信备份才能导入。

### 7.3 只有001迁移的1.1.0旧备份

1.2.x工具的检查要求新增NFC表，直接restore旧备份会失败。使用保留的旧镜像工具先复制到新文件：

```bash
cd /root/bumbum-sqlite-package/bumbum-main
sudo env APP_IMAGE=bumbum:1.1.0-sqlite docker compose --env-file .env.sqlite -f compose.sqlite.yaml -f compose.nfc.yaml run --rm tools restore /backups/before-sdm.sqlite /data/restored-legacy.sqlite
```

仅此命令临时选择旧镜像，不改.env.sqlite的APP_IMAGE，也不启动旧app。保持app停止，把SQLITE_FILE切到该副本，回到1.2.x工具执行migrate/check。

注意：1.1.0快照没有后来创建的NFC配置。若最终水位包含这些记录，merge会拒绝，必须找包含配套NFC记录的较新备份或制定专门恢复方案，不能把“表建出来了”当成历史NFC状态恢复。

## 8. 镜像回滚

1.2.1→1.2.0属于同结构补丁回滚：把APP_IMAGE改为保留的旧标签，用相同两个Compose文件`dc up -d --no-deps --wait app`。**继续使用当前库和计数，不还原旧数据库。**

旧1.2.0不支持picc_data/cmac，所以回滚会失去当前nfc.cool网址兼容性。已写动态标签后回到1.1.0更会停止/v验真；它只能保留旧档案业务，不是完整功能回滚。应优先使用兼容的修复镜像。

不覆写旧镜像标签，不执行image prune -a或volume prune作为常规清理。磁盘不足先查看占用，必要时只清可重建构建缓存；不删卷、密钥或唯一备份。

## 9. 故障速查

| 现象 | 已知原因/下一步 |
|---|---|
| docker: unknown command compose | 缺Compose插件；核对安装来源和版本 |
| no configuration file / 找不到.env.sqlite | 当前目录错误，使用本文绝对路径dc |
| No such image | 构建失败或APP_IMAGE改了但未构建；不要接着迁移/启动 |
| FileNotFoundError secrets/... | 主机相对路径用了/root，改完整项目路径；不要重新生成密钥 |
| nfc-prepare统一失败 | 先查标签UUID是否存在，再查目录1000/700、HTTPS origin、迁移和已有文件 |
| 标签记录[] | 把服装ID/错误UUID当成标签ID；按真实UID查询正确tag.id |
| 文件已存在 | 可能已准备过或有中断残留；保留文件，核对，不删除重试 |
| NFC_INVALID 参数无效 | 旧1.2.0不接受picc_data/cmac，或名称混搭/长度/额外参数错误 |
| 无法验证此标签 | 参数已进入校验；查Key1/2实际值和用途、UID、MAC输入范围；不跳过校验 |
| NFC_REPLAY / 409 | 已使用或过期计数，工具预览可能先访问；移开重新触碰 |
| TAG_UNBOUND / 409 | 在后台绑定到对应已发布服装 |
| TAG_DISABLED / 410 | 核实是否管理员停用；按业务授权重新启用 |
| 404 | 未知入口或服装草稿/下架等；不当作数据库损坏 |
| NFC_KEYS_UNAVAILABLE / 503 | runtime挂载、UUID文件名、600权限、身份和指纹不符；不把钥值发出来 |
| 健康正常但验真失败 | health不验证每枚芯片，与密钥/发布/绑定状态分别检查 |
| UNAUTHORIZED / 401 | 未登录/会话失效的正常响应；与POST登录500不是一件事 |
| POST登录500 | 取安全日志requestId诊断；历史DuckDB环境不应套当前SQLite修复 |
| 502/TLS失败 | app健康、Caddy端口/DNS/证书卷/ACME网络；不开放3000绕过 |

## 10. 安全查询标签ID

只读、无密钥，适用于找错UUID：

```bash
dc run --rm -T --entrypoint node tools --input-type=module <<'JS'
import {db,rows} from './dist/db.js';
try { console.table(await rows('SELECT id,uid,notes FROM tags ORDER BY created_at')); }
finally { await db.end(); }
JS
```

管理员完整手机号仅必要时在受保护后台查看，不通过日志排错导出全部业务数据。用户原始云库高权限GRANT历史不在SQLite环境继续执行。
