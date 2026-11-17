"""011 是仅增加通行密钥及短时挑战两张表的升级。"""

from pathlib import Path

from core.catalog_migration import CatalogMigrationError
from core.schema_checks import structure_state
from core.user_uid_migration import schema as user_uid_schema


COLUMNS = {
    ('admin_passkey', 'id'): ('bigint unsigned', 'NO', 'auto_increment'),
    ('admin_passkey', 'admin_id'): ('bigint unsigned', 'NO', ''),
    ('admin_passkey', 'credential_hash'): ('binary(32)', 'NO', ''),
    ('admin_passkey', 'public_key'): ('varbinary(4096)', 'NO', ''),
    ('admin_passkey', 'sign_count'): ('bigint unsigned', 'NO', ''),
    ('admin_passkey', 'created_at'): ('datetime(6)', 'NO', ''),
    ('admin_passkey', 'last_used_at'): ('datetime(6)', 'YES', ''),
    ('admin_passkey', 'revoked_at'): ('datetime(6)', 'YES', ''),
    ('admin_passkey_challenge', 'challenge_hash'): ('binary(32)', 'NO', ''),
    ('admin_passkey_challenge', 'session_id'): ('bigint unsigned', 'YES', ''),
    ('admin_passkey_challenge', 'expires_at'): ('datetime(6)', 'NO', ''),
}
UNIQUE_KEYS = {
    ('admin_passkey', 'PRIMARY'): ('id',),
    ('admin_passkey', 'credential_hash'): ('credential_hash',),
    ('admin_passkey_challenge', 'PRIMARY'): ('challenge_hash',),
}
FOREIGN_KEYS = {
    ('admin_passkey', 'fk_passkey_admin', 'admin_id', 'admin_user', 'id', 1, 'CASCADE', 'RESTRICT'),
    ('admin_passkey_challenge', 'fk_passkey_challenge_session', 'session_id', 'admin_session', 'id', 1, 'CASCADE', 'RESTRICT'),
}


def schema(cursor):
    return structure_state(cursor, COLUMNS, UNIQUE_KEYS, FOREIGN_KEYS)


def migrate(connection, backup):
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.admin-passkeys',5)")
        if cursor.fetchone()[0] != 1:
            raise CatalogMigrationError("另一个通行密钥升级正在运行。")
        try:
            state = schema(cursor)
            if state == "ready":
                return False
            if state != "missing" or user_uid_schema(cursor) != "ready":
                raise CatalogMigrationError("需要完整的账户双标识结构。部分通行密钥结构须先核对现场。")
            connection.commit()
            backup()
            path = Path(__file__).resolve().parents[1] / "db/migrations/011_admin_passkeys.sql"
            sql = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("--"))
            for statement in sql.split(";"):
                if statement.strip():
                    cursor.execute(statement)
            connection.commit()
            if schema(cursor) != "ready":
                raise CatalogMigrationError("通行密钥升级后的结构未通过核对。")
            return True
        finally:
            cursor.execute("SELECT RELEASE_LOCK('bumbum.admin-passkeys')")
