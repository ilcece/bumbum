"""受控服务器命令：创建账号、重置验证器和停用账号。"""

from functools import wraps
import getpass
import json
import os
from pathlib import Path
import re

import click
from flask import current_app
from flask.cli import AppGroup
import pymysql
import pyotp
from werkzeug.security import generate_password_hash

from core.admin_auth import matching_step, revoke_sessions
from core.admin_qr import show_qr
from core.auth_settings import AuthUnavailable, auth_settings, iso_time, utc_now
from core.db import get_database
from core.secret_storage import encrypt_totp_secret

admin_commands = AppGroup("admin", help="管理员账号的服务器操作，不提供网页恢复入口。")


def audit(action, username, result, *, committed=False):
    """独立记录服务器操作，不伪装成某个网页登录管理员。"""
    reasons = {"create": "首次设置管理员与验证器", "reset-totp": "更换或恢复验证器", "disable": "停用管理员账号"}
    record = {"time": iso_time(utc_now()), "operator": getpass.getuser(), "action": action,
              "reason": reasons[action], "username": username, "result": result}
    try:
        path = Path(current_app.config["ADMIN_CLI_AUDIT_PATH"])
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        if committed:
            message = "数据库操作已完成，但完成记录写入失败，请检查受限日志。"
        elif result == "started":
            message = "操作记录无法写入，尚未开始修改账号。"
        else:
            message = "操作未确认完成且结果记录写入失败，请检查账号状态和受限日志。"
        raise click.ClickException(message) from None


def cli_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except AuthUnavailable as error:
            raise click.ClickException(str(error)) from None
        except pymysql.IntegrityError as error:
            message = "账号已存在，未覆盖。" if error.args[0] == 1062 else "数据库约束拒绝此操作，未覆盖已有账号。"
            raise click.ClickException(message) from None
        except pymysql.MySQLError:
            raise click.ClickException("数据库操作未能确认完成，请检查服务和操作记录，不要盲目重复。") from None
    return wrapped


def validate_username(username):
    if not isinstance(username, str) or not 1 <= len(username) <= 64 or username != username.strip() or not username:
        raise click.ClickException("账号须为1到64个字符，首尾不能有空格。")


def enroll(username):
    """用本机临时页面扫码，终端隐藏输入验证码，最多尝试三次。"""
    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=current_app.config["ADMIN_TOTP_ISSUER"])
    with show_qr(uri):
        for _ in range(3):
            code = click.prompt("输入手机当前6位验证码", hide_input=True)
            if re.fullmatch(r"[0-9]{6}", code):
                step = matching_step(secret, code, utc_now())
                if step is not None:
                    return secret, step
            click.echo("验证码未通过，请核对手机时间或等待下一组验证码。")
    raise click.ClickException("验证未完成，账号不能通过本次设置登录；可重新执行命令。")


@admin_commands.command("create")
@click.argument("username")
@cli_errors
def create_admin(username):
    """创建管理员；验证码确认前不保存账号或验证器秘密。"""
    validate_username(username)
    auth_settings()
    connection = get_database()
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM admin_user WHERE username=%s", (username,))
        existing = cursor.fetchone()
    connection.rollback()
    if existing:
        raise click.ClickException("账号已存在，未覆盖；需要更换验证器时使用重置命令。")
    password = click.prompt("设置密码（12到128个字符）", hide_input=True, confirmation_prompt="请再次输入密码")
    if not 12 <= len(password) <= 128:
        raise click.ClickException("新密码长度须为12到128个字符。")
    password_hash = generate_password_hash(password)
    audit("create", username, "started")
    try:
        secret, step = enroll(username)
        connection.begin()
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO admin_user (username,password_hash) VALUES (%s,%s)", (username, password_hash))
            admin_id = cursor.lastrowid
            encrypted = encrypt_totp_secret(secret, admin_id)
            cursor.execute("UPDATE admin_user SET totp_secret_encrypted=%s,totp_enabled=1,totp_last_step=%s WHERE id=%s", (encrypted, step, admin_id))
        connection.commit()
    except (click.Abort, click.ClickException, pymysql.MySQLError, AuthUnavailable):
        connection.rollback()
        audit("create", username, "incomplete")
        raise
    audit("create", username, "committed", committed=True)
    click.echo("账号已创建。请等Authenticator切换到下一组验证码后，再到网页登录。")


@admin_commands.command("reset-totp")
@click.argument("username")
@cli_errors
def reset_totp(username):
    """先撤销旧验证器和所有会话，再确认新验证器；中断时保持不能登录。"""
    validate_username(username)
    auth_settings()
    click.confirm(f"确认停用 {username} 的旧验证器、退出全部登录并重新设置？", abort=True)
    audit("reset-totp", username, "started")
    connection, now = get_database(), utc_now()
    connection.begin()
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT id FROM admin_user WHERE username=%s FOR UPDATE", (username,))
        row = cursor.fetchone()
        if not row:
            connection.rollback()
            raise click.ClickException("账号不存在，未修改任何账号。")
        admin_id = row["id"]
        cursor.execute("UPDATE admin_user SET totp_enabled=0,totp_secret_encrypted=NULL,totp_last_step=NULL,failed_login_attempts=0,locked_until=NULL WHERE id=%s", (admin_id,))
        revoke_sessions(cursor, admin_id, now)
    connection.commit()
    try:
        secret, step = enroll(username)
        connection.begin()
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT totp_enabled,totp_secret_encrypted FROM admin_user WHERE id=%s FOR UPDATE", (admin_id,))
            row = cursor.fetchone()
            if not row or row["totp_enabled"] or row["totp_secret_encrypted"] is not None:
                raise click.ClickException("账号已被其他设置操作更新，本次未覆盖；请先确认账号状态。")
            cursor.execute("UPDATE admin_user SET totp_enabled=1,totp_secret_encrypted=%s,totp_last_step=%s WHERE id=%s", (encrypt_totp_secret(secret, admin_id), step, admin_id))
        connection.commit()
    except (click.Abort, click.ClickException, pymysql.MySQLError, AuthUnavailable):
        connection.rollback()
        audit("reset-totp", username, "incomplete")
        raise
    audit("reset-totp", username, "committed", committed=True)
    click.echo("验证器已重置，旧登录均失效。请等下一组验证码再登录；此命令不会修改密码或启用已停用账号。")


@admin_commands.command("disable")
@click.argument("username")
@cli_errors
def disable_admin(username):
    """停用账号并撤销全部会话，即使存储密钥丢失仍可停用。"""
    validate_username(username)
    click.confirm(f"确认停用 {username} 并退出其全部登录？", abort=True)
    audit("disable", username, "started")
    connection = get_database()
    connection.begin()
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM admin_user WHERE username=%s FOR UPDATE", (username,))
        row = cursor.fetchone()
        if not row:
            connection.rollback()
            raise click.ClickException("账号不存在。")
        cursor.execute("UPDATE admin_user SET status='disabled' WHERE id=%s", (row[0],))
        revoke_sessions(cursor, row[0], utc_now())
    connection.commit()
    audit("disable", username, "committed", committed=True)
    click.echo("账号已停用，全部旧登录已失效。")
