"""物品完整查询及普通资料一次保存，不改变身份和启停权限。"""

import json

import pymysql
import pytest

from core import admin_items
from tests.test_admin_auth import ORIGIN, query
from tests.test_admin_items import drafts, create

pytestmark = pytest.mark.auth_database


def test_atomic_sku_profile_preserves_size_identity_and_noop(auth_app, drafts):
    client, headers = drafts
    item = create(drafts, sku_code="旧款式").json["data"]
    path = f'/api/admin/items/{item["id"]}'
    query(auth_app, "INSERT INTO fashion_item_profile(item_id,name,size_chart,image_urls) VALUES (%s,'旧名称',JSON_OBJECT('S',80),JSON_ARRAY())", (item['id'],))
    query(auth_app, "UPDATE item SET updated_at='2020-01-01' WHERE id=%s", (item['id'],))
    original = query(auth_app, "SELECT * FROM item WHERE id=%s", (item['id'],))[0]
    profile = {"name": " 新名称 ", "description": " 新介绍 ", "image_urls": ["https://example.com/a.webp"]}
    response = client.patch(path, json={"sku_code": " 新款式 ", "profile": profile}, headers=headers)
    assert response.status_code == 200
    found = response.json['data']
    assert found['sku_code'] == '新款式' and found['profile']['name'] == '新名称'
    assert found['profile']['description'] == '新介绍' and found['profile']['size_chart'] == {'S': 80}
    assert found['linked_chip'] is None and found['keyword_matches'] == []
    after = query(auth_app, "SELECT * FROM item WHERE id=%s", (item['id'],))[0]
    assert after['updated_at'] > original['updated_at']
    assert {k: v for k, v in after.items() if k not in {'sku_code','updated_at'}} == {k: v for k, v in original.items() if k not in {'sku_code','updated_at'}}
    audit = query(auth_app, "SELECT detail FROM admin_audit WHERE action='item.details.update'")
    assert len(audit) == 1
    detail = json.loads(audit[0]['detail'])
    assert detail['project'] == 'fashion' and detail['sku_code'] == {'from': '旧款式', 'to': '新款式'}
    assert set(detail['fields']) == {'sku_code', 'profile.name', 'profile.description', 'profile.image_urls'}
    assert '新介绍' not in audit[0]['detail'] and 'example.com' not in audit[0]['detail']
    assert client.patch(path, json={"sku_code": "新款式", "profile": profile}, headers=headers).status_code == 200
    assert query(auth_app, "SELECT * FROM item WHERE id=%s", (item['id'],))[0] == after
    assert len(query(auth_app, "SELECT detail FROM admin_audit WHERE action='item.details.update'")) == 1
    # 兼容PUT与普通PATCH共用无变化规则，仍只返回profile。
    legacy = client.put(path + '/profile', json=profile, headers=headers)
    assert legacy.status_code == 200 and legacy.json['data'] == found['profile']
    assert not query(auth_app, "SELECT action FROM admin_audit WHERE action='item.profile.save'")


@pytest.mark.parametrize('project,prefix', [('fashion','FASH'), ('jewelry','JEW')])
def test_sku_only_does_not_force_profile_and_can_clear_reuse(auth_app, drafts, project, prefix):
    client, headers = drafts
    item = create(drafts, project=project, item_uid=prefix + '-2026-000002').json['data']
    other = create(drafts, project=project, item_uid=prefix + '-2026-000003', sku_code='重复款式').json['data']
    for value in (' 重复款式 ', 'x' * 64, '  ', None):
        response = client.patch(f'/api/admin/items/{item["id"]}', json={'sku_code': value}, headers=headers)
        assert response.status_code == 200 and response.json['data']['profile'] is None
        assert response.json['data']['sku_code'] == (value.strip() or None if value is not None else None)
    assert client.get(f'/api/admin/items/{other["id"]}').json['data']['sku_code'] == '重复款式'
    if project == 'jewelry':
        assert client.patch(f'/api/admin/items/{item["id"]}', json={'sku_code': '不写入', 'profile': {'name': '不写入'}}, headers=headers).status_code == 409
        assert client.get(f'/api/admin/items/{item["id"]}').json['data']['sku_code'] is None


@pytest.mark.parametrize('failure', ['audit', 'commit', 'permission'])
def test_merged_save_rolls_back_all_fields(auth_app, drafts, monkeypatch, failure):
    client, headers = drafts
    item = create(drafts, sku_code='原款式').json['data']
    before = query(auth_app, 'SELECT * FROM item')
    if failure == 'audit':
        original = pymysql.cursors.DictCursor.execute
        def execute(cursor, sql, args=None):
            if sql.startswith('INSERT INTO admin_audit'):
                raise pymysql.OperationalError('合成审计失败')
            return original(cursor, sql, args)
        monkeypatch.setattr(pymysql.cursors.DictCursor, 'execute', execute)
    elif failure == 'commit':
        def fail(_connection):
            raise pymysql.OperationalError('合成提交失败')
        monkeypatch.setattr(pymysql.connections.Connection, 'commit', fail)
    else:
        original = admin_items.lock_admin_session
        def revoke(cursor):
            cursor.execute('UPDATE admin_session SET revoked_at=UTC_TIMESTAMP()')
            original(cursor)
        monkeypatch.setattr(admin_items, 'lock_admin_session', revoke)
    response = client.patch(f'/api/admin/items/{item["id"]}', json={'sku_code': '新款式', 'profile': {'name': '新名称'}}, headers=headers)
    monkeypatch.undo()
    assert response.status_code == (401 if failure == 'permission' else 503)
    assert query(auth_app, 'SELECT * FROM item') == before
    assert not query(auth_app, 'SELECT * FROM fashion_item_profile')
    assert not query(auth_app, "SELECT * FROM admin_audit WHERE action='item.details.update'")


@pytest.mark.parametrize('payload', [{}, {'sku_code': False}, {'sku_code': 1}, {'sku_code': 'x' * 65},
    {'profile': None}, {'profile': []}, {'profile': {}}, {'profile': {'name': 'x', 'size_chart': {}}},
    {'status': 'active', 'sku_code': 'x'}, {'status': 'disabled', 'profile': {'name': 'x'}},
    {'item_uid': 'FASH-2026-999999'}, {'project': 'jewelry'}, {'linked_chip': None}])
def test_ordinary_save_rejects_invalid_or_readonly_input(auth_app, drafts, payload):
    client, headers = drafts
    item = create(drafts).json['data']
    assert client.patch(f'/api/admin/items/{item["id"]}', json=payload, headers=headers).status_code == 400
    assert not query(auth_app, "SELECT * FROM admin_audit WHERE action='item.details.update'")


def test_new_save_permissions_size_and_archived(auth_app, drafts):
    client, headers = drafts
    item = create(drafts).json['data']; path = f'/api/admin/items/{item["id"]}'
    assert client.patch(path, json={'sku_code': 'x'}, headers=ORIGIN).status_code == 403
    assert auth_app.test_client().patch(path, json={'sku_code': 'x'}, headers=ORIGIN).status_code == 401
    assert client.patch(path + '?extra=1', json={'sku_code': 'x'}, headers=headers).status_code == 400
    # 资料分支可超过旧8KiB限制；启停及创建仍保留各自限制。
    large = {'name': '😀' * 128, 'description': '中' * 4000, 'image_urls': ['https://example.com/' + 'x' * 1900] * 20}
    assert client.patch(path, json={'sku_code': None, 'profile': large}, headers=headers).status_code == 200
    assert client.patch(path, data=' ' * 9000 + '{"status":"active"}', content_type='application/json', headers=headers).status_code == 400
    assert client.patch(path, data='x' * (256 * 1024 + 1), content_type='application/json', headers=headers).status_code == 400
    query(auth_app, "UPDATE item SET status='archived' WHERE id=%s", (item['id'],))
    assert client.patch(path, json={'sku_code': None}, headers=headers).status_code == 409


def test_name_chip_keyword_ranges_and_candidate_conflict(auth_app, drafts):
    client, headers = drafts
    items = []
    for n, project in ((1,'fashion'), (2,'jewelry')):
        item = create(drafts, project=project, item_uid=('FASH' if n == 1 else 'JEW') + f'-2026-93000{n}', sku_code='款式!_%').json['data']
        query(auth_app, f'INSERT INTO {project}_item_profile(item_id,name) VALUES (%s,%s)', (item['id'], '同名!_%资料'))
        query(auth_app, "UPDATE item SET created_at='2026-11-02 16:00:00',updated_at='2026-11-03 15:59:59' WHERE id=%s", (item['id'],))
        query(auth_app, "INSERT INTO chip(chip_uid,project_id,item_id,chip_status,provisioned_at) VALUES (%s,%s,%s,'lost','2026-11-03 00:00:00')", (f'04:11:22:33:44:55:0{n}', n, item['id']))
        items.append(item)
    create(drafts, item_uid='FASH-2026-930003')
    result = client.get('/api/admin/items', query_string={'keyword': '同名!_%', 'has_chip': 'true', 'created_from': '2026-11-03', 'created_to': '2026-11-03', 'updated_to': '2026-11-03', 'page_size': 1, 'page': 2}).json['data']
    assert result['total'] == 2 and result['page'] == 2 and len(result['items']) == 1
    summary = result['items'][0]
    assert summary['keyword_matches'] == ['name'] and summary['id'] == items[0]['id']
    chip = summary['linked_chip']
    assert set(chip) == {'id','chip_uid','chip_status','keys_generated','provisioned_at'}
    assert chip['chip_status'] == 'lost' and chip['keys_generated'] is False and chip['provisioned_at'].endswith('Z')
    assert client.get(f'/api/admin/items/{summary["id"]}').json['data']['linked_chip'] == chip
    for keyword, field in (('04:11:22:33:44:55:01','chip_uid'), ('04112233445501','chip_uid'), ('930001','item_uid'), ('款式!_%','sku_code')):
        found = client.get('/api/admin/items', query_string={'keyword': keyword}).json['data']
        assert found['total'] == (2 if field == 'sku_code' else 1) and field in found['items'][0]['keyword_matches']
    assert client.get('/api/admin/items?has_chip=false').json['data']['total'] == 1
    assert client.get('/api/admin/items?unbound_only=true&has_chip=true').status_code == 400
    assert client.get('/api/admin/items?unbound_only=false&has_chip=true').json['data']['total'] == 2
    for parameter in ({'has_chip': '1'}, {'created_to': '2026-02-30'}, {'created_from': '2026-11-04', 'created_to': '2026-11-03'}, [('has_chip','true'),('has_chip','false')]):
        assert client.get('/api/admin/items', query_string=parameter).status_code == 400
