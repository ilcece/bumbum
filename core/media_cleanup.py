"""只清理到期的媒体技术资源；不删除物品、外部URL或业务历史。"""

from collections import Counter
from datetime import datetime
import hashlib
import json
import os
import re
import stat

import pymysql

from core.db import media_asset_schema
from core.media_assets import MediaUnavailable, database_now, managed_path, media_root, sync_directory, valid_metadata
from core.media_backup import inspect_bundle, required_files, snapshot

STATES = {'uploading', 'pending', 'retired', 'deleting'}


def unreferenced(cursor, asset):
    for project in ('fashion', 'jewelry'):
        cursor.execute(f'SELECT image_urls FROM {project}_item_profile')
        for row in cursor.fetchall():
            urls = json.loads(row['image_urls'] or '[]')
            if not isinstance(urls, list) or any(not isinstance(url, str) for url in urls):
                raise MediaUnavailable('资料图片引用结构不明，停止清理。')
            for value in urls:
                match = managed_path(value)
                if value == asset['reference_url'] or (match and match[3] == asset['asset_id']):
                    raise MediaUnavailable('图片仍被资料引用，停止清理。')


def files_to_remove(root, asset):
    """核对本功能固定文件名、摘要及硬链接归属，不跟随链接或递归删目录。"""
    valid_metadata(asset)
    final = root / asset['storage_key']
    paths = [final] if os.path.lexists(final) else []
    for path in root.glob('.' + asset['asset_id'] + '-*.tmp'):
        if not re.fullmatch(r'\.' + asset['asset_id'] + r'-[a-z0-9_]{8}\.tmp', path.name) or asset['state'] not in {'uploading','deleting'}:
            raise MediaUnavailable('暂存文件归属无法确认，停止清理。')
        paths.append(path)
    if not os.path.lexists(final) and asset['byte_size'] and asset['state'] in {'pending','retired'}:
        raise MediaUnavailable('完整图片缺失，先核对存储与备份，停止清理。')
    stats = []
    for path in paths:
        info = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or path.is_symlink() or info.st_size > asset['byte_size']:
            raise MediaUnavailable('图片文件类型或内容不明，停止清理。')
        if path == final:
            if not asset['sha256'] or info.st_size != asset['byte_size']:
                raise MediaUnavailable('图片摘要证明不完整，停止清理。')
            descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
            with os.fdopen(descriptor, 'rb') as stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise MediaUnavailable('核对期间文件变化，停止清理。')
                if hashlib.file_digest(stream, 'sha256').hexdigest() != asset['sha256']:
                    raise MediaUnavailable('图片内容与记录不符，停止清理。')
        stats.append((path, info))
    linked = Counter((info.st_dev, info.st_ino) for _, info in stats)
    if any(info.st_nlink != linked[(info.st_dev, info.st_ino)] for _, info in stats):
        raise MediaUnavailable('图片存在未知硬链接，停止清理。')
    return stats


def cleanup(connection, *, apply=False, backup_bundle=None):
    root = media_root(writable=apply)
    with connection.cursor() as cursor:
        if media_asset_schema(cursor) != 'ready':
            raise MediaUnavailable('媒体结构无法完整识别，停止清理。')
    connection.rollback()
    data = snapshot(connection)
    required_files(data)
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        now = database_now(cursor)
    connection.rollback()
    candidates = [row for row in data['assets'] if row['state'] in STATES and row['expires_at'] and datetime.fromisoformat(row['expires_at']) <= now]
    known_ids = {row['asset_id'] for row in data['assets']}
    known_files = {row['storage_key'] for row in data['assets']}
    unknown = sum(path.name not in known_files and not (re.fullmatch(r'\.[a-f0-9]{32}-[a-z0-9_]{8}\.tmp', path.name) and path.name[1:33] in known_ids) for path in root.iterdir())
    result = {'candidates': [{key: row[key] for key in ('asset_id','item_id','state','byte_size','expires_at')} for row in candidates], 'deleted': 0, 'unknown_files_preserved': unknown}
    if not apply:
        return result
    if backup_bundle is None:
        raise MediaUnavailable('执行清理须提供已经验证的配套备份目录。')
    backup = {row['asset_id']: row for row in inspect_bundle(backup_bundle)['assets']}
    for requested in candidates:
        connection.begin()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute('SELECT id FROM item WHERE id=%s FOR UPDATE', (requested['item_id'],))
                cursor.execute('SELECT * FROM media_asset WHERE asset_id=%s FOR UPDATE', (requested['asset_id'],))
                asset = cursor.fetchone()
                now = database_now(cursor)
                if not asset or asset['state'] not in STATES or asset['expires_at'] is None or asset['expires_at'] > now:
                    connection.rollback()
                    continue
                unreferenced(cursor, asset)
                if asset['byte_size'] and asset['state'] != 'uploading':
                    saved = backup.get(asset['asset_id'])
                    if not saved or saved['state'] not in {'pending','attached','retired'} or any(saved[key] != asset[key] for key in ('item_id','created_by','storage_key','reference_url','sha256','source_sha256','byte_size')):
                        raise MediaUnavailable('缺少本图片可核对的配套备份，停止清理。')
                files = files_to_remove(root, asset)
                cursor.execute("UPDATE media_asset SET state='deleting',expires_at=%s,updated_at=%s WHERE asset_id=%s", (now, now, asset['asset_id']))
            connection.commit()
            for path, original in files:
                try:
                    current = path.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if path.is_symlink() or (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
                    raise MediaUnavailable('清理期间文件变化，保留记录等待核对。')
                path.unlink()
            sync_directory(root)
            connection.begin()
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute('SELECT id FROM item WHERE id=%s FOR UPDATE', (asset['item_id'],))
                cursor.execute('SELECT * FROM media_asset WHERE asset_id=%s FOR UPDATE', (asset['asset_id'],))
                current = cursor.fetchone()
                if current:
                    if current['state'] != 'deleting':
                        raise MediaUnavailable('清理状态已变化，保留记录等待核对。')
                    unreferenced(cursor, current)
                    cursor.execute("DELETE FROM media_asset WHERE asset_id=%s AND state='deleting'", (asset['asset_id'],))
                    result['deleted'] += cursor.rowcount
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return result
