-- 管理后台数字档案升级：先备份并停止管理写入；不猜测旧款式、发行、售出或所有者。
-- 此文件由受控升级工具执行一次；MySQL DDL不作为可回滚事务。
ALTER TABLE chip MODIFY chip_status ENUM('pending','bound','disabled','lost','retired') NOT NULL DEFAULT 'pending';
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
 owner_id BIGINT UNSIGNED NOT NULL,
 recipient_id BIGINT UNSIGNED NOT NULL,
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
 CONSTRAINT fk_work_owner FOREIGN KEY(owner_id) REFERENCES user(id),
 CONSTRAINT fk_work_recipient FOREIGN KEY(recipient_id) REFERENCES user(id)
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
-- 只迁移真实当前绑定；旧规格没有来源，不补造为新规格。挂失时间未知，留空。
INSERT INTO digital_item(item_id) SELECT id FROM item;
INSERT INTO whole_item(item_id,chip_id,generation,spec,started_at,loss_evidence)
 SELECT c.item_id,c.id,1,'历史规格待核对',NULL,IF(c.chip_status='lost','旧芯片挂失事实，时间未记录',NULL)
 FROM chip c WHERE c.item_id IS NOT NULL;
