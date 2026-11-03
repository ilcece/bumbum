"""媒体005在专属MySQL验证完整识别、先备份、拒绝未知结构和旧记录保留。"""

import pytest

from core.db import get_database, media_asset_schema
from core.media_migration import MediaMigrationError, migrate
from scripts import migrate_local as cli
from tests.test_admin_auth import query

pytestmark = pytest.mark.auth_database


def inspect(connection):
    with connection.cursor() as cursor:
        return media_asset_schema(cursor)


@pytest.fixture
def old_media(auth_app):
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE media_asset')
        try:
            yield connection
        finally:
            with connection.cursor() as cursor:
                cursor.execute('DROP TABLE IF EXISTS media_asset')
            migrate(connection, lambda: None)


def test_native_backup_upgrade_preserves_old_rows_and_is_idempotent(auth_app, old_media, auth_database, tmp_path):
    query(auth_app, "INSERT INTO item(project_id,item_uid,sku_code) VALUES (1,'FASH-2026-940001','原款式')")
    before = query(auth_app, 'SELECT id,item_uid,sku_code,status FROM item')
    assert inspect(old_media) == 'missing' and auth_app.test_client().get('/api/ready').status_code == 503
    dump = tmp_path / 'private-backup' / 'before-media.sql'
    assert migrate(old_media, lambda: cli.backup_database(auth_database['TEST_DOCKER_COMMAND'], auth_database['TEST_CONTAINER'], dump))
    assert dump.stat().st_size > 100 and inspect(old_media) == 'ready'
    assert query(auth_app, 'SELECT id,item_uid,sku_code,status FROM item') == before
    assert not migrate(old_media, lambda: pytest.fail('完整结构不应重复备份'))
    assert auth_app.test_client().get('/api/ready').status_code == 200


def test_backup_failure_keeps_missing_table(old_media):
    def fail():
        raise MediaMigrationError('合成备份失败')
    with pytest.raises(MediaMigrationError, match='备份失败'):
        migrate(old_media, fail)
    assert inspect(old_media) == 'missing'


@pytest.mark.parametrize('change', [
    'ALTER TABLE media_asset ADD unexpected INT',
    "ALTER TABLE media_asset MODIFY storage_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL",
    "ALTER TABLE media_asset ALTER COLUMN mime_type SET DEFAULT 'other/type'",
    'ALTER TABLE media_asset ALTER CHECK ck_media_size NOT ENFORCED',
    'ALTER TABLE media_asset DROP INDEX uk_media_storage, ADD UNIQUE KEY uk_media_storage(storage_key(16))',
    'ALTER TABLE media_asset DROP CHECK ck_media_size, ADD CONSTRAINT ck_media_size CHECK(byte_size<=8388608)',
    'ALTER TABLE media_asset DROP FOREIGN KEY fk_media_item, ADD CONSTRAINT fk_media_item_changed FOREIGN KEY(item_id) REFERENCES item(id) ON DELETE CASCADE',
])
def test_unknown_or_weakened_schema_refuses_upgrade(auth_app, old_media, change):
    assert migrate(old_media, lambda: None)
    with old_media.cursor() as cursor:
        cursor.execute(change)
    assert inspect(old_media) == 'unknown' and auth_app.test_client().get('/api/ready').status_code == 503
    with pytest.raises(MediaMigrationError, match='无法完整识别'):
        migrate(old_media, lambda: pytest.fail('未知结构不应启动备份或DDL'))


@pytest.mark.parametrize('apply', [False, True])
def test_local_media_entry_uses_existing_private_backup(auth_app, old_media, auth_database, tmp_path, monkeypatch, apply):
    import app as app_module
    import pymysql
    monkeypatch.setattr(app_module, 'create_app', lambda: auth_app)
    monkeypatch.setattr(cli, 'validate_local_config', lambda _config: None)
    monkeypatch.setattr(cli, 'local_container', lambda: (auth_database['TEST_DOCKER_COMMAND'], auth_database['TEST_CONTAINER']) if apply else pytest.fail('检查不应启动备份'))
    execute = pymysql.cursors.Cursor.execute
    def local_account(cursor, sql, args=None):
        if sql == 'SELECT CURRENT_USER(),@@server_uuid':
            sql = "SELECT 'bumbum_dev@localhost',@@server_uuid"
        return execute(cursor, sql, args)
    monkeypatch.setattr(pymysql.cursors.Cursor, 'execute', local_account)
    monkeypatch.setattr(cli.sys, 'argv', ['migrate_local.py', '--media-assets', '--backup-dir', str(tmp_path / 'private')] + (['--apply'] if apply else []))
    assert cli.main() == 0 and inspect(old_media) == ('ready' if apply else 'missing')
    if apply:
        assert len(list((tmp_path / 'private').glob('before-media-assets-*.sql'))) == 1
        assert cli.main() == 0
        assert len(list((tmp_path / 'private').glob('*.sql'))) == 1
