# 本地启动：先确认程序和测试数据库能运行

目标：按步骤启动后，网页显示“后端已启动、测试数据库连接正常”。本文对应当前 main 的运行检查，不含芯片登记、写卡或短信，也不是正式上线步骤。

管理员登录仍在 [feat/admin-auth 分支](https://github.com/ilcece/bumbum/tree/feat/admin-auth)验收；测试登录时，先切换到该分支，再读该分支的 `docs/ADMIN_LOGIN.md`。不要在 main 执行只有功能分支才提供的命令。

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

在浏览器打开 **http://localhost:5174**，预期两个检查都通过。项目固定使用5174端口，占用时会报错，不会自动换成5173或其他端口。保留这个地址，后续管理员登录也会检查网页来源。

网页读取真实接口，没有模拟“成功”结果；点“重新检查”可再次确认。两个终端都要保持运行。

## 4. 验证这一小步

再开一个根目录终端，按系统选择命令：

| 检查 | macOS / Linux | Windows PowerShell |
|---|---|---|
| 已运行服务 | `.venv/bin/python scripts/verify_local.py` | `.\.venv\Scripts\python.exe -X utf8 scripts\verify_local.py` |
| 自动检查 | `.venv/bin/python -m pytest -q` | `.\.venv\Scripts\python.exe -X utf8 -m pytest -q` |

服务检查应显示两行“通过”；任一失败会以非零状态退出。普通自动检查不要求数据库，真实数据库检查默认显示 `skipped`（跳过），不算通过。出现 `failed` 表示未通过。

要检查真实 MySQL，先确认第2节的数据库已启动，再按系统执行：

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

## 5. 停止和下次继续

在后端和网页各自的终端按 `Ctrl+C`，再执行：

```bash
docker compose stop
```

测试数据会保留。下次先启动 Docker，再执行 `docker compose up -d --wait --wait-timeout 120`，然后按第3节启动后端和网页；无需重新建表或重复首次准备。

拉取代码或切换分支后，如果 `requirements-dev.txt` 变化，重跑第2节的 Python 依赖安装命令；如果前端 `package.json` 或 `package-lock.json` 变化，重跑网页依赖安装命令。遇到数据库升级时按专门的升级说明操作，不重新执行建表文件。

`.env` 和数据库卷要配套保留，不提交到 Git。不要删除配置后重新生成密码，也不要为重跑建表删除数据卷；修改 `db/schema.sql` 不会自动更新已有数据库。当前仓库没有一键启动工具，按本文分别启动即可。

## 6. 常见情况

| 看到什么 | 下一步 |
|---|---|
| 找不到 Python 或版本不对 | 按第1节检查3.12版本；安装后重开终端，已有环境用 `.venv` 内的 Python |
| 找不到 docker，或无法连接 Docker | 安装并启动 Docker；Windows 确认使用 Linux 容器；重试 `docker compose version` 和 `docker info` |
| 33306、5000或5174端口被占用 | 先确认是否有自己之前启动的服务，停止它再重试；不要结束不认识的进程或随意改端口 |
| 数据库启动失败 | 用 `docker compose ps -a` 查看状态；首次准备没完成的先补齐，已有数据不要盲目清空，让 AI 根据隐藏秘密后的报错排查 |
| 后端正常，数据库未就绪 | 确认数据库启动成功，`.env` 与最初初始化使用的账号密码一致，再点网页“重新检查” |
| 后端无法连接 | 确认终端一仍在运行、没有启动错误；不要只启动网页 |
| 测试报 UnicodeDecodeError，提示 gbk 无法解码 | 使用第4节带 `-X utf8` 的 Windows 命令；不要把源码改成GBK或删除数据库 |
| 已有 `.env` 但提示缺少配置 | 保留文件，只补齐报错提到的变量；不要把文件或密码发到聊天里 |
| npm 提示“禁止运行脚本” | 使用 Windows 命令中的 `npm.cmd`，不必修改系统执行策略 |
| 提示不认识认证测试参数或缺少登录说明 | 确认自己是否仍在 main；管理员功能要按 `feat/admin-auth` 分支内的说明验证 |

程序、网页和数据库端口只监听本机，不能直接作为公网服务。历史实测和验证范围见 [变更记录](../CHANGELOG.md)。cece 已反馈 Windows 的13项检查和网页构建通过；本次文档修订仍需各系统按实际环境核对，不代表已测试所有工具安装方式。
