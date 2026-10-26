"""三条核心桌面回归，必须显式启用，使用独立临时MySQL。"""

import json

import pytest

from tests.browser_support import browser_fixture

pytestmark = [pytest.mark.auth_database, pytest.mark.browser]


@pytest.fixture(autouse=True)
def browser_gate(request):
    if not request.config.getoption('--browser'):
        pytest.skip('未启用--browser，普通回归不启动浏览器')


@pytest.fixture
def desktop(request, auth_app, admin_account, tmp_path):
    yield from browser_fixture(request, auth_app, admin_account, tmp_path)


def test_login_restore_logout(desktop):
    desktop.login()
    page = desktop.page
    page.reload(wait_until='networkidle')
    page.get_by_role('heading', name='你好，cece', exact=True).wait_for()
    desktop.navigate('所有权')
    page.get_by_role('button', name='绑定所有权', exact=True).click()
    popup = page.get_by_role('dialog', name='功能暂未开放')
    popup.get_by_text('当前版本暂未实现', exact=True).wait_for()
    popup.get_by_role('button', name='知道了', exact=True).click()
    page.get_by_role('button', name='退出登录', exact=True).click()
    page.get_by_role('button', name='登录', exact=True).wait_for()
    assert page.locator('.admin-shell').count() == 0


def test_chip_batch_duplicate_and_query(desktop):
    desktop.login(); desktop.navigate('芯片管理')
    page = desktop.page
    for batch in ('BROWSER-BATCH', 'SHOULD-NOT-REPLACE'):
        page.get_by_role('button', name='登记芯片', exact=True).click()
        dialog = page.get_by_role('dialog', name='登记新芯片')
        dialog.get_by_label('芯片UID', exact=True).fill('04a27f1b5e8000')
        dialog.get_by_label('批次（可选）', exact=True).fill(batch)
        dialog.get_by_role('button', name='登记芯片', exact=True).click()
        page.get_by_role('status').filter(has_text='登记成功' if batch == 'BROWSER-BATCH' else '无需重复登记').wait_for()
        page.get_by_role('cell', name='BROWSER-BATCH', exact=True).wait_for()
    assert page.get_by_role('cell', name='SHOULD-NOT-REPLACE', exact=True).count() == 0
    page.get_by_role('button', name='查看全部', exact=True).click()
    page.get_by_role('cell', name='04:A2:7F:1B:5E:80:00', exact=True).wait_for()


def test_item_profile_status_and_failure(desktop):
    desktop.login(); desktop.navigate('物品管理')
    page = desktop.page
    page.get_by_role('button', name='创建物品', exact=True).click()
    create = page.get_by_role('dialog', name='创建物品草稿', exact=True)
    create.get_by_label('所属项目', exact=True).select_option('fashion')
    create.get_by_label('物品编号', exact=True).fill('FASH-2026-770001')
    create.get_by_role('button', name='创建草稿', exact=True).click()
    row = page.get_by_role('row').filter(has_text='FASH-2026-770001')
    row.get_by_role('button', name='编辑资料', exact=True).click()
    editor = page.get_by_role('dialog', name='服装基础资料', exact=True)
    name = editor.get_by_label('名称（必填，最多128字符）', exact=True)
    name.fill('浏览器回归服装')
    editor.get_by_role('button', name='保存资料', exact=True).click()
    editor.get_by_role('status').filter(has_text='资料已保存').wait_for()
    editor.get_by_role('button', name='启用物品', exact=True).click()
    editor.get_by_role('status').filter(has_text='物品已启用').wait_for()
    editor.get_by_role('button', name='停用物品', exact=True).click()
    editor.get_by_role('status').filter(has_text='物品已停用').wait_for()
    name.fill('尚未保存')
    page.once('dialog', lambda dialog: dialog.dismiss())
    editor.get_by_role('button', name='关闭', exact=True).click()
    assert name.input_value() == '尚未保存'
    page.once('dialog', lambda dialog: dialog.accept())
    editor.get_by_role('button', name='重新读取资料', exact=True).click()
    page.wait_for_function("document.querySelector('.profile-editor input')?.value === '浏览器回归服装'")
    writes = []
    def failure(route):
        writes.append(1)
        route.fulfill(status=503, content_type='application/json', body=json.dumps({'status':'error','code':'service_unavailable','message':'合成保存失败'}))
    page.route('**/api/admin/items/*/profile', failure)
    name.fill('失败后保留')
    editor.get_by_role('button', name='保存资料', exact=True).click()
    editor.get_by_role('alert').filter(has_text='合成保存失败').wait_for()
    assert name.input_value() == '失败后保留' and len(writes) == 1
    page.unroute('**/api/admin/items/*/profile')
