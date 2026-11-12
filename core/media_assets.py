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


def sync_directory(root):
    if os.name != 'nt':
        descriptor = os.open(root, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def map_profile_images(cursor, profiles, *, context='admin'):
    """只为当前H5映射新版款图；旧图片/外链不再回退。"""
    for item_id,profile in profiles.items():
        urls=[]
        for url in profile.get('image_urls',[]):
            prefix=f'/api/tap/items/{item_id}/style-images/'
            if context in {'tap','fashion'} and isinstance(url,str) and url.startswith(prefix) and ASSET_ID.fullmatch(url[len(prefix):]):
                urls.append(f"{origin(context)}/api/{context}/items/{item_id}/style-images/{url[len(prefix):]}")
        profile['image_urls']=urls
