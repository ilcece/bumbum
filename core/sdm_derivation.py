"""适配固定版本sdm-backend的逐卡派生；不包含全零兼容或K1派生。"""

import hashlib
import hmac

from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.cmac import CMAC

# 来源提交37585f0c76eded73798b936b17aa5e187075b78f；许可见本目录对应文件。
DIV_CONST2 = bytes.fromhex("536c6f744d61737465724b6579")
DIV_CONST3 = bytes.fromhex("446976426173654b6579")


def aes_cmac(key, message):
    value = CMAC(algorithms.AES(key))
    value.update(message)
    return value.finalize()


def derive_tag_key(master_key, uid, key_no):
    """正常输入保持上游字节规则；槽位1由独立全局配置提供。"""
    if len(master_key) != 16 or master_key == bytes(16) or len(uid) != 7 or key_no not in (0, 2, 3, 4):
        raise ValueError("逐卡派生参数不符合约定。")
    slot_key = hmac.new(master_key, DIV_CONST2 + bytes([key_no]), hashlib.sha256).digest()[:16]
    base_key = hmac.new(master_key, DIV_CONST3, hashlib.sha256).digest()
    diversified = hmac.new(base_key, uid, hashlib.sha256).digest()[:16]
    return aes_cmac(slot_key, b"\x01" + diversified)
