"""008/009结构检查及带备份的顺序升级。"""

from pathlib import Path

from core.catalog_migration import CatalogMigrationError
from core.testdata_migration import schema as testdata_schema


ASSEMBLY = {
    'physical_item': {'physical_uid','style_id','spec'},
    'digital_item_right': {'item_id','kind','rule_version'},
    'whole_item': {'physical_item_id','installed_at','installed_by','current_physical_id'},
    'item_handover': {'physical_item_id','installed_at','installed_by','seller_confirmation','recipient_confirmation','identity_verification_reference','pending_physical_id','quota_year'},
    'user': {'phone_verified_at'},
}
ACCOUNT = {
    'user_session': {'token_hash','user_id','expires_at','revoked_at'},
    'user_sms_challenge': {'challenge_id','code_hash','expires_at','consumed_at','failed_attempts'},
    'item_claim_code': {'item_id','code_hash','open_item_id','expires_at','consumed_at','revoked_at'},
}


def schema(cursor):
    cursor.execute('SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()')
    columns={(table,column):kind for table,column,kind in cursor.fetchall()}
    assembly=[(table,column) in columns for table,names in ASSEMBLY.items() for column in names]
    assembly.append("'physical'" in columns.get(('test_batch_object','kind'),''))
    account=[(table,column) in columns for table,names in ACCOUNT.items() for column in names]
    if all(assembly) and all(account):return 'ready'
    if all(assembly) and not any(account):return 'assembly'
    if not any(assembly) and not any(account):return 'missing'
    return 'unknown'


def migrate(connection, backup):
    migrations=Path(__file__).resolve().parents[1]/'db/migrations'
    with connection.cursor() as c:
        c.execute("SELECT GET_LOCK('bumbum.assembly-h5',5)")
        if c.fetchone()[0]!=1:raise CatalogMigrationError('另一个装配或H5升级正在运行。')
        try:
            state=schema(c)
            if state=='ready':return False
            if state=='unknown' or testdata_schema(c)!='ready':
                raise CatalogMigrationError('请先完成007；部分008/009结构保留现场，先核对备份。')
            connection.commit()
            backup()
            files=[('009_h5_claim.sql','ready')]
            if state=='missing':files.insert(0,('008_physical_assembly.sql','assembly'))
            for filename, expected in files:
                sql=(migrations/filename).read_text(encoding='utf-8')
                sql='\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
                for statement in sql.split(';'):
                    if statement.strip():c.execute(statement)
                connection.commit()
                if schema(c)!=expected:raise CatalogMigrationError('装配或H5升级核对失败，保留备份。')
            return True
        finally:
            c.execute("SELECT RELEASE_LOCK('bumbum.assembly-h5')")
