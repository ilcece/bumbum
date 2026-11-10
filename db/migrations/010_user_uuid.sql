-- 只用于已备份、停写且账户及其引用已经清空的测试库。
ALTER TABLE user_session DROP FOREIGN KEY fk_user_session_user;
ALTER TABLE item_handover DROP FOREIGN KEY fk_work_owner, DROP FOREIGN KEY fk_work_recipient;
ALTER TABLE jewelry_task_record DROP FOREIGN KEY fk_taskrecord_user;
ALTER TABLE jewelry_user_progress DROP FOREIGN KEY fk_progress_user;
ALTER TABLE ownership_history DROP FOREIGN KEY fk_history_from_user, DROP FOREIGN KEY fk_history_to_user,
 DROP CHECK ck_history_action;
ALTER TABLE ownership DROP FOREIGN KEY fk_ownership_user;

ALTER TABLE user DROP PRIMARY KEY, DROP COLUMN id,
 ADD COLUMN uid CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL PRIMARY KEY FIRST,
 ADD COLUMN public_uid BINARY(16) NOT NULL AFTER uid,
 ADD UNIQUE KEY uk_user_public_uid(public_uid);
ALTER TABLE user_session MODIFY user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 ADD CONSTRAINT fk_user_session_user FOREIGN KEY(user_id) REFERENCES user(uid) ON DELETE CASCADE;
ALTER TABLE item_handover MODIFY owner_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 MODIFY recipient_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 ADD CONSTRAINT fk_work_owner FOREIGN KEY(owner_id) REFERENCES user(uid),
 ADD CONSTRAINT fk_work_recipient FOREIGN KEY(recipient_id) REFERENCES user(uid);
ALTER TABLE jewelry_task_record MODIFY user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 ADD CONSTRAINT fk_taskrecord_user FOREIGN KEY(user_id) REFERENCES user(uid);
ALTER TABLE jewelry_user_progress MODIFY user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 ADD CONSTRAINT fk_progress_user FOREIGN KEY(user_id) REFERENCES user(uid);
ALTER TABLE ownership_history
 MODIFY from_user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL COMMENT 'NULL 表示首次绑定',
 MODIFY to_user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL COMMENT 'NULL 表示解绑',
 ADD CONSTRAINT fk_history_from_user FOREIGN KEY(from_user_id) REFERENCES user(uid),
 ADD CONSTRAINT fk_history_to_user FOREIGN KEY(to_user_id) REFERENCES user(uid),
 ADD CONSTRAINT ck_history_action CHECK (
  (action = 'bind' AND from_user_id IS NULL AND to_user_id IS NOT NULL) OR
  (action = 'unbind' AND from_user_id IS NOT NULL AND to_user_id IS NULL) OR
  (action = 'transfer' AND from_user_id IS NOT NULL AND to_user_id IS NOT NULL AND from_user_id <> to_user_id)
 );
ALTER TABLE ownership MODIFY user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 ADD CONSTRAINT fk_ownership_user FOREIGN KEY(user_id) REFERENCES user(uid);
ALTER TABLE test_batch_object MODIFY object_id VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL;
