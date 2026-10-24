-- 只有不存在未分配芯片时才允许回退；scripts/migrate_local.py 会先检查并备份。
-- 不替用户猜项目、不删除记录；已有未分配芯片时停止回退。
ALTER TABLE chip
  DROP FOREIGN KEY fk_chip_project_v2,
  DROP FOREIGN KEY fk_chip_item_project_v2,
  DROP CHECK ck_chip_project_assignment,
  MODIFY COLUMN project_id TINYINT UNSIGNED NOT NULL COMMENT '',
  ADD CONSTRAINT fk_chip_project FOREIGN KEY (project_id) REFERENCES project(id),
  ADD CONSTRAINT fk_chip_item_project FOREIGN KEY (item_id, project_id) REFERENCES item(id, project_id);
