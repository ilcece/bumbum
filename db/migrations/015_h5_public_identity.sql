-- 停写并备份后逐段执行。先加列并回填，再约束新旧记录。
ALTER TABLE item
    ADD COLUMN public_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL COMMENT '对外地址用的随机 UUIDv4',
    ADD UNIQUE KEY uk_item_public_id (public_id);
UPDATE item SET public_id=LOWER(CONCAT(HEX(RANDOM_BYTES(4)),'-',HEX(RANDOM_BYTES(2)),'-4',SUBSTR(HEX(RANDOM_BYTES(2)),2),'-',SUBSTR('89ab',1+(ORD(RANDOM_BYTES(1)) & 3),1),SUBSTR(HEX(RANDOM_BYTES(2)),2),'-',HEX(RANDOM_BYTES(6)))), updated_at=updated_at WHERE public_id IS NULL;
ALTER TABLE item MODIFY COLUMN public_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT (LOWER(CONCAT(HEX(RANDOM_BYTES(4)),'-',HEX(RANDOM_BYTES(2)),'-4',SUBSTR(HEX(RANDOM_BYTES(2)),2),'-',SUBSTR('89ab',1+(ORD(RANDOM_BYTES(1)) & 3),1),SUBSTR(HEX(RANDOM_BYTES(2)),2),'-',HEX(RANDOM_BYTES(6))))) COMMENT '对外地址用的随机 UUIDv4';
ALTER TABLE scan_log
    ADD COLUMN actor_state ENUM('anonymous','account') DEFAULT NULL COMMENT '当次验证记录的 H5 账户状态',
    ADD COLUMN actor_user_uid CHAR(36) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL COMMENT '触碰当时已登录的账户',
    ADD CONSTRAINT fk_scan_actor FOREIGN KEY (actor_user_uid) REFERENCES user(uid) ON DELETE SET NULL;
