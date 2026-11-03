"""私有图片的元数据、归属、文件访问与资料关联；备份工具不依赖本模块。"""

from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit

from flask import current_app
import pymysql

from core.admin_auth import AuthRequestError
from core.auth_settings import iso_time

MAX_FILE = 8 * 1024**2
MAX_PIXELS = 16_000_000
MAX_WEBP_PIXELS = 8_000_000
ASSET_ID = re.compile(r'[a-f0-9]{32}')
IMAGE_PATH = re.compile(r'/api/(admin|tap|fashion)/items/([1-9][0-9]*)/images/([a-f0-9]{32})')


class MediaUnavailable(Exception):
    """图片存储或记录不满足使用前提。"""


def conflict(message='图片的归属或暂存状态已变化，请核对后重新选择。'):
    raise AuthRequestError(409, 'asset_conflict', message)


def database_now(cursor):
    cursor.execute('SELECT UTC_TIMESTAMP(6) AS now')
    return cursor.fetchone()['now']


def init_media_settings(app):
    app.config.setdefault('MEDIA_ENABLED', os.getenv('MEDIA_ENABLED', 'false') == 'true' if os.getenv('MEDIA_ENABLED', 'false') in {'true', 'false'} else None)
    app.config.setdefault('MEDIA_ROOT', os.getenv('MEDIA_ROOT') or str(Path(__file__).resolve().parents[1] / 'media'))
    raw = os.getenv('MEDIA_MAX_TOTAL_BYTES', str(2 * 1024**3))
    app.config.setdefault('MEDIA_MAX_TOTAL_BYTES', int(raw) if raw.isascii() and raw.isdecimal() and 0 < int(raw) < 2**63 else None)


def media_root(*, writable=False):
    try:
        path = Path(current_app.config['MEDIA_ROOT'])
        if not path.is_absolute() or path.resolve(strict=True) != path or not path.is_dir() or path.is_symlink():
            raise ValueError
        if os.name != 'nt' and path.stat().st_mode & 0o077:
            raise ValueError
        if writable and not os.access(path, os.W_OK):
            raise ValueError
        return path
    except (KeyError, TypeError, ValueError, OSError):
        raise MediaUnavailable('图片私有目录未就绪。') from None


def origin(context):
    key = 'ADMIN_ORIGIN' if context == 'admin' else 'PUBLIC_ORIGIN'
    value = current_app.config.get(key)
    try:
        parts = urlsplit(value)
        parts.port
        local = parts.hostname in {'127.0.0.1', 'localhost', '::1'}
        if not isinstance(value, str) or not parts.hostname or parts.username or parts.password or parts.path or parts.query or parts.fragment or parts.scheme not in {'http', 'https'}:
            raise ValueError
        if parts.scheme == 'http' and not (local and current_app.config['APP_ENV'] == 'development'):
            raise ValueError
        return value
    except (TypeError, ValueError, KeyError):
        raise MediaUnavailable('图片访问来源配置未就绪。') from None


def image_url(item_id, asset_id, context='admin'):
    return f'{origin(context)}/api/{context}/items/{item_id}/images/{asset_id}'


def managed_path(value):
    try:
        return IMAGE_PATH.fullmatch(urlsplit(value).path)
    except (ValueError, TypeError):
        return None


def valid_metadata(asset):
    uid = asset['asset_id']
    if not ASSET_ID.fullmatch(uid) or asset['storage_key'] != uid + '.webp':
        raise MediaUnavailable('图片记录无法验证。')
    try:
        parts = urlsplit(asset['reference_url'])
        if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path != f"/api/tap/items/{asset['item_id']}/images/{uid}":
            raise ValueError
    except (ValueError, TypeError):
        raise MediaUnavailable('图片引用无法验证。') from None


def asset_payload(asset, now):
    valid_metadata(asset)
    expired = asset['expires_at'] is not None and asset['expires_at'] <= now
    available = asset['state'] == 'attached' or (asset['state'] == 'pending' and not expired)
    return {'asset_id': asset['asset_id'], 'state': asset['state'], 'expired': expired,
            'url': asset['reference_url'], 'preview_url': image_url(asset['item_id'], asset['asset_id']) if available else None,
            'expires_at': iso_time(asset['expires_at']) if asset['expires_at'] else None}


def open_asset(asset, *, verify_hash=False):
    """固定私有文件名并拒绝符号链接；返回已打开文件，传输不占数据库锁。"""
    valid_metadata(asset)
    stream = None
    try:
        path = media_root() / asset['storage_key']
        if path.is_symlink():
            raise ValueError
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
        stream = os.fdopen(descriptor, 'rb')
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != asset['byte_size'] or not 0 < info.st_size <= MAX_FILE:
            raise ValueError
        if verify_hash:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != asset['sha256']:
                raise ValueError
            stream.seek(0)
        return stream
    except (OSError, ValueError):
        if stream is not None:
            stream.close()
        raise MediaUnavailable('图片文件暂不可读取，请核对配套备份与存储。') from None


def sync_directory(root):
    if os.name != 'nt':
        descriptor = os.open(root, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def asset_for_read(cursor, item_id, asset_id, *, admin_id=None):
    if not ASSET_ID.fullmatch(asset_id):
        raise AuthRequestError(404, 'not_found', '图片不存在。')
    cursor.execute("""SELECT a.*,CASE p.code WHEN 'fashion' THEN fp.image_urls WHEN 'jewelry' THEN jp.image_urls END AS saved_images
        FROM media_asset a JOIN item i ON i.id=a.item_id JOIN project p ON p.id=i.project_id
        LEFT JOIN fashion_item_profile fp ON fp.item_id=i.id AND p.code='fashion'
        LEFT JOIN jewelry_item_profile jp ON jp.item_id=i.id AND p.code='jewelry'
        WHERE a.item_id=%s AND a.asset_id=%s""", (item_id, asset_id))
    asset = cursor.fetchone()
    if asset is None:
        raise AuthRequestError(404, 'not_found', '图片不存在。')
    now = database_now(cursor)
    saved = json.loads(asset.pop('saved_images') or '[]')
    attached = asset['state'] == 'attached' and asset['reference_url'] in saved
    pending = admin_id is not None and asset['created_by'] == admin_id and asset['state'] == 'pending' and asset['expires_at'] > now
    if not attached and not pending:
        raise AuthRequestError(403, 'forbidden', '当前不能读取该图片。')
    valid_metadata(asset)
    return asset


def map_profile_images(cursor, profiles, *, context='admin'):
    """跨一页资料批量映射，旧外部URL原样保留；不按当前域名前缀猜归属。"""
    ids = [item_id for item_id, profile in profiles.items() if any(managed_path(url) for url in profile.get('image_urls', []))]
    if not ids:
        return
    cursor.execute(f"SELECT * FROM media_asset WHERE item_id IN ({','.join(['%s'] * len(ids))}) AND state='attached'", ids)
    assets = {}
    for asset in cursor.fetchall():
        valid_metadata(asset)
        assets[(asset['item_id'], asset['reference_url'])] = asset
    for item_id in ids:
        urls = []
        for url in profiles[item_id]['image_urls']:
            asset = assets.get((item_id, url))
            if asset:
                urls.append(image_url(item_id, asset['asset_id'], context))
            elif managed_path(url):
                raise MediaUnavailable('物品图片引用与元数据不一致。')
            else:
                urls.append(url)
        profiles[item_id]['image_urls'] = urls


def attach_images(cursor, item_id, admin_id, urls, previous_urls):
    """在既有物品锁内调用；按标识顺序锁图片，与资料和审计一起提交。"""
    if not any(managed_path(value) for value in [*urls, *previous_urls]):
        return urls
    for value in urls:
        match = managed_path(value)
        if match and int(match[2]) != item_id:
            conflict('不能引用其他物品的图片。')
    cursor.execute('SELECT * FROM media_asset WHERE item_id=%s ORDER BY asset_id FOR UPDATE', (item_id,))
    assets = list(cursor.fetchall())
    by_reference = {asset['reference_url']: asset for asset in assets}
    by_id = {asset['asset_id']: asset for asset in assets}
    now = database_now(cursor)
    normalized, selected = [], set()
    for value in urls:
        match = managed_path(value)
        if not match:
            normalized.append(value)
            continue
        asset = by_reference.get(value)
        if asset is None and match[1] == 'admin':
            candidate = by_id.get(match[3])
            if candidate and value in {image_url(item_id, candidate['asset_id']), f"/api/admin/items/{item_id}/images/{candidate['asset_id']}"}:
                asset = candidate
        if asset is None:
            conflict('图片引用无法对应本物品的已上传记录。')
        valid_metadata(asset)
        if asset['state'] == 'pending':
            if asset['reference_url'] in previous_urls:
                raise MediaUnavailable('已有图片引用的发布状态不一致。')
            if asset['created_by'] != admin_id or asset['expires_at'] <= now:
                conflict('暂存图片已过期或由其他管理员上传，请重新选择。')
        elif asset['state'] != 'attached' or asset['reference_url'] not in previous_urls:
            conflict()
        with open_asset(asset, verify_hash=True):
            pass
        normalized.append(asset['reference_url'])
        selected.add(asset['asset_id'])
    for asset in assets:
        if asset['asset_id'] in selected and asset['state'] == 'pending':
            cursor.execute("UPDATE media_asset SET state='attached',expires_at=NULL,updated_at=%s WHERE asset_id=%s", (now, asset['asset_id']))
        elif asset['state'] == 'attached' and asset['asset_id'] not in selected:
            if asset['reference_url'] not in previous_urls:
                raise MediaUnavailable('图片关联记录不一致，请先核对。')
            cursor.execute("UPDATE media_asset SET state='retired',expires_at=%s,updated_at=%s WHERE asset_id=%s", (now + timedelta(days=7), now, asset['asset_id']))
    return normalized
