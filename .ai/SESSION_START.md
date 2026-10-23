## AI 会话启动指令
你正在协助开发 BUMBUM NFC 数字项目（含数字服装与数字文创饰品）。请先阅读：
- `README.md`（项目定位与全局约束）
- `PRD.md`（产品需求）
- `TECH_SPEC.md`（技术栈和架构约定）
- `API_CONTRACT.md`（接口契约）
- `db/schema.sql`（数据库唯一事实来源）

规则：
1. 不要更换技术栈（Python 3 + Flask + MySQL + React + Vite）。
2. 不要臆造数据库字段，一切以 `db/schema.sql` 为准。
3. 不要自行修改 `API_CONTRACT.md` 中的字段名；如果发现需要改，先告诉我并说明理由。
4. 生成代码时，标注“需要我修改的地方”（如数据库密码、域名、IP 白名单）。
5. 我是产品经理，不懂代码，请用简洁中文解释关键决策，不要贴大段无关的底层实现。
6. NTAG424 DNA 的 SDM 验证，优先用 `nfc-developer/sdm-backend` 或 `pylibsdm`，不要从零实现 AES-CMAC。
7. SUN URL 的最终模板为 `https://nfc.bumbum.cc/tap?picc_data={picc}&cmac={cmac}`；URL 中不包含 `item_uid`，物品身份由后端解密 `picc_data` 得到的 `chip_uid` 反查。NFC 入口由 Nginx 返回前端 SPA，前端调用 `POST /api/tap/verify`，请求体只含 `picc_data` 和 `cmac`；不要生成 `GET /t/<item_uid>` 或任何依赖路径参数的后端路由。

我当前的任务是：<在这里填入这次要做的事>

