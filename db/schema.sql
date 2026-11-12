-- BUMBUM 数据库建表文件（DDL）：定义要保存什么，以及哪些数据不能重复或互相矛盾。
-- cece 阅读方法：先看各表上方的中文用途，再按需要看字段；精确字段名保留给 AI 实现。
-- 一张表保存一类记录；id 是内部编号；带 _id 的字段通常指向另一张表的记录。
-- PRIMARY KEY 是记录的唯一编号；UNIQUE 禁止重复；FOREIGN KEY 检查关联记录是否存在。
-- CHECK 拒绝不符合条件的数据；NULL 表示没有值；ON DELETE CASCADE 表示随关联记录删除。
-- 相关业务流程见 TECH_SPEC.md 第 2 节；保存顺序等精确要求见技术附录第 1 节。
-- 仅用于第一次给空库建表，不是已有数据库的升级脚本，也不能重复运行。
-- 执行前核对连接和数据库内容；已有库要另做升级、备份和验证，不要为重跑而删库。
-- MySQL 至少 8.0.16，确保 CHECK 实际生效；utf8mb4 支持中文，InnoDB 支持关联检查和一起保存。
-- 阶段表不表示所有功能已实现；触碰验证已接入，短信、认领与养成仍按API_CONTRACT区分。
SET SESSION time_zone = '+00:00';
SET SESSION default_storage_engine = InnoDB;

CREATE DATABASE IF NOT EXISTS bumbum_digital
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bumbum_digital;

-- ============================================================
-- 1. 项目表：区分服装 fashion 和饰品 jewelry。
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
-- 2. 用户表：同一个手机号只登记一次，在服装和饰品项目共用。
-- ============================================================
CREATE TABLE user (
  uid CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  public_uid BINARY(16) NOT NULL,
  phone VARCHAR(20) NOT NULL,
  nickname VARCHAR(64) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_phone (phone),
  UNIQUE KEY uk_user_public_uid (public_uid)
) COMMENT='用户表，手机号唯一，跨项目共享';

-- ============================================================
-- 3. 物品表：每件物品一条记录；业务编号 item_uid 在整个系统中不重复。
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
-- 4. 芯片表：每枚芯片一条记录；最多关联一个同项目物品，物品也最多关联一枚芯片。
-- pending 待绑定；bound 已绑定；disabled 停用；lost 丢失。停用和丢失时保留绑定。
-- 项目可暂不分配；未分配时不能关联物品、记录写卡完成或接受防伪读数。
-- ============================================================
CREATE TABLE chip (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  chip_uid VARCHAR(32) NOT NULL,
  registration_source ENUM('unknown','manual','nfc_cool') NOT NULL DEFAULT 'unknown' COMMENT '首次登记来源：历史未知、网页手工、手机扫描；重扫不改写',
  project_id TINYINT UNSIGNED DEFAULT NULL COMMENT '空值表示尚未分配项目，绑定物品时确定',
  item_id BIGINT UNSIGNED DEFAULT NULL,
  chip_status ENUM('pending','bound','disabled','lost','retired') NOT NULL DEFAULT 'pending',
  batch_no VARCHAR(64) DEFAULT NULL,
  provisioned_at DATETIME DEFAULT NULL,
  last_verified_counter BIGINT UNSIGNED DEFAULT NULL COMMENT '第二阶段：仅保存防伪码CMAC核对通过的最大读取序号',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_chip_uid (chip_uid),
  KEY idx_project_status (project_id, chip_status),
  UNIQUE KEY uk_chip_item (item_id),
  KEY idx_chip_item_project (item_id, project_id),
  CONSTRAINT fk_chip_project_v2 FOREIGN KEY (project_id) REFERENCES project(id),
  CONSTRAINT fk_chip_item_project_v2 FOREIGN KEY (item_id, project_id) REFERENCES item(id, project_id),
  CONSTRAINT ck_chip_binding CHECK (
    (chip_status <> 'pending' OR item_id IS NULL) AND
    (chip_status <> 'bound' OR item_id IS NOT NULL)
  ),
  CONSTRAINT ck_chip_project_assignment CHECK (
    project_id IS NOT NULL OR
    (item_id IS NULL AND provisioned_at IS NULL AND last_verified_counter IS NULL)
  ),
  CONSTRAINT ck_chip_counter CHECK (last_verified_counter IS NULL OR last_verified_counter <= 16777215)
) COMMENT='NTAG424 DNA 芯片表';

-- ============================================================
-- 5. 芯片密钥表：保存加密后的 K0 至 K4，不直接保存可读密钥。
-- 先用临时钥匙 DEK 加密密钥，再用独立存储密钥加密 DEK，这叫信封加密。
-- ============================================================
CREATE TABLE chip_key (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  chip_id BIGINT UNSIGNED NOT NULL,
  encrypted_keys VARBINARY(2048) NOT NULL COMMENT '加密保存K0至K4；K1是对应版本全局密钥的副本，其余按芯片编号UID分别计算；原文格式为JSON',
  nonce BINARY(12) NOT NULL COMMENT '加密密钥数据时新生成的12字节随机数；encrypted_keys末尾含16字节验证标记；使用AES-GCM',
  dek_ciphertext VARBINARY(512) NOT NULL COMMENT '用AES-GCM加密后的32字节随机临时钥匙DEK，末尾含16字节验证标记',
  dek_nonce BINARY(12) NOT NULL COMMENT '加密临时钥匙DEK时独立新生成的12字节随机数，使用AES-GCM，不复用数据层随机数',
  storage_key_version VARCHAR(16) NOT NULL DEFAULT 'v1' COMMENT '加密临时钥匙DEK所用存储密钥的版本，与项目根密钥版本分开',
  key_version VARCHAR(16) NOT NULL DEFAULT 'v1' COMMENT '芯片动态验证SDM的配置版本；初始v1固定对应全局K1的v1',
  master_key_version VARCHAR(16) NOT NULL DEFAULT 'v1' COMMENT '计算K0、K2、K3、K4所用项目根密钥的版本，不代表全局K1版本',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_chip (chip_id),
  CONSTRAINT fk_chipkey_chip FOREIGN KEY (chip_id) REFERENCES chip(id) ON DELETE CASCADE
) COMMENT='芯片槽位密钥，K1同版本全局共享、K2单芯片独立，具体参数待实测';

-- ============================================================
-- 6. 所有权表：记录物品属于谁；同一物品同时最多有一个有效所有者，旧记录保留。
-- active_item_id 只在当前有效时填物品编号，用 UNIQUE 拦住重复有效绑定。
-- ============================================================
CREATE TABLE ownership (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
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
  CONSTRAINT fk_ownership_user FOREIGN KEY (user_id) REFERENCES user(uid),
  CONSTRAINT ck_ownership_active CHECK (is_active IN (0, 1)),
  CONSTRAINT ck_ownership_dates CHECK (
    (is_active = 1 AND unbound_at IS NULL) OR
    (is_active = 0 AND unbound_at IS NOT NULL AND unbound_at >= bound_at)
  )
) COMMENT='物品-所有者绑定，历史保留，有效绑定唯一';

-- ============================================================
-- 7. 流转历史：记录首次绑定 bind、解绑 unbind、转赠 transfer，以及前后所有者。
-- ============================================================
CREATE TABLE ownership_history (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  from_user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL COMMENT 'NULL 表示首次绑定',
  to_user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL COMMENT 'NULL 表示解绑',
  action ENUM('bind','unbind','transfer') NOT NULL,
  occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  note VARCHAR(256) DEFAULT NULL,
  KEY idx_item_time (item_id, occurred_at),
  CONSTRAINT fk_history_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_history_from_user FOREIGN KEY (from_user_id) REFERENCES user(uid),
  CONSTRAINT fk_history_to_user FOREIGN KEY (to_user_id) REFERENCES user(uid),
  CONSTRAINT ck_history_action CHECK (
    (action = 'bind' AND from_user_id IS NULL AND to_user_id IS NOT NULL) OR
    (action = 'unbind' AND from_user_id IS NOT NULL AND to_user_id IS NULL) OR
    (action = 'transfer' AND from_user_id IS NOT NULL AND to_user_id IS NOT NULL AND from_user_id <> to_user_id)
  )
) COMMENT='所有权流转历史';

-- ============================================================
-- 8. 触碰验证记录：用于追查防伪结果和异常；身份尚无法确认时，芯片编号可以为空。
-- ============================================================
CREATE TABLE scan_log (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  chip_uid VARCHAR(32) DEFAULT NULL COMMENT '解密失败或无法识别时为空，不伪造UID',
  project_id TINYINT UNSIGNED DEFAULT NULL,
  picc_data VARCHAR(256) DEFAULT NULL,
  cmac VARCHAR(64) DEFAULT NULL,
  scan_counter BIGINT UNSIGNED DEFAULT NULL,
  verify_result ENUM('pass','cmac_fail','decrypt_fail','unknown_chip','replay_suspect','disabled','not_ready') NOT NULL,
  user_agent VARCHAR(512) DEFAULT NULL,
  ip_hash VARCHAR(64) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  chip_id BIGINT UNSIGNED DEFAULT NULL COMMENT '完整验签后的芯片关联；未验证的候选身份不写入',
  item_id BIGINT UNSIGNED DEFAULT NULL COMMENT '触碰发生时的物品，不随未来换绑迁移历史',
  accepted_counter BIGINT UNSIGNED GENERATED ALWAYS AS (CASE WHEN verify_result='pass' THEN scan_counter ELSE NULL END) STORED,
  UNIQUE KEY uk_scan_accepted (chip_id, accepted_counter),
  KEY idx_scan_success_time (verify_result, created_at),
  KEY idx_scan_project_success (project_id, verify_result, created_at),
  KEY idx_scan_item_success (item_id, verify_result, created_at),
  CONSTRAINT fk_scan_chip FOREIGN KEY (chip_id) REFERENCES chip(id),
  CONSTRAINT fk_scan_item_project FOREIGN KEY (item_id, project_id) REFERENCES item(id, project_id),
  CONSTRAINT ck_scan_pass CHECK (verify_result<>'pass' OR (chip_id IS NOT NULL AND item_id IS NOT NULL AND project_id IS NOT NULL AND chip_uid IS NOT NULL AND scan_counter IS NOT NULL AND scan_counter<16777215)),
  KEY idx_chip_time (chip_uid, created_at),
  KEY idx_verify_result (verify_result),
  KEY idx_project_time (project_id, created_at)
) COMMENT='芯片动态验证SDM的结果记录，用于追查防伪结果和排查异常';

-- ============================================================
-- 9. 管理员账号：保存密码校验值、加密后的验证器秘密和账号状态。
-- ============================================================
CREATE TABLE admin_user (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  totp_secret_encrypted VARBINARY(2048) DEFAULT NULL COMMENT '验证器秘密的两层加密结果，按技术附录第3节完整JSON格式存为UTF-8字节',
  totp_enabled TINYINT(1) NOT NULL DEFAULT 0,
  totp_last_step BIGINT UNSIGNED DEFAULT NULL COMMENT '最近一次通过验证的验证码所属时段；旧时段和同一时段不能再次使用',
  failed_login_attempts INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '密码或验证码连续失败次数；成功或锁定到期后的新尝试先清零',
  locked_until DATETIME DEFAULT NULL COMMENT '连续5次失败后暂锁15分钟；锁定期间不延长时间',
  status ENUM('active','disabled') NOT NULL DEFAULT 'active',
  last_login_at DATETIME DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_username (username)
) COMMENT='管理端用户';

-- ============================================================
-- 10. 管理员操作记录：谁在什么时间对什么对象做了什么，方便事后追查。
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
) COMMENT='管理员关键操作记录，供事后追查';

-- 第一阶段登录会话：账号、密码和验证码全部通过后才创建，没有临时设置权限。
-- 正式登录凭证只保存指纹；随机防冒用口令单独不能登录，可保存原值供页面刷新后取回。
CREATE TABLE admin_session (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id BIGINT UNSIGNED NOT NULL,
  token_hash BINARY(32) NOT NULL,
  csrf_token CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '组件生成的32字节随机口令，以64位小写十六进制保存；独立于登录凭证',
  expires_at DATETIME NOT NULL,
  revoked_at DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_session_token (token_hash),
  KEY idx_session_admin_expiry (admin_id, expires_at),
  CONSTRAINT fk_session_admin FOREIGN KEY (admin_id) REFERENCES admin_user(id)
) COMMENT='密码加Authenticator验证码通过后的登录会话，最长8小时；没有备份码或设置阶段权限';

-- 请求次数表由触碰验证使用，短信仍预留；第一阶段登录不使用此表。
CREATE TABLE security_rate_limit (
  bucket_key BINARY(32) PRIMARY KEY COMMENT '按用途和统一格式的账号或IP等标识，用带秘密的HMAC算法计算指纹；不存原始IP或手机号',
  window_started_at DATETIME NOT NULL,
  attempt_count INT UNSIGNED NOT NULL DEFAULT 0,
  locked_until DATETIME DEFAULT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT='第二阶段短信和芯片验证的请求次数预留；在事务里先锁定对应行再更新，防止同时请求漏计';

-- 登录结果记录：包括未知账号的失败，用于排查异常，不保存密码或验证码。
CREATE TABLE admin_login_event (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id BIGINT UNSIGNED DEFAULT NULL,
  username_hash BINARY(32) DEFAULT NULL,
  result ENUM('failed','locked','success') NOT NULL,
  ip_hash VARCHAR(64) DEFAULT NULL,
  user_agent VARCHAR(512) DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_login_admin_time (admin_id, created_at),
  CONSTRAINT fk_login_admin FOREIGN KEY (admin_id) REFERENCES admin_user(id)
) COMMENT='登录事件，未知账号的失败也可记录，不写密码或验证码';

-- 触碰凭证供查看使用；短信认领及养成接口仍按阶段单独实现和验收。
-- 触碰凭证表：验证通过后临时允许查看或绑定，不证明访问者是登记所有者。
CREATE TABLE tap_grant (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  token_hash BINARY(32) NOT NULL,
  chip_id BIGINT UNSIGNED NOT NULL,
  item_id BIGINT UNSIGNED NOT NULL,
  allowed_action ENUM('read','bind','view') NOT NULL COMMENT 'read及bind为五分钟触碰资格；view仅供浏览器持续查看，成功查询后延长24小时，不允许认领',
  expires_at DATETIME NOT NULL,
  consumed_at DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_tap_token (token_hash),
  KEY idx_tap_expiry (expires_at),
  CONSTRAINT fk_tap_chip FOREIGN KEY (chip_id) REFERENCES chip(id),
  CONSTRAINT fk_tap_item FOREIGN KEY (item_id) REFERENCES item(id)
) COMMENT='触碰与持续查看凭证，只存摘要；read和bind保持五分钟，view仅续只读期限；不证明所有者身份';

-- 短信验证记录：必须同时对应本次触碰凭证、手机号和有效验证码。
CREATE TABLE sms_challenge (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  tap_grant_id BIGINT UNSIGNED NOT NULL,
  phone VARCHAR(20) NOT NULL,
  code_hash BINARY(32) NOT NULL COMMENT '将触碰凭证grant和手机号一起校验，用SMS_CODE_HASH_KEY经HMAC-SHA256计算带秘密的指纹',
  failed_attempts INT UNSIGNED NOT NULL DEFAULT 0,
  sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL,
  consumed_at DATETIME DEFAULT NULL,
  KEY idx_sms_grant_phone (tap_grant_id, phone),
  KEY idx_sms_expiry (expires_at),
  CONSTRAINT fk_sms_grant FOREIGN KEY (tap_grant_id) REFERENCES tap_grant(id)
) COMMENT='第二阶段短信验证；发送新码后，同一触碰凭证grant和手机号的旧验证记录失效';

-- ============================================================
-- 11. 服装资料：基础资料第一阶段使用；来源、故事、渠道的完整编辑功能第三阶段实现。
-- ============================================================
-- 服装基础资料：每件服装一份，保存名称、材质、养护说明、尺码和图片。
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

-- 来源记录：记录原料、生产、质检、物流和零售等阶段，供页面按时间线展示。
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

-- 品牌故事：每件物品一份，保存标题、正文和媒体链接。
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

-- 购买渠道：每件物品可以有多条；公开页面不展示订单号。
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
-- 12. 饰品资料：基础资料第一阶段使用；养成相关表仅预留，第三阶段确认规则后再实现。
-- ============================================================
-- 饰品基础资料：每件饰品一份，保存名称、材质、寓意和图片。
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

-- 养成进度：记录物品与用户的等级、经验和触碰次数；当前不能据此认定访问者身份。
CREATE TABLE jewelry_user_progress (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  level INT NOT NULL DEFAULT 1,
  exp INT NOT NULL DEFAULT 0,
  total_taps INT NOT NULL DEFAULT 0,
  last_tap_at DATETIME DEFAULT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_item_user (item_id, user_id),
  CONSTRAINT fk_progress_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_progress_user FOREIGN KEY (user_id) REFERENCES user(uid)
) COMMENT='饰品养成进度';

-- 任务定义：配置可以做什么任务、完成后得到多少经验，第三阶段细化。
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
) COMMENT='饰品任务定义（第三阶段细化）';

-- 任务完成记录：谁在什么时间对哪件物品完成了哪个任务。
CREATE TABLE jewelry_task_record (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  task_id BIGINT UNSIGNED NOT NULL,
  item_id BIGINT UNSIGNED NOT NULL,
  user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  completed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user_time (user_id, completed_at),
  KEY idx_item_task (item_id, task_id),
  CONSTRAINT fk_taskrecord_task FOREIGN KEY (task_id) REFERENCES jewelry_task(id),
  CONSTRAINT fk_taskrecord_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_taskrecord_user FOREIGN KEY (user_id) REFERENCES user(uid)
) COMMENT='饰品任务完成记录';

-- 奖励定义：配置奖励内容和所需等级，第三阶段细化。
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
) COMMENT='饰品奖励定义（第三阶段细化）';

-- A：自管图片，独立文件与数据库须配套备份；上传接口尚未接入。
-- A方案门槛验证与后续图片上传共用的元数据定义；已有库须先备份再获准执行。
SET NAMES utf8mb4;
CREATE TABLE media_asset (
  asset_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  created_by BIGINT UNSIGNED NOT NULL,
  storage_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  reference_url VARCHAR(2048) NOT NULL,
  mime_type VARCHAR(32) NOT NULL DEFAULT 'image/webp',
  byte_size INT UNSIGNED NOT NULL DEFAULT 0,
  width INT UNSIGNED DEFAULT NULL,
  height INT UNSIGNED DEFAULT NULL,
  source_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  state ENUM('uploading','pending','attached','retired','deleting') NOT NULL,
  reserved_bytes INT UNSIGNED NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  expires_at DATETIME(6) DEFAULT NULL,
  UNIQUE KEY uk_media_storage (storage_key),
  KEY idx_media_item_state (item_id,state),
  KEY idx_media_expiry (state,expires_at),
  KEY idx_media_creator (created_by,state),
  CONSTRAINT fk_media_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_media_creator FOREIGN KEY (created_by) REFERENCES admin_user(id),
  CONSTRAINT ck_media_size CHECK (byte_size<=8388608 AND reserved_bytes<=8388608),
  CONSTRAINT ck_media_expiry CHECK (expires_at IS NULL OR expires_at>=created_at),
  CONSTRAINT ck_media_complete CHECK (
    state NOT IN ('pending','attached','retired') OR
    (byte_size>0 AND width IS NOT NULL AND width BETWEEN 1 AND 2048 AND
     height IS NOT NULL AND height BETWEEN 1 AND 2048 AND sha256 IS NOT NULL AND
     source_sha256 IS NOT NULL AND mime_type='image/webp')
  ),
  CONSTRAINT ck_media_lifetime CHECK (
    (state='attached' AND expires_at IS NULL) OR (state<>'attached' AND expires_at IS NOT NULL)
  )
) COMMENT='物品自管图片元数据；文件独立持久化，不含上传服务凭证';

CREATE TABLE product_style (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 project_id TINYINT UNSIGNED NOT NULL,
 code VARCHAR(64) NOT NULL,
 name VARCHAR(128) NOT NULL,
 description TEXT NULL,
 material VARCHAR(256) NULL,
 care_instructions TEXT NULL,
 specs JSON NOT NULL,
 image_urls JSON NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
 UNIQUE KEY uk_style_code(project_id,code),
 CONSTRAINT fk_style_project FOREIGN KEY(project_id) REFERENCES project(id)
) COMMENT='共用款式资料，不承载发行承诺';
CREATE TABLE style_image (
 asset_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 style_id BIGINT UNSIGNED NOT NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 source_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 content MEDIUMBLOB NOT NULL,
 expires_at DATETIME(6) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_style_image FOREIGN KEY(style_id) REFERENCES product_style(id),
 CONSTRAINT fk_style_image_admin FOREIGN KEY(created_by) REFERENCES admin_user(id),
 CONSTRAINT ck_style_image_size CHECK(OCTET_LENGTH(content) BETWEEN 1 AND 8388608)
) COMMENT='小规模共用款图，随数据库备份，不公开暴露';
CREATE TABLE product_issue (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 style_id BIGINT UNSIGNED NOT NULL,
 name VARCHAR(128) NOT NULL,
 series VARCHAR(128) NULL,
 mode ENUM('fixed','period','unlimited') NOT NULL,
 total INT UNSIGNED NULL,
 starts_at DATETIME NULL,
 ends_at DATETIME NULL,
 counting_rule TEXT NULL,
 description TEXT NOT NULL,
 rights JSON NOT NULL,
 confirmed_at DATETIME(6) NULL,
 sealed_at DATETIME(6) NULL,
 seal_evidence VARCHAR(1000) NULL,
 ever_used BOOLEAN NOT NULL DEFAULT FALSE,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_issue_style FOREIGN KEY(style_id) REFERENCES product_style(id),
 CONSTRAINT ck_issue_total CHECK(total IS NULL OR total>0),
 CONSTRAINT ck_issue_period CHECK(mode<>'period' OR (starts_at IS NOT NULL AND ends_at>starts_at))
) COMMENT='独立发行约定及人工核定结果';
CREATE TABLE digital_item (
 item_id BIGINT UNSIGNED PRIMARY KEY,
 issue_id BIGINT UNSIGNED NULL,
 edition_number INT UNSIGNED NULL,
 sold BOOLEAN NOT NULL DEFAULT FALSE,
 first_sold_at DATETIME(6) NULL,
 sale_evidence VARCHAR(1000) NULL,
 is_validation BOOLEAN NOT NULL DEFAULT FALSE,
 quota_year SMALLINT UNSIGNED NULL,
 quota_used INT UNSIGNED NOT NULL DEFAULT 0,
 quota_review BOOLEAN NOT NULL DEFAULT FALSE,
 UNIQUE KEY uk_digital_edition(issue_id,edition_number),
 CONSTRAINT fk_digital_item FOREIGN KEY(item_id) REFERENCES item(id) ON DELETE CASCADE,
 CONSTRAINT fk_digital_issue FOREIGN KEY(issue_id) REFERENCES product_issue(id),
 CONSTRAINT ck_digital_number CHECK(edition_number IS NULL OR edition_number>0)
) COMMENT='稳定数字身份的发行、售出及验证事实';
CREATE TABLE whole_item (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 item_id BIGINT UNSIGNED NOT NULL,
 chip_id BIGINT UNSIGNED NOT NULL,
 generation INT UNSIGNED NOT NULL,
 spec VARCHAR(256) NOT NULL,
 started_at DATETIME(6) NULL,
 ended_at DATETIME(6) NULL,
 exit_reason VARCHAR(32) NULL,
 lost_at DATETIME(6) NULL,
 loss_evidence VARCHAR(1000) NULL,
 current_item_id BIGINT UNSIGNED GENERATED ALWAYS AS (CASE WHEN ended_at IS NULL THEN item_id ELSE NULL END) STORED,
 UNIQUE KEY uk_whole_current(current_item_id),
 UNIQUE KEY uk_whole_chip(chip_id),
 UNIQUE KEY uk_whole_generation(item_id,generation),
 CONSTRAINT fk_whole_item FOREIGN KEY(item_id) REFERENCES item(id),
 CONSTRAINT fk_whole_chip FOREIGN KEY(chip_id) REFERENCES chip(id) ON DELETE CASCADE
) COMMENT='每代整套物品等于实物加芯片';
CREATE TABLE item_handover (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 item_id BIGINT UNSIGNED NOT NULL,
 source_id BIGINT UNSIGNED NOT NULL,
 target_id BIGINT UNSIGNED NULL,
 chip_id BIGINT UNSIGNED NOT NULL,
 kind ENUM('periodic','loss','resale') NOT NULL,
 generation INT UNSIGNED NOT NULL,
 spec VARCHAR(256) NOT NULL,
 owner_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 recipient_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 prepare_evidence VARCHAR(1000) NOT NULL,
 delivery_evidence VARCHAR(1000) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 completed_at DATETIME(6) NULL,
 pending_item_id BIGINT UNSIGNED GENERATED ALWAYS AS(CASE WHEN completed_at IS NULL THEN item_id ELSE NULL END) STORED,
 pending_chip_id BIGINT UNSIGNED GENERATED ALWAYS AS(CASE WHEN completed_at IS NULL THEN chip_id ELSE NULL END) STORED,
 UNIQUE KEY uk_work_pending_item(pending_item_id),
 UNIQUE KEY uk_work_pending_chip(pending_chip_id),
 CONSTRAINT fk_work_item FOREIGN KEY(item_id) REFERENCES item(id),
 CONSTRAINT fk_work_source FOREIGN KEY(source_id) REFERENCES whole_item(id) ON DELETE CASCADE,
 CONSTRAINT fk_work_target FOREIGN KEY(target_id) REFERENCES whole_item(id) ON DELETE CASCADE,
 CONSTRAINT fk_work_chip FOREIGN KEY(chip_id) REFERENCES chip(id),
 CONSTRAINT fk_work_owner FOREIGN KEY(owner_id) REFERENCES user(uid),
 CONSTRAINT fk_work_recipient FOREIGN KEY(recipient_id) REFERENCES user(uid)
) COMMENT='两段办理记录，固定原新整套物品对应';
CREATE TABLE chip_validation (
 chip_id BIGINT UNSIGNED PRIMARY KEY,
 is_validation BOOLEAN NOT NULL DEFAULT FALSE,
 CONSTRAINT fk_validation_chip FOREIGN KEY(chip_id) REFERENCES chip(id) ON DELETE CASCADE
) COMMENT='芯片生产验证标记';

CREATE TABLE admin_operation (
 request_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 admin_id BIGINT UNSIGNED NOT NULL,
 action VARCHAR(64) NOT NULL,
 payload_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 result JSON NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_operation_admin FOREIGN KEY(admin_id) REFERENCES admin_user(id)
) COMMENT='管理写请求的已提交回执，防止响应丢失后重复办理';

-- 验收数据007：来源与生产验证开关分开；先完整备份，停止写入后执行。
CREATE TABLE test_batch (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 code VARCHAR(64) NOT NULL UNIQUE,
 name VARCHAR(128) NOT NULL,
 status ENUM('active','deleted') NOT NULL DEFAULT 'active',
 manifest JSON NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 deleted_at DATETIME(6) NULL
) COMMENT='测试批次与验收说明，清理后保留摘要';
CREATE TABLE test_batch_object (
 kind ENUM('style','issue','item','chip','user','scan') NOT NULL,
 object_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 batch_id BIGINT UNSIGNED NOT NULL,
 PRIMARY KEY(kind,object_id),
 KEY ix_test_batch(batch_id,kind),
 CONSTRAINT fk_test_batch_object FOREIGN KEY(batch_id) REFERENCES test_batch(id)
) COMMENT='不可由生产验证开关改写的对象来源；业务行删除后仍可追溯';

-- 实体、装配与物品权益；先备份并暂停写入。
CREATE TABLE physical_item (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 physical_uid VARCHAR(64) NOT NULL UNIQUE,
 style_id BIGINT UNSIGNED NOT NULL,
 spec VARCHAR(256) NOT NULL,
 batch_no VARCHAR(64) NULL,
 supplier_serial VARCHAR(128) NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 CONSTRAINT fk_physical_style FOREIGN KEY(style_id) REFERENCES product_style(id)
) COMMENT='具有独立编号的实体物品';
CREATE TABLE digital_item_right (
 item_id BIGINT UNSIGNED NOT NULL,
 kind ENUM('renewal','resale') NOT NULL,
 rule_version VARCHAR(32) NOT NULL,
 PRIMARY KEY(item_id,kind),
 CONSTRAINT fk_right_digital FOREIGN KEY(item_id) REFERENCES digital_item(item_id) ON DELETE CASCADE
) COMMENT='数字物品适用的权益及版本';
ALTER TABLE whole_item
 ADD COLUMN physical_item_id BIGINT UNSIGNED NULL,
 ADD COLUMN installed_at DATETIME(6) NULL,
 ADD COLUMN installed_by BIGINT UNSIGNED NULL,
 ADD COLUMN current_physical_id BIGINT UNSIGNED GENERATED ALWAYS AS (CASE WHEN ended_at IS NULL THEN physical_item_id ELSE NULL END) STORED,
 ADD UNIQUE KEY uk_whole_current_physical(current_physical_id),
 ADD CONSTRAINT fk_whole_physical FOREIGN KEY(physical_item_id) REFERENCES physical_item(id);
ALTER TABLE item_handover
 ADD COLUMN physical_item_id BIGINT UNSIGNED NULL,
 ADD COLUMN installed_at DATETIME(6) NULL,
 ADD COLUMN installed_by BIGINT UNSIGNED NULL,
 ADD COLUMN seller_confirmation VARCHAR(1000) NULL,
 ADD COLUMN recipient_confirmation VARCHAR(1000) NULL,
 ADD COLUMN identity_verification_reference VARCHAR(128) NULL,
 ADD COLUMN quota_year SMALLINT UNSIGNED NULL,
 ADD COLUMN pending_physical_id BIGINT UNSIGNED GENERATED ALWAYS AS (CASE WHEN completed_at IS NULL THEN physical_item_id ELSE NULL END) STORED,
 ADD UNIQUE KEY uk_handover_pending_physical(pending_physical_id),
 ADD KEY ix_handover_quota(item_id,quota_year),
 ADD CONSTRAINT fk_handover_physical FOREIGN KEY(physical_item_id) REFERENCES physical_item(id);
ALTER TABLE user ADD COLUMN phone_verified_at DATETIME(6) NULL;
ALTER TABLE test_batch_object MODIFY kind ENUM('style','issue','item','chip','user','scan','physical') NOT NULL;

-- H5手机号账户会话与一次性认领；凭证仅保存校验摘要。
CREATE TABLE user_session (
 token_hash BINARY(32) PRIMARY KEY,
 user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 expires_at DATETIME(6) NOT NULL,
 revoked_at DATETIME(6) NULL,
 CONSTRAINT fk_user_session_user FOREIGN KEY(user_id) REFERENCES user(uid) ON DELETE CASCADE
) COMMENT='独立于管理端的用户会话';
CREATE TABLE user_sms_challenge (
 phone VARCHAR(20) PRIMARY KEY,
 challenge_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
 code_hash BINARY(32) NOT NULL,
 expires_at DATETIME(6) NOT NULL,
 consumed_at DATETIME(6) NULL,
 failed_attempts TINYINT UNSIGNED NOT NULL DEFAULT 0
) COMMENT='手机号登录的最近一次短信挑战';
CREATE TABLE item_claim_code (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 item_id BIGINT UNSIGNED NOT NULL,
 code_hash BINARY(32) NOT NULL,
 issued_by BIGINT UNSIGNED NOT NULL,
 delivery_reference VARCHAR(128) NOT NULL,
 issued_at DATETIME(6) NOT NULL,
 expires_at DATETIME(6) NOT NULL,
 consumed_at DATETIME(6) NULL,
 revoked_at DATETIME(6) NULL,
 open_item_id BIGINT UNSIGNED GENERATED ALWAYS AS (CASE WHEN consumed_at IS NULL AND revoked_at IS NULL THEN item_id ELSE NULL END) STORED,
 UNIQUE KEY uk_claim_open_item(open_item_id),
 KEY ix_claim_item(item_id),
 CONSTRAINT fk_claim_item FOREIGN KEY(item_id) REFERENCES item(id)
) COMMENT='按实际交付发放或补发的一次性认领码';

-- 通行密钥只保存校验所需的凭据指纹、公钥和计数。
CREATE TABLE admin_passkey (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 admin_id BIGINT UNSIGNED NOT NULL,
 credential_hash BINARY(32) NOT NULL UNIQUE,
 public_key VARBINARY(4096) NOT NULL,
 sign_count BIGINT UNSIGNED NOT NULL,
 created_at DATETIME(6) NOT NULL,
 last_used_at DATETIME(6) NULL,
 revoked_at DATETIME(6) NULL,
 CONSTRAINT fk_passkey_admin FOREIGN KEY(admin_id) REFERENCES admin_user(id) ON DELETE CASCADE
) COMMENT='管理员登记的 WebAuthn 公钥凭据';

CREATE TABLE admin_passkey_challenge (
 challenge_hash BINARY(32) PRIMARY KEY,
 session_id BIGINT UNSIGNED NULL,
 expires_at DATETIME(6) NOT NULL,
 KEY ix_passkey_challenge_expiry(expires_at),
 CONSTRAINT fk_passkey_challenge_session FOREIGN KEY(session_id) REFERENCES admin_session(id) ON DELETE CASCADE
) COMMENT='两分钟单次挑战，登记时绑定管理会话';
