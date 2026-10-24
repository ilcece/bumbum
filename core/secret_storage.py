"""按技术附录的两层AES-GCM格式保护验证器秘密。"""

import base64
import json
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app

from core.auth_settings import AuthUnavailable, secret_key


def aad(admin_id, version, layer):
    return f"bumbum|admin_user|{admin_id}|totp_secret|{version}|{layer}".encode("utf-8")


def encrypt_totp_secret(secret, admin_id):
    storage_key = secret_key("STORAGE_ENCRYPTION_KEY")
    version = current_app.config["STORAGE_KEY_VERSION"]
    if version != "v1":
        raise AuthUnavailable("不支持的存储密钥版本。")
    dek, nonce, dek_nonce = secrets.token_bytes(32), secrets.token_bytes(12), secrets.token_bytes(12)
    values = {
        "ciphertext": AESGCM(dek).encrypt(nonce, secret.encode("ascii"), aad(admin_id, version, "data")),
        "nonce": nonce,
        "dek_ciphertext": AESGCM(storage_key).encrypt(dek_nonce, dek, aad(admin_id, version, "dek")),
        "dek_nonce": dek_nonce,
    }
    envelope = {
        "format_version": 1,
        "algorithm": "AES-256-GCM",
        "storage_key_version": version,
        **{key: base64.b64encode(value).decode("ascii") for key, value in values.items()},
    }
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")


def decrypt_totp_secret(encrypted, admin_id):
    try:
        envelope = json.loads(bytes(encrypted).decode("utf-8"))
        expected = {"format_version", "algorithm", "storage_key_version", "ciphertext", "nonce", "dek_ciphertext", "dek_nonce"}
        if (
            not isinstance(envelope, dict) or set(envelope) != expected
            or type(envelope["format_version"]) is not int or envelope["format_version"] != 1
            or envelope["algorithm"] != "AES-256-GCM"
            or envelope["storage_key_version"] != current_app.config["STORAGE_KEY_VERSION"]
            or envelope["storage_key_version"] != "v1"
        ):
            raise ValueError
        values = {name: base64.b64decode(envelope[name], validate=True) for name in ("ciphertext", "nonce", "dek_ciphertext", "dek_nonce")}
        if len(values["nonce"]) != 12 or len(values["dek_nonce"]) != 12 or len(values["dek_ciphertext"]) != 48 or len(values["ciphertext"]) < 17:
            raise ValueError
        version = envelope["storage_key_version"]
        dek = AESGCM(secret_key("STORAGE_ENCRYPTION_KEY")).decrypt(values["dek_nonce"], values["dek_ciphertext"], aad(admin_id, version, "dek"))
        return AESGCM(dek).decrypt(values["nonce"], values["ciphertext"], aad(admin_id, version, "data")).decode("ascii")
    except (ValueError, TypeError, KeyError, UnicodeError, InvalidTag) as error:
        raise AuthUnavailable("验证器加密资料无法验证，请检查存储密钥或通过受控命令恢复。") from None
