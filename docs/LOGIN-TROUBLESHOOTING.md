# 登录500：安全诊断更新

适用：POST /api/admin/login 返回500 INTERNAL_ERROR，且现有日志只有requestId/code。诊断更新不宣称登录问题已经修复；需要下一次失败日志的errorType/errorCode/sites才能定位真实原因。

本次仅新增src/diagnostics.ts，修改src/app.ts错误日志。不会记录异常原文、SQL、请求正文、手机号、密码散列、Cookie或密钥；公开错误响应保持不变。TypeScript编译、2项日志隐私测试和16组隔离MySQL回归测试通过。

## ECS更新（不迁移、不覆盖配置）

1. 从GitHub main重新Download ZIP，在电脑将新包命名为bumbum-diagnostics.zip，上传到/root/bumbum/uploads。不是之前的旧ZIP。
2. 在ECS终端执行下方命令。目标目录已存在时先停下来检查，避免混用旧解压文件。

```bash
cd /root/bumbum
unzip uploads/bumbum-diagnostics.zip -d releases/login-diagnostics
ls -l releases/login-diagnostics/bumbum-main/src/app.ts releases/login-diagnostics/bumbum-main/src/diagnostics.ts
```

两文件都存在才继续；如果ZIP解压根目录不同，以实际find结果为准，不直接复制错误路径。

3. 备份当前应用源码和镜像。以下默认你仍在使用首版镜像bumbum:1.0.0；曾改APP_IMAGE需按实际旧镜像备份。备份文件/标签已存在则保留，不覆盖。

```bash
cp -n src/app.ts releases/app.before-login-diagnostics.ts
if sudo docker image inspect bumbum:before-login-diagnostics >/dev/null 2>&1; then
  echo "保留已有备份镜像"
else
  sudo docker image tag bumbum:1.0.0 bumbum:before-login-diagnostics
fi
cp releases/login-diagnostics/bumbum-main/src/app.ts src/app.ts
cp releases/login-diagnostics/bumbum-main/src/diagnostics.ts src/diagnostics.ts
```

只替换这两个源码文件，不复制.env/.env.migrate/secrets。两源码文件应属于同一新ZIP。

4. 用nano打开.env，只将APP_IMAGE改为bumbum:1.0.1-diagnostics，其他值不改，不分享文件内容。Ctrl+O、回车保存；Ctrl+X退出。

```bash
nano .env
sudo docker compose config --quiet
sudo docker compose build app
sudo docker compose up -d --force-recreate --wait app
```

一条失败先停止排查，不执行后面的命令。构建成功后再重建应用，网站会短暂中断。Caddy/数据库/证书卷保留，不需要执行迁移或重建管理员。

5. 刷新正式HTTPS登录页，只尝试一次，然后：

```bash
sudo docker compose logs --since=5m --tail=50 app
```

新错误日志应包含errorType、可用时的errorCode、sites（源文件及代码行）。把这条日志和浏览器POST登录响应requestId发给维护者。不要分享请求正文、Cookie、密码或完整环境变量。

如果更新后需退回旧应用，将APP_IMAGE改为bumbum:before-login-diagnostics，再docker compose up -d --no-build --force-recreate --wait app。此更新没有数据库迁移。
