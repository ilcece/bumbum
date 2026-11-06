"""验收批次007升级，复用006的备份和未知结构保护。"""
from pathlib import Path
from core.catalog_migration import CatalogMigrationError, catalog_schema

TABLES={'test_batch','test_batch_object'}

def schema(cursor):
    cursor.execute("SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('test_batch','test_batch_object')")
    cols={}
    for table,column in cursor.fetchall():cols.setdefault(table,set()).add(column)
    if not cols:return 'missing'
    if not {'id','code','status','manifest','deleted_at'}<=cols.get('test_batch',set()) or not {'kind','object_id','batch_id'}<=cols.get('test_batch_object',set()):return 'unknown'
    return 'ready'

def migrate(connection,backup):
    with connection.cursor() as c:
        c.execute("SELECT GET_LOCK('bumbum.test-batches',5)")
        if c.fetchone()[0]!=1:raise CatalogMigrationError('另一个007升级正在进行。')
        try:
            state=schema(c)
            if state=='ready':return False
            if state!='missing' or catalog_schema(c)!='ready':raise CatalogMigrationError('先完成006；部分007结构保留现场，不自动重建。')
            connection.commit();backup()
            sql=(Path(__file__).resolve().parents[1]/'db/migrations/007_test_batches.sql').read_text()
            sql='\n'.join(x for x in sql.splitlines() if not x.lstrip().startswith('--'))
            for statement in sql.split(';'):
                if statement.strip():c.execute(statement)
            connection.commit()
            if schema(c)!='ready':raise CatalogMigrationError('007升级后核对失败，保留备份。')
            return True
        finally:c.execute("SELECT RELEASE_LOCK('bumbum.test-batches')")
