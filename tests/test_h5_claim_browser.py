"""用真实页面、隔离数据库及合成短信验证过期认领恢复，不发送真实短信。"""

from datetime import timedelta
from urllib.parse import urlencode

import pytest

from tests.browser_support import browser_fixture
from tests.test_admin_browser import browser_gate, expect
from tests.test_admin_catalog import catalog
from tests.test_admin_chips import logged_in
from tests.test_admin_auth import query
from tests.test_chip_keys import reading
from tests.test_h5_claim import claim_ready

pytestmark = [pytest.mark.auth_database, pytest.mark.browser]


@pytest.fixture
def claim_phone(request, auth_app, claim_ready, tmp_path):
    yield from browser_fixture(request, auth_app, None, tmp_path,
                               frontend_name='user', clear_items=False)


def test_expired_claim_prompts_retap_and_resumes_without_sms_login(claim_phone, claim_ready):
    item, uid, keys, issued, sms = claim_ready
    page = claim_phone.page
    origin = 'http://127.0.0.1:5175'
    page.goto(origin + '/tap?' + urlencode(reading(keys, uid, 3)))
    page.get_by_role('button', name='认领这件物品', exact=True).click()
    page.get_by_label('手机号', exact=True).fill('13900009704')
    page.get_by_role('button', name='发送短信验证码', exact=True).click()
    expect(page.get_by_label('短信验证码', exact=True)).to_be_visible()
    page.get_by_label('短信验证码', exact=True).fill(sms['13900009704'])
    page.get_by_role('button', name='验证并继续', exact=True).click()
    expect(page.get_by_text('认领账户 139****9704', exact=True)).to_be_visible()
    page.get_by_label('交付认领码', exact=True).fill(issued['claim_code'])
    claim_phone.app.test_clock[0] += timedelta(minutes=6)
    page.get_by_role('button', name='确认认领', exact=True).click()
    expect(page.get_by_role('alert')).to_have_text('请重新碰一下物品，再继续认领。')
    expect(page.get_by_role('heading', name='手机号登录／注册', exact=True)).to_have_count(0)
    assert not query(claim_phone.app, 'SELECT id FROM ownership WHERE item_id=%s', (item,))
    # 新碰卡通过后直接恢复原物品的认领表单，不再次发送或验证短信。
    page.goto(origin + '/tap?' + urlencode(reading(keys, uid, 4)))
    expect(page.get_by_text('认领账户 139****9704', exact=True)).to_be_visible()
    expect(page.get_by_role('heading', name='手机号登录／注册', exact=True)).to_have_count(0)
    page.get_by_label('交付认领码', exact=True).fill(issued['claim_code'])
    page.get_by_role('button', name='确认认领', exact=True).click()
    expect(page.get_by_role('heading', name='已认领到我的数字物品', exact=True)).to_be_visible()
    page.get_by_role('link', name='查看我的物品', exact=True).click()
    expect(page.get_by_text('你持有这件物品', exact=True)).to_be_visible()
    assert page.url == f'{origin}/mine/items/{item}'
    assert len(query(claim_phone.app, 'SELECT id FROM ownership WHERE item_id=%s', (item,))) == 1
    assert len(query(claim_phone.app, 'SELECT challenge_id FROM user_sms_challenge')) == 1
