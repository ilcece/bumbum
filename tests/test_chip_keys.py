"""专属临时MySQL核对密钥、审计、权限与实卡配置确认事务。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
import json
import secrets

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import pymysql
import pytest

from core import chip_keys
from core.sdm_derivation import aes_cmac
from core.secret_storage import decrypt_chip_keys
from tests.test_admin_auth import ORIGIN, query
from tests.test_admin_chips import logged_in
from tests.test_chip_binding import inventory, item, chip, bind, second_session

pytestmark = pytest.mark.auth_database


def configure(app):
    app.config.update(MASTER_KEY_FASHION=secrets.token_hex(16), MASTER_KEY_JEWELRY=secrets.token_hex(16), SDM_META_KEY_V1=secrets.token_hex(16), SDM_META_KEY_VERSION="v1")


@pytest.fixture
def keyed(auth_app, inventory):
    configure(auth_app)
    target = item(auth_app)
    source = chip(inventory)
    assert bind(inventory, source, target).status_code == 200
    return inventory, source


def post(keyed, action, body=None):
    session, source = keyed
    return session[0].post(f"/api/admin/chips/{source['id']}/{action}", headers=session[1], json={} if body is None else body)


def stored(app):
    return query(app, "SELECT * FROM chip_key")[0]


def generated(app, keyed):
    assert post(keyed, "generate-keys").status_code == 200
    response = post(keyed, "keys", {"confirm": True})
    assert response.status_code == 200
    return response.json["data"]["keys"]


def reading(keys, uid, counter):
    raw = bytes.fromhex(uid.replace(":", ""))
    plain = b"\xC7" + raw + counter.to_bytes(3, "little") + bytes(5)
    cipher = Cipher(algorithms.AES(bytes.fromhex(keys["K1"])), modes.CBC(bytes(16))).encryptor()
    encrypted = cipher.update(plain) + cipher.finalize()
    session = aes_cmac(bytes.fromhex(keys["K2"]), bytes.fromhex("3CC300010080") + raw + counter.to_bytes(3, "little"))
    return {"picc_data": encrypted.hex().upper(), "cmac": aes_cmac(session, b"")[1::2].hex().upper()}


def confirmation(keyed, keys, first=5, second=8):
    return {"management_confirmed": True, "readings": [reading(keys, keyed[1]["chip_uid"], n) for n in (first, second)]}


def test_generate_view_confirm_and_preserve_item(auth_app, keyed, caplog):
    before = query(auth_app, "SELECT * FROM item")[0]
    keys = generated(auth_app, keyed)
    assert list(keys) == [f"K{n}" for n in range(5)]
    row = stored(auth_app)
    assert all(value.encode() not in row["encrypted_keys"] for value in keys.values())
    with auth_app.app_context(): assert decrypt_chip_keys(row, keyed[1]["id"]) == keys
    assert query(auth_app, "SELECT provisioned_at,last_verified_counter FROM chip")[0] == {"provisioned_at": None, "last_verified_counter": None}
    body = confirmation(keyed, keys)
    result = post(keyed, "confirm-provisioning", body)
    assert result.status_code == 200 and result.json["data"]["provisioned_at"]
    assert result.headers["Cache-Control"] == "no-store"
    assert query(auth_app, "SELECT last_verified_counter FROM chip")[0]["last_verified_counter"] == 8
    assert query(auth_app, "SELECT * FROM item")[0] == before
    assert post(keyed, "confirm-provisioning", body).json["code"] == "already_configured"
    assert post(keyed, "generate-keys").json["code"] == "already_exists"
    records = query(auth_app, "SELECT action,detail,ip_hash FROM admin_audit WHERE action IN ('chip.generate_keys','chip.view_keys','chip.confirm_provisioning')")
    assert len(records) == 3 and all(len(row["ip_hash"]) == 64 for row in records)
    assert all(value not in json.dumps(records) + caplog.text for value in keys.values())
    assert all(value not in json.dumps(records) + caplog.text for entry in body["readings"] for value in entry.values())


@pytest.mark.parametrize("mode", ["missing", "zero", "invalid", "version", "same_meta", "same_project"])
def test_config_errors_do_not_write_or_break_existing_queries(auth_app, keyed, mode):
    if mode == "missing": auth_app.config["MASTER_KEY_FASHION"] = ""
    elif mode == "zero": auth_app.config["SDM_META_KEY_V1"] = "0"*32
    elif mode == "invalid": auth_app.config["MASTER_KEY_FASHION"] = "bad"
    elif mode == "version": auth_app.config["SDM_META_KEY_VERSION"] = "v2"
    elif mode == "same_meta": auth_app.config["SDM_META_KEY_V1"] = auth_app.config["MASTER_KEY_FASHION"]
    else: auth_app.config["MASTER_KEY_JEWELRY"] = auth_app.config["MASTER_KEY_FASHION"]
    response = post(keyed, "generate-keys")
    assert response.status_code == 503 and "密钥配置" in response.json["message"]
    assert not query(auth_app, "SELECT * FROM chip_key")
    assert keyed[0][0].get("/api/admin/chips").status_code == 200


@pytest.mark.parametrize("mode", ["root", "meta", "storage", "ciphertext", "key_version", "master_version"])
def test_changed_or_damaged_config_never_returns_keys(auth_app, keyed, mode):
    generated(auth_app, keyed)
    if mode in {"root", "meta", "storage"}:
        name = {"root": "MASTER_KEY_FASHION", "meta": "SDM_META_KEY_V1", "storage": "STORAGE_ENCRYPTION_KEY"}[mode]
        auth_app.config[name] = secrets.token_hex(32 if mode == "storage" else 16)
    elif mode == "ciphertext": query(auth_app, "UPDATE chip_key SET encrypted_keys=%s", (bytes(16),))
    else: query(auth_app, "UPDATE chip_key SET " + ("key_version" if mode == "key_version" else "master_key_version") + "='v2'")
    assert post(keyed, "keys", {"confirm": True}).status_code == 503
    assert len(query(auth_app, "SELECT * FROM admin_audit WHERE action='chip.view_keys'")) == 1
    assert post(keyed, "generate-keys").status_code == 409


@pytest.mark.parametrize("mode", ["unbound", "disabled", "lost", "archived"])
def test_rejects_invalid_business_state(auth_app, keyed, mode):
    if mode == "unbound": query(auth_app, "UPDATE chip SET item_id=NULL,chip_status='pending'")
    elif mode == "archived": query(auth_app, "UPDATE item SET status='archived'")
    else: query(auth_app, "UPDATE chip SET chip_status=%s", (mode,))
    assert post(keyed, "generate-keys").status_code == 409
    assert not query(auth_app, "SELECT * FROM chip_key")


@pytest.mark.parametrize("mode", ["same", "reverse", "exhausted", "uid", "mac", "layout", "wrong_key", "shape", "format", "management"])
def test_bad_readings_never_mark_provisioned(auth_app, keyed, mode):
    keys = generated(auth_app, keyed)
    body = confirmation(keyed, keys)
    if mode == "same": body = confirmation(keyed, keys, 5, 5)
    elif mode == "reverse": body = confirmation(keyed, keys, 8, 5)
    elif mode == "exhausted": body = confirmation(keyed, keys, 8, 0xFFFFFF)
    elif mode == "uid": body["readings"][0] = reading(keys, "04:00:00:00:00:00:FF", 5)
    elif mode == "mac": body["readings"][0]["cmac"] = "0"*16
    elif mode == "layout": body["readings"][0]["picc_data"] = "0"*32
    elif mode == "wrong_key": body["readings"][0] = reading({**keys, "K2": "03"*16}, keyed[1]["chip_uid"], 5)
    elif mode == "shape": body["readings"][0]["extra"] = True
    elif mode == "format": body["readings"][0]["picc_data"] = "Ｇ"*32
    else: body["management_confirmed"] = 1
    assert post(keyed, "confirm-provisioning", body).status_code in (400,409)
    assert query(auth_app, "SELECT provisioned_at,last_verified_counter FROM chip")[0] == {"provisioned_at": None, "last_verified_counter": None}


@pytest.mark.parametrize("operation", ["generate-keys", "keys", "confirm-provisioning"])
@pytest.mark.parametrize("failure", ["audit", "commit"])
def test_storage_failure_rolls_back(auth_app, keyed, monkeypatch, operation, failure):
    keys = generated(auth_app, keyed) if operation != "generate-keys" else None
    before = query(auth_app, "SELECT * FROM admin_audit")
    execute = pymysql.cursors.DictCursor.execute
    def fail_execute(cursor, sql, args=None):
        if sql.startswith("INSERT INTO admin_audit"): raise pymysql.OperationalError(1205, "合成审计失败")
        return execute(cursor, sql, args)
    def fail_commit(_): raise pymysql.OperationalError(2013, "合成提交前失败")
    with monkeypatch.context() as patch:
        if failure == "audit": patch.setattr(pymysql.cursors.DictCursor, "execute", fail_execute)
        else: patch.setattr(pymysql.connections.Connection, "commit", fail_commit)
        body = {"confirm":True} if operation == "keys" else confirmation(keyed, keys) if keys else {}
        assert post(keyed, operation, body).status_code == 503
    assert query(auth_app, "SELECT * FROM admin_audit") == before
    assert query(auth_app, "SELECT provisioned_at FROM chip")[0]["provisioned_at"] is None
    if operation == "generate-keys": assert not query(auth_app, "SELECT * FROM chip_key")


@pytest.mark.parametrize("mode", ["csrf", "origin", "logout", "disabled", "expired"])
def test_auth_protection(auth_app, keyed, monkeypatch, mode):
    session, source = keyed
    headers = dict(session[1])
    if mode == "csrf": headers.pop("X-CSRF-Token")
    elif mode == "origin": headers["Origin"] = "https://other.example"
    elif mode == "logout": session[0].post("/api/admin/auth/logout", headers=headers, json={})
    else:
        original = chip_keys.lock_admin_session
        def revoke(cursor):
            if mode == "disabled": cursor.execute("UPDATE admin_user SET status='disabled'")
            else: cursor.execute("UPDATE admin_session SET expires_at=%s", (auth_app.test_clock[0] - timedelta(seconds=1),))
            original(cursor)
        monkeypatch.setattr(chip_keys, "lock_admin_session", revoke)
    response = session[0].post(f"/api/admin/chips/{source['id']}/generate-keys", headers=headers, json={})
    assert response.status_code == (403 if mode in {"csrf","origin"} else 401)
    assert not query(auth_app, "SELECT * FROM chip_key")


@pytest.mark.parametrize("action,body", [("generate-keys", {"force":True}), ("keys", {"confirm":1}), ("keys", {}), ("confirm-provisioning", {"readings":[],"management_confirmed":True})])
def test_strict_requests(keyed, action, body):
    assert post(keyed, action, body).status_code == 400


def test_same_version_global_meta_and_independent_per_card(auth_app, keyed):
    first = generated(auth_app, keyed)
    target = item(auth_app, project="jewelry", n=2)
    second_chip = chip(keyed[0], n=2)
    assert bind(keyed[0], second_chip, target).status_code == 200
    second = generated(auth_app, (keyed[0], second_chip))
    assert first["K1"] == second["K1"]
    assert all(first[f"K{slot}"] != second[f"K{slot}"] for slot in (0,2,3,4))


def test_two_concurrent_generations_only_one_record(auth_app, keyed, monkeypatch):
    session, source = keyed
    sessions = [session, second_session(auth_app)]
    barrier = Barrier(2)
    original = chip_keys.lock_admin_session
    def together(cursor):
        barrier.wait(timeout=10)
        original(cursor)
    monkeypatch.setattr(chip_keys, "lock_admin_session", together)
    def generate(index):
        client, headers = sessions[index]
        return client.post(f"/api/admin/chips/{source['id']}/generate-keys", headers=headers, json={}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: statuses = list(pool.map(generate, range(2)))
    assert sorted(statuses) == [200,409]
    assert len(query(auth_app, "SELECT * FROM chip_key")) == 1
    assert len(query(auth_app, "SELECT * FROM admin_audit WHERE action='chip.generate_keys'")) == 1


@pytest.mark.parametrize("operation", ["generate-keys", "confirm-provisioning"])
def test_commit_receipt_lost_preserves_committed_result(auth_app, keyed, monkeypatch, operation):
    keys = generated(auth_app, keyed) if operation == "confirm-provisioning" else None
    original = pymysql.connections.Connection.commit
    def committed_then_lost(connection):
        original(connection)
        raise pymysql.OperationalError(2013, "合成提交成功后回执丢失")
    with monkeypatch.context() as patch:
        patch.setattr(pymysql.connections.Connection, "commit", committed_then_lost)
        response = post(keyed, operation, confirmation(keyed, keys) if keys else {})
        assert response.status_code == 503
    actual = keyed[0][0].get('/api/admin/chips').json['data']['items'][0]
    assert actual['keys_generated']
    assert bool(actual['provisioned_at']) == (operation == "confirm-provisioning")
    assert post(keyed, operation, confirmation(keyed, keys) if keys else {}).status_code == 409


def test_missing_and_large_paths_and_read_without_keys(keyed):
    session, source = keyed
    assert post(keyed, 'keys', {'confirm': True}).status_code == 404
    for identifier, status in [(0,400),(18446744073709551616,400),(18446744073709551615,404)]:
        assert session[0].post(f'/api/admin/chips/{identifier}/generate-keys',headers=session[1],json={}).status_code == status
    assert session[0].post(f'/api/admin/chips/{source["id"]}/generate-keys?force=1',headers=session[1],json={}).status_code == 400
    assert session[0].post(f'/api/admin/chips/{source["id"]}/generate-keys',headers=session[1],data='{}',content_type='text/plain').status_code == 400
