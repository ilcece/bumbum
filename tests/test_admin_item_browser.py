"""Ant Design物品完整流程，真实API/文件/隔离MySQL，故障回执明确合成。"""

from io import BytesIO
import json
import re

from PIL import Image
import pytest

from tests.test_admin_auth import query
from tests.test_admin_browser import browser_gate, desktop

pytestmark = [pytest.mark.auth_database, pytest.mark.browser]


def sample(desktop, *, project='fashion', status='draft'):
    prefix = 'FASH' if project == 'fashion' else 'JEW'
    query(desktop.app,'INSERT INTO item(project_id,item_uid,sku_code,status) VALUES (%s,%s,%s,%s)',(1 if project=='fashion' else 2,prefix+'-2026-920001','原款式',status))
    item = query(desktop.app,'SELECT id FROM item')[0]['id']
    if project=='fashion':
        query(desktop.app,"INSERT INTO fashion_item_profile(item_id,name,description,material,size_chart) VALUES (%s,'原名称','原介绍','棉',JSON_OBJECT('S',80))",(item,))
    else:
        query(desktop.app,"INSERT INTO jewelry_item_profile(item_id,name,meaning) VALUES (%s,'既有饰品','既有寓意')",(item,))
    return item


def open_item(desktop, edit=False):
    desktop.login(); desktop.navigate('物品管理')
    page=desktop.page
    page.get_by_role('button',name='查看详情',exact=True).click()
    page.get_by_role('heading',name='物品详情',exact=True).wait_for()
    page.get_by_text('原名称',exact=True).or_(page.get_by_text('既有饰品',exact=True)).first.wait_for()
    if edit:
        page.get_by_role('button',name='编辑物品',exact=True).click()
        page.get_by_label('款式编号',exact=True).wait_for()
    return page


def png():
    out=BytesIO();Image.new('RGBA',(24,16),(30,120,70,100)).save(out,'PNG');return out.getvalue()


def enable_upload(desktop,tmp_path):
    root=tmp_path/'private-media';root.mkdir(mode=0o700)
    desktop.app.config.update(MEDIA_ROOT=str(root),MEDIA_ENABLED=True,MEDIA_MAX_TOTAL_BYTES=2*1024**3,PUBLIC_ORIGIN='http://127.0.0.1:5175')
    return root


def select_image(page,name='synthetic.png'):
    page.locator('input[type=file]').set_input_files({'name':name,'mimeType':'image/png','buffer':png()})


def test_item_fields_relation_atomic_save_and_noop(desktop):
    from playwright.sync_api import expect
    item=sample(desktop)
    query(desktop.app,"INSERT INTO chip(chip_uid,project_id,item_id,chip_status) VALUES ('04:00:00:00:00:00:71',1,%s,'bound')",(item,))
    chip=query(desktop.app,'SELECT id FROM chip')[0]['id']
    page=open_item(desktop)
    labels=page.locator('.ant-descriptions-item-label').all_text_contents()
    page.get_by_role('link',name='04:00:00:00:00:00:71',exact=True).click()
    expect(page).to_have_url(re.compile(f'/chips/{chip}$'))
    page.get_by_role('button',name='返回来源',exact=True).click()
    page.get_by_role('button',name='编辑物品',exact=True).click()
    page.get_by_label('名称',exact=True).wait_for()
    for label in labels:
        expect(page.locator('.ant-form-item-label').filter(has_text=re.compile('^'+re.escape(label)+'$'))).to_have_count(1)
    assert page.get_by_text('80').count()>0
    writes=[]
    page.on('request',lambda req:writes.append(req.post_data_json) if req.method=='PATCH' and req.url.endswith('/items/'+str(item)) else None)
    page.get_by_label('款式编号',exact=True).fill('新款式')
    page.get_by_label('名称',exact=True).fill('新名称')
    page.get_by_role('button',name='保存修改',exact=True).click()
    expect(page).to_have_url(re.compile(f'/items/{item}$'))
    page.get_by_text('新名称',exact=True).wait_for()
    assert len(writes)==1 and set(writes[0])=={'sku_code','profile'}
    assert json.loads(query(desktop.app,'SELECT size_chart FROM fashion_item_profile')[0]['size_chart'])=={'S':80}
    page.get_by_role('button',name='编辑物品',exact=True).click()
    page.get_by_label('款式编号',exact=True).wait_for()
    page.get_by_role('button',name='保存修改',exact=True).click()
    expect(page).to_have_url(re.compile(f'/items/{item}$'))
    assert len(writes)==1


def test_continuous_create_preserves_query_and_exact_record(desktop):
    from playwright.sync_api import expect
    desktop.login();desktop.navigate('物品管理');page=desktop.page
    page.get_by_label('关键词',exact=True).fill('原筛选无匹配')
    page.get_by_role('button',name=re.compile(r'查\s*询$')).click()
    expect(page).to_have_url(re.compile('keyword='));source=page.url
    page.get_by_role('button',name='创建物品',exact=True).click()
    dialog=page.get_by_role('dialog',name='创建物品草稿',exact=True)
    for number in (920011,920012):
        dialog.get_by_label('物品编号',exact=True).fill('FASH-2026-'+str(number))
        dialog.get_by_label('款式编号',exact=True).fill('可重复款式')
        dialog.get_by_role('button',name='创建并继续',exact=True).evaluate('(button)=>{button.click();button.click()}')
        dialog.get_by_text(re.compile('已取得物品 FASH-2026-'+str(number))).wait_for()
        expect(dialog.get_by_label('物品编号',exact=True)).to_have_value('')
        expect(dialog.get_by_label('款式编号',exact=True)).to_have_value('')
        expect(dialog.locator('.ant-select-content')).to_have_text('服装')
    assert len(query(desktop.app,'SELECT id FROM item'))==2
    target=query(desktop.app,"SELECT id FROM item WHERE item_uid='FASH-2026-920012'")[0]['id']
    dialog.get_by_role('button',name='完善该物品',exact=True).click()
    expect(page).to_have_url(re.compile(f'/items/{target}/edit$'))
    page.get_by_label('款式编号',exact=True).wait_for()
    page.get_by_role('dialog',name=re.compile('编辑物品')).get_by_role('button',name='返回来源',exact=True).click()
    expect(page).to_have_url(source)
    expect(page.get_by_label('关键词',exact=True)).to_have_value('原筛选无匹配')
    expect(page.get_by_role('dialog',name='创建物品草稿',exact=True)).to_have_count(0)


def test_upload_pending_save_read_remove_retire(desktop,tmp_path):
    from playwright.sync_api import expect
    item=sample(desktop);root=enable_upload(desktop,tmp_path)
    page=open_item(desktop,True);select_image(page)
    expect(page.locator('.ant-upload-list-item-done')).to_have_count(1)
    page.locator('.ant-upload-list-item-name').click()
    expect(page.locator('.ant-image-preview')).to_be_visible()
    expect(page.locator('.ant-image-preview')).to_have_css('opacity','1')
    page.keyboard.press('Escape')
    expect(page.locator('.ant-image-preview')).not_to_be_visible()
    expect(page.get_by_role('dialog',name=re.compile('编辑物品'))).to_be_visible()
    asset=query(desktop.app,'SELECT * FROM media_asset')[0]
    assert asset['state']=='pending' and not json.loads(query(desktop.app,'SELECT image_urls FROM fashion_item_profile')[0]['image_urls'] or '[]')
    page.get_by_role('button',name='保存修改',exact=True).click()
    expect(page).to_have_url(re.compile(f'/items/{item}$'))
    page.get_by_alt_text('物品图片1',exact=True).wait_for()
    assert query(desktop.app,'SELECT state FROM media_asset')[0]['state']=='attached'
    page.get_by_role('button',name='编辑物品',exact=True).click()
    page.locator('.ant-upload-list-item .anticon-delete').click()
    expect(page.locator('.ant-upload-list-item')).to_have_count(0)
    page.get_by_role('button',name='保存修改',exact=True).click()
    expect(page).to_have_url(re.compile(f'/items/{item}$'))
    assert query(desktop.app,'SELECT state FROM media_asset')[0]['state']=='retired'
    assert (root/(asset['asset_id']+'.webp')).exists()


def test_upload_lost_response_queries_status_without_replay(desktop,tmp_path):
    from playwright.sync_api import expect
    item=sample(desktop);enable_upload(desktop,tmp_path);page=open_item(desktop,True)
    writes=[]
    def lose(route):
        writes.append(1);response=route.fetch();assert response.status==200
        route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','code':'service_unavailable','message':'合成上传回执丢失'}))
    page.route(f'**/api/admin/items/{item}/images',lose)
    select_image(page)
    page.get_by_text('上传结果尚未确认',exact=True).wait_for()
    expect(page.get_by_role('button',name='保存修改',exact=True)).to_be_disabled()
    page.get_by_role('button',name='核对上传结果',exact=True).click()
    expect(page.locator('.ant-upload-list-item-done')).to_have_count(1)
    assert writes==[1]
    page.get_by_role('button',name='保存修改',exact=True).click()
    expect(page).to_have_url(re.compile(f'/items/{item}$'))
    assert query(desktop.app,'SELECT state FROM media_asset')[0]['state']=='attached'


def test_save_lost_response_reads_id_and_keeps_input(desktop):
    from playwright.sync_api import expect
    item=sample(desktop);page=open_item(desktop,True);writes=[]
    def lose(route):
        if route.request.method!='PATCH':route.continue_();return
        writes.append(1);response=route.fetch();assert response.status==200
        route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','code':'service_unavailable','message':'合成资料回执丢失'}))
    page.route(f'**/api/admin/items/{item}',lose)
    page.get_by_label('名称',exact=True).fill('回执丢失但已保存')
    page.get_by_role('button',name='保存修改',exact=True).click()
    page.get_by_text('保存结果尚未确认，请先按物品ID核对；不会自动重发。',exact=True).wait_for()
    expect(page.get_by_role('button',name='保存修改',exact=True)).to_be_disabled()
    page.get_by_role('button',name='核对保存结果',exact=True).click()
    page.get_by_text('已确认服务器当前资料与本次提交一致。',exact=True).wait_for()
    expect(page.get_by_label('名称',exact=True)).to_have_value('回执丢失但已保存')
    assert writes==[1]


def test_unsaved_three_choices_and_separate_status_confirmation(desktop):
    from playwright.sync_api import expect
    item=sample(desktop);page=open_item(desktop,True)
    page.get_by_label('名称',exact=True).fill('离开前保存')
    desktop.navigate('芯片管理')
    guard=page.get_by_role('dialog',name='有未保存修改',exact=True)
    guard.get_by_role('button',name=re.compile(r'^取\s*消$')).click()
    expect(page.get_by_label('名称',exact=True)).to_have_value('离开前保存')
    desktop.navigate('芯片管理');guard.get_by_role('button',name='保存后继续',exact=True).click()
    expect(page).to_have_url(re.compile('/chips$'))
    assert query(desktop.app,'SELECT name FROM fashion_item_profile')[0]['name']=='离开前保存'
    desktop.navigate('物品管理');page.get_by_role('button',name='查看详情',exact=True).click()
    page.get_by_role('button',name='编辑物品',exact=True).click()
    page.get_by_label('名称',exact=True).fill('应放弃的名称')
    page.get_by_role('button',name='启用物品',exact=True).click()
    guard.get_by_role('button',name='放弃继续',exact=True).click()
    confirm=page.get_by_role('dialog',name='启用此物品？',exact=True)
    assert query(desktop.app,'SELECT status FROM item WHERE id=%s',(item,))[0]['status']=='draft'
    confirm.get_by_role('button',name='确认启用',exact=True).click()
    page.get_by_role('status').filter(has_text='物品已启用。').wait_for()
    expect(page.get_by_label('名称',exact=True)).to_have_value('离开前保存')
    page.get_by_role('button',name='停用物品',exact=True).click()
    page.get_by_role('dialog',name='停用此物品？',exact=True).get_by_role('button',name='确认停用',exact=True).click()
    page.get_by_role('status').filter(has_text='物品已停用').wait_for()
    assert query(desktop.app,'SELECT status FROM item WHERE id=%s',(item,))[0]['status']=='disabled'


def test_cancel_upload_ignores_late_success_and_never_attaches(desktop,tmp_path):
    from playwright.sync_api import expect
    item=sample(desktop);enable_upload(desktop,tmp_path);page=open_item(desktop,True);held=[]
    def delay(route):
        response=route.fetch();assert response.status==200
        held.append((route,response))
        page.evaluate('window.__testUploadFinished=true')
    page.route(f'**/api/admin/items/{item}/images',delay)
    page.get_by_label('款式编号',exact=True).fill('取消上传后仅改款式')
    select_image(page)
    expect(page.locator('.ant-upload-list-item-uploading')).to_have_count(1)
    page.wait_for_function('window.__testUploadFinished===true')
    expect(page.get_by_role('button',name='保存修改',exact=True)).to_be_disabled()
    page.locator('.ant-upload-list-item .anticon-delete').click()
    expect(page.locator('.ant-upload-list-item')).to_have_count(0)
    assert held
    from playwright.sync_api import Error
    try:held[0][0].fulfill(response=held[0][1])
    except Error:pass
    expect(page.locator('.ant-upload-list-item')).to_have_count(0)
    page.get_by_role('button',name='保存修改',exact=True).click()
    expect(page).to_have_url(re.compile(f'/items/{item}$'))
    assert query(desktop.app,'SELECT state FROM media_asset')[0]['state']=='pending'
    assert not json.loads(query(desktop.app,'SELECT image_urls FROM fashion_item_profile')[0]['image_urls'] or '[]')


def test_upload_csrf_explicit_retry_and_invalid_type(desktop,tmp_path):
    from playwright.sync_api import expect
    item=sample(desktop);enable_upload(desktop,tmp_path);page=open_item(desktop,True);writes=[]
    def deny(route):
        writes.append(1);route.fulfill(status=403,content_type='application/json',body=json.dumps({'status':'error','code':'csrf_failed','message':'合成口令失效'}))
    page.route(f'**/api/admin/items/{item}/images',deny)
    page.locator('input[type=file]').set_input_files({'name':'bad.svg','mimeType':'image/svg+xml','buffer':b'<svg/>'})
    page.get_by_text('请选择不超过8MiB的静态JPEG、PNG或WebP；实际格式由服务端校验。',exact=True).wait_for()
    assert not writes
    select_image(page)
    page.get_by_text('登录状态已更新，请明确重试本张上传；未自动重发。',exact=True).wait_for()
    assert writes==[1] and not query(desktop.app,'SELECT * FROM media_asset')
    page.unroute(f'**/api/admin/items/{item}/images')
    page.get_by_role('button',name='重试上传',exact=True).click()
    expect(page.locator('.ant-upload-list-item-done')).to_have_count(1)
    assert len(query(desktop.app,'SELECT * FROM media_asset'))==1
    page.get_by_label('名称',exact=True).fill('上传后丢弃')
    page.get_by_role('button',name='返回来源',exact=True).click()
    page.get_by_role('dialog',name='有未保存修改',exact=True).get_by_role('button',name='放弃继续',exact=True).click()
    assert query(desktop.app,'SELECT name FROM fashion_item_profile')[0]['name']=='原名称'
    assert query(desktop.app,'SELECT state FROM media_asset')[0]['state']=='pending'


@pytest.mark.parametrize('archived',[False,True])
def test_jewelry_and_archived_keep_readonly_fields(desktop,archived):
    from playwright.sync_api import expect
    item=sample(desktop,project='jewelry',status='archived' if archived else 'draft')
    page=open_item(desktop)
    labels=page.locator('.ant-descriptions-item-label').all_text_contents()
    if archived:
        assert page.get_by_role('button',name='编辑物品',exact=True).count()==0
        page.goto(f'http://localhost:5174/items/{item}/edit',wait_until='networkidle')
    else:
        page.get_by_role('button',name='编辑物品',exact=True).click()
    page.get_by_text('既有寓意',exact=True).wait_for()
    for label in labels:
        expect(page.locator('.ant-form-item-label').filter(has_text=re.compile('^'+re.escape(label)+'$'))).to_have_count(1)
    expect(page.locator('input[type=file]')).to_have_count(0)
    expect(page.get_by_role('textbox')).to_have_count(0 if archived else 1)
    if not archived:
        page.get_by_label('款式编号',exact=True).fill('饰品新款式')
        page.get_by_role('button',name='保存修改',exact=True).click()
        expect(page).to_have_url(re.compile(f'/items/{item}$'))
        assert query(desktop.app,'SELECT meaning FROM jewelry_item_profile')[0]['meaning']=='既有寓意'
    else:expect(page.get_by_role('button',name='保存修改',exact=True)).to_have_count(0)


def test_new_item_sku_only_and_profile_name_validation(desktop):
    from playwright.sync_api import expect
    query(desktop.app,"INSERT INTO item(project_id,item_uid) VALUES (1,'FASH-2026-920021')")
    desktop.login();desktop.navigate('物品管理');page=desktop.page
    page.get_by_role('button',name='查看详情',exact=True).click()
    page.get_by_role('button',name='编辑物品',exact=True).click()
    page.get_by_label('款式编号',exact=True).fill('仅维护款式')
    page.get_by_role('button',name='保存修改',exact=True).click()
    page.get_by_role('heading',name='物品详情',exact=True).wait_for()
    assert not query(desktop.app,'SELECT * FROM fashion_item_profile')
    page.get_by_role('button',name='编辑物品',exact=True).click()
    page.get_by_label('介绍',exact=True).fill('未填写名称的资料')
    page.get_by_role('button',name='保存修改',exact=True).click()
    page.get_by_text('修改服装资料时须填写名称。',exact=True).wait_for()
    assert not query(desktop.app,'SELECT * FROM fashion_item_profile')


def test_create_lost_response_and_duplicate_never_overwrite(desktop):
    from playwright.sync_api import expect
    desktop.login();desktop.navigate('物品管理');page=desktop.page;writes=[]
    def lose(route):
        if route.request.method!='POST':route.continue_();return
        writes.append(1);response=route.fetch();assert response.status==200
        route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','code':'service_unavailable','message':'合成创建回执丢失'}))
    page.route('**/api/admin/items',lose)
    page.get_by_role('button',name='创建物品',exact=True).click()
    dialog=page.get_by_role('dialog',name='创建物品草稿',exact=True)
    dialog.get_by_label('物品编号',exact=True).fill('FASH-2026-920031')
    dialog.get_by_label('款式编号',exact=True).fill('原输入款式')
    dialog.get_by_role('button',name='创建并继续',exact=True).click()
    page.get_by_text('创建结果尚未确认，请先按本次完整物品编号查询；不会自动重发。',exact=True).wait_for()
    expect(dialog.get_by_role('button',name='创建并继续',exact=True)).to_be_disabled()
    dialog.get_by_role('button',name='按本次编号核对结果',exact=True).click()
    dialog.get_by_text(re.compile('已取得物品 FASH-2026-920031')).wait_for()
    assert writes==[1]
    page.unroute('**/api/admin/items')
    dialog.get_by_label('物品编号',exact=True).fill('FASH-2026-920031')
    dialog.get_by_label('款式编号',exact=True).fill('不能覆盖款式')
    dialog.get_by_role('button',name='创建并继续',exact=True).click()
    dialog.get_by_role('alert').filter(has_text='已存在').wait_for()
    assert query(desktop.app,'SELECT sku_code FROM item')[0]['sku_code']=='原输入款式'


def test_item_query_advanced_date_page_return_and_reset(desktop):
    from playwright.sync_api import expect
    for number in range(25):
        query(desktop.app,"INSERT INTO item(project_id,item_uid,sku_code,created_at) VALUES (1,%s,'范围款式','2026-11-02 16:00:00')",('FASH-2026-'+str(921000+number),))
    query(desktop.app,"INSERT INTO item(project_id,item_uid,sku_code,created_at) VALUES (1,'FASH-2026-929999','不匹配款式','2026-10-01 00:00:00')")
    desktop.login();desktop.navigate('物品管理');page=desktop.page
    page.get_by_label('关键词',exact=True).fill('范围款式')
    page.get_by_text('展开',exact=True).click()
    dates=page.locator('.ant-form-item').filter(has_text='创建日期（北京时间）').locator('.ant-picker-range input')
    dates.nth(0).fill('2026-11-03');dates.nth(0).press('Tab');dates.nth(1).fill('2026-11-03');dates.nth(1).press('Enter')
    page.get_by_role('button',name=re.compile(r'查\s*询$')).click()
    expect(page).to_have_url(re.compile('created_from=2026-11-03'))
    expect(page.get_by_text('命中：款式编号',exact=True)).to_have_count(20)
    expect(page.locator('.ant-table-tbody .ant-table-row')).to_have_count(20)
    page.locator('.ant-pagination-next button').click()
    expect(page.locator('.ant-table-tbody .ant-table-row')).to_have_count(5)
    source=page.url
    page.get_by_role('button',name='查看详情',exact=True).first.click()
    page.get_by_role('button',name='返回来源',exact=True).click()
    expect(page).to_have_url(source)
    expect(page.locator('.ant-table-tbody .ant-table-row')).to_have_count(5)
    page.reload(wait_until='networkidle');expect(page.get_by_label('关键词',exact=True)).to_have_value('范围款式')
    page.get_by_role('button',name=re.compile(r'重\s*置$')).click()
    expect(page.get_by_label('关键词',exact=True)).to_have_value('')


def test_twenty_existing_images_limit_and_desktop_layout(desktop,tmp_path):
    from playwright.sync_api import expect
    item=sample(desktop);enable_upload(desktop,tmp_path)
    urls=['https://images.example.test/'+str(number)+'.png' for number in range(20)]
    query(desktop.app,'UPDATE fashion_item_profile SET image_urls=%s WHERE item_id=%s',(json.dumps(urls),item))
    page=desktop.page;page.route('https://images.example.test/**',lambda route:route.fulfill(status=200,content_type='image/png',body=png()))
    page=open_item(desktop,True);writes=[]
    page.on('request',lambda req:writes.append(1) if req.method=='POST' and req.url.endswith('/images') else None)
    expect(page.locator('.ant-upload-list-item-done')).to_have_count(20)
    expect(page.get_by_role('button',name='选择图片上传',exact=True)).to_have_count(0)
    for width,height in [(1280,720),(1440,900)]:
        page.set_viewport_size({'width':width,'height':height})
        page.get_by_role('button',name='保存修改',exact=True).scroll_into_view_if_needed()
        expect(page.get_by_role('button',name='保存修改',exact=True)).to_be_in_viewport()
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        if width==1440:
            import tempfile
            from pathlib import Path
            folder=Path(tempfile.mkdtemp(prefix='item-preview-',dir=Path(__file__).resolve().parents[1]/'.local-run'))
            page.screenshot(path=str(folder/'edit.png'),full_page=True)
            (Path(__file__).resolve().parents[1]/'.local-run/item-preview-path').write_text(str(folder/'edit.png'))
    assert not writes
    page.locator('.ant-upload-list-item .anticon-delete').first.click()
    expect(page.locator('.ant-upload-list-item')).to_have_count(19)
    select_image(page)
    expect(page.locator('.ant-upload-list-item-done')).to_have_count(20)
    assert len(writes)==1


def test_save_csrf_preserves_draft_then_manual_retry_and_upload_401_hides(desktop,tmp_path):
    from playwright.sync_api import expect
    item=sample(desktop);enable_upload(desktop,tmp_path);page=open_item(desktop,True);writes=[]
    def denied(route):
        if route.request.method!='PATCH':route.continue_();return
        writes.append(1);route.fulfill(status=403,content_type='application/json',body=json.dumps({'status':'error','code':'csrf_failed','message':'合成保存口令失效'}))
    page.route(f'**/api/admin/items/{item}',denied)
    page.get_by_label('名称',exact=True).fill('口令更新保留输入')
    page.get_by_role('button',name='保存修改',exact=True).click()
    page.get_by_text('登录状态已更新，输入已保留，请再次明确提交；未自动重发。',exact=True).wait_for()
    expect(page.get_by_label('名称',exact=True)).to_have_value('口令更新保留输入')
    assert writes==[1] and query(desktop.app,'SELECT name FROM fashion_item_profile')[0]['name']=='原名称'
    page.unroute(f'**/api/admin/items/{item}')
    page.get_by_role('button',name='保存修改',exact=True).click()
    expect(page).to_have_url(re.compile(f'/items/{item}$'))
    page.get_by_role('button',name='编辑物品',exact=True).click()
    page.get_by_label('名称',exact=True).wait_for()
    page.route(f'**/api/admin/items/{item}/images',lambda route:route.fulfill(status=401,content_type='application/json',body=json.dumps({'status':'error','code':'unauthorized','message':'合成会话失效'})))
    select_image(page)
    page.get_by_role('button',name=re.compile(r'^登\s*录$')).wait_for()
    expect(page.get_by_role('heading',name='编辑物品',exact=True)).to_have_count(0)
    assert not query(desktop.app,'SELECT * FROM media_asset')


def test_late_item_read_never_overwrites_other_record(desktop):
    from playwright.sync_api import expect
    item=sample(desktop)
    query(desktop.app,"INSERT INTO item(project_id,item_uid) VALUES (1,'FASH-2026-920099')")
    other=query(desktop.app,"SELECT id FROM item WHERE item_uid='FASH-2026-920099'")[0]['id']
    held=[];page=desktop.page
    def delay(route):
        result=route.fetch();held.append((route,result));page.evaluate('window.__testItemReadHeld=true')
    page.route(f'**/api/admin/items/{item}',delay)
    desktop.login();desktop.navigate('物品管理')
    page.get_by_role('row').filter(has_text='FASH-2026-920001').get_by_role('button',name='查看详情',exact=True).click()
    page.wait_for_function('window.__testItemReadHeld===true')
    desktop.navigate('物品管理')
    page.get_by_role('row').filter(has_text='FASH-2026-920099').get_by_role('button',name='查看详情',exact=True).click()
    expect(page).to_have_url(re.compile(f'/items/{other}$'))
    page.get_by_text('此物品尚未填写资料；可单独维护款式编号。',exact=True).wait_for()
    from playwright.sync_api import Error
    try:held[0][0].fulfill(response=held[0][1])
    except Error:pass
    expect(page.get_by_role('dialog',name=re.compile('物品详情')).get_by_text('原名称',exact=True)).to_have_count(0)
    expect(page).to_have_url(re.compile(f'/items/{other}$'))


def test_item_list_return_restores_scroll(desktop):
    from playwright.sync_api import expect
    for number in range(25):
        query(desktop.app,"INSERT INTO item(project_id,item_uid) VALUES (1,%s)",('FASH-2026-'+str(922000+number),))
    desktop.login();desktop.navigate('物品管理');page=desktop.page
    expect(page.locator('.ant-table-tbody .ant-table-row')).to_have_count(20)
    target=page.get_by_role('button',name='查看详情',exact=True).last
    target.scroll_into_view_if_needed();position=page.evaluate('window.scrollY')
    assert position>300
    target.click();page.get_by_role('heading',name='物品详情',exact=True).wait_for()
    page.get_by_role('button',name='返回来源',exact=True).click()
    expect(page.locator('.ant-table-tbody .ant-table-row')).to_have_count(20)
    page.wait_for_function('(expected)=>Math.abs(window.scrollY-expected)<50',arg=position)


def test_jewelry_create_changes_project_and_retains_selection(desktop):
    from playwright.sync_api import expect
    desktop.login();desktop.navigate('物品管理');page=desktop.page
    page.get_by_role('button',name='创建物品',exact=True).click()
    dialog=page.get_by_role('dialog',name='创建物品草稿',exact=True)
    dialog.locator('.ant-select-content').click()
    page.locator('.ant-select-item-option-content').filter(has_text=re.compile('^饰品$')).click()
    dialog.get_by_label('物品编号',exact=True).fill('FASH-2026-923001')
    dialog.get_by_role('button',name='创建并继续',exact=True).click()
    dialog.get_by_text('请输入JEW-YYYY-NNNNNN格式的半角大写编号。',exact=True).wait_for()
    assert not query(desktop.app,'SELECT * FROM item')
    for number in (923001,923002):
        dialog.get_by_label('物品编号',exact=True).fill('JEW-2026-'+str(number))
        dialog.get_by_role('button',name='创建并继续',exact=True).click()
        dialog.get_by_text(re.compile('已取得物品 JEW-2026-'+str(number))).wait_for()
        expect(dialog.locator('.ant-select-content')).to_have_text('饰品')
        expect(dialog.get_by_label('物品编号',exact=True)).to_have_value('')
    assert len(query(desktop.app,'SELECT * FROM item WHERE project_id=2'))==2


def test_modal_close_keeps_or_saves_real_input(desktop):
    from playwright.sync_api import expect
    item=sample(desktop);page=open_item(desktop,True)
    editor=page.get_by_role('dialog',name=re.compile('编辑物品'))
    page.get_by_label('名称',exact=True).fill('关闭前的输入')
    editor.get_by_role('button',name=re.compile(r'^取\s*消$')).click()
    guard=page.get_by_role('dialog',name='有未保存修改',exact=True)
    guard.get_by_role('button',name=re.compile(r'^取\s*消$')).click()
    expect(page.get_by_label('名称',exact=True)).to_have_value('关闭前的输入')
    editor.get_by_role('button',name=re.compile(r'^取\s*消$')).click()
    guard.get_by_role('button',name='保存后继续',exact=True).click()
    expect(page).to_have_url(re.compile('/items$'))
    assert query(desktop.app,'SELECT name FROM fashion_item_profile WHERE item_id=%s',(item,))[0]['name']=='关闭前的输入'
    page.get_by_role('button',name='查看详情',exact=True).click();page.get_by_role('button',name='编辑物品',exact=True).click()
    page.get_by_label('名称',exact=True).fill('要丢弃的输入')
    editor.get_by_role('button',name='关闭',exact=True).click()
    guard.get_by_role('button',name='放弃继续',exact=True).click()
    expect(page).to_have_url(re.compile('/items$'))
    assert query(desktop.app,'SELECT name FROM fashion_item_profile WHERE item_id=%s',(item,))[0]['name']=='关闭前的输入'


def test_disabled_upload_is_known_failure_and_never_written(desktop):
    from playwright.sync_api import expect
    sample(desktop);desktop.app.config['MEDIA_ENABLED']=False
    page=open_item(desktop,True)
    select_image(page)
    expect(page.get_by_role('alert')).to_contain_text('图片尚未上传成功')
    expect(page.get_by_role('alert')).to_contain_text('图片上传未启用。')
    expect(page.get_by_role('button',name='核对上传结果',exact=True)).to_have_count(0)
    assert not query(desktop.app,'SELECT asset_id FROM media_asset')
