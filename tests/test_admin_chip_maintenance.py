"""芯片维护在真实MySQL上验证完整过滤、精确详情和原子批次更新。"""

import json
from time import perf_counter

import pymysql
import pytest

from core import admin_chips
from tests.test_admin_auth import ORIGIN, query
from tests.test_admin_chips import logged_in, register

pytestmark = pytest.mark.auth_database


def test_detail_and_batch_edit_preserve_identity_and_noop(auth_app, logged_in):
    client, headers = logged_in
    chip = register(logged_in, project=None, batch_no="原批次").json["data"]["chip"]
    path = f'/api/admin/chips/{chip["id"]}'
    before = query(auth_app, "SELECT * FROM chip")[0]
    detail = client.get(path).json["data"]
    assert detail == {**chip, "item_name": None, "keyword_matches": []}
    query(auth_app, "UPDATE chip SET updated_at='2020-01-01' WHERE id=%s", (chip["id"],))
    noop = client.patch(path, json={"batch_no": " 原批次 "}, headers=headers)
    assert noop.status_code == 200 and noop.json["data"]["updated_at"] == "2020-01-01T00:00:00Z"
    assert len(query(auth_app, "SELECT * FROM admin_audit")) == 1
    response = client.patch(path, json={"batch_no": " 新批次 "}, headers=headers)
    assert response.status_code == 200 and response.json["data"]["batch_no"] == "新批次"
    after = query(auth_app, "SELECT * FROM chip")[0]
    assert {k: v for k, v in after.items() if k not in {"batch_no", "updated_at"}} == {k: v for k, v in before.items() if k not in {"batch_no", "updated_at"}}
    audit = query(auth_app, "SELECT * FROM admin_audit WHERE action='chip.batch.update'")[0]
    assert json.loads(audit["detail"]) == {"from": "原批次", "to": "新批次"}
    for empty in ("  ", None):
        assert client.patch(path, json={"batch_no": empty}, headers=headers).json["data"]["batch_no"] is None
    assert len(query(auth_app, "SELECT * FROM admin_audit WHERE action='chip.batch.update'")) == 2


@pytest.mark.parametrize("payload", [{}, {"batch_no": 1}, {"batch_no": False}, {"batch_no": []}, {"batch_no": "x" * 65}, {"batch_no": "x", "project": "jewelry"}, {"chip_status": "lost"}, {"item_id": 1}])
def test_batch_rejects_readonly_and_invalid_fields(auth_app, logged_in, payload):
    client, headers = logged_in
    chip = register(logged_in).json["data"]["chip"]
    before = query(auth_app, "SELECT * FROM chip")
    assert client.patch(f'/api/admin/chips/{chip["id"]}', json=payload, headers=headers).status_code == 400
    assert query(auth_app, "SELECT * FROM chip") == before


def test_detail_patch_permissions_and_exact_id(auth_app, logged_in):
    client, headers = logged_in
    chip = register(logged_in).json["data"]["chip"]
    path = f'/api/admin/chips/{chip["id"]}'
    assert auth_app.test_client().get(path).status_code == 401
    assert client.patch(path, json={"batch_no": "x"}, headers=ORIGIN).status_code == 403
    assert client.patch(path, json={"batch_no": "x"}, headers={**headers, "Origin": "https://other.example"}).status_code == 403
    assert client.get(path + "?extra=1").status_code == 400
    for invalid_id in (0, 18446744073709551616):
        assert client.get(f"/api/admin/chips/{invalid_id}").status_code == 400
    assert client.get("/api/admin/chips/99999999").status_code == 404
    assert client.patch("/api/admin/chips/99999999", json={"batch_no": None}, headers=headers).status_code == 404
    assert client.get(path).headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("failure", ["audit", "permission"])
def test_batch_failure_rolls_back(auth_app, logged_in, monkeypatch, failure):
    client, headers = logged_in
    chip = register(logged_in, batch_no="before").json["data"]["chip"]
    before = query(auth_app, "SELECT * FROM chip")
    if failure == "audit":
        original = pymysql.cursors.DictCursor.execute
        def execute(cursor, sql, args=None):
            if sql.startswith("INSERT INTO admin_audit"):
                raise pymysql.OperationalError("合成审计失败")
            return original(cursor, sql, args)
        monkeypatch.setattr(pymysql.cursors.DictCursor, "execute", execute)
    else:
        original = admin_chips.lock_admin_session
        def revoked(cursor):
            cursor.execute("UPDATE admin_session SET revoked_at=UTC_TIMESTAMP()")
            original(cursor)
        monkeypatch.setattr(admin_chips, "lock_admin_session", revoked)
    response = client.patch(f'/api/admin/chips/{chip["id"]}', json={"batch_no": "after"}, headers=headers)
    assert response.status_code == (503 if failure == "audit" else 401)
    assert query(auth_app, "SELECT * FROM chip") == before
    assert query(auth_app, "SELECT COUNT(*) n FROM admin_audit")[0]["n"] == 1


def test_combined_filters_match_related_profiles_before_pagination(auth_app, logged_in):
    client, headers = logged_in
    ids = []
    for number, project in ((1, "fashion"), (2, "jewelry")):
        chip = register(logged_in, chip_uid=f"04A27F1B5E80{number:02X}", project=project, batch_no="样!_%批").json["data"]["chip"]
        item = client.post("/api/admin/items", json={"project": project, "item_uid": ("FASH" if number == 1 else "JEW") + f"-2026-88000{number}"}, headers=headers).json["data"]
        query(auth_app, f"INSERT INTO {project}_item_profile(item_id,name) VALUES (%s,%s)", (item["id"], "同名!_%资料"))
        query(auth_app, "UPDATE chip SET chip_status='disabled',item_id=%s,created_at='2026-11-02 16:00:00',updated_at='2026-11-03 15:59:59',registration_source='nfc_cool' WHERE id=%s", (item["id"], chip["id"]))
        ids.append(chip["id"])
    # 无关联的更晚记录不能挤占符合条件的页面。
    register(logged_in, chip_uid="04A27F1B5E8003")
    filters = {"keyword": "同名!_%", "batch_no": "!_%", "registration_source": "nfc_cool", "has_item": "true", "keys_generated": "false", "provisioned": "false", "created_from": "2026-11-03", "created_to": "2026-11-03", "updated_to": "2026-11-03", "page_size": "1", "page": "2"}
    result = client.get("/api/admin/chips", query_string=filters).json["data"]
    assert result["total"] == 2 and result["total_pages"] == 2 and result["page"] == 2
    assert result["items"][0]["id"] == ids[0] and result["items"][0]["keyword_matches"] == ["item_name"]
    assert result["items"][0]["item_name"] == "同名!_%资料"
    for number, chip_id in enumerate(ids, 1):
        found = client.get("/api/admin/chips", query_string={"keyword": f"88000{number}"}).json["data"]
        assert found["total"] == 1 and found["items"][0]["keyword_matches"] == ["item_uid"]
        assert client.get(f"/api/admin/chips/{chip_id}").json["data"]["item_name"] == "同名!_%资料"
    compact = client.get("/api/admin/chips?keyword=04a27f1b5e8001").json["data"]
    assert compact["total"] == 1 and compact["items"][0]["keyword_matches"] == ["chip_uid"]
    assert client.get("/api/admin/chips", query_string={"keyword": "'% OR 1=1"}).json["data"]["total"] == 0
    assert client.get("/api/admin/chips?has_item=false").json["data"]["total"] == 1
    empty = client.get("/api/admin/chips?batch_no=nope&page=99").json["data"]
    assert empty["page"] == 1 and empty["page_adjusted"] is True and empty["items"] == []
    query(auth_app, "UPDATE chip SET provisioned_at='2026-11-03 16:00:00' WHERE id=%s", (ids[0],))
    assert client.get("/api/admin/chips?provisioned_to=2026-11-03").json["data"]["total"] == 0
    assert client.get("/api/admin/chips?provisioned_from=2026-11-04&provisioned=true").json["data"]["total"] == 1


@pytest.mark.parametrize("parameters", [
    {"has_item": "1"}, {"keys_generated": "False"}, {"provisioned": ""}, {"registration_source": "web"},
    {"batch_no": "x" * 65}, {"keyword": "x" * 129}, {"created_from": "2026-02-30"},
    {"updated_to": "9999-12-31"}, {"created_from": "0001-01-01"}, {"created_to": "2026-1-2"},
    {"created_from": "2026-11-04", "created_to": "2026-11-03"}, {"provisioned": "false", "provisioned_from": "2026-11-03"},
    [("has_item", "true"), ("has_item", "false")],
])
def test_strict_new_filters(logged_in, parameters):
    client, _ = logged_in
    assert client.get("/api/admin/chips", query_string=parameters).status_code == 400


def test_count_and_rows_share_snapshot(auth_app, logged_in, monkeypatch):
    client, _ = logged_in
    chip = register(logged_in).json["data"]["chip"]
    original = pymysql.cursors.DictCursor.execute
    def execute(cursor, sql, args=None):
        result = original(cursor, sql, args)
        if sql.startswith("SELECT COUNT(*) AS total "):
            query(auth_app, "UPDATE chip SET batch_no='并发更改' WHERE id=%s", (chip["id"],))
        return result
    monkeypatch.setattr(pymysql.cursors.DictCursor, "execute", execute)
    found = client.get("/api/admin/chips").json["data"]
    assert found["total"] == 1 and found["items"][0]["batch_no"] is None
    assert client.get(f'/api/admin/chips/{chip["id"]}').json["data"]["batch_no"] == "并发更改"


def test_contains_query_plan_on_isolated_inventory(auth_app, logged_in, record_property):
    """记录小库存实测与关联计划，不声称前导模糊匹配使用普通索引。"""
    from core.db import get_database
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            for number in range(200):
                cursor.execute("INSERT INTO item(project_id,item_uid) VALUES (1,%s)", (f"FASH-2026-{920000 + number:06d}",))
                item_id = cursor.lastrowid
                cursor.execute("INSERT INTO fashion_item_profile(item_id,name) VALUES (%s,%s)", (item_id, f"计划样本{number % 4}"))
                cursor.execute("INSERT INTO chip(chip_uid,project_id,item_id,chip_status,batch_no) VALUES (%s,1,%s,'bound','计划批次')",
                               (f"04:01:02:03:04:05:{number:02X}", item_id))
        connection.commit()
    client, _ = logged_in
    started = perf_counter()
    result = client.get("/api/admin/chips", query_string={"keyword": "计划样本3", "batch_no": "计划", "has_item": "true", "page": 3}).json["data"]
    elapsed = perf_counter() - started
    assert result["total"] == 50 and result["page"] == 3 and len(result["items"]) == 10
    assert {row["item_name"] for row in result["items"]} == {"计划样本3"}
    with auth_app.app_context():
        with get_database().cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("EXPLAIN " + admin_chips.READ_VIEW + admin_chips.READ_JOINS + " WHERE " + admin_chips.ITEM_NAME + " LIKE %s ESCAPE '!' ORDER BY c.id DESC LIMIT 20", ("%计划样本3%",))
            plan = cursor.fetchall()
    record_property("inventory_rows", 200)
    record_property("contains_query_seconds", round(elapsed, 4))
    record_property("join_plan", json.dumps([{key: row[key] for key in ("table", "type", "key", "possible_keys", "rows")} for row in plan]))
