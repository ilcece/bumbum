"""在正式后台构建产物上从空库建单，走完缺资料补建和订单件回跳。"""

import re

import pytest

from tests.admin_ui_helpers import api, choose, key_configuration
from tests.test_admin_auth import query
from tests.test_admin_browser import browser_gate, button, desktop, expect
from tests.test_chip_keys import configure


pytestmark = [pytest.mark.auth_database, pytest.mark.browser]


def test_empty_order_workflow_in_admin(desktop):
    configure(desktop.app)
    desktop.app.config["SMS_CODE_HASH_KEY"] = "aa" * 32
    desktop.login()
    p = desktop.page
    button(p, "查看订单")
    button(p, "新建订单")
    dialog = p.get_by_role("dialog", name="新建订单", exact=True)
    dialog.get_by_label("成交渠道", exact=True).fill("验收店铺")
    dialog.get_by_label("外部订单号", exact=True).fill("EMPTY-ORDER")
    dialog.get_by_label("购买商品", exact=True).fill("棒球帽")
    dialog.get_by_label("购买规格", exact=True).fill("黑色")
    button(dialog, "保存并打开订单")
    button(p, "登记实物")
    physical = p.get_by_role("dialog", name="登记实体物品", exact=True)
    physical.get_by_label("实体编号", exact=True).fill("EMPTY-PHYSICAL")
    button(physical, "新建款式")
    style = p.get_by_role("dialog", name="维护款式共用资料", exact=True)
    style.get_by_label("款式编号", exact=True).fill("EMPTY-STYLE")
    choose(style, "物品类别", "服装")
    style.get_by_label("款式名称", exact=True).fill("空库棒球帽")
    button(style, "保存共用资料")
    expect(physical.get_by_label("实体编号", exact=True)).to_have_value("EMPTY-PHYSICAL")
    physical.get_by_label("实际规格", exact=True).fill("黑色")
    button(physical, "保存实体")
    expect(p).to_have_url(re.compile(r"/orders/\d+\?unit=\d+"))
    unit_url = p.url
    p.reload(wait_until="networkidle")
    button(p, "开始装配")
    button(p, "新建发行草案")
    issue = p.get_by_role("dialog", name="发行约定草案", exact=True)
    issue.get_by_label("发行名称", exact=True).fill("空库首发")
    issue.get_by_label("固定发行总量", exact=True).fill("5")
    issue.get_by_label("发行说明与规格承诺", exact=True).fill("黑色棒球帽")
    button(issue, "保存草案")
    confirm = p.get_by_role("dialog", name="确认发行约定", exact=True)
    confirm.get_by_label("发行确认依据", exact=True).fill("已核对")
    confirm.get_by_role("checkbox").check()
    button(confirm, "确认发行")
    item_number = p.get_by_label("数字物品编号", exact=True)
    item_number.fill("EMPTY-ITEM")
    button(p, "登记新芯片")
    chip = p.get_by_role("dialog", name="登记新芯片", exact=True)
    chip.get_by_label("芯片 UID", exact=True).fill("040000000000D1")
    button(chip, "登记芯片")
    expect(item_number).to_have_value("EMPTY-ITEM")
    p.get_by_role("checkbox", name="已将所选芯片安装到这件实物").check()
    button(p, "确认安装")
    expect(p).to_have_url(unit_url)
    button(p, "配置并核验芯片")
    chip_id = query(desktop.app, "SELECT id FROM chip WHERE chip_uid='04:00:00:00:00:00:D1'")[0]["id"]
    key_configuration(desktop, chip_id)
    button(p, "启用数字物品")
    button(p.get_by_role("dialog", name="启用数字物品", exact=True), "启用数字物品")
    expect(p).to_have_url(unit_url)
    button(p, "确认分配")
    button(p.get_by_role("dialog", name="确认分配", exact=True), "确认分配")
    button(p, "确认首次售出")
    sale = p.get_by_role("dialog", name="确认首次售出", exact=True)
    # 隔离库使用固定时钟，输入相应的北京时间。
    sale.get_by_label("实际首次成交（北京时间）", exact=True).fill("2026-10-24 10:00:00")
    sale.get_by_label("实际首次成交（北京时间）", exact=True).press("Enter")
    button(sale, "确认首次售出")
    assert not query(desktop.app, "SELECT id FROM item_claim_code")
    button(p, "核对实际交付并发码")
    delivery = p.get_by_role("dialog", name="核对实际交付并发码", exact=True)
    delivery.get_by_label("首次交付核对依据", exact=True).fill("已核对验收实物")
    delivery.get_by_role("checkbox").check()
    button(delivery, "核对实际交付并发码")
    expect(p.get_by_role("dialog", name="交付认领码", exact=True)).to_be_visible()
    button(p, "完成")
    expect(p.get_by_text("已核对验收实物", exact=True)).to_be_visible()


def test_existing_stock_stays_with_its_order_unit(desktop):
    from tests.admin_ui_helpers import install, setup

    style, _, stock, chips = setup(desktop)
    install(desktop, style, stock, chips[0])
    query(desktop.app, "UPDATE chip SET provisioned_at=UTC_TIMESTAMP(),last_verified_counter=2 WHERE id=%s", (chips[0],))
    api(desktop, "toggleItem", {"item_id": stock, "status": "active"})
    order = api(desktop, "createOrder", {"channel": "验收店铺", "external_order_no": "TWO-ITEMS",
                                      "units": [{"product_name": "A"}, {"product_name": "B"}]})
    p = desktop.page
    p.goto("http://localhost:5174/orders/" + str(order["id"]), wait_until="networkidle")
    units = p.locator("section[id^=order-unit-]")
    a, b = units.nth(0), units.nth(1)
    button(a, "选用已就绪数字库存")
    pick = p.get_by_role("dialog", name="确认分配", exact=True)
    choose(pick, "可分配数字库存", "FASH-2026-880001")
    button(pick, "确认分配")
    expect(a.get_by_text("待售出", exact=True)).to_be_visible()
    expect(b.get_by_text("待准备", exact=True)).to_be_visible()
    button(b, "选用已就绪数字库存")
    pick.get_by_label("可分配数字库存", exact=True).click()
    expect(p.locator(".ant-select-dropdown:visible .ant-select-item-option")).to_have_count(0)
