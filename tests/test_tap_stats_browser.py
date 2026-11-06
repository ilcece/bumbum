"""正式工作台按真实事件切换统计、键盘图表和失败恢复；不注入浏览器会话。"""
from datetime import datetime,timedelta
import pytest
from tests.test_admin_browser import browser_gate,desktop,button,expect
from tests.admin_ui_helpers import setup,api
from tests.test_admin_auth import query
pytestmark=[pytest.mark.auth_database,pytest.mark.browser]


def test_real_scope_switch_and_failure_not_zero(desktop,tmp_path):
    _,_,item,chips=setup(desktop);p=desktop.page
    api(desktop,'bind',{'item_id':item,'chip_id':chips[0],'spec':'L黑'})
    api(desktop,'sale',{'item_id':item,'confirmed':True,'evidence':'售出事实'})
    uid=query(desktop.app,'SELECT chip_uid FROM chip WHERE id=%s',(chips[0],))[0]['chip_uid']
    for n,days in enumerate((-1,1,2),3):query(desktop.app,"INSERT INTO scan_log(chip_id,item_id,chip_uid,project_id,scan_counter,verify_result,created_at) VALUES (%s,%s,%s,1,%s,'pass',%s)",(chips[0],item,uid,n,desktop.app.test_clock[0]+timedelta(days=days)))
    desktop.navigate('工作台');p.get_by_role('combobox').nth(1).click();p.locator('.ant-select-dropdown:visible .ant-select-item-option').filter(has_text='全部时间').click()
    expect(p.locator('.ant-statistic-content').first).to_contain_text('2')
    p.get_by_role('combobox').first.click();p.locator('.ant-select-dropdown:visible .ant-select-item-option').filter(has_text='生命周期全部有效触碰').click();expect(p.locator('.ant-statistic-content').first).to_contain_text('3')
    chart=p.get_by_role('region',name='每日触碰趋势');expect(chart).to_be_visible()
    path='**/api/admin/catalog/statistics?*';p.route(path,lambda route:route.fulfill(status=503,json={'status':'error','code':'service_unavailable','message':'合成统计不可用'}));button(p,'刷新数据')
    expect(p.get_by_text('合成统计不可用',exact=True)).to_be_visible();expect(p.locator('.ant-statistic-content').first).to_contain_text('—')
    p.unroute(path);button(p,'刷新数据');expect(p.locator('.ant-statistic-content').first).to_contain_text('3')
    p.screenshot(animations='disabled',path=str(tmp_path/'statistics-1280.png'))
