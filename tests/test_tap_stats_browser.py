"""桌面统计浏览器回归只使用专属临时库和明确的故障注入。"""

from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from core import tap_statistics as service
from core.db import get_database
from tests.test_admin_auth import query
from tests.test_admin_browser import browser_gate, desktop

pytestmark = [pytest.mark.auth_database, pytest.mark.browser]
NOW = datetime(2026,10,27,4)


def expect(locator):
    """只有实际启用浏览器时才加载可选依赖，基础CI也能收集测试。"""
    from playwright.sync_api import expect as browser_expect
    return browser_expect(locator)


@pytest.fixture(autouse=True)
def cutoff(monkeypatch):
    monkeypatch.setattr(service,'snapshot_time',lambda cursor: NOW)


def seed(app, number=1, project='fashion', taps=1, name=None, at=NOW):
    prefix = 'FASH' if project == 'fashion' else 'JEW'
    uid = f'{prefix}-2026-{number:06d}'
    with app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM project WHERE code=%s',(project,))
            project_id = cursor.fetchone()[0]
            cursor.execute('INSERT INTO item(project_id,item_uid,status) VALUES (%s,%s,\'active\')',(project_id,uid))
            target = cursor.lastrowid
            table = 'fashion_item_profile' if project == 'fashion' else 'jewelry_item_profile'
            if name is not None: cursor.execute(f'INSERT INTO {table}(item_id,name) VALUES (%s,%s)',(target,name))
            cursor.execute("INSERT INTO chip(chip_uid,project_id,item_id,chip_status) VALUES (%s,%s,%s,'bound')",(f'04:{number:02X}:11:22:33:44:55',project_id,target))
            source = cursor.lastrowid
            cursor.executemany("INSERT INTO scan_log(chip_id,item_id,project_id,chip_uid,scan_counter,verify_result,created_at) VALUES (%s,%s,%s,%s,%s,'pass',%s)",
                               [(source,target,project_id,f'04:{number:02X}:11:22:33:44:55',counter,at) for counter in range(1,taps+1)])
        connection.commit()
    return target,source


def panel(desktop):
    return desktop.page.get_by_role('region',name='有效触碰统计',exact=True)


def test_real_default_filters_keyword_scope_pagination_and_clear(desktop):
    for number in range(1,23): seed(desktop.app,number,name=f'外套{number}')
    seed(desktop.app,23,project='jewelry',taps=2,name='平安扣')
    desktop.login()
    area = panel(desktop)
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('24')
    expect(area.get_by_label('被触碰物品数',exact=True)).to_have_text('23')
    expect(area.get_by_role('row')).to_have_count(21)
    area.get_by_role('button',name='下一页',exact=True).click()
    expect(area.get_by_text('共23件／第2页，共2页',exact=True)).to_be_visible()
    expect(area.get_by_role('row')).to_have_count(4)
    area.get_by_label('统计项目',exact=True).select_option('jewelry')
    expect(area.get_by_text('筛选条件已修改，点击查询统计生效。',exact=True)).to_be_visible()
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('24')
    area.get_by_role('button',name='查询统计',exact=True).click()
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('2')
    expect(area.get_by_text('共1件／第1页，共1页',exact=True)).to_be_visible()
    area.get_by_label('物品编号或名称',exact=True).fill('不存在')
    expect(area.get_by_text('明细关键词已修改，尚未查询。',exact=True)).to_be_visible()
    area.get_by_label('物品编号或名称',exact=True).press('Enter')
    expect(area.get_by_text('没有匹配的物品',exact=True)).to_be_visible()
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('2')
    area.get_by_role('button',name='清空',exact=True).click()
    expect(area.get_by_role('cell',name='平安扣',exact=True)).to_be_visible()
    # 库存始终是全局，不跟着饰品筛选缩小。
    expect(desktop.page.locator('.overview-inventory .metric-card').nth(2).locator('strong')).to_have_text('23')
    expect(desktop.page.get_by_text('入库趋势',exact=True)).to_have_count(0)


def test_refresh_uses_applied_filters_and_retry_uses_failed_request(desktop):
    seed(desktop.app,1,name='外套')
    seed(desktop.app,2,project='jewelry',name='平安扣',taps=2)
    desktop.login()
    page,area = desktop.page,panel(desktop)
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('3')
    requests = []
    def watch(route):
        requests.append(parse_qs(urlsplit(route.request.url).query))
        route.continue_()
    page.route('**/api/admin/stats/taps?*',watch)
    area.get_by_label('统计项目',exact=True).select_option('jewelry')
    area.get_by_label('物品编号或名称',exact=True).fill('未查询关键词')
    area.get_by_role('button',name='刷新统计',exact=True).click()
    expect(area.get_by_role('button',name='刷新统计',exact=True)).to_be_enabled()
    assert 'project' not in requests[-1] and 'q' not in requests[-1]
    expect(area.get_by_label('统计项目',exact=True)).to_have_value('jewelry')
    expect(area.get_by_label('物品编号或名称',exact=True)).to_have_value('未查询关键词')
    page.unroute('**/api/admin/stats/taps?*')
    page.route('**/api/admin/stats/taps?*',lambda route: route.fulfill(status=503,json={'status':'error','code':'service_unavailable','message':'合成失败','error_id':'a'*24}))
    area.get_by_role('button',name='查询统计',exact=True).click()
    expect(area.get_by_role('alert')).to_contain_text('触碰统计读取失败')
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('3')
    expect(area.get_by_text('失败请求：饰品',exact=False)).to_be_visible()
    area.get_by_label('统计项目',exact=True).select_option('fashion')
    page.unroute('**/api/admin/stats/taps?*')
    page.route('**/api/admin/stats/taps?*',watch)
    area.get_by_role('button',name='重试',exact=True).click()
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('2')
    assert requests[-1]['project'] == ['jewelry'] and 'q' not in requests[-1]


@pytest.mark.parametrize('mode',['failure','missing','precision'])
def test_initial_failures_are_not_zero_or_partial_success(desktop, mode):
    page = desktop.page
    def response(route):
        if mode == 'failure':
            route.fulfill(status=503,json={'status':'error','code':'service_unavailable','message':'合成读取失败'})
        else:
            payload = route.fetch().json()
            if mode == 'missing': del payload['data']['summary']
            else:
                payload['data']['summary']['valid_taps'] = 9007199254740992
                payload['data']['daily'][-1]['valid_taps'] = 9007199254740992
            route.fulfill(status=200,json=payload)
    page.route('**/api/admin/stats/taps?*',response)
    desktop.login()
    area = panel(desktop)
    expect(area.get_by_role('alert')).to_contain_text('触碰统计读取失败')
    expect(area.locator('output')).to_have_count(0)
    expect(area.get_by_text('尚未获得有效统计结果，请查询或重试。',exact=True)).to_be_visible()
    page.unroute('**/api/admin/stats/taps?*')
    area.get_by_role('button',name='重试',exact=True).click()
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('0')
    expect(area.get_by_text('共0件',exact=True)).to_be_visible()


def test_chart_keyboard_tooltip_and_short_desktop_scroll(desktop, tmp_path):
    seed(desktop.app,name='长名称'+ '测'*100,taps=3)
    desktop.login()
    page,area = desktop.page,panel(desktop)
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('3')
    chart = area.get_by_role('group',name='每日有效触碰柱状图',exact=True)
    chart.focus()
    chart.press('End')
    expect(area.get_by_role('tooltip')).to_contain_text('3次（今日未结束）')
    chart.press('Home')
    expect(area.get_by_role('tooltip')).to_contain_text('0次')
    page.locator('.page').evaluate('(node)=>node.scrollTop=0')
    page.screenshot(path=str(tmp_path/'stats-workbench.png'))
    area.get_by_label('统计项目',exact=True).scroll_into_view_if_needed()
    page.screenshot(path=str(tmp_path/'stats-panel.png'))
    chart.evaluate('(node)=>node.scrollIntoView({block:"center"})')
    page.screenshot(path=str(tmp_path/'stats-chart.png'))
    page.set_viewport_size({'width':1280,'height':500})
    area.get_by_role('button',name='下一页',exact=True).scroll_into_view_if_needed()
    expect(area.get_by_role('button',name='下一页',exact=True)).to_be_visible()
    assert page.locator('body').evaluate('(node)=>getComputedStyle(node).overflow') == 'hidden'
    assert page.locator('.page').evaluate('(node)=>node.scrollHeight>node.clientHeight')


def test_late_response_cannot_replace_new_page_result(desktop):
    target,source = seed(desktop.app,name='外套')
    pending = []
    def hold_first(route):
        payload = route.fetch().json()
        if not pending: pending.append((route,payload))
        else: route.fulfill(status=200,json=payload)
    page = desktop.page
    page.route('**/api/admin/stats/taps?*',hold_first)
    desktop.login()
    expect(panel(desktop).get_by_role('button',name='查询统计',exact=True)).to_be_disabled()
    desktop.navigate('芯片管理')
    query(desktop.app,"INSERT INTO scan_log(chip_id,item_id,project_id,chip_uid,scan_counter,verify_result,created_at) SELECT id,item_id,project_id,chip_uid,2,'pass',%s FROM chip WHERE id=%s",(NOW,source))
    desktop.navigate('工作台')
    expect(panel(desktop).get_by_label('有效触碰次数',exact=True)).to_have_text('2')
    pending[0][0].fulfill(status=200,json=pending[0][1])
    page.wait_for_timeout(100)
    expect(panel(desktop).get_by_label('有效触碰次数',exact=True)).to_have_text('2')


def test_expired_session_clears_whole_dashboard(desktop):
    desktop.login()
    area = panel(desktop)
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('0')
    query(desktop.app,'UPDATE admin_session SET revoked_at=%s',(desktop.app.test_clock[0],))
    area.get_by_role('button',name='刷新统计',exact=True).click()
    expect(desktop.page.get_by_role('button',name='登录',exact=True)).to_be_visible()
    expect(desktop.page.locator('.admin-shell')).to_have_count(0)


def test_microsecond_timestamp_and_unicode_keyword_boundary(desktop):
    requests = []
    def response(route):
        requests.append(parse_qs(urlsplit(route.request.url).query))
        payload = route.fetch().json()
        payload['data']['as_of'] = '2026-10-27T04:00:00.123456Z'
        route.fulfill(status=200,json=payload)
    desktop.page.route('**/api/admin/stats/taps?*',response)
    desktop.login()
    area = panel(desktop)
    expect(area.get_by_label('有效触碰次数',exact=True)).to_have_text('0')
    initial = len(requests)
    area.get_by_label('物品编号或名称',exact=True).fill('😀'*129)
    area.get_by_role('button',name='查询物品',exact=True).click()
    expect(area.get_by_role('alert')).to_contain_text('关键词最多128个字符')
    assert len(requests) == initial
    area.get_by_label('物品编号或名称',exact=True).fill('😀'*128)
    area.get_by_role('button',name='查询物品',exact=True).click()
    expect(area.get_by_text('没有匹配的物品',exact=True)).to_be_visible()
    assert requests[-1]['q'] == ['😀'*128]
