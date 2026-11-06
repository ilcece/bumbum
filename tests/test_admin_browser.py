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
        button(p,'登记芯片');dialog=p.get_by_role('dialog',name='登记芯片')
        dialog.get_by_label('芯片编号 UID',exact=True).fill('04000000000071')
        dialog.get_by_label('批次',exact=True).fill(batch);button(dialog,'保存')
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
    desktop.login();p=desktop.page;p.goto(f'http://localhost:5174/chips/{c}',wait_until='networkidle')
    button(p,'查看密钥与配置');d=p.get_by_role('dialog').last
    button(d,'生成密钥');expect(d.get_by_text('密钥已生成',exact=False).first).to_be_visible()
    # 所用读数来自临时库合成密钥，不把它当作真实芯片验证。
    with desktop.app.app_context():keys=target_keys('fashion','04:00:00:00:00:00:72')
    for n,count in enumerate((3,4),1):
        data=reading(keys,'04:00:00:00:00:00:72',count)
        link='https://nfc.bumbum.cc/tap?picc_data='+data['picc_data']+'&cmac='+data['cmac']
        d.get_by_label(f'第{n}条触碰链接',exact=False).fill(link)
    d.get_by_role('checkbox').last.check();button(d,'确认配置核验')
    expect(d.get_by_text('配置已核验',exact=False).first).to_be_visible()
    assert query(desktop.app,'SELECT provisioned_at FROM chip WHERE id=%s',(c,))[0]['provisioned_at']
