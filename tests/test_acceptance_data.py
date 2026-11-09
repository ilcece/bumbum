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
    assert expected['items']==84
    with auth_app.test_request_context():assert seed(get_database(),admin_account['username'],apply=True)['reused']
    assert ok(s[0].get('/api/admin/catalog/items'))['total']==0
    listed=ok(s[0].get(f'/api/admin/catalog/items?data_scope=test&test_batch_id={batch}'))
    assert listed['total']==84 and all(x['test_batch_id']==batch for x in listed['items'])
    for scope,key in [('all','lifecycle_taps'),('sold','sold_taps')]:
        stats=ok(s[0].get(f'/api/admin/catalog/statistics?scope={scope}&range=all&data_scope=test&test_batch_id={batch}'))
        assert stats['total']==expected[key] and stats['counts']['items']==84 and stats['counts']['users']==6
        assert ok(s[0].get(f'/api/admin/catalog/statistics?scope={scope}&range=all'))['total']==0
    assert ok(s[0].get('/api/admin/catalog/users'))['total']==0
    assert ok(s[0].get('/api/admin/catalog/users?data_scope=test'))['total']==6
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


def test_replace_old_simulated_batch_after_preview(auth_app,admin_account,acceptance):
    old=acceptance['batch_id']
    query(auth_app,"UPDATE test_batch SET manifest=JSON_SET(manifest,'$.pack','acceptance-v2') WHERE id=%s",(old,))
    with auth_app.test_request_context():
        planned=seed(get_database(),admin_account['username'],replace_batch=old)
        assert planned['replacing']['status']=='active' and not planned['replacing']['conflicts']
        result=seed(get_database(),admin_account['username'],replace_batch=old,apply=True)
        assert result['replaced']['status']=='deleted' and result['batch_id']!=old
        assert seed(get_database(),admin_account['username'],replace_batch=old,apply=True)['reused']
    assert query(auth_app,'SELECT status FROM test_batch WHERE id=%s',(old,))[0]['status']=='deleted'
    assert len(result['manifest']['items'])==84 and all(x['physical_uid'] for x in result['manifest']['items'])

def test_external_reference_blocks_whole_batch_and_production_denies(auth_app,logged_in,acceptance,monkeypatch):
    batch=acceptance['batch_id'];s=logged_in
    user=query(auth_app,"INSERT INTO user(phone,nickname) VALUES ('TEST-EXTERNAL','批次外账户')")
    uid=query(auth_app,"SELECT id FROM user WHERE phone='TEST-EXTERNAL'")[0]['id']
    i=acceptance['manifest']['items'][0]['item_id']
    query(auth_app,"INSERT INTO ownership(item_id,user_id,bind_source) VALUES (%s,%s,'import')",(i,uid))
    assert ok(s[0].get(f'/api/admin/catalog/test-batches/{batch}/preview'))['conflicts']
    assert action(s,'clearTestBatch',{'batch_id':batch,'confirmed':True}).status_code==409
    assert query(auth_app,'SELECT COUNT(*) AS n FROM item')[0]['n']==84
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
    assert ok(s[0].get('/api/admin/catalog/items?data_scope=test'))['total']==84
    monkeypatch.setattr(admin_catalog,'audit',original)
    import uuid
    token=str(uuid.uuid4());p={'batch_id':batch,'confirmed':True}
    first=ok(action(s,'clearTestBatch',p,token));assert ok(action(s,'clearTestBatch',p,token))==first
    assert query(auth_app,"SELECT COUNT(*) AS n FROM admin_audit WHERE action='catalog.clearTestBatch'")[0]['n']==1


def test_prototype_statistics_filters_pagination_and_atomic_batch_sale(auth_app,logged_in,acceptance,monkeypatch):
    batch=acceptance['batch_id'];client=logged_in[0]
    base=f'/api/admin/catalog/statistics?data_scope=test&test_batch_id={batch}&scope=all&range=all'
    result=ok(client.get(base))
    assert result['total']==138 and result['inventory']['items']==84
    assert result['details']['total']==84 and len(result['details']['items'])==10
    first={r['id'] for r in result['details']['items']}
    second=ok(client.get(base+'&page=2'))
    assert first.isdisjoint({r['id'] for r in second['details']['items']})
    style=ok(client.get('/api/admin/catalog/styles?data_scope=test'))['items'][-1]
    filtered=ok(client.get(base+f"&style_id={style['id']}"))
    assert filtered['counts']['items']==14 and filtered['details']['total']==14
    assert filtered['inventory']['items']==84
    issue=ok(client.get('/api/admin/catalog/issues?data_scope=test'))['items'][0]
    assert ok(client.get(base+f"&issue_id={issue['id']}"))['counts']['items']==0
    for resource,parameter in [('items','owner'),('chips','configured')]:
        yes=ok(client.get(f'/api/admin/catalog/{resource}?data_scope=test&{parameter}=yes'))
        no=ok(client.get(f'/api/admin/catalog/{resource}?data_scope=test&{parameter}=no'))
        assert yes['total']+no['total']==(84 if resource=='items' else 114)
        assert yes['total']>0 and no['total']>0
    assert ok(client.get('/api/admin/catalog/issues?data_scope=test&mode=fixed'))['total']==4
    assert ok(client.get('/api/admin/catalog/issues?data_scope=test&status=confirmed'))['total']==8
    assert client.get('/api/admin/catalog/issues?mode=invalid').status_code==400
    ids=[r['item_id'] for r in acceptance['manifest']['items'][:2]]
    payload={'item_ids':ids,'confirmed':True,'evidence':'隔离验收核对'}
    result=ok(action(logged_in,'saleBatch',payload));assert result['ids']==sorted(ids)
    assert query(auth_app,'SELECT COUNT(*) AS n FROM digital_item WHERE item_id IN (%s,%s) AND sold=1',tuple(ids))[0]['n']==2
    assert action(logged_in,'saleBatch',{'item_ids':[ids[0],2147483647],'confirmed':False,'evidence':'应整体拒绝'}).status_code==409
    assert query(auth_app,'SELECT sold FROM digital_item WHERE item_id=%s',(ids[0],))[0]['sold']==1

    from core import admin_catalog
    original=admin_catalog.item_action
    def fail_second(cursor,name,payload):
        if payload['item_id']==ids[1]:raise RuntimeError('隔离测试第二件失败')
        return original(cursor,name,payload)
    monkeypatch.setattr(admin_catalog,'item_action',fail_second)
    assert action(logged_in,'saleBatch',{'item_ids':ids,'confirmed':False,'evidence':'验证事务回滚'}).status_code==500
    assert query(auth_app,'SELECT sold FROM digital_item WHERE item_id=%s',(ids[0],))[0]['sold']==1


def test_rich_pack_real_photos_specs_states_and_synthetic_boundaries(auth_app,acceptance):
    """照片、实物规格及历代状态一致；模拟卡没有密钥，不冒充实卡。"""
    manifest=acceptance['manifest']
    assert manifest['expected_initial']=={'styles':6,'issues':10,'items':84,'chips':114,'users':6,'lifecycle_taps':138,'sold_taps':132}
    assert len(manifest['photos'])==6 and len({p['sha256'] for p in manifest['photos']})==6
    assert all(p['page'].startswith('https://commons.wikimedia.org/wiki/File:') and p['artist'] and p['license'] for p in manifest['photos'])
    assert query(auth_app,'SELECT COUNT(*) AS n FROM chip_key')[0]['n']==0
    assert {r['chip_status'] for r in query(auth_app,'SELECT DISTINCT chip_status FROM chip')}=={'pending','bound','lost','retired','disabled'}
    assert {r['status'] for r in query(auth_app,'SELECT DISTINCT status FROM item')}=={'draft','active','disabled'}
    assert len(query(auth_app,'SELECT id FROM item_handover WHERE completed_at IS NULL'))==12
    assert len(query(auth_app,'SELECT id FROM whole_item WHERE ended_at IS NOT NULL'))==12
    assert len(query(auth_app,'SELECT item_id FROM item_handover WHERE quota_year IS NOT NULL AND completed_at IS NOT NULL'))==6
    assert len(query(auth_app,'SELECT id FROM ownership WHERE is_active=1'))==54
    assert query(auth_app,'SELECT COUNT(*) AS n FROM chip c JOIN (SELECT chip_id,MAX(scan_counter) AS counter FROM scan_log GROUP BY chip_id) s ON s.chip_id=c.id WHERE c.last_verified_counter<s.counter')[0]['n']==0
    rows=query(auth_app,'SELECT w.spec,s.specs FROM whole_item w JOIN digital_item d ON d.item_id=w.item_id JOIN product_issue i ON i.id=d.issue_id JOIN product_style s ON s.id=i.style_id')
    assert rows and all(r['spec'] in json.loads(r['specs']) for r in rows)
