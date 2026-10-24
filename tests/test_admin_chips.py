"""在专属临时MySQL中验证登记、去重、筛选、权限及一起保存的规则。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Barrier

import pymysql
import pyotp
import pytest
from werkzeug.security import generate_password_hash

from core import admin_chips
from core.db import get_database
from core.secret_storage import encrypt_totp_secret
from tests.test_admin_auth import ORIGIN, login, query

pytestmark = pytest.mark.auth_database
UID = "04:A2:7F:1B:5E:80:00"


@pytest.fixture
def logged_in(auth_app, admin_account):
    client = auth_app.test_client()
    assert login(client, auth_app, admin_account).status_code == 200
    csrf = client.get("/api/admin/auth/session").json["data"]["csrf_token"]
    return client, {**ORIGIN, "X-CSRF-Token": csrf}


def register(logged_in, **changes):
    client, headers = logged_in
    return client.post("/api/admin/chips", json={"chip_uid": UID, "project": "fashion", **changes}, headers=headers)


def test_register_then_list_uses_real_data_and_atomic_audit(auth_app, logged_in):
    response = register(logged_in, chip_uid=" 04a27f1b5e8000 ", batch_no=" 首批 ")
    assert response.status_code == 200
    data = response.json["data"]
    assert data["is_new"] is True
    chip = data["chip"]
    assert chip["chip_uid"] == UID and chip["project"] == "fashion"
    assert chip["batch_no"] == "首批" and chip["chip_status"] == "pending"
    assert chip["item_id"] is None and chip["item_uid"] is None
    assert chip["keys_generated"] is False and chip["provisioned_at"] is None
    assert chip["created_at"].endswith("Z")
    assert set(chip) == {"id", "chip_uid", "project", "chip_status", "item_id", "item_uid", "batch_no", "provisioned_at", "keys_generated", "created_at", "updated_at"}
    client, _headers = logged_in
    listed = client.get("/api/admin/chips")
    assert listed.status_code == 200
    assert listed.json["data"] == {"items": [chip], "total": 1, "page": 1, "page_size": 20}
    assert listed.headers["Cache-Control"] == "no-store"
    events = query(auth_app, "SELECT action,target_type,target_id,detail,ip_hash FROM admin_audit")
    assert len(events) == 1 and events[0]["action"] == "chip.register"
    assert events[0]["target_id"] == str(chip["id"]) and len(events[0]["ip_hash"]) == 64
    assert json.loads(events[0]["detail"]) == {"project": "fashion", "source": "manual"}


def test_duplicate_uid_never_overwrites_existing_data(auth_app, logged_in):
    first = register(logged_in, batch_no="原批次").json["data"]["chip"]
    query(auth_app, "UPDATE chip SET chip_status='disabled',updated_at='2020-01-01 00:00:00'")
    before = query(auth_app, "SELECT * FROM chip")[0]
    response = register(logged_in, chip_uid="04a27f1b5e8000", batch_no="覆盖尝试")
    assert response.status_code == 200 and response.json["data"]["is_new"] is False
    chip = response.json["data"]["chip"]
    assert chip["id"] == first["id"] and chip["batch_no"] == "原批次"
    assert chip["chip_status"] == "disabled"
    assert query(auth_app, "SELECT * FROM chip")[0] == before
    assert query(auth_app, "SELECT COUNT(*) AS count FROM chip")[0]["count"] == 1
    assert query(auth_app, "SELECT COUNT(*) AS count FROM admin_audit")[0]["count"] == 1


def test_cross_project_registration_cannot_move_chip(auth_app, logged_in):
    assert register(logged_in).status_code == 200
    response = register(logged_in, project="jewelry")
    assert response.status_code == 409 and response.json["code"] == "project_mismatch"
    assert query(auth_app, "SELECT project_id FROM chip")[0]["project_id"] == 1
    assert query(auth_app, "SELECT COUNT(*) AS count FROM admin_audit")[0]["count"] == 1


def test_pagination_filters_and_uid_search(logged_in, auth_app):
    for number in range(3):
        assert register(logged_in, chip_uid=f"04A27F1B5E80{number:02X}", project="jewelry" if number == 2 else "fashion").status_code == 200
    query(auth_app, "UPDATE chip SET chip_status='lost' WHERE project_id=2")
    client, _headers = logged_in
    first = client.get("/api/admin/chips?page_size=1").json["data"]
    second = client.get("/api/admin/chips?page_size=1&page=2").json["data"]
    assert first["total"] == second["total"] == 3
    assert first["items"][0]["id"] > second["items"][0]["id"]
    filtered = client.get("/api/admin/chips?project=jewelry&status=lost&keyword=04a27f").json["data"]
    assert filtered["total"] == 1 and filtered["items"][0]["project"] == "jewelry"
    assert client.get("/api/admin/chips?keyword=%25").json["data"]["total"] == 0
    assert client.get("/api/admin/chips?keyword='OR1=1").json["data"]["total"] == 0
    assert client.get("/api/admin/chips?page=99").json["data"]["items"] == []


@pytest.mark.parametrize("changes", [
    {"chip_uid": 123}, {"chip_uid": "04:A2:7F"}, {"chip_uid": "04-A2-7F-1B-5E-80-00"},
    {"chip_uid": "04A27F1B5E800G"}, {"project": "other"}, {"project": []},
    {"batch_no": ""}, {"batch_no": "x" * 65}, {"batch_no": 1}, {"force": True},
])
def test_invalid_registration_does_not_write(auth_app, logged_in, changes):
    response = register(logged_in, **changes)
    assert response.status_code == 400 and response.json["code"] == "invalid_param"
    assert query(auth_app, "SELECT COUNT(*) AS count FROM chip")[0]["count"] == 0


@pytest.mark.parametrize("query_string", ["page=0", "page=-1", "page=1.5", "page_size=101", "page=999999999999", "project=other", "status=active", "extra=1", "page=1&page=2"])
def test_list_rejects_invalid_queries(logged_in, query_string):
    client, _headers = logged_in
    response = client.get("/api/admin/chips?" + query_string)
    assert response.status_code == 400


def test_registration_requires_cookie_origin_and_matching_csrf(auth_app, logged_in):
    assert auth_app.test_client().get("/api/admin/chips").status_code == 401
    response = auth_app.test_client().post("/api/admin/chips", json={"chip_uid": UID, "project": "fashion"}, headers=ORIGIN)
    assert response.status_code == 401
    client, headers = logged_in
    assert client.post("/api/admin/chips", json={"chip_uid": UID, "project": "fashion"}, headers=ORIGIN).status_code == 403
    assert client.post("/api/admin/chips", json={"chip_uid": UID, "project": "fashion"}, headers={**headers, "Origin": "https://other.example"}).status_code == 403
    assert client.post("/api/admin/chips?project=fashion", json={"chip_uid": UID, "project": "fashion"}, headers=headers).status_code == 400
    assert client.get("/api/admin/auth/session?extra=1").status_code == 400
    assert query(auth_app, "SELECT COUNT(*) AS count FROM chip")[0]["count"] == 0


def test_preflight_allows_both_registered_resource_methods(logged_in):
    client, _headers = logged_in
    response = client.options("/api/admin/chips", headers={**ORIGIN, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type, X-CSRF-Token"})
    assert response.status_code == 204
    assert "POST" in response.headers["Access-Control-Allow-Methods"]


def test_parallel_registration_is_deduplicated(logged_in, auth_app):
    client, headers = logged_in
    from core.admin_auth import COOKIE_NAME
    token = client.get_cookie(COOKIE_NAME, path="/api/admin").value
    def attempt(_):
        other = auth_app.test_client()
        other.set_cookie(COOKIE_NAME, token, path="/api/admin")
        return register((other, headers))
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(response.json["data"]["is_new"] for response in responses) == [False, True]
    assert query(auth_app, "SELECT COUNT(*) AS count FROM chip")[0]["count"] == 1
    assert query(auth_app, "SELECT COUNT(*) AS count FROM admin_audit")[0]["count"] == 1


@pytest.mark.parametrize("second_project", ["fashion", "jewelry"])
def test_different_admins_registering_same_uid_are_serialized_by_unique_index(auth_app, logged_in, second_project, monkeypatch):
    second_account = {"username": "second-test-admin", "password": "test-only-second-password", "secret": pyotp.random_base32()}
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO admin_user(username,password_hash) VALUES (%s,%s)", (second_account["username"], generate_password_hash(second_account["password"])))
            admin_id = cursor.lastrowid
            cursor.execute("UPDATE admin_user SET totp_enabled=1,totp_secret_encrypted=%s WHERE id=%s", (encrypt_totp_secret(second_account["secret"], admin_id), admin_id))
        connection.commit()
    second = auth_app.test_client()
    assert login(second, auth_app, second_account).status_code == 200
    headers = {**ORIGIN, "X-CSRF-Token": second.get("/api/admin/auth/session").json["data"]["csrf_token"]}
    barrier = Barrier(2)
    original_execute = pymysql.cursors.DictCursor.execute
    def execute(cursor, sql, args=None):
        result = original_execute(cursor, sql, args)
        if sql.startswith("SELECT id FROM project"):
            # 让两次请求先建立读取快照，再同时争抢同一个UID。
            barrier.wait(timeout=10)
        return result
    monkeypatch.setattr(pymysql.cursors.DictCursor, "execute", execute)
    def attempt(number):
        return register(logged_in if number == 0 else (second, headers), project="fashion" if number == 0 else second_project)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))
    assert sorted(response.status_code for response in responses) == ([200, 200] if second_project == "fashion" else [200, 409])
    assert query(auth_app, "SELECT COUNT(*) AS count FROM chip")[0]["count"] == 1
    assert query(auth_app, "SELECT COUNT(*) AS count FROM admin_audit")[0]["count"] == 1


def test_audit_failure_rolls_back_new_chip(auth_app, logged_in, monkeypatch):
    original = pymysql.cursors.DictCursor.execute
    def execute(cursor, sql, args=None):
        if sql.startswith("INSERT INTO admin_audit"):
            raise pymysql.OperationalError("测试用审计保存失败")
        return original(cursor, sql, args)
    with monkeypatch.context() as changes:
        changes.setattr(pymysql.cursors.DictCursor, "execute", execute)
        assert register(logged_in).status_code == 503
    assert query(auth_app, "SELECT COUNT(*) AS count FROM chip")[0]["count"] == 0


def test_commit_failure_rolls_back_new_chip(auth_app, logged_in, monkeypatch):
    def fail(_self):
        raise pymysql.OperationalError("测试用提交失败")
    with monkeypatch.context() as changes:
        changes.setattr(pymysql.connections.Connection, "commit", fail)
        assert register(logged_in).status_code == 503
    assert query(auth_app, "SELECT COUNT(*) AS count FROM chip")[0]["count"] == 0
    assert query(auth_app, "SELECT COUNT(*) AS count FROM admin_audit")[0]["count"] == 0


def test_permission_is_rechecked_inside_write_transaction(auth_app, logged_in, monkeypatch):
    original = admin_chips.lock_admin_session
    def revoked(cursor):
        cursor.execute("UPDATE admin_session SET revoked_at=UTC_TIMESTAMP()")
        return original(cursor)
    monkeypatch.setattr(admin_chips, "lock_admin_session", revoked)
    assert register(logged_in).status_code == 401
    assert query(auth_app, "SELECT COUNT(*) AS count FROM chip")[0]["count"] == 0


def test_expired_session_cannot_register(auth_app, logged_in):
    auth_app.test_clock[0] += timedelta(hours=8)
    assert register(logged_in).status_code == 401
