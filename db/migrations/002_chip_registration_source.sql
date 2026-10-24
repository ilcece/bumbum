-- 给已有芯片库增加首次登记来源；只在检查缺少此字段后执行，不重建业务表。
ALTER TABLE chip ADD COLUMN registration_source ENUM('unknown','manual','nfc_cool') NOT NULL DEFAULT 'unknown'
  COMMENT '首次登记来源：历史未知、网页手工、手机扫描；重扫不改写' AFTER chip_uid;
