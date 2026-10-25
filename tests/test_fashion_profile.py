"""服装资料与启停在专属临时MySQL中的行为、权限和回滚检查。"""

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier

import pymysql
import pyotp
import pytest
from werkzeug.security import generate_password_hash

from core import admin_items
from core.secret_storage import encrypt_totp_secret
from tests.test_admin_auth import ORIGIN, login, query
from tests.test_admin_items import drafts, create

pytestmark = pytest.mark.auth_database


@pytest.fixture
def garment(drafts):
    response = create(drafts)
    assert response.status_code == 200
    return response.json["data"]["id"]


def save(drafts, garment, **changes):
    client, headers = drafts
    return client.put(f"/api/admin/items/{garment}/profile", json={"name": "棉质短袖", **changes}, headers=headers)


def status(drafts, garment, value):
    client, headers = drafts
    return client.patch(f"/api/admin/items/{garment}", json={"status": value}, headers=headers)


def test_save_replace_preserve_size_and_identity(auth_app, drafts, garment):
    query(auth_app, "UPDATE item SET updated_at='2020-01-01 00:00:00' WHERE id=%s", (garment,))
    original = query(auth_app, "SELECT * FROM item WHERE id=%s", (garment,))[0]
    result = save(drafts, garment, name=" 名称😀 ", description=" 介绍\n换行 ", material=" 纯棉 ", care_instructions=" 冷水洗 ", image_urls=[" https://example.com/a.png "])
    assert result.status_code == 200
    profile = result.json["data"]
    assert profile["name"] == "名称😀" and profile["description"] == "介绍\n换行"
    assert profile["image_urls"] == ["https://example.com/a.png"]
    query(auth_app, "UPDATE fashion_item_profile SET size_chart=%s WHERE item_id=%s", (json.dumps({"S": "90cm"}), garment))
    assert save(drafts, garment, name="新名", material="  ").status_code == 200
    found = drafts[0].get(f"/api/admin/items/{garment}").json["data"]
    assert found["profile"]["size_chart"] == {"S": "90cm"}
    assert found["profile"]["description"] is None and found["profile"]["image_urls"] == []
    current = query(auth_app, "SELECT * FROM item WHERE id=%s", (garment,))[0]
    assert current["updated_at"] > original["updated_at"]
    for field in ("project_id", "item_uid", "sku_code", "status", "created_at"):
        assert current[field] == original[field]
    assert query(auth_app, "SELECT COUNT(*) AS n FROM fashion_item_profile")[0]["n"] == 1
    audit = query(auth_app, "SELECT * FROM admin_audit WHERE action='item.profile.save'")
    assert len(audit) == 2 and audit[0]["target_id"] == str(garment)
    assert json.loads(audit[0]["detail"]) == {"project": "fashion"} and len(audit[0]["ip_hash"]) == 64


@pytest.mark.parametrize("changes", [
    {"name": None}, {"name": " "}, {"name": "字" * 129}, {"name": 1},
    {"description": "字" * 4001}, {"description": []}, {"material": "字" * 257},
    {"care_instructions": "字" * 2001}, {"image_urls": None}, {"image_urls": "https://example.com"},
    {"image_urls": [1]}, {"image_urls": ["https://example.com"] * 21},
    {"image_urls": ["javascript:alert(1)"]}, {"image_urls": ["data:image/png;base64,AA"]},
    {"image_urls": ["https://user:pass@example.com/a"]}, {"image_urls": ["https://example.com/a\nb"]},
    {"image_urls": ["https://example.com:99999/a"]}, {"image_urls": ["/relative.png"]},
    {"image_urls": ["https://example.com:0/a"]},
    {"image_urls": ["https://example.com/" + "x" * 2048]},
    {"size_chart": None}, {"status": "active"}, {"item_uid": "other"}, {"meaning": "其他项目"},
])
def test_invalid_profile_never_writes(auth_app, drafts, garment, changes):
    assert save(drafts, garment, **changes).status_code == 400
    assert query(auth_app, "SELECT COUNT(*) AS n FROM fashion_item_profile")[0]["n"] == 0


def test_payload_and_character_boundaries(drafts, garment):
    assert save(drafts, garment, name="😀" * 128, description="中" * 4000, material="棉" * 256, care_instructions="洗" * 2000, image_urls=["https://example.com/" + "a" * 2000] * 20).status_code == 200
    client, headers = drafts
    assert client.put(f"/api/admin/items/{garment}/profile", data="x" * (256 * 1024 + 1), content_type="application/json", headers=headers).status_code == 400
    assert client.post("/api/admin/items", data="x" * 9000, content_type="application/json", headers=headers).status_code == 400


def test_status_transitions_and_idempotency(auth_app, drafts, garment):
    assert status(drafts, garment, "active").status_code == 409
    assert status(drafts, garment, "disabled").status_code == 409
    assert save(drafts, garment).status_code == 200
    assert status(drafts, garment, "active").json["data"]["status"] == "active"
    assert status(drafts, garment, "active").status_code == 200
    assert save(drafts, garment, name="启用时修改").status_code == 200
    assert status(drafts, garment, "disabled").json["data"]["status"] == "disabled"
    assert save(drafts, garment, name="停用时修改").status_code == 200
    assert status(drafts, garment, "active").status_code == 200
    audit = query(auth_app, "SELECT detail FROM admin_audit WHERE action='item.status.change' ORDER BY id")
    assert [json.loads(a["detail"])["from"] for a in audit] == ["draft", "active", "disabled"]
    assert [json.loads(a["detail"])["to"] for a in audit] == ["active", "disabled", "active"]
    for value in ("draft", "archived", None, [], 1):
        assert status(drafts, garment, value).status_code == 400
    query(auth_app, "UPDATE item SET status='archived' WHERE id=%s", (garment,))
    assert status(drafts, garment, "active").status_code == 409
    assert save(drafts, garment).status_code == 409


@pytest.mark.parametrize("action", ["save", "status"])
@pytest.mark.parametrize("point", ["audit", "commit"])
def test_atomic_failure(auth_app, drafts, garment, monkeypatch, action, point):
    assert save(drafts, garment).status_code == 200
    before = query(auth_app, "SELECT * FROM fashion_item_profile")[0]
    item_before = query(auth_app, "SELECT * FROM item")[0]
    count = query(auth_app, "SELECT COUNT(*) AS n FROM admin_audit")[0]["n"]
    execute = pymysql.cursors.DictCursor.execute
    def fail_audit(cursor, sql, args=None):
        if sql.startswith("INSERT INTO admin_audit"):
            raise pymysql.OperationalError("合成审计失败")
        return execute(cursor, sql, args)
    def fail_commit(connection):
        raise pymysql.OperationalError("合成提交失败")
    with monkeypatch.context() as patch:
        patch.setattr(pymysql.cursors.DictCursor, "execute", fail_audit) if point == "audit" else patch.setattr(pymysql.connections.Connection, "commit", fail_commit)
        result = save(drafts, garment, name="不应保存") if action == "save" else status(drafts, garment, "active")
        assert result.status_code == 503
    assert query(auth_app, "SELECT * FROM fashion_item_profile")[0] == before
    assert query(auth_app, "SELECT * FROM item")[0] == item_before
    assert query(auth_app, "SELECT COUNT(*) AS n FROM admin_audit")[0]["n"] == count


def test_read_permissions_projects_and_request_shape(auth_app, drafts, garment):
    client, headers = drafts
    url = f"/api/admin/items/{garment}"
    assert client.get(url).json["data"]["profile"] is None
    assert client.get(url + "?x=1").status_code == 400
    assert client.get("/api/admin/items/999999").status_code == 404
    assert save(drafts, 999999).status_code == 404
    assert client.get("/api/admin/items/0").status_code == 400
    assert client.get("/api/admin/items/18446744073709551616").status_code == 400
    for path, method, body in [(url, "get", None), (url, "patch", {"status": "active"}), (url + "/profile", "put", {"name": "名"})]:
        assert getattr(auth_app.test_client(), method)(path, json=body, headers=ORIGIN).status_code == 401
        assert getattr(client, method)(path, json=body, headers={**headers, "Origin": "https://other.example"}).status_code == 403
        if method != "get":
            assert getattr(client, method)(path, json=body, headers={**headers, "X-CSRF-Token": "wrong"}).status_code == 403
            assert getattr(client, method)(path + "?x=1", json=body, headers=headers).status_code == 400
    jewel = create(drafts, project="jewelry", item_uid="JEW-2026-000001").json["data"]["id"]
    assert client.get(f"/api/admin/items/{jewel}").status_code == 200
    assert save(drafts, jewel).status_code == 409
    assert status(drafts, jewel, "active").status_code == 409
    assert client.patch(url, json={"status": "active", "sku_code": "other"}, headers=headers).status_code == 400


@pytest.mark.parametrize("action", ["save", "status"])
def test_permission_revocation_rechecked(auth_app, drafts, garment, monkeypatch, admin_account, action):
    original = admin_items.lock_admin_session
    def revoke(cursor):
        query(auth_app, "UPDATE admin_user SET status='disabled' WHERE id=%s", (admin_account["id"],))
        original(cursor)
    monkeypatch.setattr(admin_items, "lock_admin_session", revoke)
    result = save(drafts, garment) if action == "save" else status(drafts, garment, "active")
    assert result.status_code == 401
    assert query(auth_app, "SELECT COUNT(*) AS n FROM fashion_item_profile")[0]["n"] == 0


def test_concurrent_initial_saves_are_whole(auth_app, drafts, garment, monkeypatch):
    second = {"username": "profile-second", "password": "synthetic-only-password", "secret": pyotp.random_base32()}
    query(auth_app, "INSERT INTO admin_user(username,password_hash) VALUES (%s,%s)", (second["username"], generate_password_hash(second["password"])))
    admin_id = query(auth_app, "SELECT id FROM admin_user WHERE username=%s", (second["username"],))[0]["id"]
    with auth_app.app_context():
        encrypted = encrypt_totp_secret(second["secret"], admin_id)
    query(auth_app, "UPDATE admin_user SET totp_enabled=1,totp_secret_encrypted=%s WHERE id=%s", (encrypted, admin_id))
    client = auth_app.test_client()
    assert login(client, auth_app, second).status_code == 200
    other = (client, {**ORIGIN, "X-CSRF-Token": client.get("/api/admin/auth/session").json["data"]["csrf_token"]})
    barrier, original = Barrier(2), admin_items.locked_fashion_item
    def synchronize(cursor, item_id):
        barrier.wait(timeout=10)
        return original(cursor, item_id)
    monkeypatch.setattr(admin_items, "locked_fashion_item", synchronize)
    def perform(args):
        identity, label = args
        return save(identity, garment, name=label, description=label)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(perform, [(drafts, "甲"), (other, "乙")]))
    assert [r.status_code for r in responses] == [200, 200]
    rows = query(auth_app, "SELECT * FROM fashion_item_profile WHERE item_id=%s", (garment,))
    assert len(rows) == 1 and rows[0]["name"] == rows[0]["description"]
