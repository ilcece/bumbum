"""识别账户主键与外键，仅在已清空并备份的测试数据上切换结构。"""

from pathlib import Path

from core.assembly_migration import schema as assembly_schema
from core.catalog_migration import CatalogMigrationError


REFERENCES = {
    ('user_session', 'user_id'),
    ('item_handover', 'owner_id'),
    ('item_handover', 'recipient_id'),
    ('jewelry_task_record', 'user_id'),
    ('jewelry_user_progress', 'user_id'),
    ('ownership_history', 'from_user_id'),
    ('ownership_history', 'to_user_id'),
    ('ownership', 'user_id'),
}


def schema(cursor):
    cursor.execute("""SELECT COLUMN_NAME,COLUMN_TYPE,COLLATION_NAME
                      FROM information_schema.COLUMNS
                      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='user' AND COLUMN_KEY='PRI'""")
    primary = set(cursor.fetchall())
    cursor.execute("""SELECT TABLE_NAME,COLUMN_NAME,REFERENCED_COLUMN_NAME
                      FROM information_schema.KEY_COLUMN_USAGE
                      WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME='user'""")
    refs = set(cursor.fetchall())
    cursor.execute("""SELECT COLUMN_TYPE,COLLATION_NAME FROM information_schema.COLUMNS
                      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='test_batch_object' AND COLUMN_NAME='object_id'""")
    batch_key = cursor.fetchone()
    cursor.execute("""SELECT COLUMN_TYPE,IS_NULLABLE FROM information_schema.COLUMNS
                      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='user' AND COLUMN_NAME='public_uid'""")
    public_uid = cursor.fetchone()
    cursor.execute("""SELECT INDEX_NAME FROM information_schema.STATISTICS
                      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='user' AND NON_UNIQUE=0
                      GROUP BY INDEX_NAME HAVING COUNT(*)=1 AND MIN(COLUMN_NAME)='public_uid'""")
    public_unique = bool(cursor.fetchone())
    if (primary == {('uid','char(36)','ascii_bin')} and batch_key == ('varchar(36)','ascii_bin')
            and public_uid == ('binary(16)','NO') and public_unique
            and refs == {(table, column, 'uid') for table, column in REFERENCES}):
        return 'ready'
    if (primary == {('id','bigint unsigned',None)} and batch_key == ('bigint unsigned',None) and public_uid is None
            and refs == {(table, column, 'id') for table, column in REFERENCES}):
        return 'legacy'
    return 'unknown'


def migrate(connection, backup):
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.user-uid',5)")
        if cursor.fetchone()[0]!=1:
            raise CatalogMigrationError('另一个账户主键升级正在进行。')
        try:
            state = schema(cursor)
            if state == 'ready':
                return False
            if state != 'legacy' or assembly_schema(cursor) != 'ready':
                raise CatalogMigrationError('账户或认领结构不符合迁移基线。')
            for table in ('user', *sorted({table for table, _ in REFERENCES})):
                cursor.execute(f'SELECT 1 FROM {table} LIMIT 1')
                if cursor.fetchone():
                    raise CatalogMigrationError(f'{table} 仍有账户记录，未切换主键。')
            connection.commit()
            backup()
            path = Path(__file__).resolve().parents[1] / 'db/migrations/010_user_uuid.sql'
            sql = '\n'.join(line for line in path.read_text(encoding='utf-8').splitlines() if not line.startswith('--'))
            for statement in sql.split(';'):
                if statement.strip():
                    cursor.execute(statement)
            connection.commit()
            if schema(cursor) != 'ready':
                raise CatalogMigrationError('账户主键升级未通过结构核验，请保留现场。')
            return True
        finally:
            cursor.execute("SELECT RELEASE_LOCK('bumbum.user-uid')")
