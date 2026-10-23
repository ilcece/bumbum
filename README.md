# bumbum
bumbum数字服装


## 12. 多项目架构约定

- 本系统包含两个业务项目：fashion（数字服装）和 jewelry（文创饰品）。
- `core/` 目录存放跨项目共享的模型与逻辑（chip、chip_key、item、ownership、
  ownership_history、scan_log、SDM验证、密钥派生、信封加密）。任何业务模块
  不得重复定义这些模型。
- `fashion/` 和 `jewelry/` 只存放各自项目的业务表和业务 API。
- 新增业务表时，必须通过 `item_id` 外键关联共享的 `item` 表，不得新建独立的
  物品身份表。
- 所有 API 路径以 `/api/` 开头，业务模块的 API 用 `/api/fashion/` 和
  `/api/jewelry/` 前缀隔离。
- 主密钥按项目隔离：`MASTER_KEY_FASHION` 和 `MASTER_KEY_JEWELRY` 分别从
  环境变量读取，派生时按芯片的 project_id 选择。
- NFC 统一入口为 `GET /t/<item_uid>`，在该路由内根据 item 的 project_id
  决定渲染哪个项目的 H5。
