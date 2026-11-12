"""正式Umi后台浏览器回归：真实认证、芯片登记和受控密钥。"""
import re
import pytest
from tests.browser_support import browser_fixture
from tests.test_admin_auth import query

pytestmark=[pytest.mark.auth_database,pytest.mark.browser]


@pytest.fixture(autouse=True)
def browser_gate(request):
    if not request.config.getoption('--browser'):pytest.skip('未启用--browser，普通回归不启动浏览器')


@pytest.fixture
def desktop(request,auth_app,admin_account,tmp_path):
    yield from browser_fixture(request,auth_app,admin_account,tmp_path)


def expect(locator):
    from playwright.sync_api import expect as match
    return match(locator)


def button(page,name):
    page.get_by_role('button',name=re.compile(r'^(?:loading )?'+r'\s*'.join(re.escape(x) for x in name)+'$')).click()


def test_login_restore_logout(desktop):
    desktop.login();p=desktop.page;p.reload(wait_until='networkidle')
    expect(p.get_by_role('link',name=re.compile('工作台$'))).to_be_visible()
    button(p,'退出登录');expect(p.get_by_role('heading',name='管理员登录')).to_be_visible()
    assert not p.locator('.ant-pro-layout').count()


def test_chip_registration_duplicate_and_real_batch(desktop):
    desktop.login();desktop.navigate('芯片管理');p=desktop.page
    for batch in ('新批次','不应覆盖'):
        button(p,'手工登记芯片');dialog=p.get_by_role('dialog',name='手工登记芯片')
        dialog.get_by_label('芯片编号 UID',exact=True).fill('04000000000071')
        dialog.get_by_label('批次',exact=True).fill(batch);button(dialog,'登记并查看')
        dialog.wait_for(state='hidden');expect(p.get_by_text('新批次',exact=True).first).to_be_visible()
        p.locator('.ant-drawer-close').click();p.get_by_role('dialog').wait_for(state='hidden')
    assert query(desktop.app,"SELECT COUNT(*) AS n FROM chip WHERE chip_uid='04:00:00:00:00:00:71'")[0]['n']==1
    assert query(desktop.app,'SELECT batch_no FROM chip')[0]['batch_no']=='新批次'


def test_keys_generate_view_confirm_and_clear(desktop):
    from tests.test_chip_keys import configure,reading
    from core.chip_keys import target_keys
    configure(desktop.app)
    query(desktop.app,"INSERT INTO item(project_id,item_uid) VALUES (1,'FASH-2026-009999')")
    i=query(desktop.app,'SELECT id FROM item')[0]['id']
    query(desktop.app,"INSERT INTO chip(chip_uid,project_id,item_id,chip_status) VALUES ('04:00:00:00:00:00:72',1,%s,'bound')",(i,))
    c=query(desktop.app,'SELECT id FROM chip')[0]['id']
    desktop.login();p=desktop.page;p.set_viewport_size({'width':1440,'height':900});p.goto(f'http://localhost:5174/chips/{c}',wait_until='networkidle')
    button(p,'查看密钥与配置');d=p.get_by_role('dialog').last
    from pathlib import Path
    evidence=Path('test-results/key-review');evidence.mkdir(parents=True,exist_ok=True)
    expect(d).to_be_visible()
    d.evaluate("el => Promise.all(el.getAnimations({subtree:true}).map(a => a.finished))")
    p.screenshot(animations="disabled",path=str(evidence/'01-unconfigured.png'),full_page=True)
    button(d,'生成密钥');expect(d.get_by_text('密钥已生成',exact=False).first).to_be_visible()
    d.get_by_role('checkbox').first.check();button(d,'查看密钥')
    expect(d.locator('.key-row')).to_have_count(5)
    expect(d.locator('.template-value')).to_contain_text('picc_data='+'0'*32+'&cmac='+'0'*16)
    p.context.grant_permissions(['clipboard-read','clipboard-write'])
    d.locator('.template-value .ant-typography-copy').click()
    assert p.evaluate('navigator.clipboard.readText()')=='https://nfc.bumbum.cc/tap?picc_data='+'0'*32+'&cmac='+'0'*16
    d.get_by_role('checkbox').first.uncheck();expect(d.locator('[aria-label="芯片密钥"]')).to_have_count(0)
    # 所用读数来自临时库合成密钥，不把它当作真实芯片验证。
    with desktop.app.app_context():keys=target_keys('fashion','04:00:00:00:00:00:72')
    for n,count in enumerate((3,4),1):
        data=reading(keys,'04:00:00:00:00:00:72',count)
        link='https://nfc.bumbum.cc/tap?picc_data='+data['picc_data']+'&cmac='+data['cmac']
        d.get_by_label(f'第{n}条触碰链接',exact=False).fill(link)
    p.get_by_role('link',name=re.compile('工作台$')).evaluate('(el)=>el.click()')
    guard=p.get_by_role('dialog',name='放弃未提交的配置核验？',exact=True);expect(guard).to_be_visible();button(guard,'继续核验')
    d.get_by_role('checkbox').last.check();button(d,'确认配置核验')
    expect(d.get_by_text('配置已核验',exact=False).first).to_be_visible()
    assert query(desktop.app,'SELECT provisioned_at FROM chip WHERE id=%s',(c,))[0]['provisioned_at']

    d.evaluate("el => Promise.all(el.getAnimations({subtree:true}).map(a => a.finished))")
    p.screenshot(animations="disabled",path=str(evidence/'02-configured.png'),full_page=True)
    expect(d.get_by_label('第1条触碰链接',exact=True)).to_have_count(0)
    d.get_by_role('button',name=re.compile(r'^关\s*闭$')).last.click();d.wait_for(state='hidden')
    button(p,'查看密钥与配置');expect(p.get_by_role('dialog',name='密钥与配置')).to_be_visible()
    desktop.navigate('工作台');expect(p.get_by_text('物品与芯片概况',exact=True)).to_be_visible()


def test_candidate_key_query_preserves_preparation(desktop,monkeypatch):
    from pathlib import Path
    from core.acceptance_data import seed
    from core.db import get_database
    from tests.test_chip_keys import configure
    configure(desktop.app)
    monkeypatch.setattr('core.test_batches.validate_test_target',lambda _:None)
    with desktop.app.test_request_context():seed(get_database(),desktop._account['username'],apply=True)
    candidate=query(desktop.app,'SELECT pending_chip_id AS id,item_id FROM item_handover WHERE pending_chip_id IS NOT NULL LIMIT 1')[0]
    desktop.login();p=desktop.page;p.goto(f"http://localhost:5174/chips/{candidate['id']}",wait_until='networkidle')
    button(p,'查看密钥与配置');d=p.get_by_role('dialog',name='密钥与配置');expect(d).to_be_visible()
    writes=[]
    def lost(route):
        writes.append(1);response=route.fetch();assert response.status==200
        route.fulfill(status=503,json={'status':'error','code':'service_unavailable','message':'隔离模拟回执丢失'})
    path='**/api/admin/chips/*/generate-keys';p.route(path,lost)
    button(d,'生成密钥');expect(d.get_by_text('结果暂未确认，请先查询实际记录；不会自动重发或重新生成密钥。',exact=True)).to_be_visible()
    p.unroute(path,lost)
    button(d,'查询实际记录');expect(d.get_by_text('芯片关联或状态已改变，请关闭弹窗并重新查询。',exact=True)).to_have_count(0)
    expect(d.get_by_text('已查到密钥生成记录；实卡配置尚未确认。',exact=True)).to_be_visible()
    expect(d.get_by_role('checkbox').first).to_be_enabled();assert writes==[1]
    assert query(desktop.app,'SELECT item_id FROM chip WHERE id=%s',(candidate['id'],))[0]['item_id'] is None
    d.evaluate('el => Promise.all(el.getAnimations({subtree:true}).map(a => a.finished))')
    p.screenshot(animations='disabled',path='test-results/key-review/03-candidate-query.png',full_page=True)
