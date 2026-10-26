"""不启动数据库即可检查来源、输入、防冒用和秘密保存规则。"""

import base64
import json
import secrets

from dotenv import dotenv_values
import pytest

from app import create_app
from core.auth_settings import AuthUnavailable
from core.csrf import valid_csrf
from core.secret_storage import decrypt_totp_secret, encrypt_totp_secret
from scripts.setup_auth_local import prepare_auth_config


def test_local_chip_config_only_fills_empty_values(tmp_path, capsys):
    content = "DB_HOST=127.0.0.1\nDB_USER=bumbum_dev\nDB_NAME=bumbum_digital\nSTORAGE_KEY_VERSION=v1\n"
    target = tmp_path / ".env"
    target.write_text(content)
    prepare_auth_config(tmp_path, chip_keys=True)
    first = target.read_bytes()
    values = dotenv_values(target)
    assert values["SDM_META_KEY_VERSION"] == "v1"
    assert len({values[name] for name in ("MASTER_KEY_FASHION", "MASTER_KEY_JEWELRY", "SDM_META_KEY_V1")}) == 3
    assert all(len(values[name]) == 32 for name in ("MASTER_KEY_FASHION", "MASTER_KEY_JEWELRY", "SDM_META_KEY_V1"))
    prepare_auth_config(tmp_path, chip_keys=True)
    assert target.read_bytes() == first
    assert all(values[name] not in capsys.readouterr().out for name in ("MASTER_KEY_FASHION", "MASTER_KEY_JEWELRY", "SDM_META_KEY_V1"))


@pytest.mark.parametrize("setting", ["DB_HOST=remote.example", "SDM_META_KEY_VERSION=v2", "MASTER_KEY_FASHION=00000000000000000000000000000000", "MASTER_KEY_FASHION=bad"])
def test_local_chip_config_rejects_before_any_write(tmp_path, setting):
    values = {"DB_HOST":"127.0.0.1", "DB_USER":"bumbum_dev", "DB_NAME":"bumbum_digital", "STORAGE_KEY_VERSION":"v1", "SDM_META_KEY_VERSION":"v1"}
    name, value = setting.split("=",1); values[name] = value
    target = tmp_path / ".env"; target.write_text("".join(f"{name}={value}\n" for name,value in values.items()))
    before = target.read_bytes()
    with pytest.raises(ValueError): prepare_auth_config(tmp_path, chip_keys=True)
    assert target.read_bytes() == before


@pytest.fixture
def secured_app():
    return create_app({"TESTING": True, "APP_ENV": "development", "ADMIN_ORIGIN": "http://localhost:5174",
                       "STORAGE_ENCRYPTION_KEY": secrets.token_hex(32), "STORAGE_KEY_VERSION": "v1", "IP_HASH_KEY": secrets.token_hex(32), "DB_USER": "", "DB_PASSWORD": ""})


@pytest.mark.parametrize("origin", [None, "null", "https://other.example", "http://localhost:5174.other.example"])
def test_login_rejects_missing_or_wrong_origin(secured_app, origin):
    headers = {"Origin": origin} if origin else {}
    response = secured_app.test_client().post("/api/admin/auth/login", json={"username":"cece","password":"test-only","code":"012345"}, headers=headers)
    assert response.status_code == 403
    assert response.json["code"] == "forbidden"
    assert "Set-Cookie" not in response.headers


@pytest.mark.parametrize("body", [None, [], {}, {"username":"cece","password":"test","code":123456}, {"username":"cece","password":"test","code":"12345"}, {"username":"cece","password":"test","code":"123456","extra":True}])
def test_login_rejects_invalid_or_extra_fields(secured_app, body):
    response = secured_app.test_client().post("/api/admin/auth/login", json=body, headers={"Origin":"http://localhost:5174"})
    assert response.status_code == 400
    assert response.json["code"] == "invalid_param"


def test_form_submission_is_not_accepted(secured_app):
    response = secured_app.test_client().post("/api/admin/auth/login", data={"username":"cece"}, headers={"Origin":"http://localhost:5174"})
    assert response.status_code == 400


def test_cookie_missing_is_unauthorized(secured_app):
    response = secured_app.test_client().get("/api/admin/auth/session")
    assert response.status_code == 401


def test_configuration_missing_fails_closed_and_keeps_health_available(secured_app):
    secured_app.config["IP_HASH_KEY"] = ""
    client = secured_app.test_client()
    assert client.get("/api/health").status_code == 200
    response = client.post("/api/admin/auth/login", json={"username":"cece","password":"test","code":"012345"}, headers={"Origin":"http://localhost:5174"})
    assert response.status_code == 503
    assert "Set-Cookie" not in response.headers


def test_preflight_allows_only_admin_origin_and_declared_headers(secured_app):
    client = secured_app.test_client()
    headers={"Origin":"http://localhost:5174","Access-Control-Request-Method":"POST","Access-Control-Request-Headers":"Content-Type, X-CSRF-Token"}
    response=client.options("/api/admin/auth/logout",headers=headers)
    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == headers["Origin"]
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    response=client.options("/api/admin/auth/logout",headers={**headers,"Access-Control-Request-Headers":"X-Unapproved"})
    assert response.status_code == 403


def test_csrf_is_bound_to_one_session_and_rejects_missing_values():
    one, two = secrets.token_hex(32), secrets.token_hex(32)
    assert valid_csrf(one, one)
    assert not valid_csrf(one, two)
    assert not valid_csrf(one, None)
    assert not valid_csrf(one, "")


def test_envelope_is_encrypted_and_bound_to_admin(secured_app):
    with secured_app.app_context():
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        encoded = encrypt_totp_secret(secret, 7)
        assert secret.encode() not in encoded
        assert decrypt_totp_secret(encoded, 7) == secret
        with pytest.raises(AuthUnavailable):
            decrypt_totp_secret(encoded, 8)
        envelope=json.loads(encoded)
        ciphertext=bytearray(base64.b64decode(envelope["ciphertext"]))
        ciphertext[0] ^= 1
        envelope["ciphertext"]=base64.b64encode(ciphertext).decode()
        with pytest.raises(AuthUnavailable):
            decrypt_totp_secret(json.dumps(envelope).encode(),7)
        secured_app.config["STORAGE_ENCRYPTION_KEY"] = secrets.token_hex(32)
        with pytest.raises(AuthUnavailable):
            decrypt_totp_secret(encoded,7)


def test_local_auth_preparation_preserves_existing_keys_and_chip_key(tmp_path):
    path=tmp_path/".env"
    path.write_text("DB_HOST=127.0.0.1\nDB_USER=bumbum_dev\nDB_NAME=bumbum_digital\nSTORAGE_KEY_VERSION=v1\nSTORAGE_ENCRYPTION_KEY=\nIP_HASH_KEY=\nSDM_META_KEY_V1=\n")
    prepare_auth_config(tmp_path)
    before=path.read_bytes()
    values=dotenv_values(path)
    assert len(bytes.fromhex(values["STORAGE_ENCRYPTION_KEY"])) == 32
    assert values["STORAGE_ENCRYPTION_KEY"] != values["IP_HASH_KEY"]
    assert values["SDM_META_KEY_V1"] == ""
    assert values["APP_ENV"] == "development"
    prepare_auth_config(tmp_path)
    assert path.read_bytes() == before


def test_local_auth_preparation_rejects_production_config(tmp_path):
    path=tmp_path/".env"
    path.write_text("DB_HOST=production.example\nDB_USER=production\n")
    before=path.read_bytes()
    with pytest.raises(ValueError):
        prepare_auth_config(tmp_path)
    assert path.read_bytes() == before


def test_oversized_login_body_is_rejected(secured_app):
    response=secured_app.test_client().post("/api/admin/auth/login",json={"username":"cece","password":"x"*9000,"code":"012345"},headers={"Origin":"http://localhost:5174"})
    assert response.status_code==400 and "Set-Cookie" not in response.headers


def test_authentication_keys_cannot_be_reused(secured_app):
    secured_app.config["IP_HASH_KEY"]=secured_app.config["STORAGE_ENCRYPTION_KEY"]
    assert secured_app.test_client().get("/api/admin/auth/session").status_code==503
