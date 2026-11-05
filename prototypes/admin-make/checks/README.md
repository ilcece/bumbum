# 新版检查与历史证据

当前执行入口为domain.test.mjs、browser_core.py、browser_recovery.py和browser_delivery.py。浏览器脚本通过正常UI操作，不写入或注入业务会话；为断言读取保存结果。检查使用Playwright与云端Chromium，截图/结果输出到PROTOTYPE_EVIDENCE指定目录。PROTOTYPE_URL可指定多文件构建或独立HTML。

本目录evidence中原53项及其余旧JSON属于旧Make/长经营原型，不代表新版通过。旧脚本和源码由[固定旧版本](https://github.com/ilcece/bumbum/tree/77da310193019f9f99885775e99a6394217c6c00/prototypes/admin-make/checks)保留；不继续运行旧页面脚本累计新版数量。新版结果另以umi-前缀记录，范围见[原型说明](../README.md#原型验证)。
