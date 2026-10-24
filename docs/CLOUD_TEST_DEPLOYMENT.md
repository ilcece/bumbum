# 香港云测试：手机扫描，电脑查询

目标：手机用NFC.cool扫描后，打开`https://test.bumbum.cc/`登录，点击“查询”看到真实芯片编号。本手册只管香港测试环境；本机仍按[本地运行](LOCAL_DEVELOPMENT.md)，不会同步两边的账号和数据。正式管理域名仍为admin.bumbum.cc。

本分支feat/nfc-scan-webhook提供代码及部署文件，cece已配置香港HTTPS网页并可打开，云端管理员已登录，cece已同意先写固定文本再扫描，6枚卡实测回调200；待核对后台列表和重复扫描。适用已确认的香港Ubuntu 22.04、2核4GiB；使用独立MySQL，不连接生产RDS。本轮已由cece确认并完成测试卡固定文本预写；后续新卡的预写和正式SUN配置分开，不擅自覆盖已有卡内容或密钥。

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
git -c credential.helper= clone --branch feat/nfc-scan-webhook https://github.com/ilcece/bumbum.git /opt/bumbum-test
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

官方说明该能力需要Platinum订阅；能看到设置不代表实际发送已可用，先在自己手机核对。已知用户提供版本7.30；真实请求、订阅可用性及目标卡仍待本次验收。App只保存一个回调网址；测试期间使用这里的地址，不与其他接收系统混用。

1. 按cece已确认的本轮流程，目标卡先在NFC.cool批量写入固定文本，再读取真实7字节UID；本轮使用cece。此步骤只准备登记触发内容，不包含密钥、SUN或正式写卡配置；已配置的卡不要覆盖。随机UID、兼容模式占位文字、二维码UUID不作为真实UID登记。
2. 读取未登记的测试芯片，再点击“保存NFC标签”（保存到NFC.cool），触发回调；这是cece于2026-10-25对版本7.30的实测步骤，仅识别出UID尚不会发送。最新实测6枚写有cece文本的卡均401后200；完全空白卡无回调，已按cece决定采用预写流程。此前“完全空白卡也已触发”的判断撤回。电脑在云测试后台点“查询”或按UID搜索，成功后应显示一条“未分配、待绑定”。不要查看localhost的列表。
3. 再扫描同一卡，应仍只有一条，原项目、批次和状态不变；已有手动登记资料同样保留。手机不提交项目或批次。
4. 临时将手机扫码密码改错，应请求失败且不新增；然后恢复正确密码。管理员停用后也不再允许扫码登记。
5. 网络失败时查看App的请求结果或失败记录，恢复网络后人工重扫。手机读卡成功不等于后台保存成功；电脑查到记录才确认入库。App是否能清楚展示失败结果需记录实测，不假定会显示后台中文提示。
6. 正常网络下记录从扫描到后台可查询所需时间，目标2秒内；不先承诺任何网络下都能达到。通过后按第9节停止再启动，确认账号和记录保留。

首次请求可能先收到401认证挑战，App再带已保存的凭证重发，最终成功才算通过；持续401才是凭证或账号问题。失败没有自动离线队列，不能以为稍后会自行补入库。登记不代表防伪验证通过。

持续401时，在手机点一次“测试Webhook”或读取并保存一次真实标签，随后运行第9节的logs命令，查看最近的“扫码认证诊断”：

| 诊断内容 | 含义 |
|---|---|
| 认证头存在=否 | 请求没有携带认证信息；首次挑战正常，重发后仍如此才需检查App发送行为 |
| Basic凭证可解析=否 | 认证方式或格式不符合Basic，未尝试写数据库 |
| 用户名匹配=否／密码匹配=否 | 手机送来的对应字段与运行配置不一致；日志只显示匹配标志及密码字符数，不显示凭证 |
| 凭证匹配，但账号不存在、停用或未完成验证器设置 | 检查凭证归属账号的状态，不重置已验证的密码 |

401响应对手机仍保持统一错误，不返回这些诊断细节。空JSON的认证自检返回400，只证明凭证检查通过，不能证明后续账号检查或真实入库通过；App测试按钮也不能替代真实卡验收。最新实测有内容卡已完成401挑战后重发并获得200，此类首个401是正常握手。完全空白卡无回调不靠服务端认证解决；本轮已批准固定文本预写。随机UID卡返回400是另一项规则，不代表密码错误。

### 临时监听实际回调

cece已要求本轮无秘密测试卡直接查看请求体原文。更新代码并start一次后，执行：

```bash
bash scripts/cloud_test.sh listen-scan-raw
```

终端“扫码请求观察”新增“请求体原文”，以WARNING记录收到的完整UTF-8正文，包括未知字段、空内容、非JSON和不完整JSON；认证失败、参数被拒也能看到。JSON日志中的\n或\"是换行或引号的转义，不是App额外提交的字段。此模式只用于本轮确认不含秘密的测试数据，不记录Authorization等请求头，不关闭认证或允许非法数据入库。仍保留8192字节、明确长度、五分钟及每进程12条的采集边界。Ctrl+C退出，或使用stop-listen关闭；原文仍保留在Docker日志中。普通listen-scan保持只输出结构、不输出原文。

先用一枚已能回调的卡确认出现原文，再用空白卡执行相同步骤；若空白卡没有任何观察行，就没有本监听收到的请求体可看，不能将其归因于UID格式校验。Nginx未转入后端的请求仍查访问日志。

需要知道App到底提交了什么结构时，先更新并start一次以加载新的监听代码和只读控制目录，再执行：

```bash
bash scripts/cloud_test.sh listen-scan
```

看到“结构监听已开启”后，保持终端，手机读取并保存同一枚卡一次。终端会出现“扫码请求观察”的JSON摘要，记录本次请求编号、请求方式、认证是否存在、内容类型、字段类型、UID是冒号/空格等何种格式，以及最终响应状态；认证失败时还会保留原来的匹配诊断。将这些摘要发给AI即可，不需再靠旧日志猜测。401之后如果400，比较这两条请求摘要来确定哪项输入不符合契约。

普通结构模式不记录完整UID、卡内内容、日期原文、收到的密码或完整认证头。只列预定义的常见字段名和类型，其余字段只计数；最多观察8192字节且长度明确的JSON，过大、非JSON或长度未知的请求只记元信息。摘要标记的是收到的输入，不证明芯片身份，原认证、参数检查和保存结果不改变。到达Nginx但未转给后端的请求，仍按访问日志及错误日志定位。

监听默认关闭，最长5分钟，每个工作进程最多记录12条，计数随进程重建重置。按Ctrl+C提前结束，服务继续运行；SSH意外断开时采集也会到期停止。需要从另一个终端关闭采集时执行：

```bash
bash scripts/cloud_test.sh stop-listen
```

控制文件只含到期时间，不改.env、账号或数据库。关闭后已有摘要仍属于Docker日志；普通模式不会生成包含原始请求内容的抓包文件；原文模式的正文保留在Docker日志。

排查新一轮操作时，先在ECS实时查看访问日志，再操作手机一次：

```bash
tail -n 0 -f /var/log/nginx/bumbum-cloud-test-access.log
```

此处能看到每次请求的地址和状态，包括200/400/401；backend的“扫码认证诊断”只记录认证失败，没有新警告不等于没有请求。按Ctrl+C仅结束查看。之后再运行logs查看对应时间的诊断；后端时间为UTC，加8小时对应北京时间。例如UTC 16:55:58对应次日00:55:58。curl不带凭证的检查也会产生认证缺失日志，按时间区分，不把旧记录当作手机重试结果。

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

更新时先确认本分支没有自己的未提交修改，备份成功后再执行：

```bash
cd /opt/bumbum-test
bash scripts/cloud_test.sh backup
git status --short
git -c credential.helper= pull --ff-only origin feat/nfc-scan-webhook
bash scripts/cloud_test.sh start
bash scripts/cloud_test.sh publish-page
git log -1 --oneline
```

应为交付的新提交，原账号和芯片仍在；Nginx、证书或表结构若有变化，以该次交付的专门步骤为准，不自动改表。当前脚本保留已有秘密，不自动恢复备份覆盖数据库。合入main后由交付说明调整拉取分支，不擅自切到过时分支。

首次构建在创建服务前就失败时，备份命令暂不可用；直接拉取交付的修复再执行start即可。已有.env.cloud-test保留，不重复生成密码或重建目录；数据库启动后再使用备份入口。

## 10. 失败时按现象定位

| 现象 | 先做什么 |
|---|---|
| 找不到网页或证书签发失败 | 检查A/AAAA、80/443、安全组和nginx -t；保留错误，不关闭HTTPS检查 |
| 电脑打开网页403 | 电脑公网IP可能变化；重跑第4节prepare命令更新IP，再按第6节安装生成的HTTPS配置、检查并reload；已有密码不变 |
| “请求必须来自允许的管理网页” | 确认打开https://test.bumbum.cc，云配置ADMIN_ORIGIN相同；不要把本机.env覆盖过去 |
| 二维码地址打不开 | 容器文件需要先导出再安全下载，按第7节处理；不是重启后端能解决 |
| 导出提示临时页面不可读取 | 确认使用最新脚本、路径来自本次设置，原终端仍在等待；原设置已结束则重新创建并用新路径，看到导出成功后才下载 |
| 后端或数据库未就绪 | 查status、logs和本机/api/ready；不重建账号、密钥或数据卷 |
| Control server error，提示/home/bumbum只读 | 更新镜像后start，当前未使用的控制socket已关闭；保留只读设置，不通过放开主目录权限解决 |
| Docker下载/构建失败 | 记录失败镜像或安装阶段，检查公网网络、磁盘及BuildKit支持；不关闭证书验证、不换成未核对版本 |
| additional privileges requested，提示allow=fs.read证书路径 | 更新本分支后重跑start，启动工具会将正常CA包暂存到项目内供构建读取；保留原配置和数据 |
| 手机持续401 | 核对独立扫码密码、账号名、账号启用且已完成验证器设置；别填登录密码或验证码 |
| 手机返回400 | 核对真实UID及请求格式，保留隐去内容的错误信息，不用编造编号代替 |
| 手机返回429 | 请求太密，稍等后重扫；不要循环刷接口 |
| 手机返回503 | 配置或数据库未就绪，查服务状态；修复后手动重扫 |
| 扫描后电脑没有记录 | 确认电脑在云端后台，清除不匹配的筛选；检查App是否实际发出并收到成功响应，再核对卡片触发方式 |

恢复旧代码时先核对本次数据库是否兼容，不自动倒退表结构或覆盖数据。已确认的产品、接口及第三方证据分别见[PRD](../PRD.md)、[接口说明](../API_CONTRACT.md#11-post-apiwebhookadminscan登记芯片第一阶段)及[技术附录](IMPLEMENTATION_DETAILS.md#8-配置与资料来源)。
