"""隔离数据库中验证找回权限、防重放和换新转售记录。"""

from datetime import timedelta
import hashlib
import secrets
from urllib.parse import urlencode

import pytest

from core.chip_keys import target_keys
from core.db import get_database
from core.holder_migration import migrate, schema
from tests.test_admin_auth import query
from tests.test_admin_catalog import action, assembly, catalog, config_chip, ok, owner
from tests.test_admin_chips import logged_in
from tests.browser_support import browser_fixture
from tests.test_chip_keys import reading

def public_ref(app, item_id):
    return query(app, 'SELECT public_id AS ref FROM item WHERE id=%s', (item_id,))[0]['ref']


pytestmark = pytest.mark.auth_database
ORIGIN = {'Origin':'http://127.0.0.1:5175'}


def signed_in(app, user_id):
    token = secrets.token_hex(32)
    query(app,'INSERT INTO user_session(token_hash,user_id,expires_at) VALUES (%s,%s,%s)',
          (hashlib.sha256(token.encode()).digest(),user_id,app.test_clock[0]+timedelta(days=30)))
    client = app.test_client()
    client.set_cookie('bumbum_user',token,path='/api/public')
    return client


def test_014_upgrade(auth_app):
    query(auth_app,'DROP TABLE item_notice_dismissal,item_recovery_contact')
    query(auth_app,"ALTER TABLE tap_grant MODIFY allowed_action ENUM('read','bind','view') NOT NULL")
    checked = []
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            assert schema(cursor) == 'missing'
        assert migrate(connection,lambda:checked.append(True))
        assert not migrate(connection,lambda:pytest.fail('已升级的结构不得再备份和修改'))
        assert checked == [True]
    assert auth_app.test_client().get('/api/ready').status_code == 200


def test_recovery_and_handover_boundaries(auth_app,catalog):
    admin, style, issue, item_id, chips = catalog
    ok(action(admin,'installAssembly',{'item_id':item_id,**assembly(admin,style,chips[0],'L黑')}))
    config_chip(auth_app,admin,chips[0])
    ok(action(admin,'toggleItem',{'item_id':item_id,'status':'active'}))
    seller = owner(auth_app,item_id,31)
    recipient = owner(auth_app,None,32)
    another = ok(action(admin,'item',{'issue_id':issue,'item_uid':'FASH-OTHER','edition_number':2}))['id']
    owner(auth_app,another,31)
    original = signed_in(auth_app,seller)
    receiver = signed_in(auth_app,recipient)
    visitor = auth_app.test_client()
    item_path = f'/api/public/me/items/{public_ref(auth_app,item_id)}'
    contact = '/api/tap/recovery'
    chip_uid = query(auth_app,'SELECT chip_uid FROM chip WHERE id=%s',(chips[0],))[0]['chip_uid']
    with auth_app.app_context():
        keys = target_keys('fashion',chip_uid)

    def touch(counter):
        return ok(visitor.post('/api/public/tap/verify',headers=ORIGIN,json=reading(keys,chip_uid,counter)))

    assert touch(3)['verified']
    whole_id = ok(admin[0].get(f'/api/admin/catalog/items/{item_id}'))['whole_id']
    ok(action(admin,'loseItem',{'item_id':item_id,'whole_id':whole_id,'evidence':'失主私有挂失说明'}))
    assert touch(3)['reason'] == 'replay_suspect'
    assert touch(4)['recovery']
    assert ok(visitor.get(contact)) == {'contact_available':False}
    assert receiver.post(item_path+'/recovery',headers=ORIGIN,json={'enabled':True}).status_code == 404
    assert ok(original.post(item_path+'/recovery',headers=ORIGIN,json={'enabled':True}))['enabled']
    assert ok(visitor.get(contact)) == {'contact_available':True}
    phone = '13900000031'
    reveal = visitor.post(contact,headers=ORIGIN,json={})
    assert ok(reveal) == {'contact_available':True,'phone':phone} and reveal.headers['Cache-Control'] == 'no-store'
    assert visitor.post(contact,headers={'Origin':'https://other.example'},json={}).status_code == 403
    assert auth_app.test_client().get(contact).status_code == 403
    assert touch(4)['reason'] == 'replay_suspect'
    assert query(auth_app,"SELECT COUNT(*) AS total FROM scan_log WHERE verify_result='pass'")[0]['total'] == 1
    ok(original.post(item_path+'/recovery',headers=ORIGIN,json={'enabled':False}))
    assert ok(visitor.post(contact,headers=ORIGIN,json={})) == {'contact_available':False}
    ok(original.post(item_path+'/recovery',headers=ORIGIN,json={'enabled':True}))
    query(auth_app,'UPDATE user SET phone_verified_at=phone_verified_at+INTERVAL 1 SECOND WHERE uid=%s',(seller,))
    assert ok(visitor.post(contact,headers=ORIGIN,json={})) == {'contact_available':True,'phone':phone}
    query(auth_app,'UPDATE user SET phone=%s WHERE uid=%s',('13900000034',seller))
    assert ok(visitor.post(contact,headers=ORIGIN,json={})) == {'contact_available':False}
    ok(original.post(item_path+'/recovery',headers=ORIGIN,json={'enabled':True}))

    renewal = ok(action(admin,'prepare',{'item_id':item_id,'kind':'loss','evidence':'换新核对',
                                          **assembly(admin,style,chips[1],'换新实物')}))['work_id']
    stage = ok(original.get(item_path))['item']['lifecycle']
    assert stage['lost'] and stage['stage'] == 'renewal' and not stage['awaiting_delivery']
    config_chip(auth_app,admin,chips[1])
    assert ok(original.get(item_path))['item']['lifecycle']['awaiting_delivery']
    ok(action(admin,'complete',{'work_id':renewal,'checked':True,'evidence':'确认换新交付'}))
    assert visitor.post(contact,headers=ORIGIN,json={}).status_code == 403
    assert not touch(5)['verified']
    notice = ok(original.get(item_path))['item']['lifecycle']['notice']
    assert notice['kind'] == 'renewed' and 'id' not in notice
    assert receiver.post(item_path+'/dismiss-notice',headers=ORIGIN,json={'notice_token':notice['token']}).status_code == 404
    ok(original.post(item_path+'/dismiss-notice',headers=ORIGIN,json={'notice_token':notice['token']}))
    assert ok(original.get(item_path))['item']['lifecycle']['notice'] is None

    auth_app.test_clock[0] += timedelta(seconds=1)
    resale = ok(action(admin,'prepare',{'item_id':item_id,'kind':'resale','recipient_id':recipient,'evidence':'转售核对',
                                        'seller_confirmation':'原持有人确认','recipient_confirmation':'接收人确认',
                                        **assembly(admin,style,chips[2],'转售新实物')}))['work_id']
    assert ok(receiver.get('/api/public/me/records'))['records'] == []
    config_chip(auth_app,admin,chips[2])
    ok(action(admin,'complete',{'work_id':resale,'checked':True,'evidence':'确认转售交付'}))
    assert [record['public_id'] for record in ok(original.get('/api/public/me/items'))['items']] == [public_ref(auth_app,another)]
    assert original.get(item_path).status_code == 404
    assert 'resold' in {entry['event'] for entry in ok(original.get('/api/public/me/records'))['records']}
    detail = ok(receiver.get(item_path))['item']
    assert detail['lifecycle']['notice']['kind'] == 'received' and not detail['recovery_enabled']
    assert [record['event'] for record in detail['records']] == ['received']
    assert {'issued','physical_started','physical_ended'} == {record['event'] for record in detail['history']}
    assert '失主私有' not in str(detail) and phone not in str(detail) and seller not in str(detail)
    auth_app.test_clock[0] += timedelta(days=7)
    assert ok(receiver.get(item_path))['item']['lifecycle']['notice'] is None
    assert ok(receiver.get('/api/public/me/records'))['records'][0]['event'] == 'received'


@pytest.mark.parametrize('original_state', ['bound', 'disabled', 'legacy'])
def test_cancel_loss_restores_service_and_preserves_history(auth_app,catalog,original_state):
    admin, style, _, item_id, chips = catalog
    chip_id = chips[0]
    ok(action(admin,'installAssembly',{'item_id':item_id,**assembly(admin,style,chip_id,'L黑')}))
    config_chip(auth_app,admin,chip_id)
    ok(action(admin,'toggleItem',{'item_id':item_id,'status':'active'}))
    holder = signed_in(auth_app,owner(auth_app,item_id,35))
    detail_url = f'/api/admin/catalog/items/{item_id}'
    whole_id = ok(admin[0].get(detail_url))['whole_id']
    loss = {'item_id':item_id,'whole_id':whole_id,'evidence':'挂失凭据'}
    if original_state=='disabled':
        ok(action(admin,'chipState',{'chip_id':chip_id,'state':'disabled','evidence':'维护停用'}))
    ok(action(admin,'loseItem',loss))
    if original_state=='legacy':
        query(auth_app,"UPDATE admin_audit SET detail=JSON_REMOVE(detail,'$.before.chip_status') WHERE action='catalog.loseItem'")
    detail = ok(admin[0].get(detail_url))
    assert detail['chip_state_before_loss'] == (None if original_state=='legacy' else original_state)

    uid = query(auth_app,'SELECT chip_uid FROM chip WHERE id=%s',(chip_id,))[0]['chip_uid']
    with auth_app.app_context():
        keys = target_keys('fashion',uid)
    visitor = auth_app.test_client()
    def touch(counter):
        return ok(visitor.post('/api/public/tap/verify',headers=ORIGIN,json=reading(keys,uid,counter)))

    assert touch(3)['recovery']
    cancel = {**loss,'lost_at':detail['lost_at'],'evidence':'已找回并核对实物'}
    assert action(admin,'cancelLoss',{**cancel,'lost_at':None}).status_code == 409
    if original_state=='legacy':
        assert action(admin,'cancelLoss',cancel).status_code == 400
        cancel['chip_state'] = 'bound'
    elif original_state=='disabled':
        assert action(admin,'cancelLoss',{**cancel,'chip_state':'bound'}).status_code == 400
    auth_app.test_clock[0] += timedelta(seconds=1)
    ok(action(admin,'cancelLoss',cancel))
    assert action(admin,'cancelLoss',cancel).status_code == 409
    assert visitor.get('/api/tap/recovery').status_code == 403
    after = ok(admin[0].get(detail_url))
    assert after['whole_id']==whole_id and after['lost_at'] is None
    assert after['chip_status'] == ('disabled' if original_state=='disabled' else 'bound')
    assert [row['event'] for row in ok(holder.get('/api/public/me/records'))['records']].count('lost') == 1
    assert ok(holder.get(f'/api/public/me/items/{public_ref(auth_app,item_id)}'))['item']['records'][0]['event'] == 'loss_cancelled'
    assert touch(4)['verified'] == (original_state!='disabled')
    if original_state=='bound':
        ok(action(admin,'loseItem',loss))
        ok(action(admin,'prepare',{'item_id':item_id,'kind':'loss','evidence':'挂失换新',
                                  **assembly(admin,style,chips[1],'替换实物')}))
        assert action(admin,'cancelLoss',{**cancel,'lost_at':ok(admin[0].get(detail_url))['lost_at']}).status_code == 409


@pytest.mark.browser
def test_owner_settings_and_finder_view_in_mobile_browser(request,auth_app,catalog,tmp_path):
    from tests.test_mobile_browser import expect

    admin, style, _, item_id, chips = catalog
    ok(action(admin,'installAssembly',{'item_id':item_id,**assembly(admin,style,chips[0],'L黑')}))
    config_chip(auth_app,admin,chips[0])
    ok(action(admin,'toggleItem',{'item_id':item_id,'status':'active'}))
    uid = owner(auth_app,item_id,33)
    client = signed_in(auth_app,uid)
    cookie = client.get_cookie('bumbum_user',path='/api/public').value
    whole_id = ok(admin[0].get(f'/api/admin/catalog/items/{item_id}'))['whole_id']
    ok(action(admin,'loseItem',{'item_id':item_id,'whole_id':whole_id,'evidence':'合成挂失'}))
    chip_uid = query(auth_app,'SELECT chip_uid FROM chip WHERE id=%s',(chips[0],))[0]['chip_uid']
    with auth_app.app_context():
        keys = target_keys('fashion',chip_uid)

    for browser in browser_fixture(request,auth_app,None,tmp_path,frontend_name='user',clear_items=False):
        page = browser.page
        page.context.add_cookies([{'name':'bumbum_user','value':cookie,'domain':'127.0.0.1','path':'/api/public','httpOnly':True}])
        page.goto(f'http://127.0.0.1:5175/mine/items/{public_ref(auth_app,item_id)}')
        expect(page.get_by_role('heading',name='当前实物已挂失')).to_be_visible()
        page.get_by_role('button',name='找回设置').click()
        page.get_by_role('checkbox',name='公开已验证的手机号').check()
        page.get_by_role('button',name='保存设置').click()
        expect(page.get_by_text('已保存。挂失期间拾到的人可以查看号码。')).to_be_visible()
        page.context.clear_cookies()
        page.goto('http://127.0.0.1:5175/tap?'+urlencode(reading(keys,chip_uid,3)))
        expect(page.get_by_role('heading',name='这件物品已挂失')).to_be_visible()
        expect(page.get_by_role('link',name='我的数字物品')).to_have_attribute('href','/mine')
        expect(page.locator('[data-private]')).to_have_count(0)
        page.get_by_role('button',name='联系失主').click()
        expect(page.get_by_role('link',name='拨打电话')).to_have_attribute('href','tel:13900000033')
        assert page.evaluate('document.documentElement.scrollWidth === innerWidth')
        page.reload()
        expect(page.get_by_role('heading',name='请重新碰一下这件物品')).to_be_visible()
        expect(page.locator('[data-private]')).to_have_count(0)
        page.get_by_role('link',name='我的数字物品').click()
        expect(page.get_by_role('heading',name='手机号登录／注册')).to_be_visible()


@pytest.mark.browser
def test_holder_tap_uses_one_document_and_one_loading_state(request,auth_app,catalog,tmp_path):
    from tests.test_mobile_browser import expect

    admin, style, _, item_id, chips = catalog
    ok(action(admin,'installAssembly',{'item_id':item_id,**assembly(admin,style,chips[0],'L黑')}))
    config_chip(auth_app,admin,chips[0])
    ok(action(admin,'toggleItem',{'item_id':item_id,'status':'active'}))
    client = signed_in(auth_app, owner(auth_app,item_id,37))
    cookie = client.get_cookie('bumbum_user',path='/api/public').value
    chip_uid = query(auth_app,'SELECT chip_uid FROM chip WHERE id=%s',(chips[0],))[0]['chip_uid']
    with auth_app.app_context():
        keys = target_keys('fashion',chip_uid)
    for browser in browser_fixture(request,auth_app,None,tmp_path,frontend_name='user',clear_items=False):
        page = browser.page
        page.context.add_cookies([{'name':'bumbum_user','value':cookie,'domain':'127.0.0.1','path':'/api/public','httpOnly':True}])
        auth_app.config['H5_LEGACY_ITEM_UNTIL']='2099-01-01T00:00:00+00:00'
        page.goto(f'http://127.0.0.1:5175/mine/items/{item_id}')
        expect(page.get_by_role('tab',name='权益')).to_be_visible()
        assert page.url.endswith('/mine/items/'+public_ref(auth_app,item_id))
        documents = []
        page.on('request', lambda req: documents.append(req.url) if req.resource_type == 'document' else None)
        page.route('**/api/public/me/items/*', lambda route: (page.wait_for_timeout(350), route.continue_()))
        page.goto('http://127.0.0.1:5175/tap?'+urlencode(reading(keys,chip_uid,3)))
        expect(page.locator('.loading-line')).to_have_count(1)
        expect(page.get_by_role('tab',name='权益')).to_be_visible()
        assert page.url.endswith('/mine/items/'+public_ref(auth_app,item_id))
        assert len(documents)==1 and page.locator('.loading-line').count()==0
        assert query(auth_app,"SELECT COUNT(*) AS n FROM scan_log WHERE verify_result='pass'")[0]['n']==1
