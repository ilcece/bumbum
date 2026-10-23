"""在专属临时MySQL中验证完整登录、退出、恢复和并发行为。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets

import pymysql
import pyotp
import pytest

from core import admin_cli
from core.admin_auth import COOKIE_NAME
from core.db import get_database
from core.secret_storage import decrypt_totp_secret

pytestmark = pytest.mark.auth_database
ORIGIN = {"Origin": "http://localhost:5174"}


def otp(app, account):
    when = app.test_clock[0].replace(tzinfo=timezone.utc)
    return pyotp.TOTP(account["secret"]).at(when)


def login(client, app, account, **changes):
    payload={"username":account["username"],"password":account["password"],"code":otp(app,account),**changes}
    return client.post("/api/admin/auth/login",json=payload,headers=ORIGIN)


def query(app, sql, args=()):
    with app.app_context():
        connection=get_database()
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql,args)
            result=cursor.fetchall() if cursor.description else []
        connection.commit()
        return result


def test_login_cookie_session_refresh_and_logout(auth_app,admin_account):
    client=auth_app.test_client()
    response=login(client,auth_app,admin_account)
    assert response.status_code==200
    assert response.json=={"status":"ok","data":{"authenticated":True,"expires_in":28800}}
    cookie=response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Path=/api/admin" in cookie
    assert "Secure" not in cookie and "Domain=" not in cookie
    first=client.get("/api/admin/auth/session")
    assert first.status_code==200
    csrf=first.json["data"]["csrf_token"]
    assert re.fullmatch('[0-9a-f]{64}',csrf)
    assert client.get("/api/admin/auth/session").json==first.json
    assert first.headers["Cache-Control"]=="no-store"
    token=client.get_cookie(COOKIE_NAME,path="/api/admin").value
    stored=query(auth_app,"SELECT token_hash,csrf_token FROM admin_session")[0]
    assert stored["token_hash"]==hashlib.sha256(token.encode()).digest()
    assert stored["csrf_token"]==csrf and token!=csrf
    assert token not in json.dumps(first.json)
    response=client.post("/api/admin/auth/logout",json={},headers={**ORIGIN,"X-CSRF-Token":csrf})
    assert response.status_code==200 and response.json["data"]["logged_out"]
    assert client.get("/api/admin/auth/session").status_code==401
    client.set_cookie(COOKIE_NAME,token,path="/api/admin")
    assert client.get("/api/admin/auth/session").status_code==401


def test_wrong_credentials_and_unknown_account_are_indistinguishable(auth_app,admin_account):
    client=auth_app.test_client()
    one=login(client,auth_app,admin_account,password="wrong-test-only")
    two=login(client,auth_app,admin_account,username="unknown-account")
    assert one.status_code==two.status_code==401
    assert one.json==two.json
    assert "Set-Cookie" not in one.headers
    assert query(auth_app,"SELECT failed_login_attempts FROM admin_user")[0]["failed_login_attempts"]==1
    events=query(auth_app,"SELECT admin_id,result,username_hash,ip_hash FROM admin_login_event ORDER BY id")
    assert events[1]["admin_id"] is None
    assert all(len(event["username_hash"])==32 and len(event["ip_hash"])==64 for event in events)


def test_lock_after_five_failures_does_not_extend_and_expires(auth_app,admin_account):
    client=auth_app.test_client()
    statuses=[login(client,auth_app,admin_account,password="wrong").status_code for _ in range(5)]
    assert statuses==[401,401,401,401,429]
    locked=query(auth_app,"SELECT locked_until,failed_login_attempts FROM admin_user")[0]
    assert locked["failed_login_attempts"]==5
    auth_app.test_clock[0]+=timedelta(minutes=1)
    assert login(client,auth_app,admin_account).status_code==429
    assert query(auth_app,"SELECT locked_until FROM admin_user")[0]["locked_until"]==locked["locked_until"]
    auth_app.test_clock[0]+=timedelta(minutes=15)
    assert login(client,auth_app,admin_account).status_code==200
    result=query(auth_app,"SELECT locked_until,failed_login_attempts FROM admin_user")[0]
    assert result=={"locked_until":None,"failed_login_attempts":0}


def test_old_totp_cannot_issue_second_session(auth_app,admin_account):
    client=auth_app.test_client()
    assert login(client,auth_app,admin_account).status_code==200
    assert login(auth_app.test_client(),auth_app,admin_account).status_code==401
    assert query(auth_app,"SELECT COUNT(*) AS count FROM admin_session")[0]["count"]==1


def test_parallel_same_totp_only_creates_one_session(auth_app,admin_account):
    def attempt(_):
        return login(auth_app.test_client(),auth_app,admin_account).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(attempt,range(2)))
    assert sorted(statuses)==[200,401]
    assert query(auth_app,"SELECT COUNT(*) AS count FROM admin_session")[0]["count"]==1


def test_successful_relogin_revokes_old_cookie(auth_app,admin_account):
    client=auth_app.test_client()
    assert login(client,auth_app,admin_account).status_code==200
    old=client.get_cookie(COOKIE_NAME,path="/api/admin").value
    auth_app.test_clock[0]+=timedelta(seconds=30)
    assert login(client,auth_app,admin_account).status_code==200
    assert client.get_cookie(COOKIE_NAME,path="/api/admin").value!=old
    other=auth_app.test_client()
    other.set_cookie(COOKIE_NAME,old,path="/api/admin")
    assert other.get("/api/admin/auth/session").status_code==401


def test_expired_and_disabled_session_are_rejected(auth_app,admin_account):
    client=auth_app.test_client()
    assert login(client,auth_app,admin_account).status_code==200
    auth_app.test_clock[0]+=timedelta(hours=8)
    assert client.get("/api/admin/auth/session").status_code==401
    assert login(client,auth_app,admin_account).status_code==200
    query(auth_app,"UPDATE admin_user SET status='disabled'")
    assert client.get("/api/admin/auth/session").status_code==401
    assert login(client,auth_app,admin_account).status_code==401


@pytest.mark.parametrize('supplied',['missing','wrong','other-session'])
def test_logout_csrf_cannot_be_bypassed(auth_app,admin_account,supplied):
    client=auth_app.test_client()
    assert login(client,auth_app,admin_account).status_code==200
    headers=dict(ORIGIN)
    if supplied=='wrong':
        headers['X-CSRF-Token']=secrets.token_hex(32)
    elif supplied=='other-session':
        auth_app.test_clock[0]+=timedelta(seconds=30)
        other=auth_app.test_client()
        assert login(other,auth_app,admin_account).status_code==200
        headers['X-CSRF-Token']=other.get('/api/admin/auth/session').json['data']['csrf_token']
    response=client.post("/api/admin/auth/logout",json={},headers=headers)
    assert response.status_code==403 and response.json['code']=='csrf_failed'
    assert client.get("/api/admin/auth/session").status_code==200


def test_logged_in_session_still_requires_origin(auth_app,admin_account):
    client=auth_app.test_client()
    assert login(client,auth_app,admin_account).status_code==200
    csrf=client.get('/api/admin/auth/session').json['data']['csrf_token']
    response=client.post('/api/admin/auth/logout',json={},headers={'Origin':'https://other.example','X-CSRF-Token':csrf})
    assert response.status_code==403
    assert client.get('/api/admin/auth/session').status_code==200


def test_production_cookie_requires_https(auth_app,admin_account):
    auth_app.config.update(APP_ENV='production',ADMIN_ORIGIN='https://admin.bumbum.cc')
    client=auth_app.test_client()
    payload={'username':admin_account['username'],'password':admin_account['password'],'code':otp(auth_app,admin_account)}
    response=client.post('/api/admin/auth/login',json=payload,headers={'Origin':'https://admin.bumbum.cc'},base_url='https://admin.bumbum.cc')
    assert response.status_code==200
    assert 'Secure' in response.headers['Set-Cookie'] and 'Domain=' not in response.headers['Set-Cookie']
    assert 'Access-Control-Allow-Origin' not in response.headers


def test_corrupt_secret_fails_without_cookie_or_counter_change(auth_app,admin_account):
    query(auth_app,"UPDATE admin_user SET totp_secret_encrypted=%s",(b'test-only-corrupt',))
    response=login(auth_app.test_client(),auth_app,admin_account)
    assert response.status_code==503 and 'Set-Cookie' not in response.headers
    assert query(auth_app,'SELECT failed_login_attempts FROM admin_user')[0]['failed_login_attempts']==0


def test_database_unavailable_does_not_issue_cookie(auth_app,admin_account,monkeypatch):
    def fail(**_kwargs):raise pymysql.OperationalError('测试中的敏感错误，不得泄露')
    monkeypatch.setattr(pymysql,'connect',fail)
    response=login(auth_app.test_client(),auth_app,admin_account)
    assert response.status_code==503 and 'Set-Cookie' not in response.headers
    assert '敏感错误' not in json.dumps(response.json,ensure_ascii=False)


def test_cli_create_confirms_qr_and_never_overwrites_account(auth_app,monkeypatch):
    secret=pyotp.random_base32()
    monkeypatch.setattr(admin_cli.pyotp,'random_base32',lambda:secret)
    seen=[]
    monkeypatch.setattr(admin_cli,'show_qr',seen.append)
    account={'secret':secret}
    password='test-only-cli-password'
    result=auth_app.test_cli_runner().invoke(args=['admin','create','cli-admin'],input=f'{password}\n{password}\n{otp(auth_app,account)}\n')
    assert result.exit_code==0, '服务器创建命令未完成'
    assert len(seen)==1 and seen[0].startswith('otpauth://totp/')
    row=query(auth_app,'SELECT * FROM admin_user')[0]
    with auth_app.app_context():
        assert decrypt_totp_secret(row['totp_secret_encrypted'],row['id'])==secret
    assert password not in result.output and secret not in result.output
    second=auth_app.test_cli_runner().invoke(args=['admin','create','cli-admin'])
    assert second.exit_code!=0
    assert query(auth_app,'SELECT COUNT(*) AS count FROM admin_user')[0]['count']==1
    auth_app.test_clock[0]+=timedelta(seconds=30)
    assert login(auth_app.test_client(),auth_app,{'username':'cli-admin','password':password,'secret':secret}).status_code==200


def test_interrupted_reset_revokes_sessions_and_keeps_account_unavailable(auth_app,admin_account,monkeypatch):
    client=auth_app.test_client()
    assert login(client,auth_app,admin_account).status_code==200
    monkeypatch.setattr(admin_cli,'show_qr',lambda _uri:None)
    result=auth_app.test_cli_runner().invoke(args=['admin','reset-totp',admin_account['username']],input='y\n')
    assert result.exit_code!=0
    row=query(auth_app,'SELECT totp_enabled,totp_secret_encrypted FROM admin_user')[0]
    assert row=={'totp_enabled':0,'totp_secret_encrypted':None}
    assert client.get('/api/admin/auth/session').status_code==401
    assert login(auth_app.test_client(),auth_app,admin_account).status_code==401


def test_reset_replaces_secret_and_old_sessions_stay_invalid(auth_app,admin_account,monkeypatch):
    client=auth_app.test_client()
    assert login(client,auth_app,admin_account).status_code==200
    new=pyotp.random_base32()
    monkeypatch.setattr(admin_cli.pyotp,'random_base32',lambda:new)
    monkeypatch.setattr(admin_cli,'show_qr',lambda _uri:None)
    result=auth_app.test_cli_runner().invoke(args=['admin','reset-totp',admin_account['username']],input='y\n'+otp(auth_app,{'secret':new})+'\n')
    assert result.exit_code==0, '服务器重置命令未完成'
    assert client.get('/api/admin/auth/session').status_code==401
    auth_app.test_clock[0]+=timedelta(seconds=30)
    assert login(auth_app.test_client(),auth_app,{**admin_account,'secret':new}).status_code==200
    events=json.loads('['+','.join(Path(auth_app.config['ADMIN_CLI_AUDIT_PATH']).read_text().splitlines())+']')
    assert events[-1]['result']=='committed'
    assert new not in json.dumps(events)


def test_disable_command_revokes_sessions_even_after_reenable(auth_app,admin_account):
    client=auth_app.test_client()
    assert login(client,auth_app,admin_account).status_code==200
    result=auth_app.test_cli_runner().invoke(args=['admin','disable',admin_account['username']],input='y\n')
    assert result.exit_code==0
    query(auth_app,"UPDATE admin_user SET status='active'")
    assert client.get('/api/admin/auth/session').status_code==401


def test_commit_failure_never_sets_cookie_and_rolls_back_session(auth_app,admin_account,monkeypatch):
    def fail_commit(_self):
        raise pymysql.OperationalError("测试用提交失败")
    with monkeypatch.context() as changes:
        changes.setattr(pymysql.connections.Connection,"commit",fail_commit)
        response=login(auth_app.test_client(),auth_app,admin_account)
    assert response.status_code==503 and "Set-Cookie" not in response.headers
    assert query(auth_app,"SELECT COUNT(*) AS count FROM admin_session")[0]["count"]==0
    assert query(auth_app,"SELECT totp_last_step FROM admin_user")[0]["totp_last_step"] is None
