"""检查及升级首次登记来源；不处理卡内内容、手机时间或任何密钥。"""

import argparse
from pathlib import Path
import sys

from core.db import get_database, registration_source_schema

MIGRATIONS = Path(__file__).resolve().parents[1] / "db/migrations"


class SourceMigrationError(Exception):
    """只输出可公开的阶段说明，不包含连接凭证。"""


def migrate(connection, backup):
    """调用者停止登记写入；锁内先备份，再补字段和历史来源，失败可重跑。"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.registration-source',5)")
        if cursor.fetchone()[0] != 1:
            raise SourceMigrationError("另一个来源升级正在执行，请稍后再试。")
        try:
            cursor.execute("SELECT VERSION()")
            if not cursor.fetchone()[0].startswith("8.0."):
                raise SourceMigrationError("本次升级只在MySQL 8.0验证过，未执行修改。")
            state = registration_source_schema(cursor)
            if state == "unknown":
                raise SourceMigrationError("来源字段结构不符合约定，请保留数据让AI核对。")
            # 新库或已完成升级的库无需再备份；未知历史且没有证据时保持未知。
            if state == "ready":
                cursor.execute("""SELECT COUNT(*) FROM chip c JOIN (
                    SELECT target_id FROM admin_audit WHERE action='chip.register' AND target_type='chip'
                    GROUP BY target_id HAVING COUNT(*)=1
                    AND MAX(JSON_UNQUOTE(JSON_EXTRACT(detail,'$.source'))) IN ('manual','nfc_cool')
                    ) a ON a.target_id=CAST(c.id AS CHAR) WHERE c.registration_source='unknown'""")
                if cursor.fetchone()[0] == 0:
                    return False
            connection.commit()
            backup()
            cursor.execute("SET SESSION lock_wait_timeout=10")
            if state == "missing":
                cursor.execute((MIGRATIONS / "002_chip_registration_source.sql").read_text(encoding="utf-8"))
            cursor.execute((MIGRATIONS / "002_chip_registration_source_backfill.sql").read_text(encoding="utf-8"))
            connection.commit()
            if registration_source_schema(cursor) != "ready":
                raise SourceMigrationError("来源升级后检查未通过，请保留备份并停止操作。")
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.execute("SELECT RELEASE_LOCK('bumbum.registration-source')")


def validate_cloud_config(config):
    expected = {"APP_ENV": "production", "DB_HOST": "127.0.0.1", "DB_PORT": 33307,
                "DB_USER": "bumbum_test", "DB_NAME": "bumbum_digital", "ADMIN_ORIGIN": "https://test.bumbum.cc"}
    if any(config.get(name) != value for name, value in expected.items()):
        raise SourceMigrationError("此入口只允许约定的香港测试库；未操作其他数据库。")


def main():
    parser = argparse.ArgumentParser(description="香港来源升级入口；请通过cloud_test.sh upgrade-source执行，先停止后端并备份。")
    parser.add_argument("--apply-after-backup", action="store_true")
    args = parser.parse_args()
    try:
        from app import create_app
        app = create_app()
        validate_cloud_config(app.config)
        with app.app_context():
            connection = get_database()
            if not args.apply_after_backup:
                with connection.cursor() as cursor:
                    state = registration_source_schema(cursor)
                print({"ready": "来源字段已就绪。", "missing": "需要升级：缺少登记来源字段。"}.get(state, "来源字段结构无法识别。"))
                return 0 if state != "unknown" else 1
            changed = migrate(connection, lambda: None)
            print("来源升级完成；账号和芯片资料保留。" if changed else "来源已是目标版本，无需重复修改。")
            return 0
    except SourceMigrationError as error:
        print("未完成：" + str(error), file=sys.stderr)
    except Exception:
        print("未完成：来源升级失败；保留备份，不重建数据库，请让AI核对。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
