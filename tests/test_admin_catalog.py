"""临时MySQL中验证真实数字档案、整套事务、配置与历史统计。"""
from io import BytesIO
import json
import uuid

from PIL import Image
import pytest

from core.catalog_migration import catalog_schema
from tests.test_admin_auth import query
from tests.test_admin_chips import logged_in
from tests.test_chip_keys import configure, reading

pytestmark=pytest.mark.auth_database


def action(session,name,payload,token=None):
    return session[0].post('/api/admin/catalog/actions/'+name,headers=session[1],json={'request_id':token or str(uuid.uuid4()),'payload':payload})


def ok(response):
    assert response.status_code==200,response.json
    return response.json['data']


def assembly(session,style_id,chip_id,spec):
    entity=ok(action(session,'createPhysicalItem',{'style_id':style_id,'physical_uid':'PHY-'+uuid.uuid4().hex,'spec':spec}))
    return {'physical_item_id':entity['id'],'chip_id':chip_id,'installed':True}


@pytest.fixture
def catalog(auth_app,logged_in):
    for table in ('item_handover','whole_item','ownership_history','ownership','fashion_item_profile','jewelry_item_profile','media_asset','item','product_issue','style_image','product_style','admin_operation'):
        query(auth_app,f'DELETE FROM {table}')
    configure(auth_app)
    style=ok(action(logged_in,'style',{'project':'fashion','code':'CAP','name':'通用限量帽子','specs':['L黑'],'image_urls':[]}))['id']
    issue=ok(action(logged_in,'issue',{'style_id':style,'name':'限量50个身份','mode':'fixed','total':50,'description':'换新和转售都交付新整套','rights':['renewal','resale']}))['id']
    ok(action(logged_in,'confirmIssue',{'issue_id':issue}))
    ident=ok(action(logged_in,'item',{'issue_id':issue,'item_uid':'FASH-2026-000001','edition_number':1}))['id']
    chips=[ok(action(logged_in,'register',{'chip_uid':f'04{n:012X}'}))['id'] for n in range(1,5)]
    return logged_in,style,issue,ident,chips


def config_chip(app,session,chip_id):
    ok(session[0].post(f'/api/admin/chips/{chip_id}/generate-keys',headers=session[1],json={}))
    uid=query(app,'SELECT chip_uid FROM chip WHERE id=%s',(chip_id,))[0]['chip_uid']
    from core.chip_keys import target_keys
    with app.app_context():keys=target_keys('fashion',uid)
    body={'management_confirmed':True,'readings':[reading(keys,uid,1),reading(keys,uid,2)]}
    ok(session[0].post(f'/api/admin/chips/{chip_id}/confirm-provisioning',headers=session[1],json=body))


def owner(app,ident,n):
    query(app,'INSERT INTO user(phone,nickname,phone_verified_at) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE phone_verified_at=VALUES(phone_verified_at)',(f'1390000{n:04d}',f'临时账户{n}',app.test_clock[0]))
    uid=query(app,'SELECT id FROM user WHERE phone=%s',(f'1390000{n:04d}',))[0]['id']
    if ident:query(app,"INSERT INTO ownership(item_id,user_id,bind_source,bound_at) VALUES (%s,%s,'import',%s)",(ident,uid,app.test_clock[0]))
    return uid


def test_audit_lists_current_and_historical_targets_with_mixed_collations(auth_app, catalog):
    session, _, _, item, _ = catalog
    operator = query(auth_app, 'SELECT id FROM admin_user')[0]['id']
    targets = [('item', str(item)), ('item', f'0{item}'), ('item', '18446744073709551615'), ('style', str(item))]
    for kind, target in targets:
        query(auth_app, 'INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail) VALUES (%s,%s,%s,%s,%s)',
              (operator, 'catalog.installAssembly', kind, target, json.dumps({'summary': '排序规则验收'})))
    client = session[0]
    assert ok(client.get('/api/admin/catalog/audit'))['items']
    data = ok(client.get('/api/admin/catalog/audit', query_string={'keyword': '排序规则验收'}))
    actual = {(record['target_type'], record['target_id']): bool(record['object_exists']) for record in data['items']}
    assert actual == {target: target == ('item', str(item)) for target in targets}


def test_whole_loss_renewal_resale_keeps_identity_history_and_real_configuration(auth_app,catalog):
    s,style,issue,i,chips=catalog
    ok(action(s,'installAssembly',{'item_id':i,**assembly(s,style,chips[0],'L黑')}));config_chip(auth_app,s,chips[0]);ok(action(s,'toggleItem',{'item_id':i,'status':'active'}))
    a=owner(auth_app,i,1);b=owner(auth_app,None,2)
    ok(action(s,'sale',{'item_id':i,'confirmed':True,'evidence':'外部店铺实际售出'}))
    original=ok(s[0].get(f'/api/admin/catalog/items/{i}'))
    ok(action(s,'prepare',{'item_id':i,'kind':'periodic','evidence':'核对资格',**assembly(s,style,chips[1],'新实物L黑')}))
    config_chip(auth_app,s,chips[1])
    w=query(auth_app,'SELECT * FROM item_handover WHERE item_id=%s',(i,))[0]
    # 候选真实配置通过，但尚未获得物品关联或触碰授权。
    assert query(auth_app,'SELECT item_id,chip_status FROM chip WHERE id=%s',(chips[1],))[0]=={'item_id':None,'chip_status':'pending'}
    token=str(uuid.uuid4());p={'item_id':i,'whole_id':original['whole_id'],'evidence':'整套丢失，身份保留'}
    ok(action(s,'loseItem',p,token));ok(action(s,'loseItem',p,token))
    assert query(auth_app,"SELECT COUNT(*) AS n FROM admin_audit WHERE action='catalog.loseItem'")[0]['n']==1
    assert action(s,'chipState',{'chip_id':chips[0],'state':'restore','evidence':'不允许绕过'}).status_code==409
    assert query(auth_app,'SELECT kind FROM item_handover WHERE id=%s',(w['id'],))[0]['kind']=='loss'
    ok(action(s,'complete',{'work_id':w['id'],'checked':True,'evidence':'已核对整套实际交付'}))
    renewed=ok(s[0].get(f'/api/admin/catalog/items/{i}'))
    assert renewed['item_uid']==original['item_uid'] and renewed['edition_number']==1 and renewed['owner_id']==a
    assert renewed['wholes'][0]['generation']==2 and renewed['wholes'][0]['loss_evidence'] is None
    assert renewed['wholes'][1]['loss_evidence']=='整套丢失，身份保留'
    assert query(auth_app,'SELECT chip_status FROM chip WHERE id=%s',(chips[0],))[0]['chip_status']=='retired'
    assert renewed['quota_review']==0 and renewed['quota_used']==1
    ok(action(s,'prepare',{'item_id':i,'kind':'resale','recipient_id':b,'evidence':'已核对接收账户','seller_confirmation':'原持有人已确认','recipient_confirmation':'接收人已确认',**assembly(s,style,chips[2],'转售新实物')}));config_chip(auth_app,s,chips[2])
    resale=query(auth_app,'SELECT * FROM item_handover WHERE item_id=%s ORDER BY id DESC',(i,))[0]
    ok(action(s,'complete',{'work_id':resale['id'],'checked':True,'evidence':'新整套交付新持有人'}))
    result=ok(s[0].get(f'/api/admin/catalog/items/{i}'));assert result['owner_id']==b and len(result['wholes'])==3 and result['first_sold_at']==original['first_sold_at']
    old=[x for x in result['handovers'] if x['id']==w['id']][0]
    assert old['source_id']==original['whole_id'] and old['target_id']==renewed['whole_id']
    assert query(auth_app,'SELECT COUNT(*) AS n FROM item')[0]['n']==1


def test_release_uniqueness_validation_cleanup_and_receipt(auth_app,catalog):
    s,style,issue,i,chips=catalog
    assert action(s,'item',{'issue_id':issue,'item_uid':'FASH-2026-000002','edition_number':1}).status_code==409
    ok(action(s,'installAssembly',{'item_id':i,**assembly(s,style,chips[0],'整套')}))
    assert action(s,'deleteItem',{'item_id':i}).status_code==409
    ok(action(s,'validationItem',{'item_id':i,'enabled':True}))
    token=str(uuid.uuid4());ok(action(s,'deleteItem',{'item_id':i},token))
    assert ok(action(s,'receipt',{'request_id':token}))['id']==i
    assert query(auth_app,'SELECT * FROM chip WHERE id=%s',(chips[0],))[0]['chip_status']=='pending'
    assert not query(auth_app,'SELECT * FROM item WHERE id=%s',(i,))
    assert action(s,'deleteIssue',{'issue_id':issue}).status_code==409
    assert action(s,'item',{'issue_id':issue,'item_uid':'FASH-2026-000002','edition_number':2},token).status_code==409


def test_shared_upload_and_server_pagination(auth_app,catalog):
    s,style,issue,i,chips=catalog
    auth_app.config['MEDIA_ENABLED']=True
    image=Image.new('RGB',(20,20),'blue');buf=BytesIO();image.save(buf,format='PNG');asset=uuid.uuid4().hex
    path=f'/api/admin/catalog/styles/{style}/images/{asset}'
    uploaded=ok(s[0].post(path,headers=s[1],data={'file':(BytesIO(buf.getvalue()),'test.png')},content_type='multipart/form-data'))
    assert s[0].get(path).status_code==200
    ok(action(s,'style',{'id':style,'project':'fashion','code':'CAP','name':'新共用名称','specs':['L黑'],'image_urls':[uploaded['url']],'shared_confirmed':True}))
    page=ok(s[0].get('/api/admin/catalog/items?keyword=新共用名称&page=2&page_size=1'))
    assert page['total']==1 and page['page']==1 and page['items'][0]['name']=='新共用名称'
    with auth_app.app_context():
        from core.db import get_database
        with get_database().cursor() as c:assert catalog_schema(c)=='ready'
    # 同一共用图支持现有短资格与持续查看，挂失后两条链路均失效。
    ok(action(s,'installAssembly',{'item_id':i,**assembly(s,style,chips[0],'L黑')}));config_chip(auth_app,s,chips[0]);ok(action(s,'toggleItem',{'item_id':i,'status':'active'}))
    auth_app.config['PUBLIC_ORIGIN']='http://127.0.0.1:5175'
    from core.chip_keys import target_keys
    with auth_app.app_context():keys=target_keys('fashion',query(auth_app,'SELECT chip_uid FROM chip WHERE id=%s',(chips[0],))[0]['chip_uid'])
    uid=query(auth_app,'SELECT chip_uid FROM chip WHERE id=%s',(chips[0],))[0]['chip_uid']
    public=auth_app.test_client();verified=ok(public.post('/api/tap/verify',json={**reading(keys,uid,3),'browser_view':True},headers={'Origin':'http://127.0.0.1:5175'}))
    from urllib.parse import urlsplit
    image_path=urlsplit(verified['item_detail']['image_urls'][0]).path
    assert public.get(image_path,headers={'Origin':'http://127.0.0.1:5175'}).status_code==200
    assert auth_app.test_client().get(image_path,headers={'Origin':'http://127.0.0.1:5175'}).status_code==403
    detail=ok(public.get(f'/api/fashion/items/{i}/detail',headers={'X-Tap-Token':verified['tap_token']}))
    short_path=urlsplit(detail['profile']['image_urls'][0]).path
    assert short_path.startswith(f'/api/fashion/items/{i}/style-images/')
    assert public.get(short_path,headers={'X-Tap-Token':verified['tap_token']}).status_code==200
    whole=ok(s[0].get(f'/api/admin/catalog/items/{i}'))['whole_id'];ok(action(s,'loseItem',{'item_id':i,'whole_id':whole,'evidence':'整套挂失'}))
    assert public.get(image_path,headers={'Origin':'http://127.0.0.1:5175'}).status_code in {403,409}
    assert public.get(short_path,headers={'X-Tap-Token':verified['tap_token']}).status_code in {403,409}
    assert s[0].get('/api/admin/catalog/items?page=0').status_code==400
    assert s[0].post('/api/admin/catalog/actions/item',headers={},json={}).status_code in {401,403}


def test_loss_failure_rolls_back_and_lost_response_has_single_committed_receipt(auth_app,catalog,monkeypatch):
    from core import admin_catalog
    import pymysql
    s,style,issue,i,chips=catalog
    ok(action(s,'installAssembly',{'item_id':i,**assembly(s,style,chips[0],'整套')}))
    e=ok(s[0].get(f'/api/admin/catalog/items/{i}'))['whole_id']
    original=admin_catalog.audit
    def fail_audit(*_):raise RuntimeError('测试专用审计故障')
    monkeypatch.setattr(admin_catalog,'audit',fail_audit)
    assert action(s,'loseItem',{'item_id':i,'whole_id':e,'evidence':'测试回滚'}).status_code==500
    assert query(auth_app,'SELECT chip_status FROM chip WHERE id=%s',(chips[0],))[0]['chip_status']=='bound'
    assert query(auth_app,'SELECT lost_at FROM whole_item WHERE id=%s',(e,))[0]['lost_at'] is None
    monkeypatch.setattr(admin_catalog,'audit',original)
    with auth_app.app_context():
        from core.db import get_database
        connection=get_database()
        class LostResponse:
            failed=False
            def __getattr__(self,key):return getattr(connection,key)
            def commit(self):
                connection.commit()
                if not self.failed:self.failed=True;raise pymysql.OperationalError(2006,'测试专用提交回执丢失')
        proxy=LostResponse();monkeypatch.setattr(admin_catalog,'get_database',lambda:proxy)
        token=str(uuid.uuid4());p={'item_id':i,'confirmed':True,'evidence':'单次售出'}
        assert action(s,'sale',p,token).status_code==503
        ok(action(s,'receipt',{'request_id':token}));ok(action(s,'sale',p,token))
        assert query(auth_app,"SELECT COUNT(*) AS n FROM admin_audit WHERE action='catalog.sale'")[0]['n']==1


def test_real_event_statistics_do_not_depend_on_current_chip_or_holder(auth_app,catalog):
    from datetime import timedelta
    s,style,issue,i,chips=catalog
    ok(action(s,'installAssembly',{'item_id':i,**assembly(s,style,chips[0],'整套')}))
    ok(action(s,'sale',{'item_id':i,'confirmed':True,'evidence':'外部售出事实'}))
    uid=query(auth_app,'SELECT chip_uid FROM chip WHERE id=%s',(chips[0],))[0]['chip_uid']
    for n,delta in enumerate((-1,1,2),3):
        query(auth_app,"INSERT INTO scan_log(chip_id,item_id,chip_uid,project_id,scan_counter,verify_result,created_at) VALUES (%s,%s,%s,1,%s,'pass',%s)",(chips[0],i,uid,n,auth_app.test_clock[0]+timedelta(seconds=delta)))
    assert ok(s[0].get(f'/api/admin/catalog/statistics?item_id={i}&range=all&scope=all'))['total']==3
    assert ok(s[0].get(f'/api/admin/catalog/statistics?item_id={i}&range=all&scope=sold'))['total']==2
    ok(action(s,'validationChip',{'chip_id':chips[0],'enabled':True}));ok(action(s,'deleteChip',{'chip_id':chips[0]}))
    assert ok(s[0].get(f'/api/admin/catalog/statistics?item_id={i}&range=all&scope=all'))['total']==0
    assert ok(s[0].get(f'/api/admin/catalog/items/{i}'))['sold']==1


def test_upgrade_existing_records_without_guessing_style_issuance_or_sales(auth_app,logged_in):
    from core.catalog_migration import migrate
    from core.assembly_migration import migrate as migrate_assembly, schema as assembly_schema
    from core.db import get_database
    for table in ('fashion_item_profile','jewelry_item_profile','item'):query(auth_app,f'DELETE FROM {table}')
    with auth_app.app_context():
        connection=get_database()
        with connection.cursor() as c:
            for table in ('item_claim_code','user_session','user_sms_challenge','digital_item_right','admin_operation','item_handover','whole_item','physical_item','digital_item','style_image','product_issue','product_style','chip_validation'):
                c.execute('DROP TABLE '+table)
            c.execute('ALTER TABLE user DROP COLUMN phone_verified_at')
            c.execute("ALTER TABLE test_batch_object MODIFY kind ENUM('style','issue','item','chip','user','scan') NOT NULL")
            c.execute("ALTER TABLE chip MODIFY chip_status ENUM('pending','bound','disabled','lost') NOT NULL DEFAULT 'pending'")
            c.execute("INSERT INTO item(project_id,item_uid) VALUES (1,'FASH-2026-900001')");ident=c.lastrowid
            c.execute("INSERT INTO chip(chip_uid,project_id,item_id,chip_status) VALUES ('04:00:00:00:00:99:01',1,%s,'lost')",(ident,))
        connection.commit();backups=[]
        def backup():
            with connection.cursor() as c:assert catalog_schema(c)=='missing'
            connection.commit();backups.append(True)
        assert migrate(connection,backup) is True
        assert migrate(connection,backup) is False and len(backups)==1
        with connection.cursor() as c:assert catalog_schema(c)=='ready'
        assert migrate_assembly(connection,lambda:backups.append(True))
        assert not migrate_assembly(connection,lambda:pytest.fail('重复升级无需备份'))
        with connection.cursor() as c:assert assembly_schema(c)=='ready'
    d=query(auth_app,'SELECT * FROM digital_item WHERE item_id=%s',(ident,))[0]
    e=query(auth_app,'SELECT * FROM whole_item WHERE item_id=%s',(ident,))[0]
    assert d['issue_id'] is None and d['sold']==0 and d['first_sold_at'] is None
    assert e['generation']==1 and e['started_at'] is None and e['lost_at'] is None and e['loss_evidence'] and e['physical_item_id'] is None


def test_period_estimate_does_not_cap_identities_and_sealing_does_not_create_items(auth_app,catalog):
    s,style,_,_,_=catalog
    issue=ok(action(s,'issue',{'style_id':style,'name':'按外部销量定量','mode':'period','total':100,'starts_at':'2020-01-01T00:00:00+08:00','ends_at':'2020-02-01T00:00:00+08:00','counting_rule':'退款不计入，跨店按实际有效件数核对','description':'预估100，最终以核定为准','rights':[]}))['id']
    ok(action(s,'confirmIssue',{'issue_id':issue}))
    for n in range(101):ok(action(s,'item',{'issue_id':issue,'item_uid':f'FASH-2026-{1000+n:06d}'}))
    before=query(auth_app,'SELECT COUNT(*) AS n FROM item')[0]['n']
    ok(action(s,'seal',{'issue_id':issue,'total':137,'evidence':'多店核定有效137件'}))
    assert query(auth_app,'SELECT COUNT(*) AS n FROM item')[0]['n']==before
    numbers=query(auth_app,'SELECT edition_number FROM digital_item WHERE issue_id=%s ORDER BY item_id',(issue,))
    assert [r['edition_number'] for r in numbers]==list(range(1,102))
    assert action(s,'seal',{'issue_id':issue,'total':138,'evidence':'不重封'}).status_code==409


def test_jewelry_validation_cleanup_keeps_chip_account_and_task_definition(auth_app,catalog):
    s,_,_,_,chips=catalog
    style=ok(action(s,'style',{'project':'jewelry','code':'BRACELET','name':'紫檀手串','specs':[],'image_urls':[]}))['id']
    issue=ok(action(s,'issue',{'style_id':style,'name':'限量50个身份','mode':'fixed','total':50,'description':'整套物品','rights':[]}))['id'];ok(action(s,'confirmIssue',{'issue_id':issue}))
    ident=ok(action(s,'item',{'issue_id':issue,'item_uid':'JEW-2026-000001','edition_number':1,'is_validation':True}))['id'];ok(action(s,'installAssembly',{'item_id':ident,**assembly(s,style,chips[0],'无尺码')}))
    uid=owner(auth_app,ident,88)
    query(auth_app,'INSERT INTO jewelry_user_progress(item_id,user_id) VALUES (%s,%s)',(ident,uid))
    code='TEST-'+uuid.uuid4().hex;query(auth_app,'INSERT INTO jewelry_task(code,name) VALUES (%s,%s)',(code,'历史预留任务'))
    task=query(auth_app,'SELECT id FROM jewelry_task WHERE code=%s',(code,))[0]['id'];query(auth_app,'INSERT INTO jewelry_task_record(task_id,item_id,user_id) VALUES (%s,%s,%s)',(task,ident,uid))
    ok(action(s,'deleteItem',{'item_id':ident}))
    assert query(auth_app,'SELECT id FROM chip WHERE id=%s',(chips[0],))
    assert query(auth_app,'SELECT id FROM user WHERE id=%s',(uid,))
    assert query(auth_app,'SELECT id FROM jewelry_task WHERE id=%s',(task,))
    assert not query(auth_app,'SELECT id FROM jewelry_task_record WHERE item_id=%s',(ident,))
    assert not query(auth_app,'SELECT id FROM jewelry_user_progress WHERE item_id=%s',(ident,))


def test_testdata_preview_flag_guard_and_no_holder_overwrite(auth_app,catalog,admin_account):
    from core.catalog_testdata import seed_holders
    from core.db import get_database
    s,_,_,item,_=catalog
    with auth_app.app_context():
        with pytest.raises(ValueError):seed_holders(get_database(),item,admin_account['username'],apply=True)
    ok(action(s,'validationItem',{'item_id':item,'enabled':True}))
    with auth_app.app_context():
        assert seed_holders(get_database(),item,admin_account['username'])['applied'] is False
        result=seed_holders(get_database(),item,admin_account['username'],apply=True)
        with pytest.raises(ValueError):seed_holders(get_database(),item,admin_account['username'],apply=True)
    assert query(auth_app,'SELECT user_id FROM ownership WHERE active_item_id=%s',(item,))[0]['user_id']==result['owner_id']
    assert result['owner_id']!=result['recipient_id']


def test_testdata_refuses_non_test_configuration_before_connection():
    from core.catalog_testdata import validate_test_target
    for config in ({},{'HANGZHOU_SLOT':'production'},{'APP_ENV':'development','DB_HOST':'localhost','DB_PORT':33306,'DB_USER':'bumbum_dev','DB_NAME':'real_business'}):
        with pytest.raises(ValueError):validate_test_target(config)
