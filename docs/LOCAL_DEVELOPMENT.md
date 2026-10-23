# 本地启动：先确认程序和测试数据库能运行

目标：cece 按步骤启动后，网页显示“后端已启动、测试数据库连接正常”。当前不包含管理员登录、芯片登记、写卡或短信；这不是正式上线步骤。

## 1. 准备工具和目录

需要 Python 3.12、Node.js 24 LTS、Docker Desktop（Linux 可用 Docker Engine + 支持 `--wait` 的 Compose v2）。先启动 Docker，再打开终端，进入包含 README.md 的仓库根目录。下面所有命令都在根目录执行。

检查 `docker compose version` 能显示版本；`node --version` 应为 24.x。Python 在 macOS/Linux 用 `python3 --version`，Windows 用 `py -3.12 --version`。缺少工具时先安装，不需要阿里云密码。

## 2. 首次准备

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/setup_local.py
```

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe scripts\setup_local.py
```

预期看到“本地测试配置已准备好”。脚本只生成本机数据库密码，保存在不上传的 `.env`；已有 `.env` 不覆盖。公开的建表文件会设置为容器可读。其他秘密继续留空。

接着执行，两个系统相同：

```bash
docker compose up -d --wait --wait-timeout 120
npm --prefix frontend/admin ci
```

首次需要下载 MySQL 镜像和网页依赖。数据库就绪后，命令成功退出；如果失败，按第 6 节排查。它在独立容器中创建24张表和服装、饰品两个项目，后端使用普通测试账号，不用数据库管理账号。

## 3. 启动后端和网页

保留两个终端窗口，都在仓库根目录。

**终端一，启动后端：** 按自己的系统选择一条，不需要激活虚拟环境。

| 系统 | 命令 |
|---|---|
| macOS / Linux | `.venv/bin/python -m flask --app app:create_app --no-debug run --host 127.0.0.1 --port 5000` |
| Windows PowerShell | `.venv\Scripts\python.exe -m flask --app app:create_app --no-debug run --host 127.0.0.1 --port 5000` |

看到 `http://127.0.0.1:5000` 后保持窗口运行。直接打开这个地址的首页会显示地址不存在；检查地址是 `/api/health` 和 `/api/ready`。

**终端二，启动网页：**

```bash
npm --prefix frontend/admin run dev
```

在浏览器打开 **http://localhost:5174**。预期两个检查都通过。网页读取真实检查接口，没有模拟“成功”结果；点“重新检查”可再次确认。

## 4. 验证这一小步

再开一个根目录终端，按系统选择命令：

| 检查 | macOS / Linux | Windows PowerShell |
|---|---|---|
| 已运行服务 | `.venv/bin/python scripts/verify_local.py` | `.venv\Scripts\python.exe scripts\verify_local.py` |
| 自动检查 | `.venv/bin/python -m pytest -q` | `.venv\Scripts\python.exe -m pytest -q` |

服务检查应显示两行“通过”；任一失败会以非零状态退出。普通自动检查不要求数据库，真实数据库检查默认显示跳过，不算通过。

需要检查真实 MySQL 时，先确认第 2 步数据库已启动：

```bash
# macOS / Linux
RUN_DB_TESTS=1 .venv/bin/python -m pytest -q
```

```powershell
# Windows PowerShell
$env:RUN_DB_TESTS="1"
.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:RUN_DB_TESTS
```

这会额外确认普通账号连接、UTC 时间设置、完整表清单及数据库就绪接口。检查只接受本机33306端口和测试账号，不写业务数据。

页面代码改过后，执行 `npm --prefix frontend/admin run build`；成功表示类型检查和打包通过，不等于登录或业务功能已经完成。

## 5. 停止和下次继续

在后端和网页各自的终端按 `Ctrl+C`，再执行：

```bash
docker compose stop
```

测试数据会保留。下次先执行 `docker compose up -d --wait --wait-timeout 120`，再按第 3 节启动后端和网页。无需重新安装或重新建表。

`.env` 和数据库卷要配套保留；不要删除配置后重新生成密码，也不要为了重跑建表文件删除已有数据。以后改表要另写升级步骤，修改 schema 不会自动更新现有数据库。

## 6. 常见情况

| 看到什么 | 下一步 |
|---|---|
| 找不到 docker，或无法连接 Docker | 安装并启动 Docker；确认 `docker compose version` 和 `docker info` 成功 |
| 33306、5000 或5174端口被占用 | 先找出自己之前启动的进程并停止；不要结束不认识的服务 |
| 数据库启动失败 | 先重新运行准备脚本，再用 `docker compose ps -a` 查看状态；已有初始化失败的数据不要盲目清空，让 AI 根据隐藏秘密后的错误排查 |
| 后端正常，数据库未就绪 | 确认数据库启动命令已成功、`.env` 与最初初始化使用的账号密码一致；网页点击重新检查 |
| 后端无法连接 | 确认终端一仍在运行、没有启动错误；不要只启动网页 |
| 已有 `.env` 但提示缺少配置 | 保留文件，补齐报错提到的变量；请 AI 协助，不要把文件或密码发到聊天里 |

程序、网页和数据库端口只监听本机，不能直接作为公网服务。当前实测版本及检查结果见 [变更记录](../CHANGELOG.md)；macOS、Windows 和真实部署环境需各自复核。
