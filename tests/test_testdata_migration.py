"""007在真实MySQL中检查备份前置、重复无操作和部分结构保护。"""
import pytest
from core.db import get_database
from core.testdata_migration import schema,migrate
from core.catalog_migration import CatalogMigrationError
pytestmark=pytest.mark.auth_database

def test_007_backup_first_repeat_noop_and_partial_refused(auth_app):
    with auth_app.app_context():
        conn=get_database()
        # 007会重建旧结构；结束时恢复包括010账户引用在内的完整现行DDL。
        # 夹具已清空这两张专属测试表，不能以只补physical枚举代替完整恢复。
        definitions={}
        with conn.cursor() as c:
            assert schema(c)=='ready'
            for table in ('test_batch','test_batch_object'):
                c.execute(f'SELECT COUNT(*) FROM {table}')
                assert c.fetchone()==(0,)
                c.execute(f'SHOW CREATE TABLE {table}')
                definitions[table]=c.fetchone()[1]
        try:
            with conn.cursor() as c:
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
        finally:
            conn.rollback()
            with conn.cursor() as c:
                c.execute('DROP TABLE IF EXISTS test_batch_object')
                c.execute('DROP TABLE IF EXISTS test_batch')
                for table in ('test_batch','test_batch_object'):
                    c.execute(definitions[table])
        assert auth_app.test_client().get('/api/ready').status_code==200
