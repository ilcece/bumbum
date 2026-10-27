"""芯片密钥生成、受控查看与配置确认；不连接卡片、不签发用户凭证。"""

import hmac
import json
import os
import re

from flask import current_app, g
import pymysql

from core.admin_auth import AuthRequestError, lock_admin_session
from core.auth_settings import AuthUnavailable, client_ip, fingerprint, utc_now
from core.chip_registry import CHIP_VIEW, chip_view
from core.db import get_database
from core.sdm_derivation import derive_tag_key
from core.sdm_verification import InvalidReading, InvalidLayout, decode_reading, valid_mac
from core.secret_storage import decrypt_chip_keys, encrypt_chip_keys

URL_TEMPLATE = "https://nfc.bumbum.cc/tap?picc_data={picc}&cmac={cmac}"
CONFIG_NAMES = ("MASTER_KEY_FASHION", "MASTER_KEY_JEWELRY", "SDM_META_KEY_V1", "SDM_META_KEY_VERSION")


class ChipKeyUnavailable(Exception):
    """配置故障与认证故障分开提示，不泄露秘密或底层异常。"""


def init_chip_keys(app):
    for name in CONFIG_NAMES:
        app.config.setdefault(name, os.getenv(name, "v1" if name == "SDM_META_KEY_VERSION" else ""))


def configured_key(name):
    value = current_app.config.get(name, "")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", value) or value == "0" * 32:
        raise AuthUnavailable(f"请配置合格的{name}；密钥功能暂不可用。")
    return bytes.fromhex(value)


def target_keys(project, uid):
    if project not in {"fashion", "jewelry"} or current_app.config["SDM_META_KEY_VERSION"] != "v1":
        raise AuthUnavailable("芯片项目或SDM配置版本不支持。")
    root = configured_key("MASTER_KEY_" + project.upper())
    meta = configured_key("SDM_META_KEY_V1")
    other = current_app.config.get("MASTER_KEY_JEWELRY" if project == "fashion" else "MASTER_KEY_FASHION", "")
    if hmac.compare_digest(root, meta) or (isinstance(other, str) and other.lower() == root.hex()):
        raise AuthUnavailable("项目根密钥与其他项目或全局K1必须独立。")
    raw_uid = bytes.fromhex(uid.replace(":", ""))
    keys = {f"K{slot}": derive_tag_key(root, raw_uid, slot).hex().upper() for slot in (0, 2, 3, 4)}
    keys["K1"] = meta.hex().upper()
    return {f"K{slot}": keys[f"K{slot}"] for slot in range(5)}


def verify_reading(reading, keys, uid):
    """固定AES、C7布局和零长度MAC输入，不自动猜测其他配置。"""
    try:
        candidate, counter = decode_reading(reading, bytes.fromhex(keys["K1"]))
    except InvalidReading:
        raise AuthRequestError(400, "invalid_param", "读数须包含完整十六进制picc_data和cmac。") from None
    except InvalidLayout:
        raise AuthRequestError(400, "verification_failed", "读数与该芯片的目标配置不匹配，请核对卡片和配置。") from None
    if not hmac.compare_digest(candidate, uid) or not valid_mac(reading, bytes.fromhex(keys["K2"]), candidate, counter):
        raise AuthRequestError(400, "verification_failed", "读数与该芯片的目标配置不匹配，请核对卡片和配置。")
    return counter


def checked_saved_keys(stored, chip):
    """核对保存的五个槽位与当前目标配置，供配置和用户验证共同使用。"""
    expected = target_keys(chip["project"], chip["chip_uid"])
    saved = decrypt_chip_keys(stored, chip["id"])
    if stored["key_version"] != "v1" or stored["master_key_version"] != "v1" or not isinstance(saved, dict) or set(saved) != set(expected) or any(
        not isinstance(saved[name], str) or not hmac.compare_digest(saved[name], expected[name]) for name in expected
    ):
        raise AuthUnavailable("保存的密钥与当前配置不一致，请停止操作，不要覆盖记录或重配卡片。")
    return saved


def audit(cursor, action, chip, extra=None):
    detail = {"item_id": chip["item_id"], "project": chip["project"], "key_version": "v1", **(extra or {})}
    cursor.execute(
        "INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,%s,%s,%s,%s)",
        (g.admin_session["admin_id"], action, "chip", str(chip["id"]), json.dumps(detail), fingerprint("ip", client_ip())),
    )


def lock_chip(cursor, chip_id):
    # 先查关联以确定锁目标，再按物品→芯片锁定重查，防止关联变化后使用旧项目。
    cursor.execute("SELECT item_id FROM chip WHERE id=%s", (chip_id,))
    initial = cursor.fetchone()
    if initial is None:
        raise AuthRequestError(404, "not_found", "芯片不存在。")
    if initial["item_id"] is None:
        raise AuthRequestError(409, "invalid_state", "请先绑定物品并确定项目。")
    cursor.execute("SELECT id,project_id,status FROM item WHERE id=%s FOR UPDATE", (initial["item_id"],))
    item = cursor.fetchone()
    cursor.execute("SELECT * FROM chip WHERE id=%s FOR UPDATE", (chip_id,))
    chip = cursor.fetchone()
    if not chip or not item or chip["item_id"] != item["id"] or chip["project_id"] != item["project_id"] or chip["chip_status"] != "bound" or item["status"] == "archived":
        raise AuthRequestError(409, "invalid_state", "芯片关联或状态已改变，请重新查询。")
    cursor.execute("SELECT code FROM project WHERE id=%s", (chip["project_id"],))
    chip["project"] = cursor.fetchone()["code"]
    return chip


def key_operation(chip_id, operation, readings=None):
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            lock_admin_session(cursor)
            chip = lock_chip(cursor, chip_id)
            cursor.execute("SELECT * FROM chip_key WHERE chip_id=%s FOR UPDATE", (chip_id,))
            stored = cursor.fetchone()
            if operation == "generate" and (stored or chip["provisioned_at"] is not None or chip["last_verified_counter"] is not None):
                raise AuthRequestError(409, "already_exists", "已有密钥或配置记录，不可覆盖或重新生成。")
            if operation != "generate" and stored is None:
                raise AuthRequestError(404, "not_found", "尚未生成密钥，请先生成。")
            keys = target_keys(chip["project"], chip["chip_uid"])
            if operation == "generate":
                envelope = encrypt_chip_keys(keys, chip_id)
                cursor.execute(
                    "INSERT INTO chip_key(chip_id,encrypted_keys,nonce,dek_ciphertext,dek_nonce,storage_key_version,key_version,master_key_version) VALUES (%s,%s,%s,%s,%s,%s,'v1','v1')",
                    (chip_id, *(envelope[name] for name in ("encrypted_keys", "nonce", "dek_ciphertext", "dek_nonce", "storage_key_version"))),
                )
                audit(cursor, "chip.generate_keys", chip)
                result = {"chip_id": chip_id, "generated": True, "key_version": "v1"}
            else:
                saved = checked_saved_keys(stored, chip)
                if operation == "view":
                    audit(cursor, "chip.view_keys", chip)
                    result = {"chip_uid": chip["chip_uid"], "keys": saved, "sun_url_template": URL_TEMPLATE}
                else:
                    if chip["provisioned_at"] is not None:
                        raise AuthRequestError(409, "already_configured", "已有配置完成记录，请按UID查询；本入口不重配或重置计数。")
                    counters = [verify_reading(value, saved, chip["chip_uid"]) for value in readings]
                    if counters[1] <= counters[0] or (chip["last_verified_counter"] is not None and counters[0] <= chip["last_verified_counter"]) or counters[1] == 0xFFFFFF:
                        raise AuthRequestError(409, "invalid_counter", "请提供依次取得的两条新读数；计数须递增且尚未耗尽。")
                    cursor.execute("UPDATE chip SET provisioned_at=%s,last_verified_counter=%s WHERE id=%s", (utc_now(), counters[1], chip_id))
                    audit(cursor, "chip.confirm_provisioning", chip, {"system_checks": "two_sun_readings", "management_confirmed_by_admin": True})
                    cursor.execute(CHIP_VIEW + " WHERE c.id=%s", (chip_id,))
                    result = chip_view(cursor.fetchone())
        connection.commit()
        return result
    except Exception as error:
        try:
            connection.rollback()
        except pymysql.MySQLError:
            pass
        if isinstance(error, AuthUnavailable):
            raise ChipKeyUnavailable from None
        raise
