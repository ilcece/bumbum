-- BUMBUM NFC 数字项目 — 数据库 DDL
-- 当前目标结构的唯一事实来源；仅供空库初始化，不是升级/重复执行脚本。
-- 已部署数据库须经独立迁移、备份和验证；不要为重跑本文件删除已有数据库。
-- MySQL >= 8.0.16（需要实际执行 CHECK）/ utf8mb4 / InnoDB。
-- Phase 2/3 的表是预留结构，不表示功能已实现或未决方案已批准。
SET SESSION time_zone = '+00:00';
SET SESSION default_storage_engine = InnoDB;

CREATE DATABASE IF NOT EXISTS bumbum_digital
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bumbum_digital;

-- ============================================================
-- 1. 项目表
-- ============================================================
CREATE TABLE project (
  id TINYINT UNSIGNED PRIMARY KEY,
  code VARCHAR(32) NOT NULL,
  name VARCHAR(64) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_code (code)
) COMMENT='项目表：fashion / jewelry';

INSERT INTO project (id, code, name) VALUES
  (1, 'fashion', 'NFC数字服装'),
  (2, 'jewelry', 'NFC文创饰品');

-- ============================================================
-- 2. 用户表（跨项目共享，以手机号为核心）
-- ============================================================
CREATE TABLE user (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  phone VARCHAR(20) NOT NULL,
  nickname VARCHAR(64) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_phone (phone)
) COMMENT='用户表，手机号唯一，跨项目共享';

-- ============================================================
-- 3. 物品身份表（跨项目共享）
-- ============================================================
CREATE TABLE item (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  project_id TINYINT UNSIGNED NOT NULL,
  item_uid VARCHAR(32) NOT NULL,
  sku_code VARCHAR(64) DEFAULT NULL,
  status ENUM('draft','active','disabled','archived') NOT NULL DEFAULT 'draft',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_item_uid (item_uid),
  UNIQUE KEY uk_item_project (id, project_id),
  KEY idx_project_status (project_id, status),
  CONSTRAINT fk_item_project FOREIGN KEY (project_id) REFERENCES project(id)
) COMMENT='物品身份表，item_uid 全局唯一';

-- ============================================================
-- 4. 芯片表（chip_uid 全局唯一）
-- ============================================================
CREATE TABLE chip (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  chip_uid VARCHAR(32) NOT NULL,
  project_id TINYINT UNSIGNED NOT NULL,
  item_id BIGINT UNSIGNED DEFAULT NULL,
  chip_status ENUM('pending','bound','disabled','lost') NOT NULL DEFAULT 'pending',
  batch_no VARCHAR(64) DEFAULT NULL,
  provisioned_at DATETIME DEFAULT NULL,
  last_verified_counter BIGINT UNSIGNED DEFAULT NULL COMMENT 'Phase 2：只保存通过CMAC校验的最大计数器',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_chip_uid (chip_uid),
  KEY idx_project_status (project_id, chip_status),
  UNIQUE KEY uk_chip_item (item_id),
  KEY idx_chip_item_project (item_id, project_id),
  CONSTRAINT fk_chip_project FOREIGN KEY (project_id) REFERENCES project(id),
  CONSTRAINT fk_chip_item_project FOREIGN KEY (item_id, project_id) REFERENCES item(id, project_id),
  CONSTRAINT ck_chip_binding CHECK (
    (chip_status <> 'pending' OR item_id IS NULL) AND
    (chip_status <> 'bound' OR item_id IS NOT NULL)
  ),
  CONSTRAINT ck_chip_counter CHECK (last_verified_counter IS NULL OR last_verified_counter <= 16777215)
) COMMENT='NTAG424 DNA 芯片表';

-- ============================================================
-- 5. 芯片密钥表（信封加密存储）
-- ============================================================
CREATE TABLE chip_key (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  chip_id BIGINT UNSIGNED NOT NULL,
  encrypted_keys VARBINARY(2048) NOT NULL COMMENT '5个密钥JSON的AES-GCM密文',
  nonce BINARY(12) NOT NULL COMMENT '数据层AES-GCM nonce；encrypted_keys末尾包含16字节认证标签',
  dek_ciphertext VARBINARY(512) NOT NULL COMMENT '当前为AES-GCM包装的32字节随机DEK，末尾包含16字节认证标签',
  dek_nonce BINARY(12) NOT NULL COMMENT '包装DEK独立生成的AES-GCM nonce',
  storage_key_version VARCHAR(16) NOT NULL DEFAULT 'v1' COMMENT '包装DEK的存储密钥版本，与主密钥版本独立',
  key_version VARCHAR(16) NOT NULL DEFAULT 'v1',
  master_key_version VARCHAR(16) NOT NULL DEFAULT 'v1',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_chip (chip_id),
  CONSTRAINT fk_chipkey_chip FOREIGN KEY (chip_id) REFERENCES chip(id) ON DELETE CASCADE
) COMMENT='芯片槽位密钥，信封加密存储，实际角色待SDM核验';

-- ============================================================
-- 6. 所有权绑定记录（保留历史，最多一条有效绑定）
-- ============================================================
CREATE TABLE ownership (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  bound_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  unbound_at DATETIME DEFAULT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  bind_source ENUM('user_self','admin','import') NOT NULL DEFAULT 'user_self',
  active_item_id BIGINT UNSIGNED GENERATED ALWAYS AS
    (CASE WHEN is_active = 1 THEN item_id ELSE NULL END) STORED,
  UNIQUE KEY uk_ownership_active_item (active_item_id),
  KEY idx_item_active (item_id, is_active),
  KEY idx_user_active (user_id, is_active),
  CONSTRAINT fk_ownership_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_ownership_user FOREIGN KEY (user_id) REFERENCES user(id),
  CONSTRAINT ck_ownership_active CHECK (is_active IN (0, 1)),
  CONSTRAINT ck_ownership_dates CHECK (
    (is_active = 1 AND unbound_at IS NULL) OR
    (is_active = 0 AND unbound_at IS NOT NULL AND unbound_at >= bound_at)
  )
) COMMENT='物品-所有者绑定，历史保留，有效绑定唯一';

-- ============================================================
-- 7. 所有权流转历史
-- ============================================================
CREATE TABLE ownership_history (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  from_user_id BIGINT UNSIGNED DEFAULT NULL COMMENT 'NULL 表示首次绑定',
  to_user_id BIGINT UNSIGNED DEFAULT NULL COMMENT 'NULL 表示解绑',
  action ENUM('bind','unbind','transfer') NOT NULL,
  occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  note VARCHAR(256) DEFAULT NULL,
  KEY idx_item_time (item_id, occurred_at),
  CONSTRAINT fk_history_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_history_from_user FOREIGN KEY (from_user_id) REFERENCES user(id),
  CONSTRAINT fk_history_to_user FOREIGN KEY (to_user_id) REFERENCES user(id),
  CONSTRAINT ck_history_action CHECK (
    (action = 'bind' AND from_user_id IS NULL AND to_user_id IS NOT NULL) OR
    (action = 'unbind' AND from_user_id IS NOT NULL AND to_user_id IS NULL) OR
    (action = 'transfer' AND from_user_id IS NOT NULL AND to_user_id IS NOT NULL AND from_user_id <> to_user_id)
  )
) COMMENT='所有权流转历史';

-- ============================================================
-- 8. SDM 验证日志
-- ============================================================
CREATE TABLE scan_log (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  chip_uid VARCHAR(32) DEFAULT NULL COMMENT '解密失败或无法识别时为空，不伪造UID',
  project_id TINYINT UNSIGNED DEFAULT NULL,
  picc_data VARCHAR(256) DEFAULT NULL,
  cmac VARCHAR(64) DEFAULT NULL,
  scan_counter BIGINT UNSIGNED DEFAULT NULL,
  verify_result ENUM('pass','cmac_fail','decrypt_fail','unknown_chip','replay_suspect','disabled') NOT NULL,
  user_agent VARCHAR(512) DEFAULT NULL,
  ip_hash VARCHAR(64) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  KEY idx_chip_time (chip_uid, created_at),
  KEY idx_verify_result (verify_result),
  KEY idx_project_time (project_id, created_at)
) COMMENT='SDM验证日志，用于防伪审计和异常排查';

-- ============================================================
-- 9. 管理端用户
-- ============================================================
CREATE TABLE admin_user (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  totp_secret_encrypted VARBINARY(2048) DEFAULT NULL COMMENT 'TECH_SPEC定义的完整信封JSON，UTF-8字节',
  totp_enabled TINYINT(1) NOT NULL DEFAULT 0,
  totp_last_step BIGINT UNSIGNED DEFAULT NULL COMMENT '最近一次成功的time step，防重放',
  status ENUM('active','disabled') NOT NULL DEFAULT 'active',
  last_login_at DATETIME DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_username (username)
) COMMENT='管理端用户';

-- ============================================================
-- 10. 管理员操作审计
-- ============================================================
CREATE TABLE admin_audit (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id BIGINT UNSIGNED NOT NULL,
  action VARCHAR(64) NOT NULL,
  target_type VARCHAR(32) DEFAULT NULL,
  target_id VARCHAR(64) DEFAULT NULL,
  detail JSON DEFAULT NULL,
  ip_hash VARCHAR(64) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  KEY idx_admin_time (admin_id, created_at),
  KEY idx_target (target_type, target_id),
  CONSTRAINT fk_audit_admin FOREIGN KEY (admin_id) REFERENCES admin_user(id)
) COMMENT='管理员操作审计';

-- Phase 1：认证状态只在服务端保存摘要；所有消费、锁定更新均须事务化。
CREATE TABLE admin_session (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id BIGINT UNSIGNED NOT NULL,
  token_hash BINARY(32) NOT NULL,
  csrf_token_hash BINARY(32) NOT NULL,
  scope ENUM('enroll','full') NOT NULL,
  expires_at DATETIME NOT NULL,
  revoked_at DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_session_token (token_hash),
  KEY idx_session_admin_expiry (admin_id, expires_at),
  CONSTRAINT fk_session_admin FOREIGN KEY (admin_id) REFERENCES admin_user(id)
) COMMENT='管理员Cookie会话，enroll仅可完成首次TOTP设置';

CREATE TABLE admin_mfa_challenge (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id BIGINT UNSIGNED NOT NULL,
  ticket_hash BINARY(32) NOT NULL,
  expires_at DATETIME NOT NULL,
  used_at DATETIME DEFAULT NULL,
  failed_attempts INT UNSIGNED NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_mfa_ticket (ticket_hash),
  KEY idx_mfa_expiry (expires_at),
  CONSTRAINT fk_mfa_admin FOREIGN KEY (admin_id) REFERENCES admin_user(id)
) COMMENT='密码校验后的5分钟MFA挑战，TOTP或备份码成功后原子消费';

CREATE TABLE admin_backup_code (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id BIGINT UNSIGNED NOT NULL,
  code_hash BINARY(32) NOT NULL,
  used_at DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_backup_admin_code (admin_id, code_hash),
  CONSTRAINT fk_backup_admin FOREIGN KEY (admin_id) REFERENCES admin_user(id)
) COMMENT='每个备份码至少128位随机熵，只存SHA-256摘要，一次性使用';

CREATE TABLE security_rate_limit (
  bucket_key BINARY(32) PRIMARY KEY COMMENT '按用途和账号/IP等规范化标识计算HMAC，不存原始IP或手机号',
  window_started_at DATETIME NOT NULL,
  attempt_count INT UNSIGNED NOT NULL DEFAULT 0,
  locked_until DATETIME DEFAULT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT='登录与Phase 2短信等限流状态，事务锁定桶行后更新';

CREATE TABLE admin_login_event (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id BIGINT UNSIGNED DEFAULT NULL,
  username_hash BINARY(32) DEFAULT NULL,
  result ENUM('password_fail','mfa_fail','locked','success','enroll_required') NOT NULL,
  ip_hash VARCHAR(64) DEFAULT NULL,
  user_agent VARCHAR(512) DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_login_admin_time (admin_id, created_at),
  CONSTRAINT fk_login_admin FOREIGN KEY (admin_id) REFERENCES admin_user(id)
) COMMENT='登录事件，未知账号的失败也可记录，不写密码或验证码';

-- Phase 2预留：不代表SDM选钥与用户身份方案已定稿。
CREATE TABLE tap_grant (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  token_hash BINARY(32) NOT NULL,
  chip_id BIGINT UNSIGNED NOT NULL,
  item_id BIGINT UNSIGNED NOT NULL,
  allowed_action ENUM('read','bind') NOT NULL COMMENT 'touch权限待Phase 3决策后扩展，当前不得签发',
  expires_at DATETIME NOT NULL,
  consumed_at DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_tap_token (token_hash),
  KEY idx_tap_expiry (expires_at),
  CONSTRAINT fk_tap_chip FOREIGN KEY (chip_id) REFERENCES chip(id),
  CONSTRAINT fk_tap_item FOREIGN KEY (item_id) REFERENCES item(id)
) COMMENT='短时触碰授权，只存摘要；read不消费，成功bind事务内消费';

CREATE TABLE sms_challenge (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  tap_grant_id BIGINT UNSIGNED NOT NULL,
  phone VARCHAR(20) NOT NULL,
  code_hash BINARY(32) NOT NULL COMMENT '绑定grant和手机号，用SMS_CODE_HASH_KEY计算HMAC-SHA256',
  failed_attempts INT UNSIGNED NOT NULL DEFAULT 0,
  sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL,
  consumed_at DATETIME DEFAULT NULL,
  KEY idx_sms_grant_phone (tap_grant_id, phone),
  KEY idx_sms_expiry (expires_at),
  CONSTRAINT fk_sms_grant FOREIGN KEY (tap_grant_id) REFERENCES tap_grant(id)
) COMMENT='Phase 2短信挑战，发新码使同grant同手机号旧挑战失效';

-- ============================================================
-- 11. 服装业务表
-- ============================================================
CREATE TABLE fashion_item_profile (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(128) NOT NULL,
  description TEXT,
  material VARCHAR(256) DEFAULT NULL,
  care_instructions TEXT,
  size_chart JSON DEFAULT NULL,
  image_urls JSON DEFAULT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_item_profile (item_id),
  CONSTRAINT fk_fashion_profile_item FOREIGN KEY (item_id) REFERENCES item(id) ON DELETE CASCADE
) COMMENT='服装基础信息';

CREATE TABLE fashion_item_trace (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  stage ENUM('raw_material','manufacturing','quality_check','logistics','retail') NOT NULL,
  event_time DATETIME DEFAULT NULL,
  location VARCHAR(128) DEFAULT NULL,
  operator VARCHAR(128) DEFAULT NULL,
  detail JSON DEFAULT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  KEY idx_item_stage (item_id, stage),
  CONSTRAINT fk_fashion_trace_item FOREIGN KEY (item_id) REFERENCES item(id) ON DELETE CASCADE
) COMMENT='服装溯源信息';

CREATE TABLE fashion_item_story (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  title VARCHAR(256) DEFAULT NULL,
  content MEDIUMTEXT,
  media_urls JSON DEFAULT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  UNIQUE KEY uk_story_item (item_id),
  CONSTRAINT fk_fashion_story_item FOREIGN KEY (item_id) REFERENCES item(id) ON DELETE CASCADE
) COMMENT='品牌故事';

CREATE TABLE fashion_item_channel (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  channel_type ENUM('official_store','authorized_dealer','popup','online','other') NOT NULL,
  channel_name VARCHAR(128) DEFAULT NULL,
  order_no VARCHAR(64) DEFAULT NULL,
  purchased_at DATETIME DEFAULT NULL,
  KEY idx_item_channel (item_id),
  CONSTRAINT fk_fashion_channel_item FOREIGN KEY (item_id) REFERENCES item(id) ON DELETE CASCADE
) COMMENT='购买渠道信息';

-- ============================================================
-- 12. 饰品业务表（养成机制 Phase 3 细化）
-- ============================================================
CREATE TABLE jewelry_item_profile (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(128) NOT NULL,
  description TEXT,
  material VARCHAR(256) DEFAULT NULL,
  meaning TEXT COMMENT '寓意/祈福说明',
  image_urls JSON DEFAULT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_item_profile (item_id),
  CONSTRAINT fk_jewelry_profile_item FOREIGN KEY (item_id) REFERENCES item(id) ON DELETE CASCADE
) COMMENT='饰品基础信息';

CREATE TABLE jewelry_user_progress (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  level INT NOT NULL DEFAULT 1,
  exp INT NOT NULL DEFAULT 0,
  total_taps INT NOT NULL DEFAULT 0,
  last_tap_at DATETIME DEFAULT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_item_user (item_id, user_id),
  CONSTRAINT fk_progress_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_progress_user FOREIGN KEY (user_id) REFERENCES user(id)
) COMMENT='饰品养成进度';

CREATE TABLE jewelry_task (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  description TEXT,
  exp_reward INT NOT NULL DEFAULT 0,
  config JSON DEFAULT NULL,
  status ENUM('active','disabled') NOT NULL DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_task_code (code)
) COMMENT='饰品任务定义（Phase 3 细化）';

CREATE TABLE jewelry_task_record (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  task_id BIGINT UNSIGNED NOT NULL,
  item_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  completed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user_time (user_id, completed_at),
  KEY idx_item_task (item_id, task_id),
  CONSTRAINT fk_taskrecord_task FOREIGN KEY (task_id) REFERENCES jewelry_task(id),
  CONSTRAINT fk_taskrecord_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_taskrecord_user FOREIGN KEY (user_id) REFERENCES user(id)
) COMMENT='饰品任务完成记录';

CREATE TABLE jewelry_reward (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  description TEXT,
  required_level INT NOT NULL DEFAULT 1,
  config JSON DEFAULT NULL,
  status ENUM('active','disabled') NOT NULL DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_reward_code (code)
) COMMENT='饰品奖励定义（Phase 3 细化）';
