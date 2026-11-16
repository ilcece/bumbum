"""隔离 MySQL 中补核装配保护、配置前纠错和北京时间跨年计次。"""

from datetime import datetime

import pytest

from core import admin_catalog
from tests.test_admin_auth import query
from tests.test_admin_catalog import action, assembly, catalog, config_chip, ok, owner
from tests.test_admin_chips import logged_in


pytestmark = pytest.mark.auth_database


def test_assembly_conflicts_unverified_activation_and_preconfiguration_undo(auth_app, catalog):
    session, style, issue, item, chips = catalog
    entity = ok(action(session, 'createPhysicalItem', {
        'style_id': style, 'physical_uid': 'PHY-ACCEPTANCE-UNIQUE', 'spec': 'L黑',
    }))
    duplicate = action(session, 'createPhysicalItem', {
        'style_id': style, 'physical_uid': 'PHY-ACCEPTANCE-UNIQUE', 'spec': '不可覆盖原规格',
    })
    assert duplicate.status_code == 409
    assert query(auth_app, 'SELECT spec FROM physical_item WHERE id=%s', (entity['id'],)) == [{'spec': 'L黑'}]
    second = ok(action(session, 'item', {
        'issue_id': issue, 'item_uid': 'FASH-2026-000002', 'edition_number': 2,
    }))['id']
    payload = {'item_id': item, 'physical_item_id': entity['id'], 'chip_id': chips[0], 'installed': True}
    assert action(session, 'installAssembly', {**payload, 'installed': False}).status_code == 400
    assert not query(auth_app, 'SELECT id FROM whole_item WHERE item_id=%s', (item,))
    ok(action(session, 'installAssembly', payload))
    original = ok(session[0].get(f'/api/admin/catalog/items/{item}'))
    assert original['physical_uid'] == 'PHY-ACCEPTANCE-UNIQUE'
    assert original['status'] == 'draft'
    assert action(session, 'toggleItem', {'item_id': item, 'status': 'active'}).status_code == 409
    assert ok(session[0].get(f'/api/admin/catalog/items/{item}'))['status'] == 'draft'

    # 分别争用已安装的实体和芯片，拒绝后第二件仍未安装。
    assert action(session, 'installAssembly', {**payload, 'item_id': second, 'chip_id': chips[1]}).status_code == 409
    fresh = assembly(session, style, chips[0], '新实体')
    assert action(session, 'installAssembly', {'item_id': second, **fresh}).status_code == 409
    assert not query(auth_app, 'SELECT id FROM whole_item WHERE item_id=%s', (second,))
    assert query(auth_app, 'SELECT item_id,chip_status FROM chip WHERE id=%s', (chips[0],)) == [
        {'item_id': item, 'chip_status': 'bound'},
    ]

    ok(action(session, 'undoInstall', {
        'item_id': item, 'whole_id': original['whole_id'], 'evidence': '隔离测试核对误安装并拆离', 'confirmed': True,
    }))
    assert not query(auth_app, 'SELECT id FROM whole_item WHERE item_id=%s', (item,))
    assert query(auth_app, 'SELECT item_id,chip_status FROM chip WHERE id=%s', (chips[0],)) == [
        {'item_id': None, 'chip_status': 'pending'},
    ]
    events = ok(session[0].get('/api/admin/catalog/audit', query_string={'item_id': item}))['items']
    undone = next(event for event in events if event['action'] == 'catalog.undoInstall')
    assert undone['detail']['before']['physical_uid'] == 'PHY-ACCEPTANCE-UNIQUE'
    assert undone['detail']['before']['chip_uid'] == original['chip_uid']
    assert undone['detail']['after']['physical_uid'] is None
    assert undone['detail']['after']['chip_uid'] is None
    # 配置前纠错释放原组合；配置完成后不能再走普通纠错。
    ok(action(session, 'installAssembly', payload))
    config_chip(auth_app, session, chips[0])
    installed = ok(session[0].get(f'/api/admin/catalog/items/{item}'))
    assert action(session, 'undoInstall', {
        'item_id': item, 'whole_id': installed['whole_id'], 'evidence': '不得绕过配置后专用纠错', 'confirmed': True,
    }).status_code == 409
    ok(action(session, 'toggleItem', {'item_id': item, 'status': 'active'}))


@pytest.mark.parametrize('effective_at,expected_year', [
    (datetime(2029, 12, 31, 15, 59, 59), 2029),
    (datetime(2029, 12, 31, 16, 0, 0), 2030),
])
def test_renewal_counts_beijing_effective_year_and_resale_inherits_usage(auth_app, catalog, monkeypatch, effective_at, expected_year):
    session, style, _, item, chips = catalog
    # 只控制业务时钟，真实认证夹具时钟不跳年；所有对象均来自独立临时库。
    clock = [datetime(2029, 12, 31, 15, 59, 58)]
    monkeypatch.setattr(admin_catalog, 'now', lambda: clock[0])
    ok(action(session, 'installAssembly', {'item_id': item, **assembly(session, style, chips[0], '原实物')}))
    config_chip(auth_app, session, chips[0])
    first_owner = owner(auth_app, item, 81)
    recipient = owner(auth_app, None, 82)
    original = ok(session[0].get(f'/api/admin/catalog/items/{item}'))
    prepared = ok(action(session, 'prepare', {
        'item_id': item, 'kind': 'periodic', 'evidence': '北京旧年准备',
        **assembly(session, style, chips[1], '换新实物'),
    }))
    config_chip(auth_app, session, chips[1])
    clock[0] = effective_at
    completion = {'work_id': prepared['work_id'], 'checked': True, 'evidence': '以确认时刻生效'}
    ok(action(session, 'complete', completion))
    assert ok(action(session, 'complete', completion))['already_completed'] is True
    fact = query(auth_app, 'SELECT quota_year,completed_at FROM item_handover WHERE id=%s', (prepared['work_id'],))[0]
    assert fact == {'quota_year': expected_year, 'completed_at': effective_at}
    renewed = ok(session[0].get(f'/api/admin/catalog/items/{item}'))
    assert (renewed['quota_year'], renewed['quota_used'], renewed['owner_id']) == (expected_year, 1, first_owner)
    resale = ok(action(session, 'prepare', {
        'item_id': item, 'kind': 'resale', 'recipient_id': recipient, 'evidence': '核对转售',
        'seller_confirmation': '原持有人明确同意', 'recipient_confirmation': '接收人明确接受',
        **assembly(session, style, chips[2], '转售实物'),
    }))
    config_chip(auth_app, session, chips[2])
    ok(action(session, 'complete', {'work_id': resale['work_id'], 'checked': True, 'evidence': '转售交付已核对'}))
    transferred = ok(session[0].get(f'/api/admin/catalog/items/{item}'))
    assert (transferred['item_uid'], transferred['edition_number']) == (original['item_uid'], original['edition_number'])
    assert (transferred['quota_year'], transferred['quota_used'], transferred['owner_id']) == (expected_year, 1, recipient)
    assert transferred['physical_uid'] != renewed['physical_uid']
    candidate = assembly(session, style, chips[3], '应拒绝再次换新')
    assert action(session, 'prepare', {'item_id': item, 'kind': 'periodic', 'evidence': '同年不能重复使用', **candidate}).status_code == 409
    ok(action(session, 'loseItem', {'item_id': item, 'whole_id': transferred['whole_id'], 'evidence': '隔离测试挂失'}))
    assert action(session, 'prepare', {'item_id': item, 'kind': 'loss', 'evidence': '挂失与定期共享额度', **candidate}).status_code == 409
    assert query(auth_app, 'SELECT COUNT(*) AS n FROM item_handover WHERE item_id=%s AND quota_year=%s', (item, expected_year)) == [{'n': 1}]
