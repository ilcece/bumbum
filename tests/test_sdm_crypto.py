"""公开向量与合成秘密验证派生及芯片信封，不使用真实卡凭证。"""

import secrets

from flask import Flask
import pytest

from core.auth_settings import AuthUnavailable
from core.chip_keys import verify_reading
from core.sdm_derivation import derive_tag_key
from core.secret_storage import decrypt_chip_keys, encrypt_chip_keys


@pytest.mark.parametrize("root,uid,expected", [
    ("C9EB67DF090AFF47C3B19A2516680B9D", "03030303030303", "85f7cc459a5b4b2f5d1a5019ded61c88"),
    ("B95F4C27E3D0BC333792EA968545217F", "05050505050505", "89ae686de793fdf48057ee6e78505cfc"),
])
def test_upstream_public_answers(root, uid, expected):
    assert derive_tag_key(bytes.fromhex(root), bytes.fromhex(uid), 2).hex() == expected


@pytest.mark.parametrize("root,uid,slot", [(bytes(16), bytes(7), 2), (bytes(15), bytes(7), 2), (b"x"*16, bytes(4), 2), (b"x"*16, bytes(7), 1)])
def test_generation_rejects_factory_and_bad_inputs(root, uid, slot):
    with pytest.raises(ValueError):
        derive_tag_key(root, uid, slot)


def test_purpose_and_project_separation():
    uid = bytes.fromhex("04010203040506")
    values = {derive_tag_key(bytes([n])*16, uid, slot) for n in (1, 2) for slot in (0, 2, 3, 4)}
    assert len(values) == 8
    assert derive_tag_key(b"x"*16, uid, 2) != derive_tag_key(b"x"*16, bytes.fromhex("04010203040507"), 2)


def test_nxp_an12196_public_sun_answer():
    # 官方零密钥向量只用于原语验证；生成入口仍拒绝零密钥。
    assert verify_reading({"picc_data": "EF963FF7828658A599F3041510671E88", "cmac": "94EED9EE65337086"}, {"K1": "00"*16, "K2": "00"*16}, "04:DE:5F:1E:AC:C0:40") == 61


@pytest.mark.parametrize("damage", ["swap", "encrypted_keys", "nonce", "dek_ciphertext", "dek_nonce", "storage_key_version"])
def test_chip_envelope_rejects_damage_and_other_identity(damage):
    app = Flask(__name__)
    app.config.update(STORAGE_ENCRYPTION_KEY=secrets.token_hex(32), STORAGE_KEY_VERSION="v1")
    with app.app_context():
        keys = {f"K{n}": secrets.token_hex(16).upper() for n in range(5)}
        row = encrypt_chip_keys(keys, 7)
        assert decrypt_chip_keys(row, 7) == keys
        assert all(value.encode() not in row["encrypted_keys"] for value in keys.values())
        if damage == "storage_key_version": row[damage] = "v2"
        elif damage != "swap":
            value = bytearray(row[damage]); value[0] ^= 1; row[damage] = bytes(value)
        with pytest.raises(AuthUnavailable): decrypt_chip_keys(row, 8 if damage == "swap" else 7)
