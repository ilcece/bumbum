"""独立 MySQL 中核对实签名触碰、账户验证与并发认领。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import secrets
import uuid

import pytest

from core.chip_keys import target_keys
from core import public_account
from tests.test_admin_auth import query
from tests.test_admin_catalog import action, assembly, catalog, config_chip, ok
from tests.test_admin_chips import logged_in
from tests.test_chip_keys import reading


pytestmark=pytest.mark.auth_database
ORIGIN={'Origin':'http://127.0.0.1:5175'}


@pytest.mark.parametrize(('provider', 'slot', 'number_setting'), [
    ('aliyun', 'test', 'SMS_ALIYUN_TEST_PHONE'),
    ('aliyun_pilot', 'production', 'SMS_ALIYUN_PILOT_PHONE'),
])
def test_aliyun_sms_rejects_other_slots_and_recipients_before_creating_challenge(auth_app, monkeypatch, provider, slot, number_setting):
    phone = '13900009701'
    auth_app.config.update(
        PUBLIC_ORIGIN=ORIGIN['Origin'], SMS_CODE_HASH_KEY=secrets.token_hex(32),
        SMS_PROVIDER=provider, SMS_ALIYUN_ACCESS_KEY_ID='synthetic-id',
        SMS_ALIYUN_ACCESS_KEY_SECRET='synthetic-secret', SMS_ALIYUN_SIGN_NAME='隔离验收签名',
        SMS_ALIYUN_TEMPLATE_CODE='SMS_123456',
        SMS_ALIYUN_TEST_PHONE='13900009702', SMS_ALIYUN_PILOT_PHONE='13900009702',
        TEST_SMS_SENDER=lambda *_: pytest.fail('不能绕回模拟发送'),
    )
    auth_app.config[number_setting] = phone
    attempts = []

    def send(_config, recipient, code):
        attempts.append((recipient, code))
        return len(attempts) > 1

    monkeypatch.setattr(public_account, 'send_aliyun_sms', send)
    client = auth_app.test_client()

    def request_sms(recipient):
        return client.post('/api/public/sms/send', headers=ORIGIN, json={'phone': recipient})

    other_slot = 'production' if slot == 'test' else 'test'
    for wrong_slot in ('', other_slot):
        auth_app.config['HANGZHOU_SLOT'] = wrong_slot
        assert request_sms(phone).status_code == 503
    auth_app.config['HANGZHOU_SLOT'] = slot
    assert request_sms('13900009702').status_code == 403
    auth_app.config[number_setting] = ''
    assert request_sms(phone).status_code == 503
    assert not attempts and not query(auth_app, 'SELECT bucket_key FROM security_rate_limit')
    assert not query(auth_app, 'SELECT phone FROM user_sms_challenge')

    auth_app.config[number_setting] = phone
    assert request_sms(phone).status_code == 503
    assert query(auth_app, 'SELECT consumed_at FROM user_sms_challenge')[0]['consumed_at'] is not None
    auth_app.test_clock[0] += timedelta(seconds=61)
    challenge_id = ok(request_sms(phone))['challenge_id']
    assert [recipient for recipient, _ in attempts] == [phone, phone]
    result = client.post('/api/public/sms/verify', headers=ORIGIN,
                         json={'challenge_id': challenge_id, 'code': attempts[-1][1]})
    assert ok(result)['account']['phone'] == '139****9701'
    assert client.post('/api/public/sms/verify', headers=ORIGIN,
                       json={'challenge_id': challenge_id, 'code': attempts[-1][1]}).status_code == 400


def test_claim_requires_verified_user_tap_and_delivery_and_only_one_wins(auth_app,catalog):
    admin,style,issue,item,chips=catalog
    sms={}
    auth_app.config.update(PUBLIC_ORIGIN=ORIGIN['Origin'],SMS_CODE_HASH_KEY=secrets.token_hex(32),TEST_SMS_SENDER=sms.__setitem__)
    physical=assembly(admin,style,chips[0],'L黑')
    ok(action(admin,'installAssembly',{'item_id':item,**physical}))
    assert 'rights' not in ok(admin[0].get(f'/api/admin/catalog/issues/{issue}'))
    assert {x['kind'] for x in ok(admin[0].get(f'/api/admin/catalog/items/{item}'))['rights']}=={'renewal','resale'}
    preview=ok(admin[0].get(f'/api/admin/catalog/items/{item}/h5-preview'))
    assert 'chip_uid' not in preview and preview['edition_number']==1
    assert not query(auth_app,'SELECT id FROM scan_log')
    config_chip(auth_app,admin,chips[0])
    ok(action(admin,'toggleItem',{'item_id':item,'status':'active'}))
    reference={'item_id':item,'confirmed':True,'delivery_reference':'隔离验收交付'}
    token=str(uuid.uuid4())
    issued=ok(action(admin,'issueClaimCode',reference,token))
    old=issued['claim_code']
    def reveal_path(code_id):
        return f'/api/admin/catalog/items/{item}/claim-codes/{code_id}/reveal'

    reveal_url=reveal_path(issued['claim_code_id'])
    assert auth_app.test_client().post(reveal_url,headers={'Origin':'http://localhost:5174'},json={}).status_code==401
    assert admin[0].post(reveal_url,headers={'Origin':'http://localhost:5174'},json={}).status_code==403
    result=admin[0].post(reveal_url,headers=admin[1],json={})
    assert ok(result)=={'claim_code':old,'expires_at':issued['expires_at']}
    assert 'no-store' in result.headers['Cache-Control']
    assert old not in admin[0].get(f'/api/admin/catalog/items/{item}').get_data(as_text=True)
    audit=query(auth_app,"SELECT detail FROM admin_audit WHERE action='catalog.viewClaimCode'")
    assert len(audit)==1 and old not in audit[0]['detail']

    previous_expiry=query(auth_app,'SELECT expires_at FROM item_claim_code WHERE id=%s',(issued['claim_code_id'],))[0]['expires_at']
    query(auth_app,'UPDATE item_claim_code SET expires_at=%s WHERE id=%s',(auth_app.test_clock[0],issued['claim_code_id']))
    expired=admin[0].post(reveal_url,headers=admin[1],json={})
    assert expired.status_code==409 and expired.json['code']=='claim_code_expired'
    from core.public_account import code_digest
    legacy=secrets.token_hex(8).upper()
    with auth_app.app_context():
        legacy_digest=code_digest('claim',item,legacy)
    query(auth_app,'UPDATE item_claim_code SET expires_at=%s,code_hash=%s WHERE id=%s',
          (previous_expiry,legacy_digest,issued['claim_code_id']))
    unavailable=admin[0].post(reveal_url,headers=admin[1],json={})
    assert unavailable.status_code==409 and unavailable.json['code']=='claim_code_not_recoverable'
    assert len(query(auth_app,"SELECT id FROM admin_audit WHERE action='catalog.viewClaimCode'"))==1
    receipt=ok(action(admin,'receipt',{'request_id':token}))
    assert 'claim_code' not in receipt
    replacement=ok(action(admin,'reissueClaimCode',reference))
    fresh=replacement['claim_code']
    assert fresh!=old
    assert admin[0].post(reveal_url,headers=admin[1],json={}).status_code==409
    fresh_url=reveal_path(replacement['claim_code_id'])
    assert ok(admin[0].post(fresh_url,headers=admin[1],json={}))['claim_code']==fresh
    for event in query(auth_app,"SELECT detail FROM admin_audit WHERE action IN ('catalog.issueClaimCode','catalog.reissueClaimCode')"):
        assert old not in event['detail'] and fresh not in event['detail']

    clients=[auth_app.test_client(),auth_app.test_client()]
    uid=query(auth_app,'SELECT chip_uid FROM chip WHERE id=%s',(chips[0],))[0]['chip_uid']
    with auth_app.app_context():keys=target_keys('fashion',uid)
    public_id = query(auth_app,'SELECT public_id AS ref FROM item WHERE id=%s',(item,))[0]['ref']
    payloads=[]
    public_uids=[]
    for offset,client in enumerate(clients):
        phone=f'1390000970{offset}'
        challenge=ok(client.post('/api/public/sms/send',headers=ORIGIN,json={'phone':phone}))['challenge_id']
        assert client.post('/api/public/sms/send',headers=ORIGIN,json={'phone':phone}).status_code==429
        session=ok(client.post('/api/public/sms/verify',headers=ORIGIN,json={'challenge_id':challenge,'code':sms[phone]}))['account']
        assert session['phone']!=phone
        assert uuid.UUID(session['uid']).version == 4
        public_uids.append(session['uid'])
        view=ok(client.post('/api/public/tap/verify',headers=ORIGIN,json=reading(keys,uid,3+offset)))
        assert view['claim_state']=='available' and view['public_id']==public_id and 'item_id' not in view
        payloads.append({'tap_token':view['tap_token'],'claim_code':fresh})
    path=f'/api/public/items/{public_id}/claim'
    assert clients[0].post(path,headers=ORIGIN,json={**payloads[0],'tap_token':'0'*64}).status_code==403
    assert clients[0].post(path,headers=ORIGIN,json={**payloads[0],'claim_code':legacy}).status_code==400
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda pair:pair[0].post(path,headers=ORIGIN,json=pair[1]),zip(clients,payloads)))
    assert sorted(x.status_code for x in responses)==[200,409]
    assert admin[0].post(fresh_url,headers=admin[1],json={}).status_code==409
    winner=next(i for i,x in enumerate(responses) if x.status_code==200)
    assert ok(clients[winner].post(path,headers=ORIGIN,json=payloads[winner]))['state']=='mine'
    assert ok(clients[winner].get(f'/api/public/me/items/{public_id}'))['item']['public_id']==public_id
    assert clients[1-winner].get(f'/api/public/me/items/{public_id}').status_code==404
    detail = admin[0].get(f'/api/admin/catalog/items/{item}')
    owners = ok(detail)['owners']
    assert len(owners) == 1 and owners[0]['is_active']
    assert owners[0]['masked_phone'] == f'139****970{winner}'
    assert f'1390000970{winner}' not in detail.get_data(as_text=True)
    holder_uid = owners[0]['user_id']
    assert uuid.UUID(holder_uid).version == 7
    public_uid = public_uids[winner]
    guest = auth_app.test_client()
    touch = lambda client, counter: ok(client.post('/api/public/tap/verify',headers=ORIGIN,json=reading(keys,uid,counter)))
    assert touch(clients[winner],5)['verified'] and touch(clients[1-winner],6)['verified'] and touch(guest,7)['verified']
    assert touch(guest,7)['reason']=='replay_suspect'
    auth_app.config['H5_LEGACY_ITEM_UNTIL']='2099-01-01T00:00:00+00:00'
    legacy_path=f'/api/public/me/items/{item}'
    private=ok(clients[winner].get(legacy_path))['item']
    assert private['public_id']==public_id and 'item_id' not in private
    assert guest.get(legacy_path).status_code==401 and clients[1-winner].get(legacy_path).status_code==404
    auth_app.config['H5_LEGACY_ITEM_UNTIL']='2000-01-01T00:00:00+00:00'
    assert clients[winner].get(legacy_path).status_code==404
    activity = ok(admin[0].get('/api/admin/catalog/activity',query_string={'item_id':item}))['items']
    assert [(e['event'],e['user_uid']) for e in activity].count(('claim',public_uid)) == 1
    assert sorted((e['actor_state'],e['user_uid'] or '') for e in activity if e['event']=='tap') == sorted([('account',uid) for uid in public_uids]*2+[('anonymous','')])
    card = ok(admin[0].get(f'/api/admin/catalog/users/{public_uid}/card'))
    assert card == {'public_uid':public_uid,'nickname':None,'masked_phone':f'139****970{winner}'}
    accounts = ok(admin[0].get('/api/admin/catalog/users', query_string={'keyword':public_uid}))['items']
    assert [(a['id'],a['public_uid']) for a in accounts] == [(holder_uid,public_uid)]
    reveal = f"/api/admin/catalog/items/{item}/owners/{owners[0]['id']}/phone"
    assert auth_app.test_client().post(reveal, headers={'Origin':'http://localhost:5174'}, json={}).status_code == 401
    assert admin[0].post(reveal, headers={'Origin':'http://localhost:5174'}, json={}).status_code == 403
    response = admin[0].post(reveal, headers=admin[1], json={})
    assert ok(response)['phone'] == f'1390000970{winner}'
    assert 'no-store' in response.headers['Cache-Control']
    events = query(auth_app,"SELECT detail FROM admin_audit WHERE action='catalog.viewHolderPhone'")
    assert len(events) == 1 and public_uid in events[0]['detail']
    assert f'1390000970{winner}' not in events[0]['detail']
    assert ok(admin[0].post(f'/api/admin/catalog/users/{public_uid}/phone',headers=admin[1],json={}))['phone'] == f'1390000970{winner}'
    account_events = query(auth_app,"SELECT target_id,detail FROM admin_audit WHERE action='catalog.viewUserPhone'")
    assert [event['target_id'] for event in account_events] == [public_uid]
    assert f'1390000970{winner}' not in account_events[0]['detail']
    query(auth_app, 'UPDATE user SET phone=%s WHERE uid=%s', ('13900009799', holder_uid))
    account = ok(clients[winner].get('/api/public/account/session'))['account']
    assert account == {'uid': public_uid, 'phone': '139****9799'}
    assert query(auth_app, 'SELECT uid FROM user WHERE phone=%s', ('13900009799',))[0]['uid'] == holder_uid
    assert len(query(auth_app,"SELECT id FROM ownership_history WHERE item_id=%s AND action='bind'",(item,)))==1
    assert query(auth_app,'SELECT consumed_at FROM item_claim_code WHERE id=%s',(receipt['claim_code_id'],))[0]['consumed_at'] is None
    assert len(query(auth_app,'SELECT id FROM item_claim_code WHERE item_id=%s AND consumed_at IS NOT NULL',(item,)))==1


@pytest.fixture
def claim_ready(auth_app, catalog):
    """经真实后台接口建立可认领物品；短信只交给本测试的内存收件箱。"""
    admin, style, _, item, chips = catalog
    sms = {}
    auth_app.config.update(PUBLIC_ORIGIN=ORIGIN['Origin'],
                           SMS_CODE_HASH_KEY=secrets.token_hex(32),
                           SMS_PROVIDER='gateway', TEST_SMS_SENDER=sms.__setitem__)
    ok(action(admin, 'installAssembly', {'item_id': item, **assembly(admin, style, chips[0], 'L黑')}))
    config_chip(auth_app, admin, chips[0])
    ok(action(admin, 'toggleItem', {'item_id': item, 'status': 'active'}))
    issued = ok(action(admin, 'issueClaimCode', {
        'item_id': item, 'confirmed': True, 'delivery_reference': '隔离过期认领验收',
    }))
    uid = query(auth_app, 'SELECT chip_uid FROM chip WHERE id=%s', (chips[0],))[0]['chip_uid']
    with auth_app.app_context():
        keys = target_keys('fashion', uid)
    return item, uid, keys, issued, sms


def test_expired_tap_keeps_account_and_fresh_tap_resumes_claim(auth_app, claim_ready):
    item, uid, keys, issued, sms = claim_ready
    client = auth_app.test_client()
    phone = '13900009703'
    challenge = ok(client.post('/api/public/sms/send', headers=ORIGIN, json={'phone': phone}))['challenge_id']
    account = ok(client.post('/api/public/sms/verify', headers=ORIGIN,
                            json={'challenge_id': challenge, 'code': sms[phone]}))['account']
    view = ok(client.post('/api/public/tap/verify', headers=ORIGIN, json=reading(keys, uid, 3)))
    # 只推进服务时钟，不伪造无效 token，直接验证自然过期边界。
    auth_app.test_clock[0] += timedelta(seconds=view['expires_in'] + 1)
    ref = view['public_id']
    response = client.post(f'/api/public/items/{ref}/claim', headers=ORIGIN,
                           json={'tap_token': view['tap_token'], 'claim_code': issued['claim_code']})
    assert response.status_code == 403 and response.json['code'] == 'retap_required'
    assert response.json['message'] == '请重新碰一下物品，再继续认领。'
    assert ok(client.get('/api/public/account/session'))['account'] == account
    assert not query(auth_app, 'SELECT id FROM ownership WHERE item_id=%s', (item,))
    assert query(auth_app, 'SELECT consumed_at FROM item_claim_code WHERE id=%s',
                 (issued['claim_code_id'],))[0]['consumed_at'] is None
    renewed = ok(client.post('/api/public/tap/verify', headers=ORIGIN, json=reading(keys, uid, 4)))
    assert renewed['tap_token'] != view['tap_token']
    result = ok(client.post(f'/api/public/items/{ref}/claim', headers=ORIGIN,
                            json={'tap_token': renewed['tap_token'], 'claim_code': issued['claim_code']}))
    assert result['state'] == 'mine'
    assert ok(client.get('/api/public/account/session'))['account'] == account
    assert ok(client.get(f'/api/public/me/items/{ref}'))['item']['public_id'] == ref
    assert len(query(auth_app, 'SELECT id FROM ownership WHERE item_id=%s', (item,))) == 1
    assert query(auth_app, 'SELECT consumed_at FROM item_claim_code WHERE id=%s',
                 (issued['claim_code_id'],))[0]['consumed_at'] is not None
