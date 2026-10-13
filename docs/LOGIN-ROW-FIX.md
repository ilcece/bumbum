# 登录限速记录缺失修复

诊断日志TypeError、sites包含app:188:23，对应诊断版编译代码的`let count = a.failures`：数据库没有返回限速记录，代码仍读取其字段。旧`INSERT IGNORE`可能将插入错误降为警告并跳过记录。生产为何插入被忽略尚需SHOW CREATE TABLE/新错误代码确认，不能仅从此日志推断具体约束。

修复使用指定列的INSERT和重复键更新，不吞掉其他插入错误；缺少记录时返回503并保留限速保护，不允许绕过认证。未修改密码、管理员或迁移。已在MySQL8.0重现检查约束下INSERT IGNORE跳过记录的行为，17组集成测试通过。

## ECS最小补丁（无需重新下载ZIP）

在/root/bumbum执行：

```bash
python3 - <<'PY_PATCH'
from pathlib import Path
p=Path('src/app.ts')
s=p.read_text()
old='INSERT IGNORE INTO login_attempts VALUES (?,0,UTC_TIMESTAMP(3))'
new='INSERT INTO login_attempts (attempt_key,failures,window_start) VALUES (?,0,UTC_TIMESTAMP(3)) ON DUPLICATE KEY UPDATE attempt_key=attempt_key'
marker='    let count = a.failures;'
if s.count(old)!=1 or s.count(marker)!=1:
    raise SystemExit('源码版本不匹配或已经更新，未修改文件；请将提示发给维护者。')
Path('.local').mkdir(mode=0o700,exist_ok=True)
backup=Path('.local/app.before-login-row-fix.ts')
if not backup.exists():
    with backup.open('x') as f: f.write(s)
s=s.replace(old,new).replace(marker,'    if (!a) throw fail(503, "LOGIN_LIMITER_UNAVAILABLE", "登录服务暂不可用，请稍后重试");\n'+marker)
p.write_text(s)
print('源码补丁完成；数据库、管理员及配置均未修改。')
PY_PATCH
```

修改.env中APP_IMAGE为bumbum:1.0.2-login，其他内容保持。保留旧bumbum:1.0.1-diagnostics镜像用于回滚，不覆盖旧标签。

```bash
nano .env
sudo docker compose config --quiet
sudo docker compose build app
sudo docker compose up -d --force-recreate --wait app
```

一条失败先停，不执行后面的命令。无需migrate/admin初始化。应用短暂重启，数据库/Caddy证书卷保留。

刷新正式HTTPS页面，尝试一次登录，再查看：

```bash
sudo docker compose logs --since=5m --tail=50 app
```

若仍失败，发送新错误日志/响应代码，并在DMS空白窗口单独选中执行：

```sql
SHOW CREATE TABLE bumbum_mvp.login_attempts;
```

发送表结构，不发送记录、密码、Cookie或.env。不要删表/重置库、关闭限速或盲目移除约束。生产是否恢复需实际登录验证，不以本地测试代替。
