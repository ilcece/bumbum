"""管理员认证的配置与时间，不包含默认秘密。"""

from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from flask import current_app, request


class AuthUnavailable(Exception):
    """配置或加密资料不完整时关闭认证功能，不影响公开运行检查。"""


def utc_now():
    """数据库时间统一按UTC处理；测试可提供独立时钟。"""
    clock = current_app.config.get("AUTH_CLOCK")
    return clock() if clock else datetime.now(timezone.utc).replace(tzinfo=None)


def iso_time(value):
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def load_auth_settings(app):
    defaults = {
        "APP_ENV": os.getenv("APP_ENV", "production"),
        "ADMIN_ORIGIN": os.getenv("ADMIN_ORIGIN", "https://admin.bumbum.cc"),
        "ADMIN_TOTP_ISSUER": os.getenv("ADMIN_TOTP_ISSUER", "BUMBUM Admin"),
        "STORAGE_ENCRYPTION_KEY": os.getenv("STORAGE_ENCRYPTION_KEY", ""),
        "STORAGE_KEY_VERSION": os.getenv("STORAGE_KEY_VERSION", "v1"),
        "IP_HASH_KEY": os.getenv("IP_HASH_KEY", ""),
        "ADMIN_CLI_AUDIT_PATH": str(Path(app.root_path) / "logs/admin-operations.jsonl"),
    }
    for name, value in defaults.items():
        app.config.setdefault(name, value)


def secret_key(name):
    value = current_app.config.get(name, "")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise AuthUnavailable(f"请按管理员登录说明配置 {name}。")
    return bytes.fromhex(value)


def auth_settings():
    """仅开发环境的明确本机来源可关闭Cookie的HTTPS要求。"""
    config = current_app.config
    origin = config["ADMIN_ORIGIN"]
    try:
        if not isinstance(origin, str):
            raise ValueError
        parts = urlsplit(origin)
        parts.port
    except ValueError:
        raise AuthUnavailable("管理网页来源配置不合法。") from None
    local = parts.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        config["APP_ENV"] not in {"development", "production"}
        or parts.scheme not in {"http", "https"}
        or not parts.netloc or parts.path or parts.query or parts.fragment
        or parts.username or parts.password
        or (config["APP_ENV"] == "production" and (parts.scheme != "https" or local))
        or (parts.scheme == "http" and not local)
        or config["STORAGE_KEY_VERSION"] != "v1"
    ):
        raise AuthUnavailable("认证配置不符合当前环境，请检查运行说明。")
    storage_key = secret_key("STORAGE_ENCRYPTION_KEY")
    ip_key = secret_key("IP_HASH_KEY")
    if hmac.compare_digest(storage_key, ip_key):
        raise AuthUnavailable("存储密钥与来源指纹密钥必须分别生成，不能相同。")
    return {"origin": origin, "secure_cookie": parts.scheme == "https"}


def fingerprint(purpose, value, *, binary=False):
    result = hmac.new(secret_key("IP_HASH_KEY"), f"bumbum|{purpose}|{value}".encode(), hashlib.sha256)
    return result.digest() if binary else result.hexdigest()


def client_ip():
    """正式服务只信任本机Nginx覆写的来源；开发时不相信客户端自报头。"""
    source = request.remote_addr or "127.0.0.1"
    if current_app.config["APP_ENV"] == "production" and source in {"127.0.0.1", "::1"}:
        source = request.headers.get("X-Real-IP", source)
    try:
        address = ipaddress.ip_address(source)
        return str(getattr(address, "ipv4_mapped", None) or address)
    except ValueError:
        return "unknown"
