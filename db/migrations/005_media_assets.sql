-- A方案门槛验证与后续图片上传共用的元数据定义；已有库须先备份再获准执行。
SET NAMES utf8mb4;
CREATE TABLE media_asset (
  asset_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  item_id BIGINT UNSIGNED NOT NULL,
  created_by BIGINT UNSIGNED NOT NULL,
  storage_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  reference_url VARCHAR(2048) NOT NULL,
  mime_type VARCHAR(32) NOT NULL DEFAULT 'image/webp',
  byte_size INT UNSIGNED NOT NULL DEFAULT 0,
  width INT UNSIGNED DEFAULT NULL,
  height INT UNSIGNED DEFAULT NULL,
  source_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  state ENUM('uploading','pending','attached','retired','deleting') NOT NULL,
  reserved_bytes INT UNSIGNED NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  expires_at DATETIME(6) DEFAULT NULL,
  UNIQUE KEY uk_media_storage (storage_key),
  KEY idx_media_item_state (item_id,state),
  KEY idx_media_expiry (state,expires_at),
  KEY idx_media_creator (created_by,state),
  CONSTRAINT fk_media_item FOREIGN KEY (item_id) REFERENCES item(id),
  CONSTRAINT fk_media_creator FOREIGN KEY (created_by) REFERENCES admin_user(id),
  CONSTRAINT ck_media_size CHECK (byte_size<=8388608 AND reserved_bytes<=8388608),
  CONSTRAINT ck_media_expiry CHECK (expires_at IS NULL OR expires_at>=created_at),
  CONSTRAINT ck_media_complete CHECK (
    state NOT IN ('pending','attached','retired') OR
    (byte_size>0 AND width IS NOT NULL AND width BETWEEN 1 AND 2048 AND
     height IS NOT NULL AND height BETWEEN 1 AND 2048 AND sha256 IS NOT NULL AND
     source_sha256 IS NOT NULL AND mime_type='image/webp')
  ),
  CONSTRAINT ck_media_lifetime CHECK (
    (state='attached' AND expires_at IS NULL) OR (state<>'attached' AND expires_at IS NOT NULL)
  )
) COMMENT='物品自管图片元数据；文件独立持久化，不含上传服务凭证';
