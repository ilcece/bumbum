"""离线核对数据库快照与图片文件；不导入上传服务或发HTTP请求。"""

from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
from urllib.parse import urlsplit

from PIL import Image
import pymysql


class MediaBackupError(Exception):
    """可公开的阶段说明，不包含数据库凭证或业务正文。"""


def digest(path):
    """拒绝链接和非普通文件，以流式方式核对内容。"""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise MediaBackupError('备份所需文件缺失或不是普通文件。')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise MediaBackupError('拒绝非普通文件。')
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot(connection):
    """仅在新连接的只读一致性事务中取得关联核对所需字段。"""
    if connection.server_status & 1:
        raise MediaBackupError('连接已有事务，未隐式提交或撤销调用方工作。')
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            cursor.execute('SELECT * FROM media_asset ORDER BY asset_id')
            assets = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='style_image'")
            shared_images, shared_styles = [], []
            if cursor.fetchone()['n']:
                cursor.execute('SELECT asset_id,style_id,source_sha256,SHA2(content,256) AS sha256,OCTET_LENGTH(content) AS byte_size FROM style_image ORDER BY asset_id')
                shared_images = cursor.fetchall()
                cursor.execute('SELECT id,image_urls FROM product_style ORDER BY id')
                shared_styles = [{'id': r['id'], 'image_urls': json.loads(r['image_urls']) if isinstance(r['image_urls'],str) else r['image_urls']} for r in cursor.fetchall()]
            cursor.execute('SELECT i.id,i.project_id,i.item_uid,p.code AS project FROM item i JOIN project p ON p.id=i.project_id ORDER BY i.id')
            items = cursor.fetchall()
            profiles = []
            for project in ('fashion', 'jewelry'):
                cursor.execute(f'SELECT item_id,image_urls FROM {project}_item_profile ORDER BY item_id')
                for row in cursor.fetchall():
                    profiles.append({'project': project, 'item_id': row['item_id'], 'image_urls': json.loads(row['image_urls']) if row['image_urls'] else []})
        return json.loads(json.dumps({'assets': assets, 'items': items, 'profiles': profiles, **({'shared_images':shared_images,'shared_styles':shared_styles} if shared_images or shared_styles else {})}, default=lambda value: value.isoformat() if isinstance(value, (date, datetime)) else value))
    finally:
        connection.rollback()


def required_files(data):
    """核对稳定引用、归属及发布状态，明确哪些完整文件必须存在。"""
    shared={x['asset_id']:x for x in data.get('shared_images',[])}
    for style in data.get('shared_styles',[]):
        for url in style['image_urls']:
            match=re.fullmatch(r'/api/admin/catalog/styles/([1-9][0-9]*)/images/([a-f0-9]{32})',url)
            if not match or int(match[1])!=style['id'] or match[2] not in shared or shared[match[2]]['style_id']!=style['id']:
                raise MediaBackupError('共用款图的引用与数据库元数据不一致。')
    assets, references, items = {}, {}, {row['id']: row for row in data['items']}
    required = {}
    for asset in data['assets']:
        uid = asset['asset_id']
        if asset['state'] not in {'uploading', 'pending', 'attached', 'retired', 'deleting'}:
            raise MediaBackupError('图片生命周期状态非法。')
        if not isinstance(uid, str) or not re.fullmatch('[a-f0-9]{32}', uid) or uid in assets:
            raise MediaBackupError('图片标识重复或非法。')
        key = uid + '.webp'
        if asset['storage_key'] != key or asset['item_id'] not in items:
            raise MediaBackupError('图片文件名或对象归属不一致。')
        url = urlsplit(asset['reference_url'])
        if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password or url.query or url.fragment or url.path != f"/api/tap/items/{asset['item_id']}/images/{uid}":
            raise MediaBackupError('图片稳定引用与元数据不一致。')
        if asset['reference_url'] in references:
            raise MediaBackupError('图片稳定引用重复。')
        assets[uid], references[asset['reference_url']] = asset, asset
        if asset['state'] in {'pending', 'attached', 'retired'}:
            if not isinstance(asset['sha256'], str) or not re.fullmatch('[a-f0-9]{64}', asset['sha256']) or not 0 < asset['byte_size'] <= 8 * 1024**2:
                raise MediaBackupError('完整图片的摘要或大小非法。')
            required[key] = asset
    linked = set()
    for profile in data['profiles']:
        if profile['item_id'] not in items or items[profile['item_id']]['project'] != profile['project']:
            raise MediaBackupError('资料项目与物品不一致。')
        if not isinstance(profile['image_urls'], list):
            raise MediaBackupError('资料图片引用不是数组。')
        for url in profile['image_urls']:
            if not isinstance(url, str):
                raise MediaBackupError('图片引用类型非法。')
            asset = references.get(url)
            if asset:
                if asset['item_id'] != profile['item_id'] or asset['state'] != 'attached':
                    raise MediaBackupError('资料引用了其他物品或非已保存图片。')
                linked.add(asset['asset_id'])
            elif re.fullmatch(r'/api/(?:admin|tap|fashion)/items/[1-9][0-9]*/images/[a-f0-9]{32}', urlsplit(url).path):
                raise MediaBackupError('资料中的自管图片缺少元数据。')
    if any(row['state'] == 'attached' and row['asset_id'] not in linked for row in assets.values()):
        raise MediaBackupError('已保存图片缺少对应资料引用。')
    return required


def verify_files(data, root):
    """摘要、字节、图片格式与尺寸都必须匹配，不仅检查数量。"""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise MediaBackupError('图片目录不存在或为符号链接。')
    required = required_files(data)
    for key, asset in required.items():
        path = root / key
        if digest(path) != asset['sha256'] or path.stat().st_size != asset['byte_size']:
            raise MediaBackupError('图片内容摘要或字节大小不一致。')
        try:
            with Image.open(path) as image:
                if image.format != 'WEBP' or image.size != (asset['width'], asset['height']) or max(image.size) > 2048 or getattr(image, 'n_frames', 1) != 1:
                    raise MediaBackupError('图片格式或尺寸与元数据不一致。')
                image.load()
        except (OSError, ValueError, Image.DecompressionBombError):
            raise MediaBackupError('图片无法完整读取。') from None
    return required


def private_copy(source, destination):
    """只新建私有文件，调用方不会覆盖已有内容。"""
    with Path(destination).open('xb') as stream:
        os.chmod(destination, 0o600)
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(source, flags), 'rb') as original:
            if not stat.S_ISREG(os.fstat(original.fileno()).st_mode):
                raise MediaBackupError('拒绝复制非普通文件。')
            shutil.copyfileobj(original, stream)
        stream.flush()
        os.fsync(stream.fileno())


def create_bundle(connection, media_root, database_dump, destination, *, writes_frozen=False):
    """原生数据库转储须在同一停止写入窗口取得；不运行上传API。"""
    if not writes_frozen:
        raise MediaBackupError('必须先停止上传、图片关联写入和清理并等待在途请求结束。')
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise MediaBackupError('备份目标已存在，未覆盖。')
    data = snapshot(connection)
    required = verify_files(data, media_root)
    dump_hash = digest(database_dump)
    destination.mkdir(mode=0o700)
    try:
        (destination / 'images').mkdir(mode=0o700)
        private_copy(database_dump, destination / 'database.sql')
        for key in required:
            private_copy(Path(media_root) / key, destination / 'images' / key)
        if snapshot(connection) != data or digest(database_dump) != dump_hash:
            raise MediaBackupError('冻结窗口内数据库或转储发生变化，未生成有效备份。')
        verify_files(data, destination / 'images')
        document = {'format_version': 1, 'database_sha256': dump_hash, 'snapshot': data}
        with (destination / 'manifest.json').open('x', encoding='utf-8') as manifest:
            os.chmod(manifest.name, 0o600)
            json.dump(document, manifest, ensure_ascii=False, sort_keys=True)
            manifest.flush()
            os.fsync(manifest.fileno())
        return len(required)
    except Exception:
        # 只清理本函数独占创建的新备份目录；不碰源图、转储或已有目标。
        shutil.rmtree(destination)
        raise


def inspect_bundle(bundle):
    """备份自校验无需数据库或上传服务。"""
    bundle = Path(bundle)
    if bundle.is_symlink():
        raise MediaBackupError('拒绝链接备份目录。')
    digest(bundle / 'manifest.json')
    try:
        document = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
        if document['format_version'] != 1 or digest(bundle / 'database.sql') != document['database_sha256']:
            raise MediaBackupError('数据库转储不属于该备份。')
        verify_files(document['snapshot'], bundle / 'images')
        return document['snapshot']
    except (KeyError, TypeError, ValueError):
        raise MediaBackupError('备份清单结构不完整。') from None


def restore_files(connection, bundle, destination):
    """先用原生数据库工具恢复到隔离目标，再离线核对并还原文件。"""
    data = inspect_bundle(bundle)
    if snapshot(connection) != data:
        raise MediaBackupError('恢复数据库的元数据/引用不属于该文件备份。')
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise MediaBackupError('恢复图片目标已存在，未覆盖。')
    destination.mkdir(mode=0o700)
    try:
        for key in required_files(data):
            private_copy(Path(bundle) / 'images' / key, destination / key)
        verify_files(data, destination)
        if snapshot(connection) != data:
            raise MediaBackupError('恢复过程中数据库发生变化，未宣告成功。')
        return len(required_files(data))
    except Exception:
        shutil.rmtree(destination)
        raise
