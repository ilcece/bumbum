"""两种入口共用固定AES/C7布局的解密与防伪码核对，不写数据库。"""

import hmac
import re

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from core.sdm_derivation import aes_cmac


class InvalidReading(ValueError):
    """输入长度、编码或字段集合不符合固定读数格式。"""


class InvalidLayout(ValueError):
    """解密后的布局不属于当前已核验的配置。"""


def validate_reading(reading):
    if not isinstance(reading, dict) or set(reading) != {"picc_data", "cmac"}:
        raise InvalidReading
    for name, length in (("picc_data", 32), ("cmac", 16)):
        if not isinstance(reading[name], str) or not re.fullmatch(r"[0-9a-fA-F]{%d}" % length, reading[name]):
            raise InvalidReading


def decode_reading(reading, meta_key):
    """解密只能得到候选身份，调用者必须继续验签。"""
    validate_reading(reading)
    decryptor = Cipher(algorithms.AES(meta_key), modes.CBC(bytes(16))).decryptor()
    plain = decryptor.update(bytes.fromhex(reading["picc_data"])) + decryptor.finalize()
    if plain[0] != 0xC7:
        raise InvalidLayout
    uid = ":".join(f"{value:02X}" for value in plain[1:8])
    return uid, int.from_bytes(plain[8:11], "little")


def valid_mac(reading, key, uid, counter):
    raw_uid = bytes.fromhex(uid.replace(":", ""))
    session = aes_cmac(key, bytes.fromhex("3CC300010080") + raw_uid + counter.to_bytes(3, "little"))
    return hmac.compare_digest(aes_cmac(session, b"")[1::2], bytes.fromhex(reading["cmac"]))
