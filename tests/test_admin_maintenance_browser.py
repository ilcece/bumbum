"""正式Umi维护与恢复：服务端分页、原子保存、未知回执和生产验证清理。"""
import json
import re
import pytest
from tests.test_admin_browser import browser_gate,desktop,button,expect
from tests.admin_ui_helpers import setup,api
from tests.test_admin_auth import query
pytestmark=[pytest.mark.auth_database,pytest.mark.browser]


def test_server_pagination_query_drawer_and_validation_cleanup(desktop,tmp_path):
    _,issue,item,chips=setup(desktop);p=desktop.page
    for n in range(2,13):api(desktop,'item',{'issue_id':issue,'item_uid':f'FASH-2026-{880000+n:06d}','edition_number':n})
    desktop.navigate('数字物品');expect(p.locator('.ant-table-tbody tr.ant-table-row')).to_have_count(10)
    p.get_by_label('关键词',exact=True).fill('FASH-2026-880001');button(p,'查询');expect(p.locator('.ant-table-tbody tr.ant-table-row')).to_have_count(1)
    button(p,'查看');d=p.get_by_role('dialog',name='数字物品详情');expect(d).to_have_css('width','900px')
    expect(d.get_by_text('#01/50',exact=True)).to_have_count(1)
    d.get_by_role('switch',name='物品生产验证对象',exact=True).click();expect(d.get_by_role('switch',name='物品生产验证对象',exact=True)).to_be_checked();button(d,'直接删除物品');d.wait_for(state='hidden')
    assert not query(desktop.app,'SELECT id FROM item WHERE id=%s',(item,))
    assert len(query(desktop.app,'SELECT id FROM chip'))==3
    assert query(desktop.app,"SELECT id FROM admin_audit WHERE action='catalog.deleteItem'")
    p.screenshot(path=str(tmp_path/'validation-cleanup.png'))


def test_unknown_save_checks_receipt_without_duplicate_and_csrf_explicit_retry(desktop):
    _,_,item,_=setup(desktop);p=desktop.page;p.goto(f'http://localhost:5174/items/{item}',wait_until='networkidle')
    path='**/api/admin/catalog/actions/sale';writes=[]
    def lost(route):
        writes.append(1);response=route.fetch();assert response.status==200
        route.fulfill(status=503,json={'status':'error','code':'service_unavailable','message':'合成回执丢失'})
    p.route(path,lost);button(p,'维护售出事实');d=p.get_by_role('dialog',name='维护售出事实');d.get_by_label('销售确认或更正依据',exact=True).fill('外部实际售出')
    button(d,'保存售出确认');expect(d.get_by_text('保存结果未知，请先核对',exact=True)).to_be_visible();expect(d.get_by_role('button',name=re.compile('保存售出确认$'))).to_be_disabled();button(d,'核对已提交回执');d.wait_for(state='hidden')
    assert writes==[1] and len(query(desktop.app,"SELECT id FROM admin_audit WHERE action='catalog.sale'"))==1
    p.unroute(path,lost)
    blocked=[]
    def csrf(route):blocked.append(1);route.fulfill(status=403,json={'status':'error','code':'csrf_failed','message':'合成口令失效'})
    p.route(path,csrf);button(p,'维护售出事实');d=p.get_by_role('dialog',name='维护售出事实');d.get_by_label('销售确认或更正依据',exact=True).fill('退货更正依据');button(d,'保存售出确认')
    expect(d.get_by_text('会话口令已更新，请明确重试；未自动重发。',exact=True)).to_be_visible();assert blocked==[1]
    p.unroute(path,csrf);button(d,'保存售出确认');d.wait_for(state='hidden');assert query(desktop.app,'SELECT sold FROM digital_item WHERE item_id=%s',(item,))[0]['sold']==0


def test_unsaved_three_choices_and_expired_session_clears_management(desktop):
    setup(desktop);p=desktop.page;desktop.navigate('款式与发行');button(p,'维护资料');d=p.get_by_role('dialog',name='维护款式共用资料');d.get_by_label('款式名称',exact=True).fill('尚未保存')
    p.get_by_role('link',name=re.compile('数字物品$')).evaluate('(el)=>el.click()');guard=p.get_by_role('dialog',name='有未保存修改',exact=True)
    button(guard,'继续编辑');expect(d.get_by_label('款式名称',exact=True)).to_have_value('尚未保存')
    p.route('**/api/admin/catalog/actions/style',lambda route:route.fulfill(status=401,json={'status':'error','code':'unauthorized','message':'合成过期'}))
    button(d,'保存共用资料');button(p.get_by_role('dialog',name='确认同步共用商品资料？',exact=True),'确认同步保存');expect(p.get_by_role('heading',name='管理员登录')).to_be_visible();assert not p.locator('.ant-pro-layout').count()
