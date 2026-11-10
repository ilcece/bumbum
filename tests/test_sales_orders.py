"""隔离 MySQL 中从空库建单，并验证逐件分配、交付和可追溯性。"""

import pytest

from tests.test_admin_catalog import action, config_chip, ok
from tests.test_admin_chips import logged_in


pytestmark = pytest.mark.auth_database


def test_empty_order_and_independent_units(auth_app, logged_in):
    auth_app.config["SMS_CODE_HASH_KEY"] = "aa" * 32

    def save(action_name, **payload):
        return ok(action(logged_in, action_name, payload))

    def get(path):
        return ok(logged_in[0].get("/api/admin/catalog/" + path))

    created = save("createOrder", channel="线上", external_order_no="TEST-ORDER",
                   units=[{"product_name": "棒球帽", "ordered_spec": "黑 L"}, {"product_name": "棒球帽"}])
    order_id = created["id"]
    first, second = get(f"orders/{order_id}")["units"]
    assert not first["item_id"] and not second["physical_item_id"]

    style = save("style", project="fashion", code="ORDER-CAP", name="棒球帽", specs=["黑 L"], image_urls=[])["id"]
    save("orderPhysical", order_unit_id=first["id"],
         physical={"style_id": style, "physical_uid": "ORDER-PHYS-1", "spec": "黑 L"})
    first, second = get(f"orders/{order_id}")["units"]
    assert first["physical_uid"] == "ORDER-PHYS-1"
    assert action(logged_in, "orderPhysical", {"order_unit_id": second["id"],
                  "physical_item_id": first["physical_item_id"]}).status_code == 409
    issue = save("issue", style_id=style, name="测试发行", mode="fixed", total=2, description="黑 L")["id"]
    save("confirmIssue", issue_id=issue)

    from tests.test_chip_keys import configure
    configure(auth_app)
    chip = save("register", chip_uid="040000000000A1")["id"]
    item = save("assembleOrderItem", order_unit_id=first["id"], issue_id=issue, item_uid="ORDER-ITEM-1",
                edition_number=1, chip_id=chip, physical_item_id=first["physical_item_id"], installed=True)["id"]
    assert get(f"items/{item}")["order"]["id"] == first["id"]
    assert get(f"orders/{order_id}")["units"][0]["provisioned_at"] is None
    assert action(logged_in, "allocateOrderUnit", {"order_unit_id": first["id"], "item_id": item}).status_code == 409
    config_chip(auth_app, logged_in, chip)
    save("toggleItem", item_id=item, status="active")
    save("allocateOrderUnit", order_unit_id=first["id"], item_id=item)
    assert action(logged_in, "allocateOrderUnit", {"order_unit_id": second["id"], "item_id": item}).status_code == 409

    physical = save("createPhysicalItem", style_id=style, physical_uid="ORDER-PHYS-2", spec="黑 L")["id"]
    chip = save("register", chip_uid="040000000000A2")["id"]
    stock = save("assembleOrderItem", issue_id=issue, item_uid="ORDER-ITEM-2", edition_number=2,
                 chip_id=chip, physical_item_id=physical, installed=True)["id"]
    config_chip(auth_app, logged_in, chip)
    save("toggleItem", item_id=stock, status="active")
    assert [r["id"] for r in get("items?order_stock=true")["items"]] == [stock]
    save("allocateOrderUnit", order_unit_id=second["id"], item_id=stock)
    save("releaseOrderUnit", order_unit_id=second["id"], evidence="订单件暂缓")
    assert [r["id"] for r in get("items?order_stock=true")["items"]] == [stock]
    save("allocateOrderUnit", order_unit_id=second["id"], item_id=stock)

    delivery = {"item_id": item, "delivery_reference": "首次交付凭证", "confirmed": True}
    assert action(logged_in, "issueClaimCode", delivery).status_code == 409
    save("orderSale", order_unit_id=first["id"], item_id=item, first_sold_at="2026-10-24T10:00:00+08:00")
    assert get(f"orders/{order_id}")["units"][0]["delivered_at"] is None
    assert save("issueClaimCode", **delivery)["claim_code"]
    first, second = get(f"orders/{order_id}")["units"]
    assert first["delivered_generation"] == 1 and first["first_delivery_reference"] == "首次交付凭证"
    assert second["item_id"] == stock and not second["sold"] and not second["delivered_at"]
    assert get("items?keyword=TEST-ORDER&workflow=claim")["items"][0]["id"] == item
