"""接收NFC.cool扫描回调，只登记真实格式的UID，不写卡或修改已有记录。"""

from datetime import datetime
import hmac
import os
import re

from flask import Blueprint, current_app, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, failure, request_json
from core.auth_settings import AuthUnavailable, secret_key
from core.chip_registry import normalize_uid, save_chip
from core.db import get_database

blueprint = Blueprint("scan_webhook", __name__)


def init_scan(app):
    from core.scan_capture import init_capture
    for name in ("WEBHOOK_ADMIN_USERNAME", "WEBHOOK_SHARED_SECRET"):
        app.config.setdefault(name, os.getenv(name, ""))
    app.register_blueprint(blueprint)
    init_capture(app)


def deny(reason):
    # 仅记录固定诊断文字和匹配标志，不记录收到的账号、密码或认证头。
    current_app.logger.warning("扫码认证诊断：%s", reason)
    raise AuthRequestError(401, "webhook_auth_failed", "扫码凭证无效，或对应管理员未启用。")


def credential_owner():
    """独立扫码密码不授予网页登录权限；空配置关闭入口，不产生默认凭证。"""
    username = current_app.config["WEBHOOK_ADMIN_USERNAME"]
    password = current_app.config["WEBHOOK_SHARED_SECRET"]
    if (
        not isinstance(username, str) or not 1 <= len(username) <= 64 or username != username.strip()
        or not isinstance(password, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", password)
    ):
        raise AuthUnavailable("扫描回调配置尚未就绪。")
    secret_key("IP_HASH_KEY")
    auth = request.authorization
    if auth is None or auth.type.lower() != "basic" or auth.username is None or auth.password is None:
        deny("认证头存在=%s，Basic凭证可解析=否" % ("是" if "Authorization" in request.headers else "否"))
    user_ok = hmac.compare_digest(auth.username.encode("utf-8"), username.encode("utf-8"))
    password_ok = hmac.compare_digest(auth.password.encode("utf-8"), password.encode("utf-8"))
    if not (user_ok and password_ok):
        deny("用户名匹配=%s，密码匹配=%s，密码字符数=%d" %
             ("是" if user_ok else "否", "是" if password_ok else "否", len(auth.password)))
    return username


def scan_data():
    if request.args or request.mimetype != "application/json":
        raise AuthRequestError(400, "invalid_param", "请提交JSON，扫描回调不接收网址参数。")
    data = request_json({"identifier"}, {"content", "date"})
    uid = normalize_uid(data["identifier"])
    if "content" in data and (not isinstance(data["content"], str) or len(data["content"]) > 4096):
        raise AuthRequestError(400, "invalid_param", "扫描内容须为最多4096个字符的文字。")
    if "date" in data:
        try:
            value = data["date"]
            if not isinstance(value, str) or len(value) > 64 or "T" not in value:
                raise ValueError
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                raise ValueError
        except ValueError:
            raise AuthRequestError(400, "invalid_param", "扫描时间须为含时区的ISO 8601时间。") from None
    return uid


@blueprint.errorhandler(AuthRequestError)
def scan_error(error):
    response, status = failure(error.status, error.code, error.message)
    if status == 401:
        # NFC.cool先等401认证挑战，再携带已保存的用户名和密码重发。
        response.headers["WWW-Authenticate"] = 'Basic realm="bumbum-scan"'
    return response, status


@blueprint.post("/api/webhook/admin/scan")
def scan():
    username = credential_owner()
    uid = scan_data()
    connection = get_database()
    connection.begin()
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        # 和网页写入、账号停用保持相同锁顺序；禁用完成后不再允许新登记。
        cursor.execute("SELECT id,status,totp_enabled FROM admin_user WHERE username=%s FOR UPDATE", (username,))
        admin = cursor.fetchone()
        if not admin or admin["status"] != "active" or admin["totp_enabled"] != 1:
            deny("凭证匹配，但账号不存在、停用或未完成验证器设置")
        chip, is_new = save_chip(cursor, uid, admin_id=admin["id"], source="nfc_cool")
    connection.commit()
    return jsonify(status="ok", data={"chip_uid": chip["chip_uid"], "is_new": is_new})
