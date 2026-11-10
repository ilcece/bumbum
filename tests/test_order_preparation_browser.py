"""使用独立数据库验证工作台的两条实际办理路径。"""

import pytest

from tests.admin_ui_helpers import api, choose, install, key_configuration, setup
from tests.test_admin_auth import query
from tests.test_admin_browser import browser_gate, button, desktop, expect

pytestmark = [pytest.mark.auth_database, pytest.mark.browser]


def test_order_preparation_resume_and_separate_delivery(desktop, tmp_path):
    style, issue, stock, chips = setup(desktop)
    install(desktop, style, stock, chips[0])
    desktop.app.config["SMS_CODE_HASH_KEY"] = "aa" * 32
    # 临时库预置已核验库存；新登记路径另外提交真实的核验接口。
    query(desktop.app, "UPDATE chip SET provisioned_at=UTC_TIMESTAMP(),last_verified_counter=2 WHERE id=%s", (chips[0],))
    api(desktop, "toggleItem", {"item_id": stock, "status": "active"})
    p = desktop.page
    button(p, "准备订单物品")
    p.get_by_label("成交渠道", exact=True).fill("品牌店铺")
    p.get_by_label("外部订单号", exact=True).fill("BROWSER-ORDER-12")
    choose(p, "关联款式", "UI-CAP")
    p.get_by_label("实体编号", exact=True).fill("UI-PHYSICAL-ORDER")
    p.get_by_label("实际规格", exact=True).fill("L黑")
    button(p, "保存实物")
    expect(p.get_by_label("同款已确认发行", exact=True)).to_be_visible()
    button(p, "保存，稍后继续")
    p.reload(wait_until="networkidle")
    button(p, "继续办理")
    choose(p, "同款已确认发行", "浏览器限定发行")
    button(p, "采用建议编号")
    choose(p, "配套芯片 UID", "04:00:00:00:00:00:CA")
    p.get_by_role("checkbox", name="已核对实物和芯片，并完成实际安装").check()
    button(p, "确认安装")
    expect(p.get_by_text("已安装 · 待核验", exact=True)).to_be_visible()
    button(p, "保存，稍后继续")
    button(p, "继续办理")
    p.set_viewport_size({"width": 1280, "height": 720})
    p.screenshot(path=str(tmp_path / "order-resume.png"), animations="disabled")
    button(p, "打开配置核验")
    key_configuration(desktop, chips[1])
    button(p, "确认启用")
    expect(p.get_by_label("外部订单号", exact=True)).to_have_value("BROWSER-ORDER-12")
    button(p, "确认售出")
    expect(p.get_by_label("首次交付核对依据", exact=True)).to_be_visible()
    assert not query(desktop.app, "SELECT id FROM item_claim_code")
    button(p, "保存，稍后继续")
    button(p, "继续办理")
    p.get_by_label("首次交付核对依据", exact=True).fill("已核对实物与接收人")
    p.get_by_role("checkbox", name="已核对实际交付与接收对象").check()
    button(p, "确认交付并发放认领码")
    expect(p.get_by_role("dialog", name="交付认领码")).to_be_visible()
    button(p, "完成")
    button(p, "同订单再准备一件")
    p.get_by_role("radio", name="选用已有库存").check()
    choose(p, "已核验、已启用的未售库存", "FASH-2026-880001")
    button(p, "选用此件，进入售出确认")
    expect(p.get_by_label("外部订单号", exact=True)).to_have_value("BROWSER-ORDER-12")
    button(p, "确认售出")
    p.get_by_label("首次交付核对依据", exact=True).fill("已核对库存物品与接收人")
    p.get_by_role("checkbox", name="已核对实际交付与接收对象").check()
    button(p, "确认交付并发放认领码")
    expect(p.get_by_role("dialog", name="交付认领码")).to_be_visible()
    assert len(query(desktop.app, "SELECT item_id FROM item_claim_code")) == 2
    sales = query(desktop.app, "SELECT sale_evidence FROM digital_item WHERE sold=1")
    assert len(sales) == 2 and all("BROWSER-ORDER-12" in sale["sale_evidence"] for sale in sales)
    audits = p.request.get("http://localhost:5174/api/admin/catalog/audit?keyword=BROWSER-ORDER-12").json()["data"]
    assert len(audits["items"]) == 2 and all(row["action"] == "catalog.orderSale" for row in audits["items"])
