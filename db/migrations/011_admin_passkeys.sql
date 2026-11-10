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
