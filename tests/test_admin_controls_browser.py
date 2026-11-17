"""在真实隔离接口上核对筛选、导航与退出；截图仅使用合成数据。"""
from datetime import timedelta
from pathlib import Path
import re

import pytest

from tests.admin_ui_helpers import api, choose, setup
from tests.test_admin_auth import query
from tests.test_admin_browser import browser_gate, button, desktop, expect

pytestmark = [pytest.mark.auth_database, pytest.mark.browser]


def capture(page, name):
    folder = Path('test-results/admin-controls')
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / name), animations='disabled')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')


def test_filters_preserve_current_facts_and_drilldown(desktop):
    _, _, item, chips = setup(desktop)
    p = desktop.page
    now = query(desktop.app, 'SELECT UTC_TIMESTAMP(6) AS now_utc')[0]['now_utc']
    query(desktop.app, 'UPDATE digital_item SET sold=1,first_sold_at=%s WHERE item_id=%s',
          (now - timedelta(days=10), item))
    uid = query(desktop.app, 'SELECT chip_uid FROM chip WHERE id=%s', (chips[0],))[0]['chip_uid']
    for counter, days in enumerate((15, 8, 1), 1):
        query(desktop.app, "INSERT INTO scan_log(chip_id,item_id,chip_uid,project_id,scan_counter,verify_result,created_at) VALUES (%s,%s,%s,1,%s,'pass',%s)",
              (chips[0], item, uid, counter, now - timedelta(days=days)))
    p.goto('http://localhost:5174/overview', wait_until='networkidle')
    metric = p.locator('.metric-card').filter(has=p.get_by_text('有效触碰次数', exact=True))
    sold = p.locator('.metric-card').filter(has=p.get_by_text('已确认售出物品', exact=True))
    expect(metric.locator('.ant-statistic-content')).to_have_text('1次')
    expect(sold.locator('.ant-statistic-content')).to_have_text('1件')
    choose(p, '时间范围', '近30日')
    expect(metric.locator('.ant-statistic-content')).to_have_text('1次')
    button(p, '应用筛选')
    expect(metric.locator('.ant-statistic-content')).to_have_text('2次')
    expect(sold.locator('.ant-statistic-content')).to_have_text('1件')
    choose(p, '触碰情况', '重复触碰')
    expect(p).to_have_url(re.compile('detail_filter=repeat'))
    expect(p.locator('#overview-details .ant-table-tbody .ant-table-row')).to_have_count(1)
    p.get_by_label('触碰情况', exact=True).press('Home')
    p.get_by_label('触碰情况', exact=True).press('ArrowDown')
    p.get_by_label('触碰情况', exact=True).press('Escape')
    expect(p.locator('.ant-select-dropdown:visible')).to_have_count(0)
    for width in (1920, 1280):
        p.set_viewport_size({'width': width, 'height': 1080 if width == 1920 else 720})
        p.get_by_text('售出与持有', exact=True).scroll_into_view_if_needed()
        capture(p, f'overview-{width}.png')
    p.goto(f'http://localhost:5174/items/{item}', wait_until='networkidle')
    stats = p.locator('.ant-pro-card').filter(has=p.get_by_text('物品触碰统计', exact=True)).last
    expect(stats.get_by_role('button', name='查看 2 次有效触碰明细')).to_be_visible()
    choose(stats, '时间范围', '近7日')
    expect(stats.get_by_role('button', name='查看 1 次有效触碰明细')).to_be_visible()
    choose(stats, '统计口径', '全生命周期有效触碰')
    choose(stats, '时间范围', '累计')
    expect(stats.get_by_role('button', name='查看 3 次有效触碰明细')).to_be_visible()
    for width in (1920, 1280):
        p.set_viewport_size({'width': width, 'height': 1080 if width == 1920 else 720})
        stats.scroll_into_view_if_needed()
        capture(p, f'item-{width}.png')
    stats.get_by_role('button', name='查看 3 次有效触碰明细').click()
    expect(p).to_have_url(re.compile('scope=all.*range=all'))
    expect(p.locator('.ant-table-tbody .ant-table-row')).to_have_count(3)


def test_menu_order_navigation_and_logout_recovery(desktop):
    desktop.login()
    p = desktop.page
    menu = p.locator('aside')
    parent = menu.get_by_role('menuitem', name=re.compile('数字物品管理$'))
    parent.click()
    physical = menu.get_by_role('link', name='实体物品', exact=True)
    expect(physical).to_be_visible()
    physical.click()
    expect(physical.locator('xpath=ancestor::li[1]')).to_have_class(re.compile('ant-menu-item-selected'))
    menu.get_by_role('link', name=re.compile('数字物品$')).click()
    p.reload(wait_until='networkidle')
    expect(menu.get_by_role('link', name=re.compile('数字物品$'))).to_be_visible()
    collapse = p.locator('.ant-pro-sider-collapsed-button')
    collapse.click()
    expect(menu).to_have_class(re.compile('ant-layout-sider-collapsed'))
    collapse.click()
    expect(menu.get_by_role('link', name=re.compile('工作台$'))).to_be_visible()
    order = api(desktop, 'createOrder', {'channel': '隔离验收', 'external_order_no': 'CONTROL-NAV',
                                       'units': [{'product_name': 'A'}, {'product_name': 'B'}]})
    p.goto(f'http://localhost:5174/orders/{order["id"]}?from=%2Forders', wait_until='networkidle')
    nav = p.get_by_role('navigation', name='定位订单件')
    nav.get_by_role('link').nth(1).press('Enter')
    expect(nav.locator('[aria-current="location"]')).to_contain_text('第 2 件')
    expect(p.locator('section[id^="order-unit-"]').nth(1)).to_be_focused()
    expect(p.locator('section[id^="order-unit-"]')).to_have_count(2)
    current = p.url
    p.reload(wait_until='networkidle')
    expect(nav.locator('[aria-current="location"]')).to_contain_text('第 2 件')
    assert p.url == current
    for width in (1920, 1280):
        p.set_viewport_size({'width': width, 'height': 1080 if width == 1920 else 720})
        nav.scroll_into_view_if_needed()
        capture(p, f'orders-{width}.png')
    p.get_by_role('button', name='back', exact=True).click()
    expect(p).to_have_url(re.compile('/orders$'))
    expect(p.get_by_text('验收测试数据：关闭', exact=True)).to_be_visible()
    p.locator('.sider-caption').focus()
    expect(p.get_by_role('tooltip')).to_contain_text('与 test／生产环境无关')
    expect(p.get_by_text('管理会话', exact=True)).to_have_count(0)
    path = '**/api/admin/auth/logout'
    p.route(path, lambda route: route.fulfill(status=503, json={
        'status': 'error', 'code': 'service_unavailable', 'message': '合成退出失败'}))
    button(p, '退出登录')
    expect(p.get_by_text('合成退出失败', exact=False)).to_be_visible()
    expect(p.get_by_role('button', name='退出登录', exact=True)).to_be_visible()
    p.unroute(path)
    button(p, '退出登录')
    expect(p.get_by_role('heading', name='管理员登录')).to_be_visible()
