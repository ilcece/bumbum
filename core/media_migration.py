"""005只新增媒体表；先备份，拒绝修复未知已有结构。"""

from pathlib import Path

from core.db import media_asset_schema

MIGRATION = Path(__file__).resolve().parents[1] / 'db/migrations/005_media_assets.sql'


class MediaMigrationError(Exception):
    """可公开的升级阶段说明，不含连接或凭证。"""


def migrate(connection, backup):
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.media-assets',5)")
        if cursor.fetchone()[0] != 1:
            raise MediaMigrationError('另一个媒体升级正在执行，请稍后重试。')
        try:
            cursor.execute('SELECT VERSION()')
            if not cursor.fetchone()[0].startswith('8.0.'):
                raise MediaMigrationError('媒体升级只在MySQL 8.0验证过，未修改。')
            state = media_asset_schema(cursor)
            if state == 'ready':
                return False
            if state != 'missing':
                raise MediaMigrationError('媒体结构无法完整识别，未修改，请先核对。')
            connection.commit()
            backup()
            cursor.execute('SET SESSION lock_wait_timeout=10')
            for statement in MIGRATION.read_text(encoding='utf-8').split(';'):
                if statement.strip():
                    cursor.execute(statement)
            if media_asset_schema(cursor) != 'ready':
                raise MediaMigrationError('媒体升级后检查未通过，保留备份，不自动删除或重建。')
            return True
        finally:
            cursor.execute("SELECT RELEASE_LOCK('bumbum.media-assets')")
