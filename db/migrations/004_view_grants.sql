-- 仅扩展权限取值；已有read/bind记录、数据和索引保留。调用方须先检查及完整备份。
ALTER TABLE tap_grant MODIFY allowed_action ENUM('read','bind','view') NOT NULL COMMENT 'read及bind为五分钟触碰资格；view仅供浏览器持续查看，成功查询后延长24小时，不允许认领', COMMENT='触碰与持续查看凭证，只存摘要；read和bind保持五分钟，view仅续只读期限；不证明所有者身份';
