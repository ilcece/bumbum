"""只为已准备好的本机测试配置补齐认证所需的两个独立密钥。"""

from pathlib import Path
import re
import secrets
import sys

from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]


def prepare_auth_config(root=ROOT):
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
    for name in ("STORAGE_ENCRYPTION_KEY", "IP_HASH_KEY"):
        existing = values.get(name)
        if existing and not re.fullmatch(r"[0-9a-fA-F]{64}", existing):
            raise ValueError(f"{name} 格式不合法，未覆盖。请先检查该项配置。")
    target.chmod(0o600)
    for name in ("STORAGE_ENCRYPTION_KEY", "IP_HASH_KEY"):
        if not values.get(name):
            set_key(target, name, secrets.token_hex(32), quote_mode="never")
    if not values.get("APP_ENV"):
        set_key(target, "APP_ENV", "development", quote_mode="never")
    print("本机认证配置已准备，已有密钥未覆盖；没有创建管理员或生成芯片密钥。")


if __name__ == "__main__":
    try:
        prepare_auth_config()
    except (ValueError, OSError) as error:
        print(str(error) if isinstance(error, ValueError) else "无法写入本机配置，请检查文件权限。", file=sys.stderr)
        sys.exit(1)
