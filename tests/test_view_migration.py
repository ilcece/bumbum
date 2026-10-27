"""004升级只操作专属临时库，验证先备份、旧凭证保留及恢复。"""

from pathlib import Path
import subprocess

import pytest
import pymysql

from core.db import get_database, view_grant_schema
from core.view_migration import migrate, ViewMigrationError
from scripts import migrate_local as cli
from tests.test_admin_auth import query
from tests.test_admin_chips import logged_in
from tests.test_chip_binding import inventory
from tests.test_chip_keys import keyed
from tests.test_tap_verification import ready, tap

pytestmark=pytest.mark.auth_database
NEW_SQL=Path('db/migrations/004_view_grants.sql').read_text()


@pytest.fixture
def old_views(auth_app):
    with auth_app.app_context():
        connection=get_database()
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE tap_grant MODIFY allowed_action ENUM('read','bind') NOT NULL")
        try:
            yield connection
        finally:
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute(NEW_SQL)


def inspect(connection):
    with connection.cursor() as cursor: return view_grant_schema(cursor)


def test_upgrade_preserves_grant_backup_restore_and_idempotence(auth_app,ready,auth_database,tmp_path):
    data=tap(auth_app,ready).json['data']
    original=query(auth_app,'SELECT * FROM tap_grant')
    with auth_app.app_context():
        connection=get_database()
        with connection.cursor() as cursor: cursor.execute("ALTER TABLE tap_grant MODIFY allowed_action ENUM('read','bind') NOT NULL")
        assert inspect(connection)=='missing'
        assert auth_app.test_client().get('/api/ready').status_code==503
        file=tmp_path/'私有完整备份'/'before.sql'
        command,container=auth_database['TEST_DOCKER_COMMAND'],auth_database['TEST_CONTAINER']
        assert migrate(connection,lambda:cli.backup_database(command,container,file))
        assert inspect(connection)=='ready'
        assert not migrate(connection,lambda:pytest.fail('已完成不能重复备份'))
        connection.commit()
        assert query(auth_app,'SELECT * FROM tap_grant')==original
        with file.open('rb') as source:
            result=subprocess.run([*command,'exec','-i',container,'sh','-c','MYSQL_PWD="$MYSQL_PASSWORD" exec mysql -u "$MYSQL_USER" "$MYSQL_DATABASE"'],stdin=source,capture_output=True,timeout=120)
        assert result.returncode==0,'临时库恢复失败；不显示含秘密的原文'
        connection.rollback()
        assert inspect(connection)=='missing'
        assert query(auth_app,'SELECT * FROM tap_grant')==original
        assert migrate(connection,lambda:None)
        assert auth_app.test_client().get('/api/ready').status_code==200


def test_failed_backup_does_not_change_old_schema(old_views):
    def fail(): raise ViewMigrationError('合成备份失败')
    with pytest.raises(ViewMigrationError,match='备份失败'): migrate(old_views,fail)
    assert inspect(old_views)=='missing'


def test_unknown_enum_refuses_migration(old_views):
    with old_views.cursor() as cursor: cursor.execute("ALTER TABLE tap_grant MODIFY allowed_action ENUM('read','bind','unexpected') NOT NULL")
    assert inspect(old_views)=='unknown'
    with pytest.raises(ViewMigrationError,match='无法识别'): migrate(old_views,lambda:pytest.fail('未知不能备份或升级'))


@pytest.mark.parametrize('apply',[False,True])
def test_local_cli_004_uses_private_default_and_is_repeatable(auth_app,old_views,auth_database,tmp_path,monkeypatch,apply):
    import app as app_module
    monkeypatch.setattr(app_module,'create_app',lambda:auth_app)
    monkeypatch.setattr(cli,'validate_local_config',lambda config:None)
    monkeypatch.setattr(cli,'WINDOWS',True)
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'私有用户目录'))
    monkeypatch.setattr(cli,'local_container',lambda:(auth_database['TEST_DOCKER_COMMAND'],auth_database['TEST_CONTAINER']) if apply else pytest.fail('检查不执行备份'))
    execute=pymysql.cursors.Cursor.execute
    def account(cursor,sql,args=None):
        if sql=='SELECT CURRENT_USER(),@@server_uuid':sql="SELECT 'bumbum_dev@localhost',@@server_uuid"
        return execute(cursor,sql,args)
    monkeypatch.setattr(pymysql.cursors.Cursor,'execute',account)
    monkeypatch.setattr(cli.sys,'argv',['migrate_local.py','--view-grants']+(['--apply'] if apply else []))
    assert cli.main()==0 and inspect(old_views)==('ready' if apply else 'missing')
    folder=tmp_path/'私有用户目录'/'Bumbum'/'backups'
    if apply:
        assert len(list(folder.glob('before-view-grants-*.sql')))==1
        assert cli.main()==0 and len(list(folder.glob('*.sql')))==1
    else: assert not folder.exists()
