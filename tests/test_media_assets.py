"""真实HTTP/文件/MySQL验证私有图片暂存、原子关联、并发及失败恢复。"""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import os
from pathlib import Path
from threading import Event
import uuid

from PIL import Image
import pymysql
import pytest

from app import create_app
from core import admin_media
from core.admin_auth import COOKIE_NAME
from tests.test_admin_auth import ORIGIN, query
from tests.test_admin_items import drafts, create

pytestmark = pytest.mark.auth_database


@pytest.fixture
def media(auth_app, drafts, tmp_path):
    root = tmp_path / 'media'
    root.mkdir(mode=0o700)
    auth_app.config.update(MEDIA_ENABLED=True, MEDIA_ROOT=str(root), MEDIA_MAX_TOTAL_BYTES=2 * 1024**3,
                           PUBLIC_ORIGIN='http://127.0.0.1:5175')
    item = create(drafts).json['data']
    return {'app': auth_app, 'client': drafts[0], 'headers': drafts[1], 'root': root, 'item': item['id']}


def picture(format='PNG', size=(320, 180), mode='RGB'):
    output = BytesIO()
    image = Image.new(mode, size, (25, 140, 80, 100) if mode == 'RGBA' else (25, 140, 80))
    image.save(output, format=format)
    return output.getvalue()


def upload(media, raw=None, *, asset_id=None, item_id=None, client=None, headers=None):
    return (client or media['client']).post(f"/api/admin/items/{item_id or media['item']}/images",
        data={'client_upload_id': asset_id or uuid.uuid4().hex, 'file': (BytesIO(raw if raw is not None else picture()), '../../不应持久化的原名.png', 'application/octet-stream')},
        headers=headers or media['headers'])


def save(media, urls, **extra):
    return media['client'].patch(f"/api/admin/items/{media['item']}", json={'profile': {'name': '测试服装', 'image_urls': urls}, **extra}, headers=media['headers'])


def test_upload_pending_preview_atomic_attach_retire_and_disabled(media):
    response = upload(media)
    assert response.status_code == 200, response.json
    result = response.json['data']; path = '/api/admin/items/' + str(media['item']) + '/images/' + result['asset_id']
    assert result['state'] == 'pending' and not result['expired']
    assert query(media['app'], 'SELECT * FROM fashion_item_profile') == ()
    found = media['client'].get(path)
    assert found.status_code == 200 and found.mimetype == 'image/webp'
    assert found.headers['X-Content-Type-Options'] == 'nosniff' and found.headers['Cache-Control'] == 'no-store'
    with Image.open(BytesIO(found.data)) as image:
        assert image.size == (320, 180) and image.format == 'WEBP' and not image.info.get('exif')
    assert len(list(media['root'].iterdir())) == 1
    assert media['app'].test_client().get(path).status_code == 401
    assert media['client'].get(f"/api/tap/items/{media['item']}/images/{result['asset_id']}").status_code == 403
    assert save(media, [result['url']], sku_code='一起保存').status_code == 200
    asset = query(media['app'], 'SELECT * FROM media_asset')[0]
    assert asset['state'] == 'attached' and asset['expires_at'] is None and asset['reserved_bytes'] == 0
    detail = media['client'].get(f"/api/admin/items/{media['item']}").json['data']
    assert detail['profile']['image_urls'] == [result['preview_url']]
    assert detail['sku_code'] == '一起保存'
    stored = json.loads(query(media['app'], 'SELECT image_urls FROM fashion_item_profile')[0]['image_urls'])
    assert stored == [result['url']]
    # 后续保存读取方的预览URL会归一为同一稳定引用，并且不重复审计。
    audits = len(query(media['app'], "SELECT * FROM admin_audit WHERE action='item.details.update'"))
    assert save(media, [result['preview_url']], sku_code='一起保存').status_code == 200
    assert len(query(media['app'], "SELECT * FROM admin_audit WHERE action='item.details.update'")) == audits
    media['app'].config['MEDIA_ENABLED'] = False
    assert media['client'].get(path).status_code == 200 and upload(media).status_code == 503
    assert save(media, []).status_code == 200
    assert query(media['app'], 'SELECT state FROM media_asset')[0]['state'] == 'retired'
    assert media['client'].get(path).status_code == 403 and len(list(media['root'].iterdir())) == 1
    assert save(media, [result['url']]).status_code == 409


@pytest.mark.parametrize('format,mode', [('JPEG','RGB'), ('PNG','RGBA'), ('WEBP','RGBA')])
def test_actual_format_and_transparency(media, format, mode):
    response = upload(media, picture(format, mode=mode))
    assert response.status_code == 200, response.json
    data = response.json['data']
    with Image.open(media['root'] / (data['asset_id'] + '.webp')) as image:
        assert image.format == 'WEBP' and image.getexif() == {}
        if mode == 'RGBA':
            assert image.mode == 'RGBA' and image.getpixel((10,10))[3] == 100
    asset = query(media['app'], 'SELECT * FROM media_asset')[0]
    assert asset['source_sha256'] != asset['sha256'] or format == 'WEBP'


def test_orientation_resize_metadata_removal_and_large_multipart(media):
    image = Image.new('RGB', (3000,1200), 'red')
    exif = image.getexif(); exif[274] = 6; exif[315] = '合成私有元数据'
    source = BytesIO(); image.save(source, 'JPEG', exif=exif)
    result = upload(media, source.getvalue()).json['data']
    with Image.open(media['root'] / (result['asset_id'] + '.webp')) as image:
        assert image.size == (819,2048) and not image.info.get('exif') and not image.info.get('icc_profile')
    # 有效文件超过解析器常用缓冲区，仍应接受，而非把文件流误当表单文字。
    image = Image.frombytes('RGB', (640,640), os.urandom(640 * 640 * 3))
    source = BytesIO(); image.save(source, 'PNG')
    assert len(source.getvalue()) > 512 * 1024
    response = upload(media, source.getvalue())
    assert response.status_code == 200, response.json


@pytest.mark.parametrize('raw', [b'<svg xmlns="http://www.w3.org/2000/svg"/>', b'not an image', picture()[:40], picture('WEBP')[:-5], picture('GIF')])
def test_bad_files_release_own_reservation(media, raw):
    response = upload(media, raw)
    assert response.status_code == 400
    assert not query(media['app'], 'SELECT * FROM media_asset') and not list(media['root'].iterdir())


def test_animation_oversize_and_part_limits(media):
    source = BytesIO()
    Image.new('RGB', (2,2), 'red').save(source, 'WEBP', save_all=True, append_images=[Image.new('RGB',(2,2),'blue')], duration=100, loop=0)
    assert upload(media, source.getvalue()).status_code == 400
    assert upload(media, b'x' * (8 * 1024**2 + 1)).status_code == 413
    client, headers = media['client'], media['headers']
    assert client.post(f"/api/admin/items/{media['item']}/images", data={'client_upload_id': uuid.uuid4().hex, 'other': 'x', 'file': (BytesIO(picture()), 'x')}, headers=headers).status_code == 413
    assert client.post(f"/api/admin/items/{media['item']}/images", data={'client_upload_id': 'x' * (64 * 1024 + 1), 'file': (BytesIO(picture()), 'x')}, headers=headers).status_code == 413


def test_webp_pixel_limit_rejects_before_pillow_decoder(media,monkeypatch):
    raw = picture('WEBP',size=(4000,2001),mode='RGBA')
    monkeypatch.setattr(admin_media.Image,'open',lambda *_args,**_kw: pytest.fail('超限WebP不应分配解码画布'))
    assert upload(media,raw).status_code == 400
    assert not query(media['app'],'SELECT * FROM media_asset')


def test_nonce_reuse_unknown_finish_does_not_delete_published_file(media, monkeypatch):
    uid, raw = uuid.uuid4().hex, picture()
    original = admin_media.finish
    def lost(*args):
        original(*args)
        raise pymysql.OperationalError('合成成功回执丢失')
    with monkeypatch.context() as changes:
        changes.setattr(admin_media, 'finish', lost)
        assert upload(media, raw, asset_id=uid).status_code == 503
    status = media['client'].get(f"/api/admin/items/{media['item']}/images/{uid}/status")
    assert status.status_code == 200 and status.json['data']['state'] == 'pending'
    path = media['root'] / (uid + '.webp'); inode = path.stat().st_ino
    assert upload(media, raw, asset_id=uid).status_code == 200 and path.stat().st_ino == inode
    assert upload(media, picture(size=(20,10)), asset_id=uid).status_code == 409
    assert len(query(media['app'], 'SELECT * FROM media_asset')) == 1


@pytest.mark.parametrize('replacement', [False,True])
def test_late_uploader_rechecks_lease_and_only_removes_its_own_unpublished_file(media,monkeypatch,replacement):
    original = admin_media.publish_file
    def interrupted(root,asset_id,encoded,proof):
        original(root,asset_id,encoded,proof)
        # 模拟处理租约到期后维护已清掉预留，或同标识已进入新的处理代次。
        if replacement:
            query(media['app'],'UPDATE media_asset SET created_at=DATE_ADD(created_at,INTERVAL 1 MICROSECOND) WHERE asset_id=%s',(asset_id,))
        else:
            query(media['app'],'DELETE FROM media_asset WHERE asset_id=%s',(asset_id,))
    monkeypatch.setattr(admin_media,'publish_file',interrupted)
    response = upload(media)
    assert response.status_code == 409
    assets = query(media['app'],'SELECT * FROM media_asset')
    assert len(assets) == len(list(media['root'].iterdir())) == int(replacement)
    assert not query(media['app'],'SELECT * FROM fashion_item_profile')


def test_cross_app_processing_admission_is_shared_in_mysql(media, monkeypatch):
    entered, release = Event(), Event()
    original = admin_media.encode_image
    def hold(raw):
        entered.set()
        assert release.wait(10)
        return original(raw)
    monkeypatch.setattr(admin_media, 'encode_image', hold)
    other_app = create_app(dict(media['app'].config))
    second = other_app.test_client()
    token = media['client'].get_cookie(COOKIE_NAME, path='/api/admin').value
    second.set_cookie(COOKIE_NAME, token, path='/api/admin')
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(upload, media)
        try:
            assert entered.wait(5)
            response = upload(media, client=second)
            assert response.status_code == 429 and response.headers['Retry-After'] == '2'
        finally:
            release.set()
        assert first.result(timeout=10).status_code == 200
    assert len(query(media['app'], 'SELECT * FROM media_asset')) == 1


def test_quota_ownership_archive_csrf_and_symlink(media, tmp_path, monkeypatch):
    uid = uuid.uuid4().hex
    path = f"/api/admin/items/{media['item']}/images"
    # 来源/会话/CSRF必须在正文解析前生效。
    from flask.wrappers import Request
    with monkeypatch.context() as changes:
        changes.setattr(Request, '_load_form_data', lambda _request: (_ for _ in ()).throw(AssertionError('不应解析')))
        assert upload(media, headers=ORIGIN).status_code == 403
        assert upload(media, client=media['app'].test_client()).status_code == 401
    assert media['client'].post(path, json={}, headers=media['headers']).status_code == 400
    media['app'].config['MEDIA_MAX_TOTAL_BYTES'] = 8 * 1024**2 - 1
    assert upload(media).json['code'] == 'media_quota_exceeded'
    media['app'].config['MEDIA_MAX_TOTAL_BYTES'] = 2 * 1024**3
    outside = tmp_path / 'outside'; outside.write_bytes(b'original')
    (media['root'] / (uid + '.webp')).symlink_to(outside)
    assert upload(media, asset_id=uid).status_code == 409 and outside.read_bytes() == b'original'
    (media['root'] / (uid + '.webp')).unlink()
    result = upload(media).json['data']
    source = media['root'] / (result['asset_id'] + '.webp')
    source.unlink(); source.symlink_to(outside)
    assert media['client'].get('/api/admin/items/' + str(media['item']) + '/images/' + result['asset_id']).status_code == 503
    assert save(media, [result['url']], sku_code='不应保存').status_code == 503
    assert query(media['app'], 'SELECT sku_code FROM item')[0]['sku_code'] is None
    assert query(media['app'], 'SELECT state FROM media_asset')[0]['state'] == 'pending'
    query(media['app'], "UPDATE item SET status='archived' WHERE id=%s", (media['item'],))
    assert upload(media).status_code == 409


def test_pending_owner_cross_item_expiry_and_association_rollback(media, monkeypatch):
    from tests.test_chip_binding import second_session
    second, headers = second_session(media['app'])
    result = upload(media).json['data']; uid = result['asset_id']
    path = f"/api/admin/items/{media['item']}/images/{uid}"
    assert second.get(path).status_code == 403 and second.get(path + '/status').status_code == 403
    assert second.patch(f"/api/admin/items/{media['item']}", json={'profile': {'name': '不能占用', 'image_urls': [result['url']]}}, headers=headers).status_code == 409
    other = media['client'].post('/api/admin/items', json={'project': 'fashion', 'item_uid': 'FASH-2026-000002'}, headers=media['headers']).json['data']['id']
    assert media['client'].patch(f'/api/admin/items/{other}', json={'profile': {'name': '其他物品', 'image_urls': [result['url']]}}, headers=media['headers']).status_code == 409
    original = pymysql.cursors.DictCursor.execute
    def fail(cursor, sql, args=None):
        if sql.startswith('INSERT INTO admin_audit'):
            raise pymysql.OperationalError('合成审计失败')
        return original(cursor, sql, args)
    with monkeypatch.context() as changes:
        changes.setattr(pymysql.cursors.DictCursor, 'execute', fail)
        assert save(media, [result['url']], sku_code='不得部分成功').status_code == 503
    assert query(media['app'], 'SELECT state FROM media_asset')[0]['state'] == 'pending'
    assert not query(media['app'], 'SELECT * FROM fashion_item_profile')
    assert save(media, [result['url']]).status_code == 200 and second.get(path).status_code == 200
    assert second.get(path + '/status').status_code == 200
    assert media['client'].get(f'/api/admin/items/{other}/images/{uid}').status_code == 404
    pending = upload(media).json['data']
    query(media['app'], "UPDATE media_asset SET created_at=UTC_TIMESTAMP()-INTERVAL 3 DAY,expires_at=UTC_TIMESTAMP()-INTERVAL 1 DAY WHERE asset_id=%s", (pending['asset_id'],))
    assert save(media, [result['url'], pending['url']]).status_code == 409
    assert media['client'].get(f"/api/admin/items/{media['item']}/images/{pending['asset_id']}/status").json['data']['expired'] is True


def prepare_public(media, urls):
    from tests.test_chip_keys import configure, generated, confirmation
    configure(media['app'])
    session = media['client'], media['headers']
    source = session[0].post('/api/admin/chips', json={'chip_uid': '04:11:22:33:44:55:66'}, headers=session[1]).json['data']['chip']
    assert session[0].post(f"/api/admin/chips/{source['id']}/bind-item", json={'item_id': media['item']}, headers=session[1]).status_code == 200
    keyed = session, source
    keys = generated(media['app'], keyed)
    assert session[0].post(f"/api/admin/chips/{source['id']}/confirm-provisioning", json=confirmation(keyed, keys), headers=session[1]).status_code == 200
    assert save(media, urls).status_code == 200
    assert session[0].patch(f"/api/admin/items/{media['item']}", json={'status': 'active'}, headers=session[1]).status_code == 200
    return source, keys


def test_twenty_images_cookie_and_short_grant_do_not_renew_or_count(media):
    from tests.test_chip_keys import reading
    from tests.test_tap_verification import counts
    from urllib.parse import urlsplit
    images = [upload(media).json['data'] for _ in range(20)]
    source, keys = prepare_public(media, [image['url'] for image in images])
    user = media['app'].test_client()
    response = user.post('/api/tap/verify', json={**reading(keys, source['chip_uid'], 9), 'browser_view': True}, headers={'Origin': 'http://127.0.0.1:5175'})
    assert response.status_code == 200
    data = response.json['data']
    assert data['verified'] and data['item_detail']['image_urls'] == [image['url'] for image in images]
    grants = query(media['app'], 'SELECT * FROM tap_grant ORDER BY id')
    counted = counts(media['app'])
    before = query(media['app'], 'SELECT last_verified_counter FROM chip')
    for image in images:
        assert user.get(urlsplit(image['url']).path).status_code == 200
        path = f"/api/fashion/items/{media['item']}/images/{image['asset_id']}"
        assert user.get(path, headers={'X-Tap-Token': data['tap_token']}).status_code == 200
    assert query(media['app'], 'SELECT * FROM tap_grant ORDER BY id') == grants
    assert counts(media['app']) == counted and query(media['app'], 'SELECT last_verified_counter FROM chip') == before
    assert user.get(urlsplit(images[0]['url']).path, headers={'Origin': 'https://other.example'}).status_code == 403
    assert user.get(urlsplit(images[0]['url']).path, headers={'Sec-Fetch-Site': 'same-site'}).status_code == 403
    assert user.get(urlsplit(images[0]['url']).path + '?token=not-allowed').status_code == 400
    detail = user.get(f"/api/fashion/items/{media['item']}/detail", headers={'X-Tap-Token': data['tap_token']}).json['data']
    assert all('/api/fashion/' in url for url in detail['profile']['image_urls'])


@pytest.mark.parametrize('reason', ['disabled', 'lost', 'unbound', 'unprovisioned', 'expired', 'wrong_item'])
def test_public_images_recheck_current_qualification_without_mutation(media, reason):
    from datetime import timedelta
    from tests.test_chip_keys import reading
    result = upload(media).json['data']
    source, keys = prepare_public(media, [result['url']])
    user = media['app'].test_client()
    response = user.post('/api/tap/verify', json={**reading(keys, source['chip_uid'], 9), 'browser_view': True}, headers={'Origin': 'http://127.0.0.1:5175'})
    assert response.json['data']['verified']
    before = query(media['app'], 'SELECT * FROM tap_grant ORDER BY id')
    item_id = media['item']
    if reason == 'disabled': query(media['app'], "UPDATE item SET status='disabled'")
    elif reason == 'lost': query(media['app'], "UPDATE chip SET chip_status='lost'")
    elif reason == 'unbound': query(media['app'], "UPDATE chip SET item_id=NULL,chip_status='pending'")
    elif reason == 'unprovisioned': query(media['app'], "UPDATE chip SET provisioned_at=NULL")
    elif reason == 'expired': media['app'].test_clock[0] += timedelta(hours=24)
    elif reason == 'wrong_item': item_id += 1
    assert user.get(f"/api/tap/items/{item_id}/images/{result['asset_id']}").status_code in {403,409}
    assert query(media['app'], 'SELECT * FROM tap_grant ORDER BY id') == before
