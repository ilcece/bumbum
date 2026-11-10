"""使用真实工作台与触碰明细检查口径、返回和异常提示。"""
from datetime import timedelta
import re

import pytest

from tests.admin_ui_helpers import api, choose, install, setup
from tests.test_admin_auth import query
from tests.test_admin_browser import browser_gate, button, desktop, expect


pytestmark = [pytest.mark.auth_database, pytest.mark.browser]


def test_real_scope_switch_and_failure_not_zero(desktop, tmp_path):
    style, _, item, chips = setup(desktop)
    p = desktop.page
    install(desktop, style, item, chips[0])
    api(desktop, "sale", {"item_id": item, "confirmed": True, "evidence": "售出事实"})
    uid = query(desktop.app, "SELECT chip_uid FROM chip WHERE id=%s", (chips[0],))[0]["chip_uid"]
    for counter, days in enumerate((-1, 1, 2), 3):
        query(desktop.app, """INSERT INTO scan_log(chip_id,item_id,chip_uid,project_id,scan_counter,verify_result,created_at)
                              VALUES (%s,%s,%s,1,%s,'pass',%s)""",
              (chips[0], item, uid, counter, desktop.app.test_clock[0] + timedelta(days=days)))
    desktop.navigate("工作台")
    expect(p.locator("aside").get_by_role("link", name=re.compile("订单管理$"))).to_be_visible()
    choose(p, "时间范围", "累计")
    button(p, "应用筛选")
    metric = p.locator(".metric-primary .ant-statistic-content").first
    expect(metric).to_contain_text("2")
    button(p, "查看触碰明细")
    expect(p).to_have_url(re.compile(r"/overview/activity.*scope=sold"))
    expect(p.locator(".ant-table-tbody .ant-table-row")).to_have_count(2)
    p.go_back(wait_until="networkidle")
    expect(metric).to_contain_text("2")
    choose(p, "统计口径", "全生命周期有效触碰")
    button(p, "应用筛选")
    expect(metric).to_contain_text("3")
    expect(p.get_by_role("img", name="按北京时间汇总的有效触碰日趋势")).to_be_visible()

    path = "**/api/admin/catalog/statistics?*"
    p.route(path, lambda route: route.fulfill(status=503, json={
        "status": "error", "code": "service_unavailable", "message": "合成统计不可用",
    }))
    button(p, "应用筛选")
    expect(p.get_by_text("合成统计不可用", exact=True)).to_be_visible()
    expect(metric).to_contain_text("3")
    p.unroute(path)
    button(p, "重试")
    expect(p.get_by_text("合成统计不可用", exact=True)).to_have_count(0)
    p.screenshot(animations="disabled", path=str(tmp_path / "statistics-1280.png"))
