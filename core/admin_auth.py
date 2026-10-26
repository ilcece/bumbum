"""单次登录、数据库会话和管理员请求防护。"""

from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets

from flask import Blueprint, current_app, g, jsonify, request
import pymysql
import pyotp
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash

from core.auth_settings import AuthUnavailable, auth_settings, client_ip, fingerprint, iso_time, load_auth_settings, utc_now
from core.csrf import valid_csrf
from core.db import get_database
from core.diagnostics import record_failure
from core.secret_storage import decrypt_totp_secret

COOKIE_NAME = "bumbum_admin_session"
COOKIE_PATH = "/api/admin"
SESSION_SECONDS = 8 * 60 * 60
DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_hex(32))
blueprint = Blueprint("admin_auth", __name__, url_prefix="/api/admin/auth")


class AuthRequestError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def failure(status, code, message):
    return jsonify(status="error", code=code, message=message), status


def token_hash(token):
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{64}", token):
        return None
    return hashlib.sha256(token.encode("ascii")).digest()


def matching_step(secret, code, now):
    """由成熟库验证每个允许时段，同时返回真正匹配的时段供数据库防重用。"""
    step = int(now.replace(tzinfo=timezone.utc).timestamp()) // 30
    try:
        totp = pyotp.TOTP(secret, digits=6, interval=30, digest=hashlib.sha1)
        for candidate in (step - 1, step, step + 1):
            when = datetime.fromtimestamp(candidate * 30, timezone.utc)
            if totp.verify(code, for_time=when):
                return candidate
    except (ValueError, TypeError) as error:
        raise AuthUnavailable("验证器资料不完整，请通过受控命令恢复。") from None
    return None


def request_json(fields, optional=(), *, max_bytes=8192):
    if request.content_length is not None and request.content_length > max_bytes:
        raise AuthRequestError(400, "invalid_param", "提交内容过大。")
    request.max_content_length = max_bytes
    try:
        data = request.get_json(silent=True)
    except RequestEntityTooLarge:
        raise AuthRequestError(400, "invalid_param", "提交内容过大。") from None
    if not isinstance(data, dict) or not set(fields) <= set(data) <= set(fields) | set(optional):
        raise AuthRequestError(400, "invalid_param", "提交字段不符合接口约定。")
    return data


def record_login(cursor, admin_id, username, result):
    cursor.execute(
        "INSERT INTO admin_login_event (admin_id, username_hash, result, ip_hash, user_agent) VALUES (%s,%s,%s,%s,%s)",
        (admin_id, fingerprint("username", username.strip().casefold(), binary=True), result,
         fingerprint("ip", client_ip()), request.headers.get("User-Agent", "")[:512] or None),
    )


def revoke_sessions(cursor, admin_id, now):
    cursor.execute("UPDATE admin_session SET revoked_at=%s WHERE admin_id=%s AND revoked_at IS NULL", (now, admin_id))


def current_session():
    digest = token_hash(request.cookies.get(COOKIE_NAME))
    if digest is None:
        return None
    with get_database().cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute(
            "SELECT s.id, s.admin_id, s.csrf_token, s.expires_at, s.revoked_at, u.status, u.totp_enabled "
            "FROM admin_session s JOIN admin_user u ON u.id=s.admin_id WHERE s.token_hash=%s", (digest,),
        )
        row = cursor.fetchone()
    if not row or row["revoked_at"] is not None or row["expires_at"] <= utc_now() or row["status"] != "active" or row["totp_enabled"] != 1:
        return None
    return row


def lock_admin_session(cursor):
    """管理写入事务先锁账号再锁会话，避免权限撤销后仍保存业务变更。"""
    admin_id, session_id = g.admin_session["admin_id"], g.admin_session["id"]
    cursor.execute("SELECT status,totp_enabled FROM admin_user WHERE id=%s FOR UPDATE", (admin_id,))
    admin = cursor.fetchone()
    cursor.execute("SELECT revoked_at,expires_at FROM admin_session WHERE id=%s AND admin_id=%s FOR UPDATE", (session_id, admin_id))
    session = cursor.fetchone()
    if (
        not admin or admin["status"] != "active" or admin["totp_enabled"] != 1
        or not session or session["revoked_at"] is not None or session["expires_at"] <= utc_now()
    ):
        raise AuthRequestError(401, "unauthorized", "登录已失效，请重新登录。")


def login_attempt(data):
    username, password, code = data["username"], data["password"], data["code"]
    if (
        not isinstance(username, str) or not 1 <= len(username) <= 64 or not username.strip()
        or not isinstance(password, str) or not 1 <= len(password) <= 128
        or not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code)
    ):
        raise AuthRequestError(400, "invalid_param", "请填写账号、密码和6位验证码。")
    connection, now = get_database(), utc_now()
    connection.begin()
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT * FROM admin_user WHERE username=%s FOR UPDATE", (username,))
        admin = cursor.fetchone()
        if not admin:
            check_password_hash(DUMMY_PASSWORD_HASH, password)
            record_login(cursor, None, username, "failed")
            connection.commit()
            return None, 401
        admin_id = admin["id"]
        if admin["status"] != "active" or admin["totp_enabled"] != 1:
            check_password_hash(DUMMY_PASSWORD_HASH, password)
            record_login(cursor, admin_id, username, "failed")
            connection.commit()
            return None, 401
        if admin["locked_until"] and admin["locked_until"] > now:
            record_login(cursor, admin_id, username, "locked")
            connection.commit()
            return None, 429
        attempts = 0 if admin["locked_until"] else admin["failed_login_attempts"]
        valid_password = check_password_hash(admin["password_hash"], password)
        step = None
        if valid_password:
            step = matching_step(decrypt_totp_secret(admin["totp_secret_encrypted"], admin_id), code, now)
        if step is None or (admin["totp_last_step"] is not None and step <= admin["totp_last_step"]):
            attempts += 1
            locked = now + timedelta(minutes=15) if attempts >= 5 else None
            cursor.execute("UPDATE admin_user SET failed_login_attempts=%s, locked_until=%s WHERE id=%s", (attempts, locked, admin_id))
            record_login(cursor, admin_id, username, "locked" if locked else "failed")
            connection.commit()
            return None, 429 if locked else 401
        token, csrf_token = secrets.token_hex(32), secrets.token_hex(32)
        expires = now + timedelta(seconds=SESSION_SECONDS)
        cursor.execute("UPDATE admin_user SET totp_last_step=%s, last_login_at=%s, failed_login_attempts=0, locked_until=NULL WHERE id=%s", (step, now, admin_id))
        old = token_hash(request.cookies.get(COOKIE_NAME))
        if old:
            cursor.execute("UPDATE admin_session SET revoked_at=%s WHERE token_hash=%s AND revoked_at IS NULL", (now, old))
        cursor.execute("INSERT INTO admin_session (admin_id,token_hash,csrf_token,expires_at) VALUES (%s,%s,%s,%s)", (admin_id, token_hash(token), csrf_token, expires))
        record_login(cursor, admin_id, username, "success")
        connection.commit()
        return (token, expires), 200


@blueprint.post("/login")
def login():
    result, status = login_attempt(request_json({"username", "password", "code"}))
    if status == 401:
        return failure(401, "unauthorized", "登录未通过，请核对账号、密码和当前验证码。")
    if status == 429:
        return failure(429, "rate_limited", "登录尝试过多，请稍后再试。")
    token, expires = result
    response = jsonify(status="ok", data={"authenticated": True, "expires_in": SESSION_SECONDS})
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, expires=expires.replace(tzinfo=timezone.utc),
                        httponly=True, secure=g.auth_settings["secure_cookie"], samesite="Strict", path=COOKIE_PATH)
    return response


@blueprint.get("/session")
def session():
    row = g.admin_session
    return jsonify(status="ok", data={"authenticated": True, "expires_at": iso_time(row["expires_at"]), "csrf_token": row["csrf_token"]})


@blueprint.post("/logout")
def logout():
    request_json(set())
    connection = get_database()
    with connection.cursor() as cursor:
        cursor.execute("UPDATE admin_session SET revoked_at=%s WHERE id=%s AND revoked_at IS NULL", (utc_now(), g.admin_session["id"]))
    connection.commit()
    response = jsonify(status="ok", data={"logged_out": True})
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, secure=g.auth_settings["secure_cookie"], httponly=True, samesite="Strict")
    return response


def init_auth(app):
    load_auth_settings(app)
    app.register_blueprint(blueprint)

    @app.before_request
    def protect_admin_request():
        # 未注册的地址仍返回404；已注册的管理接口统一保护，后续业务也会经过这里。
        if not request.endpoint or not request.path.startswith("/api/admin/"):
            return None
        settings = auth_settings()
        g.auth_settings = settings
        origin = request.headers.get("Origin")
        if (origin and origin != settings["origin"]) or (request.method not in {"GET", "HEAD"} and origin != settings["origin"]):
            raise AuthRequestError(403, "forbidden", "请求必须来自允许的管理网页。")
        if request.method == "OPTIONS":
            if request.headers.get("Access-Control-Request-Method") not in request.url_rule.methods:
                raise AuthRequestError(403, "forbidden", "不允许这种跨网页请求。")
            headers = {part.strip().lower() for part in request.headers.get("Access-Control-Request-Headers", "").split(",") if part.strip()}
            if not headers.issubset({"content-type", "x-csrf-token"}):
                raise AuthRequestError(403, "forbidden", "不允许这些请求头。")
            return "", 204
        if request.args and (request.blueprint == "admin_auth" or request.method not in {"GET", "HEAD"}):
            raise AuthRequestError(400, "invalid_param", "此接口不接收查询参数。")
        if request.method not in {"GET", "HEAD"} and request.mimetype != "application/json":
            raise AuthRequestError(400, "invalid_param", "请使用JSON提交。")
        if request.endpoint == "admin_auth.login":
            return None
        row = current_session()
        if row is None:
            raise AuthRequestError(401, "unauthorized", "登录已失效，请重新登录。")
        g.admin_session = row
        if request.method not in {"GET", "HEAD"} and not valid_csrf(row["csrf_token"], request.headers.get("X-CSRF-Token")):
            raise AuthRequestError(403, "csrf_failed", "操作口令已失效，请重新读取登录状态。")

    @app.after_request
    def admin_cors(response):
        if request.endpoint and request.path.startswith("/api/admin/") and current_app.config["APP_ENV"] == "development" and request.headers.get("Origin") == current_app.config["ADMIN_ORIGIN"]:
            response.headers["Access-Control-Allow-Origin"] = current_app.config["ADMIN_ORIGIN"]
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.vary.add("Origin")
            if request.method == "OPTIONS":
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
                response.headers["Access-Control-Allow-Methods"] = ", ".join(sorted(request.url_rule.methods - {"OPTIONS", "HEAD"}))
        return response

    @app.errorhandler(AuthRequestError)
    def request_error(error):
        return failure(error.status, error.code, error.message)

    @app.errorhandler(AuthUnavailable)
    def unavailable(_error):
        return failure(503, "service_unavailable", "认证配置或验证器资料未就绪，请按管理员登录说明检查。")

    @app.errorhandler(pymysql.MySQLError)
    def database_error(error):
        return jsonify(status="error", code="service_unavailable", message="数据库暂时无法完成操作，请稍后再试。", error_id=record_failure(error)), 503
