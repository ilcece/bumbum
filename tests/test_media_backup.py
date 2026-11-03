"""在专属MySQL及合成图片上演练离线配套恢复，不调用上传服务。"""

import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import uuid

from PIL import Image
import pymysql
import pytest

from core.media_backup import MediaBackupError, create_bundle, digest, inspect_bundle, restore_files, snapshot, verify_files
from tests.test_admin_items import drafts

pytestmark = pytest.mark.auth_database


@pytest.fixture
def media_recovery(auth_database, auth_app, admin_account, drafts, tmp_path):
    config = auth_database
    source = pymysql.connect(host=config['DB_HOST'], port=config['DB_PORT'], user=config['DB_USER'], password=config['DB_PASSWORD'], database=config['DB_NAME'], autocommit=True, init_command="SET time_zone='+00:00'")
    root = tmp_path / 'original-media'
    root.mkdir()
    item_ids, asset_ids = [], []
    for color in ('blue', 'red'):
        asset_id = uuid.uuid4().hex
        key = asset_id + '.webp'
        path = root / key
        Image.new('RGB', (12, 8), color).save(path, format='WEBP')
        sha = digest(path)
        with source.cursor() as cursor:
            uid = 'FASH-2026-' + str(uuid.uuid4().int % 1000000).zfill(6)
            cursor.execute('INSERT INTO item(project_id,item_uid) VALUES (1,%s)', (uid,))
            item_id = cursor.lastrowid
            url = f'https://nfc.example.test/api/tap/items/{item_id}/images/{asset_id}'
            cursor.execute('INSERT INTO fashion_item_profile(item_id,name,image_urls) VALUES (%s,%s,%s)', (item_id, '合成恢复图片', json.dumps([url])))
            cursor.execute("INSERT INTO media_asset(asset_id,item_id,created_by,storage_key,reference_url,byte_size,width,height,source_sha256,sha256,state) VALUES (%s,%s,%s,%s,%s,%s,12,8,%s,%s,'attached')", (asset_id, item_id, admin_account['id'], key, url, path.stat().st_size, sha, sha))
        item_ids.append(item_id)
        asset_ids.append(asset_id)
    command = config['TEST_DOCKER_COMMAND']
    container = config['TEST_CONTAINER']

    def docker(script, data=None):
        result = subprocess.run([*command, 'exec', '-i', container, 'sh', '-c', script], input=data, capture_output=True)
        if result.returncode:
            pytest.fail('专属临时数据库转储/恢复失败；未显示凭证或业务SQL')
        return result.stdout

    target_name = 'bumbum_media_restore_' + uuid.uuid4().hex[:12]
    docker('MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "CREATE DATABASE ' + target_name + '; GRANT ALL ON ' + target_name + '.* TO \'bumbum_auth_test\'@\'%\';"')
    dump = tmp_path / 'database.sql'
    dump.write_bytes(docker('MYSQL_PWD="$MYSQL_PASSWORD" mysqldump --user="$MYSQL_USER" --single-transaction --no-tablespaces --set-gtid-purged=OFF --skip-comments bumbum_digital'))
    dump.chmod(0o600)
    assert b'USE `bumbum_digital`' not in dump.read_bytes()
    bundle = tmp_path / 'bundle'
    assert create_bundle(source, root, dump, bundle, writes_frozen=True) == 2
    docker('MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot --database=' + target_name, (bundle / 'database.sql').read_bytes())
    target = pymysql.connect(host=config['DB_HOST'], port=config['DB_PORT'], user=config['DB_USER'], password=config['DB_PASSWORD'], database=target_name, autocommit=True, init_command="SET time_zone='+00:00'")
    try:
        yield source, target, root, bundle, tmp_path / 'restored-media', asset_ids
    finally:
        target.close()
        docker('MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "DROP DATABASE ' + target_name + ';"')
        with source.cursor() as cursor:
            for item_id in item_ids:
                cursor.execute('DELETE FROM media_asset WHERE item_id=%s', (item_id,))
                cursor.execute('DELETE FROM fashion_item_profile WHERE item_id=%s', (item_id,))
                cursor.execute('DELETE FROM item WHERE id=%s', (item_id,))
        source.close()


def test_native_mysql_and_files_restore_with_uploader_stopped(media_recovery, monkeypatch):
    source, target, original, bundle, destination, _ = media_recovery
    class UnavailableUpload(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(503)
            self.end_headers()
        def log_message(self, *_args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), UnavailableUpload)
    port = server.server_port
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    server.shutdown()
    server.server_close()
    worker.join()
    with pytest.raises(OSError):
        socket.create_connection(('127.0.0.1', port), timeout=.5)
    def forbidden_http(*_args, **_kwargs):
        pytest.fail('离线恢复不得依赖HTTP上传/查询')
    monkeypatch.setattr(http.client.HTTPConnection, 'request', forbidden_http)
    # 原生转储已在另一个新数据库恢复；这里仅离线还原文件并核对实际关联。
    assert snapshot(source) == snapshot(target)
    assert restore_files(target, bundle, destination) == 2
    assert len(verify_files(snapshot(target), destination)) == 2
    assert sorted(digest(p) for p in destination.iterdir()) == sorted(digest(p) for p in original.iterdir())
    config = source
    child_env = {**os.environ, 'APP_ENV': 'development', 'DB_HOST': config.host, 'DB_PORT': str(config.port), 'DB_USER': config.user.decode() if isinstance(config.user, bytes) else config.user,
                 'DB_PASSWORD': config.password.decode() if isinstance(config.password, bytes) else config.password,
                 'DB_NAME': target.db.decode() if isinstance(target.db, bytes) else target.db,
                 'DB_SSL_MODE': 'LOCAL', 'DB_SSL_CA': '', 'HANGZHOU_SLOT': '', 'MEDIA_ENABLED': 'false'}
    offline_target = destination.with_name('cli-restored-media')
    result = subprocess.run([sys.executable, 'scripts/media_backup.py', 'restore-files', '--bundle', str(bundle), '--media-root', str(offline_target)], cwd=Path(__file__).parents[1], env=child_env, capture_output=True, text=True)
    assert result.returncode == 0, '独立离线恢复命令失败；未输出配置或转储正文'
    assert len(verify_files(snapshot(target), offline_target)) == 2


@pytest.mark.parametrize('damage', ['missing', 'content', 'sql', 'path'])
def test_damaged_bundle_refuses_restore_without_touching_target_or_original(media_recovery, damage):
    _, target, original, bundle, destination, assets = media_recovery
    original_hashes = {p.name: digest(p) for p in original.iterdir()}
    broken = bundle.parent / 'broken-bundle'
    shutil.copytree(bundle, broken)
    image = broken / 'images' / (assets[0] + '.webp')
    if damage == 'missing':
        image.unlink()
    elif damage == 'content':
        image.write_bytes(b'corrupt-synthetic-image')
    elif damage == 'sql':
        (broken / 'database.sql').write_bytes(b'wrong-snapshot')
    else:
        manifest = json.loads((broken / 'manifest.json').read_text())
        manifest['snapshot']['assets'][0]['storage_key'] = '../outside.webp'
        (broken / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(MediaBackupError):
        restore_files(target, broken, destination)
    assert not destination.exists()
    assert original_hashes == {p.name: digest(p) for p in original.iterdir()}
    assert len(inspect_bundle(bundle)['assets']) == 2


@pytest.mark.parametrize('mismatch', ['reference', 'owner', 'snapshot_time'])
def test_wrong_metadata_or_snapshot_refuses_files_before_copy(media_recovery, mismatch):
    _, target, _, bundle, destination, assets = media_recovery
    with target.cursor() as cursor:
        if mismatch == 'reference':
            cursor.execute("UPDATE fashion_item_profile SET image_urls=JSON_ARRAY('https://external.example.test/other.webp') WHERE item_id=(SELECT item_id FROM media_asset WHERE asset_id=%s)", (assets[0],))
        elif mismatch == 'owner':
            cursor.execute('UPDATE media_asset SET item_id=(SELECT other.item_id FROM (SELECT item_id FROM media_asset WHERE asset_id=%s) other) WHERE asset_id=%s', (assets[1], assets[0]))
        else:
            cursor.execute('UPDATE media_asset SET created_at=DATE_SUB(created_at,INTERVAL 1 SECOND) WHERE asset_id=%s', (assets[0],))
    with pytest.raises(MediaBackupError, match='元数据/引用'):
        restore_files(target, bundle, destination)
    assert not destination.exists()


def test_existing_destination_never_overwritten(media_recovery):
    _, target, _, bundle, destination, _ = media_recovery
    destination.mkdir()
    sentinel = destination / 'unrelated.txt'
    sentinel.write_text('保留现有内容')
    with pytest.raises(MediaBackupError, match='已存在'):
        restore_files(target, bundle, destination)
    assert sentinel.read_text() == '保留现有内容'


def test_missing_source_symlink_and_unfrozen_backup_are_rejected(media_recovery):
    source, _, original, bundle, destination, assets = media_recovery
    with pytest.raises(MediaBackupError, match='停止上传'):
        create_bundle(source, original, bundle / 'database.sql', destination)
    path = original / (assets[0] + '.webp')
    path.unlink()
    path.symlink_to(bundle / 'images' / path.name)
    with pytest.raises(MediaBackupError, match='不是普通文件'):
        create_bundle(source, original, bundle / 'database.sql', destination, writes_frozen=True)
    assert not destination.exists()


def test_mysql_constraints_and_migration_match_empty_schema(media_recovery):
    source, _, _, _, _, assets = media_recovery
    for sql in ['UPDATE media_asset SET byte_size=0 WHERE asset_id=%s', 'UPDATE media_asset SET width=2049 WHERE asset_id=%s', "UPDATE media_asset SET expires_at=CURRENT_TIMESTAMP(6) WHERE asset_id=%s", 'UPDATE media_asset SET item_id=18446744073709551615 WHERE asset_id=%s']:
        with source.cursor() as cursor, pytest.raises(pymysql.MySQLError):
            cursor.execute(sql, (assets[0],))
    with source.cursor() as cursor:
        cursor.execute('SHOW CREATE TABLE media_asset')
        actual = cursor.fetchone()[1]
        cursor.execute('DROP TABLE media_asset')
        ddl = (Path(__file__).parents[1] / 'db/migrations/005_media_assets.sql').read_text()
        cursor.execute('SET NAMES utf8mb4')
        cursor.execute('CREATE TABLE' + ddl.split('CREATE TABLE', 1)[1])
        cursor.execute('SHOW CREATE TABLE media_asset')
        assert cursor.fetchone()[1] == actual
