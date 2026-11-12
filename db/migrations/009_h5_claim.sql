-- H5手机号账户会话与一次性认领；凭证仅保存校验摘要。
CREATE TABLE user_session (
 token_hash BINARY(32) PRIMARY KEY,
 user_id BIGINT UNSIGNED NOT NULL,
 expires_at DATETIME(6) NOT NULL,
 revoked_at DATETIME(6) NULL,
 CONSTRAINT fk_user_session_user FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE
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
