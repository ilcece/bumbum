"""原型审查整改的实际页面回归，全部使用正常认证与专属临时库。"""
from pathlib import Path
import re
import pytest
from tests.test_admin_browser import desktop,browser_gate,button,expect
from tests.admin_ui_helpers import setup,api,choose,install
from tests.test_admin_auth import query

pytestmark=[pytest.mark.auth_database,pytest.mark.browser]
OUT=Path('test-results/admin-review');OUT.mkdir(parents=True,exist_ok=True)

def shot(p,name):
    p.wait_for_timeout(350)
    p.screenshot(path=str(OUT/(name+'.png')),animations='disabled')


def test_danger_navigation_never_submits_and_style_save_confirms_real_impact(desktop):
    style,issue,item,chips=setup(desktop);p=desktop.page
    install(desktop,style,item,chips[0])
    p.goto(f'http://localhost:5174/items/{item}',wait_until='networkidle')
    button(p,'挂失物品');p.get_by_label('核对依据',exact=True).fill('仅填写，未确认挂失')
    p.get_by_role('link',name=re.compile('芯片管理')).evaluate('(e)=>e.click()')
    guard=p.get_by_role('dialog',name='离开未完成的业务确认？',exact=True);expect(guard).to_be_visible()
    assert guard.get_by_role('button',name='保存后继续',exact=True).count()==0
    shot(p,'danger-navigation')
    button(guard,'放弃输入并离开');p.wait_for_url('**/chips')
    assert query(desktop.app,'SELECT lost_at FROM whole_item WHERE item_id=%s',(item,))[0]['lost_at'] is None
    p.goto('http://localhost:5174/catalog',wait_until='networkidle');button(p,'维护资料')
    d=p.get_by_role('dialog',name='维护款式共用资料',exact=True)
    d.get_by_label('款式名称',exact=True).fill('共用影响确认后的名称');button(d,'保存共用资料')
    confirm=p.get_by_role('dialog',name='确认同步共用商品资料？',exact=True);expect(confirm).to_contain_text('将影响1件引用该款式的物品，其中0件已启用')
    shot(p,'style-impact-confirm')
    assert query(desktop.app,'SELECT name FROM product_style WHERE id=%s',(style,))[0]['name']=='浏览器共用帽子'
    button(confirm,'确认同步保存');d.wait_for(state='hidden')
    assert query(desktop.app,'SELECT name FROM product_style WHERE id=%s',(style,))[0]['name']=='共用影响确认后的名称'


def test_issue_dirty_guard_and_free_identity_registration_open_exact_record(desktop):
    style,issue,item,_=setup(desktop);p=desktop.page;p.set_viewport_size({'width':1440,'height':900})
    draft=api(desktop,'issue',{'style_id':style,'name':'待保存发行','mode':'fixed','total':9,'description':'九件身份','rights':[]})['id']
    p.goto(f'http://localhost:5174/catalog/issue/{draft}',wait_until='networkidle')
    p.get_by_label('发行名称',exact=True).fill('已保存后才允许确认')
    expect(p.get_by_role('button',name='确认发行约定',exact=True)).to_be_disabled()
    button(p,'保存发行草案');expect(p.get_by_role('button',name='确认发行约定',exact=True)).to_be_enabled()
    shot(p,'issue-editor')
    button(p,'确认发行约定');button(p.get_by_role('dialog',name='确认发行约定',exact=True),'确认发行约定')
    expect(p.get_by_text('发行承诺与核定结果',exact=True)).to_be_visible()
    button(p,'登记该发行物品')
    d=p.get_by_role('dialog',name='登记数字物品',exact=True);expect(d).to_be_visible()
    expect(d.get_by_label('本件正式序号',exact=True)).to_have_value('1')
    d.get_by_label('系统物品编号',exact=True).fill('业务自定义号-帽子/甲')
    shot(p,'register-identity')
    button(d,'登记并查看物品');d.wait_for(state='hidden')
    detail=p.get_by_role('dialog',name='数字物品详情',exact=True)
    expect(detail.get_by_text('业务自定义号-帽子/甲',exact=True).first).to_be_visible()
    expect(detail.get_by_text('#1/9',exact=True).first).to_be_visible()
    shot(p,'identity-created')
    for total,expected in ((50,'#02/50'),(200,'#002/200'),(2000,'#0002/2000'),(None,'#002')):
        agreement=api(desktop,'issue',{'style_id':style,'name':f'序号位数验证{total}','mode':'fixed' if total else 'unlimited',**({'total':total} if total else {}),'description':'只验证显示位数，存储仍为整数','rights':[]})['id']
        api(desktop,'confirmIssue',{'issue_id':agreement})
        identity=api(desktop,'item',{'issue_id':agreement,'item_uid':f'序号验证-{total}','edition_number':2})['id']
        p.goto(f'http://localhost:5174/items/{identity}',wait_until='networkidle')
        expect(p.get_by_text(expected,exact=True).first).to_be_visible()
        if total==2000:shot(p,'edition-2000')



def test_sale_backdate_is_preserved_and_chip_form_has_no_business_category(desktop):
    _,_,item,_=setup(desktop);p=desktop.page
    p.goto(f'http://localhost:5174/items/{item}',wait_until='networkidle')
    button(p,'维护售出事实');d=p.get_by_role('dialog',name='维护售出事实',exact=True)
    # 明确选择确认，默认时间来自与服务一致的受控页面时钟。
    d.get_by_role('radio',name='确认已售出',exact=True).check()
    date=d.get_by_label('首次售出时间（北京时间）',exact=True)
    date.fill('2026-10-20 11:00:00');date.press('Enter')
    d.get_by_label('销售确认或更正依据',exact=True).fill('外部成交记录已核对')
    button(d,'保存售出确认');d.wait_for(state='hidden')
    assert query(desktop.app,'SELECT first_sold_at FROM digital_item WHERE item_id=%s',(item,))[0]['first_sold_at'].strftime('%Y-%m-%d %H:%M:%S')=='2026-10-20 03:00:00'
    p.goto('http://localhost:5174/chips',wait_until='networkidle');button(p,'手工登记芯片')
    d=p.get_by_role('dialog',name='手工登记芯片',exact=True)
    assert d.get_by_label('物品类别',exact=True).count()==0
    expect(d.get_by_text('用于验证的对象标记',exact=False)).to_be_visible()
    shot(p,'chip-register')


def test_beijing_input_in_foreign_timezone_and_paged_style_label(desktop):
    from tests.browser_support import BrowserSession
    context=desktop.page.context.browser.new_context(timezone_id='America/Los_Angeles',viewport={'width':1440,'height':900})
    try:
        page=context.new_page();session=BrowserSession(page,desktop.app,desktop._account)
        style,_,_,_=setup(session)
        for n in range(21):api(session,'style',{'project':'fashion','code':f'PAGE-{n}','name':f'后建款式{n}','specs':[],'image_urls':[]})
        draft=api(session,'issue',{'style_id':style,'name':'北京时间限时发行','mode':'period','starts_at':'2026-10-01T03:00:00Z','ends_at':'2026-10-20T03:00:00Z','counting_rule':'外部有效成交核对','description':'按北京时间约定','rights':[]})['id']
        page.goto(f'http://localhost:5174/catalog/issue/{draft}',wait_until='networkidle')
        expect(page.get_by_text('UI-CAP · 浏览器共用帽子',exact=True)).to_be_visible()
        expect(page.get_by_label('销售开始（北京时间）',exact=True)).to_have_value('2026-10-01 11:00:00')
        start=page.get_by_label('销售开始（北京时间）',exact=True);start.fill('2026-10-02 12:30:00');start.press('Enter')
        button(page,'保存发行草案')
        expect(page.get_by_role('button',name='确认发行约定',exact=True)).to_be_enabled()
        assert query(desktop.app,'SELECT starts_at FROM product_issue WHERE id=%s',(draft,))[0]['starts_at'].strftime('%Y-%m-%d %H:%M:%S')=='2026-10-02 04:30:00'
        page.reload(wait_until='networkidle')
        expect(page.get_by_label('销售开始（北京时间）',exact=True)).to_have_value('2026-10-02 12:30:00')
        shot(page,'beijing-input-los-angeles')
        page.get_by_label('发行名称',exact=True).fill('离开时明确放弃')
        button(page,'取消');guard=page.get_by_role('dialog',name='有未保存修改',exact=True)
        button(guard,'放弃并继续');page.wait_for_url('**/catalog?tab=issues')
        expect(page.get_by_role('dialog',name='有未保存修改',exact=True)).to_have_count(0)
    finally:context.close()
