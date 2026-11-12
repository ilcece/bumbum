"""隔离库使用实际 WebAuthn 注册数据和签名检查登录、重放及撤销。"""

from base64 import urlsafe_b64encode
from hashlib import sha256
import json
import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
import pytest

from tests.test_admin_chips import logged_in
from tests.test_admin_auth import query
from core.db import get_database
from core.passkey_migration import migrate, schema


pytestmark = pytest.mark.auth_database
BASE = "/api/admin/auth/passkeys"
ORIGIN = {"Origin":"http://localhost:5174"}


def b64(value):
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def test_passkey_uses_single_challenge_and_revoke_closes_sessions(auth_app, logged_in, admin_account):
    import cbor2

    admin, headers = logged_in
    visitor = auth_app.test_client()
    assert visitor.post(BASE+"/login/options",headers=ORIGIN,json={}).status_code == 404
    auth_app.config["TEST_ADMIN_PASSKEYS"] = True
    register = admin.post(BASE+"/register/options",headers=headers,json={}).json["data"]["options"]
    assert register["rp"]["id"] == "localhost"
    assert register["authenticatorSelection"]["userVerification"] == "required"
    rp_hash = sha256(b"localhost").digest()
    key_id = secrets.token_bytes(32)
    key = ec.generate_private_key(ec.SECP256R1())
    numbers = key.public_key().public_numbers()
    cose = cbor2.dumps({1:2,3:-7,-1:1,-2:numbers.x.to_bytes(32,"big"),-3:numbers.y.to_bytes(32,"big")})

    def credential(challenge, kind, response, origin=ORIGIN["Origin"]):
        data = json.dumps({"type":kind,"challenge":challenge,"origin":origin}).encode()
        return {"challenge":challenge,"credential":{"type":"public-key","id":b64(key_id),"rawId":b64(key_id),
                "response":{"clientDataJSON":b64(data),**response(data)}}}

    attested = rp_hash + bytes([0x45]) + bytes(4) + bytes(16) + len(key_id).to_bytes(2,"big") + key_id + cose
    registration = credential(register["challenge"],"webauthn.create",lambda _: {
        "attestationObject":b64(cbor2.dumps({"fmt":"none","attStmt":{},"authData":attested})),
    })
    assert admin.post(BASE+"/register/finish",headers=headers,json=registration).status_code == 200
    assert admin.post(BASE+"/register/finish",headers=headers,json=registration).status_code == 409

    def assertion(counter, flags=0x05, origin=ORIGIN["Origin"]):
        challenge = visitor.post(BASE+"/login/options",headers=ORIGIN,json={}).json["data"]["options"]["challenge"]
        data = rp_hash + bytes([flags]) + counter.to_bytes(4,"big")
        return credential(challenge,"webauthn.get",lambda client_data: {
            "authenticatorData":b64(data),
            "signature":b64(key.sign(data+sha256(client_data).digest(),ec.ECDSA(hashes.SHA256()))),
            "userHandle":register["user"]["id"],
        },origin)

    assert visitor.post(BASE+"/login/finish",headers=ORIGIN,json=assertion(1,0x01)).status_code == 401
    assert visitor.post(BASE+"/login/finish",headers=ORIGIN,json=assertion(1,origin="https://example.invalid")).status_code == 401
    response = assertion(1)
    assert visitor.post(BASE+"/login/finish",headers=ORIGIN,json=response).status_code == 200
    assert visitor.get("/api/admin/auth/session").status_code == 200
    assert visitor.post(BASE+"/login/finish",headers=ORIGIN,json=response).status_code == 409
    assert visitor.post(BASE+"/login/finish",headers=ORIGIN,json=assertion(1)).status_code == 401
    key_record = admin.get(BASE).json["data"]["items"][0]
    assert admin.post(BASE+f"/{key_record['id']}/revoke",headers=headers,json={}).status_code == 200
    assert visitor.get("/api/admin/auth/session").status_code == 401
    assert visitor.post(BASE+"/login/finish",headers=ORIGIN,json=assertion(2)).status_code == 401


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
