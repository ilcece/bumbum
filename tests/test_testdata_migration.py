"""007在真实MySQL中检查备份前置、重复无操作和部分结构保护。"""
import pytest
from core.db import get_database
from core.testdata_migration import schema,migrate
from core.catalog_migration import CatalogMigrationError
pytestmark=pytest.mark.auth_database

def test_007_backup_first_repeat_noop_and_partial_refused(auth_app):
    with auth_app.app_context():
        conn=get_database()
        with conn.cursor() as c:
            assert schema(c)=='ready'
            c.execute('DROP TABLE test_batch_object');c.execute('DROP TABLE test_batch');conn.commit()
        def denied():raise ValueError('测试备份失败')
        with pytest.raises(ValueError):migrate(conn,denied)
        with conn.cursor() as c:assert schema(c)=='missing'
        backups=[];assert migrate(conn,lambda:backups.append(True))
        assert len(backups)==1 and not migrate(conn,lambda:pytest.fail('重复升级不备份'))
        with conn.cursor() as c:
            c.execute('ALTER TABLE test_batch_object RENAME COLUMN batch_id TO unknown_batch')
            assert schema(c)=='unknown'
        with pytest.raises(CatalogMigrationError):migrate(conn,lambda:pytest.fail('部分结构不升级'))
        with conn.cursor() as c:
            c.execute('ALTER TABLE test_batch_object RENAME COLUMN unknown_batch TO batch_id')
            c.execute("ALTER TABLE test_batch_object MODIFY kind ENUM('style','issue','item','chip','user','scan','physical') NOT NULL")
