"""准备本地测试配置；已有 .env 原样保留，不输出密码。"""

import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def prepare_local_config(root=ROOT):
    """仅生成两个本地数据库密码，不生成生产凭证、芯片或登录密钥。"""
    target = root / ".env"
    replacements = {
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "33306",
        "DB_USER": "bumbum_dev",
        "DB_PASSWORD": secrets.token_hex(24),
        "DEV_DB_ROOT_PASSWORD": secrets.token_hex(24),
    }
    lines = []
    for line in (root / ".env.example").read_text(encoding="utf-8").splitlines():
        key = line.partition("=")[0]
        lines.append(f"{key}={replacements[key]}" if key in replacements else line)
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("已有 .env，保留原配置，未覆盖。")
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as config:
        config.write("\n".join(lines) + "\n")
    print("本地测试配置已准备好。密码仅保存在本机 .env，未显示或上传。")
    return True


if __name__ == "__main__":
    # 建表文件已公开在仓库中，允许容器用户读取；秘密配置仍使用仅本人可读权限。
    (ROOT / "db/schema.sql").chmod(0o644)
    prepare_local_config()
