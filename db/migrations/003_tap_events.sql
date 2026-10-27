-- 先停止写入并通过受控入口完成结构、旧记录及备份检查；不重建库。
ALTER TABLE scan_log
  MODIFY COLUMN verify_result ENUM('pass','cmac_fail','decrypt_fail','unknown_chip','replay_suspect','disabled','not_ready') NOT NULL,
  ADD COLUMN chip_id BIGINT UNSIGNED DEFAULT NULL COMMENT '完整验签后的芯片关联；未验证的候选身份不写入',
  ADD COLUMN item_id BIGINT UNSIGNED DEFAULT NULL COMMENT '触碰发生时的物品，不随未来换绑迁移历史',
  ADD COLUMN accepted_counter BIGINT UNSIGNED GENERATED ALWAYS AS (CASE WHEN verify_result='pass' THEN scan_counter ELSE NULL END) STORED,
  ADD UNIQUE KEY uk_scan_accepted (chip_id, accepted_counter),
  ADD KEY idx_scan_success_time (verify_result, created_at),
  ADD KEY idx_scan_project_success (project_id, verify_result, created_at),
  ADD KEY idx_scan_item_success (item_id, verify_result, created_at),
  ADD CONSTRAINT fk_scan_chip FOREIGN KEY (chip_id) REFERENCES chip(id),
  ADD CONSTRAINT fk_scan_item_project FOREIGN KEY (item_id, project_id) REFERENCES item(id, project_id),
  ADD CONSTRAINT ck_scan_pass CHECK (verify_result<>'pass' OR (chip_id IS NOT NULL AND item_id IS NOT NULL AND project_id IS NOT NULL AND chip_uid IS NOT NULL AND scan_counter IS NOT NULL AND scan_counter<16777215));
