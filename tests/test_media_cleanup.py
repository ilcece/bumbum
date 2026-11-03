"""到期技术资源先预览/备份核对，再锁定重查；不删除业务记录或未知文件。"""

from pathlib import Path

import pytest

from core import media_cleanup
from core.db import get_database
from core.media_assets import MediaUnavailable
from core.media_backup import create_bundle
from scripts.migrate_local import backup_database
from tests.test_admin_auth import query
from tests.test_media_assets import media, drafts, upload, save

pytestmark = pytest.mark.auth_database


def bundle(media, auth_database, tmp_path):
    dump = tmp_path / 'private' / 'database.sql'
    backup_database(auth_database['TEST_DOCKER_COMMAND'], auth_database['TEST_CONTAINER'], dump)
    destination = tmp_path / 'bundle'
    with media['app'].app_context():
        create_bundle(get_database(), media['root'], dump, destination, writes_frozen=True)
    return destination


def retire(media):
    result = upload(media).json['data']
    assert save(media, [result['url']]).status_code == 200
    assert save(media, []).status_code == 200
    query(media['app'], 'UPDATE media_asset SET created_at=UTC_TIMESTAMP()-INTERVAL 10 DAY,expires_at=UTC_TIMESTAMP()-INTERVAL 1 DAY WHERE asset_id=%s', (result['asset_id'],))
    return result


def test_preview_apply_backup_and_unknown_files_preserved(media, auth_database, tmp_path):
    result = retire(media)
    protected = media['root'] / 'unproven-original.bin'; protected.write_bytes(b'original')
    backed = bundle(media, auth_database, tmp_path)
    items = query(media['app'], 'SELECT * FROM item')
    profiles = query(media['app'], 'SELECT * FROM fashion_item_profile')
    with media['app'].app_context():
        connection = get_database()
        preview = media_cleanup.cleanup(connection)
        assert len(preview['candidates']) == 1 and preview['deleted'] == 0 and preview['unknown_files_preserved'] == 1
        assert (media['root'] / (result['asset_id'] + '.webp')).exists()
        with pytest.raises(MediaUnavailable, match='配套备份'):
            media_cleanup.cleanup(connection, apply=True)
        applied = media_cleanup.cleanup(connection, apply=True, backup_bundle=backed)
        assert applied['deleted'] == 1 and protected.read_bytes() == b'original'
        assert media_cleanup.cleanup(connection, apply=True, backup_bundle=backed)['deleted'] == 0
    assert not query(media['app'], 'SELECT * FROM media_asset')
    assert query(media['app'], 'SELECT * FROM item') == items and query(media['app'], 'SELECT * FROM fashion_item_profile') == profiles


def test_failed_unlink_remains_deleting_and_retry_is_safe(media, auth_database, tmp_path, monkeypatch):
    result = retire(media)
    backed = bundle(media, auth_database, tmp_path)
    original = Path.unlink
    def fail(path, *args, **kwargs):
        if path.name == result['asset_id'] + '.webp':
            raise OSError('合成文件删除失败')
        return original(path, *args, **kwargs)
    with media['app'].app_context():
        connection = get_database()
        with monkeypatch.context() as changes:
            changes.setattr(Path, 'unlink', fail)
            with pytest.raises(OSError):
                media_cleanup.cleanup(connection, apply=True, backup_bundle=backed)
        assert query(media['app'], 'SELECT state FROM media_asset')[0]['state'] == 'deleting'
        incomplete_root = tmp_path / 'after-deleting'; incomplete_root.mkdir()
        incomplete = bundle(media, auth_database, incomplete_root)
        with pytest.raises(MediaUnavailable, match='配套备份'):
            media_cleanup.cleanup(connection, apply=True, backup_bundle=incomplete)
        assert (media['root'] / (result['asset_id'] + '.webp')).exists()
        assert media_cleanup.cleanup(connection, apply=True, backup_bundle=backed)['deleted'] == 1


@pytest.mark.parametrize('damage', ['symlink', 'hash'])
def test_unproven_file_refuses_cleanup_without_marking_or_deleting(media, auth_database, tmp_path, damage):
    result = retire(media)
    backed = bundle(media, auth_database, tmp_path)
    path = media['root'] / (result['asset_id'] + '.webp')
    if damage == 'symlink':
        path.unlink(); outside = tmp_path / 'outside'; outside.write_bytes(b'outside'); path.symlink_to(outside)
    else:
        path.write_bytes(b'X' * path.stat().st_size)
    with media['app'].app_context():
        with pytest.raises(MediaUnavailable):
            media_cleanup.cleanup(get_database(), apply=True, backup_bundle=backed)
    assert path.exists() and query(media['app'], 'SELECT state FROM media_asset')[0]['state'] == 'retired'
    if damage == 'symlink':
        assert outside.read_bytes() == b'outside'


def test_rechecks_new_attachment_after_preview(media, auth_database, tmp_path, monkeypatch):
    result = retire(media)
    backed = bundle(media, auth_database, tmp_path)
    original = media_cleanup.snapshot
    def changed(connection):
        data = original(connection)
        query(media['app'], "UPDATE media_asset SET state='attached',expires_at=NULL WHERE asset_id=%s", (result['asset_id'],))
        import json
        query(media['app'], 'UPDATE fashion_item_profile SET image_urls=%s', (json.dumps([result['url']]),))
        return data
    monkeypatch.setattr(media_cleanup, 'snapshot', changed)
    with media['app'].app_context():
        assert media_cleanup.cleanup(get_database(), apply=True, backup_bundle=backed)['deleted'] == 0
    assert (media['root'] / (result['asset_id'] + '.webp')).exists()
