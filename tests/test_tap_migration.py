"""只在专属临时库检查旧触碰日志升级、完整备份恢复与未知历史拒绝。"""

from pathlib import Path
import re
import subprocess

import pymysql
import pytest

from core.db import get_database, tap_event_schema
from core.tap_migration import migrate, TapMigrationError
from scripts.migrate_local import backup_database
from tests.test_admin_auth import query

pytestmark = pytest.mark.auth_database
ROOT = Path(__file__).resolve().parents[1]
NEW_TABLE = re.search(r'CREATE TABLE scan_log \(.*?\n\).*?;', (ROOT/'db/schema.sql').read_text(), re.S).group()
OLD_TABLE = '''CREATE TABLE scan_log (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 chip_uid VARCHAR(32) DEFAULT NULL,
 project_id TINYINT UNSIGNED DEFAULT NULL,
 picc_data VARCHAR(256) DEFAULT NULL,
 cmac VARCHAR(64) DEFAULT NULL,
 scan_counter BIGINT UNSIGNED DEFAULT NULL,
 verify_result ENUM('pass','cmac_fail','decrypt_fail','unknown_chip','replay_suspect','disabled') NOT NULL,
 user_agent VARCHAR(512) DEFAULT NULL,
 ip_hash VARCHAR(64) DEFAULT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 KEY idx_chip_time(chip_uid,created_at),
 KEY idx_verify_result(verify_result),
 KEY idx_project_time(project_id,created_at)
)'''


def test_new_schema_is_ready(auth_app):
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            observed = tap_event_schema(cursor)
            cursor.execute("SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,GENERATION_EXPRESSION FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='scan_log'")
            columns = cursor.fetchall()
            cursor.execute("SELECT CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND CONSTRAINT_NAME='ck_scan_pass'")
            clause = cursor.fetchall()
            if observed != 'ready':
                pytest.fail('\n'.join(str(row) for row in columns + clause))


@pytest.fixture
def old_taps(auth_app):
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE scan_log')
            cursor.execute(OLD_TABLE)
        try:
            yield connection
        finally:
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute('DROP TABLE scan_log')
                cursor.execute(NEW_TABLE)


def state(connection):
    with connection.cursor() as cursor:
        return tap_event_schema(cursor)


def test_empty_upgrade_complete_backup_restore_and_idempotence(auth_app, admin_account, old_taps, auth_database, tmp_path):
    assert state(old_taps) == 'missing'
    assert auth_app.test_client().get('/api/ready').status_code == 503
    with old_taps.cursor() as cursor:
        cursor.execute("INSERT INTO scan_log(verify_result) VALUES ('decrypt_fail')")
        cursor.execute('SELECT totp_secret_encrypted FROM admin_user')
        original_secret = cursor.fetchone()[0]
    old_taps.commit()
    command, container = auth_database['TEST_DOCKER_COMMAND'], auth_database['TEST_CONTAINER']
    backup = tmp_path/'私有备份'/ 'before.sql'
    assert migrate(old_taps, lambda: backup_database(command, container, backup))
    assert state(old_taps) == 'ready'
    assert auth_app.test_client().get('/api/ready').status_code == 200
    assert not migrate(old_taps, lambda: pytest.fail('已升级不重复备份'))
    with old_taps.cursor() as cursor:
        cursor.execute('SELECT verify_result,item_id FROM scan_log')
        assert cursor.fetchall() == (('decrypt_fail', None),)
    # 仅恢复夹具新建的专属临时数据库，确认备份可读且账号秘密未丢失。
    old_taps.commit()
    with backup.open('rb') as source:
        result = subprocess.run([*command,'exec','-i',container,'sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" exec mysql -u "$MYSQL_USER" "$MYSQL_DATABASE"'], stdin=source,capture_output=True,timeout=120)
    assert result.returncode == 0, '专属临时库恢复未完成；不输出含秘密的数据库原文'
    assert state(old_taps) == 'missing'
    with old_taps.cursor() as cursor:
        cursor.execute('SELECT totp_secret_encrypted FROM admin_user')
        assert cursor.fetchone()[0] == original_secret
    assert migrate(old_taps, lambda: None)


def test_legacy_success_refuses_to_guess_or_delete(old_taps):
    with old_taps.cursor() as cursor:
        cursor.execute("INSERT INTO scan_log(chip_uid,scan_counter,verify_result) VALUES ('04:01:02:03:04:05:06',7,'pass')")
    old_taps.commit()
    with pytest.raises(TapMigrationError, match='缺少当时物品归属'):
        migrate(old_taps, lambda: pytest.fail('拒绝时不执行备份/DDL'))
    assert state(old_taps) == 'missing'
    with old_taps.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM scan_log')
        assert cursor.fetchone()[0] == 1


@pytest.mark.parametrize('phase', ['backup','ddl'])
def test_failed_backup_or_ddl_preserves_old_structure(old_taps, monkeypatch, phase):
    execute = pymysql.cursors.Cursor.execute
    def fail_execute(cursor, sql, args=None):
        if 'ALTER TABLE scan_log' in sql:
            raise pymysql.OperationalError(1205,'合成DDL失败')
        return execute(cursor,sql,args)
    def backup():
        if phase == 'backup': raise OSError('合成备份不可读')
    with monkeypatch.context() as patch:
        if phase == 'ddl': patch.setattr(pymysql.cursors.Cursor,'execute',fail_execute)
        with pytest.raises((OSError,pymysql.OperationalError)):
            migrate(old_taps,backup)
    assert state(old_taps) == 'missing'
    assert migrate(old_taps,lambda: None)


@pytest.mark.parametrize('change', ['constraint','index','column','grouping'])
def test_partial_or_tampered_structure_not_reported_ready(auth_app, old_taps, change):
    assert migrate(old_taps,lambda: None)
    with old_taps.cursor() as cursor:
        cursor.execute({'constraint':'ALTER TABLE scan_log DROP CHECK ck_scan_pass', 'index':'ALTER TABLE scan_log DROP INDEX idx_scan_success_time', 'column':'ALTER TABLE scan_log ADD extra_unrecognized INT NULL', 'grouping':"ALTER TABLE scan_log DROP CHECK ck_scan_pass, ADD CONSTRAINT ck_scan_pass CHECK ((verify_result<>'pass' OR chip_id IS NOT NULL) AND item_id IS NOT NULL AND project_id IS NOT NULL AND chip_uid IS NOT NULL AND scan_counter IS NOT NULL AND scan_counter<16777215)"}[change])
    assert state(old_taps) == 'unknown'
    assert auth_app.test_client().get('/api/ready').status_code == 503
    with pytest.raises(TapMigrationError,match='结构无法识别'):
        migrate(old_taps,lambda: pytest.fail('未知结构不能自动执行'))


@pytest.mark.parametrize('apply', [False, True])
def test_local_cli_uses_correct_schema_and_private_backup(auth_app, old_taps, auth_database, tmp_path, monkeypatch, apply):
    import app as app_module
    from scripts import migrate_local as cli
    monkeypatch.setattr(app_module, 'create_app', lambda: auth_app)
    monkeypatch.setattr(cli, 'validate_local_config', lambda config: None)
    monkeypatch.setattr(cli, 'local_container', lambda: (auth_database['TEST_DOCKER_COMMAND'], auth_database['TEST_CONTAINER']) if apply else pytest.fail('只检查不能检查备份容器或修改结构'))
    execute = pymysql.cursors.Cursor.execute
    def test_account(cursor, sql, args=None):
        if sql == 'SELECT CURRENT_USER(),@@server_uuid':
            sql = "SELECT 'bumbum_dev@localhost',@@server_uuid"
        return execute(cursor, sql, args)
    monkeypatch.setattr(pymysql.cursors.Cursor, 'execute', test_account)
    folder = tmp_path/'私有升级备份'
    arguments = ['migrate_local.py','--tap-events','--backup-dir',str(folder)]
    if apply: arguments.append('--apply')
    monkeypatch.setattr(cli.sys, 'argv', arguments)
    assert cli.main() == 0
    assert state(old_taps) == ('ready' if apply else 'missing')
    if apply:
        files = list(folder.glob('before-tap-events-*.sql'))
        assert len(files) == 1 and b'-- Dump completed on' in files[0].read_bytes()[-512:]
        assert cli.main() == 0
        assert len(list(folder.glob('*.sql'))) == 1
    else:
        assert not folder.exists()
