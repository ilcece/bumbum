"""手机资料页用合成卡读数、独立数据库和可控浏览器时钟验收。"""

from datetime import timedelta
import json
from urllib.parse import urlencode

import pytest

from tests.browser_support import browser_fixture
from tests.test_admin_browser import browser_gate
from tests.test_admin_auth import query
from tests.test_admin_chips import logged_in
from tests.test_chip_binding import inventory
from tests.test_chip_keys import keyed, reading
from tests.test_tap_verification import ready, counts

pytestmark=[pytest.mark.auth_database,pytest.mark.browser]


def expect(locator):
    """可选浏览器依赖仅在实际运行时加载。"""
    from playwright.sync_api import expect as check
    return check(locator)


@pytest.fixture
def phone(request,auth_app,ready,tmp_path):
    yield from browser_fixture(request,auth_app,None,tmp_path,frontend_name='user',clear_items=False)


def open_card(phone,ready,counter=9):
    phone.page.route('https://example.com/**',lambda route:route.abort())
    payload=reading(ready[1],ready[0][1]['chip_uid'],counter)
    phone.page.goto('http://127.0.0.1:5175/tap?'+urlencode(payload))
    expect(phone.page.get_by_role('heading',name='测试外套',exact=True)).to_be_visible()
    return phone.page


def test_touch_refresh_after_five_minutes_latest_state_and_no_extra_tap(phone,ready,tmp_path):
    page=open_card(phone,ready)
    assert page.url.endswith('/tap/items/'+query(phone.app,'SELECT public_id AS ref FROM item')[0]['ref'])
    assert counts(phone.app)==(1,2)
    assert page.evaluate('Object.keys(localStorage).length+Object.keys(sessionStorage).length')==0
    assert 'bumbum_item_view' not in page.evaluate('document.cookie')
    assert page.get_by_role('button',name='更新资料',exact=True).count()==0
    phone.app.test_clock[0]+=timedelta(minutes=6)
    query(phone.app,"UPDATE fashion_item_profile SET name='刷新后的外套',description='第一段\\n第二段'")
    page.reload()
    expect(page.get_by_role('heading',name='刷新后的外套',exact=True)).to_be_visible()
    assert counts(phone.app)==(1,2)
    expect(page.get_by_text('图片暂不可用',exact=True)).to_be_visible()
    page.screenshot(path=str(tmp_path/'mobile-profile.png'),full_page=True)
    query(phone.app,"UPDATE item SET status='disabled'")
    page.reload()
    expect(page.get_by_role('heading',name='该物品当前暂不可查看',exact=True)).to_be_visible()
    assert page.get_by_role('heading',name='刷新后的外套',exact=True).count()==0
    assert counts(phone.app)==(1,2)


def test_frontground_poll_hidden_pause_return_and_failure_recovery(phone,ready):
    page=phone.page
    page.clock.install()
    open_card(phone,ready)
    requests=[]
    page.on('request',lambda request:requests.append(1) if '/view' in request.url else None)
    query(phone.app,"UPDATE fashion_item_profile SET name='自动更新外套'")
    page.clock.fast_forward(61000)
    expect(page.get_by_role('heading',name='自动更新外套',exact=True)).to_be_visible()
    assert len(requests)==1 and counts(phone.app)==(1,2)
    page.evaluate("Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>window.testHidden?'hidden':'visible'});window.testHidden=true;document.dispatchEvent(new Event('visibilitychange'))")
    page.clock.fast_forward(180000)
    assert len(requests)==1
    query(phone.app,"UPDATE fashion_item_profile SET name='返回后最新外套'")
    page.evaluate("window.testHidden=false;document.dispatchEvent(new Event('visibilitychange'));window.dispatchEvent(new Event('pageshow'))")
    expect(page.get_by_role('heading',name='返回后最新外套',exact=True)).to_be_visible()
    assert len(requests)==2
    page.route('**/api/tap/items/*/view',lambda route:route.fulfill(status=503,content_type='application/json',body=json.dumps({'status':'error','code':'service_unavailable','message':'合成读取失败'})))
    page.clock.fast_forward(61000)
    expect(page.get_by_text('资料更新失败，当前显示上次内容',exact=True)).to_be_visible()
    expect(page.get_by_role('heading',name='返回后最新外套',exact=True)).to_be_visible()
    page.unroute('**/api/tap/items/*/view')
    query(phone.app,"UPDATE fashion_item_profile SET name='恢复后外套'")
    page.get_by_role('button',name='重试更新',exact=True).click()
    expect(page.get_by_role('heading',name='恢复后外套',exact=True)).to_be_visible()
    assert page.get_by_role('button',name='重试更新',exact=True).count()==0
    assert counts(phone.app)==(1,2)


def test_old_reading_and_missing_cookie_never_fall_back_to_prior_profile(phone,ready):
    page=open_card(phone,ready)
    payload=reading(ready[1],ready[0][1]['chip_uid'],9)
    page.goto('http://127.0.0.1:5175/tap?'+urlencode(payload))
    expect(page.get_by_role('heading',name='这次链接已使用',exact=True)).to_be_visible()
    assert page.get_by_role('heading',name='测试外套',exact=True).count()==0
    assert counts(phone.app)==(1,2)
    page.context.clear_cookies()
    item=query(phone.app,'SELECT item_id FROM chip')[0]['item_id']
    page.goto(f'http://127.0.0.1:5175/tap/items/{item}')
    expect(page.get_by_role('heading',name='本次查看资格不可用',exact=True)).to_be_visible()


def test_rate_limit_wait_is_not_bypassed_by_online_or_visibility(phone,ready):
    page=phone.page
    page.clock.install()
    open_card(phone,ready)
    attempts=[]
    def limited(route):
        attempts.append(1)
        route.fulfill(status=429,headers={'Retry-After':'180'},content_type='application/json',body=json.dumps({'status':'error','code':'rate_limited','message':'等待'}))
    page.route('**/api/tap/items/*/view',limited)
    page.clock.fast_forward(61000)
    expect(page.get_by_role('button',name='重试更新',exact=True)).to_be_visible()
    assert len(attempts)==1
    page.clock.fast_forward(60000)
    page.evaluate("window.dispatchEvent(new Event('online'));document.dispatchEvent(new Event('visibilitychange'))")
    assert page.get_by_role('button',name='重试更新',exact=True).is_disabled()
    assert len(attempts)==1
    page.clock.fast_forward(121000)
    expect(page.get_by_role('button',name='重试更新',exact=True)).to_be_visible()
    assert len(attempts)==2 and counts(phone.app)==(1,2)


def test_first_offline_read_does_not_claim_to_show_previous_content(phone,ready):
    page=open_card(phone,ready)
    page.add_init_script("Object.defineProperty(navigator,'onLine',{get:()=>false})")
    page.reload()
    expect(page.get_by_text('暂时无法读取最新资料',exact=True)).to_be_visible()
    expect(page.get_by_text('网络已断开，请检查连接。',exact=True)).to_be_visible()
    expect(page.get_by_text('当前显示上次内容',exact=False)).to_have_count(0)


def test_unknown_claim_result_can_be_checked_again_without_resubmitting(phone,ready):
    page=phone.page
    item_id=query(phone.app,'SELECT public_id AS ref FROM item')[0]['ref']
    attempts=[]
    def verify(route):
        response=route.fetch()
        result=response.json()
        result['data']['claim_state']='available'
        route.fulfill(response=response,json=result)
    def check(route):
        attempts.append(route.request.method)
        if len(attempts)==1:
            route.fulfill(status=503,json={'status':'error','code':'service_unavailable','message':'暂时无法查询。'})
        else:
            route.fulfill(json={'status':'ok','data':{'state':'mine'}})
    page.route('**/api/public/tap/verify',verify)
    page.route('**/api/public/account/session',lambda route:route.fulfill(json={
        'status':'ok','data':{'account':{'uid':'00000000-0000-4000-8000-000000000001','phone':'138****0000'}},
    }))
    submissions=[]
    def submit(route):
        submissions.append(route.request.method)
        route.fulfill(status=503,json={'status':'error','code':'service_unavailable','message':'提交结果未知。'})
    page.route(f'**/api/public/items/{item_id}/claim',submit)
    page.route(f'**/api/public/items/{item_id}/claim-status',check)
    open_card(phone,ready)
    page.get_by_role('button',name='认领这件物品',exact=True).click()
    page.get_by_label('交付认领码',exact=True).fill('0123456789ABCDEF')
    page.get_by_role('button',name='核对认领信息',exact=True).click()
    expect(page.get_by_role('heading',name='确认认领',exact=True)).to_be_visible()
    assert submissions==[]
    page.get_by_role('button',name='返回输入认领码').click()
    expect(page.get_by_label('交付认领码',exact=True)).to_have_value('0123456789ABCDEF')
    page.get_by_role('button',name='核对认领信息',exact=True).click()
    page.get_by_role('button',name='确认认领',exact=True).click()
    page.get_by_role('button',name='再次核对认领结果',exact=True).click()
    expect(page.get_by_role('link',name='查看我的物品',exact=True)).to_be_visible()
    assert attempts==['GET','GET'] and submissions==['POST']


def test_gallery_fullscreen_and_poll_preserves_scroll(phone,ready,admin_account,tmp_path):
    from hashlib import sha256
    from io import BytesIO
    from uuid import uuid4
    from PIL import Image

    page=phone.page
    page.clock.install()
    item_id=query(phone.app,'SELECT item_id FROM chip')[0]['item_id']
    query(phone.app,"""INSERT INTO product_style(project_id,code,name,description,material,specs,image_urls)
        SELECT project_id,'TEST-GALLERY','测试外套',%s,'棉',JSON_ARRAY(),JSON_ARRAY() FROM item WHERE id=%s""",
        ('很长的服装介绍\n'*120,item_id))
    style_id=query(phone.app,"SELECT id FROM product_style WHERE code='TEST-GALLERY'")[0]['id']
    query(phone.app,"INSERT INTO product_issue(style_id,name,mode,description,rights) VALUES (%s,'测试发行','unlimited','',JSON_ARRAY())",(style_id,))
    issue_id=query(phone.app,'SELECT id FROM product_issue WHERE style_id=%s',(style_id,))[0]['id']
    query(phone.app,'INSERT INTO digital_item(item_id,issue_id) VALUES (%s,%s)',(item_id,issue_id))
    assets=[]
    for size,color in (((36,24),'white'),((24,36),'blue')):
        image=BytesIO()
        Image.new('RGB',size,color).save(image,format='WEBP')
        content=image.getvalue()
        asset=uuid4().hex
        query(phone.app,'INSERT INTO style_image(asset_id,style_id,created_by,source_sha256,content) VALUES (%s,%s,%s,%s,%s)',
              (asset,style_id,admin_account['id'],sha256(content).hexdigest(),content))
        assets.append(asset)
    query(phone.app,'UPDATE product_style SET image_urls=%s WHERE id=%s',
          (json.dumps([f'/api/admin/catalog/styles/{style_id}/images/{asset}' for asset in assets]),style_id))
    public_id=query(phone.app,'SELECT public_id FROM item WHERE id=%s',(item_id,))[0]['public_id']
    urls=[f'http://127.0.0.1:5175/api/tap/items/{public_id}/style-images/{asset}' for asset in assets]
    payload=reading(ready[1],ready[0][1]['chip_uid'],9)
    page.goto('http://127.0.0.1:5175/tap?'+urlencode(payload))
    expect(page.get_by_role('heading',name='测试外套',exact=True)).to_be_visible()
    expect(page.get_by_role('button',name='下一张图片',exact=True)).to_have_count(0)
    gallery=page.get_by_role('region',name='物品照片，可左右滑动')
    assert gallery.evaluate('(node) => getComputedStyle(node).scrollSnapType')=='x mandatory'
    bounds=gallery.bounding_box()
    assert bounds and abs(bounds['width']/bounds['height'] - 11/12)<0.02
    assert bounds['x']==0 and bounds['width']==390
    session=page.context.new_cdp_session(page)
    def swipe(frame, forward):
        bounds=frame.bounding_box()
        y=bounds['y']+bounds['height']/2
        fractions=(.9,.78,.65,.51,.38,.24,.12)
        points=[bounds['x']+bounds['width']*fraction for fraction in (fractions if forward else reversed(fractions))]
        session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':points[0],'y':y}]})
        for x in points[1:]:
            session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x,'y':y}]})
        assert frame.evaluate('(node) => node.scrollLeft > 0 && node.scrollLeft < node.clientWidth')
        session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
        expect(frame).to_have_js_property('scrollLeft',frame.evaluate('(node) => node.clientWidth') if forward else 0)
    swipe(gallery,True)
    expect(page.locator('.photo-strip > .gallery-position')).to_have_text('物品照片 · 2 / 2')
    page.get_by_role('button',name='放大服装图片',exact=True).click()
    dialog=page.get_by_role('dialog',name='服装图片大图',exact=True)
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role('img')).to_have_attribute('src',urls[1])
    expect(dialog.get_by_role('button',name='上一张图片',exact=True)).to_have_count(0)
    full=dialog.get_by_role('region',name='物品照片，可左右滑动')
    swipe(full,False)
    expect(dialog.get_by_role('img')).to_have_attribute('src',urls[0])
    swipe(full,True)
    expect(dialog.get_by_role('img')).to_have_attribute('src',urls[1])
    page.clock.fast_forward(61000)
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role('img')).to_have_attribute('src',urls[1])
    dialog.get_by_role('button',name='关闭大图',exact=True).click()
    expect(gallery).to_have_js_property('scrollLeft',390)
    page.evaluate('window.scrollTo(0,700)')
    position=page.evaluate('window.scrollY')
    query(phone.app,"UPDATE product_style SET material='新材质' WHERE id=%s",(style_id,))
    page.clock.fast_forward(61000)
    expect(page.get_by_text('新材质',exact=True)).to_be_attached()
    assert abs(page.evaluate('window.scrollY')-position)<5
    assert counts(phone.app)==(1,2)
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(tmp_path/'mobile-gallery.png'),full_page=False)
