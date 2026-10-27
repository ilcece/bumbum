"""专属临时MySQL核对真实事务、两项目验证、凭证、事件与跨进程限流。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import multiprocessing
import secrets

import pymysql
import pytest

from core import tap_verification as service
from tests.test_admin_auth import query
from tests.test_admin_chips import logged_in
from tests.test_chip_binding import inventory, item, chip, bind
from tests.test_chip_keys import keyed, generated, reading, confirmation, post

pytestmark = pytest.mark.auth_database


@pytest.fixture
def ready(auth_app, keyed):
    keys = generated(auth_app, keyed)
    assert post(keyed, 'confirm-provisioning', confirmation(keyed, keys)).status_code == 200
    query(auth_app, "INSERT INTO fashion_item_profile(item_id,name,material,image_urls) VALUES (%s,'测试外套','棉','[\"https://example.com/item.jpg\"]')", (keyed[1]['item_id'] or query(auth_app, 'SELECT item_id FROM chip')[0]['item_id'],))
    query(auth_app, "UPDATE item SET status='active'")
    return keyed, keys


def tap(app, ready, counter=9, **kwargs):
    keyed, keys = ready
    return app.test_client().post('/api/tap/verify', json=reading(keys, keyed[1]['chip_uid'], counter), **kwargs)


def counts(app):
    return query(app, 'SELECT COUNT(*) AS n FROM scan_log WHERE verify_result=\'pass\'')[0]['n'], query(app, 'SELECT COUNT(*) AS n FROM tap_grant')[0]['n']


def test_success_get_detail_and_statistics_source(auth_app, ready):
    assert auth_app.test_client().get('/api/ready').status_code == 200
    assert counts(auth_app) == (0, 0)
    response = tap(auth_app, ready)
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
    data = response.json['data']
    assert data['verified'] and data['project'] == 'fashion' and data['expires_in'] == 300
    assert data['item_detail']['name'] == '测试外套' and data['item_detail']['image_urls'] == ['https://example.com/item.jpg']
    assert not data['owner_bound']
    token = data['tap_token']
    grant = query(auth_app, 'SELECT * FROM tap_grant')[0]
    assert grant['token_hash'] == hashlib.sha256(token.encode()).digest() and grant['allowed_action'] == 'bind'
    assert grant['expires_at'] == auth_app.test_clock[0] + timedelta(seconds=300)
    event = query(auth_app, 'SELECT * FROM scan_log')[0]
    assert event['item_id'] == data['item_id'] and event['chip_id'] == ready[0][1]['id'] and event['scan_counter'] == 9
    assert all(event[name] is None for name in ('picc_data', 'cmac', 'user_agent', 'ip_hash'))
    for _ in range(2):
        detail = auth_app.test_client().get(f"/api/fashion/items/{data['item_id']}/detail", headers={'X-Tap-Token': token})
        assert detail.status_code == 200 and detail.json['data']['profile']['name'] == '测试外套'
        assert 'chip_uid' not in detail.get_data(as_text=True)
    assert counts(auth_app) == (1, 1)
    assert query(auth_app, 'SELECT consumed_at FROM tap_grant')[0]['consumed_at'] is None
    assert tap(auth_app, ready, 20).json['data']['verified']
    result = query(auth_app, "SELECT COUNT(*) AS taps,COUNT(DISTINCT item_id) AS items FROM scan_log WHERE verify_result='pass'")[0]
    assert result == {'taps': 2, 'items': 1}
    assert token not in str(query(auth_app, 'SELECT * FROM scan_log'))


@pytest.mark.parametrize('body', [{}, [], None, {'picc_data': 'A'*32, 'cmac':'A'*16,'project':'fashion'}, {'picc_data': 'Ａ'*32, 'cmac':'A'*16}, {'picc_data': 'A'*31, 'cmac':'A'*16}, {'picc_data': 'A'*32, 'cmac':123}])
def test_strict_body_never_advances(auth_app, ready, body):
    import json
    response = auth_app.test_client().post('/api/tap/verify', data=json.dumps(body), content_type='application/json')
    assert response.status_code == 400
    assert counts(auth_app) == (0,0)
    assert query(auth_app, 'SELECT last_verified_counter FROM chip')[0]['last_verified_counter'] == 8


def test_content_query_method_and_size_boundaries(auth_app, ready):
    client = auth_app.test_client()
    assert client.get('/api/tap/verify').status_code == 405
    assert client.post('/api/tap/verify?token=forbidden', json={}).status_code == 400
    assert client.post('/api/tap/verify', data='{}', content_type='text/plain').status_code == 400
    assert client.post('/api/tap/verify', data='x'*9000, content_type='application/json').status_code == 400
    assert counts(auth_app) == (0,0)


@pytest.mark.parametrize('mode,reason', [('mac','cmac_fail'), ('uid','unknown_chip'), ('layout','decrypt_fail'), ('old','replay_suspect'), ('equal','replay_suspect'), ('max','not_ready')])
def test_bad_or_old_readings_never_issue_grant(auth_app, ready, mode, reason):
    keys = ready[1]
    counter = {'old':7, 'equal':8, 'max':0xFFFFFF}.get(mode, 9)
    payload = reading(keys, '04:00:00:00:00:00:FF' if mode == 'uid' else ready[0][1]['chip_uid'], counter)
    if mode == 'mac': payload['cmac'] = '0'*16
    if mode == 'layout':
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        cipher = Cipher(algorithms.AES(bytes.fromhex(keys['K1'])), modes.CBC(bytes(16))).encryptor()
        payload['picc_data'] = (cipher.update(b'\xC6' + bytes(15)) + cipher.finalize()).hex()
    response = auth_app.test_client().post('/api/tap/verify', json=payload)
    assert response.status_code == 200 and response.json['data']['reason'] == reason
    assert counts(auth_app) == (0,0)
    assert query(auth_app, 'SELECT last_verified_counter FROM chip')[0]['last_verified_counter'] == 8
    event = query(auth_app, 'SELECT * FROM scan_log')[0]
    assert (event['chip_id'] is None) == (mode in {'mac','uid','layout'})


@pytest.mark.parametrize('mode,reason', [('draft','not_ready'),('disabled_item','disabled'),('archived','disabled'),('disabled_chip','disabled'),('lost','disabled'),('unprovisioned','not_ready'),('no_profile','not_ready'),('no_keys','not_ready'),('unbound','not_ready')])
def test_states_do_not_count(auth_app, ready, mode, reason):
    if mode in {'draft','archived'}: query(auth_app, 'UPDATE item SET status=%s', (mode,))
    elif mode == 'disabled_item': query(auth_app, "UPDATE item SET status='disabled'")
    elif mode == 'disabled_chip': query(auth_app, "UPDATE chip SET chip_status='disabled'")
    elif mode == 'lost': query(auth_app, "UPDATE chip SET chip_status='lost'")
    elif mode == 'unprovisioned': query(auth_app, 'UPDATE chip SET provisioned_at=NULL')
    elif mode == 'no_profile': query(auth_app, 'DELETE FROM fashion_item_profile')
    elif mode == 'no_keys': query(auth_app, 'DELETE FROM chip_key')
    elif mode == 'unbound': query(auth_app, "UPDATE chip SET item_id=NULL,chip_status='pending'")
    response = tap(auth_app, ready)
    assert response.json['data']['reason'] == reason
    assert counts(auth_app) == (0,0)


@pytest.mark.parametrize('mode', ['meta','root','storage','cipher','version','missing'])
def test_service_errors_have_safe_id_and_no_business_success(auth_app, ready, mode, caplog):
    if mode in {'meta','root','storage','missing'}:
        name = {'meta':'SDM_META_KEY_V1','root':'MASTER_KEY_FASHION','storage':'STORAGE_ENCRYPTION_KEY','missing':'SDM_META_KEY_V1'}[mode]
        auth_app.config[name] = '' if mode == 'missing' else secrets.token_hex(32 if mode == 'storage' else 16)
    elif mode == 'cipher': query(auth_app, 'UPDATE chip_key SET encrypted_keys=%s',(bytes(16),))
    else: query(auth_app, "UPDATE chip_key SET key_version='v2'")
    response = tap(auth_app, ready)
    # 错误的K1可能产生无法解析的布局；它不能被当成成功身份。
    if mode == 'meta' and response.status_code == 200:
        assert not response.json['data']['verified']
    else:
        assert response.status_code == 503 and response.json['error_id']
    assert counts(auth_app) == (0,0)
    assert all(value not in response.get_data(as_text=True) + caplog.text for value in ready[1].values())


@pytest.mark.parametrize('mode', ['missing','expired','consumed','wrong_item','chip_disabled','item_disabled','rebound','no_profile'])
def test_detail_rechecks_permission_every_time(auth_app, ready, mode):
    data = tap(auth_app, ready).json['data']
    headers = {'X-Tap-Token':data['tap_token']}
    target = data['item_id']
    if mode == 'missing': headers = {}
    elif mode == 'expired': auth_app.test_clock[0] += timedelta(seconds=300)
    elif mode == 'consumed': query(auth_app, 'UPDATE tap_grant SET consumed_at=%s',(auth_app.test_clock[0],))
    elif mode == 'wrong_item': target += 1
    elif mode == 'chip_disabled': query(auth_app, "UPDATE chip SET chip_status='disabled'")
    elif mode == 'item_disabled': query(auth_app, "UPDATE item SET status='disabled'")
    elif mode == 'rebound': query(auth_app, "UPDATE chip SET item_id=NULL,chip_status='pending'")
    else: query(auth_app, 'DELETE FROM fashion_item_profile')
    response = auth_app.test_client().get(f'/api/fashion/items/{target}/detail',headers=headers)
    assert response.status_code == 403 and response.json['code'] == 'invalid_tap_token'
    assert counts(auth_app) == (1,1)


def test_both_projects_and_wrong_project_detail(auth_app, ready):
    assert tap(auth_app, ready).json['data']['verified']
    session = ready[0][0]
    target = item(auth_app, project='jewelry', n=2)
    source = chip(session, n=2)
    assert bind(session, source, target).status_code == 200
    pair = session, source
    keys = generated(auth_app, pair)
    assert post(pair, 'confirm-provisioning', confirmation(pair, keys)).status_code == 200
    query(auth_app,"INSERT INTO jewelry_item_profile(item_id,name,meaning) VALUES (%s,'平安扣','平安')",(target['id'],))
    query(auth_app,"UPDATE item SET status='active' WHERE id=%s",(target['id'],))
    response = tap(auth_app, (pair, keys))
    data = response.json['data']
    assert data['verified'] and data['project'] == 'jewelry' and data['item_detail']['meaning'] == '平安'
    assert data['item_detail'].get('care_instructions') is None
    result = auth_app.test_client().get(f"/api/fashion/items/{target['id']}/detail",headers={'X-Tap-Token':data['tap_token']})
    assert result.status_code == 409 and result.json['code'] == 'project_mismatch'
    groups = query(auth_app,"SELECT p.code,COUNT(*) AS n FROM scan_log s JOIN project p ON p.id=s.project_id WHERE s.verify_result='pass' GROUP BY p.code ORDER BY p.code")
    assert groups == [{'code':'fashion','n':1},{'code':'jewelry','n':1}]
    assert counts(auth_app) == (2,2)


@pytest.mark.parametrize('stage', ['grant','counter','event','commit_before','commit_after','rate_commit'])
def test_each_storage_failure_is_atomic(auth_app, ready, monkeypatch, stage):
    execute = pymysql.cursors.DictCursor.execute
    commit = pymysql.connections.Connection.commit
    commits = [0]
    def fail_execute(cursor, sql, args=None):
        prefixes = {'grant':'INSERT INTO tap_grant','counter':'UPDATE chip SET last_verified_counter','event':'INSERT INTO scan_log'}
        if stage in prefixes and sql.startswith(prefixes[stage]):
            raise pymysql.OperationalError(2013, '合成秘密不要输出')
        return execute(cursor, sql, args)
    def fail_commit(connection):
        commits[0] += 1
        if (stage == 'rate_commit' and commits[0] == 1) or (stage.startswith('commit_') and commits[0] == 2):
            if stage == 'commit_after': commit(connection)
            raise pymysql.OperationalError(2013, '合成提交结果未知')
        return commit(connection)
    with monkeypatch.context() as patch:
        patch.setattr(pymysql.cursors.DictCursor,'execute',fail_execute)
        patch.setattr(pymysql.connections.Connection,'commit',fail_commit)
        response = tap(auth_app, ready)
    assert response.status_code == 503 and response.json['error_id']
    committed = stage == 'commit_after'
    assert counts(auth_app) == ((1,1) if committed else (0,0))
    assert query(auth_app,'SELECT last_verified_counter FROM chip')[0]['last_verified_counter'] == (9 if committed else 8)
    if committed: assert tap(auth_app, ready).json['data']['reason'] == 'replay_suspect'


def test_same_reading_concurrency_and_persisted_replay(auth_app, ready):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: tap(auth_app, ready), range(4)))
    assert all(result.status_code == 200 for result in results)
    assert sum(result.json['data']['verified'] for result in results) == 1
    assert counts(auth_app) == (1,1)
    from app import create_app
    restarted = create_app(dict(auth_app.config))
    assert not tap(restarted, ready).json['data']['verified']


def test_rate_window_bad_requests_and_proxy_header(auth_app, ready):
    auth_app.config['TAP_VERIFY_PER_MINUTE'] = 2
    client = auth_app.test_client()
    assert client.post('/api/tap/verify',json={}).status_code == 400
    assert client.post('/api/tap/verify',json={},headers={'X-Forwarded-For':'192.0.2.1','X-Real-IP':'192.0.2.2'}).status_code == 400
    limited = tap(auth_app, ready)
    assert limited.status_code == 429 and limited.headers['Retry-After'] == '60'
    auth_app.test_clock[0] += timedelta(minutes=1)
    assert tap(auth_app, ready).json['data']['verified']
    assert query(auth_app,'SELECT attempt_count FROM security_rate_limit')[0]['attempt_count'] == 1


def test_limits_shared_across_actual_processes(auth_app, ready):
    if 'fork' not in multiprocessing.get_all_start_methods():
        pytest.skip('此多进程用例需要fork；Windows另以共享数据库并发测试覆盖')
    auth_app.config['TAP_VERIFY_PER_MINUTE'] = 1
    context = multiprocessing.get_context('fork')
    queue = context.Queue()
    def worker():
        queue.put(tap(auth_app, ready).status_code)
    workers = [context.Process(target=worker) for _ in range(3)]
    for process in workers: process.start()
    for process in workers:
        process.join(timeout=15)
        assert process.exitcode == 0
    assert sorted(queue.get(timeout=3) for _ in workers) == [200,429,429]
    assert counts(auth_app) == (1,1)


def test_unique_event_constraint_and_snapshot_survive_unbind(auth_app, ready):
    data = tap(auth_app, ready).json['data']
    source = ready[0][1]
    with pytest.raises(pymysql.IntegrityError):
        query(auth_app,"INSERT INTO scan_log(chip_id,item_id,project_id,chip_uid,scan_counter,verify_result) SELECT chip_id,item_id,project_id,chip_uid,scan_counter,'pass' FROM scan_log WHERE verify_result='pass'")
    with pytest.raises(pymysql.OperationalError):
        query(auth_app,"INSERT INTO scan_log(verify_result) VALUES ('pass')")
    query(auth_app,"UPDATE chip SET item_id=NULL,chip_status='pending'")
    event = query(auth_app,'SELECT item_id,chip_id FROM scan_log')[0]
    assert event == {'item_id':data['item_id'],'chip_id':source['id']}
    assert counts(auth_app) == (1,1)


def test_owned_item_read_grant_and_updated_profile(auth_app, ready):
    query(auth_app, "INSERT INTO user(phone) VALUES ('13800000001') ON DUPLICATE KEY UPDATE phone=phone")
    owner = query(auth_app, "SELECT id FROM user WHERE phone='13800000001'")[0]['id']
    target = query(auth_app, 'SELECT item_id FROM chip')[0]['item_id']
    query(auth_app, 'INSERT INTO ownership(item_id,user_id) VALUES (%s,%s)', (target, owner))
    result = tap(auth_app, ready).json['data']
    assert result['owner_bound'] and query(auth_app, 'SELECT allowed_action FROM tap_grant')[0]['allowed_action'] == 'read'
    query(auth_app, "UPDATE fashion_item_profile SET name='更新后的名称' WHERE item_id=%s", (target,))
    response = auth_app.test_client().get(f'/api/fashion/items/{target}/detail', headers={'X-Tap-Token':result['tap_token']})
    assert response.json['data']['profile']['name'] == '更新后的名称'
    assert '13800000001' not in str(response.json)
    assert auth_app.test_client().post('/api/public/bind',json={}).status_code == 404
    assert auth_app.test_client().post('/api/public/sms/send',json={}).status_code == 404
