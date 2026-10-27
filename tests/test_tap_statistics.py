"""独立临时MySQL验证统计口径、日期、只读快照和真实触碰记录，不连业务库。"""

from datetime import datetime, timedelta
import json

import pymysql
import pytest

from core import tap_statistics as service
from core.db import get_database
from tests.test_admin_auth import query
from tests.test_admin_chips import logged_in
from tests.test_chip_binding import inventory, item, chip, bind
from tests.test_chip_keys import keyed
from tests.test_tap_verification import ready, tap
from tests.test_tap_migration import old_taps

pytestmark = pytest.mark.auth_database
NOW = datetime(2026, 10, 27, 4, 0, 0)


@pytest.fixture(autouse=True)
def database_cutoff(monkeypatch):
    monkeypatch.setattr(service, 'snapshot_time', lambda cursor: NOW)


def stats(session, **parameters):
    return session[0].get('/api/admin/stats/taps', query_string=parameters)


def tracked(app, session, n=1, project='fashion', name='测试服装'):
    target = item(app, project=project, status='active', n=n)
    source = chip(session, n=n)
    assert bind(session, source, target).status_code == 200
    if name is not None:
        table = 'fashion_item_profile' if project == 'fashion' else 'jewelry_item_profile'
        query(app, f'INSERT INTO {table}(item_id,name) VALUES (%s,%s)', (target['id'],name))
    return source, target


def event(app, source, target, counter=1, at=NOW, result='pass'):
    query(app, 'INSERT INTO scan_log(chip_id,item_id,project_id,chip_uid,scan_counter,verify_result,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)',
          (source['id'],target['id'],target['project_id'],source['chip_uid'],counter,result,at))


@pytest.mark.parametrize('period,length', [('7d',7),('30d',30),('all',0)])
def test_empty_is_real_zero_with_exact_dates(inventory, period, length):
    result = stats(inventory, range=period)
    assert result.status_code == 200 and result.headers['Cache-Control'] == 'no-store'
    data = result.json['data']
    assert data['summary'] == {'valid_taps':0,'touched_items':0}
    assert len(data['daily']) == length and all(day['valid_taps'] == 0 for day in data['daily'])
    assert data['first_recorded_at'] is None and data['items'] == [] and data['total_pages'] == 0 and data['page'] == 1
    assert data['period']['to_date'] == '2026-10-27'
    assert data['period']['from_date'] == (None if period == 'all' else '2026-10-21' if period == '7d' else '2026-09-28')


def test_project_aggregation_failure_exclusion_and_history(auth_app, inventory):
    first, target = tracked(auth_app, inventory)
    other, jewelry = tracked(auth_app, inventory, n=2, project='jewelry', name='平安扣')
    event(auth_app, first, target, 1)
    event(auth_app, first, target, 2)
    event(auth_app, other, jewelry, 1)
    for reason in ('cmac_fail','decrypt_fail','unknown_chip','replay_suspect','disabled','not_ready'):
        event(auth_app, first, target, 3, result=reason)
    query(auth_app,"UPDATE item SET status='archived' WHERE id=%s",(target['id'],))
    query(auth_app,"UPDATE chip SET chip_status='disabled' WHERE id=%s",(first['id'],))
    all_data = stats(inventory).json['data']
    assert all_data['summary'] == {'valid_taps':3,'touched_items':2}
    assert stats(inventory,project='fashion').json['data']['summary'] == {'valid_taps':2,'touched_items':1}
    assert stats(inventory,project='jewelry').json['data']['summary'] == {'valid_taps':1,'touched_items':1}
    assert all_data['items'][0]['item_uid'] == target['item_uid']
    assert sum(day['valid_taps'] for day in all_data['daily']) == 3
    assert all(set(row) == {'project','item_uid','name','valid_taps','last_tap_at'} for row in all_data['items'])
    # 历史关联留在日志，不因当前解绑而消失。
    query(auth_app,"UPDATE chip SET chip_status='pending',item_id=NULL WHERE id=%s",(first['id'],))
    assert stats(inventory).json['data']['summary'] == all_data['summary']


def test_beijing_boundaries_first_record_and_future_exclusion(auth_app, inventory):
    source, target = tracked(auth_app, inventory)
    times = [datetime(2026,9,1), datetime(2026,10,20,15,59,59), datetime(2026,10,20,16), datetime(2026,10,26,15,59,59), datetime(2026,10,26,16), NOW, NOW + timedelta(seconds=1)]
    for counter, at in enumerate(times, 1): event(auth_app,source,target,counter,at)
    data = stats(inventory).json['data']
    assert data['summary']['valid_taps'] == 4
    assert data['daily'][0] == {'date':'2026-10-21','valid_taps':1}
    assert data['daily'][-2] == {'date':'2026-10-26','valid_taps':1}
    assert data['daily'][-1] == {'date':'2026-10-27','valid_taps':2}
    assert data['first_recorded_at'] == '2026-09-01T00:00:00Z'
    whole = stats(inventory, range='all').json['data']
    assert whole['summary']['valid_taps'] == 6 and whole['period']['from_date'] == '2026-09-01'
    assert len(whole['daily']) == 57
    searched = stats(inventory,q='不存在').json['data']
    assert searched['first_recorded_at'] == data['first_recorded_at'] and searched['summary'] == data['summary'] and not searched['items']


def test_names_keyword_escaping_order_and_page_clamp(auth_app, inventory):
    for number in range(1,24):
        source, target = tracked(auth_app,inventory,n=number,name='100%_外套' if number == 1 else None)
        event(auth_app,source,target,at=NOW)
    first = stats(inventory).json['data']
    assert first['total_items'] == 23 and len(first['items']) == 20 and first['total_pages'] == 2
    assert first['items'][0]['name'] == '100%_外套' and first['items'][1]['name'] is None
    assert first['items'][0]['item_uid'] < first['items'][1]['item_uid']
    last = stats(inventory,page=999).json['data']
    assert last['page'] == 2 and last['page_adjusted'] and len(last['items']) == 3
    for keyword in ('%', '_', ' 100%_ ', '000001'):
        data = stats(inventory,q=keyword).json['data']
        assert data['total_items'] == 1 and data['summary']['valid_taps'] == 23 and data['filters']['q'] == keyword.strip()
    missing = stats(inventory,q='不存在',page=2).json['data']
    assert missing['page'] == 1 and missing['page_adjusted'] and missing['total_pages'] == 0
    assert missing['summary'] == first['summary']
    assert stats(inventory,q='\u0085  ').json['data']['filters']['q'] == ''


@pytest.mark.parametrize('parameters', [{'project':'all'},{'project':''},{'project':'1'},{'range':'week'},{'page':'０'},{'page':0},{'page':'1.0'},{'page':'2147483648'},{'page_size':101},{'page_size':0},{'q':'字'*129},{'extra':'value'}])
def test_invalid_parameters_rejected(inventory, parameters):
    response = stats(inventory,**parameters)
    assert response.status_code == 400 and response.json['code'] == 'invalid_param'


def test_duplicate_parameters_and_methods(inventory):
    assert inventory[0].get('/api/admin/stats/taps?range=7d&range=all').status_code == 400
    assert inventory[0].post('/api/admin/stats/taps',json={}).status_code == 405


def test_real_verified_tap_and_config_confirmation_count_once(auth_app, ready):
    session = ready[0][0]
    assert stats(session, range='all').json['data']['summary']['valid_taps'] == 0
    assert tap(auth_app,ready).json['data']['verified']
    assert not tap(auth_app,ready).json['data']['verified']
    response = stats(session,range='all').json['data']
    assert response['summary'] == {'valid_taps':1,'touched_items':1}
    assert response['items'][0]['name'] == '测试外套'


def test_same_snapshot_ignores_interleaved_insert_and_rename(auth_app, inventory, monkeypatch):
    source, target = tracked(auth_app,inventory,name='原名称')
    event(auth_app,source,target)
    execute = pymysql.cursors.DictCursor.execute
    changed = [False]
    def interleave(cursor, sql, args=None):
        if sql.startswith('SELECT COUNT(*) AS valid_taps') and not changed[0]:
            changed[0] = True
            event(auth_app,source,target,2)
            query(auth_app,"UPDATE fashion_item_profile SET name='新名称' WHERE item_id=%s",(target['id'],))
        return execute(cursor,sql,args)
    with monkeypatch.context() as patch:
        patch.setattr(pymysql.cursors.DictCursor,'execute',interleave)
        first = stats(inventory).json['data']
    assert changed[0] and first['summary']['valid_taps'] == 1 and first['items'][0]['name'] == '原名称'
    second = stats(inventory).json['data']
    assert second['summary']['valid_taps'] == 2 and second['items'][0]['name'] == '新名称'


def test_read_only_sql_and_no_audit_or_event_mutations(auth_app, inventory, monkeypatch):
    source, target = tracked(auth_app,inventory)
    event(auth_app,source,target)
    before = {table:query(auth_app,f'SELECT COUNT(*) AS n FROM {table}')[0]['n'] for table in ('scan_log','tap_grant','admin_audit','security_rate_limit')}
    statements = []
    execute = pymysql.cursors.DictCursor.execute
    def observe(cursor, sql, args=None):
        statements.append(sql)
        return execute(cursor,sql,args)
    with monkeypatch.context() as patch:
        patch.setattr(pymysql.cursors.DictCursor,'execute',observe)
        assert stats(inventory).status_code == 200
    assert any('CONSISTENT SNAPSHOT, READ ONLY' in sql for sql in statements)
    assert not any(sql.startswith(('INSERT','UPDATE','DELETE')) or 'FOR UPDATE' in sql or 'FOR SHARE' in sql for sql in statements)
    after = {table:query(auth_app,f'SELECT COUNT(*) AS n FROM {table}')[0]['n'] for table in before}
    assert after == before


@pytest.mark.parametrize('stage',['coverage','summary','daily','total','items'])
def test_any_query_failure_is_whole_safe_error(auth_app, inventory, monkeypatch, stage):
    prefixes = {'coverage':'SELECT MIN(s.created_at)', 'summary':'SELECT COUNT(*) AS valid_taps', 'daily':'SELECT DATE(s.created_at', 'total':'SELECT COUNT(*) AS total_items', 'items':'SELECT p.code AS project,i.item_uid'}
    execute = pymysql.cursors.DictCursor.execute
    def fail(cursor,sql,args=None):
        if sql.startswith(prefixes[stage]): raise pymysql.OperationalError(1205,'合成敏感故障原文')
        return execute(cursor,sql,args)
    with monkeypatch.context() as patch:
        patch.setattr(pymysql.cursors.DictCursor,'execute',fail)
        response = stats(inventory)
    assert response.status_code == 503 and response.json['error_id'] and 'data' not in response.json
    assert '敏感' not in json.dumps(response.json)


def test_login_origin_and_revocation(auth_app, inventory):
    assert auth_app.test_client().get('/api/admin/stats/taps').status_code == 401
    assert inventory[0].get('/api/admin/stats/taps',headers={'Origin':'https://other.example'}).status_code == 403
    assert stats(inventory).status_code == 200
    query(auth_app,'UPDATE admin_session SET revoked_at=%s',(auth_app.test_clock[0],))
    assert stats(inventory).status_code == 401


def test_old_structure_is_not_empty_success(auth_app, logged_in, old_taps):
    response = stats(logged_in)
    assert response.status_code == 503 and response.json['error_id'] and '003' in response.json['message']


def test_queries_use_indexes_and_constant_count_on_5000_events(auth_app, inventory, monkeypatch):
    pairs = [tracked(auth_app,inventory,n=number,project='fashion' if number % 2 else 'jewelry') for number in range(1,26)]
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            rows = [(source['id'],target['id'],target['project_id'],source['chip_uid'],counter,NOW-timedelta(days=counter%40))
                    for source,target in pairs for counter in range(1,201)]
            cursor.executemany("INSERT INTO scan_log(chip_id,item_id,project_id,chip_uid,scan_counter,verify_result,created_at) VALUES (%s,%s,%s,%s,%s,'pass',%s)",rows)
        connection.commit()
    execute = pymysql.cursors.DictCursor.execute
    statements = []
    def observe(cursor,sql,args=None):
        if 'FROM scan_log s' in sql: statements.append((sql,tuple(args) if args else ()))
        return execute(cursor,sql,args)
    for parameters in ({'range':'7d'},{'range':'30d','project':'jewelry'},{'range':'all','q':'000001'}):
        statements.clear()
        with monkeypatch.context() as patch:
            patch.setattr(pymysql.cursors.DictCursor,'execute',observe)
            response = stats(inventory,**parameters)
        assert response.status_code == 200 and len(statements) == 5
        assert sum(row['valid_taps'] for row in response.json['data']['daily']) == response.json['data']['summary']['valid_taps']
        with auth_app.app_context():
            connection = get_database()
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                for sql,args in statements:
                    cursor.execute('EXPLAIN ' + sql,args)
                    plans = cursor.fetchall()
                    assert any((row.get('possible_keys') and 'idx_scan_' in row['possible_keys']) or row.get('Extra') == 'Select tables optimized away' for row in plans)
    assert stats(inventory,range='all').json['data']['summary'] == {'valid_taps':5000,'touched_items':25}
