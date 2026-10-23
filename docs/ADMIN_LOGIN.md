# 管理员登录：创建账号、扫码、验证

目标：用你手机已有的 Authenticator 扫码，使用账号、密码和6位验证码登录；刷新仍保持登录，退出后旧登录失效。当前只做登录，不含芯片和物品管理，也不是正式上线步骤。

这一步在 `feat/admin-auth` 分支。可以先完成 main 上的运行检查，再切换分支；不要覆盖自己未提交的修改。以下命令均在仓库根目录执行。

## 1. 准备本机认证配置

先按 [本地运行说明](LOCAL_DEVELOPMENT.md) 准备依赖和测试数据库。已经准备过的，更新本分支的 Python 依赖即可，不删除或重建数据库：

| 系统 | 更新依赖 | 补齐认证配置 |
|---|---|---|
| macOS / Linux | `.venv/bin/python -m pip install -r requirements-dev.txt` | `.venv/bin/python scripts/setup_auth_local.py` |
| Windows PowerShell | `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` | `.venv\Scripts\python.exe scripts\setup_auth_local.py` |

预期看到“本机认证配置已准备”。脚本只补齐 `.env` 中为空的 `STORAGE_ENCRYPTION_KEY`（保护验证器秘密）和 `IP_HASH_KEY`（隐藏日志中的来源），明确本机开发模式，保留原有数据库配置和已有密钥。不创建账号，不生成芯片密钥；生产配置会被拒绝。

账号创建后，要妥善保留本机 `.env`，不要上传或把密钥发给 AI。丢失或随意替换存储密钥，会导致已有验证器秘密无法解开；不能靠再次运行脚本恢复。若后端已运行，准备配置后先重启它，启动命令仍见本地运行说明。

## 2. 创建自己的管理员账号

确认测试数据库已启动，在私密终端执行一条。示例账号是 `cece`，可以换成你自己的账号名：

| 系统 | 命令 |
|---|---|
| macOS / Linux | `.venv/bin/python -m flask --app app:create_app admin create cece` |
| Windows PowerShell | `.venv\Scripts\python.exe -m flask --app app:create_app admin create cece` |

按终端提示操作：

1. 设置12到128个字符的密码，再输一次确认。输入时不显示字符，属于正常情况。
2. 手机打开 Authenticator，选择添加账号并扫描终端二维码。不要截图分享或把二维码贴进聊天；终端窗口过窄时先放大。
3. 回到终端输入手机当前6位验证码。看到“账号已创建”才表示完成；扫码本身不算完成。
4. 等手机切换到**下一组验证码**再到网页登录：设置时用过的那组不能再次登录。

设置确认前中断不会留下可登录账号；同名账号不会被覆盖。二维码和验证码只用于此次设置，不写入普通日志。

## 3. 在网页检查结果

按 [本地运行说明第3节](LOCAL_DEVELOPMENT.md#3-启动后端和网页) 启动后端与网页，打开 **http://localhost:5174**。保持这个地址，不换成 `127.0.0.1` 或其他端口；后台按配置检查网页来源。

| 操作 | 应看到什么 |
|---|---|
| 填账号、密码、当前手机验证码，点登录 | “管理员已登录”和到期时间 |
| 刷新网页 | 仍显示已登录；最长8小时，不因刷新续期 |
| 点退出登录，再刷新 | 回到登录表单 |
| 退出后立刻重复使用刚才成功的验证码 | 登录未通过；等下一组再试 |

登录凭证由浏览器自动保管；不用复制 Cookie 或防冒用口令。验证码必须保留开头的零；手机日期时间应设为自动。

连续5次登录失败会锁15分钟，锁定期间继续尝试不会延长锁期。避免为了检查反复输错。这里已实现账号级限制；按 IP 限制还需部署 Nginx，普通本地 Flask 启动不包含这一层。

## 4. 换手机、丢手机和停用账号

换手机前优先在 Authenticator 中迁移账号。丢失且不能恢复时，由有权限操作服务器的人执行重置；不会从网页跳过验证器。以下命令只针对你有权管理的账号：

| 操作 | macOS / Linux | Windows PowerShell |
|---|---|---|
| 重置验证器 | `.venv/bin/python -m flask --app app:create_app admin reset-totp cece` | `.venv\Scripts\python.exe -m flask --app app:create_app admin reset-totp cece` |
| 停用账号 | `.venv/bin/python -m flask --app app:create_app admin disable cece` | `.venv\Scripts\python.exe -m flask --app app:create_app admin disable cece` |

重置会要求确认，**先停用旧验证器、退出全部登录，再显示新二维码**。中断或验证码确认失败时，账号保持不能登录，重新执行重置完成设置即可；它不改密码，也不会重新启用已停用账号。停用命令同样使全部旧登录失效；当前没有网页恢复、备份码或启用账号功能。

服务器操作结果写入不上传的 `logs/admin-operations.jsonl`，不保存密码、二维码、秘密或验证码。

## 5. 失败时先看什么

| 现象 | 下一步 |
|---|---|
| 提示认证配置或资料未就绪 | 确认完成第1节，并已重启后端；不要随意换已有密钥 |
| 扫码后验证码一直不通过 | 手机开启自动时间，等下一组再试，确认用的是本次二维码对应的账号 |
| 网页提示登录未通过 | 核对账号、密码和当前验证码；确认没有重复用设置或登录成功时的验证码 |
| 提示必须来自允许的管理网页 | 使用 `http://localhost:5174`，核对 `.env` 的 `ADMIN_ORIGIN` 后重启后端 |
| 数据库无法完成操作 | 回到本地运行说明检查 Docker 和数据库；不要删除数据来解决登录问题 |

开发自动检查见 [本地运行说明第4节](LOCAL_DEVELOPMENT.md#4-验证这一小步)。代码检查与合成账号的浏览器验证已经完成；你自己的手机扫码、首次登录和重置操作，仍需按本文人工确认。
