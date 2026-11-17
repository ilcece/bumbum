"""隔离库使用实际 WebAuthn 注册数据和签名检查登录、重放及撤销。"""

from base64 import urlsafe_b64encode
from contextlib import nullcontext
from datetime import timedelta
from hashlib import sha256
import json
import secrets
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from flask import Flask
import pyotp
import pytest

from tests.test_admin_chips import logged_in
from tests.test_admin_auth import otp, query
from core import admin_cli
from core.admin_passkeys import passkeys_enabled
from core.db import get_database
from core.passkey_migration import migrate, schema


pytestmark = pytest.mark.auth_database
BASE = "/api/admin/auth/passkeys"
ORIGIN = {"Origin":"http://localhost:5174"}
PRODUCTION_ORIGIN = "https://admin.bumbum.cc"
TEST_ORIGIN = "https://test.bumbum.cc"


def b64(value):
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class Authenticator:
    def __init__(self, origin):
        self.origin = origin
        self.rp_id = urlsplit(origin).hostname
        self.key_id = secrets.token_bytes(32)
        self.key = ec.generate_private_key(ec.SECP256R1())

    def credential(self, challenge, kind, response, origin):
        data = json.dumps({"type": kind, "challenge": challenge, "origin": origin}).encode()
        return {"challenge": challenge, "credential": {
            "type": "public-key", "id": b64(self.key_id), "rawId": b64(self.key_id),
            "response": {"clientDataJSON": b64(data), **response(data)},
        }}

    def registration(self, options, *, origin=None, rp_id=None):
        import cbor2

        self.user_handle = options["user"]["id"]
        numbers = self.key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1,
                            -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")})
        attested = (sha256((rp_id or self.rp_id).encode()).digest() + bytes([0x45]) + bytes(4)
                    + bytes(16) + len(self.key_id).to_bytes(2, "big") + self.key_id + cose)
        return self.credential(options["challenge"], "webauthn.create", lambda _: {
            "attestationObject": b64(cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": attested})),
        }, origin or self.origin)

    def assertion(self, options, *, counter=1, flags=0x05, origin=None, rp_id=None):
        data = sha256((rp_id or self.rp_id).encode()).digest() + bytes([flags]) + counter.to_bytes(4, "big")
        return self.credential(options["challenge"], "webauthn.get", lambda client_data: {
            "authenticatorData": b64(data),
            "signature": b64(self.key.sign(data + sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))),
            "userHandle": self.user_handle,
        }, origin or self.origin)


def password_login(app, account, origin):
    client = app.test_client()
    response = client.post("/api/admin/auth/login", base_url=origin, headers={"Origin": origin}, json={
        "username": account["username"], "password": account["password"], "code": otp(app, account),
    })
    assert response.status_code == 200
    session = client.get("/api/admin/auth/session", base_url=origin).json["data"]
    return client, {"Origin": origin, "X-CSRF-Token": session["csrf_token"]}


def options(client, mode, headers, origin):
    response = client.post(BASE + f"/{mode}/options", headers=headers, json={}, base_url=origin)
    assert response.status_code == 200
    return response.json["data"]["options"]


@pytest.fixture
def production_admin(auth_app, admin_account):
    auth_app.config.update(APP_ENV="production", HANGZHOU_SLOT="production",
                           ADMIN_ORIGIN=PRODUCTION_ORIGIN, TEST_ADMIN_PASSKEYS=False)
    return password_login(auth_app, admin_account, PRODUCTION_ORIGIN)


@pytest.mark.parametrize("slot,origin,testing,override,enabled", [
    ("test", TEST_ORIGIN, False, False, True),
    ("production", PRODUCTION_ORIGIN, False, False, True),
    ("production", TEST_ORIGIN, True, True, False),
    ("test", PRODUCTION_ORIGIN, True, True, False),
    ("", PRODUCTION_ORIGIN, False, False, False),
    ("unknown", PRODUCTION_ORIGIN, True, True, False),
    ("unknown", None, False, False, False),
    ("production", "https://nfc.bumbum.cc", True, True, False),
    ("production", "https://bumbum.cc", True, True, False),
    ("production", "https://admin.bumbum.cc.example.invalid", True, True, False),
    ("production", "http://admin.bumbum.cc", True, True, False),
    ("production", PRODUCTION_ORIGIN + "/", True, True, False),
    ("production", PRODUCTION_ORIGIN + ":443", True, True, False),
    ("", "http://localhost:5174", True, True, True),
    ("", "http://127.0.0.1:5174", True, True, True),
    ("", "http://localhost:5174", False, True, False),
    ("", "http://localhost:5174", True, False, False),
])
def test_passkey_site_allowlist(slot, origin, testing, override, enabled):
    app = Flask(__name__)
    app.config.update(HANGZHOU_SLOT=slot, ADMIN_ORIGIN=origin, TESTING=testing, TEST_ADMIN_PASSKEYS=override)
    with app.app_context():
        assert passkeys_enabled() is enabled


@pytest.mark.parametrize("slot,origin,rp_name", [
    ("", ORIGIN["Origin"], "BUMBUM Test"),
    ("test", TEST_ORIGIN, "BUMBUM Test"),
    ("production", PRODUCTION_ORIGIN, "BUMBUM"),
])
def test_passkey_uses_single_challenge_and_revoke_closes_sessions(auth_app, admin_account, slot, origin, rp_name):
    auth_app.config.update(HANGZHOU_SLOT=slot, ADMIN_ORIGIN=origin,
                           APP_ENV="production" if slot else "development", TEST_ADMIN_PASSKEYS=False)
    admin, headers = password_login(auth_app, admin_account, origin)
    visitor = auth_app.test_client()
    login_headers = {"Origin": origin}
    if not slot:
        assert visitor.post(BASE + "/login/options", headers=login_headers, json={}, base_url=origin).status_code == 404
        auth_app.config["TEST_ADMIN_PASSKEYS"] = True
    device = Authenticator(origin)
    register = options(admin, "register", headers, origin)
    assert register["rp"] == {"id": device.rp_id, "name": rp_name}
    assert register["authenticatorSelection"]["userVerification"] == "required"
    registration = device.registration(register)
    assert admin.post(BASE + "/register/finish", headers=headers, json=registration, base_url=origin).status_code == 200
    assert admin.post(BASE + "/register/finish", headers=headers, json=registration, base_url=origin).status_code == 409

    def assertion(**changes):
        return device.assertion(options(visitor, "login", login_headers, origin), **changes)

    assert visitor.post(BASE + "/login/finish", headers=login_headers, json=assertion(flags=0x01), base_url=origin).status_code == 401
    assert visitor.post(BASE + "/login/finish", headers=login_headers, json=assertion(origin="https://example.invalid"), base_url=origin).status_code == 401
    response = assertion()
    logged = visitor.post(BASE + "/login/finish", headers=login_headers, json=response, base_url=origin)
    assert logged.status_code == 200
    cookie = logged.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Path=/api/admin" in cookie and "Domain=" not in cookie
    assert ("Secure" in cookie) is bool(slot)
    assert logged.json == {"status": "ok", "data": {"authenticated": True, "expires_in": 28800}}
    assert visitor.get("/api/admin/auth/session", base_url=origin).status_code == 200
    assert visitor.post(BASE + "/login/finish", headers=login_headers, json=response, base_url=origin).status_code == 409
    assert visitor.post(BASE + "/login/finish", headers=login_headers, json=assertion(), base_url=origin).status_code == 401
    key_record = admin.get(BASE, base_url=origin).json["data"]["items"][0]
    assert admin.post(BASE + f"/{key_record['id']}/revoke", headers=headers, json={}, base_url=origin).status_code == 200
    assert admin.get("/api/admin/auth/session", base_url=origin).status_code == 401
    assert visitor.get("/api/admin/auth/session", base_url=origin).status_code == 401
    assert visitor.post(BASE + "/login/finish", headers=login_headers, json=assertion(counter=2), base_url=origin).status_code == 401
    audit = query(auth_app, "SELECT action FROM admin_audit ORDER BY id")
    assert [row["action"] for row in audit] == ["auth.passkey.register", "auth.passkey.revoke"]
    auth_app.test_clock[0] += timedelta(seconds=30)
    password_login(auth_app, admin_account, origin)


def test_production_rejects_test_origin_and_rp_for_registration_and_login(auth_app, production_admin):
    admin, headers = production_admin
    device = Authenticator(PRODUCTION_ORIGIN)
    for changed in ({"origin": TEST_ORIGIN}, {"rp_id": "test.bumbum.cc"}):
        payload = device.registration(options(admin, "register", headers, PRODUCTION_ORIGIN), **changed)
        assert admin.post(BASE + "/register/finish", headers=headers, json=payload, base_url=PRODUCTION_ORIGIN).status_code == 400
    payload = device.registration(options(admin, "register", headers, PRODUCTION_ORIGIN))
    assert admin.post(BASE + "/register/finish", headers=headers, json=payload, base_url=PRODUCTION_ORIGIN).status_code == 200
    visitor = auth_app.test_client()
    response = visitor.post(BASE + "/login/options", headers={"Origin": TEST_ORIGIN}, json={}, base_url=PRODUCTION_ORIGIN)
    assert response.status_code == 403
    for changed in ({"origin": TEST_ORIGIN}, {"rp_id": "test.bumbum.cc"}):
        payload = device.assertion(options(visitor, "login", headers, PRODUCTION_ORIGIN), **changed)
        assert visitor.post(BASE + "/login/finish", headers=headers, json=payload, base_url=PRODUCTION_ORIGIN).status_code == 401
    assert len(query(auth_app, "SELECT id FROM admin_session")) == 1
    assert [row["action"] for row in query(auth_app, "SELECT action FROM admin_audit")] == ["auth.passkey.register"]


def test_production_management_keeps_csrf_recent_session_and_challenge_boundaries(auth_app, admin_account, production_admin):
    admin, headers = production_admin
    device = Authenticator(PRODUCTION_ORIGIN)
    visitor = auth_app.test_client()
    assert visitor.post(BASE + "/register/options", headers=headers, json={}, base_url=PRODUCTION_ORIGIN).status_code == 401
    assert admin.post(BASE + "/register/options", headers={"Origin": PRODUCTION_ORIGIN}, json={}, base_url=PRODUCTION_ORIGIN).status_code == 403
    register = options(admin, "register", headers, PRODUCTION_ORIGIN)
    payload = device.registration(register)
    auth_app.test_clock[0] += timedelta(seconds=30)
    second, second_headers = password_login(auth_app, admin_account, PRODUCTION_ORIGIN)
    assert second.post(BASE + "/register/finish", headers=second_headers, json=payload, base_url=PRODUCTION_ORIGIN).status_code == 409
    assert admin.post(BASE + "/register/finish", headers=headers, json=payload, base_url=PRODUCTION_ORIGIN).status_code == 200
    key_id = admin.get(BASE, base_url=PRODUCTION_ORIGIN).json["data"]["items"][0]["id"]
    assert admin.post(BASE + f"/{key_id}/revoke", headers={"Origin": PRODUCTION_ORIGIN}, json={}, base_url=PRODUCTION_ORIGIN).status_code == 403
    register = options(admin, "register", headers, PRODUCTION_ORIGIN)
    login_options = options(visitor, "login", {"Origin": PRODUCTION_ORIGIN}, PRODUCTION_ORIGIN)
    auth_app.test_clock[0] += timedelta(minutes=2)
    assert admin.post(BASE + "/register/finish", headers=headers, json=device.registration(register), base_url=PRODUCTION_ORIGIN).status_code == 409
    assert visitor.post(BASE + "/login/finish", headers={"Origin": PRODUCTION_ORIGIN}, json=device.assertion(login_options), base_url=PRODUCTION_ORIGIN).status_code == 409
    auth_app.test_clock[0] += timedelta(minutes=8)
    for path in ("/register/options", f"/{key_id}/revoke"):
        response = admin.post(BASE + path, headers=headers, json={}, base_url=PRODUCTION_ORIGIN)
        assert response.status_code == 409 and response.json["code"] == "recent_login_required"
    assert query(auth_app, "SELECT revoked_at FROM admin_passkey")[0]["revoked_at"] is None


@pytest.mark.parametrize("command", ["reset-totp", "disable"])
def test_production_cli_revokes_passkeys_permanently(auth_app, admin_account, production_admin, monkeypatch, command):
    admin, headers = production_admin
    device = Authenticator(PRODUCTION_ORIGIN)
    payload = device.registration(options(admin, "register", headers, PRODUCTION_ORIGIN))
    assert admin.post(BASE + "/register/finish", headers=headers, json=payload, base_url=PRODUCTION_ORIGIN).status_code == 200
    visitor = auth_app.test_client()
    payload = device.assertion(options(visitor, "login", headers, PRODUCTION_ORIGIN))
    assert visitor.post(BASE + "/login/finish", headers=headers, json=payload, base_url=PRODUCTION_ORIGIN).status_code == 200
    account = admin_account
    answer = "y\n"
    if command == "reset-totp":
        secret = pyotp.random_base32()
        monkeypatch.setattr(admin_cli.pyotp, "random_base32", lambda: secret)
        monkeypatch.setattr(admin_cli, "show_qr", lambda _uri: nullcontext())
        account = {**admin_account, "secret": secret}
        answer += otp(auth_app, account) + "\n"
    result = auth_app.test_cli_runner().invoke(args=["admin", command, admin_account["username"]], input=answer)
    assert result.exit_code == 0, "隔离账号的服务器命令未完成"
    assert query(auth_app, "SELECT revoked_at FROM admin_passkey")[0]["revoked_at"] is not None
    assert admin.get("/api/admin/auth/session", base_url=PRODUCTION_ORIGIN).status_code == 401
    assert visitor.get("/api/admin/auth/session", base_url=PRODUCTION_ORIGIN).status_code == 401
    if command == "disable":
        query(auth_app, "UPDATE admin_user SET status='active'")
    payload = device.assertion(options(visitor, "login", headers, PRODUCTION_ORIGIN), counter=2)
    assert visitor.post(BASE + "/login/finish", headers=headers, json=payload, base_url=PRODUCTION_ORIGIN).status_code == 401
    auth_app.test_clock[0] += timedelta(seconds=30)
    password_login(auth_app, account, PRODUCTION_ORIGIN)


def test_passkey_migration_preserves_existing_admin_sessions(auth_app, logged_in):
    with auth_app.app_context():
        db = get_database()
        with db.cursor() as cursor:
            cursor.execute("DROP TABLE admin_passkey_challenge")
            cursor.execute("DROP TABLE admin_passkey")
            assert schema(cursor) == "missing"
        calls = []
        assert migrate(db,lambda:calls.append("backup"))
        assert not migrate(db,lambda:pytest.fail("重复执行无需备份"))
        assert calls == ["backup"]
    assert len(query(auth_app,"SELECT id FROM admin_session")) == 1
    assert logged_in[0].get("/api/admin/auth/session").status_code == 200
