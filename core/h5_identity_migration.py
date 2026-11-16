"""停写、备份后升级 H5 标识和触碰归属，允许从已完成的步骤继续。"""

from pathlib import Path

from core.catalog_migration import CatalogMigrationError
from core.holder_migration import schema as holder_schema


def schema(cursor):
    cursor.execute("""SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_KEY
                      FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()
                      AND ((TABLE_NAME='item' AND COLUMN_NAME='public_id')
                        OR (TABLE_NAME='scan_log' AND COLUMN_NAME IN ('actor_state','actor_user_uid')))""")
    columns = set(cursor.fetchall())
    item = {('item','public_id','char(36)','NO','UNI')}
    actor = {('scan_log','actor_state',"enum('anonymous','account')",'YES',''),
             ('scan_log','actor_user_uid','char(36)','YES','MUL')}
    if not columns:
        return 'missing'
    if columns == {('item','public_id','char(36)','YES','UNI')}:
        return 'backfill'
    if columns == item:
        return 'item_ready'
    if columns != item | actor:
        return 'unknown'
    cursor.execute("""SELECT DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS
                      WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='scan_log'
                      AND CONSTRAINT_NAME='fk_scan_actor' AND REFERENCED_TABLE_NAME='user'""")
    return 'ready' if cursor.fetchone() == ('SET NULL',) else 'unknown'


def migrate(connection, backup):
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.h5-public-identity',5)")
        if cursor.fetchone()[0] != 1:
            raise CatalogMigrationError('另一个 H5 标识升级正在运行。')
        try:
            before = schema(cursor)
            if before == 'ready':
                return False
            if before == 'unknown' or holder_schema(cursor) != 'ready':
                raise CatalogMigrationError('当前结构与 014 或 015 基线不一致。')
            connection.commit()
            backup()
            cursor.execute('SET SESSION lock_wait_timeout=10')
            path = Path(__file__).resolve().parents[1] / 'db/migrations/015_h5_public_identity.sql'
            sql = '\n'.join(line for line in path.read_text(encoding='utf-8').splitlines() if not line.startswith('--'))
            steps = [statement for statement in sql.split(';') if statement.strip()]
            for statement in steps[{'missing':0,'backfill':1,'item_ready':3}[before]:]:
                cursor.execute(statement)
            connection.commit()
            if schema(cursor) != 'ready':
                raise CatalogMigrationError('H5 标识升级后未通过结构核对。')
            return True
        finally:
            cursor.execute("SELECT RELEASE_LOCK('bumbum.h5-public-identity')")
