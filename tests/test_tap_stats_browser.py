"""使用真实工作台与触碰明细检查口径、返回和异常提示。"""
from datetime import timedelta
from pathlib import Path
import re

import pytest

from tests.admin_ui_helpers import api, choose, install, setup
from tests.test_admin_auth import query
from tests.test_admin_browser import browser_gate, button, desktop, expect


pytestmark = [pytest.mark.auth_database, pytest.mark.browser]


def test_real_scope_switch_and_failure_not_zero(desktop, tmp_path):
    style, issue, item, chips = setup(desktop)
    p = desktop.page
    p.set_viewport_size({"width": 1920, "height": 1080})
    desktop.app.config['SMS_CODE_HASH_KEY'] = 'aa' * 32

    def draft(number):
        return api(desktop, "item", {"issue_id": issue, "item_uid": f"WORKBENCH-{number}",
                                     "edition_number": number})["id"]

    def ready(ident, chip):
        install(desktop, style, ident, chip)
        query(desktop.app, "UPDATE chip SET provisioned_at=%s,last_verified_counter=2 WHERE id=%s",
              (desktop.app.test_clock[0], chip))
        api(desktop, "toggleItem", {"item_id": ident, "status": "active"})

    draft(2)
    install(desktop, style, draft(3), chips[1])
    ready(draft(4), chips[2])
    claim, zero = draft(5), draft(6)
    for number, ident in enumerate((claim, zero), 204):
        chip = api(desktop, "register", {"chip_uid": f"04{number:012X}"})["id"]
        ready(ident, chip)
        api(desktop, "sale", {"item_id": ident, "confirmed": True, "evidence": "模拟成交"})
    api(desktop, "issueClaimCode", {"item_id": claim, "confirmed": True, "delivery_reference": "模拟交付"})
    query(desktop.app, "UPDATE digital_item SET first_sold_at=NULL WHERE item_id=%s", (claim,))
    ready(item, chips[0])
    api(desktop, "sale", {"item_id": item, "confirmed": True, "evidence": "售出事实"})
    uid = query(desktop.app, "SELECT chip_uid FROM chip WHERE id=%s", (chips[0],))[0]["chip_uid"]
    for counter, days in enumerate((-1, 1, 2), 3):
        query(desktop.app, """INSERT INTO scan_log(chip_id,item_id,chip_uid,project_id,scan_counter,verify_result,created_at)
                              VALUES (%s,%s,%s,1,%s,'pass',%s)""",
              (chips[0], item, uid, counter, desktop.app.test_clock[0] + timedelta(days=days)))
    desktop.navigate("工作台")
    p.reload(wait_until="networkidle")
    expect(p.locator("aside").get_by_role("link", name=re.compile("订单管理$"))).to_be_visible()
    workflows = p.locator(".ant-pro-card").filter(has=p.get_by_text("待办与可分配库存", exact=True))
    expect(workflows.locator(".metric-card")).to_have_count(5)
    expect(workflows.get_by_role("button")).to_have_count(5)
    choose(p, "时间范围", "累计")
    button(p, "应用筛选")
    cards = p.locator(".metric-card")
    expect(cards).to_have_count(13)
    expect(cards.get_by_role("button")).to_have_count(10)
    expect(cards.filter(has_text="当前持有人").get_by_role("button")).to_have_count(0)
    metric = cards.filter(has_text="有效触碰次数")
    expect(metric.locator(".ant-statistic-content")).to_contain_text("2")
    expect(p.get_by_text("每件被触碰物品平均 2.0 次", exact=True)).to_be_visible()
    overview = p.url
    p.locator(".ant-timeline").get_by_role("button",name="FASH-2026-880001").first.click()
    expect(p).to_have_url(re.compile(fr"/items/{item}\?from="))
    p.go_back(wait_until="networkidle")
    assert p.url == overview
    metrics = Path("test-results/admin-governance")
    metrics.mkdir(parents=True, exist_ok=True)
    p.screenshot(path=str(metrics / "1920-overview-metrics.png"), animations="disabled")
    metric.get_by_role("button", name=re.compile("查看触碰明细")).click(position={"x": 5, "y": 5})
    expect(p).to_have_url(re.compile(r"/overview/activity.*scope=sold"))
    expect(p.locator(".ant-table-tbody .ant-table-row")).to_have_count(2)
    original = p.url
    p.locator(".ant-table-tbody .ant-table-row").first.get_by_role("button",name="FASH-2026-880001").click()
    expect(p).to_have_url(re.compile(fr"/items/{item}\?from="))
    heading = p.locator("#item-detail-heading")
    timeline = p.locator(".ant-timeline").filter(has_text="身份未记录")
    timeline.get_by_role("button",name="FASH-2026-880001").first.click()
    expect(heading).to_be_focused()
    p.go_back(wait_until="networkidle")
    assert p.url == original
    p.go_back(wait_until="networkidle")
    expect(metric).to_contain_text("2")
    for stage, label, total in (
        ("assembly", "待装配", 1), ("verification", "待核验", 1),
        ("delivery", "待交付", 2), ("claim", "待认领", 1), ("available", "可分配", 1),
    ):
        card = cards.filter(has=p.get_by_text(label, exact=True))
        expect(card.locator(".ant-statistic-content")).to_have_text(f"{total}件")
        card.get_by_role("button").press("Enter")
        expect(p).to_have_url(re.compile(r"/items\?workflow=" + stage))
        rows = p.locator(".ant-table-tbody .ant-table-row")
        expect(rows).to_have_count(total)
        expect(rows.get_by_text(label, exact=True)).to_have_count(total)
        p.go_back(wait_until="networkidle")

    for key, title, uid in (
        ("touched", "被触碰物品数", "FASH-2026-880001"),
        ("repeat", "重复触碰物品", "FASH-2026-880001"),
        ("zero", "所选时段售出后零触碰", "WORKBENCH-6"),
        ("missing_sale", "成交时间待核对", "WORKBENCH-5"),
    ):
        card = cards.filter(has=p.get_by_text(title, exact=True))
        expect(card.locator(".ant-statistic-content")).to_have_text("1件")
        card.get_by_role("button").press("Space")
        expect(p).to_have_url(re.compile(r"as_of=.*detail_filter=" + key))
        rows = p.locator("#overview-details .ant-table-tbody .ant-table-row")
        expect(rows).to_have_count(1)
        expect(rows).to_contain_text(uid)
    choose(p, "统计口径", "全生命周期有效触碰")
    button(p, "应用筛选")
    expect(metric).to_contain_text("3")
    expect(cards.filter(has_text="成交时间待核对")).to_have_count(0)
    expect(p.get_by_role("img", name="按北京时间汇总的有效触碰日趋势")).to_be_visible()

    path = "**/api/admin/catalog/statistics?*"
    p.route(path, lambda route: route.fulfill(status=503, json={
        "status": "error", "code": "service_unavailable", "message": "合成统计不可用",
    }))
    button(p, "应用筛选")
    expect(p.get_by_text("合成统计不可用", exact=True)).to_be_visible()
    expect(metric).to_contain_text("3")
    p.unroute(path)
    button(p, "重试读取")
    expect(p.get_by_text("合成统计不可用", exact=True)).to_have_count(0)
    p.screenshot(animations="disabled", path=str(tmp_path / "statistics-1920.png"))
