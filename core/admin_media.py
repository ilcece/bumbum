"""单一multipart上传入口；使用MySQL预留限制跨worker处理及容量。"""

from datetime import timedelta
import hashlib
from io import BytesIO
import os
from pathlib import Path
import shutil
import tempfile
import warnings

from flask import Blueprint, current_app, g, jsonify, request, send_file
from PIL import Image, ImageOps, UnidentifiedImageError, WebPImagePlugin
import pymysql
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.formparser import FormDataParser, MultiPartParser

from core.admin_auth import AuthRequestError, lock_admin_session
from core.admin_items import locked_fashion_item
from core.admin_queries import consistent_read
from core.chip_binding import valid_id
from core.db import get_database
from core.diagnostics import record_failure
from core.media_assets import (ASSET_ID, MAX_FILE, MAX_PIXELS, MAX_WEBP_PIXELS, MediaUnavailable, asset_for_read, asset_payload,
                               conflict, database_now, image_url, init_media_settings, media_root, open_asset, sync_directory)

blueprint = Blueprint('admin_media', __name__, url_prefix='/api/admin/items')
# Pillow的硬拒绝阈值是此值的两倍，令超16MP的WebP在分配解码画布前失败。
Image.MAX_IMAGE_PIXELS = MAX_PIXELS // 2


class MediaBusy(Exception):
    """环境已有处理中的上传；不排后台队列。"""


class UploadFormDataParser(FormDataParser):
    """沿用Werkzeug解析器，小块读取以保留64KiB文字限制而不误拒文件流。"""

    def _parse_multipart(self, stream, mimetype, content_length, options):
        parser = MultiPartParser(stream_factory=self.stream_factory, max_form_memory_size=self.max_form_memory_size,
                                 max_form_parts=self.max_form_parts, cls=self.cls, buffer_size=16 * 1024)
        boundary = options.get('boundary', '').encode('ascii')
        if not boundary:
            raise ValueError('缺少multipart边界。')
        form, files = parser.parse(stream, boundary, content_length)
        return stream, form, files


def require_item_id(item_id):
    if not valid_id(item_id) or request.args:
        raise AuthRequestError(400, 'invalid_param', '物品ID无效或包含未约定查询参数。')


def reserve(item_id, asset_id, digest):
    root = media_root(writable=True)
    maximum = current_app.config.get('MEDIA_MAX_TOTAL_BYTES')
    if current_app.config.get('MEDIA_ENABLED') is not True or type(maximum) is not int or maximum < 1:
        raise MediaUnavailable('图片上传未启用或容量配置未就绪。')
    connection = get_database()
    connection.begin()
    locked = False
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT GET_LOCK(CONCAT(DATABASE(),':media-admission'),0) AS acquired")
            locked = cursor.fetchone()['acquired'] == 1
            if not locked:
                raise MediaBusy
            lock_admin_session(cursor)
            locked_fashion_item(cursor, item_id)
            now = database_now(cursor)
            cursor.execute('SELECT * FROM media_asset WHERE asset_id=%s FOR UPDATE', (asset_id,))
            asset = cursor.fetchone()
            if asset:
                if asset['item_id'] != item_id or asset['created_by'] != g.admin_session['admin_id'] or asset['source_sha256'] != digest:
                    conflict('上传标识已被其他文件或对象使用。')
                if asset['state'] not in {'pending', 'attached'} or (asset['expires_at'] is not None and asset['expires_at'] <= now):
                    conflict('此上传仍在处理或已过期，请先查询结果。')
                with open_asset(asset, verify_hash=True):
                    pass
                result = asset_payload(asset, now)
                connection.commit()
                return result, None
            cursor.execute("SELECT COUNT(*) AS n FROM media_asset WHERE state='uploading' AND expires_at>%s", (now,))
            if cursor.fetchone()['n']:
                raise MediaBusy
            cursor.execute("SELECT COUNT(*) AS n FROM media_asset WHERE created_by=%s AND state IN ('uploading','pending')", (g.admin_session['admin_id'],))
            if cursor.fetchone()['n'] >= 20:
                raise AuthRequestError(409, 'media_quota_exceeded', '未完成或暂存图片已达20张，请先保存或按维护步骤处理到期暂存。')
            cursor.execute('SELECT COALESCE(SUM(GREATEST(byte_size,reserved_bytes)),0) AS total FROM media_asset')
            if int(cursor.fetchone()['total']) + MAX_FILE > maximum:
                raise AuthRequestError(409, 'media_quota_exceeded', '图片容量不足，未接收新文件。')
            if shutil.disk_usage(root).free < MAX_FILE:
                raise MediaUnavailable('图片磁盘可用空间不足。')
            if os.path.lexists(root / (asset_id + '.webp')) or any(root.glob('.' + asset_id + '-*.tmp')):
                conflict('此标识已有待核对文件，请使用新标识，不覆盖原文件。')
            cursor.execute("""INSERT INTO media_asset(asset_id,item_id,created_by,storage_key,reference_url,source_sha256,state,reserved_bytes,created_at,updated_at,expires_at)
                VALUES (%s,%s,%s,%s,%s,%s,'uploading',%s,%s,%s,%s)""",
                (asset_id, item_id, g.admin_session['admin_id'], asset_id + '.webp', image_url(item_id, asset_id, 'tap'), digest,
                 MAX_FILE, now, now, now + timedelta(minutes=10)))
        connection.commit()
        return None, now
    except Exception:
        connection.rollback()
        raise
    finally:
        if locked:
            with connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(CONCAT(DATABASE(),':media-admission'))")


def encode_image(raw):
    """完整解码静态图片，按方向缩小并重编码；不保存原文件或元数据。"""
    try:
        with warnings.catch_warnings():
            # 8–16MP的警告由下方明确上限接管；超16MP仍由Pillow硬拒绝。
            warnings.simplefilter('ignore', Image.DecompressionBombWarning)
            if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
                # 锁定Pillow13的头部尺寸识别在分配WebP解码画布前执行；不自行解码。
                size = WebPImagePlugin._get_size(raw[:30])
                if size is None or size[0] * size[1] > MAX_WEBP_PIXELS:
                    raise ValueError
            with Image.open(BytesIO(raw)) as image:
                limit = MAX_WEBP_PIXELS if image.format == 'WEBP' else MAX_PIXELS
                if image.format not in {'JPEG', 'PNG', 'WEBP'} or image.width * image.height > limit or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError
                image.load()
                image.thumbnail((2048, 2048), reducing_gap=3.0)
                # 先缩小再旋转，避免方向修正同时持有两份1600万像素图像。
                ImageOps.exif_transpose(image, in_place=True)
                if image.mode not in {'RGB', 'RGBA'}:
                    image = image.convert('RGBA' if 'transparency' in image.info or 'A' in image.getbands() else 'RGB')
                image.info.clear()
                output = BytesIO()
                image.save(output, format='WEBP', quality=85, method=4)
                encoded, size = output.getvalue(), image.size
        if not 0 < len(encoded) <= MAX_FILE:
            raise ValueError
        return encoded, size
    except (UnidentifiedImageError, OSError, EOFError, SyntaxError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise AuthRequestError(400, 'invalid_param', '请选择完整静态JPEG/PNG（最多1600万像素）或WebP（最多800万像素），单张8MiB；不接受损坏或多帧图片。') from None


def stage_encoded(item_id, asset_id, encoded, size, lease):
    """先记录未发布输出摘要，便于中断后核验本次文件归属。"""
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            lock_admin_session(cursor)
            locked_fashion_item(cursor, item_id)
            now = database_now(cursor)
            cursor.execute('SELECT * FROM media_asset WHERE asset_id=%s FOR UPDATE', (asset_id,))
            asset = cursor.fetchone()
            if not asset or asset['state'] != 'uploading' or asset['item_id'] != item_id or asset['created_by'] != g.admin_session['admin_id'] or asset['created_at'] != lease or asset['expires_at'] <= now:
                conflict('上传预留已失效，未写入图片。')
            cursor.execute('UPDATE media_asset SET byte_size=%s,width=%s,height=%s,sha256=%s,updated_at=%s WHERE asset_id=%s',
                           (len(encoded), size[0], size[1], hashlib.sha256(encoded).hexdigest(), now, asset_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def publish_file(root, asset_id, encoded, proof):
    path = None
    try:
        descriptor, filename = tempfile.mkstemp(prefix='.' + asset_id + '-', suffix='.tmp', dir=root)
        path = Path(filename)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # 只创建新名字，不覆盖已有文件或符号链接；完成后再发布元数据。
        info = path.stat()
        os.link(path, root / (asset_id + '.webp'), follow_symlinks=False)
        proof['inode'] = (info.st_dev, info.st_ino)
        path.unlink()
        path = None
        sync_directory(root)
    except OSError:
        raise MediaUnavailable('图片写入失败，请核对存储。') from None
    finally:
        if path is not None and not path.is_symlink():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def finish(item_id, asset_id, encoded, size, lease):
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            lock_admin_session(cursor)
            locked_fashion_item(cursor, item_id)
            now = database_now(cursor)
            cursor.execute('SELECT * FROM media_asset WHERE asset_id=%s FOR UPDATE', (asset_id,))
            asset = cursor.fetchone()
            if not asset or asset['item_id'] != item_id or asset['created_by'] != g.admin_session['admin_id'] or asset['state'] != 'uploading' or asset['created_at'] != lease or asset['expires_at'] <= now:
                conflict('上传预留已失效，未发布图片。')
            cursor.execute("UPDATE media_asset SET state='pending',byte_size=%s,width=%s,height=%s,sha256=%s,reserved_bytes=0,updated_at=%s,expires_at=%s WHERE asset_id=%s",
                           (len(encoded), size[0], size[1], hashlib.sha256(encoded).hexdigest(), now, now + timedelta(hours=24), asset_id))
            cursor.execute('SELECT * FROM media_asset WHERE asset_id=%s', (asset_id,))
            result = asset_payload(cursor.fetchone(), now)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise


def discard_failed(item_id, asset_id, proof):
    """只回收本次仍未发布的预留；未知提交结果必须先查实际状态。"""
    connection = get_database()
    try:
        connection.begin()
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute('SELECT id FROM item WHERE id=%s FOR UPDATE', (item_id,))
            cursor.execute('SELECT * FROM media_asset WHERE asset_id=%s FOR UPDATE', (asset_id,))
            asset = cursor.fetchone()
            if asset and (asset['state'] != 'uploading' or asset['item_id'] != item_id or asset['created_by'] != g.admin_session['admin_id'] or asset['created_at'] != proof['lease']):
                connection.rollback()
                return
            if asset is None:
                # 清理与晚到请求相遇时，仅回收本请求已证明创建且未被引用的文件。
                from core.media_cleanup import unreferenced
                unreferenced(cursor, {'asset_id': asset_id, 'reference_url': image_url(item_id, asset_id, 'tap')})
            root = media_root(writable=True)
            path = root / (asset_id + '.webp')
            if path.is_symlink():
                connection.rollback()
                return
            if path.exists():
                info = path.stat(follow_symlinks=False)
                if proof.get('inode') != (info.st_dev, info.st_ino):
                    connection.rollback()
                    return
                path.unlink()
                sync_directory(root)
            if any(root.glob('.' + asset_id + '-*.tmp')):
                connection.rollback()
                return
            if asset:
                cursor.execute("DELETE FROM media_asset WHERE asset_id=%s AND state='uploading' AND created_at=%s", (asset_id, proof['lease']))
        connection.commit()
    except Exception:
        connection.rollback()
        # 数据库不可核对时保留元数据和文件，由受控维护处理；不覆盖原错误。


@blueprint.post('/<int:item_id>/images')
def upload_image(item_id):
    require_item_id(item_id)
    if current_app.config.get('MEDIA_ENABLED') is not True:
        raise MediaUnavailable('图片上传未启用。')
    request.max_content_length = 9 * 1024**2
    request.max_form_memory_size = 64 * 1024
    request.max_form_parts = 2
    request.form_data_parser_class = UploadFormDataParser
    try:
        if set(request.files) != {'file'} or len(request.files.getlist('file')) != 1 or set(request.form) != {'client_upload_id'} or len(request.form.getlist('client_upload_id')) != 1:
            raise AuthRequestError(400, 'invalid_param', '仅接受一个file和一个client_upload_id。')
        asset_id = request.form['client_upload_id']
        if not ASSET_ID.fullmatch(asset_id):
            raise AuthRequestError(400, 'invalid_param', '上传标识须为32位小写随机十六进制。')
        raw = request.files['file'].stream.read(MAX_FILE + 1)
        if not raw or len(raw) > MAX_FILE:
            raise AuthRequestError(413, 'payload_too_large', '单张图片须为1字节至8MiB。')
    except RequestEntityTooLarge:
        raise AuthRequestError(413, 'payload_too_large', '上传总正文超过9MiB、表单64KiB或2部分限制。') from None
    existing, lease = reserve(item_id, asset_id, hashlib.sha256(raw).hexdigest())
    if existing:
        return jsonify(status='ok', data=existing)
    proof = {'lease': lease}
    try:
        encoded, size = encode_image(raw)
        stage_encoded(item_id, asset_id, encoded, size, lease)
        publish_file(media_root(writable=True), asset_id, encoded, proof)
        result = finish(item_id, asset_id, encoded, size, lease)
    except Exception:
        discard_failed(item_id, asset_id, proof)
        raise
    return jsonify(status='ok', data=result)


@blueprint.get('/<int:item_id>/images/<asset_id>/status')
def upload_status(item_id, asset_id):
    require_item_id(item_id)
    if not ASSET_ID.fullmatch(asset_id):
        raise AuthRequestError(404, 'not_found', '上传记录不存在。')
    with consistent_read() as cursor:
        cursor.execute('SELECT * FROM media_asset WHERE item_id=%s AND asset_id=%s', (item_id, asset_id))
        asset = cursor.fetchone()
        if not asset:
            raise AuthRequestError(404, 'not_found', '上传记录不存在。')
        if asset['created_by'] != g.admin_session['admin_id']:
            asset_for_read(cursor, item_id, asset_id)
        result = asset_payload(asset, database_now(cursor))
    return jsonify(status='ok', data=result)


def image_response(asset):
    stream = open_asset(asset)
    response = send_file(stream, mimetype='image/webp', download_name=asset['asset_id'] + '.webp',
                         as_attachment=False, conditional=False, etag=False, max_age=0)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.call_on_close(stream.close)
    return response


@blueprint.get('/<int:item_id>/images/<asset_id>')
def admin_image(item_id, asset_id):
    require_item_id(item_id)
    with consistent_read() as cursor:
        asset = asset_for_read(cursor, item_id, asset_id, admin_id=g.admin_session['admin_id'])
    return image_response(asset)


def init_media(app):
    init_media_settings(app)
    app.register_blueprint(blueprint)

    @app.errorhandler(MediaUnavailable)
    def unavailable(error):
        return jsonify(status='error', code='service_unavailable', message=str(error), error_id=record_failure(error)), 503

    @app.errorhandler(MediaBusy)
    def busy(_error):
        response = jsonify(status='error', code='rate_limited', message='已有图片正在处理，请稍后手动重试。')
        response.headers['Retry-After'] = '2'
        return response, 429
