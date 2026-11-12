"""正式工作台按真实事件切换统计、键盘图表和失败恢复；不注入浏览器会话。"""
from datetime import datetime,timedelta
import pytest
from tests.test_admin_browser import browser_gate,desktop,button,expect
from tests.admin_ui_helpers import setup,api,install,choose
from tests.test_admin_auth import query
pytestmark=[pytest.mark.auth_database,pytest.mark.browser]


def test_real_scope_switch_and_failure_not_zero(desktop,tmp_path):
    style,_,item,chips=setup(desktop);p=desktop.page
    install(desktop,style,item,chips[0])
    api(desktop,'sale',{'item_id':item,'confirmed':True,'evidence':'售出事实'})
    uid=query(desktop.app,'SELECT chip_uid FROM chip WHERE id=%s',(chips[0],))[0]['chip_uid']
    for n,days in enumerate((-1,1,2),3):query(desktop.app,"INSERT INTO scan_log(chip_id,item_id,chip_uid,project_id,scan_counter,verify_result,created_at) VALUES (%s,%s,%s,1,%s,'pass',%s)",(chips[0],item,uid,n,desktop.app.test_clock[0]+timedelta(days=days)))
    desktop.navigate('工作台')
    choose(p,'时间范围','累计');button(p,'应用筛选')
    total=p.locator('.ant-statistic').filter(has=p.get_by_text('有效触碰次数',exact=True)).locator('.ant-statistic-content-value')
    expect(total).to_have_text('2')
    choose(p,'统计口径','全生命周期有效触碰');button(p,'应用筛选')
    expect(total).to_have_text('3')
    chart=p.get_by_role('img',name='按北京时间汇总的有效触碰日趋势',exact=True)
    expect(chart).to_be_visible()
    last_asof=p.locator('.data-asof').inner_text()
    path='**/api/admin/catalog/statistics?*'
    p.route(path,lambda route:route.fulfill(status=503,json={'status':'error','code':'service_unavailable','message':'合成统计不可用'}))
    button(p,'应用筛选')
    # 更新失败明确显示错误，保留上次成功结果与截至时间，不能伪造零。
    expect(p.get_by_text('合成统计不可用',exact=True)).to_be_visible()
    expect(total).to_have_text('3')
    expect(p.get_by_text('上次成功结果',exact=True)).to_be_visible()
    expect(p.locator('.data-asof')).to_have_text(last_asof)
    # 初次加载失败没有可沿用数据，显示缺失而不是零；错误入口可以明确重试。
    p.reload(wait_until='networkidle')
    expect(p.get_by_text('合成统计不可用',exact=True)).to_be_visible()
    expect(total).to_have_text('—')
    expect(p.get_by_text('上次成功结果',exact=True)).to_have_count(0)
    p.unroute(path);button(p,'重试')
    expect(total).to_have_text('3')
    expect(p.get_by_text('合成统计不可用',exact=True)).to_have_count(0)
    expect(p.get_by_text('上次成功结果',exact=True)).to_have_count(0)
    p.screenshot(animations='disabled',path=str(tmp_path/'statistics-1280.png'))
