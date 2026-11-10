"""012 创建订单表，013 保存逐件核对的款式与规格。"""

from pathlib import Path

from core.catalog_migration import CatalogMigrationError
from core.passkey_migration import schema as passkey_schema


COLUMNS = {
    "sales_order": {"id", "test_batch_id", "source_scope", "channel", "external_order_no", "created_by", "created_at"},
    "sales_order_unit": {"id", "order_id", "position", "product_name", "ordered_spec", "physical_item_id", "item_id",
                         "allocated_at", "delivered_at", "delivery_whole_id", "first_claim_code_id"},
}


def schema(cursor):
    cursor.execute("""SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.COLUMNS
                      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('sales_order','sales_order_unit')""")
    fields = {}
    for table, column in cursor.fetchall():
        fields.setdefault(table, set()).add(column)
    return "ready" if fields == COLUMNS else "missing" if not fields else "unknown"


def match_schema(cursor):
    cursor.execute("""SELECT COLUMN_NAME FROM information_schema.COLUMNS
                      WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='sales_order_unit_match'""")
    columns = {column for column, in cursor.fetchall()}
    return "ready" if columns == {"unit_id", "style_id", "spec"} else "unknown" if columns else "missing"


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
