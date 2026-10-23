-- BUMBUM NFC 数字项目 — 数据库 DDL
-- 唯一事实来源。任何字段调整必须先改本文件，并在 CHANGELOG.md 记录原因。
-- MySQL 8.0 / utf8mb4 / InnoDB

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
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_chip_uid (chip_uid),
  KEY idx_project_status (project_id, chip_status),
  KEY idx_item_id (item_id),
  CONSTRAINT fk_chip_project FOREIGN KEY (project_id) REFERENCES project(id),
  CONSTRAINT fk_chip_item FOREIGN KEY (item_id) REFERENCES item(id) ON DELETE SET NULL
) COMMENT='NTAG424 DNA 芯片表';

-- ============================================================
-- 5. 芯片密钥表（信封加密存储）
-- ============================================================
CREATE TABLE chip_key (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  chip_id BIGINT UNSIGNED NOT NULL,
  encrypted_keys VARBINARY(2048) NOT NULL COMMENT '5个密钥JSON的AES-GCM密文',
  nonce VARBINARY(16) NOT NULL COMMENT 'AES-GCM nonce',
  dek_ciphertext VARBINARY(512) NOT NULL COMMENT 'DEK密文；当前用STORAGE_ENCRYPTION_KEY加密，未来可替换为KMS CiphertextBlob',
  key_version VARCHAR(16) NOT NULL DEFAULT 'v1',
  master_key_version VARCHAR(16) NOT NULL DEFAULT 'v1',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_chip (chip_id),
  CONSTRAINT fk_chipkey_chip FOREIGN KEY (chip_id) REFERENCES chip(id) ON DELETE CASCADE
) COMMENT='芯片5个派生密钥，信封加密存储';

-- ============================================================
-- 6. 当前有效所有权绑定
-- ============================================================
CREATE TABLE ownership (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  bound_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  unbound_at DATETIME DEFAULT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  bind_source ENUM('user_self','admin','import') NOT NULL DEFAULT 'user_self',
  KEY idx_item_active (item_id, is_active),
  KEY idx_user_active (user_id, is_active),
  CONSTRAINT fk_ownership_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_ownership_user FOREIGN KEY (user_id) REFERENCES user(id)
) COMMENT='当前有效的物品-所有者绑定';

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
  CONSTRAINT fk_history_item FOREIGN KEY (item_id) REFERENCES item(id)
) COMMENT='所有权流转历史';

-- ============================================================
-- 8. SDM 验证日志
-- ============================================================
CREATE TABLE scan_log (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  chip_uid VARCHAR(32) NOT NULL,
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
  totp_secret_encrypted VARBINARY(512) DEFAULT NULL,
  totp_enabled TINYINT(1) NOT NULL DEFAULT 0,
  totp_last_step BIGINT UNSIGNED DEFAULT NULL COMMENT '最近一次成功的time step，防重放',
  backup_codes_encrypted VARBINARY(4096) DEFAULT NULL COMMENT '一次性备份码，信封加密',
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
