# API_CONTRACT.md — BUMBUM NFC 数字项目接口契约

> 本文件是前后端唯一接口事实来源。后端按此生成路由，前端按此拼装参数。任何一方不得自行变更字段名或结构；如需变更，先改本文件并在 `CHANGELOG.md` 记录原因。

---

## 0. 通用约定

### 0.1 基础路径

- 生产环境：两个前端各自同域调用 `/api/`，由 Nginx 反代到 Flask。
- 开发环境：`VITE_API_BASE_URL=http://localhost:5000`。

### 0.2 返回结构

成功：
```json
{ "status": "ok", "data": { ... } }
```

失败：
```json
{ "status": "error", "code": "ERROR_CODE", "message": "人类可读的说明" }
```

### 0.3 认证

- 管理端接口（`/api/admin/*`）需要 `Authorization: Bearer <admin_session_token>`。
- Webhook 接口（`/api/webhook/*`）需要 `Authorization: Basic <base64(shared_secret:)>` 或 URL 参数 `?token=<WEBHOOK_SHARED_SECRET>`。
- 用户触碰验证接口（`/api/tap/verify`）不需要登录。
- 验证成功后的业务操作（绑定手机号、饰品养成）需要携带 `tap_token`。

### 0.4 tap_token 机制

`POST /api/tap/verify` 验证成功后，返回一次性、短时效（默认 5 分钟）的 `tap_token`。后续 `/api/public/bind`、`/api/jewelry/items/{item_id}/touch` 必须携带该 token。服务端校验 token 与 `chip_uid`、`item_id` 的绑定关系，防止直接刷接口。

### 0.5 时间与分页

- 时间统一 ISO 8601 UTC，如 `2026-10-23T08:00:00Z`。
- 列表分页：`?page=1&page_size=20`，返回 `{ "items": [...], "total": 100, "page": 1, "page_size": 20 }`。

---

## 1. Webhook 与用户触碰

### 1.1 `POST /api/webhook/admin/scan`

接收 NFC.cool 管理员扫描，自动登记芯片 UID。**必须快速返回 200**，不做耗时操作。

请求头：
```
Authorization: Basic <base64(WEBHOOK_SHARED_SECRET:)>
Content-Type: application/json
```

请求体（NFC.cool 原始负载）：
```json
{
  "identifier": "04:A2:7F:1B:5E:80:00",
  "content": "https://nfc.bumbum.cc/tap?picc_data=...&cmac=...",
  "date": "2026-10-23T08:00:00Z"
}
```

行为：
- 用 `identifier` 作为 `chip_uid`。
- 若 `chip` 表不存在该 UID，插入一条 `chip_status='pending'` 的记录；`project_id` 由请求参数 `?project=fashion|jewelry` 指定，缺省 `fashion`。
- 若已存在，不修改状态，直接返回。

成功 200：
```json
{ "status": "ok", "data": { "chip_uid": "04:A2:7F:1B:5E:80:00", "is_new": true } }
```

错误：
- `401`：鉴权失败。
- `400`：缺少 `identifier`。

### 1.2 `POST /api/tap/verify`

用户触碰后，前端提交 `picc_data` 和 `cmac`。**请求体只含这两个字段，不含 `item_uid`。**

请求体：
```json
{ "picc_data": "FDE4AFA99B5C820A2C1BB0F1C792D0EB", "cmac": "C48B89C17A233B2C" }
```

行为：
1. 用 `sdm-backend` / `pylibsdm` 解密 `picc_data`，得到 `chip_uid` 和 `scan_counter`。
2. 查 `chip` → `item` → `project`；芯片不存在返回 `unknown_chip`。
3. 校验 `cmac`；失败返回 `cmac_fail`。
4. 校验 `scan_counter` 大于该芯片上次记录；否则 `replay_suspect`。
5. 写 `scan_log`。
6. 生成一次性 `tap_token`（有效期 5 分钟），与 `chip_uid`、`item_id` 绑定。

成功 200（服装）：
```json
{
  "status": "ok",
  "data": {
    "verified": true,
    "project": "fashion",
    "item_id": 12,
    "item_uid": "FASH-2026-000012",
    "owner_bound": false,
    "tap_token": "t_xxx",
    "item_detail": {
      "name": "2026 春夏系列外套",
      "description": "...",
      "image_urls": ["..."],
      "trace": [],
      "story": {},
      "channel": {}
    }
  }
}
```

成功 200（饰品）：
```json
{
  "status": "ok",
  "data": {
    "verified": true,
    "project": "jewelry",
    "item_id": 21,
    "item_uid": "JEW-2026-000021",
    "owner_bound": true,
    "tap_token": "t_xxx",
    "item_detail": {
      "name": "祈福手串",
      "meaning": "...",
      "image_urls": ["..."]
    },
    "progress": { "level": 3, "exp": 120, "total_taps": 30 }
  }
}
```

失败 200（仍返回 200，由 `verified` 区分）：
```json
{
  "status": "ok",
  "data": {
    "verified": false,
    "reason": "cmac_fail",
    "message": "防伪验证未通过"
  }
}
```

> 注意：验证失败也返回 HTTP 200，方便前端统一处理；`reason` 取值：`cmac_fail` / `decrypt_fail` / `unknown_chip` / `replay_suspect` / `disabled`。

### 1.3 `POST /api/public/sms/send`

发送绑定手机号的短信验证码。需要 `tap_token`。

请求体：
```json
{ "phone": "13800138000", "tap_token": "t_xxx" }
```

成功 200：
```json
{ "status": "ok", "data": { "sent": true, "expires_in": 300 } }
```

限流：同一手机号 60 秒内只能发一次；同一 IP 每小时最多 10 次。

### 1.4 `POST /api/public/bind`

用户提交手机号 + 短信验证码，绑定物品所有者。需要 `tap_token`。

请求体：
```json
{ "phone": "13800138000", "sms_code": "123456", "tap_token": "t_xxx" }
```

行为：
- 校验 `tap_token` 有效且与当前 `item_id` 匹配。
- 校验短信验证码。
- 若 `user` 表无此手机号，创建用户。
- 若该物品已有 `is_active=1` 的 `ownership`，返回 `already_bound`。
- 写入 `ownership` 和 `ownership_history(action='bind')`。

成功 200：
```json
{ "status": "ok", "data": { "item_id": 12, "user_id": 5, "bound": true } }
```

错误码：`invalid_tap_token` / `invalid_sms_code` / `already_bound` / `sms_rate_limited`。

---

## 2. 管理端认证

### 2.1 `POST /api/admin/auth/login`

请求体：
```json
{ "username": "cece", "password": "..." }
```

行为：
- 密码正确且该管理员未启用 TOTP：直接签发 `admin_session_token`，返回 `totp_required: false`。
- 密码正确且已启用 TOTP：返回 `totp_required: true` 和临时 `mfa_ticket`（5 分钟），不签发正式会话。

成功 200：
```json
{ "status": "ok", "data": { "totp_required": true, "mfa_ticket": "m_xxx" } }
```

或：
```json
{ "status": "ok", "data": { "totp_required": false, "admin_session_token": "s_xxx", "expires_in": 28800 } }
```

### 2.2 `POST /api/admin/auth/totp/verify`

请求体：
```json
{ "mfa_ticket": "m_xxx", "code": "123456" }
```

成功 200：
```json
{ "status": "ok", "data": { "admin_session_token": "s_xxx", "expires_in": 28800 } }
```

错误码：`invalid_mfa_ticket` / `invalid_totp_code` / `totp_replay` / `rate_limited`。

### 2.3 `POST /api/admin/auth/totp/setup`

需要已登录（`Authorization: Bearer`）。

成功 200：
```json
{ "status": "ok", "data": { "provisioning_uri": "otpauth://totp/...", "secret": "BASE32..." } }
```

前端用二维码组件展示 `provisioning_uri`。

### 2.4 `POST /api/admin/auth/totp/enable`

请求体：
```json
{ "code": "123456" }
```

确认绑定，返回一次性备份码（只展示一次）：
```json
{ "status": "ok", "data": { "enabled": true, "backup_codes": ["a1b2c3", "..."] } }
```

### 2.5 `POST /api/admin/auth/logout`

需要已登录。销毁会话。

---

## 3. 管理端芯片

### 3.1 `GET /api/admin/chips`

查询参数：`?page=1&page_size=20&project=fashion&status=pending&keyword=04:A2`

返回：
```json
{
  "status": "ok",
  "data": {
    "items": [
      {
        "id": 1,
        "chip_uid": "04:A2:7F:1B:5E:80:00",
        "project": "fashion",
        "chip_status": "pending",
        "item_id": null,
        "item_uid": null,
        "batch_no": "B202610",
        "created_at": "2026-10-23T08:00:00Z"
      }
    ],
    "total": 1, "page": 1, "page_size": 20
  }
}
```

**不返回密钥明文。**

### 3.2 `GET /api/admin/chips/{id}`

单芯片详情，含绑定物品、所有权摘要。不返回密钥明文。

### 3.3 `POST /api/admin/chips/{id}/generate-keys`

为该芯片派生 K0–K4，信封加密后写入 `chip_key`。若已存在，返回 `already_exists`，除非带 `?force=true`（重新派生会覆盖，需二次确认）。

成功 200：
```json
{ "status": "ok", "data": { "chip_id": 1, "generated": true, "key_version": "v1" } }
```

### 3.4 `GET /api/admin/chips/{id}/keys`

查看密钥明文（用于手动写卡）。**必须二次确认**：请求体带 `{"confirm": true}`，并写入 `admin_audit`。

成功 200：
```json
{
  "status": "ok",
  "data": {
    "chip_uid": "04:A2:7F:1B:5E:80:00",
    "keys": { "K0": "...", "K1": "...", "K2": "...", "K3": "...", "K4": "..." },
    "sun_url_template": "https://nfc.bumbum.cc/tap?picc_data={picc}&cmac={cmac}"
  }
}
```

### 3.5 `PATCH /api/admin/chips/{id}/status`

请求体：`{ "chip_status": "disabled" }`。允许值：`pending` / `bound` / `disabled` / `lost`。

### 3.6 `POST /api/admin/chips/{id}/bind-item`

请求体：`{ "item_id": 12 }`。将 `pending` 芯片绑定到物品，芯片状态改为 `bound`。一个物品最多绑定一枚芯片；若物品已有芯片，返回 `item_already_has_chip`。

### 3.7 `POST /api/admin/chips/{id}/unbind-item`

解除芯片与物品的绑定，芯片状态回到 `pending`。

---

## 4. 管理端物品

### 4.1 `GET /api/admin/items`

查询参数：`?page=1&page_size=20&project=fashion&status=active&keyword=FASH-2026`。

### 4.2 `POST /api/admin/items`

请求体：
```json
{
  "project": "fashion",
  "item_uid": "FASH-2026-000012",
  "sku_code": "SKU-2026-012",
  "status": "draft"
}
```

### 4.3 `GET /api/admin/items/{id}`

返回物品主表 + 对应项目的 profile（fashion 或 jewelry）。

### 4.4 `PATCH /api/admin/items/{id}`

可更新 `sku_code`、`status`。`item_uid` 和 `project_id` 不允许修改。

### 4.5 `GET /api/admin/items/{id}/profile`

返回对应项目的 profile 详情。

### 4.6 `PUT /api/admin/items/{id}/profile`

请求体按项目不同：
- fashion：`name`、`description`、`material`、`care_instructions`、`size_chart`、`image_urls`。
- jewelry：`name`、`description`、`material`、`meaning`、`image_urls`。

### 4.7 `GET /api/admin/items/{id}/trace` / `PUT /api/admin/items/{id}/trace`

仅 fashion。`PUT` 接收数组，整体替换该物品的溯源记录。

### 4.8 `GET /api/admin/items/{id}/story` / `PUT /api/admin/items/{id}/story`

仅 fashion。

### 4.9 `GET /api/admin/items/{id}/channel` / `PUT /api/admin/items/{id}/channel`

仅 fashion。`PUT` 接收数组。

---

## 5. 管理端所有权

### 5.1 `GET /api/admin/ownerships`

查询参数：`?page=1&page_size=20&item_id=12&user_phone=138&is_active=1`。

### 5.2 `POST /api/admin/ownerships`

管理员手动绑定。请求体：`{ "item_id": 12, "phone": "13800138000", "note": "线下活动" }`。写入 `ownership` + `ownership_history(action='bind', bind_source='admin')`。

### 5.3 `POST /api/admin/ownerships/{id}/unbind`

解绑。写入 `ownership_history(action='unbind')`。

### 5.4 `POST /api/admin/ownerships/{id}/transfer`

转赠。请求体：`{ "to_phone": "13900139000", "note": "转赠" }`。写入 `ownership_history(action='transfer')`。

---

## 6. 服装用户侧

### 6.1 `GET /api/fashion/items/{item_id}/detail`

用户侧 H5 获取服装详情。需要 `tap_token`（由 `/api/tap/verify` 返回）作为 query 参数 `?tap_token=t_xxx`。

返回：
```json
{
  "status": "ok",
  "data": {
    "item_uid": "FASH-2026-000012",
    "profile": { "name": "...", "description": "...", "image_urls": ["..."] },
    "trace": [],
    "story": {},
    "channel": {},
    "owner_bound": false
  }
}
```

---

## 7. 饰品用户侧

### 7.1 `GET /api/jewelry/items/{item_id}/detail`

用户侧 H5 获取饰品详情。需要 `tap_token`。

### 7.2 `GET /api/jewelry/items/{item_id}/progress`

需要 `tap_token`。返回当前用户的养成进度。

### 7.3 `POST /api/jewelry/items/{item_id}/touch`

用户触碰后的养成动作（增加经验、记录任务）。需要 `tap_token`。

请求体：
```json
{ "tap_token": "t_xxx" }
```

行为：
- 校验 `tap_token` 与 `item_id` 匹配且未使用。
- 检查冷却时间（如 1 小时内只能加一次经验）。
- 增加 `exp`、`total_taps`，更新 `last_tap_at`。
- 返回最新进度。

成功 200：
```json
{ "status": "ok", "data": { "level": 3, "exp": 130, "total_taps": 31, "cooldown_seconds": 0 } }
```

---

## 8. 错误码总表

| code | 含义 |
|---|---|
| `unauthorized` | 缺少或无效的认证 |
| `forbidden` | 无权限 |
| `not_found` | 资源不存在 |
| `invalid_param` | 参数缺失或格式错误 |
| `already_exists` | 资源已存在 |
| `already_bound` | 物品已绑定所有者 |
| `item_already_has_chip` | 物品已绑定其他芯片 |
| `invalid_tap_token` | tap_token 无效、过期或与 item 不匹配 |
| `invalid_sms_code` | 短信验证码错误或过期 |
| `sms_rate_limited` | 短信发送过于频繁 |
| `invalid_totp_code` | TOTP 验证码错误 |
| `totp_replay` | TOTP 验证码已使用过 |
| `rate_limited` | 请求过于频繁 |
| `webhook_auth_failed` | Webhook 鉴权失败 |
| `internal_error` | 服务器内部错误 |
