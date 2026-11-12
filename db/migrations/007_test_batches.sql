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
 object_id BIGINT UNSIGNED NOT NULL,
 batch_id BIGINT UNSIGNED NOT NULL,
 PRIMARY KEY(kind,object_id),
 KEY ix_test_batch(batch_id,kind),
 CONSTRAINT fk_test_batch_object FOREIGN KEY(batch_id) REFERENCES test_batch(id)
) COMMENT='不可由生产验证开关改写的对象来源；业务行删除后仍可追溯';
