"""触碰日志的已知结构升级；不猜历史归属，不清库或自动恢复备份。"""

import argparse
from pathlib import Path
import sys

from core.db import get_database, tap_event_schema
from core.registration_migration import validate_cloud_config

MIGRATION = Path(__file__).resolve().parents[1] / 'db/migrations/003_tap_events.sql'


class TapMigrationError(Exception):
    """可公开的升级阶段说明，不包含数据库秘密或业务数据。"""


def migrate(connection, backup):
    """调用方先停止写入；单条原子DDL失败后保留原结构及完整备份。"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.tap-events',5)")
        if cursor.fetchone()[0] != 1:
            raise TapMigrationError('另一个触碰日志升级正在执行，请稍后重试。')
        try:
            cursor.execute('SELECT VERSION()')
            if not cursor.fetchone()[0].startswith('8.0.'):
                raise TapMigrationError('触碰日志升级只在MySQL 8.0验证过，未修改。')
            state = tap_event_schema(cursor)
            if state == 'ready':
                return False
            if state != 'missing':
                raise TapMigrationError('触碰日志结构无法识别，请保留备份让AI核对，不自动修复。')
            cursor.execute("SELECT COUNT(*) FROM scan_log WHERE verify_result='pass'")
            if cursor.fetchone()[0]:
                raise TapMigrationError('旧库已有成功触碰记录但缺少当时物品归属；未猜测回填或删除，请先对齐历史处理。')
            connection.commit()
            backup()
            cursor.execute('SET SESSION lock_wait_timeout=10')
            cursor.execute(MIGRATION.read_text(encoding='utf-8'))
            if tap_event_schema(cursor) != 'ready':
                raise TapMigrationError('触碰日志升级后检查未通过，保留备份并停止，不重建库。')
            return True
        finally:
            cursor.execute("SELECT RELEASE_LOCK('bumbum.tap-events')")


def main():
    parser = argparse.ArgumentParser(description='香港触碰日志升级；通过cloud_test.sh upgrade-tap先停服务并备份。')
    parser.add_argument('--apply-after-backup', action='store_true')
    args = parser.parse_args()
    try:
        from app import create_app
        app = create_app()
        validate_cloud_config(app.config)
        with app.app_context():
            connection = get_database()
            if not args.apply_after_backup:
                with connection.cursor() as cursor:
                    state = tap_event_schema(cursor)
                print({'ready': '触碰日志已就绪。', 'missing': '触碰日志需要升级。'}.get(state, '触碰日志结构无法识别。'))
                return 0 if state != 'unknown' else 1
            changed = migrate(connection, lambda: None)
            print('触碰日志升级完成；原业务数据保留。' if changed else '已是目标版本，未重复升级。')
            return 0
    except TapMigrationError as error:
        print('未完成：' + str(error), file=sys.stderr)
    except Exception:
        print('未完成：触碰日志升级或配置检查失败，保留备份，请让AI核对，不重建数据库。', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
