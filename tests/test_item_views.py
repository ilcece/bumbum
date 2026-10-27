"""持续查看只在专属临时库中验证；合成密钥和Cookie不来自真实卡片。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
import hashlib

import pymysql
import pytest

from core.db import get_database, view_grant_schema
from tests.test_admin_auth import query
from tests.test_admin_chips import logged_in
from tests.test_chip_binding import inventory
from tests.test_chip_keys import keyed, reading
from tests.test_tap_verification import ready, counts

pytestmark = pytest.mark.auth_database
ORIGIN = 'http://127.0.0.1:5175'


def open_view(app, ready, counter=9):
    client = app.test_client()
    response = client.post('/api/tap/verify', json={**reading(ready[1], ready[0][1]['chip_uid'], counter), 'browser_view': True}, headers={'Origin': ORIGIN})
    assert response.status_code == 200 and response.json['data']['verified']
    return client, response.json['data'], response


def route(data):
    return f"/api/tap/items/{data['item_id']}/view"


def test_view_cookie_latest_and_independent_expiries(auth_app, ready):
    client, data, response = open_view(auth_app, ready)
    cookie = response.headers['Set-Cookie']
    assert 'HttpOnly' in cookie and 'SameSite=Strict' in cookie and 'Max-Age' not in cookie and 'Domain=' not in cookie
    assert f"Path=/api/tap/items/{data['item_id']}" in cookie
    assert '_view_cookie' not in data and data['view_path'] == f"/tap/items/{data['item_id']}"
    with auth_app.app_context():
        with get_database().cursor() as cursor:
            assert view_grant_schema(cursor) == 'ready'
    assert counts(auth_app) == (1, 2)
    original = query(auth_app,"SELECT * FROM tap_grant WHERE allowed_action='view'")[0]
    auth_app.test_clock[0] += timedelta(minutes=6)
    query(auth_app,"UPDATE fashion_item_profile SET name='最新外套'")
    first = client.get(route(data))
    assert first.status_code == 200 and first.json['data']['profile']['name'] == '最新外套'
    assert set(first.json['data']['profile']) == {'name','description','material','care_instructions','image_urls'}
    assert first.json['data']['verified_at'] == data['verified_at'] and first.json['data']['retrieved_at'] != data['retrieved_at']
    assert client.get(f"/api/fashion/items/{data['item_id']}/detail",headers={'X-Tap-Token':data['tap_token']}).status_code == 403
    renewed = query(auth_app,"SELECT * FROM tap_grant WHERE allowed_action='view'")[0]
    assert renewed['expires_at'] == auth_app.test_clock[0]+timedelta(hours=24) and renewed['created_at'] == original['created_at']
    assert counts(auth_app) == (1,2)
    auth_app.test_clock[0] += timedelta(hours=24)
    assert client.get(route(data)).json['code'] == 'invalid_view_session'
    assert query(auth_app,"SELECT expires_at FROM tap_grant WHERE allowed_action='view'")[0]['expires_at'] == renewed['expires_at']


@pytest.mark.parametrize('body', [None, 'true', 1, {}, []])
def test_browser_mode_requires_boolean(auth_app, ready, body):
    payload = {**reading(ready[1],ready[0][1]['chip_uid'],9),'browser_view':body}
    assert auth_app.test_client().post('/api/tap/verify',json=payload,headers={'Origin':ORIGIN}).status_code == 400
    assert counts(auth_app) == (0,0)


@pytest.mark.parametrize('origin', [None, 'null', 'https://other.example', 'http://localhost:5174'])
def test_browser_mode_cannot_be_issued_cross_origin(auth_app, ready, origin):
    headers = {'Origin':origin} if origin else {}
    result = auth_app.test_client().post('/api/tap/verify',json={**reading(ready[1],ready[0][1]['chip_uid'],9),'browser_view':True},headers=headers)
    assert result.status_code == 403 and counts(auth_app) == (0,0)


@pytest.mark.parametrize('mode', ['disabled','draft','lost','unprovisioned','revoked','keys','profile','unbound'])
def test_current_state_is_rechecked_and_failures_do_not_renew(auth_app, ready, mode):
    client,data,_ = open_view(auth_app,ready)
    expiry = query(auth_app,"SELECT expires_at FROM tap_grant WHERE allowed_action='view'")[0]['expires_at']
    auth_app.test_clock[0] += timedelta(minutes=10)
    if mode in {'disabled','draft'}: query(auth_app,'UPDATE item SET status=%s',(mode,))
    elif mode == 'lost': query(auth_app,"UPDATE chip SET chip_status='lost'")
    elif mode == 'unprovisioned': query(auth_app,'UPDATE chip SET provisioned_at=NULL')
    elif mode == 'revoked': query(auth_app,"UPDATE tap_grant SET consumed_at=%s WHERE allowed_action='view'",(auth_app.test_clock[0],))
    elif mode == 'keys': query(auth_app,'DELETE FROM chip_key')
    elif mode == 'profile': query(auth_app,'DELETE FROM fashion_item_profile')
    elif mode == 'unbound': query(auth_app,"UPDATE chip SET item_id=NULL,chip_status='pending'")
    result=client.get(route(data))
    assert result.status_code in {403,409} and 'Set-Cookie' not in result.headers
    assert 'profile' not in result.json.get('data',{})
    assert counts(auth_app)==(1,2)
    assert query(auth_app,"SELECT expires_at FROM tap_grant WHERE allowed_action='view'")[0]['expires_at']==expiry


def test_cookie_path_and_types_are_not_interchangeable(auth_app,ready):
    client,data,response=open_view(auth_app,ready)
    token=client.get_cookie('bumbum_item_view',path=f"/api/tap/items/{data['item_id']}").value
    assert hashlib.sha256(token.encode()).digest() == query(auth_app,"SELECT token_hash FROM tap_grant WHERE allowed_action='view'")[0]['token_hash']
    assert token not in response.get_data(as_text=True)
    assert client.get(f"/api/fashion/items/{data['item_id']}/detail",headers={'X-Tap-Token':token}).status_code==403
    assert client.get(f"/api/tap/items/{data['item_id']+1}/view").status_code==403
    assert auth_app.test_client().get(route(data),headers={'X-Tap-Token':data['tap_token']}).status_code==400
    other=auth_app.test_client()
    other.set_cookie('bumbum_item_view',data['tap_token'],path=f"/api/tap/items/{data['item_id']}")
    assert other.get(route(data)).status_code==403
    for kwargs in ({'headers':{'Origin':'https://other.example'}},{'headers':{'Sec-Fetch-Site':'cross-site'}},{'query_string':{'item_id':data['item_id']}},{'data':'{}'}):
        assert client.get(route(data),**kwargs).status_code in {400,403}


def test_view_failure_rolls_back_renewal_and_creation(auth_app,ready,monkeypatch):
    execute=pymysql.cursors.DictCursor.execute
    def fail(cursor,sql,args=None):
        if sql.startswith('INSERT INTO tap_grant') and args[3]=='view':
            raise pymysql.OperationalError(2000,'合成写入失败')
        return execute(cursor,sql,args)
    monkeypatch.setattr(pymysql.cursors.DictCursor,'execute',fail)
    result=auth_app.test_client().post('/api/tap/verify',json={**reading(ready[1],ready[0][1]['chip_uid'],9),'browser_view':True},headers={'Origin':ORIGIN})
    assert result.status_code==503 and 'Set-Cookie' not in result.headers
    assert counts(auth_app)==(0,0)
    assert query(auth_app,'SELECT last_verified_counter FROM chip')[0]['last_verified_counter']==8


def test_renewal_storage_failure_returns_fault_without_count_or_renew(auth_app,ready,monkeypatch):
    client,data,_=open_view(auth_app,ready)
    before=query(auth_app,"SELECT * FROM tap_grant ORDER BY id")
    auth_app.test_clock[0]+=timedelta(minutes=8)
    execute=pymysql.cursors.DictCursor.execute
    def fail(cursor,sql,args=None):
        if sql.startswith('UPDATE tap_grant SET expires_at='):raise pymysql.OperationalError(2000,'合成续期失败')
        return execute(cursor,sql,args)
    monkeypatch.setattr(pymysql.cursors.DictCursor,'execute',fail)
    result=client.get(route(data))
    assert result.status_code==503 and result.json.get('error_id')
    assert 'Set-Cookie' not in result.headers and counts(auth_app)==(1,2)
    assert query(auth_app,'SELECT * FROM tap_grant ORDER BY id')==before


def test_production_cookie_flags_and_missing_004_are_explicit(auth_app,ready):
    auth_app.config.update(APP_ENV='production',PUBLIC_ORIGIN='https://nfc.bumbum.cc')
    client=auth_app.test_client()
    payload={**reading(ready[1],ready[0][1]['chip_uid'],9),'browser_view':True}
    response=client.post('/api/tap/verify',json=payload,headers={'Origin':'https://nfc.bumbum.cc'})
    assert response.status_code==200 and 'Secure;' in response.headers['Set-Cookie']
    query(auth_app,"DELETE FROM tap_grant WHERE allowed_action='view'")
    query(auth_app,"ALTER TABLE tap_grant MODIFY allowed_action ENUM('read','bind') NOT NULL")
    try:
        payload.update(reading(ready[1],ready[0][1]['chip_uid'],10))
        failed=client.post('/api/tap/verify',json=payload,headers={'Origin':'https://nfc.bumbum.cc'})
        assert failed.status_code==503 and 'Set-Cookie' not in failed.headers
        assert query(auth_app,'SELECT last_verified_counter FROM chip')[0]['last_verified_counter']==9
    finally:query(auth_app,Path('db/migrations/004_view_grants.sql').read_text())


def test_short_mode_false_does_not_create_browser_qualification(auth_app,ready):
    response=auth_app.test_client().post('/api/tap/verify',json={**reading(ready[1],ready[0][1]['chip_uid'],9),'browser_view':False})
    assert response.status_code==200 and response.json['data']['verified']
    assert counts(auth_app)==(1,1) and 'Set-Cookie' not in response.headers
