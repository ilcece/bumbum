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
    assert page.url.endswith('/tap/items/'+str(query(phone.app,'SELECT item_id FROM chip')[0]['item_id']))
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


def test_gallery_fullscreen_and_poll_preserves_scroll(phone,ready,tmp_path):
    import base64
    page=phone.page
    page.clock.install()
    urls=['https://example.com/a.png','https://example.com/b.png']
    query(phone.app,'UPDATE fashion_item_profile SET image_urls=%s,description=%s',(json.dumps(urls),'很长的服装介绍\n'*120))
    # 仅提供合成像素，不请求真实图片网站。
    image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aP9sAAAAASUVORK5CYII=')
    page.route('https://example.com/**',lambda route:route.fulfill(status=200,content_type='image/png',body=image))
    payload=reading(ready[1],ready[0][1]['chip_uid'],9)
    page.goto('http://127.0.0.1:5175/tap?'+urlencode(payload))
    expect(page.get_by_role('heading',name='测试外套',exact=True)).to_be_visible()
    page.get_by_role('button',name='下一张图片',exact=True).click()
    page.get_by_role('button',name='放大服装图片',exact=True).click()
    dialog=page.get_by_role('dialog',name='服装图片大图',exact=True)
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role('img')).to_have_attribute('src',urls[1])
    page.clock.fast_forward(61000)
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role('img')).to_have_attribute('src',urls[1])
    dialog.get_by_role('button',name='关闭大图',exact=True).click()
    page.evaluate('window.scrollTo(0,700)')
    position=page.evaluate('window.scrollY')
    query(phone.app,"UPDATE fashion_item_profile SET material='新材质'")
    page.clock.fast_forward(61000)
    expect(page.get_by_text('新材质',exact=True)).to_be_attached()
    assert abs(page.evaluate('window.scrollY')-position)<5
    assert counts(phone.app)==(1,2)
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(tmp_path/'mobile-gallery.png'),full_page=False)
