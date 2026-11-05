# 新版检查与历史证据

当前执行入口为domain.test.mjs、browser_core.py、browser_whole.py、browser_validation.py、browser_recovery.py、browser_delivery.py；browser_visual.py用于样式专项。浏览器脚本通过正常UI操作，不写入或注入业务会话；为断言读取保存结果。检查使用Playwright与云端Chromium，截图/结果输出到PROTOTYPE_EVIDENCE指定目录。PROTOTYPE_URL可指定多文件构建或独立HTML。

本目录evidence中原53项及其余旧JSON属于旧Make/长经营原型，不代表新版通过。旧脚本和源码由[固定旧版本](https://github.com/ilcece/bumbum/tree/77da310193019f9f99885775e99a6394217c6c00/prototypes/admin-make/checks)保留；不继续运行旧页面脚本累计新版数量。新版结果另以umi-前缀记录，范围见[原型说明](../README.md#原型验证)。

style前缀记录属于2026-11-05按附件进行的样式调整，包含当前单文件视觉、业务回归、保存恢复和资源检查。reference前缀图片只用于视觉对照，不作为当前业务或安全方案。

review前缀为2026-11-05按全部建议和四项补充整改后的当前证据：browser_visual覆盖1320px居中、款图、宽弹窗、多图、复制、详情、状态和配置窗口；core覆盖生成/双链接错误拒绝及完整业务，recovery覆盖保存/未知/离开/来源，delivery覆盖五主页面与单文件资源。旧style前缀不代替本次复审，截图和清单从[设计复审](../design-qa.md)进入。

2026-11-06本轮执行browser_validation.py与现有domain/core检查：覆盖900px抽屉、发行序号无复制、验证开关持久化/新建、各种业务状态直接删除、关联清理和另一侧/审计保留。validation前缀为新证据；旧review/style前缀各自保留原覆盖，不算新清理能力的通过记录。

2026-11-06整套物品调整使用whole前缀：领域20组、整套主线8组、常规主线8组、恢复10组、生产验证7组及最终单HTML五页面检查通过。browser_whole.py覆盖准备整套物品→未知挂失核对→准备转挂失换新→1280确认交付→转售→回看旧换新及统计累计；原新物品ID固定，旧挂失记录与触碰历史保留。未重跑browser_visual.py，也不将其旧结果计入本轮。证据见[设计复审](../design-qa.md#本轮整套物品业务与展示检查)。
