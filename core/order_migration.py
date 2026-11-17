"""012 创建订单表，013 保存逐件核对的款式与规格。"""

from pathlib import Path

from core.catalog_migration import CatalogMigrationError
from core.passkey_migration import schema as passkey_schema
from core.schema_checks import structure_state


COLUMNS = {
    ('sales_order', 'id'): ('bigint unsigned', 'NO', 'auto_increment'),
    ('sales_order', 'test_batch_id'): ('bigint unsigned', 'YES', ''),
    ('sales_order', 'source_scope'): ('bigint unsigned', 'YES', 'STORED GENERATED'),
    ('sales_order', 'channel'): ('varchar(40)', 'NO', ''),
    ('sales_order', 'external_order_no'): ('varchar(64)', 'NO', ''),
    ('sales_order', 'created_by'): ('bigint unsigned', 'NO', ''),
    ('sales_order', 'created_at'): ('datetime(6)', 'NO', 'DEFAULT_GENERATED'),
    ('sales_order_unit', 'id'): ('bigint unsigned', 'NO', 'auto_increment'),
    ('sales_order_unit', 'order_id'): ('bigint unsigned', 'NO', ''),
    ('sales_order_unit', 'position'): ('smallint unsigned', 'NO', ''),
    ('sales_order_unit', 'product_name'): ('varchar(128)', 'NO', ''),
    ('sales_order_unit', 'ordered_spec'): ('varchar(256)', 'YES', ''),
    ('sales_order_unit', 'physical_item_id'): ('bigint unsigned', 'YES', ''),
    ('sales_order_unit', 'item_id'): ('bigint unsigned', 'YES', ''),
    ('sales_order_unit', 'allocated_at'): ('datetime(6)', 'YES', ''),
    ('sales_order_unit', 'delivered_at'): ('datetime(6)', 'YES', ''),
    ('sales_order_unit', 'delivery_whole_id'): ('bigint unsigned', 'YES', ''),
    ('sales_order_unit', 'first_claim_code_id'): ('bigint unsigned', 'YES', ''),
}
UNIQUE_KEYS = {
    ('sales_order', 'PRIMARY'): ('id',),
    ('sales_order', 'uk_sales_order_source'): ('source_scope', 'channel', 'external_order_no'),
    ('sales_order_unit', 'PRIMARY'): ('id',),
    ('sales_order_unit', 'physical_item_id'): ('physical_item_id',),
    ('sales_order_unit', 'item_id'): ('item_id',),
    ('sales_order_unit', 'uk_order_unit_position'): ('order_id', 'position'),
}
FOREIGN_KEYS = {
    ('sales_order', 'fk_sales_order_batch', 'test_batch_id', 'test_batch', 'id', 1, 'RESTRICT', 'RESTRICT'),
    ('sales_order', 'fk_sales_order_admin', 'created_by', 'admin_user', 'id', 1, 'RESTRICT', 'RESTRICT'),
    ('sales_order_unit', 'fk_order_unit_order', 'order_id', 'sales_order', 'id', 1, 'CASCADE', 'RESTRICT'),
    ('sales_order_unit', 'fk_order_unit_physical', 'physical_item_id', 'physical_item', 'id', 1, 'RESTRICT', 'RESTRICT'),
    ('sales_order_unit', 'fk_order_unit_item', 'item_id', 'item', 'id', 1, 'RESTRICT', 'RESTRICT'),
    ('sales_order_unit', 'fk_order_unit_delivery', 'delivery_whole_id', 'whole_item', 'id', 1, 'RESTRICT', 'RESTRICT'),
    ('sales_order_unit', 'fk_order_unit_claim', 'first_claim_code_id', 'item_claim_code', 'id', 1, 'RESTRICT', 'RESTRICT'),
}
MATCH_COLUMNS = {
    ('sales_order_unit_match', 'unit_id'): ('bigint unsigned', 'NO', ''),
    ('sales_order_unit_match', 'style_id'): ('bigint unsigned', 'NO', ''),
    ('sales_order_unit_match', 'spec'): ('varchar(256)', 'YES', ''),
}
MATCH_UNIQUE_KEYS = {
    ('sales_order_unit_match', 'PRIMARY'): ('unit_id',),
}
MATCH_FOREIGN_KEYS = {
    ('sales_order_unit_match', 'fk_order_match_unit', 'unit_id', 'sales_order_unit', 'id', 1, 'CASCADE', 'RESTRICT'),
    ('sales_order_unit_match', 'fk_order_match_style', 'style_id', 'product_style', 'id', 1, 'RESTRICT', 'RESTRICT'),
}


def schema(cursor):
    return structure_state(cursor, COLUMNS, UNIQUE_KEYS, FOREIGN_KEYS,
                           generated={('sales_order', 'source_scope'): 'coalesce(test_batch_id,0)'},
                           defaults={('sales_order', 'created_at'): 'CURRENT_TIMESTAMP(6)'})


def match_schema(cursor):
    return structure_state(cursor, MATCH_COLUMNS, MATCH_UNIQUE_KEYS, MATCH_FOREIGN_KEYS)


def migrate(connection, backup):
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.sales-orders',5)")
        if cursor.fetchone()[0] != 1:
            raise CatalogMigrationError("另一个订单升级正在运行。")
        try:
            orders, match = schema(cursor), match_schema(cursor)
            if orders == match == "ready":
                return False
            if (orders, match) not in {("missing", "missing"), ("ready", "missing")} or passkey_schema(cursor) != "ready":
                raise CatalogMigrationError("订单结构不完整，请先核对现场。")
            connection.commit()
            backup()
            migrations = Path(__file__).resolve().parents[1] / "db/migrations"
            names = ["012_sales_orders.sql"] if orders == "missing" else []
            for name in [*names, "013_sales_order_unit_match.sql"]:
                sql = "\n".join(line for line in (migrations / name).read_text(encoding="utf-8").splitlines() if not line.startswith("--"))
                for statement in sql.split(";"):
                    if statement.strip():
                        cursor.execute(statement)
            connection.commit()
            if schema(cursor) != "ready" or match_schema(cursor) != "ready":
                raise CatalogMigrationError("订单升级后的结构未通过核对。")
            return True
        finally:
            cursor.execute("SELECT RELEASE_LOCK('bumbum.sales-orders')")
