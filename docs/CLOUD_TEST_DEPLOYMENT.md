# 香港云测试：手机扫描，电脑查询

目标：手机用NFC.cool扫描后，打开`https://test.bumbum.cc/`登录，点击“查询”看到真实芯片编号。本手册只管香港测试环境；本机仍按[本地运行](LOCAL_DEVELOPMENT.md)，不会同步两边的账号和数据。正式管理域名仍为admin.bumbum.cc。

main提供已验收的扫描登记、来源字段及部署文件，cece已配置香港HTTPS网页并可打开，云端管理员已登录，cece已通过“批量写固定文本→批量读卡自动登记”验收，6枚卡后台可查且全部重扫无重复；来源升级和监听清理也已验收并合入main。适用已确认的香港Ubuntu 22.04、2核4GiB；使用独立MySQL，不连接生产RDS。本轮已由cece确认并完成测试卡固定文本预写；后续新卡的预写和正式SUN配置分开，不擅自覆盖已有卡内容或密钥。

## 1. 操作位置与准备

除了明确标为“电脑”或“手机”的步骤，以下命令都在**香港ECS终端**执行。每段逐条运行，报错就停在该步，不继续下一段；记录步骤及错误，不发送密码、验证码、二维码、配置文件或完整备份。

准备香港ECS公网IPv4、管理电脑当前公网出口IP、域名解析权限，以及可登录的GitHub仓库。电脑在浏览器查询“我的公网IPv4”，记录当前网络的出口地址；不要填192.168开头的内网地址，也不要填ECS地址。手机来源IP可以变化，不加入后台白名单。

从阿里云控制台进入香港实例终端。提示符已经是root时直接做下面的检查；否则先单独执行这一条，进入新终端后再继续：

```bash
sudo -i
```

逐条执行只读检查：

```bash
cat /etc/os-release
free -h
df -h /
ss -lntp
command -v docker
command -v nginx
```

最后两项在未安装时可以无输出；它们本身不修改服务。确认系统为Ubuntu 22.04，磁盘有足够空间下载镜像、保存数据库和备份。若已有Docker/Nginx、80/443或15000/33307被占用，把检查结果交给AI核对，先保留现有服务，不照后续命令重复安装、覆盖站点或清空数据。SSH不是必须，控制台终端也能完成后续步骤。

## 2. 域名与安全组：在阿里云控制台操作

在实际托管bumbum.cc解析的平台新增：

| 项目 | 填写内容 |
|---|---|
| 类型 | A |
| 主机记录 | test |
| 记录值 | 香港ECS公网IPv4 |
| TTL | 保持平台默认值 |

只处理test记录，不改根域名、admin或nfc。已有test记录时先核对，不能盲目追加多个不同IP；若test存在AAAA（IPv6）记录，也要核对是否指向同一台已配置服务器。先用普通DNS解析，不接入额外CDN代理。

ECS安全组入方向允许TCP 80、443来自公网；使用SSH时，22仅允许你的管理出口IP。不要开放5000、5174、15000、3306或33307。若服务器另有防火墙，也只补齐同样必要的规则，不一键关闭防火墙。80用于证书验证及跳转，业务用443。共享443端口不能用安全组单独限制后台，后台IP限制由第6节Nginx完成。

在**电脑PowerShell**检查，正常应看到香港ECS地址；DNS生效时间不固定：

```powershell
Resolve-DnsName test.bumbum.cc -Type A
```

## 3. 安装工具并获取版本：回到ECS终端

仅在第1节确认可作为新测试环境使用、网站端口已释放后执行。已有Docker和可用的`docker compose version`时，保留原安装，只补其他工具：

```bash
apt-get update
apt-get install -y git nginx certbot
```

仅未安装Docker/Compose的新服务器，再执行下面这一条；已有安装不要重复安装另一套：

```bash
apt-get install -y docker.io docker-compose-v2
```

检查并启动：

```bash
docker --version
docker compose version
systemctl enable --now docker nginx
```

应显示Docker和Compose v2版本；找不到docker-compose-v2等包时，停下让AI核对软件源，不改用旧版docker-compose命令。服务需要Docker支持构建时临时提供证书文件（BuildKit），后续构建失败时按第10节排查。

```bash
git -c credential.helper= clone --branch main https://github.com/ilcece/bumbum.git /opt/bumbum-test
cd /opt/bumbum-test
git branch --show-current
git log -1 --oneline
```

应为交付的分支与提交。目录已存在时不要删除或重复克隆，先检查当前版本。GitHub若提示Username/Password，用户名填ilcece，Password填访问令牌，不能填GitHub登录密码。在[令牌设置](https://github.com/settings/personal-access-tokens/new)创建仅限bumbum仓库、Contents只读的细粒度令牌，测试先设7天有效期；令牌只粘贴到自己的隐藏密码提示，不拼进网址或发聊天。命令关闭凭证保存功能，更新时按同样方式认证。以后固定使用这个目录，无需复制Windows的.venv或.env。

## 4. 生成独立配置，启动后端和测试库

以下命令中的`YOUR_PC_PUBLIC_IP`必须替换为**电脑当前公网出口IP**；账号名cece可以换成本次要创建的测试账号：

```bash
cd /opt/bumbum-test
python3 scripts/setup_cloud_test.py --admin-ip YOUR_PC_PUBLIC_IP --admin-name cece
bash scripts/cloud_test.sh start
bash scripts/cloud_test.sh status
curl --fail http://127.0.0.1:15000/api/ready
```

准备脚本生成不上传的.env.cloud-test和.cloud-test/nginx-https.conf；已有密码与密钥保留，只更新生成文件中的管理IP，不自动改服务器Nginx。启动先将正常系统CA证书包暂存到项目内的.cloud-test/build-ca.crt，兼容新版Compose/Bake的目录读取限制；证书仅在安装依赖时临时挂载，保留HTTPS校验，不进入镜像或Git。之后下载固定Python 3.12.14、Node 24.19.0、MySQL 8.0.46镜像，构建网页及Gunicorn 26.2.0后端；首次需要等待网络下载。数据库使用单独数据卷，映射到本机33307，后端只监听本机15000。正常status的两项为运行且healthy，ready返回status=ok、database=ready。

APP_ENV=production表示云端启用严格的HTTPS认证规则；本环境仍连接独立测试库。ADMIN_ORIGIN为https://test.bumbum.cc，正式环境另用https://admin.bumbum.cc。本次不生成芯片密钥，不运行本机旧库迁移，不自动导入本机记录。

镜像关闭当前不使用的Gunicorn控制socket，保留容器主目录只读。它与网页/API的HTTP监听不同，关闭不影响扫码、登录或Compose管理；不需要创建可写的/home/bumbum。

## 5. 首次配置域名证书

先确认DNS已正确解析、80可访问。首次安装仅处理本项目站点；若下列目标文件或同名站点已经存在，先核对来源，不覆盖其他人的配置。先提供证书验证入口：

```bash
cd /opt/bumbum-test
install -d -m 0755 /var/lib/letsencrypt
install -m 0644 deploy/cloud_test/nginx-http.conf /etc/nginx/sites-available/bumbum-cloud-test
ln -s /etc/nginx/sites-available/bumbum-cloud-test /etc/nginx/sites-enabled/bumbum-cloud-test
nginx -t
systemctl reload nginx
certbot certonly --webroot -w /var/lib/letsencrypt -d test.bumbum.cc
```

nginx -t应显示配置检查成功；检查失败不执行reload或签发。certbot按提示填写接收续期通知的邮箱并确认服务条款；证书应覆盖test.bumbum.cc。此时尚未安装HTTPS站点，暂时不能打开管理网页，属于正常过程。证书失败先检查域名、安全组和服务器80端口，不关闭证书验证。

## 6. 安装测试网页和HTTPS入口

```bash
cd /opt/bumbum-test
bash scripts/cloud_test.sh publish-page
install -m 0644 deploy/cloud_test/nginx-proxy.conf /etc/nginx/bumbum-cloud-test-proxy.conf
install -m 0644 .cloud-test/nginx-https.conf /etc/nginx/sites-available/bumbum-cloud-test
nginx -t
systemctl reload nginx
install -m 0755 deploy/cloud_test/reload-nginx.sh /etc/letsencrypt/renewal-hooks/deploy/bumbum-cloud-test
systemctl enable --now certbot.timer
certbot renew --dry-run
```

配置检查成功才reload；证书演练应成功，续期后会自动检查并重载Nginx。**电脑浏览器**打开https://test.bumbum.cc/，应无证书警告，并看到后端及数据库两项检查通过。

网页和管理接口只允许电脑出口IP；手机只需访问准确的/api/webhook/admin/scan路径，仍须扫码密码。陌生IP不能登录或查询，未知网站名称不能借此访问本项目；不公开其他API。扫描和登录均有简单的按来源限频，不使用Redis。Nginx访问日志不记录网址参数、认证头或请求体。

## 7. 创建云端管理员并设置手机验证器

在ECS第一个终端执行，进入配置二维码后保持终端等待：

```bash
cd /opt/bumbum-test
bash scripts/cloud_test.sh admin create cece
```

按提示设置至少12位密码。云端账号与本机独立，即使同名也要单独设置。终端显示的/tmp/bumbum-authenticator-…/authenticator.html位于**容器里**，不能直接在电脑地址栏打开。

另开一个ECS管理员终端，将下面`TEMP_QR_PATH`替换为第一个终端显示的完整路径：

```bash
cd /opt/bumbum-test
bash scripts/cloud_test.sh export-qr TEMP_QR_PATH
```

看到“二维码已安全导出”后，才下载/opt/bumbum-test/.cloud-test/authenticator.html，文件仅管理员可读。导出通过容器内读取，兼容/tmp内存盘；内容直接写文件，不显示在终端，不覆盖已有导出。失败时不会留下可供误下载的不完整文件。

使用阿里云远程连接提供的安全文件下载功能；若当前连接工具没有此功能，改用已有的SSH/SFTP连接下载这一个文件，或让AI协助，不要把它放到网站目录。下载到自己的电脑后双击打开，用Authenticator扫码，再回第一个终端输入当前验证码；看到“账号已创建”才算成功。只用于修复导出脚本的更新，拉取后直接重新执行export-qr，保持原终端等待，无需重启后端或执行start。

完成或取消后关闭页面、删除电脑下载副本；ECS终端删除本次导出副本：

```bash
rm -- /opt/bumbum-test/.cloud-test/authenticator.html
```

容器内临时文件由原命令退出时自动清理。中断后重新创建会生成新二维码；旧下载文件不再使用。不要分享二维码或手动添加密钥。等手机验证码切换下一组，再在电脑云测试网页使用账号、密码和验证码登录。

## 8. 设置NFC.cool并验证真实扫描

在私密ECS终端用nano打开配置，仅本人查看WEBHOOK_ADMIN_USERNAME和WEBHOOK_SHARED_SECRET，填写到手机；不要截屏、发聊天或粘贴整个配置。修改了其他内容时不要保存：

```bash
cd /opt/bumbum-test
nano .env.cloud-test
```

| 手机设置 | 填什么 |
|---|---|
| Webhook开关 | 开启 |
| Webhook URL | https://test.bumbum.cc/api/webhook/admin/scan |
| HTTP基本认证 | 开启 |
| 用户名 | WEBHOOK_ADMIN_USERNAME对应的云端管理员名 |
| 密码 | WEBHOOK_SHARED_SECRET独立扫码密码；不是网页登录密码，也不是6位验证码 |
| NFC触发 | 开启 |
| QR码触发 | 关闭 |

官方说明该能力需要Platinum订阅；能看到设置不代表实际发送已可用，先在自己手机核对。已知用户提供版本7.30，iOS 27.0.1；该手机的真实回调、批量读卡、后台查询及重复扫描已由cece验收，不代表其他版本或设备已测。App只保存一个回调网址；测试期间使用这里的地址，不与其他接收系统混用。

1. 按cece已确认的本轮流程，目标卡先在NFC.cool批量写入固定文本，再读取真实7字节UID；本轮使用cece。此步骤只准备登记触发内容，不包含密钥、SUN或正式写卡配置；已配置的卡不要覆盖。随机UID、兼容模式占位文字、二维码UUID不作为真实UID登记。
2. 在NFC.cool使用批量读卡，逐一连续碰卡；cece于2026-10-25实测读取成功后App自动保存并触发Webhook，无需逐张点“保存NFC标签”。单次读取入口此前需要手动保存，不将这个操作推广到批量入口。最新实测6枚写有cece文本的卡均401后200；完全空白卡无回调，已按cece决定采用预写流程。此前“完全空白卡也已触发”的判断撤回。电脑在云测试后台点“查询”或按UID搜索，成功后应显示一条“未分配、待绑定”。不要查看localhost的列表。
3. 再扫描同一卡，应仍只有一条，原项目、批次和状态不变；已有手动登记资料同样保留。cece已确认6枚卡后台可查、全部重扫没有新增，完成本小步验收；截图中为未分配、待绑定。手机不提交项目或批次。
4. 临时将手机扫码密码改错，应请求失败且不新增；然后恢复正确密码。管理员停用后也不再允许扫码登记。
5. 网络失败时查看App的请求结果或失败记录，恢复网络后人工重扫。手机读卡成功不等于后台保存成功；电脑查到记录才确认入库。App是否能清楚展示失败结果需记录实测，不假定会显示后台中文提示。
6. 正常网络下记录从扫描到后台可查询所需时间，目标2秒内；本轮未提供独立计时，不把功能验收写成性能指标已测达标。通过后按第9节停止再启动，确认账号和记录保留。

首次请求可能先收到401认证挑战，App再带已保存的凭证重发，最终成功才算通过；持续401才是凭证或账号问题。失败没有自动离线队列，不能以为稍后会自行补入库。登记不代表防伪验证通过。

### 日常排查：先看请求有没有到达

临时正文/结构监听和认证匹配诊断已删除。日常查看访问状态即可：

```bash
tail -n 0 -f /var/log/nginx/bumbum-cloud-test-access.log
```

按Ctrl+C仅结束查看，不停止服务。先401再200是正常认证挑战；持续401核对独立扫码凭证与账号状态；400看App可见的参数错误，尤其7字节真实UID；没有访问记录先核对App的入口、NFC触发及批量读卡，不反复改后端密码。发生异常时用第9节logs查看必要错误，不在日常日志记录请求体或认证头。历史捕获内容仍可能留在旧Docker日志中，本次不自动清除。

## 9. 日常停止、更新、备份

以下命令在ECS的/opt/bumbum-test执行；关掉远程终端不会停止服务。

| 目的 | 命令与结果 |
|---|---|
| 查看状态 | `bash scripts/cloud_test.sh status`，后端和数据库应healthy |
| 停止测试服务 | `bash scripts/cloud_test.sh stop`，账号和数据卷保留；Nginx与其他项目不停止 |
| 重新启动 | `bash scripts/cloud_test.sh start`，等待检查通过 |
| 更新前完整备份 | `bash scripts/cloud_test.sh backup`，生成.cloud-test/backups中的受限SQL文件；备份后还需私密保存.env.cloud-test，恢复加密账号资料需要原密钥 |
| 查看后端错误 | `bash scripts/cloud_test.sh logs`，分享前检查并隐去个人信息 |

备份包含账号资料，仅本人或授权维护人员访问，不上传Git。不要使用docker compose down -v、删卷或删配置“重新来过”。本机迁移的恢复检查不能代替香港环境的恢复演练；ECS首次恢复需先在另一个空测试库验证，不直接覆盖当前库。

更新时先确认工作区没有自己的未提交修改，备份成功后再执行：

```bash
cd /opt/bumbum-test
bash scripts/cloud_test.sh backup
git status --short
git fetch origin
git switch main
git -c credential.helper= pull --ff-only origin main
bash scripts/cloud_test.sh start
bash scripts/cloud_test.sh publish-page
git log -1 --oneline
```

应为交付的新提交，原账号和芯片仍在；Nginx、证书或表结构若有变化，以该次交付的专门步骤为准，不自动改表。当前脚本保留已有秘密，不自动恢复备份覆盖数据库。日常统一使用main；从旧功能分支切换时先看第9.2节。

首次构建在创建服务前就失败时，备份命令暂不可用；直接拉取交付的修复再执行start即可。已有.env.cloud-test保留，不重复生成密码或重建目录；数据库启动后再使用备份入口。

### 9.1 已有云测试库升级：登记来源

目的：保留账号与芯片，增加列表“登记来源”。此项收尾已验收并合入main；未升级的旧库不能只运行start，已升级的不重复操作。新建空库已包含此列，无需另行升级。

在ECS的/opt/bumbum-test执行；任何一步失败立即停下，保留报错，不继续执行后面的命令：

```bash
cd /opt/bumbum-test
git fetch origin
git switch main
git -c credential.helper= pull --ff-only origin main
bash scripts/cloud_test.sh upgrade-source
bash scripts/cloud_test.sh publish-page
```

upgrade-source先构建镜像，成功后保持数据库运行、暂停后端登记，完整备份到.cloud-test/backups，再加字段并补齐有可靠记录的历史来源，最后启动后端；过程短暂不能登录或扫码，不在此时读卡。备份或升级失败会停止后续步骤，不清空数据。字段已增加但补齐中断时，可以排查后重跑；已完成的来源不重复修改。数据库与后端连接只允许本手册固定的香港测试配置，不用于RDS或正式库。

成功后刷新浏览器并登录，核对原账号及6条芯片记录还在，列表多出“登记来源”：已有唯一登记操作记录的显示手机扫描/网页手工，其余显示历史未知。用网页新增演示UID应为网页手工，用NFC.cool登记一枚未入库测试卡应为手机扫描；重扫原卡不改原来源、时间或资料。不会保存卡内文本或手机时间。已有来源是unknown且没有证据时不猜测补齐。

恢复处理：保留备份和错误，不重新执行schema、不删除卷。此升级只加字段及补历史来源，旧版代码可保留新增列运行；若需回退镜像，先让AI核对，不直接导入备份覆盖后来数据。清理监听命令和挂载仅对更新后的容器生效，不需要删除服务器旧文件。

### 9.2 已验收功能分支合入main后切换

本节记录最初886a621登记分支合入main时的切换方法；当时合并只同步文档，已完成登记来源升级的ECS无需再做同一升级。该结论不适用于后续手机页部署：若ECS目前仍为886a621，容器healthy及旧版ready仅证明旧服务健康，仍须按第10节核对新版代码、003/004、配置、静态页和用户站点。不要据此跳过本轮部署或直接按通用start重建容器。

仅在已明确本次交付步骤、备份及工作区状态后，在/opt/bumbum-test按授权切换：

```bash
git fetch origin
git switch main
git -c credential.helper= pull --ff-only origin main
```

任一步失败先停下核对，不使用强制覆盖或删除文件。切换main不会迁移账号或数据库，原服务可继续运行。以后main出现新的代码/表结构变化时按当次交付步骤更新；尚未升级的旧库仍先按第9.1节处理。

### 9.3 已有云测试库升级：触碰日志

仅在cece另行授权更新香港测试环境后执行，本轮代码构建不自动部署。新空库已有目标结构；旧库不能直接start等待就绪，也不能重跑schema或删除卷。

在/opt/bumbum-test按授权切换到交付版本并核对工作区后执行：

```bash
bash scripts/cloud_test.sh upgrade-tap
```

脚本先构建新镜像，确认独立测试数据库运行，再停止后端、完整备份，然后使用固定香港配置执行触碰日志检查/升级；成功才重新启动后端。步骤失败就停止并保留备份，不自动恢复整库。原管理员、芯片、密钥和资料保留；已有无法还原物品归属的成功触碰记录时拒绝迁移，先对齐处理。检查结构已就绪时不重复DDL，但云操作仍按流程保留本次完整备份。

本入口只处理触碰日志升级，不改Nginx公开规则或发布用户页。用户站点完整部署按第10节处理查询串隐私、Referrer-Policy、HTTPS、来源限流和管理隔离并独立验收；访问公开域名不能代替本机后端检查。代码回退保留新增结构、事件和已推进计数，不自动恢复旧基线。

## 10. 手机用户站点公开部署与验收

**以下涉及服务器、配置、升级和发布，只有cece明确授权本次云部署后才执行。** 仓库有模板和本地网关检查不表示香港已更新。管理端继续test.bumbum.cc及原管理IP限制；用户站点为nfc.bumbum.cc，使用现有独立云测试数据库，不连接生产RDS，不改变正式admin.bumbum.cc规划。

### 10.1 部署前核对

由有权限的部署者只读核对当前仓库版本/本地修改、运行服务、DNS指向、80/443归属、现有证书、001/002/003状态，以及目标物品、绑定、密钥及配置核验是否与测试卡对应。已有数据及根秘密保留；缺失样品先通过现有后台建档，根秘密与卡不一致时停下重新对齐，不自动复制本地整库或重新写卡。确认备份位置、可回退代码版本及是否已有用户站点，不覆盖其他服务。原服务器安装、Git拉取、秘密配置与管理IP操作沿用前文，不重复抄另一套命令。

接管旧环境时先收集现状，不直接执行第9节的通用更新或第10.2节升级。通过阿里云香港实例终端，在项目目录逐条执行以下只读命令；核对项目参照第10.5节A，实际结果写入CHANGELOG、当前安排维护在TODO，不提前标记部署通过：

```bash
cd /opt/bumbum-test
git status --short --branch
git log -1 --oneline
bash scripts/cloud_test.sh status
curl --max-time 5 --silent --show-error --write-out '\nHTTP %{http_code}\n' http://127.0.0.1:15000/api/ready
sudo nginx -t
```

这组结果用于确认当前代码、工作区、容器状态、数据库就绪和Nginx语法。ready返回503或连接失败时保留该结果，先核对现有版本及缺少的升级，不能反复执行start或重建库。未找到目录、脚本缺失或命令报错时记录对应步骤，不自行换路径继续部署；无需输出.env、容器完整配置或完整日志。DNS、证书、测试卡与云端数据及备份/回退前提仍须随后核对，这组检查通过不代表它们已通过。

以下命令在/opt/bumbum-test执行，使用交付说明指定版本；不是main每次更新都要重做迁移。确保构建证书及Docker按前文准备，原.env.cloud-test不覆盖。PUBLIC_ORIGIN由本项目Compose固定为https://nfc.bumbum.cc，管理来源仍为https://test.bumbum.cc，不把两个来源合并。

### 10.2 升级及分别发布静态页

当前用户版本要求003和004均就绪。新入口先构建，再暂停本项目后端、完整备份；依次检查/升级003与004，已完成则跳过，任何失败停下保留备份和服务停止状态。未知旧成功日志仍按原规则拒绝，不猜历史归属。使用upgrade-view，不用只升级003的旧入口来代替本轮两项升级。

```bash
bash scripts/cloud_test.sh upgrade-view
bash scripts/cloud_test.sh publish-page
bash scripts/cloud_test.sh publish-user-page
```

成功应显示完整备份路径、检查/升级完成及后端就绪。管理静态文件发布到/var/www/bumbum-cloud-test，用户静态文件发布到/var/www/bumbum-user-test，互不覆盖index.html。两个发布命令不会安装或重载Nginx，不自动公开接口；后端和数据库端口仍只在本机，失败不重建数据库。新空库已含结构，无需再次导入schema。

### 10.3 用户域名及HTTPS

先核对nfc.bumbum.cc已指向本机且80/443允许访问；不假设AI已经设置DNS。仅首次没有该域名证书时，启用挑战专用HTTP配置到同一站点文件，不同时启用HTTP和HTTPS两个模板：

```bash
sudo install -m 0644 deploy/cloud_test/nginx-user-http.conf /etc/nginx/sites-available/bumbum-user-test
sudo ln -s /etc/nginx/sites-available/bumbum-user-test /etc/nginx/sites-enabled/bumbum-user-test
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/bumbum-user-test -d nfc.bumbum.cc
```

已有此符号链接或用户站点时先核对其目标，不重复创建或覆盖未知配置。任何命令失败就停下；HTTP配置仅开放证书挑战，不提供资料/API，不暂时放开整个网站。证书已存在且有效时跳过首次申请。不要为签证书停掉其他站点或将证书秘密复制进仓库。

再将同一站点切换为HTTPS配置，原管理站点文件和代理头配置保持不变：

```bash
sudo install -m 0644 deploy/cloud_test/nginx-user-https.conf.template /etc/nginx/sites-available/bumbum-user-test
sudo nginx -t
sudo systemctl reload nginx
sudo certbot renew --dry-run
```

先前应已按本手册安装/etc/nginx/bumbum-cloud-test-proxy.conf；缺失先核对，不绕过来源头处理。HTTPS用户模板保留HTTP的/.well-known/acme-challenge/路径供续期，其他HTTP访问转HTTPS；不要把模板同时复制到另一个也被加载的文件造成重复站点。此站点仅开放用户静态资源、POST /api/tap/verify、准确的GET /api/tap/items/数字ID/view；其他/api包括管理、短信、旧详情、扫描回调均404。原手机登记回调仍走原已验收站点，不迁移地址。

### 10.4 公网验收与回退

按[真实卡手册第6节](NFC_CARD_VERIFICATION.md#6-手机服装资料页与自动更新验收)五组使用手机正常移动网络验收；对应云后台核对次数，电脑本地后台不会自动同步。验证时间与资料读取时间分开；自动查询不重放旧读数、不重复计数。用用户域名请求/api/admin/chips、/api/admin/auth/login和管理页面应拒绝；管理站点从非允许IP仍被拒。核对用户日志不含查询参数、Cookie或动态原文，不发送完整日志到聊天。

记录实际部署提交、备份路径、证书结果、手机/浏览器与测试物品、通过和未通过项及重启保留结果；不以一次本地构建代替。回退先明确旧代码/静态版本和用户站点维护方式，再按授权操作；保留004枚举及已存在view、触碰事件、已推进计数和后来的数据，不恢复整库、不缩回枚举删除记录、不重配卡。撤回页面不会撤回已接受的真实触碰。任何失败先保留现场，管理端可用性、用户站点及数据库分别排查。



### 10.5 公网部署与整体验收清单（按本次实际情况填写）

本节是可复用的验收模板，不替代第10.1—10.4节部署步骤。单次执行结果和证据写入CHANGELOG，当前安排及验收状态只维护在TODO；下方“待填写/待测”是模板占位，不表示已验收环境仍未部署或需要重做。**任何新的服务器更新、站点切换、数据库升级、重启或DNS变更，仍须cece明确授权后执行。**

#### A. 范围与开始条件

本轮只验收香港独立测试环境：

- 管理站点：`https://test.bumbum.cc`，继续保留管理IP限制。
- 用户站点：`https://nfc.bumbum.cc`，只公开手机资料页需要的静态页面及指定用户接口。
- 数据库：现有独立云测试库，不连接生产RDS；保留已有账号、芯片、绑定、密钥、资料及历史事件。
- `admin.bumbum.cc` 属于正式管理域名规划，不在本轮更改范围内。

开始前先核对并记录以下项目；任何一项不清楚，暂停对应部署步骤，不通过删除、重建或覆盖现有资源来“清理环境”。

| 开始前核对 | 通过条件 | 本次记录 |
|---|---|---|
| 版本 | 记录GitHub main提交及ECS实际运行提交；确认准备部署的提交包含已验收的手机页 | 待填写 |
| 现有服务 | 记录容器状态、Nginx站点和监听端口；确认不会覆盖其他项目 | 待填写 |
| DNS与证书 | 核对test与nfc的A/AAAA记录、现有证书及80/443归属；不凭猜测改DNS | 待填写 |
| 数据与备份 | 记录最近一次完整测试库备份的位置、时间和可访问权限；秘密文件不上传、不发给AI | 待填写 |
| 回退准备 | 记录当前代码提交、正在使用的Nginx配置副本和回退负责人；数据库回退策略单独核对 | 待填写 |
| 目标数据 | 确认测试卡、服装物品、绑定关系、密钥版本及配置核验彼此对应 | 待填写 |
| 授权 | 确认本次允许执行的服务器、数据库和站点操作范围及维护时间 | 待填写 |

#### B. 部署与站点基础检查

以下检查在已授权的部署窗口执行。命令只用于读取状态；不要把输出中的账号、秘密或完整配置发到聊天。

**ECS终端：**

```bash
cd /opt/bumbum-test
git log -1 --oneline
git status --short
bash scripts/cloud_test.sh status
curl --fail http://127.0.0.1:15000/api/ready
sudo nginx -t
```

通过条件：实际提交与本次交付一致；没有意外的未提交修改；后端和数据库状态正常；`/api/ready` 返回就绪；Nginx配置检查成功。若命令失败，保留失败步骤和错误编号并停止后续发布，不要重复运行数据库升级或清空数据卷。

**从电脑浏览器及命令行检查：**

| 检查 | 操作 | 通过条件 |
|---|---|---|
| 管理站点 | 打开 `https://test.bumbum.cc/` | HTTPS证书有效，无浏览器安全警告；仅允许的管理IP可以进入 |
| 用户站点 | 打开 `https://nfc.bumbum.cc/` | 页面可打开，跳转到手机触碰入口；无证书警告 |
| HTTP入口 | 访问 `http://nfc.bumbum.cc/` | 正常跳转至HTTPS；不通过HTTP展示资料或调用业务接口 |
| 静态资源 | 打开手机页并查看浏览器网络错误 | 页面脚本、样式和图片资源正常；没有指向本机localhost的生产请求 |
| 站点隔离 | 通过用户域名请求管理端路径，例如 `/api/admin/chips` | 返回拒绝/404，不返回管理数据，也不出现管理登录接口 |
| 用户页面响应头 | 检查用户页面响应头 | 存在 `Cache-Control: no-store`、`Referrer-Policy: no-referrer` 和 `X-Content-Type-Options: nosniff` |

如果实际Nginx模板或接口契约与上表不一致，先核对当前代码与部署版本，不要临时放开整个`/api`、取消管理IP限制或把管理域名加入用户允许来源。

#### C. 管理端隔离与最小权限检查

| 编号 | 操作 | 预期结果 |
|---|---|---|
| C1 | 从已允许的电脑IP打开管理站点并登录 | 账号、密码及Authenticator验证码验证成功；只看到当前测试环境数据 |
| C2 | 从非允许来源尝试打开管理站点（可使用手机移动网络） | 不能访问管理页面或管理API；不要为了测试而扩大白名单 |
| C3 | 从用户站点请求 `/api/admin/chips`、`/api/admin/auth/login` 等管理路径 | 返回404/拒绝，不返回管理数据或可复用的登录结果 |
| C4 | 检查用户页面与浏览器网络请求 | 不要求用户登录；不暴露内部物品ID以外的管理数据、芯片UID、密钥、手机号、Cookie或临时凭证 |
| C5 | 查看必要的Nginx日志 | 不包含查询参数、认证头、Cookie、完整触碰动态参数或请求正文；分享日志前先脱敏 |

限流应以配置核对和已有自动化检查为主，不对公网服务进行高频压测或人为制造大量失败登录。

#### D. 真实手机端到端验收

使用已核验的服装测试卡和**新产生的真实触碰读数**，手机切换到普通移动网络（关闭Wi-Fi）访问用户站点。具体卡片准备及页面细节按[真实卡核验与密钥配置第6节](NFC_CARD_VERIFICATION.md#6-手机服装资料页与自动更新验收)执行。不得复用旧链接、分享Cookie或重新配置/写入芯片来绕过失败。

| 编号 | 操作 | 通过条件 | 结果 |
|---|---|---|---|
| D1 新触碰 | 手机真实触碰测试卡并打开页面 | 无需账号、手工输入编号或后台操作；成功显示正确服装资料与验证时间 | 待测 |
| D2 内容与隐私 | 查看名称、描述、材质、洗护说明及图片 | 只展示已允许的服装公开资料；不显示所有权、手机号、密钥或管理信息；缺图不阻断阅读 | 待测 |
| D3 刷新与重入 | 在有有效查看资格时刷新页面或重新打开当前页面 | 获取最新资料，不重复增加有效触碰次数；刷新不能把旧读数当成新触碰 | 待测 |
| D4 自动更新 | 页面保持前台阅读，在管理端修改测试服装名称后观察页面 | 约60秒内可看到新资料；返回前台会重新查询；验证时间不变，资料读取时间更新 | 待测 |
| D5 停用状态 | 通过现有管理入口停用这件测试服装，再让页面查询 | 页面停止展示资料并给出合适提示；不判定为假货。完成后按管理入口恢复测试物品 | 待测 |
| D6 失败恢复 | 在安全、可控条件下模拟短暂断网后恢复网络 | 失败不伪装为成功；旧内容若保留需标明是上次内容；恢复后可重新查询 | 待测 |
| D7 旧读数与无资格 | 尝试重复使用已消费的触碰读数，或在无有效查看资格的独立测试浏览器打开查看路径 | 旧读数不能重新签发触碰成功；没有有效查看资格不能读取受保护资料 | 待测 |
| D8 双端对照 | 在电脑管理端查询该测试物品的有效触碰统计 | 新触碰只计一次；页面自动刷新、资料查询和失败请求不增加触碰次数 | 待测 |

不需要为了人工验收等待24小时验证过期边界；24小时闲置失效、并发、迟到响应、重放与异常事务由自动化检查覆盖，并记录对应检查结果。未实际执行的项目保留“待测”，不能根据代码或本机结果推定公网通过。

#### E. 备份、重启与恢复验证

1. **备份检查：** 在授权窗口内运行 `bash scripts/cloud_test.sh backup`。确认脚本报告完整测试库备份成功、文件存在且仅授权维护者可访问。记录文件位置和时间，但不要把备份内容或秘密配置发到聊天。
2. **重启保留：** 只有在允许短暂中断的维护窗口，才按本手册第9节的停止/启动方式重启测试服务。重启前后核对原管理员账号、芯片登记、绑定、配置核验、服装资料及历史触碰统计仍在；已消费的触碰读数不能因重启重新有效。
3. **独立恢复演练：** 必须在另一套隔离的空测试库/临时环境验证备份可恢复，不能将恢复演练直接作用于当前测试库。当前手册的`backup`命令只负责生成备份，不等于恢复已验证；执行恢复前先单独确认恢复步骤、目标和清理边界。没有完成独立恢复演练时，整体结论标记为“部分通过”，不得写“备份恢复验收通过”。
4. 不运行 `docker compose down -v`，不删除数据库卷，不重新生成密钥，不重新写卡，也不把本机数据库复制覆盖香港测试库。代码回退、静态页回退、数据库恢复和芯片恢复是不同操作，不能互相替代。

#### F. 结果记录与放行标准

每次验收参照以下字段，将实际结果汇总到CHANGELOG；当前安排只更新TODO，不在手册保留第二份状态表。证据仅保存必要信息，截图隐藏个人信息和任何秘密。

```text
验收日期/时区：
验收负责人：
环境：香港独立测试环境
GitHub main提交：
ECS实际运行提交：
管理站点：https://test.bumbum.cc
用户站点：https://nfc.bumbum.cc
测试手机/系统版本：
测试服装编号（不填芯片秘密）：
备份时间与私密存放位置：
基础检查：通过 / 失败 / 未执行
管理端隔离：通过 / 失败 / 未执行
真实手机流程：通过 / 失败 / 未执行
刷新与自动更新：通过 / 失败 / 未执行
停用状态与旧读数：通过 / 失败 / 未执行
重启数据保留：通过 / 失败 / 未执行
独立恢复演练：通过 / 失败 / 未执行
未通过项及错误编号：
是否具备放行条件：
下一步负责人：
```

**整体通过条件：** B、C、D各项必测均通过；E中的备份、重启保留和独立恢复演练均有证据；没有开放管理接口、HTTPS告警、错误计数或秘密泄露等阻断问题。任何必测项失败或未执行，结果均为“未通过”或“部分通过”，写明缺口和负责人，不以代码合入、本机测试或一次页面打开代替整体验收。

**暂停/回退条件：** 管理站点失去访问控制、用户域名暴露管理API、HTTPS证书异常、现有数据缺失/被覆盖、芯片与物品对应错误、触碰计数重复或日志泄露秘密时，立即停止继续验收与扩大流量，保留现场和必要错误信息，按已确认的回退方案处理。不得自行恢复整库、删除卷或重配真实芯片。

## 11. 服装资料分支的后续部署注意

芯片绑定、密钥与配置能力合入仓库，不代表此服务器已经更新。Compose已显式传递可选MASTER_KEY_FASHION、MASTER_KEY_JEWELRY、SDM_META_KEY_V1及SDM_META_KEY_VERSION（初期v1）；准备脚本不自动生成这三把芯片根秘密。未配置时密钥功能返回503，原登录、登记和查询可继续使用。

若要在香港启用密钥功能，须在单独授权的部署步骤中安全准备并私密备份对应云环境的根密钥/全局K1，保留已有存储密钥及已生成记录，再重建后端容器加载配置；只改文件不会更新已有容器。不要运行本机setup_auth_local代替云准备，不复制本机.env，不通过重生成秘密恢复丢失配置。填写规则见[技术附录第2节](IMPLEMENTATION_DETAILS.md#2-芯片密钥与版本)，实卡和软件验收见[真实卡手册第4节](NFC_CARD_VERIFICATION.md#4-密钥与配置联合验收)。本节不授权现在修改服务器或卡片。

服装资料与桌面管理端已验收并合入main；香港实际运行版本须按第10.1节现场核对，不由仓库状态推定。当前main模板仅对/api/admin/items/数字ID/profile提高请求体上限至256k，继承原管理IP限制；其他入口保持8k。只更新镜像而不更新现有Nginx配置，会导致较长资料被旧网关拒绝。

后续经cece授权部署时，仅重跑本手册第4节的prepare命令生成HTTPS配置，再按第6节安装，安装前核对差异并备份服务器正在使用的Nginx站点配置，通过nginx -t后再reload；不得取消管理IP限制或公开管理接口。服装资料功能本身不新增数据库迁移；本轮手机页所需003/004仍按第10.2节核对升级，不能省略。普通短资料在旧网关也可能保存成功，不能据此断言新上限已生效。代码回退时资料保留，不重建库；模板更新不会自动改动服务器。

<a name="10-失败时按现象定位"></a>

## 12. 失败时按现象定位

| 现象 | 先做什么 |
|---|---|
| 找不到网页或证书签发失败 | 检查A/AAAA、80/443、安全组和nginx -t；保留错误，不关闭HTTPS检查 |
| 电脑打开网页403 | 先按实际失败路径核对Nginx错误日志中的client字段，确认本次来源与管理白名单；管理访问日志不含来源IP且省略查询参数，不能用查不到查询参数标记推断请求未到。来源确有变化且获授权后，才按第4、6节更新配置、检查并reload；不扩大访问范围，已有密码不变，只反馈必要脱敏摘要 |
| “请求必须来自允许的管理网页” | 确认打开https://test.bumbum.cc，云配置ADMIN_ORIGIN相同；不要把本机.env覆盖过去 |
| 二维码地址打不开 | 容器文件需要先导出再安全下载，按第7节处理；不是重启后端能解决 |
| 导出提示临时页面不可读取 | 确认使用最新脚本、路径来自本次设置，原终端仍在等待；原设置已结束则重新创建并用新路径，看到导出成功后才下载 |
| 后端或数据库未就绪 | 查status、logs和本机/api/ready；不重建账号、密钥或数据卷 |
| Control server error，提示/home/bumbum只读 | 更新镜像后start，当前未使用的控制socket已关闭；保留只读设置，不通过放开主目录权限解决 |
| Docker下载/构建失败 | 记录失败镜像或安装阶段，检查公网网络、磁盘及BuildKit支持；不关闭证书验证、不换成未核对版本 |
| additional privileges requested，提示allow=fs.read证书路径 | 更新main后重跑start，启动工具会将正常CA包暂存到项目内供构建读取；保留原配置和数据 |
| 手机持续401 | 核对独立扫码密码、账号名、账号启用且已完成验证器设置；别填登录密码或验证码 |
| 手机返回400 | 核对真实UID及请求格式，保留隐去内容的错误信息，不用编造编号代替 |
| 手机返回429 | 请求太密，稍等后重扫；不要循环刷接口 |
| 手机返回503 | 配置或数据库未就绪，查服务状态；修复后手动重扫 |
| 扫描后电脑没有记录 | 确认电脑在云端后台，清除不匹配的筛选；检查App是否实际发出并收到成功响应，再核对卡片触发方式 |

恢复旧代码时先核对本次数据库是否兼容，不自动倒退表结构或覆盖数据。已确认的产品、接口及第三方证据分别见[PRD](../PRD.md)、[接口说明](../API_CONTRACT.md#11-post-apiwebhookadminscan登记芯片第一阶段)及[技术附录](IMPLEMENTATION_DETAILS.md#8-配置与资料来源)。
