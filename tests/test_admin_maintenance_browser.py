"""Ant Design芯片完整流程，使用合成账号、真实API和临时MySQL。"""

import json
import re

import pytest

from tests.test_admin_auth import query
from tests.test_admin_browser import browser_gate, desktop

pytestmark = [pytest.mark.auth_database, pytest.mark.browser]


def sample(desktop):
    query(desktop.app, "INSERT INTO item(project_id,item_uid,sku_code) VALUES (1,'FASH-2026-910001','款式一')")
    item = query(desktop.app, "SELECT id FROM item WHERE item_uid='FASH-2026-910001'")[0]['id']
    query(desktop.app, "INSERT INTO fashion_item_profile(item_id,name,description,material,size_chart) VALUES (%s,'浏览器关联名称','既有介绍','棉',JSON_OBJECT('S', 80))", (item,))
    query(desktop.app, "INSERT INTO chip(chip_uid,project_id,item_id,chip_status,batch_no,registration_source) VALUES ('04:00:00:00:00:00:51',1,%s,'bound','原批次','manual')", (item,))
    chip = query(desktop.app, "SELECT id FROM chip")[0]['id']
    return chip, item


def open_record(desktop):
    desktop.login()
    desktop.navigate('芯片管理')
    desktop.page.get_by_role('button', name='查看详情', exact=True).click()
    desktop.page.get_by_role('heading', name='芯片详情', exact=True).wait_for()


def test_chip_query_relation_equal_fields_edit_return(desktop):
    from playwright.sync_api import expect
    chip, item = sample(desktop)
    desktop.login(); desktop.navigate('芯片管理')
    page = desktop.page
    page.get_by_label('关键词', exact=True).fill('浏览器关联名称')
    page.get_by_role('button', name=re.compile(r'查\s*询$')).click()
    expect(page).to_have_url(re.compile('keyword='))
    page.get_by_text('浏览器关联名称',exact=True).wait_for()
    expect(page.get_by_text('命中：关联物品名称',exact=True)).to_be_visible()
    original = page.url
    page.get_by_role('button', name='查看详情', exact=True).click()
    expect(page).to_have_url(re.compile(f'/chips/{chip}$'))
    page.get_by_role('link', name='FASH-2026-910001', exact=True).wait_for()
    labels = page.locator('.ant-descriptions-item-label').all_text_contents()
    page.get_by_role('link', name='FASH-2026-910001', exact=True).click()
    expect(page).to_have_url(re.compile(f'/items/{item}$'))
    page.get_by_text('既有介绍', exact=True).wait_for()
    page.get_by_role('button', name='返回来源', exact=True).click()
    page.get_by_role('button', name='编辑批次', exact=True).click()
    page.get_by_label('批次', exact=True).wait_for()
    for label in labels:
        expect(page.locator('.ant-form-item-label').filter(has_text=re.compile("^" + re.escape(label) + "$"))).to_have_count(1)
    expect(page.get_by_role('textbox')).to_have_count(1)
    page.get_by_label('批次', exact=True).fill('新批次')
    page.get_by_role('button', name='保存批次', exact=True).click()
    expect(page).to_have_url(re.compile(f'/chips/{chip}$'))
    page.get_by_role('dialog',name=re.compile('芯片详情')).get_by_text('新批次',exact=True).wait_for()
    page.get_by_role('button', name='返回来源', exact=True).click()
    expect(page).to_have_url(original)
    expect(page.get_by_label('关键词', exact=True)).to_have_value('浏览器关联名称')
    page.get_by_role('cell', name='新批次', exact=True).wait_for()
    page.reload(wait_until='networkidle')
    expect(page.get_by_label('关键词', exact=True)).to_have_value('浏览器关联名称')
    page.get_by_role('button', name=re.compile(r'重\s*置$')).click()
    expect(page.get_by_label('关键词', exact=True)).to_have_value('')


def test_unsaved_cancel_save_discard_and_history(desktop):
    from playwright.sync_api import expect
    chip, _ = sample(desktop)
    open_record(desktop)
    page = desktop.page
    page.get_by_role('button', name='编辑批次', exact=True).click()
    page.get_by_label('批次', exact=True).fill('离开前保存')
    desktop.navigate('物品管理')
    popup = page.get_by_role('dialog', name='有未保存修改', exact=True)
    popup.get_by_role('button', name=re.compile(r'^取\s*消$')).click()
    expect(page.get_by_label('批次', exact=True)).to_have_value('离开前保存')
    desktop.navigate('物品管理')
    popup.get_by_role('button', name='保存后继续', exact=True).click()
    expect(page).to_have_url(re.compile('/items$'))
    assert query(desktop.app, 'SELECT batch_no FROM chip WHERE id=%s', (chip,))[0]['batch_no'] == '离开前保存'
    desktop.navigate('芯片管理')
    page.get_by_role('button', name='查看详情', exact=True).click()
    page.get_by_role('button', name='编辑批次', exact=True).click()
    page.get_by_label('批次', exact=True).fill('丢弃输入')
    page.go_back(wait_until='domcontentloaded')
    popup.get_by_role('button', name='放弃继续', exact=True).click()
    expect(page).to_have_url(re.compile(f'/chips/{chip}$'))
    assert query(desktop.app, 'SELECT batch_no FROM chip WHERE id=%s', (chip,))[0]['batch_no'] == '离开前保存'


def test_batch_lost_response_requires_read_before_retry(desktop):
    from playwright.sync_api import expect
    chip, _ = sample(desktop)
    open_record(desktop)
    page = desktop.page
    page.get_by_role('button', name='编辑批次', exact=True).click()
    writes = []
    def lose_response(route):
        if route.request.method != 'PATCH':
            route.continue_(); return
        writes.append(1)
        response = route.fetch()
        assert response.status == 200
        route.fulfill(status=503, content_type='application/json', body=json.dumps({'status': 'error', 'code': 'service_unavailable', 'message': '合成回执丢失'}))
    page.route(f'**/api/admin/chips/{chip}', lose_response)
    page.get_by_label('批次', exact=True).fill('已提交回执丢失')
    page.get_by_role('button', name='保存批次', exact=True).click()
    page.get_by_text('保存结果尚未确认，请先按记录ID核对；不会自动重发。', exact=True).wait_for()
    expect(page.get_by_role('button', name='保存批次', exact=True)).to_be_disabled()
    page.get_by_role('button', name='核对保存结果', exact=True).click()
    page.get_by_text('已确认服务器当前批次与本次提交一致。', exact=True).wait_for()
    assert writes == [1]
    expect(page.get_by_label('批次', exact=True)).to_have_value('已提交回执丢失')
    page.get_by_role('button', name='返回来源', exact=True).click()
    expect(page).to_have_url(re.compile('/chips$'))


def test_advanced_dates_pagination_and_clear(desktop):
    from playwright.sync_api import expect
    for number in range(25):
        query(desktop.app, "INSERT INTO chip(chip_uid,batch_no,created_at) VALUES (%s,'范围批次','2026-11-02 16:00:00')", (f'04:11:22:33:44:55:{number:02X}',))
    query(desktop.app,"INSERT INTO chip(chip_uid,batch_no,created_at) VALUES ('04:EE:EE:EE:EE:EE:01','不匹配批次','2026-10-01 00:00:00')")
    desktop.login(); desktop.navigate('芯片管理')
    page = desktop.page
    page.get_by_text('展开', exact=True).click()
    page.get_by_label('批次', exact=True).fill('范围批次')
    dates = page.locator('.ant-form-item').filter(has_text='登记日期（北京时间）').locator('.ant-picker-range input')
    dates.nth(0).fill('2026-11-03')
    dates.nth(0).press('Tab')
    dates.nth(1).fill('2026-11-03')
    dates.nth(1).press('Enter')
    page.get_by_role('button', name=re.compile(r'查\s*询$')).click()
    expect(page).to_have_url(re.compile('created_from=2026-11-03'))
    expect(page.locator('.ant-table-tbody .ant-table-row')).to_have_count(20)
    page.locator('.ant-pagination-next button').click()
    expect(page).to_have_url(re.compile('page=2'))
    expect(page.locator('.ant-table-tbody .ant-table-row')).to_have_count(5)
    original = page.url
    page.get_by_role('button', name='查看详情', exact=True).first.click()
    page.get_by_role('button', name='返回来源', exact=True).click()
    expect(page).to_have_url(original)
    expect(page.locator('.ant-table-tbody .ant-table-row')).to_have_count(5)
    page.get_by_text('展开', exact=True).click()
    expect(dates.nth(0)).to_have_value('2026-11-03')
    picker = page.locator('.ant-picker-range').first
    picker.hover()
    picker.locator('.ant-picker-clear').click()
    page.get_by_role('button', name=re.compile(r'查\s*询$')).click()
    expect(page).not_to_have_url(re.compile('created_from='))
    expect(page).to_have_url(re.compile('page=1'))
    expect(page.get_by_label('批次', exact=True)).to_have_value('范围批次')


@pytest.mark.parametrize('kind',['chips','items'])
def test_collapsed_query_retains_url_dates_and_advanced_conditions(desktop,kind):
    from playwright.sync_api import expect
    if kind=='chips':
        for suffix,batch,created in [(1,'保留批次','2026-11-02 16:00:00'),(2,'其他批次','2026-11-02 16:00:00'),(3,'保留批次','2026-10-01 00:00:00')]:
            query(desktop.app,'INSERT INTO chip(chip_uid,batch_no,created_at) VALUES (%s,%s,%s)',(f'04:AA:BB:CC:DD:EE:{suffix:02X}',batch,created))
        advanced='batch_no=%E4%BF%9D%E7%95%99%E6%89%B9%E6%AC%A1'
    else:
        for suffix,created in [(1,'2026-11-02 16:00:00'),(2,'2026-11-02 16:00:00'),(3,'2026-10-01 00:00:00')]:
            query(desktop.app,'INSERT INTO item(project_id,item_uid,created_at) VALUES (1,%s,%s)',(f'FASH-2026-{930000+suffix:06d}',created))
        item=query(desktop.app,"SELECT id FROM item WHERE item_uid='FASH-2026-930002'")[0]['id']
        query(desktop.app,"INSERT INTO chip(chip_uid,project_id,item_id,chip_status) VALUES ('04:AA:BB:CC:DD:EE:02',1,%s,'bound')",(item,))
        advanced='has_chip=false'
    desktop.login();page=desktop.page
    page.goto(f'http://localhost:5174/{kind}?page=1&page_size=20&{advanced}&created_from=2026-11-03&created_to=2026-11-03',wait_until='networkidle')
    rows=page.locator('.ant-table-tbody .ant-table-row')
    expect(rows).to_have_count(1)
    expect(page.get_by_role('button',name='展开',exact=True)).to_be_visible()
    page.get_by_role('button',name=re.compile(r'查\s*询$')).click()
    expect(page).to_have_url(re.compile('created_from=2026-11-03'))
    expect(page).to_have_url(re.compile(advanced))
    expect(rows).to_have_count(1)
