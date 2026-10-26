"""核心桌面与芯片绑定回归，必须显式启用，使用独立临时MySQL。"""

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


# 以下样例只写入desktop夹具创建的专属临时数据库。
def binding_samples(desktop, count=2):
    from tests.test_admin_auth import query
    for number in range(1,count+1):
        query(desktop.app,"INSERT INTO item(project_id,item_uid) SELECT id,%s FROM project WHERE code='fashion'",(f'FASH-2026-{880000+number:06d}',))
    query(desktop.app,"INSERT INTO chip(chip_uid) VALUES ('04:00:00:00:00:00:51')")
    desktop.login(); desktop.navigate('芯片管理')
    desktop.page.get_by_role('button',name='绑定物品',exact=True).click()
    return desktop.page.get_by_role('dialog',name='绑定物品',exact=True)


def open_keys(desktop):
    from tests.test_chip_keys import configure
    configure(desktop.app)
    binding = binding_samples(desktop)
    select_binding(binding)
    binding.get_by_role('button', name='确认绑定', exact=True).click()
    desktop.page.get_by_role('status').filter(has_text='绑定成功').wait_for()
    desktop.page.get_by_role('button', name='密钥与配置', exact=True).click()
    return desktop.page.get_by_role('dialog', name='密钥与配置', exact=True)


def test_keys_generate_view_confirm_and_clear(desktop):
    from tests.test_admin_auth import query
    from tests.test_chip_keys import reading
    from core.secret_storage import decrypt_chip_keys
    dialog = open_keys(desktop)
    writes = []
    desktop.page.on('request', lambda request: writes.append(request.url) if request.method == 'POST' and request.url.endswith('/generate-keys') else None)
    dialog.get_by_role('button',name='生成密钥',exact=True).evaluate('(button)=>{button.click();button.click()}')
    dialog.get_by_role('status').filter(has_text='密钥已生成并加密保存').wait_for()
    assert len(writes) == 1
    assert dialog.get_by_role('button',name='查看密钥',exact=True).is_disabled()
    dialog.get_by_role('checkbox').first.check()
    dialog.get_by_role('button',name='查看密钥',exact=True).click()
    dialog.get_by_label('K0',exact=True).wait_for()
    uid = '04:00:00:00:00:00:51'
    row = query(desktop.app,'SELECT * FROM chip_key')[0]
    with desktop.app.app_context(): keys = decrypt_chip_keys(row,row['chip_id'])
    assert dialog.get_by_label('K1',exact=True).input_value() == keys['K1']
    dialog.get_by_role('button',name='隐藏并清除密钥',exact=True).click()
    assert dialog.get_by_label('K1',exact=True).count() == 0
    for index,counter in enumerate((10,14)):
        value = reading(keys, uid, counter)
        dialog.get_by_label(f'第{index+1}条触碰链接',exact=True).fill('https://nfc.bumbum.cc/tap?picc_data='+value['picc_data']+'&cmac='+value['cmac'])
    dialog.get_by_role('checkbox').last.check()
    dialog.get_by_role('button',name='确认配置核验',exact=True).click()
    dialog.get_by_role('status').filter(has_text='配置核验通过').wait_for()
    assert query(desktop.app,'SELECT last_verified_counter FROM chip')[0]['last_verified_counter'] == 14
    assert dialog.get_by_label('第1条触碰链接',exact=True).input_value() == ''
    dialog.get_by_role('button',name='关闭',exact=True).click()
    desktop.page.get_by_role('button',name='密钥与配置',exact=True).click()
    assert dialog.get_by_label('K1',exact=True).count() == 0
    assert dialog.get_by_text('密钥已生成；配置已核验',exact=True).count() == 1


def test_keys_unknown_generation_queries_before_retry(desktop):
    dialog = open_keys(desktop)
    writes = []
    def lost_receipt(route):
        result = route.fetch()
        assert result.status == 200
        writes.append(1)
        route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','code':'service_unavailable','message':'合成回执丢失'}))
    desktop.page.route('**/generate-keys',lost_receipt)
    dialog.get_by_role('button',name='生成密钥',exact=True).click()
    dialog.get_by_role('alert').filter(has_text='结果暂未确认').wait_for()
    assert dialog.get_by_role('button',name='生成密钥',exact=True).is_disabled()
    dialog.get_by_role('button',name='查询实际记录',exact=True).click()
    dialog.get_by_role('status').filter(has_text='已查到密钥生成记录').wait_for()
    assert dialog.get_by_role('button',name='生成密钥',exact=True).is_disabled() and len(writes) == 1


@pytest.mark.parametrize('status,code',[(401,'unauthorized'),(403,'csrf_failed')])
def test_keys_expiry_does_not_retry(desktop,status,code):
    dialog = open_keys(desktop)
    writes=[]
    def reject(route):
        writes.append(1)
        route.fulfill(status=status,content_type='application/json',body=json.dumps({'status':'error','code':code,'message':'合成权限失败'}))
    desktop.page.route('**/generate-keys',reject)
    dialog.get_by_role('button',name='生成密钥',exact=True).click()
    if status == 401:
        desktop.page.get_by_role('button',name='登录',exact=True).wait_for()
        assert desktop.page.locator('.chip-keys-dialog').count()==0
    else:
        dialog.get_by_role('alert').filter(has_text='操作口令已失效').wait_for()
        assert dialog.get_by_role('button',name='生成密钥',exact=True).is_disabled()
    assert len(writes)==1


def select_binding(dialog, number=1):
    dialog.get_by_label('物品关键词',exact=True).fill(f'FASH-2026-{880000+number:06d}')
    dialog.get_by_role('button',name='查询物品',exact=True).click()
    dialog.get_by_role('radio',name=f'选择物品 FASH-2026-{880000+number:06d}',exact=True).check()
    dialog.get_by_role('checkbox').check()


def test_binding_filters_occupied_before_pagination_without_hiding_main_list(desktop):
    from tests.test_admin_auth import query
    dialog=binding_samples(desktop,count=25)
    for n,status in [(23,'bound'),(24,'disabled'),(25,'lost')]:
        target=query(desktop.app,'SELECT * FROM item WHERE item_uid=%s',(f'FASH-2026-{880000+n:06d}',))[0]
        query(desktop.app,'INSERT INTO chip(chip_uid,project_id,item_id,chip_status) VALUES (%s,%s,%s,%s)',(f'04:00:00:00:00:00:{n:02X}',target['project_id'],target['id'],status))
    dialog.get_by_role('button',name='查询物品',exact=True).click()
    dialog.get_by_text('共 22 件未被芯片占用的物品；最终能否绑定以提交时检查为准。',exact=True).wait_for()
    assert dialog.get_by_role('radio').count()==20
    assert dialog.get_by_role('cell',name='FASH-2026-880025',exact=True).count()==0
    dialog.get_by_role('button',name='下一页',exact=True).click()
    dialog.get_by_role('cell',name='FASH-2026-880001',exact=True).wait_for()
    assert dialog.get_by_role('radio').count()==2
    dialog.get_by_label('物品关键词',exact=True).fill('FASH-2026-880025')
    dialog.get_by_role('button',name='查询物品',exact=True).click()
    dialog.get_by_text('没有符合条件的可绑定物品。',exact=True).wait_for()
    dialog.get_by_role('button',name='关闭',exact=True).click()
    desktop.navigate('物品管理')
    desktop.page.get_by_role('cell',name='FASH-2026-880025',exact=True).wait_for()


def test_binding_selection_and_real_save(desktop):
    from tests.test_admin_auth import query
    dialog=binding_samples(desktop)
    page=desktop.page
    assert dialog.get_by_role('button',name='确认绑定',exact=True).is_disabled()
    select_binding(dialog)
    page.once('dialog',lambda d:d.dismiss())
    dialog.get_by_role('button',name='关闭',exact=True).click()
    assert dialog.is_visible()
    dialog.get_by_label('物品关键词',exact=True).fill('FASH-2026-880002')
    assert dialog.get_by_role('button',name='确认绑定',exact=True).is_disabled()
    dialog.get_by_role('status').filter(has_text='条件已改变').wait_for()
    select_binding(dialog,2)
    writes=[]
    page.on('request',lambda request:writes.append(1) if '/bind-item' in request.url and request.method=='POST' else None)
    dialog.get_by_role('button',name='确认绑定',exact=True).evaluate('(button)=>{button.click();button.click()}')
    page.get_by_role('status').filter(has_text='绑定成功').wait_for()
    row=page.get_by_role('row').filter(has_text='04:00:00:00:00:00:51')
    row.get_by_role('cell',name='FASH-2026-880002',exact=True).wait_for()
    assert len(writes)==1 and row.get_by_role('button',name='绑定物品',exact=True).count()==0
    assert query(desktop.app,"SELECT status FROM item WHERE item_uid='FASH-2026-880002'")[0]['status']=='draft'
    page.reload(wait_until='networkidle')
    desktop.navigate('芯片管理')
    page.get_by_role('cell',name='FASH-2026-880002',exact=True).wait_for()


def test_binding_saved_but_response_lost_and_list_failure(desktop):
    dialog=binding_samples(desktop)
    page=desktop.page
    select_binding(dialog)
    writes=[]
    def lose_response(route):
        writes.append(1)
        response=route.fetch()
        assert response.status==200
        route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','code':'service_unavailable','message':'合成回执丢失','error_id':'d'*24}))
    page.route('**/api/admin/chips/*/bind-item',lose_response)
    dialog.get_by_role('button',name='确认绑定',exact=True).click()
    dialog.get_by_role('alert').filter(has_text='结果尚未确认').wait_for()
    assert dialog.get_by_role('button',name='重试原目标绑定',exact=True).is_disabled()
    assert dialog.get_by_label('物品关键词',exact=True).is_disabled()
    assert 'd'*24 in dialog.get_by_role('alert').inner_text()
    reads=[]
    def list_failure(route):
        reads.append(1)
        if len(reads)==1:route.continue_()
        else:route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','code':'service_unavailable','message':'合成绑定后列表失败'}))
    page.route('**/api/admin/chips?*',list_failure)
    dialog.get_by_role('button',name='查询此芯片',exact=True).click()
    page.get_by_role('status').filter(has_text='已查询确认绑定结果').wait_for()
    page.get_by_role('alert').filter(has_text='合成绑定后列表失败').wait_for()
    assert len(writes)==1


def test_binding_unknown_pending_requires_manual_same_target_retry(desktop):
    dialog=binding_samples(desktop)
    page=desktop.page
    select_binding(dialog)
    writes=[]
    def fail_once(route):
        writes.append(1)
        if len(writes)==1:route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','code':'service_unavailable','message':'合成提交前故障'}))
        else:route.continue_()
    page.route('**/api/admin/chips/*/bind-item',fail_once)
    dialog.get_by_role('button',name='确认绑定',exact=True).click()
    dialog.get_by_role('button',name='查询此芯片',exact=True).click()
    dialog.get_by_role('alert').filter(has_text='原请求仍可能处理中').wait_for()
    assert dialog.get_by_role('button',name='重试原目标绑定',exact=True).is_disabled()
    assert dialog.get_by_label('候选项目',exact=True).is_disabled()
    assert dialog.get_by_role('radio',name='选择物品 FASH-2026-880001',exact=True).is_disabled()
    dialog.get_by_role('checkbox').check()
    dialog.get_by_role('button',name='重试原目标绑定',exact=True).click()
    page.get_by_role('status').filter(has_text='绑定成功').wait_for()
    assert len(writes)==2


def test_binding_csrf_does_not_refresh_or_resend(desktop):
    dialog=binding_samples(desktop)
    page=desktop.page
    select_binding(dialog)
    writes=[]; refreshes=[]
    page.on('request',lambda request:refreshes.append(1) if '/admin/auth/session' in request.url else None)
    def csrf(route):
        writes.append(1)
        route.fulfill(status=403,content_type='application/json',body=json.dumps({'status':'error','code':'csrf_failed','message':'合成防冒用校验失败'}))
    page.route('**/api/admin/chips/*/bind-item',csrf)
    dialog.get_by_role('button',name='确认绑定',exact=True).click()
    dialog.get_by_role('alert').filter(has_text='刷新页面后重新核对').wait_for()
    assert len(writes)==1 and not refreshes
    assert dialog.get_by_role('button',name='确认绑定',exact=True).is_disabled()


def test_binding_pagination_stale_queries_and_archived(desktop):
    from tests.test_admin_auth import query
    dialog=binding_samples(desktop,22)
    page=desktop.page
    query(desktop.app,"UPDATE item SET status='archived' WHERE item_uid='FASH-2026-880022'")
    dialog.get_by_role('button',name='查询物品',exact=True).click()
    dialog.get_by_role('radio',name='选择物品 FASH-2026-880022',exact=True).wait_for()
    assert dialog.get_by_role('radio',name='选择物品 FASH-2026-880022',exact=True).is_disabled()
    dialog.get_by_role('radio',name='选择物品 FASH-2026-880021',exact=True).check()
    dialog.get_by_role('checkbox').check()
    dialog.get_by_role('button',name='下一页',exact=True).click()
    dialog.get_by_role('radio',name='选择物品 FASH-2026-880001',exact=True).wait_for()
    assert dialog.get_by_role('checkbox').count()==0
    held=[]
    def hold_first(route):
        if 'keyword=hold' in route.request.url:held.append(route)
        else:route.continue_()
    page.route('**/api/admin/items?*',hold_first)
    dialog.get_by_label('物品关键词',exact=True).fill('hold')
    with page.expect_request('**/api/admin/items?*'):
        dialog.get_by_role('button',name='查询物品',exact=True).click()
    select_binding(dialog)
    assert len(held)==1
    held[0].fulfill(status=200,content_type='application/json',body=json.dumps({'status':'ok','data':{'items':[],'total':0,'page':1,'page_size':20}}))
    assert dialog.get_by_role('radio',name='选择物品 FASH-2026-880001',exact=True).is_checked()
    # 释放旧响应后再执行一次可观察操作，确认旧候选不覆盖新选择。
    dialog.get_by_role('checkbox').uncheck()
    assert dialog.get_by_role('radio',name='选择物品 FASH-2026-880001',exact=True).is_visible()


@pytest.mark.parametrize('lookup', ['other','missing','failed','disabled','lost'])
def test_binding_unknown_lookup_does_not_guess_or_overwrite(desktop,lookup):
    dialog=binding_samples(desktop)
    page=desktop.page
    select_binding(dialog)
    writes=[]
    def unavailable(route):
        writes.append(1)
        route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','code':'service_unavailable','message':'合成故障'}))
    page.route('**/api/admin/chips/*/bind-item',unavailable)
    dialog.get_by_role('button',name='确认绑定',exact=True).click()
    def altered_lookup(route):
        if lookup=='failed':
            route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','code':'service_unavailable','message':'合成查询失败'}));return
        response=route.fetch();payload=response.json()
        if lookup=='missing':payload['data'].update(items=[],total=0)
        elif lookup=='other':payload['data']['items'][0].update(chip_status='bound',item_id=999999,item_uid='FASH-2026-999999')
        else:payload['data']['items'][0]['chip_status']=lookup
        route.fulfill(status=200,content_type='application/json',body=json.dumps(payload))
    page.route('**/api/admin/chips?*',altered_lookup)
    dialog.get_by_role('button',name='查询此芯片',exact=True).click()
    text={'other':'与本次目标不符','missing':'尚未查到该芯片','failed':'结果仍未确认','disabled':'不能提交绑定','lost':'不能提交绑定'}[lookup]
    dialog.get_by_role('alert').filter(has_text=text).wait_for()
    assert len(writes)==1 and dialog.get_by_role('button',name='重试原目标绑定',exact=True).is_disabled()
    assert dialog.get_by_label('物品关键词',exact=True).is_disabled()


def test_binding_busy_blocks_close_and_navigation(desktop, tmp_path):
    dialog=binding_samples(desktop)
    page=desktop.page
    page.set_viewport_size({'width':1280,'height':500})
    select_binding(dialog)
    held=[]
    page.route('**/api/admin/chips/*/bind-item',lambda route:held.append(route))
    with page.expect_request('**/api/admin/chips/*/bind-item'):
        dialog.get_by_role('button',name='确认绑定',exact=True).click()
    try:
        dialog.get_by_role('button',name='关闭',exact=True).click()
        page.keyboard.press('Escape')
        # 模态弹窗会从无障碍树隐藏背景，使用DOM定位检查父页面的离开保护。
        page.locator('nav[aria-label="基础功能"] button').filter(has_text='物品管理').evaluate('(button)=>button.click()')
        assert dialog.is_visible() and dialog.get_by_role('button',name='正在绑定…',exact=True).is_disabled()
        assert len(held)==1
        page.screenshot(path=str(tmp_path/'binding-dialog.png'))
    finally:
        if held:held[0].continue_()
    page.get_by_role('status').filter(has_text='绑定成功').wait_for()
    # 成功后应解除父页面离开保护，导航不再要求放弃旧选择。
    desktop.navigate('物品管理')
    page.get_by_role('heading',name='物品管理',exact=True).wait_for()


def test_binding_query_401_hides_management_data(desktop):
    dialog=binding_samples(desktop)
    page=desktop.page
    page.route('**/api/admin/items?*',lambda route:route.fulfill(status=401,content_type='application/json',body=json.dumps({'status':'error','code':'unauthorized','message':'合成会话失效'})))
    dialog.get_by_role('button',name='查询物品',exact=True).click()
    page.get_by_role('button',name='登录',exact=True).wait_for()
    assert page.locator('.admin-shell').count()==0
    assert page.get_by_role('dialog',name='绑定物品',exact=True).count()==0


@pytest.mark.parametrize('unsafe', ['chip','item'])
def test_binding_refuses_imprecise_browser_ids_with_explanation(desktop,unsafe):
    dialog=binding_samples(desktop)
    page=desktop.page
    writes=[]
    page.on('request',lambda request:writes.append(1) if '/bind-item' in request.url and request.method=='POST' else None)
    def imprecise(route):
        response=route.fetch();payload=response.json()
        payload['data']['items'][0]['id']=9007199254740992
        route.fulfill(status=200,content_type='application/json',body=json.dumps(payload))
    if unsafe=='chip':
        dialog.get_by_role('button',name='取消绑定',exact=True).click()
        page.route('**/api/admin/chips?*',imprecise)
        page.reload(wait_until='networkidle');desktop.navigate('芯片管理')
        page.get_by_role('button',name='绑定物品',exact=True).click()
        dialog=page.get_by_role('dialog',name='绑定物品',exact=True)
    else:page.route('**/api/admin/items?*',imprecise)
    dialog.get_by_role('button',name='查询物品',exact=True).click()
    dialog.get_by_role('alert').filter(has_text='编号超出当前页面可处理范围').wait_for()
    assert dialog.get_by_role('radio',name='选择物品 FASH-2026-880002',exact=True).is_disabled()
    assert dialog.get_by_role('button',name='确认绑定',exact=True).is_disabled()
    assert not writes
