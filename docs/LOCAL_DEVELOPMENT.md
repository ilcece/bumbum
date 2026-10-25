# 本地启动：先确认程序和测试数据库能运行

目标：按步骤启动后，网页的后端程序和测试数据库两项均显示检查通过。main已包含运行检查、管理员登录和手动芯片登记；本页先验证环境，芯片操作另见对应手册，不涉及写卡、短信或正式上线。

香港ECS部署和手机扫描请看[云测试手册](CLOUD_TEST_DEPLOYMENT.md)，本页不用于服务器部署。main已包含Windows工具和手动芯片登记。已有测试库先按第7节检查升级，再启动；运行检查通过后用已有管理员登录，不重复创建账号。浏览器统一使用本页的localhost地址。

## 0. Windows：GitHub Desktop＋双击运行

Windows三个入口、手动芯片登记及项目可空调整都已由cece验收并合入main；在main双击运行后即可查看芯片。旧库先按第7节检查升级，已升级的原配置和资料继续使用。手册总入口是[操作入口](op_guide.md)。

### 日常快捷检查入口

除首次准备、启动、停止外，main保留两个双击工具，所在任务分支已由cece确认测试无问题。它们放在项目根目录，无需手动找地址栏或先切目录；保留在仓库里使用，不把bat单独复制到桌面。想从桌面打开时创建快捷方式，目标仍指向原文件。

| 入口 | 用途 | 预期结果 |
|---|---|---|
| [打开项目PowerShell.bat](../打开项目PowerShell.bat) | 打开命令窗口并定位当前仓库根目录 | 显示项目路径；不切分支、不拉取代码、不启动服务。关闭该窗口不停止已运行项目；纯ASCII入口新开Windows自带PowerShell窗口并明确设置项目目录，启动失败保留提示 |
| [查看启动日志.bat](../查看启动日志.bat) | 查看backend.log和frontend.log各末尾30行 | 输出日志后等待按键；不存在时明确提示。日志可能含个人信息，分享前先检查 |


PowerShell常用命令（先双击上面的打开入口）：

| 命令 | 目的 |
|---|---|
| `Get-Location` | 确认现在位于哪个文件夹 |
| `git branch --show-current` | 核对当前分支 |
| `git log -1 --oneline` | 核对当前提交编号 |
| `git status --short` | 看是否有本地未提交修改；有修改时先保留核对 |
| `Get-Content .local-run\backend.log -Encoding UTF8 -Tail 30` | 只查看后端日志末尾 |
| `Get-Content .local-run\frontend.log -Encoding UTF8 -Tail 30` | 只查看网页日志末尾 |

### 只做一次：固定本地工作目录

1. 安装 [GitHub Desktop](https://desktop.github.com/)、[Python 3.12](https://www.python.org/downloads/)、[Node.js 24 LTS](https://nodejs.org/) 和 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。Docker 使用 Linux 容器；安装或首次启动的系统确认需要本人完成。
2. 在 GitHub Desktop 用 `File → Clone repository` 克隆 `ilcece/bumbum`，以后一直用这个目录。已有克隆的直接使用；不要再下载ZIP或把 `.venv` 复制过来。若旧目录已有账号和数据库，先请 AI 协助迁移配套配置，避免换目录后生成新密码却连接旧数据卷。
3. 在 `Current branch` 选择 `main`；验收尚未合并的功能时，选择本次任务指定的分支。点击 `Fetch origin` 检查更新；出现 `Pull origin` 时继续点击，才会下载更新。确认没有自己的未提交修改被带到错误分支。
4. 点击 `Repository → Show in Explorer` 打开仓库目录，双击 [首次准备.bat](../首次准备.bat)。看到“准备完成”再双击 [启动项目.bat](../启动项目.bat)。从原环境升级的也可执行首次准备：已有配置及密钥保留，只补齐缺少的本机认证配置。

脚本不自动安装系统软件或修改 PowerShell 执行策略。缺少软件会显示安装地址；安装后重新打开入口。Python 和网页依赖第一次可能需要下载，单次安装最多等待15分钟；原环境没有本工具标记时也会检查安装，之后未变化就跳过。

尚无管理员账号时，启动成功后按 [管理员登录第2节](ADMIN_LOGIN.md#2-创建自己的管理员账号) 完成一次设置；工具不会替你设置密码或扫码。

### 每次验收：同步、启动、操作、停止

| 顺序 | 你做什么 | 正常结果 |
|---|---|---|
| 1 | 更新前双击 [停止项目.bat](../停止项目.bat)；之前手动启动的服务仍在原终端按 Ctrl+C | 本工具的前后端退出；不会结束其他程序 |
| 2 | GitHub Desktop 选本次分支，点 Fetch，再按提示 Pull | 代码更新；脚本不会自动切分支、下载或合并 |
| 3 | 双击启动项目 | 显示分支、提交编号和进度；自动更新变化的依赖，按需打开 Docker Desktop |
| 4 | 等浏览器打开 [http://localhost:5174](http://localhost:5174) | 后端、数据库检查通过；用已有账号及手机验证码登录 |
| 5 | 按对应功能手册验收，结束后双击停止项目 | 前后端停止；本工具启动的数据库停止，配置、账号和数据保留 |

保持启动窗口运行，关闭浏览器不会停止项目。正常已运行或正在准备时再次双击启动，入口直接退出，不重复启动服务、不再打开浏览器、不留下第二个等待窗口；Windows运行.bat时可能短暂闪过终端窗口。若切过版本或运行检查未通过，仍保留具体提示，不能当作正常重复启动忽略。工具固定使用5000和5174端口，不会自动换端口或强行结束占用程序。

数据库原本已经运行时，工具复用它，停止时也让它继续运行；本工具之前启动的数据库会记住所属容器，停止时只处理它。不退出整个 Docker Desktop，不删除数据卷；启动失败后也可使用停止入口。直接关闭启动窗口会结束其前后端，数据库需另点停止；正常停止后原窗口可能仍停在“按任意键继续”，可按键关闭。

启动成功后按Ctrl+C，会显示“已收到手动停止指令”和“前后端已停止”，按正常停止处理；准备或启动尚未完成时按Ctrl+C则说明当前步骤已手动中断，均不再误报需要排查。Windows可能继续询问 `Terminate batch job (Y/N)?`：Y结束当前.bat，双击打开的窗口通常关闭；N继续脚本剩余步骤，正常停止不会再显示错误排查提示。日常仍建议使用停止项目入口，一起按规则处理数据库。

停止完成会显示“停止完成；配置、管理员账号和测试数据保留”。再次启动后用原账号登录，核对原芯片记录。换版本后页面缺少功能时先核对版本，不因页面变化重建数据库或账号。

本机依赖标记、运行记录和后端/网页日志放在 `.local-run/`，不上传 Git。失败时保留窗口，先记录最后一个阶段；服务错误再看 `backend.log` / `frontend.log`，分享前隐藏个人信息，不发送 `.env`。遇到缺少配置或数据库升级要求，让 AI 排查，不删除环境、密码或数据库重新来过。

### 这一版怎样验收

- 首次准备成功，再次准备保留原配置；已有管理员仍能登录。
- 启动后网页两项检查通过；再次双击不报错、不再打开网页、不留下第二个等待窗口，原服务继续运行。缺依赖时能修复，网络或安装失败会明确停下。
- 停止后重新启动，账号和原测试数据仍在；原本手动运行的服务不会被停止工具关闭。
- 端口冲突时明确报错、不换地址、不结束其他程序；按第6节处理后可重试。

cece已确认Windows工具其余验收通过，并授权修正Ctrl+C提示后合入main；本次提示调整有回归检查，Windows原生自动检查在云端仍会跳过。下方保留各系统手动步骤，用于其他系统和故障排查；日常启动不必每次执行完整测试。

本分支接入桌面管理端后，登录前从“检查运行环境”展开运行检查，登录后可从顶栏“运行检查”或侧栏“系统状态”检查。默认登录成功进入工作台，芯片和物品通过侧栏进入；启动命令与端口不变，不支持手机后台适配。

## 1. 准备工具和目录

需要 Python 3.12、Node.js 24 LTS、Docker Desktop。Windows 的 Docker Desktop 使用 Linux 容器；Linux 也可用 Docker Engine 和支持 `--wait` 的 Compose v2。

先启动 Docker，再打开终端，进入包含 `README.md`、`compose.yaml` 的仓库根目录。**以下命令都在根目录逐条执行；某条报错时先看第6节，不继续后面的步骤。**

| 检查什么 | macOS / Linux | Windows PowerShell | 正常结果 |
|---|---|---|---|
| Python | `python3 --version` | `py -3.12 --version` | Python 3.12.x |
| Node.js | `node --version` | `node --version` | v24.x |
| 数据库运行工具 | `docker compose version`、`docker info` | 同左 | 显示版本，且能连接 Docker |

Windows 如果找不到 `py`，但 `python --version` 显示3.12.x，可把下一节创建虚拟环境的 `py -3.12` 换成 `python`；不要直接用其他版本。缺少工具时先安装对应版本，再重新打开终端，不需要阿里云密码。

建议用 GitHub Desktop 克隆一次，在固定目录切换分支。更新代码时先停止旧后端和网页，选好分支，再点 Fetch origin；有更新时继续点 Pull origin。保留本机 `.env` 和数据库；不要把 `.venv` 复制到新目录，换目录后按第2节重新建立。

## 2. 首次准备

Python 虚拟环境 `.venv` 是本项目安装依赖的目录，不需要手动激活。

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/setup_local.py
```

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -X utf8 scripts\setup_local.py
```

预期看到“本地测试配置已准备好”；已有 `.env` 时会提示保留原配置，同样正常。脚本只生成本机数据库密码，保存在不上传的 `.env`，不覆盖已有文件；芯片和其他秘密继续留空。公开的建表文件会设置为容器可读。

接着启动测试数据库，所有系统相同：

```bash
docker compose up -d --wait --wait-timeout 120
```

首次需要下载 MySQL 镜像；空数据卷会初始化24张表和服装、饰品两个项目，已有数据不会重复建表。数据库就绪后命令成功退出，后端使用普通测试账号，不用数据库管理账号。

再安装网页依赖，按系统选择一条：

| 系统 | 命令 |
|---|---|
| macOS / Linux | `npm --prefix frontend/admin ci` |
| Windows PowerShell | `npm.cmd --prefix frontend/admin ci` |

Windows 使用 `npm.cmd`，可避开 PowerShell 阻止执行 `npm.ps1` 的问题，不需要为此修改系统执行策略。已有配置和环境的，不必重复创建 `.venv`；更新依赖的时机见第5节。

## 3. 启动后端和网页

保留两个终端窗口，都在仓库根目录。

**终端一，启动后端：** 按自己的系统选择一条。

| 系统 | 命令 |
|---|---|
| macOS / Linux | `.venv/bin/python -m flask --app app:create_app --no-debug run --host 127.0.0.1 --port 5000` |
| Windows PowerShell | `.\.venv\Scripts\python.exe -X utf8 -m flask --app app:create_app --no-debug run --host 127.0.0.1 --port 5000` |

看到 `http://127.0.0.1:5000` 后保持窗口运行。直接打开这个地址的首页会提示地址不存在；运行检查入口是 `/api/health` 和 `/api/ready`。

**终端二，启动网页：**

| 系统 | 命令 |
|---|---|
| macOS / Linux | `npm --prefix frontend/admin run dev` |
| Windows PowerShell | `npm.cmd --prefix frontend/admin run dev` |

在浏览器打开：[http://localhost:5174](http://localhost:5174)。

预期两个检查都通过。项目固定使用5174端口，占用时会报错，不会自动换成5173或其他端口。保留这个地址，后续管理员登录也会检查网页来源。

网页读取真实接口，没有模拟“成功”结果；点“重新检查”可再次确认。两个终端都要保持运行。

## 4. 验证这一小步

再开一个根目录终端，按系统选择命令：

| 检查 | macOS / Linux | Windows PowerShell |
|---|---|---|
| 已运行服务 | `.venv/bin/python scripts/verify_local.py` | `.\.venv\Scripts\python.exe -X utf8 scripts\verify_local.py` |
| 自动检查 | `.venv/bin/python -m pytest -q` | `.\.venv\Scripts\python.exe -X utf8 -m pytest -q` |

服务检查应显示两行“通过”；任一失败会以非零状态退出。普通自动检查不要求数据库，真实数据库检查默认显示 `skipped`（跳过），不算通过。出现 `failed` 表示未通过。

管理员认证与芯片管理的完整自动检查需要 Docker，按系统选择一条：

| 系统 | 命令 |
|---|---|
| macOS / Linux | `.venv/bin/python -m pytest -q --auth-db` |
| Windows PowerShell | `.\.venv\Scripts\python.exe -X utf8 -m pytest -q --auth-db` |

命令新建专属临时MySQL，结束后删除测试容器及专属卷，不占用33306端口，不修改已有测试库。包含认证、芯片、旧库升级和备份恢复检查；你的已有库按第7节单独升级，不由测试命令代为修改。下方RUN_DB_TESTS只读检查已启动的原测试库。

要检查原测试库，先确认第2节的数据库已启动，再按系统执行：

```bash
# macOS / Linux
RUN_DB_TESTS=1 .venv/bin/python -m pytest -q
```

```powershell
# Windows PowerShell
$env:RUN_DB_TESTS="1"
try {
    .\.venv\Scripts\python.exe -X utf8 -m pytest -q
} finally {
    Remove-Item Env:RUN_DB_TESTS -ErrorAction SilentlyContinue
}
```

这会额外确认普通账号连接、UTC时间设置、完整表清单及数据库就绪接口。检查只接受本机33306端口和测试账号，不写业务数据。Windows 的 `-X utf8` 让本次 Python 使用UTF-8读取中文文件，不改系统设置，也兼容尚未明确文件编码的旧版本。

最后检查网页能否打包：

| 系统 | 命令 |
|---|---|
| macOS / Linux | `npm --prefix frontend/admin run build` |
| Windows PowerShell | `npm.cmd --prefix frontend/admin run build` |

成功表示类型检查和打包通过。服务检查、自动检查、网页构建和浏览器里两个状态都正常，才算这一小步通过；不代表管理员登录或业务功能已经完成。

文档改动后，AI还需运行本地链接和示例检查：

| 系统 | 命令 |
|---|---|
| macOS / Linux | `.venv/bin/python scripts/check_docs.py` |
| Windows PowerShell | `.\.venv\Scripts\python.exe -X utf8 scripts\check_docs.py` |

Windows工具的自动检查在 `tests/test_windows_local.py`；其中真实Windows文件锁和进程管理检查在其他系统会跳过，不能把跳过当作通过。

## 5. 停止和下次继续

在后端和网页各自的终端按 `Ctrl+C`，再执行：

```bash
docker compose stop
```

测试数据会保留。下次先启动 Docker，再执行 `docker compose up -d --wait --wait-timeout 120`，然后按第3节启动后端和网页；无需重新建表或重复首次准备。

拉取代码或切换分支后，如果 `requirements-dev.txt` 变化，重跑第2节的 Python 依赖安装命令；如果前端 `package.json` 或 `package-lock.json` 变化，重跑网页依赖安装命令。遇到数据库升级时按专门的升级说明操作，不重新执行建表文件。

`.env` 和数据库卷要配套保留，不提交到 Git。不要删除配置后重新生成密码，也不要为重跑建表删除数据卷；修改 `db/schema.sql` 不会自动更新已有数据库。Windows双击工具的日常用法见第0节；不要与手动服务同时运行。

## 6. 常见情况

| 看到什么 | 下一步 |
|---|---|
| 找不到 Python 或版本不对 | 按第1节检查3.12版本；安装后重开终端，已有环境用 `.venv` 内的 Python |
| 找不到 docker，或无法连接 Docker | 安装并启动 Docker；Windows 确认使用 Linux 容器；重试 `docker compose version` 和 `docker info` |
| 33306、5000或5174端口被占用 | 先确认是否有自己之前启动的服务，停止它再重试；不要结束不认识的进程或随意改端口 |
| 数据库启动失败 | 用 `docker compose ps -a` 查看状态；首次准备没完成的先补齐，已有数据不要盲目清空，让 AI 根据隐藏秘密后的报错排查 |
| 更新后数据库检查不通过，原来一直正常 | 本次项目可空需要升级，按第7节检查；不要重新建表或清空数据 |
| 后端正常，数据库未就绪 | 确认数据库启动成功，`.env` 与最初初始化使用的账号密码一致，再点网页“重新检查” |
| 后端无法连接 | 确认终端一仍在运行、没有启动错误；不要只启动网页 |
| 测试报 UnicodeDecodeError，提示 gbk 无法解码 | 使用第4节带 `-X utf8` 的 Windows 命令；不要把源码改成GBK或删除数据库 |
| 已有 `.env` 但提示缺少配置 | 保留文件，只补齐报错提到的变量；不要把文件或密码发到聊天里 |
| npm 提示“禁止运行脚本” | 使用 Windows 命令中的 `npm.cmd`，不必修改系统执行策略 |
| 没有登录表单或不认识认证测试参数 | 确认 main 已拉取最新代码、依赖已更新，并重启后端和网页；不要继续使用旧ZIP目录 |
| 双击提示项目正在运行或版本已变化 | 双击停止项目后再启动；若之前是手动运行，回原终端按 Ctrl+C |
| 旧版重复双击报“本机操作遇到异常” | 在原启动窗口按Ctrl+C，Fetch并Pull工具分支最新修复，再启动和重复双击复测；不删.local-run、配置或数据库来绕过 |
| 提示数据库属于另一个目录 | 回原克隆目录操作；不要清空数据卷，让 AI 协助核对目录及配套配置 |
| 工具提示安装失败或超时 | 检查网络及对应工具版本，再重试；安装标记不会把失败记成完成。需要详细信息时让 AI 指导执行第2节的单项命令，分享报错前隐藏秘密 |
| Windows不显示.bat后缀 | 在资源管理器选择“查看 → 显示 → 文件扩展名”，确认执行的是仓库根目录入口 |

程序、网页和数据库端口只监听本机，不能直接作为公网服务。历史实测和验证范围见 [变更记录](../CHANGELOG.md)。cece 已反馈 Windows 的13项检查和网页构建通过；本次文档修订仍需各系统按实际环境核对，不代表已测试所有工具安装方式。

## 7. 已有测试库升级：允许芯片暂不分配项目

目的：保留原账号、登录资料和芯片记录，让新芯片可以先入库、后确定用途。**只用于本机测试库，不用于RDS。新建空库已使用新版schema时无需升级；旧库不能靠重启或重跑schema自动升级。**

1. 在GitHub Desktop更新 `main`。停止原后端和网页，保留数据库运行；数据库未启动时按第2节启动，保留 `.env` 和数据卷。
2. 在仓库根目录执行下面的“检查”命令。看到“需要升级”再执行“升级”；看到“已是新版本”则无需重复执行。

| 操作 | macOS / Linux | Windows PowerShell |
|---|---|---|
| 检查，不改数据 | `.venv/bin/python scripts/migrate_local.py` | `.\.venv\Scripts\python.exe -X utf8 scripts\migrate_local.py` |
| 先备份，再升级 | `.venv/bin/python scripts/migrate_local.py --apply` | `.\.venv\Scripts\python.exe -X utf8 scripts\migrate_local.py --apply` |

3. 正常时先显示完整备份的文件路径，再显示“升级完成，原有账号和芯片资料保留”。备份在不上传Git的 `backups/`，包含账号及加密资料，留在本机，不发聊天。脚本不会显示密码，不覆盖 `.env`；备份失败就停止，表结构不改。重复执行已完成的升级只提示无需执行。
4. 双击启动项目，或按第3节手动重启后端和网页。两项运行检查通过后，用原账号登录，核对原芯片还在，再按[芯片登记手册](CHIP_REGISTRATION.md)补测“暂不分配”、重复提示和筛选。

脚本只接受本机33306、bumbum_dev、bumbum_digital及开发模式；还会核对Docker数据库属于当前目录，且备份和升级指向同一数据库。若仍在旧ZIP目录或换过克隆目录，先让AI核对配置和数据位置，不通过删除卷解决。

失败时先停在当前步骤：保留备份和报错，让AI排查，不重复初始化或直接导入备份覆盖现有数据。MySQL 8.0用一条完整的表结构修改执行本次升级；该语句失败时旧结构整体保留，检查不通过不会被当成成功。升级后检查异常时保持后端停止，先运行“检查”并反馈结果。

确需回到旧版时，先停后端和网页，再使用相同脚本的 `--apply --rollback`，同样先备份。已有未分配项目的芯片会拒绝回退，不删除记录或替你猜项目；此时保留新版结构，让AI协助安排回退。不要自行恢复整个SQL备份覆盖后来数据。回退是备用处理，不属于本次正常验收步骤。


## 8. 已有测试库升级：登记来源

目的：给芯片列表增加首次“登记来源”，保留账号和原有资料。main已包含此字段；旧库更新后需要升级，新建空库已包含字段。与第7节的项目可空升级不同，两项都需满足；已经完成第7节的不重做。

先停止后端和网页，保留本机测试数据库运行；双击工具在启动窗口按Ctrl+C会停止前后端、保留数据库。数据库若已停止，用第2节的Compose启动命令恢复。保留.env，不用schema重新建表。

在仓库根目录执行：

| 操作 | macOS / Linux | Windows PowerShell |
|---|---|---|
| 只检查来源字段 | `.venv/bin/python scripts/migrate_local.py --registration-source` | `.\.venv\Scripts\python.exe -X utf8 scripts\migrate_local.py --registration-source` |
| 先完整备份，再升级/补齐 | `.venv/bin/python scripts/migrate_local.py --registration-source --apply` | `.\.venv\Scripts\python.exe -X utf8 scripts\migrate_local.py --registration-source --apply` |

成功应显示升级完成或已是目标版本；没有可补齐记录时不重复改数据。备份在backups目录，含账号秘密，不上传或分享。随后按第3节启动前后端，登录查看新增“登记来源”：网页手工、手机扫描、历史未知；首次来源在重复登记时不变。

补齐只依据唯一、合法的首次登记操作记录；历史没有证据时保留未知。来源已存在但历史补齐中断，可以排查后重跑。失败时保留报错和备份，不清空库、不自动恢复备份覆盖后来数据；新增列可保留供旧版代码运行，不需删列回退。此命令只允许默认本机测试库，不连接香港或生产环境。


### 8.1 Windows备份目录无权限时

若出现PermissionError且定位为无法在仓库backups创建临时文件，可改用本人本地应用数据目录，不改旧目录权限，不删除旧备份。本参数只改变备份位置，数据库连接、容器归属及server_uuid核对、完整导出校验仍保留，备份失败不改表。默认不传参数仍使用仓库backups；只检查时不会创建目录。

先停止前后端、保留数据库和Docker运行。在仓库根目录的PowerShell逐条执行；任何一步报错就停下，不继续后续步骤：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\migrate_local.py --registration-source --apply --backup-dir "$env:LOCALAPPDATA\Bumbum\backups"
.\.venv\Scripts\python.exe -X utf8 scripts\migrate_local.py --registration-source
```

第一条应先显示完整备份路径，再显示升级完成；第二条应说明来源字段已存在。使用自己的私有本地目录，不选公开共享或仓库源码目录；备份包含账号秘密，不上传或分享。不要自行清理原backups或.partial文件。成功后双击启动项目，确认第5步及网页两项检查通过、原账号和芯片记录保留，再继续对应业务验收。此参数也支持第7节升级，不能用来绕过数据库身份检查。
