"""测试后台的 WebAuthn 登记、登录及撤销。"""

from datetime import timedelta
from hashlib import sha256
import json
import re
from secrets import token_bytes
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, jsonify
import pymysql

from core.admin_auth import (
    AuthRequestError, SESSION_SECONDS, lock_admin_session, login_response,
    new_session, record_login, request_json, revoke_sessions,
)
from core.auth_settings import client_ip, fingerprint, iso_time, utc_now
from core.public_account import limited, row, transaction


blueprint = Blueprint("admin_passkeys", __name__, url_prefix="/api/admin/auth/passkeys")


def passkeys_enabled():
    config = current_app.config
    origin = config["ADMIN_ORIGIN"]
    return ((config["HANGZHOU_SLOT"] == "test" and origin == "https://test.bumbum.cc")
            or (config["TESTING"] and config.get("TEST_ADMIN_PASSKEYS") is True
                and urlsplit(origin).hostname in {"localhost", "127.0.0.1"}))


@blueprint.before_request
def test_only():
    if not passkeys_enabled():
        raise AuthRequestError(404, "not_found", "当前站点未启用通行密钥。")


def ok(**data):
    return jsonify(status="ok", data=data)


def rp_id():
    return urlsplit(g.auth_settings["origin"]).hostname


def account_handle(admin_id):
    return admin_id.to_bytes(8, "big")


def recent_session():
    remaining = g.admin_session["expires_at"] - utc_now()
    if remaining < timedelta(seconds=SESSION_SECONDS - 600):
        raise AuthRequestError(409, "recent_login_required", "请重新登录，再于 10 分钟内管理通行密钥。")


def save_challenge(challenge, session_id=None):
    now = utc_now()
    with transaction() as cursor:
        cursor.execute("DELETE FROM admin_passkey_challenge WHERE expires_at<=%s ORDER BY expires_at LIMIT 100", (now,))
        cursor.execute("INSERT INTO admin_passkey_challenge(challenge_hash,session_id,expires_at) VALUES (%s,%s,%s)",
                       (sha256(challenge).digest(),session_id,now + timedelta(minutes=2)))


def consume_challenge(value, session_id=None):
    from webauthn import base64url_to_bytes

    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", value):
        raise AuthRequestError(400, "invalid_param", "通行密钥请求不完整，请重试。")
    challenge = base64url_to_bytes(value)
    with transaction() as cursor:
        cursor.execute("DELETE FROM admin_passkey_challenge WHERE challenge_hash=%s AND session_id<=>%s AND expires_at>%s",
                       (sha256(challenge).digest(),session_id,utc_now()))
        valid = cursor.rowcount == 1
    if not valid:
        raise AuthRequestError(409, "passkey_challenge_used", "通行密钥请求已使用或超时，请重试。")
    return challenge


def key_audit(cursor, action, admin_id):
    labels = {"register":"登记通行密钥","revoke":"撤销通行密钥"}
    cursor.execute("INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,'admin_account',%s,%s,%s)",
                   (admin_id,"auth.passkey."+action,str(admin_id),
                    json.dumps({"operation":labels[action],"summary":labels[action],"outcome":"已完成"},ensure_ascii=False),
                    fingerprint("ip",client_ip())))


def revoke_all_passkeys(cursor, admin_id, now):
    if passkeys_enabled():
        cursor.execute("UPDATE admin_passkey SET revoked_at=%s WHERE admin_id=%s AND revoked_at IS NULL",(now,admin_id))


@blueprint.get("")
def credentials():
    with transaction() as cursor:
        cursor.execute("SELECT id,created_at,last_used_at FROM admin_passkey WHERE admin_id=%s AND revoked_at IS NULL ORDER BY id",
                       (g.admin_session["admin_id"],))
        return ok(items=[{**key,"created_at":iso_time(key["created_at"]),
                          "last_used_at":iso_time(key["last_used_at"]) if key["last_used_at"] else None}
                         for key in cursor.fetchall()])


@blueprint.post("/register/options")
def register_options():
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import AuthenticatorAttachment, AuthenticatorSelectionCriteria, ResidentKeyRequirement, UserVerificationRequirement

    request_json(set())
    recent_session()
    limited("admin-passkey-register",g.admin_session["admin_id"],10)
    with transaction() as cursor:
        lock_admin_session(cursor)
        admin = row(cursor,"SELECT username FROM admin_user WHERE id=%s",(g.admin_session["admin_id"],))
    options = generate_registration_options(
        rp_id=rp_id(), rp_name="BUMBUM Test", user_name=admin["username"], challenge=token_bytes(32),
        user_id=account_handle(g.admin_session["admin_id"]), timeout=120000,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    save_challenge(options.challenge,g.admin_session["id"])
    return ok(options=json.loads(options_to_json(options)))


@blueprint.post("/register/finish")
def register_finish():
    from webauthn import verify_registration_response
    from webauthn.helpers.exceptions import WebAuthnException

    payload = request_json({"challenge","credential"},max_bytes=32768)
    recent_session()
    challenge = consume_challenge(payload["challenge"],g.admin_session["id"])
    try:
        result = verify_registration_response(credential=payload["credential"],
            expected_challenge=challenge, expected_rp_id=rp_id(), expected_origin=g.auth_settings["origin"],
            require_user_verification=True)
    except (WebAuthnException,ValueError,TypeError):
        raise AuthRequestError(400,"invalid_passkey","通行密钥登记未通过，请重试。") from None
    admin_id = g.admin_session["admin_id"]
    try:
        with transaction() as cursor:
            lock_admin_session(cursor)
            cursor.execute("INSERT INTO admin_passkey(admin_id,credential_hash,public_key,sign_count,created_at) VALUES (%s,%s,%s,%s,%s)",
                           (admin_id,sha256(result.credential_id).digest(),result.credential_public_key,result.sign_count,utc_now()))
            key_audit(cursor,"register",admin_id)
    except pymysql.IntegrityError as error:
        if error.args[0] != 1062:
            raise
        raise AuthRequestError(409,"duplicate_passkey","该通行密钥已登记过，请在设备上选择新建。") from None
    return ok(registered=True)


@blueprint.post("/login/options")
def login_options():
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import UserVerificationRequirement

    request_json(set())
    limited("admin-passkey-login",client_ip(),20)
    options = generate_authentication_options(rp_id=rp_id(),timeout=120000,challenge=token_bytes(32),
                                               user_verification=UserVerificationRequirement.REQUIRED)
    save_challenge(options.challenge)
    return ok(options=json.loads(options_to_json(options)))


@blueprint.post("/login/finish")
def login_finish():
    from webauthn import verify_authentication_response
    from webauthn.helpers import parse_authentication_credential_json
    from webauthn.helpers.exceptions import WebAuthnException

    payload = request_json({"challenge","credential"},max_bytes=32768)
    challenge = consume_challenge(payload["challenge"])
    error = AuthRequestError(401,"invalid_passkey","通行密钥验证未通过，可重试或用动态码登录。")
    try:
        assertion = parse_authentication_credential_json(payload["credential"])
    except (WebAuthnException,ValueError,TypeError):
        raise error from None
    credential_hash = sha256(assertion.raw_id).digest()
    now = utc_now()
    with transaction() as cursor:
        identity = row(cursor,"SELECT admin_id FROM admin_passkey WHERE credential_hash=%s",(credential_hash,))
        if not identity:
            raise error
        admin_id = identity["admin_id"]
        admin = row(cursor,"SELECT username,status,totp_enabled,locked_until FROM admin_user WHERE id=%s FOR UPDATE",(admin_id,))
        key = row(cursor,"SELECT id,public_key,sign_count,revoked_at FROM admin_passkey WHERE admin_id=%s AND credential_hash=%s FOR UPDATE",(admin_id,credential_hash))
        if (not admin or admin["status"]!="active" or not admin["totp_enabled"]
                or (admin["locked_until"] and admin["locked_until"]>now)
                or not key or key["revoked_at"] or assertion.response.user_handle != account_handle(admin_id)):
            raise error
        try:
            result = verify_authentication_response(credential=assertion, expected_challenge=challenge,
                expected_rp_id=rp_id(), expected_origin=g.auth_settings["origin"], require_user_verification=True,
                credential_public_key=key["public_key"],credential_current_sign_count=key["sign_count"])
        except (WebAuthnException,ValueError,TypeError):
            raise error from None
        cursor.execute("UPDATE admin_passkey SET sign_count=%s,last_used_at=%s WHERE id=%s",(result.new_sign_count,now,key["id"]))
        cursor.execute("UPDATE admin_user SET last_login_at=%s,failed_login_attempts=0,locked_until=NULL WHERE id=%s",(now,admin_id))
        session = new_session(cursor,admin_id,now)
        record_login(cursor,admin_id,admin["username"],"success")
    return login_response(*session)


@blueprint.post("/<int:key_id>/revoke")
def revoke(key_id):
    request_json(set())
    recent_session()
    admin_id = g.admin_session["admin_id"]
    with transaction() as cursor:
        lock_admin_session(cursor)
        now = utc_now()
        cursor.execute("UPDATE admin_passkey SET revoked_at=%s WHERE id=%s AND admin_id=%s AND revoked_at IS NULL",
                       (now,key_id,admin_id))
        if cursor.rowcount != 1:
            raise AuthRequestError(404,"not_found","通行密钥不存在或已撤销。")
        revoke_sessions(cursor,admin_id,now)
        key_audit(cursor,"revoke",admin_id)
    return ok(revoked=True)
