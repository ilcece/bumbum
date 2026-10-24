-- BUMBUM 数据库建表文件（DDL）：定义要保存什么，以及哪些数据不能重复或互相矛盾。
-- cece 阅读方法：先看各表上方的中文用途，再按需要看字段；精确字段名保留给 AI 实现。
-- 一张表保存一类记录；id 是内部编号；带 _id 的字段通常指向另一张表的记录。
-- PRIMARY KEY 是记录的唯一编号；UNIQUE 禁止重复；FOREIGN KEY 检查关联记录是否存在。
-- CHECK 拒绝不符合条件的数据；NULL 表示没有值；ON DELETE CASCADE 表示随关联记录删除。
-- 相关业务流程见 TECH_SPEC.md 第 2 节；保存顺序等精确要求见技术附录第 1 节。
-- 仅用于第一次给空库建表，不是已有数据库的升级脚本，也不能重复运行。
-- 执行前核对连接和数据库内容；已有库要另做升级、备份和验证，不要为重跑而删库。
-- MySQL 至少 8.0.16，确保 CHECK 实际生效；utf8mb4 支持中文，InnoDB 支持关联检查和一起保存。
-- 第二、三阶段的表只是预留，不表示功能已实现，也不表示待确认方案已经获批。
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
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  phone VARCHAR(20) NOT NULL,
  nickname VARCHAR(64) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_phone (phone)
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
  project_id TINYINT UNSIGNED DEFAULT NULL COMMENT '空值表示尚未分配项目，绑定物品时确定',
  item_id BIGINT UNSIGNED DEFAULT NULL,
  chip_status ENUM('pending','bound','disabled','lost') NOT NULL DEFAULT 'pending',
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
-- 7. 流转历史：记录首次绑定 bind、解绑 unbind、转赠 transfer，以及前后所有者。
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
-- 8. 触碰验证记录：用于追查防伪结果和异常；身份尚无法确认时，芯片编号可以为空。
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

-- 第二阶段请求次数限制预留：短信和芯片验证共用数据库计数；第一阶段登录不使用此表。
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

-- 第二阶段预留：全局K1方案已定，实际参数、真实单卡测试和养成身份方案仍待完成。
-- 触碰凭证表：验证通过后临时允许查看或绑定，不证明访问者是登记所有者。
CREATE TABLE tap_grant (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  token_hash BINARY(32) NOT NULL,
  chip_id BIGINT UNSIGNED NOT NULL,
  item_id BIGINT UNSIGNED NOT NULL,
  allowed_action ENUM('read','bind') NOT NULL COMMENT '仅可查看read或绑定bind；增加经验touch须等第三阶段确认，当前不能发放此权限',
  expires_at DATETIME NOT NULL,
  consumed_at DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_tap_token (token_hash),
  KEY idx_tap_expiry (expires_at),
  CONSTRAINT fk_tap_chip FOREIGN KEY (chip_id) REFERENCES chip(id),
  CONSTRAINT fk_tap_item FOREIGN KEY (item_id) REFERENCES item(id)
) COMMENT='短时触碰凭证，只存校验指纹；查看read不标记已用，成功绑定bind时在同一事务内标记已用';

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
  user_id BIGINT UNSIGNED NOT NULL,
  completed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user_time (user_id, completed_at),
  KEY idx_item_task (item_id, task_id),
  CONSTRAINT fk_taskrecord_task FOREIGN KEY (task_id) REFERENCES jewelry_task(id),
  CONSTRAINT fk_taskrecord_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_taskrecord_user FOREIGN KEY (user_id) REFERENCES user(id)
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
