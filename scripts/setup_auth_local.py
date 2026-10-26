"""为默认本机测试环境补齐认证配置，可显式选择首次准备密钥功能。"""

from pathlib import Path
import re
import secrets
import sys
import argparse

from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def prepare_auth_config(root=ROOT, *, chip_keys=False):
    """仅补齐空项；保留已有秘密，不用于丢失配置后的恢复。"""
    target = root / ".env"
    if not target.is_file():
        raise ValueError("请先按本地运行说明执行数据库配置准备步骤。")
    values = dotenv_values(target)
    if (
        values.get("DB_HOST") not in {"127.0.0.1", "localhost"}
        or values.get("DB_USER") != "bumbum_dev"
        or values.get("DB_NAME") != "bumbum_digital"
        or values.get("APP_ENV") not in {None, "", "development"}
        or values.get("STORAGE_KEY_VERSION") != "v1"
    ):
        raise ValueError("此脚本只用于默认本机测试环境，未修改配置；生产配置需单独准备。")
    names = {"STORAGE_ENCRYPTION_KEY": 32, "IP_HASH_KEY": 32}
    if chip_keys:
        if values.get("SDM_META_KEY_VERSION") not in {None, "", "v1"}:
            raise ValueError("仅支持SDM v1，未修改配置。")
        names.update(MASTER_KEY_FASHION=16, MASTER_KEY_JEWELRY=16, SDM_META_KEY_V1=16)
    for name, size in names.items():
        existing = values.get(name)
        if existing and (not re.fullmatch(r"[0-9a-fA-F]{%d}" % (size * 2), existing) or (chip_keys and existing == "0" * (size * 2))):
            raise ValueError(f"{name} 格式不合法，未覆盖。请先检查该项配置。")
    generated = {name: values.get(name) or secrets.token_hex(size) for name, size in names.items()}
    if chip_keys and len({generated[name].lower() for name in ("MASTER_KEY_FASHION", "MASTER_KEY_JEWELRY", "SDM_META_KEY_V1")}) != 3:
        raise ValueError("项目根密钥与全局K1必须各自独立，未修改配置。")
    target.chmod(0o600)
    for name in names:
        if not values.get(name):
            set_key(target, name, generated[name], quote_mode="never")
    if not values.get("APP_ENV"):
        set_key(target, "APP_ENV", "development", quote_mode="never")
    if chip_keys and not values.get("SDM_META_KEY_VERSION"):
        set_key(target, "SDM_META_KEY_VERSION", "v1", quote_mode="never")
    print("本机认证配置已准备，已有密钥未覆盖；没有创建管理员或生成芯片密钥。" if not chip_keys else "本机密钥功能配置已准备，已有值未覆盖；未生成逐卡密钥、未访问数据库或卡片。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="补齐本机测试配置，不覆盖已有秘密。")
    parser.add_argument("--chip-keys", action="store_true", help="首次准备本机密钥功能的独立根密钥和全局K1；不用于丢失秘密后的恢复")
    args = parser.parse_args()
    try:
        prepare_auth_config(chip_keys=args.chip_keys)
    except (ValueError, OSError) as error:
        print(str(error) if isinstance(error, ValueError) else "无法写入本机配置，请检查文件权限。", file=sys.stderr)
        sys.exit(1)
