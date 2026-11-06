"""旧样例与图片清理的备份、对象变化保护及真实配置卡保留。"""
import pytest
from core.db import get_database
from core.testdata_cleanup import inventory,cleanup,remove_backed_up_files
from core.media_backup import create_bundle
from scripts.migrate_local import backup_database
from tests.test_media_backup import media_recovery
from tests.test_admin_items import drafts
from tests.test_admin_auth import query

pytestmark=pytest.mark.auth_database

def test_legacy_cleanup_only_backed_up_images_and_selected_items(media_recovery,auth_app,auth_database,admin_account,tmp_path):
    f=media_recovery
    # 复用真实SQL/文件恢复夹具，键名取其现有公开结果。
    with auth_app.test_request_context():
        conn=get_database();report=inventory(conn)
        assert report['legacy_images']
        root=tmp_path/'original-media';auth_app.config['MEDIA_ROOT']=str(root)
        bundle=tmp_path/'cleanup-backup'
        dump=tmp_path/'cleanup.sql';backup_database(auth_database['TEST_DOCKER_COMMAND'],auth_database['TEST_CONTAINER'],dump)
        create_bundle(conn,root,dump,bundle,writes_frozen=True)
        unknown=root/'keep-unknown.bin';unknown.write_bytes(b'keep')
        plan={'snapshot_sha256':report['snapshot_sha256'],'delete_items':[r['id'] for r in report['items']],'delete_chips':[]}
        result,images=cleanup(conn,plan,admin_account['id'])
        assert result['legacy_images']==2
        assert remove_backed_up_files(images,bundle)==[]
        assert unknown.read_bytes()==b'keep'
        assert not list(root.glob('*.webp'))
        assert query(auth_app,'SELECT COUNT(*) AS n FROM media_asset')[0]['n']==0

def test_inventory_change_refuses_cleanup(auth_app,admin_account):
    with auth_app.test_request_context():
        conn=get_database();p=inventory(conn)
        query(auth_app,"INSERT INTO item(project_id,item_uid) VALUES (1,'FASH-2026-887799')")
        with pytest.raises(ValueError,match='已变化'):cleanup(conn,{'snapshot_sha256':p['snapshot_sha256']},admin_account['id'])

def test_configured_historical_chip_keeps_whole_item_relation(auth_app,admin_account):
    query(auth_app,"INSERT INTO item(project_id,item_uid) VALUES (1,'FASH-2026-778899')")
    i=query(auth_app,"SELECT id FROM item WHERE item_uid='FASH-2026-778899'")[0]['id']
    query(auth_app,"INSERT INTO chip(project_id,chip_uid,chip_status,provisioned_at,last_verified_counter) VALUES (1,'04:11:22:33:44:55:66','retired',UTC_TIMESTAMP(),2)")
    c=query(auth_app,"SELECT id FROM chip WHERE chip_uid='04:11:22:33:44:55:66'")[0]['id']
    query(auth_app,"INSERT INTO whole_item(item_id,chip_id,generation,spec,started_at,ended_at) VALUES (%s,%s,1,'保留历史配置',UTC_TIMESTAMP()-INTERVAL 1 DAY,UTC_TIMESTAMP())",(i,c))
    with auth_app.test_request_context():
        conn=get_database();p=inventory(conn)
        with pytest.raises(ValueError,match='受保护'):cleanup(conn,{'snapshot_sha256':p['snapshot_sha256'],'delete_items':[i]},admin_account['id'])
    assert query(auth_app,'SELECT COUNT(*) AS n FROM whole_item WHERE item_id=%s',(i,))[0]['n']==1
