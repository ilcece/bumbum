"""在正式后台构建产物上从空库建单，走完缺资料补建和订单件回跳。"""

from datetime import datetime, timezone
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
    p.locator("aside").get_by_role("link", name=re.compile("订单管理$")).click()
    button(p, "新建订单")
    dialog = p.get_by_role("dialog", name="新建订单", exact=True)
    dialog.get_by_label("成交渠道", exact=True).fill("验收店铺")
    dialog.get_by_label("外部订单号", exact=True).fill("EMPTY-ORDER")
    dialog.get_by_label("购买商品", exact=True).fill("棒球帽")
    dialog.get_by_label("购买规格", exact=True).fill("黑色")
    button(dialog, "保存并打开订单")
    button(p, "核对款式与规格")
    match = p.get_by_role("dialog", name="核对款式与规格", exact=True)
    button(match, "补建款式")
    style = p.get_by_role("dialog", name="补建款式", exact=True)
    style.get_by_label("款式编号", exact=True).fill("EMPTY-STYLE")
    style.get_by_label("款式名称", exact=True).fill("空库棒球帽")
    button(style, "保存并带回")
    match.get_by_label("对应规格", exact=True).fill("黑色")
    button(match, "确认款式与规格")
    button(p, "准备物品")
    p.get_by_role("menuitem", name="登记新实物", exact=True).click()
    physical = p.get_by_role("dialog", name="登记实体物品", exact=True)
    physical.get_by_label("实体编号", exact=True).fill("EMPTY-PHYSICAL")
    button(physical, "登记并用于本件")
    expect(p).to_have_url(re.compile(r"/orders/\d+\?unit=\d+"))
    unit_url = p.url
    p.reload(wait_until="networkidle")
    button(p, "开始装配")
    button(p, "新建发行草案")
    issue = p.get_by_role("dialog", name="发行约定草案", exact=True)
    issue.get_by_label("发行名称", exact=True).fill("空库首发")
    issue.get_by_label("固定发行总量", exact=True).fill("5")
    issue.get_by_label("发行说明与规格承诺", exact=True).fill("黑色棒球帽")
    button(issue, "保存并继续确认")
    confirm = p.get_by_role("dialog", name="确认发行约定", exact=True)
    confirm.get_by_label("发行确认依据", exact=True).fill("已核对")
    confirm.get_by_role("checkbox").check()
    button(confirm, "确认并带回")
    item_number = p.get_by_label("数字物品编号", exact=True)
    expect(item_number).to_have_value(re.compile(r"^FASH-"))
    item_number.fill("EMPTY-ITEM")
    attestation = p.get_by_role("checkbox", name="已将所选芯片安装到这件实物")
    expect(attestation).to_be_disabled()
    api(desktop, "register", {"chip_uid": "040000000000D2"})
    button(p, "登记新芯片")
    chip = p.get_by_role("dialog", name="手工登记芯片", exact=True)
    chip.get_by_label("芯片编号 UID", exact=True).fill("040000000000D1")
    button(chip, "登记并带回")
    expect(item_number).to_have_value("EMPTY-ITEM")
    attestation.check()
    choose(p, "芯片 UID", "04:00:00:00:00:00:D2")
    expect(attestation).not_to_be_checked()
    choose(p, "芯片 UID", "04:00:00:00:00:00:D1")
    attestation.check()
    button(p, "确认安装")
    expect(p).to_have_url(unit_url)
    button(p, "配置并核验芯片")
    chip_id = query(desktop.app, "SELECT id FROM chip WHERE chip_uid='04:00:00:00:00:00:D1'")[0]["id"]
    key_configuration(desktop, chip_id)
    button(p, "EMPTY-ITEM")
    expect(p).to_have_url(re.compile(r"/items/\d+\?from="))
    item_url = p.url
    button(p, "打开对应订单件")
    expect(p).to_have_url(unit_url)
    button(p, "EMPTY-ITEM")
    expect(p).to_have_url(item_url)
    p.get_by_role("button", name="back", exact=True).click()
    expect(p).to_have_url(unit_url)
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
    issued = p.get_by_role("dialog", name="交付认领码", exact=True)
    expect(issued).to_be_visible()
    original = issued.locator('[data-private]').get_by_text(re.compile(r'^[0-9A-F]{16}$')).inner_text()
    issued.get_by_role("button", name=re.compile(r"^关\s*闭$")).last.click()
    expect(p.get_by_text("已核对验收实物", exact=True)).to_be_visible()
    p.clock.set_fixed_time(datetime(2026, 10, 25, tzinfo=timezone.utc))
    p.reload(wait_until="networkidle")
    button(p, "查看认领码")
    expect(issued.locator('[data-private]').get_by_text(original, exact=True)).to_be_visible()
    issued.get_by_role("button", name=re.compile(r'^关\s*闭$')).last.click()
    button(p, "EMPTY-ITEM")
    button(p, "查看认领码")
    expect(issued.locator('[data-private]').get_by_text(original, exact=True)).to_be_visible()
    issued.get_by_role("button", name=re.compile(r'^关\s*闭$')).last.click()
    query(desktop.app, "UPDATE item_claim_code SET expires_at='2026-10-24 00:00:00'")
    p.reload(wait_until="networkidle")
    expect(p.get_by_text("已过期", exact=True)).to_be_visible()
    expect(p.get_by_role("button", name="查看认领码", exact=True)).to_have_count(0)


def test_existing_stock_stays_with_its_order_unit(desktop):
    from tests.admin_ui_helpers import install, setup

    style, _, stock, chips = setup(desktop)
    install(desktop, style, stock, chips[0])
    query(desktop.app, "UPDATE chip SET provisioned_at=UTC_TIMESTAMP(),last_verified_counter=2 WHERE id=%s", (chips[0],))
    api(desktop, "toggleItem", {"item_id": stock, "status": "active"})
    order = api(desktop, "createOrder", {"channel": "验收店铺", "external_order_no": "TWO-ITEMS",
                                      "units": [{"product_name": "A"}, {"product_name": "B"}]})
    for unit in query(desktop.app, "SELECT id FROM sales_order_unit WHERE order_id=%s", (order["id"],)):
        api(desktop, "matchOrderUnit", {"order_unit_id": unit["id"], "style_id": style, "spec": "L黑"})
    p = desktop.page
    p.goto("http://localhost:5174/orders/" + str(order["id"]), wait_until="networkidle")
    units = p.locator("section[id^=order-unit-]")
    a, b = units.nth(0), units.nth(1)
    button(a, "准备物品")
    p.get_by_role("menuitem", name="选用已就绪数字库存", exact=True).click()
    pick = p.get_by_role("dialog", name="选择可分配数字库存", exact=True)
    choose(pick, "可分配数字库存", "FASH-2026-880001")
    button(pick, "确认分配")
    expect(a.get_by_text("待售出", exact=True)).to_be_visible()
    expect(b.get_by_text("待准备", exact=True)).to_be_visible()
    button(b, "准备物品")
    p.get_by_role("menuitem", name="选用已就绪数字库存", exact=True).click()
    expect(pick.get_by_label("可分配数字库存", exact=True)).to_be_disabled()
    expect(pick.get_by_role("button", name="确认分配", exact=True)).to_be_disabled()
    expect(pick.get_by_role("button", name="选用已有实物", exact=True)).to_be_visible()


def test_workbench_and_filtered_list_return_paths(desktop):
    from tests.admin_ui_helpers import setup

    style, _, _, _ = setup(desktop)
    api(desktop, "createPhysicalItem", {"style_id": style, "physical_uid": "ROUTE-PHY-01", "spec": "L黑"})
    order = api(desktop, "createOrder", {"channel": "验收店铺", "external_order_no": "ROUTE-ORDER-01",
                                      "units": [{"product_name": "A"}, {"product_name": "B"}]})
    p = desktop.page
    desktop.navigate("数字物品")
    expect(p).to_have_url(re.compile(r"/items\?page=1$"))
    listing = p.url
    button(p, "新建数字物品")
    expect(p.get_by_label("数字物品编号", exact=True)).to_be_visible()
    button(p, "取消")
    expect(p).to_have_url(listing)

    def search(label, keyword):
        field = p.get_by_role("textbox", name=re.compile(label))
        field.fill(keyword)
        field.press("Enter")
        expect(p).to_have_url(re.compile(r"keyword="))
        return field, p.url

    back = p.get_by_role("button", name="back", exact=True)
    p.get_by_role("link", name=re.compile("订单管理$")).click()
    field, previous = search("订单号或渠道", "ROUTE-ORDER-01")
    button(p, "ROUTE-ORDER-01")
    button(p, "第 2 件 · 待核对款式规格")
    expect(p).to_have_url(re.compile(r"/orders/" + str(order["id"]) + r"\?unit="))
    back.click()
    expect(p).to_have_url(previous)
    expect(field).to_have_value("ROUTE-ORDER-01")

    physical_link = p.get_by_role("link", name="实体物品", exact=True)
    if not physical_link.is_visible():
        p.get_by_role("menuitem", name=re.compile("数字物品管理")).click()
    physical_link.click()
    field, previous = search("实体编号或规格", "ROUTE-PHY-01")
    button(p, "ROUTE-PHY-01")
    button(p, "新建数字物品")
    expect(p.get_by_text("ROUTE-PHY-01 · L黑", exact=True)).to_be_visible()
    button(p, "取消")
    back.click()
    expect(p).to_have_url(previous)
    expect(field).to_have_value("ROUTE-PHY-01")

    p.get_by_role("link", name=re.compile("芯片管理$")).click()
    chip_uid = "04:00:00:00:00:00:C9"
    field, previous = search("关键词", chip_uid)
    button(p, chip_uid)
    chip = p.get_by_role("dialog", name="芯片详情", exact=True)
    button(chip, "新建数字物品")
    expect(p.get_by_text(chip_uid, exact=True)).to_be_visible()
    button(p, "取消")
    back.click()
    expect(p).to_have_url(previous)
    expect(field).to_have_value(chip_uid)
