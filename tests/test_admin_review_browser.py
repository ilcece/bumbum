"""原型审查整改的实际页面回归，全部使用正常认证与专属临时库。"""
from pathlib import Path
import re
import pytest
from tests.test_admin_browser import desktop,browser_gate,button,expect
from tests.admin_ui_helpers import setup,api,choose,install,save_identity_draft
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


@pytest.mark.parametrize('failure', ['network', 'server'])
def test_style_preflight_failure_keeps_draft_editable_and_can_save(desktop, failure):
    style, _, _, _ = setup(desktop)
    p = desktop.page
    p.goto('http://localhost:5174/catalog', wait_until='networkidle')
    button(p, '维护资料')
    dialog = p.get_by_role('dialog', name='维护款式共用资料', exact=True)
    name = dialog.get_by_label('款式名称', exact=True)
    name.fill('保存前读取失败后保留的草稿')
    audit_sql = "SELECT COUNT(*) AS n FROM admin_audit WHERE action='catalog.style' AND target_id=%s"
    audit_before = query(desktop.app, audit_sql, (str(style),))[0]['n']
    writes, receipts = [], []

    def observed(request):
        if request.method == 'POST' and request.url.endswith('/api/admin/catalog/actions/style'):
            writes.append(request.post_data_json['request_id'])
        if request.method == 'POST' and request.url.endswith('/api/admin/catalog/actions/receipt'):
            receipts.append(1)

    def failed_read(route):
        if failure == 'network':
            route.abort('failed')
        else:
            route.fulfill(status=503, json={
                'status': 'error', 'code': 'service_unavailable', 'message': '隔离模拟保存前读取失败',
            })

    endpoint = f'**/api/admin/catalog/styles/{style}'
    p.on('request', observed)
    p.route(endpoint, failed_read)
    button(dialog, '保存共用资料')
    expect(dialog.get_by_role('alert')).to_be_visible()
    expect(name).to_have_value('保存前读取失败后保留的草稿')
    expect(name).to_be_enabled()
    save_button = dialog.get_by_role('button', name=re.compile(r'^(?:loading )?保存共用资料$'))
    expect(save_button).to_be_enabled()
    expect(save_button.locator('.anticon-loading')).to_have_count(0)
    expect(dialog.get_by_text('保存结果未知，请先核对', exact=True)).to_have_count(0)
    expect(dialog.get_by_role('button', name='核对已提交回执', exact=True)).to_have_count(0)
    assert writes == [] and receipts == []
    assert query(desktop.app, 'SELECT name FROM product_style WHERE id=%s', (style,))[0]['name'] == '浏览器共用帽子'
    assert query(desktop.app, audit_sql, (str(style),))[0]['n'] == audit_before

    name.fill('读取恢复后明确保存的草稿')
    p.unroute(endpoint, failed_read)
    button(dialog, '保存共用资料')
    confirm = p.get_by_role('dialog', name='确认同步共用商品资料？', exact=True)
    expect(confirm).to_contain_text('将影响1件引用该款式的物品')
    assert writes == []
    button(confirm, '确认同步保存')
    dialog.wait_for(state='hidden')
    assert len(writes) == 1 and receipts == []
    assert query(desktop.app, 'SELECT name FROM product_style WHERE id=%s', (style,))[0]['name'] == '读取恢复后明确保存的草稿'
    assert query(desktop.app, audit_sql, (str(style),))[0]['n'] == audit_before + 1


@pytest.mark.parametrize('committed', [False, True])
def test_style_unknown_write_keeps_receipt_and_original_request(desktop, committed):
    style, _, _, _ = setup(desktop)
    p = desktop.page
    p.goto('http://localhost:5174/catalog', wait_until='networkidle')
    button(p, '维护资料')
    dialog = p.get_by_role('dialog', name='维护款式共用资料', exact=True)
    name = dialog.get_by_label('款式名称', exact=True)
    name.fill('真实写入结果未知时的原始草稿')
    audit_sql = "SELECT COUNT(*) AS n FROM admin_audit WHERE action='catalog.style' AND target_id=%s"
    audit_before = query(desktop.app, audit_sql, (str(style),))[0]['n']
    writes = []

    def observed(request):
        if request.method == 'POST' and request.url.endswith('/api/admin/catalog/actions/style'):
            writes.append(request.post_data_json)

    def lost_write(route):
        if committed:
            assert route.fetch().status == 200
        route.fulfill(status=503, json={
            'status': 'error', 'code': 'service_unavailable', 'message': '隔离模拟提交结果未知',
        })

    endpoint = '**/api/admin/catalog/actions/style'
    p.on('request', observed)
    p.route(endpoint, lost_write)
    button(dialog, '保存共用资料')
    button(p.get_by_role('dialog', name='确认同步共用商品资料？', exact=True), '确认同步保存')
    expect(dialog.get_by_text('保存结果未知，请先核对', exact=True)).to_be_visible()
    expect(name).to_have_value('真实写入结果未知时的原始草稿')
    expect(name).to_be_disabled()
    assert len(writes) == 1
    assert query(desktop.app, audit_sql, (str(style),))[0]['n'] == audit_before + int(committed)
    p.unroute(endpoint, lost_write)
    button(dialog, '核对已提交回执')

    if not committed:
        expect(dialog.get_by_text('服务端尚无已提交回执，可以明确重试原请求。', exact=True)).to_be_visible()
        read_endpoint = f'**/api/admin/catalog/styles/{style}'

        def failed_retry_preflight(route):
            route.fulfill(status=503, json={
                'status': 'error', 'code': 'service_unavailable', 'message': '隔离模拟原请求重试前读取失败',
            })

        p.route(read_endpoint, failed_retry_preflight)
        button(dialog, '明确重试原请求')
        expect(dialog.get_by_text('隔离模拟原请求重试前读取失败', exact=True)).to_be_visible()
        expect(name).to_be_disabled()
        assert len(writes) == 1
        p.unroute(read_endpoint, failed_retry_preflight)
        button(dialog, '明确重试原请求')
        button(p.get_by_role('dialog', name='确认同步共用商品资料？', exact=True), '确认同步保存')

    dialog.wait_for(state='hidden')
    assert len(writes) == (1 if committed else 2)
    assert all(entry == writes[0] for entry in writes)
    assert query(desktop.app, 'SELECT name FROM product_style WHERE id=%s', (style,))[0]['name'] == '真实写入结果未知时的原始草稿'
    assert query(desktop.app, audit_sql, (str(style),))[0]['n'] == audit_before + 1
    if committed:
        p.goto('http://localhost:5174/system?tab=audit&keyword=UI-CAP&action=catalog.style', wait_until='networkidle')
        rows = p.locator('.ant-table-tbody tr').filter(has_text='保存款式')
        expect(rows).to_have_count(audit_before + 1)
        expect(rows.first).to_contain_text('UI-CAP')


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
    expect(p.get_by_label('本件正式序号',exact=True)).to_have_value('1')
    shot(p,'register-identity')
    save_identity_draft(p, '业务自定义号-帽子/甲')
    button(p,'业务自定义号-帽子/甲')
    expect(p.get_by_text('业务自定义号-帽子/甲',exact=True).first).to_be_visible()
    expect(p.get_by_text('#1/9',exact=True).first).to_be_visible()
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
        button(guard,'放弃并离开');page.wait_for_url('**/catalog?tab=issues')
        expect(page.get_by_role('dialog',name='有未保存修改',exact=True)).to_have_count(0)
    finally:context.close()


def test_admin_navigation_and_visual_samples(desktop, tmp_path):
    from uuid import UUID
    from core.account_uid import new_account_identity

    style, issue, item, chips = setup(desktop)
    install(desktop, style, item, chips[0])
    order = api(desktop, 'createOrder', {
        'channel': '模拟店铺', 'external_order_no': 'UI-GOV-ORDER',
        'units': [{'product_name': '模拟棒球帽', 'ordered_spec': 'L黑'}],
    })['id']
    internal_uid, uid = new_account_identity()
    query(desktop.app, 'INSERT INTO user(uid,public_uid,phone) VALUES (%s,%s,%s)',
          (internal_uid, uid, '00000000000'))
    routes = (
        ('overview', '工作台', '最近用户动态'),
        ('overview/activity', '工作台', '用户动态'),
        ('orders', '订单管理', 'UI-GOV-ORDER'),
        (f'orders/{order}', '订单管理', '第 1 件 · 模拟棒球帽'),
        ('items', '数字物品', '数字物品档案'),
        (f'items/{item}', '数字物品', '持有人与权益'),
        ('physical-items', '实体物品', '登记实物'),
        ('catalog', '款式与发行', '共用款式资料'),
        ('catalog?tab=issues', '款式与发行', '发行承诺与核定结果'),
        ('chips', '芯片管理', '芯片档案'),
        (f'chips/{chips[0]}', '芯片管理', '芯片档案'),
        ('system?tab=audit', '系统管理', '操作日志'),
        ('system?tab=settings', '系统管理', '测试数据'),
        ('system?tab=runtime', '系统管理', '数据库'),
        ('users', '用户管理', '账户与持有'),
    )
    p = desktop.page
    out = Path('test-results/admin-governance')
    out.mkdir(parents=True, exist_ok=True)
    width, height = 1920, 1080
    p.set_viewport_size({'width': width, 'height': height})
    for n, (path, heading, landmark) in enumerate(routes, 1):
        p.goto(f'http://localhost:5174/{path}', wait_until='networkidle')
        expect(p.locator('.header-context strong')).to_have_text(heading)
        expect(p.get_by_text(landmark, exact=True).last).to_be_visible()
        assert p.evaluate('document.documentElement.scrollWidth <= innerWidth'), path
        p.screenshot(path=str(out / f'{width}-{n:02d}.png'), animations='disabled')
    uid_button = p.get_by_role('button', name=str(UUID(bytes=uid)), exact=True)
    uid_button.press('Enter')
    card = p.get_by_role('region', name='账户资料')
    expect(card.get_by_text('000****0000', exact=True)).to_be_visible()
    expect(card.get_by_text('未设置', exact=True)).to_be_visible()
    p.screenshot(path=str(out / f'{width}-account.png'), animations='disabled')
    heading = card.get_by_text('账户资料', exact=True).bounding_box()
    close = card.get_by_role('button', name='关闭账户资料').bounding_box()
    phone = card.get_by_text('000****0000', exact=True).bounding_box()
    reveal = card.get_by_role('button', name='查看完整手机号').bounding_box()
    assert heading and close and close['x'] > heading['x'] + 220
    assert phone and reveal
    assert 0 <= reveal['x'] - (phone['x'] + phone['width']) <= 8
    assert abs((phone['y'] + phone['height'] / 2) - (reveal['y'] + reveal['height'] / 2)) <= 2
    card.get_by_role('button', name='关闭账户资料').press('Escape')
    expect(card).to_be_hidden()
    expect(uid_button).to_be_focused()
    uid_button.click()
    button(card, '查看完整手机号')
    number = p.get_by_role('dialog', name='完整手机号', exact=True)
    expect(number.locator('[data-private]')).to_have_text('00000000000')
    expect(card.get_by_text('000****0000', exact=True)).to_be_visible()
    number.get_by_role('button', name=re.compile(r'^关\s*闭$')).last.click()
    assert len(query(desktop.app, "SELECT id FROM admin_audit WHERE action='catalog.viewUserPhone'")) == 1

    forms = (
        ('orders', '新建订单', '新建订单', '保存并打开订单'),
        ('physical-items', '登记实物', '登记实体物品', '登记实物'),
        ('chips', '手工登记芯片', '手工登记芯片', '登记并查看'),
    )
    for n, (path, trigger, title, submit) in enumerate(forms, 1):
        p.goto(f'http://localhost:5174/{path}', wait_until='networkidle')
        button(p, trigger)
        dialog = p.get_by_role('dialog', name=title, exact=True)
        cancel = dialog.get_by_role('button', name=re.compile(r'^取\s*消$'))
        primary = dialog.get_by_role('button', name=submit, exact=True)
        expect(primary).to_be_visible()
        # 遮罩与弹窗内容在不同 DOM 节点，等遮罩完全进入后再保存截图。
        expect(p.locator('.ant-modal-mask:visible')).to_have_css('opacity', '1')
        cancel_box, primary_box = cancel.bounding_box(), primary.bounding_box()
        assert cancel_box and primary_box and cancel_box['x'] < primary_box['x']
        assert abs(cancel_box['y'] - primary_box['y']) < 2
        p.screenshot(path=str(out / f'1920-form-{n}.png'), animations='disabled')
        cancel.click()
        expect(dialog).to_be_hidden()



def test_user_card_keeps_workbench_scroll(desktop):
    from uuid import UUID
    from core.account_uid import new_account_identity

    _, _, item, _ = setup(desktop)
    internal_uid, uid = new_account_identity()
    query(desktop.app, "INSERT INTO user(uid,public_uid,phone) VALUES (%s,%s,%s)",
          (internal_uid, uid, "00000000042"))
    query(desktop.app, """INSERT INTO ownership(item_id,user_id,bind_source,bound_at)
                          VALUES (%s,%s,'user_self',%s)""",
          (item, internal_uid, desktop.app.test_clock[0]))
    p = desktop.page
    p.set_viewport_size({"width": 1920, "height": 1080})
    desktop.navigate("工作台")
    p.reload(wait_until="networkidle")
    trigger = p.get_by_role("button", name=str(UUID(bytes=uid)), exact=True)
    trigger.scroll_into_view_if_needed()
    assert p.evaluate("scrollY") > 0
    y = trigger.bounding_box()["y"]
    trigger.click()
    card = p.get_by_role("region", name="账户资料")
    expect(card.get_by_text("000****0042", exact=True)).to_be_visible()
    close = card.get_by_role("button", name="关闭账户资料")
    expect(close).to_be_focused()
    assert trigger.bounding_box()["y"] == pytest.approx(y, abs=1)
    close.press("Escape")
    expect(card).to_be_hidden()
    expect(trigger).to_be_focused()
    assert trigger.bounding_box()["y"] == pytest.approx(y, abs=1)
    trigger.press("Enter")
    expect(close).to_be_focused()
    assert trigger.bounding_box()["y"] == pytest.approx(y, abs=1)
    close.click()
    expect(card).to_be_hidden()
    expect(trigger).to_be_focused()
    assert trigger.bounding_box()["y"] == pytest.approx(y, abs=1)


def test_list_and_preview_distinguish_failure_from_empty(desktop):
    _, _, item, _ = setup(desktop)
    p = desktop.page
    p.set_viewport_size({'width': 1920, 'height': 1080})
    p.route(re.compile(r'/api/admin/catalog/orders\?'), lambda route: route.fulfill(
        status=503, json={'status': 'error', 'code': 'service_unavailable', 'message': '隔离模拟列表读取失败'}))
    p.goto('http://localhost:5174/orders', wait_until='networkidle')
    expect(p.get_by_text('列表加载失败', exact=True)).to_be_visible()
    expect(p.get_by_text('读取失败，请重试', exact=True)).to_be_visible()
    expect(p.get_by_text('暂无数据', exact=True)).to_have_count(0)
    p.unroute(re.compile(r'/api/admin/catalog/orders\?'))
    button(p, '重试读取')
    expect(p.get_by_text('列表加载失败', exact=True)).to_have_count(0)
    expect(p.locator('.ant-empty-description').get_by_text('暂无数据', exact=True)).to_be_visible()

    endpoint = f'**/api/admin/catalog/items/{item}/h5-preview'
    p.route(endpoint, lambda route: route.fulfill(
        status=503, json={'status': 'error', 'code': 'service_unavailable', 'message': '隔离模拟预览读取失败'}))
    p.goto(f'http://localhost:5174/items/{item}', wait_until='networkidle')
    button(p, '预览手机页')
    preview = p.get_by_role('dialog', name=re.compile(r'^手机页预览'))
    expect(preview.get_by_text('隔离模拟预览读取失败', exact=True)).to_be_visible()
    p.unroute(endpoint)

    def synthetic_images(route):
        response = route.fetch()
        assert response.status == 200
        body = response.json()
        body['data']['image_urls'] = [
            'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=',
            'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=#second',
        ]
        route.fulfill(response=response, json=body)

    p.route(endpoint, synthetic_images)
    button(preview, '重试读取')
    expect(preview.get_by_alt_text('商品图片 1', exact=True)).to_be_visible()
    button(preview, '查看商品图片 2')
    expect(preview.get_by_alt_text('商品图片 2', exact=True)).to_be_visible()
    preview.get_by_text('待认领', exact=True).click()
    button(preview, '查看下一步')
    expect(preview.get_by_text('手机号验证', exact=True)).to_be_visible()
    preview.get_by_text('持有人', exact=True).click()
    expect(preview.get_by_text('本年换新用量', exact=True)).to_be_visible()
    preview.get_by_role('button', name='关闭', exact=True).click()

    button(p, '查看全部')
    expect(p.get_by_text('操作日志', exact=True)).to_be_visible()
    button(p, '重置')
    assert f'item_id={item}' in p.url and 'from=' in p.url
    button(p, 'back')
    expect(p).to_have_url(f'http://localhost:5174/items/{item}')

    p.get_by_role('button', name=re.compile(r'^查看 \d+ 次有效触碰明细$')).click()
    expect(p.get_by_role('button', name='back')).to_be_visible()
    button(p, '重置')
    assert all(f'{field}=' in p.url for field in ('from', 'event', 'scope', 'range', 'as_of', 'item_id'))
    button(p, 'back')
    expect(p).to_have_url(f'http://localhost:5174/items/{item}')



def test_admin_list_errors_and_full_page_forms_share_visible_patterns(desktop):
    setup(desktop)
    p = desktop.page
    p.set_viewport_size({'width': 1920, 'height': 1080})
    out = Path('test-results/admin-governance')
    out.mkdir(parents=True, exist_ok=True)
    for resource, path in (
        ('orders', 'orders'), ('physical-items', 'physical-items'), ('items', 'items'),
        ('styles', 'catalog'), ('issues', 'catalog?tab=issues'), ('chips', 'chips'),
        ('users', 'users'), ('audit', 'system?tab=audit'), ('activity', 'overview/activity'),
    ):
        endpoint = re.compile(rf'/api/admin/catalog/{resource}\?')
        p.route(endpoint, lambda route: route.fulfill(status=503, json={
            'status': 'error', 'code': 'service_unavailable', 'message': '隔离模拟读取失败',
        }))
        p.goto(f'http://localhost:5174/{path}', wait_until='networkidle')
        failure = p.get_by_role('alert').filter(has_text='列表加载失败')
        expect(failure).to_contain_text('隔离模拟读取失败')
        expect(p.get_by_text('暂无数据', exact=True)).to_have_count(0)
        p.screenshot(path=str(out / f'1920-error-{resource}.png'), animations='disabled')
        p.unroute(endpoint)
        button(failure, '重试读取')
        expect(failure).to_have_count(0)
    for name, path, submit in (
        ('style', 'catalog/style/new', '保存共用资料'),
        ('issue', 'catalog/issue/new', '保存发行草案'),
        ('item', 'items/new', '确认安装'),
    ):
        p.goto(f'http://localhost:5174/{path}', wait_until='networkidle')
        primary = p.get_by_role('button', name=submit, exact=True)
        expect(primary).to_be_visible()
        cancel = p.get_by_role('button', name=re.compile(r'^取\s*消$'))
        cancel_box, primary_box = cancel.bounding_box(), primary.bounding_box()
        assert cancel_box and primary_box and cancel_box['x'] < primary_box['x']
        assert abs(cancel_box['y'] - primary_box['y']) < 2 and primary_box['y'] > 1000
        p.screenshot(path=str(out / f'1920-form-{name}.png'), animations='disabled')
