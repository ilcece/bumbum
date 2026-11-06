"""隔离MySQL验收：灌入、统一剔除、来源继承、外部关联保护、整批回执及重建。"""
import json
import pytest
from core.acceptance_data import seed
from core.db import get_database
from tests.test_admin_auth import query
from tests.test_admin_chips import logged_in
from tests.test_admin_catalog import ok,action

pytestmark=pytest.mark.auth_database

@pytest.fixture
def acceptance(auth_app,admin_account,logged_in,monkeypatch):
    query(auth_app,'DELETE FROM item');query(auth_app,'DELETE FROM user')
    monkeypatch.setattr('core.test_batches.validate_test_target',lambda config:None)
    with auth_app.test_request_context():
        result=seed(get_database(),admin_account['username'],apply=True)
    return result

def test_seed_statistics_idempotence_and_rebuild(auth_app,admin_account,logged_in,acceptance):
    batch=acceptance['batch_id'];s=logged_in;expected=acceptance['manifest']['expected_initial']
    assert expected['items']==20
    with auth_app.test_request_context():assert seed(get_database(),admin_account['username'],apply=True)['reused']
    assert ok(s[0].get('/api/admin/catalog/items'))['total']==0
    listed=ok(s[0].get(f'/api/admin/catalog/items?data_scope=test&test_batch_id={batch}'))
    assert listed['total']==20 and all(x['test_batch_id']==batch for x in listed['items'])
    for scope,key in [('all','lifecycle_taps'),('sold','sold_taps')]:
        stats=ok(s[0].get(f'/api/admin/catalog/statistics?scope={scope}&range=all&data_scope=test&test_batch_id={batch}'))
        assert stats['total']==expected[key] and stats['counts']['items']==20 and stats['counts']['users']==2
        assert ok(s[0].get(f'/api/admin/catalog/statistics?scope={scope}&range=all'))['total']==0
    assert ok(s[0].get('/api/admin/catalog/users'))['total']==0
    assert ok(s[0].get('/api/admin/catalog/users?data_scope=test'))['total']==2
    preview=ok(s[0].get(f'/api/admin/catalog/test-batches/{batch}/preview'));assert preview['conflicts']==[]
    cleared=ok(action(s,'clearTestBatch',{'batch_id':batch,'confirmed':True}));assert cleared['status']=='deleted'
    assert ok(s[0].get('/api/admin/catalog/items?data_scope=all'))['total']==0
    assert query(auth_app,'SELECT COUNT(*) AS n FROM user')[0]['n']==0
    assert query(auth_app,"SELECT COUNT(*) AS n FROM admin_audit WHERE action='catalog.test_seed'")[0]['n']==1
    with auth_app.test_request_context():assert seed(get_database(),admin_account['username'],apply=True)['batch_id']!=batch

def test_source_inherits_and_switch_does_not_reclassify(auth_app,logged_in,acceptance):
    s=logged_in;entry=acceptance['manifest']['items'][0];i=entry['item_id'];batch=acceptance['batch_id']
    ok(action(s,'validationItem',{'item_id':i,'enabled':False}))
    assert ok(s[0].get(f'/api/admin/catalog/items/{i}'))['test_batch_id']==batch
    assert ok(s[0].get('/api/admin/catalog/items'))['total']==0
    style=ok(s[0].get('/api/admin/catalog/styles?data_scope=test'))['items'][0]
    issue=ok(action(s,'issue',{'style_id':style['id'],'name':'继承测试发行','mode':'fixed','total':2,'rights':[],'description':'测试继承'}))['id']
    assert ok(s[0].get(f'/api/admin/catalog/issues/{issue}'))['test_batch_id']==batch

def test_external_reference_blocks_whole_batch_and_production_denies(auth_app,logged_in,acceptance,monkeypatch):
    batch=acceptance['batch_id'];s=logged_in
    user=query(auth_app,"INSERT INTO user(phone,nickname) VALUES ('TEST-EXTERNAL','批次外账户')")
    uid=query(auth_app,"SELECT id FROM user WHERE phone='TEST-EXTERNAL'")[0]['id']
    i=acceptance['manifest']['items'][0]['item_id']
    query(auth_app,"INSERT INTO ownership(item_id,user_id,bind_source) VALUES (%s,%s,'import')",(i,uid))
    assert ok(s[0].get(f'/api/admin/catalog/test-batches/{batch}/preview'))['conflicts']
    assert action(s,'clearTestBatch',{'batch_id':batch,'confirmed':True}).status_code==409
    assert query(auth_app,'SELECT COUNT(*) AS n FROM item')[0]['n']==20
    def deny(_):raise ValueError('拒绝生产')
    monkeypatch.setattr('core.test_batches.validate_test_target',deny)
    assert action(s,'clearTestBatch',{'batch_id':batch,'confirmed':True}).status_code==403

def test_old_images_retired_shared_images_remain_guarded(logged_in,acceptance):
    s=logged_in
    for path in ['/api/admin/items/1/images','/api/admin/items/1/images/'+'a'*32,'/api/tap/items/1/images/'+'a'*32]:
        assert s[0].get(path).status_code in {404,405}
    style=ok(s[0].get('/api/admin/catalog/styles?data_scope=test'))['items'][0]
    assert s[0].get(style['image_urls'][0]).status_code==200
    assert s[0].get('/api/tap/items/1/style-images/'+'a'*32).status_code==403

def test_clear_batch_audit_failure_rolls_back_and_receipt_is_single(auth_app,logged_in,acceptance,monkeypatch):
    s=logged_in;batch=acceptance['batch_id']
    from core import admin_catalog
    original=admin_catalog.audit
    def broken(*_):raise RuntimeError('测试审计故障')
    monkeypatch.setattr(admin_catalog,'audit',broken)
    assert action(s,'clearTestBatch',{'batch_id':batch,'confirmed':True}).status_code==500
    assert ok(s[0].get('/api/admin/catalog/items?data_scope=test'))['total']==20
    monkeypatch.setattr(admin_catalog,'audit',original)
    import uuid
    token=str(uuid.uuid4());p={'batch_id':batch,'confirmed':True}
    first=ok(action(s,'clearTestBatch',p,token));assert ok(action(s,'clearTestBatch',p,token))==first
    assert query(auth_app,"SELECT COUNT(*) AS n FROM admin_audit WHERE action='catalog.clearTestBatch'")[0]['n']==1
