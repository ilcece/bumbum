"""在专属临时MySQL验证首次绑定、权限、争抢和提交不确定结果。"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import json
from datetime import timedelta

import pymysql
import pyotp
import pytest
from werkzeug.security import generate_password_hash

from core import chip_binding
from core.db import get_database
from core.secret_storage import encrypt_totp_secret
from tests.test_admin_auth import ORIGIN, login, query
from tests.test_admin_chips import logged_in

pytestmark = pytest.mark.auth_database


@pytest.fixture
def inventory(auth_app, logged_in):
    for table in ("fashion_item_profile", "jewelry_item_profile", "item"):
        query(auth_app, f"DELETE FROM {table}")
    return logged_in


def item(app, project="fashion", status="draft", n=1):
    uid = f"{'FASH' if project == 'fashion' else 'JEW'}-2026-{n:06d}"
    query(app, "INSERT INTO item(project_id,item_uid,status) SELECT id,%s,%s FROM project WHERE code=%s", (uid, status, project))
    return query(app, "SELECT * FROM item WHERE item_uid=%s", (uid,))[0]


def chip(session, n=1, project=None):
    client, headers = session
    response = client.post('/api/admin/chips', headers=headers, json={"chip_uid": f"04{n:012X}", "project": project, "batch_no": "绑定测试"})
    assert response.status_code == 200
    return response.json['data']['chip']


def bind(session, source, target):
    return session[0].post(f"/api/admin/chips/{source['id']}/bind-item", headers=session[1], json={"item_id": target['id']})


def audits(app):
    return query(app, "SELECT * FROM admin_audit WHERE action='chip.bind_item'")


@pytest.mark.parametrize('project', ['fashion','jewelry'])
@pytest.mark.parametrize('assigned', [False,True])
@pytest.mark.parametrize('status', ['draft','active','disabled'])
def test_bind_and_preserve_real_data(auth_app, inventory, project, assigned, status):
    target = item(auth_app, project, status)
    source = chip(inventory, project=project if assigned else None)
    before = query(auth_app, 'SELECT * FROM chip')[0]
    response = bind(inventory, source, target)
    assert response.status_code == 200
    result = response.json['data']
    assert set(result) == set(source)
    assert result['chip_status'] == 'bound' and result['project'] == project
    assert (result['item_id'], result['item_uid']) == (target['id'],target['item_uid'])
    after = query(auth_app, 'SELECT * FROM chip')[0]
    for key in set(before) - {'project_id','item_id','chip_status','updated_at'}:
        assert after[key] == before[key]
    assert query(auth_app, 'SELECT * FROM item')[0] == target
    record = audits(auth_app)[0]
    assert len(audits(auth_app)) == 1 and record['target_type'] == 'chip'
    assert record['target_id'] == str(source['id']) and len(record['ip_hash']) == 64
    assert json.loads(record['detail']) == {'item_id':target['id'], 'project':project, 'previous_project':project if assigned else None, 'from_status':'pending','to_status':'bound'}
    assert inventory[0].get('/api/admin/chips', query_string={'keyword':source['chip_uid']}).json['data']['items'] == [result]
    assert query(auth_app, 'SELECT COUNT(*) AS n FROM ownership')[0]['n'] == 0
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('value', [None,True,False,0,-1,1.0,'1',[],{},18446744073709551616])
def test_rejects_bad_item_id(auth_app, inventory, value):
    source = chip(inventory)
    response = inventory[0].post(f"/api/admin/chips/{source['id']}/bind-item", headers=inventory[1], json={'item_id':value})
    assert response.status_code == 400 and response.json['code'] == 'invalid_param'
    assert not audits(auth_app)
    assert query(auth_app,'SELECT item_id FROM chip')[0]['item_id'] is None


@pytest.mark.parametrize('body', [{},{'item_id':1,'force':True},{'item_id':1,'project':'fashion'},[],None])
def test_rejects_body_shape(inventory, body):
    assert inventory[0].post('/api/admin/chips/1/bind-item', headers=inventory[1], data=json.dumps(body),content_type='application/json').status_code == 400


@pytest.mark.parametrize('path,status', [('0',400),('18446744073709551616',400),('-1',404),('1.5',404),('abc',404)])
def test_path_boundaries(inventory,path,status):
    assert inventory[0].post(f'/api/admin/chips/{path}/bind-item',headers=inventory[1],json={'item_id':1}).status_code == status


def test_upper_id_and_missing_records(auth_app, inventory):
    target = item(auth_app)
    source = chip(inventory)
    for path, body in [(source['id'],18446744073709551615),(18446744073709551615,target['id'])]:
        response = inventory[0].post(f'/api/admin/chips/{path}/bind-item',headers=inventory[1],json={'item_id':body})
        assert response.status_code == 404
    assert not audits(auth_app)


@pytest.mark.parametrize('mode,code', [('disabled','invalid_state'),('lost','invalid_state'),('archived','invalid_state'),('mismatch','project_mismatch')])
def test_rejects_state_and_project_without_changes(auth_app, inventory, mode, code):
    source = chip(inventory,project='jewelry' if mode == 'mismatch' else None)
    target = item(auth_app,status='archived' if mode == 'archived' else 'draft')
    if mode in {'disabled','lost'}:query(auth_app,'UPDATE chip SET chip_status=%s',(mode,))
    before = query(auth_app,'SELECT * FROM chip')[0]
    response = bind(inventory,source,target)
    assert response.status_code == 409 and response.json['code'] == code
    assert query(auth_app,'SELECT * FROM chip')[0] == before and not audits(auth_app)


@pytest.mark.parametrize('occupant_status', ['bound','disabled','lost'])
def test_duplicates_and_occupied_items(auth_app, inventory, occupant_status):
    target = item(auth_app)
    first, other = chip(inventory),chip(inventory,n=2)
    assert bind(inventory,first,target).status_code == 200
    repeat = bind(inventory,first,target)
    assert repeat.status_code == 409 and repeat.json['code'] == 'already_bound'
    query(auth_app,'UPDATE chip SET chip_status=%s WHERE id=%s',(occupant_status,first['id']))
    before = query(auth_app,'SELECT * FROM chip WHERE id=%s',(other['id'],))[0]
    response = bind(inventory,other,target)
    assert response.status_code == 409 and response.json['code'] == 'item_already_has_chip'
    assert query(auth_app,'SELECT * FROM chip WHERE id=%s',(other['id'],))[0] == before
    assert len(audits(auth_app)) == 1


def test_permissions_and_payload_limits(auth_app, inventory):
    source, target = chip(inventory), item(auth_app)
    path=f"/api/admin/chips/{source['id']}/bind-item"
    assert auth_app.test_client().post(path,headers=ORIGIN,json={'item_id':target['id']}).status_code == 401
    for headers in [{**inventory[1],'Origin':'https://other.example'},{**inventory[1],'X-CSRF-Token':''}]:
        assert inventory[0].post(path,headers=headers,json={'item_id':target['id']}).status_code == 403
    assert inventory[0].post(path+'?x=1',headers=inventory[1],json={'item_id':target['id']}).status_code == 400
    assert inventory[0].post(path,headers=inventory[1],data='x'*9000,content_type='application/json').status_code == 400
    assert not audits(auth_app)


@pytest.mark.parametrize("mode", ["admin", "session", "expiry"])
def test_rechecks_session_inside_transaction(auth_app, inventory, monkeypatch, admin_account, mode):
    source, target = chip(inventory),item(auth_app)
    original = chip_binding.lock_admin_session
    def revoke(cursor):
        if mode == "admin":query(auth_app,"UPDATE admin_user SET status='disabled' WHERE id=%s",(admin_account['id'],))
        elif mode == "session":query(auth_app,"UPDATE admin_session SET revoked_at=CURRENT_TIMESTAMP WHERE admin_id=%s",(admin_account['id'],))
        else:auth_app.test_clock[0] += timedelta(hours=9)
        original(cursor)
    monkeypatch.setattr(chip_binding,'lock_admin_session',revoke)
    assert bind(inventory,source,target).status_code == 401
    assert query(auth_app,'SELECT item_id FROM chip')[0]['item_id'] is None and not audits(auth_app)


@pytest.mark.parametrize('kind', [pymysql.OperationalError,pymysql.IntegrityError])
def test_audit_failure_rolls_back_and_is_not_misclassified(auth_app, inventory, monkeypatch, kind):
    source, target = chip(inventory),item(auth_app)
    before = query(auth_app,'SELECT * FROM chip')[0]
    def fail(*args):raise kind(1062,'合成审计故障')
    monkeypatch.setattr(chip_binding,'record_binding',fail)
    response=bind(inventory,source,target)
    assert response.status_code == 503 and response.json['error_id']
    assert query(auth_app,'SELECT * FROM chip')[0] == before and not audits(auth_app)


@pytest.mark.parametrize('committed', [False,True])
def test_commit_failure_can_mean_unknown_result(auth_app, inventory, monkeypatch, committed):
    source, target = chip(inventory),item(auth_app)
    original=pymysql.connections.Connection.commit
    def fail(connection):
        if committed:original(connection)
        raise pymysql.OperationalError(2013,'合成提交回执丢失')
    with monkeypatch.context() as changes:
        changes.setattr(pymysql.connections.Connection,'commit',fail)
        assert bind(inventory,source,target).status_code == 503
    found=inventory[0].get('/api/admin/chips').json['data']['items'][0]
    assert found['item_id'] == (target['id'] if committed else None)
    assert len(audits(auth_app)) == (1 if committed else 0)


def second_session(app):
    account={'username':'binding-second','password':'synthetic-second-password','secret':pyotp.random_base32()}
    with app.app_context():
        connection=get_database()
        with connection.cursor() as cursor:
            cursor.execute('INSERT INTO admin_user(username,password_hash) VALUES (%s,%s)',(account['username'],generate_password_hash(account['password'])))
            identifier=cursor.lastrowid
            cursor.execute('UPDATE admin_user SET totp_enabled=1,totp_secret_encrypted=%s WHERE id=%s',(encrypt_totp_secret(account['secret'],identifier),identifier))
        connection.commit()
    client=app.test_client()
    assert login(client,app,account).status_code == 200
    return client,{**ORIGIN,'X-CSRF-Token':client.get('/api/admin/auth/session').json['data']['csrf_token']}


@pytest.mark.parametrize('same_chip', [False,True])
def test_two_independent_admins_race(auth_app, inventory, monkeypatch, same_chip):
    sources=[chip(inventory),chip(inventory,n=2)]
    targets=[item(auth_app),item(auth_app,n=2)]
    sessions=[inventory,second_session(auth_app)]
    barrier=Barrier(2)
    original=chip_binding.lock_admin_session
    def together(cursor):
        barrier.wait(timeout=10)
        original(cursor)
    monkeypatch.setattr(chip_binding,'lock_admin_session',together)
    def attempt(index):return bind(sessions[index],sources[0 if same_chip else index],targets[index if same_chip else 0])
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(attempt,range(2)))
    assert sorted(response.status_code for response in responses) == [200,409]
    assert len(audits(auth_app)) == 1
    assert query(auth_app,'SELECT COUNT(*) AS n FROM chip WHERE item_id IS NOT NULL')[0]['n'] == 1


def test_preserves_keys_readings_and_profiles(auth_app, inventory):
    target=item(auth_app)
    source=chip(inventory,project='fashion')
    query(auth_app,"UPDATE chip SET provisioned_at='2025-01-01',last_verified_counter=15,registration_source='nfc_cool' WHERE id=%s",(source['id'],))
    query(auth_app,"INSERT INTO fashion_item_profile(item_id,name,size_chart) VALUES (%s,'原资料',%s)",(target['id'],json.dumps({'合成尺码':'保留'})))
    # 只在专属临时库建立不用于真实加密的密钥占位，以检查绑定不会碰该记录。
    query(auth_app,"INSERT INTO chip_key(chip_id,encrypted_keys,nonce,dek_ciphertext,dek_nonce) VALUES (%s,%s,%s,%s,%s)",(source['id'],b'synthetic',b'0'*12,b'synthetic',b'1'*12))
    before={table:query(auth_app,f'SELECT * FROM {table}') for table in ['chip_key','fashion_item_profile','item']}
    original=query(auth_app,'SELECT * FROM chip')[0]
    assert bind(inventory,source,target).status_code == 200
    after=query(auth_app,'SELECT * FROM chip')[0]
    for key in set(original)-{'item_id','chip_status','updated_at'}:assert after[key] == original[key]
    for table,records in before.items():assert query(auth_app,f'SELECT * FROM {table}') == records


@pytest.mark.parametrize("code", [1213,1205,1452])
def test_lock_and_constraint_failures_are_safe_database_errors(auth_app, inventory, monkeypatch, code):
    source,target=chip(inventory),item(auth_app)
    before=query(auth_app,'SELECT * FROM chip')[0]
    original=pymysql.cursors.DictCursor.execute
    def fail(cursor,sql,args=None):
        if sql.startswith("UPDATE chip SET project_id="):
            kind=pymysql.IntegrityError if code==1452 else pymysql.OperationalError
            raise kind(code,"合成约束或锁故障")
        return original(cursor,sql,args)
    with monkeypatch.context() as changes:
        changes.setattr(pymysql.cursors.DictCursor,'execute',fail)
        response=bind(inventory,source,target)
    assert response.status_code==503 and response.json['error_id']
    assert query(auth_app,'SELECT * FROM chip')[0]==before and not audits(auth_app)
