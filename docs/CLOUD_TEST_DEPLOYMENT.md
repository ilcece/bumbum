# 香港云测试：历史手册入口

香港ECS已于2026-10-30释放。原手册全文见[历史归档](archive/cloud-test-deployment.md)，不作为当前部署、恢复或再次释放资源的步骤。当前运维见[杭州手册](HANGZHOU_DEPLOYMENT.md)。deploy/cloud_test模板仍被杭州工具复用，不因手册归档删除目录。

<details>
<summary>旧章节链接兼容入口</summary>

- <a name="1-操作位置与准备"></a> [原章节：1-操作位置与准备](archive/cloud-test-deployment.md#1-操作位置与准备)
- <a name="10-失败时按现象定位"></a> [原章节：10-失败时按现象定位](archive/cloud-test-deployment.md#10-失败时按现象定位)
- <a name="10-手机用户站点公开部署与验收"></a> [原章节：10-手机用户站点公开部署与验收](archive/cloud-test-deployment.md#10-手机用户站点公开部署与验收)
- <a name="101-部署前核对"></a> [原章节：101-部署前核对](archive/cloud-test-deployment.md#101-部署前核对)
- <a name="102-升级及分别发布静态页"></a> [原章节：102-升级及分别发布静态页](archive/cloud-test-deployment.md#102-升级及分别发布静态页)
- <a name="103-用户域名及https"></a> [原章节：103-用户域名及https](archive/cloud-test-deployment.md#103-用户域名及https)
- <a name="104-公网验收与回退"></a> [原章节：104-公网验收与回退](archive/cloud-test-deployment.md#104-公网验收与回退)
- <a name="105-公网部署与整体验收清单按本次实际情况填写"></a> [原章节：105-公网部署与整体验收清单按本次实际情况填写](archive/cloud-test-deployment.md#105-公网部署与整体验收清单按本次实际情况填写)
- <a name="11-服装资料分支的后续部署注意"></a> [原章节：11-服装资料分支的后续部署注意](archive/cloud-test-deployment.md#11-服装资料分支的后续部署注意)
- <a name="12-失败时按现象定位"></a> [原章节：12-失败时按现象定位](archive/cloud-test-deployment.md#12-失败时按现象定位)
- <a name="2-域名与安全组在阿里云控制台操作"></a> [原章节：2-域名与安全组在阿里云控制台操作](archive/cloud-test-deployment.md#2-域名与安全组在阿里云控制台操作)
- <a name="3-安装工具并获取版本回到ecs终端"></a> [原章节：3-安装工具并获取版本回到ecs终端](archive/cloud-test-deployment.md#3-安装工具并获取版本回到ecs终端)
- <a name="4-生成独立配置启动后端和测试库"></a> [原章节：4-生成独立配置启动后端和测试库](archive/cloud-test-deployment.md#4-生成独立配置启动后端和测试库)
- <a name="5-首次配置域名证书"></a> [原章节：5-首次配置域名证书](archive/cloud-test-deployment.md#5-首次配置域名证书)
- <a name="6-安装测试网页和https入口"></a> [原章节：6-安装测试网页和https入口](archive/cloud-test-deployment.md#6-安装测试网页和https入口)
- <a name="7-创建云端管理员并设置手机验证器"></a> [原章节：7-创建云端管理员并设置手机验证器](archive/cloud-test-deployment.md#7-创建云端管理员并设置手机验证器)
- <a name="8-设置nfccool并验证真实扫描"></a> [原章节：8-设置nfccool并验证真实扫描](archive/cloud-test-deployment.md#8-设置nfccool并验证真实扫描)
- <a name="9-日常停止更新备份"></a> [原章节：9-日常停止更新备份](archive/cloud-test-deployment.md#9-日常停止更新备份)
- <a name="91-已有云测试库升级登记来源"></a> [原章节：91-已有云测试库升级登记来源](archive/cloud-test-deployment.md#91-已有云测试库升级登记来源)
- <a name="92-已验收功能分支合入main后切换"></a> [原章节：92-已验收功能分支合入main后切换](archive/cloud-test-deployment.md#92-已验收功能分支合入main后切换)
- <a name="93-已有云测试库升级触碰日志"></a> [原章节：93-已有云测试库升级触碰日志](archive/cloud-test-deployment.md#93-已有云测试库升级触碰日志)
- <a name="a-范围与开始条件"></a> [原章节：a-范围与开始条件](archive/cloud-test-deployment.md#a-范围与开始条件)
- <a name="b-部署与站点基础检查"></a> [原章节：b-部署与站点基础检查](archive/cloud-test-deployment.md#b-部署与站点基础检查)
- <a name="c-管理端隔离与最小权限检查"></a> [原章节：c-管理端隔离与最小权限检查](archive/cloud-test-deployment.md#c-管理端隔离与最小权限检查)
- <a name="d-真实手机端到端验收"></a> [原章节：d-真实手机端到端验收](archive/cloud-test-deployment.md#d-真实手机端到端验收)
- <a name="e-备份重启与恢复验证"></a> [原章节：e-备份重启与恢复验证](archive/cloud-test-deployment.md#e-备份重启与恢复验证)
- <a name="f-结果记录与放行标准"></a> [原章节：f-结果记录与放行标准](archive/cloud-test-deployment.md#f-结果记录与放行标准)
- <a name="日常排查先看请求有没有到达"></a> [原章节：日常排查先看请求有没有到达](archive/cloud-test-deployment.md#日常排查先看请求有没有到达)
- <a name="香港云测试手机扫描电脑查询"></a> [原章节：香港云测试手机扫描电脑查询](archive/cloud-test-deployment.md#香港云测试手机扫描电脑查询)

</details>
