"""011 是仅增加通行密钥及短时挑战两张表的升级。"""

from pathlib import Path

from core.catalog_migration import CatalogMigrationError
from core.user_uid_migration import schema as user_uid_schema


COLUMNS = {
    "admin_passkey": {"id","admin_id","credential_hash","public_key","sign_count","created_at","last_used_at","revoked_at"},
    "admin_passkey_challenge": {"challenge_hash","session_id","expires_at"},
}


def schema(cursor):
    cursor.execute("""SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.COLUMNS
                      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('admin_passkey','admin_passkey_challenge')""")
    fields = {}
    for table, column in cursor.fetchall():
        fields.setdefault(table,set()).add(column)
    return "ready" if fields == COLUMNS else "missing" if not fields else "unknown"


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
