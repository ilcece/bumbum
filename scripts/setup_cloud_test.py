"""生成独立香港测试配置和Nginx文件；不安装软件、启动服务或覆盖已有秘密。"""

import argparse
import ipaddress
import os
from pathlib import Path
import re
import secrets

ROOT = Path(__file__).resolve().parents[1]


def prepare(root, admin_ip, username):
    address = ipaddress.ip_address(admin_ip)
    if not address.is_global or address.is_multicast:
        raise ValueError("请填写电脑当前的公网出口IP，不能填内网或文档示例地址。")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", username):
        raise ValueError("本次云测试账号名请使用1到64位英文字母、数字、点、下划线或短横线。")
    folder = root / ".cloud-test"
    if folder.is_symlink() or (root / ".env.cloud-test").is_symlink():
        raise ValueError("配置路径不能是软链接；未覆盖现有文件。")
    # 建表文件是仓库公开资料，允许数据库容器读取；秘密配置仍只允许本人读取。
    schema = root / "db/schema.sql"
    if schema.is_symlink() or not schema.is_file():
        raise ValueError("缺少仓库原有的db/schema.sql，或路径异常；请核对仓库。")
    schema.chmod(0o644)
    folder.mkdir(mode=0o700, exist_ok=True)
    values = {
        "APP_ENV": "production", "ADMIN_ORIGIN": "https://test.bumbum.cc",
        "ADMIN_TOTP_ISSUER": "BUMBUM-Test", "STORAGE_KEY_VERSION": "v1",
        "DB_HOST": "127.0.0.1", "DB_PORT": "33307", "DB_USER": "bumbum_test", "DB_NAME": "bumbum_digital",
        "DB_PASSWORD": secrets.token_hex(24), "CLOUD_DB_ROOT_PASSWORD": secrets.token_hex(24),
        "STORAGE_ENCRYPTION_KEY": secrets.token_hex(32), "IP_HASH_KEY": secrets.token_hex(32),
        "WEBHOOK_ADMIN_USERNAME": username, "WEBHOOK_SHARED_SECRET": secrets.token_hex(32),
    }
    try:
        descriptor = os.open(root / ".env.cloud-test", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("已有云测试配置，原密码和密钥全部保留；账号名沿用原配置。")
    else:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("# 独立云测试配置；不要分享或上传。\n")
            stream.write("".join(f"{key}={value}\n" for key, value in values.items()))
        print("已创建独立云测试配置，未显示秘密；没有修改本机.env。")
    template = (root / "deploy/cloud_test/nginx-https.conf.template").read_text(encoding="utf-8")
    target = folder / "nginx-https.conf"
    if target.is_symlink():
        raise ValueError("生成文件不能是软链接。")
    target.write_text(template.replace("__ADMIN_IP__", str(address)), encoding="utf-8")
    print("管理IP配置已生成；需要按手册安装并检查Nginx后才会生效。")


def main():
    parser = argparse.ArgumentParser(description="准备香港云测试配置；已有秘密原样保留。")
    parser.add_argument("--admin-ip", required=True, help="电脑当前公网出口IP")
    parser.add_argument("--admin-name", default="cece", help="云测试管理员名，默认cece")
    args = parser.parse_args()
    try:
        prepare(ROOT, args.admin_ip, args.admin_name)
    except (ValueError, OSError) as error:
        print("未完成：" + (str(error) if isinstance(error, ValueError) else "文件无法创建，请检查目录权限；未删除原配置或数据。"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
