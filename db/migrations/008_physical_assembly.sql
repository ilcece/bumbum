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
INSERT INTO digital_item_right(item_id,kind,rule_version)
 SELECT d.item_id, 'renewal', 'legacy-issue' FROM digital_item d JOIN product_issue i ON i.id=d.issue_id
 WHERE i.confirmed_at IS NOT NULL AND JSON_CONTAINS(i.rights, '"renewal"');
INSERT INTO digital_item_right(item_id,kind,rule_version)
 SELECT d.item_id, 'resale', 'legacy-issue' FROM digital_item d JOIN product_issue i ON i.id=d.issue_id
 WHERE i.confirmed_at IS NOT NULL AND JSON_CONTAINS(i.rights, '"resale"');
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
