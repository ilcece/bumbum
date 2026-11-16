-- 停止 test 写入并完成数据库与媒体配套备份后执行。
CREATE TABLE IF NOT EXISTS item_recovery_contact (
 ownership_id BIGINT UNSIGNED PRIMARY KEY,
 consent_hash BINARY(32) NOT NULL,
 CONSTRAINT fk_recovery_ownership FOREIGN KEY(ownership_id) REFERENCES ownership(id) ON DELETE CASCADE
) COMMENT='当前持有关系对已验证联系号码的公开同意，只保存指纹';

CREATE TABLE IF NOT EXISTS item_notice_dismissal (
 handover_id BIGINT UNSIGNED PRIMARY KEY,
 CONSTRAINT fk_notice_handover FOREIGN KEY(handover_id) REFERENCES item_handover(id) ON DELETE CASCADE
) COMMENT='交付接收人主动收起该笔完成提示';

ALTER TABLE tap_grant MODIFY COLUMN allowed_action ENUM('read','bind','view','recovery') NOT NULL
 COMMENT 'recovery仅限五分钟找回，其余凭证维持原期限和用途';
