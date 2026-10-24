-- 仅将已有芯片的项目改为可空并补充保护，不更改任何已有记录。
-- 通过 scripts/migrate_local.py 先检查、备份再执行；不要重复执行 schema.sql。
-- 单条 ALTER 由 MySQL 8.0 的原子表结构变更保证整体成功或失败。
ALTER TABLE chip
  DROP FOREIGN KEY fk_chip_project,
  DROP FOREIGN KEY fk_chip_item_project,
  MODIFY COLUMN project_id TINYINT UNSIGNED DEFAULT NULL COMMENT '空值表示尚未分配项目，绑定物品时确定',
  ADD CONSTRAINT fk_chip_project_v2 FOREIGN KEY (project_id) REFERENCES project(id),
  ADD CONSTRAINT fk_chip_item_project_v2 FOREIGN KEY (item_id, project_id) REFERENCES item(id, project_id),
  ADD CONSTRAINT ck_chip_project_assignment CHECK (
    project_id IS NOT NULL OR
    (item_id IS NULL AND provisioned_at IS NULL AND last_verified_counter IS NULL)
  );
