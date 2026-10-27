"""持续查看资格的已知枚举升级；保留旧凭证，不清库或自动恢复备份。"""

import argparse
from pathlib import Path
import sys

from core.db import get_database, view_grant_schema
from core.registration_migration import validate_cloud_config

MIGRATION = Path(__file__).resolve().parents[1] / 'db/migrations/004_view_grants.sql'


class ViewMigrationError(Exception):
    """可公开的升级阶段说明，不包含数据库秘密或业务数据。"""


def migrate(connection, backup):
    """调用方先停止写入；单条原子DDL失败后保留原结构及完整备份。"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.view-grants',5)")
        if cursor.fetchone()[0] != 1:
            raise ViewMigrationError('另一个持续查看资格升级正在执行，请稍后重试。')
        try:
            cursor.execute('SELECT VERSION()')
            if not cursor.fetchone()[0].startswith('8.0.'):
                raise ViewMigrationError('持续查看资格升级只在MySQL 8.0验证过，未修改。')
            state = view_grant_schema(cursor)
            if state == 'ready':
                return False
            if state != 'missing':
                raise ViewMigrationError('持续查看资格结构无法识别，请保留备份让AI核对，不自动修复。')
            connection.commit()
            backup()
            cursor.execute('SET SESSION lock_wait_timeout=10')
            cursor.execute(MIGRATION.read_text(encoding='utf-8'))
            if view_grant_schema(cursor) != 'ready':
                raise ViewMigrationError('持续查看资格升级后检查未通过，保留备份并停止，不重建库。')
            return True
        finally:
            cursor.execute("SELECT RELEASE_LOCK('bumbum.view-grants')")


def main():
    parser = argparse.ArgumentParser(description='香港持续查看资格升级；通过cloud_test.sh upgrade-view先停服务并备份。')
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
                    state = view_grant_schema(cursor)
                print({'ready': '持续查看资格已就绪。', 'missing': '持续查看资格需要升级。'}.get(state, '持续查看资格结构无法识别。'))
                return 0 if state != 'unknown' else 1
            changed = migrate(connection, lambda: None)
            print('持续查看资格升级完成；原业务数据保留。' if changed else '已是目标版本，未重复升级。')
            return 0
    except ViewMigrationError as error:
        print('未完成：' + str(error), file=sys.stderr)
    except Exception:
        print('未完成：持续查看资格升级或配置检查失败，保留备份，请让AI核对，不重建数据库。', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
