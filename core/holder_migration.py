"""检查和升级 014 持有体验结构，由部署工具在停写和备份后执行。"""

from pathlib import Path

from core.catalog_migration import CatalogMigrationError
from core.order_migration import match_schema


def schema(cursor):
    cursor.execute('''SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_KEY
                      FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()
                      AND TABLE_NAME IN ('item_recovery_contact','item_notice_dismissal')''')
    columns = set(cursor.fetchall())
    cursor.execute('''SELECT COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()
                      AND TABLE_NAME='tap_grant' AND COLUMN_NAME='allowed_action' ''')
    action = cursor.fetchone()
    expected = {('item_recovery_contact','ownership_id','bigint unsigned','NO','PRI'),
                ('item_recovery_contact','consent_hash','binary(32)','NO',''),
                ('item_notice_dismissal','handover_id','bigint unsigned','NO','PRI')}
    if not columns and action == ("enum('read','bind','view')",):
        return 'missing'
    if columns != expected or action != ("enum('read','bind','view','recovery')",):
        return 'unknown'
    cursor.execute('''SELECT TABLE_NAME,REFERENCED_TABLE_NAME,DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS
                      WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME IN ('item_recovery_contact','item_notice_dismissal')''')
    return 'ready' if set(cursor.fetchall()) == {('item_recovery_contact','ownership','CASCADE'),
                                                ('item_notice_dismissal','item_handover','CASCADE')} else 'unknown'


def migrate(connection, backup):
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.holder-lifecycle',5)")
        if cursor.fetchone()[0] != 1:
            raise CatalogMigrationError('另一个持有体验升级正在运行。')
        try:
            before = schema(cursor)
            if before == 'ready':
                return False
            if before != 'missing' or match_schema(cursor) != 'ready':
                raise CatalogMigrationError('当前数据库结构与 013 基线不一致。')
            connection.commit()
            backup()
            cursor.execute('SET SESSION lock_wait_timeout=10')
            path = Path(__file__).resolve().parents[1] / 'db/migrations/014_holder_lifecycle.sql'
            sql = '\n'.join(line for line in path.read_text(encoding='utf-8').splitlines() if not line.startswith('--'))
            for statement in sql.split(';'):
                if statement.strip():
                    cursor.execute(statement)
            connection.commit()
            if schema(cursor) != 'ready':
                raise CatalogMigrationError('持有体验结构升级后未通过核对。')
            return True
        finally:
            cursor.execute("SELECT RELEASE_LOCK('bumbum.holder-lifecycle')")
