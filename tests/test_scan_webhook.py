"""在专属临时库检查手机回调、网页互通、权限撤销及并发去重。"""

from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
import json
import secrets

import pymysql
import pytest

from core import scan_webhook
from core.db import get_database
from tests.test_admin_auth import ORIGIN, login, query

pytestmark = pytest.mark.auth_database
PATH = "/api/webhook/admin/scan"
UID = "04:A2:7F:1B:5E:80:00"


def authorization(username, password):
    return {"Authorization": "Basic " + b64encode(f"{username}:{password}".encode()).decode()}


@pytest.fixture
def scanner(auth_app, admin_account):
    password = secrets.token_hex(32)
    auth_app.config.update(WEBHOOK_ADMIN_USERNAME=admin_account["username"], WEBHOOK_SHARED_SECRET=password)
    return auth_app.test_client(), authorization(admin_account["username"], password)


def post(scanner, **changes):
    client, headers = scanner
    return client.post(PATH, headers=headers, json={"identifier": UID, **changes})


def test_scan_challenge_then_save_then_query_from_authenticated_webpage(auth_app, scanner, admin_account):
    client, headers = scanner
    challenge = client.post(PATH, json={"identifier": UID})
    assert challenge.status_code == 401
    assert challenge.headers["WWW-Authenticate"] == 'Basic realm="bumbum-scan"'
    response = post(scanner, identifier="04a27f1b5e8000", date="2026-10-24T11:00:00+08:00", content="")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "data": {"chip_uid": UID, "is_new": True}}
    assert response.headers["Cache-Control"] == "no-store"
    assert "Set-Cookie" not in response.headers
    row = query(auth_app, "SELECT * FROM chip")[0]
    assert row["project_id"] is None and row["chip_status"] == "pending" and row["item_id"] is None
    assert row["provisioned_at"] is None
    audit = query(auth_app, "SELECT * FROM admin_audit")[0]
    assert audit["admin_id"] == admin_account["id"]
    assert json.loads(audit["detail"]) == {"project": None, "source": "nfc_cool"}
    assert client.get("/api/admin/chips", headers=headers).status_code == 401
    assert client.post("/api/admin/chips", headers={**headers, **ORIGIN}, json={"chip_uid": UID}).status_code == 401
    browser = auth_app.test_client()
    assert login(browser, auth_app, admin_account).status_code == 200
    listed = browser.get("/api/admin/chips?project=unassigned").json["data"]
    assert listed["total"] == 1 and listed["items"][0]["chip_uid"] == UID


def test_repeat_keeps_assigned_disabled_chip_and_only_one_audit(auth_app, scanner):
    assert post(scanner).status_code == 200
    query(auth_app, "UPDATE chip SET project_id=2,batch_no='原批次',chip_status='disabled',updated_at='2020-01-01'")
    before = query(auth_app, "SELECT * FROM chip")[0]
    assert post(scanner).json["data"]["is_new"] is False
    assert query(auth_app, "SELECT * FROM chip")[0] == before
    assert query(auth_app, "SELECT COUNT(*) AS n FROM admin_audit")[0]["n"] == 1


@pytest.mark.parametrize("header", [None, "Basic !!!", "Bearer test-only", "Basic dXNlcg=="])
def test_missing_or_malformed_basic_challenges_without_writing(auth_app, scanner, header):
    response = auth_app.test_client().post(PATH, json={"identifier": UID}, headers={"Authorization": header} if header else {})
    assert response.status_code == 401 and "WWW-Authenticate" in response.headers
    assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 0


@pytest.mark.parametrize("change", ["username", "password", "unknown", "disabled", "totp"])
def test_wrong_credentials_or_ineligible_owner_never_write(auth_app, scanner, change):
    client, headers = scanner
    if change == "username":
        headers = authorization("wrong-user", auth_app.config["WEBHOOK_SHARED_SECRET"])
    elif change == "password":
        headers = authorization(auth_app.config["WEBHOOK_ADMIN_USERNAME"], "wrong-password")
    elif change == "unknown":
        auth_app.config["WEBHOOK_ADMIN_USERNAME"] = "unknown-user"
        headers = authorization("unknown-user", auth_app.config["WEBHOOK_SHARED_SECRET"])
    elif change == "disabled":
        query(auth_app, "UPDATE admin_user SET status='disabled'")
    else:
        query(auth_app, "UPDATE admin_user SET totp_enabled=0")
    response = client.post(PATH, headers=headers, json={"identifier": UID})
    assert response.status_code == 401 and "WWW-Authenticate" in response.headers
    assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 0


@pytest.mark.parametrize("changes", [
    {"identifier": "NoIdentifierInCompatibilityMode"}, {"identifier": "not-a-uid"},
    {"identifier": None}, {"identifier": "04-A2-7F-1B-5E-80-00"},
    {"project": "fashion"}, {"batch_no": "不允许"}, {"force": True},
    {"content": None}, {"content": "文" * 4097}, {"date": None}, {"date": 123},
    {"date": "2026-10-24"}, {"date": "2026-10-24T03:00:00"}, {"date": "x" * 65},
])
def test_invalid_input_never_writes(auth_app, scanner, changes):
    assert post(scanner, **changes).status_code == 400
    assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 0


def test_query_non_json_and_oversized_body_are_rejected(auth_app, scanner):
    client, headers = scanner
    assert client.post(PATH + "?project=fashion", headers=headers, json={"identifier": UID}).status_code == 400
    assert client.post(PATH, headers=headers, data="identifier=test-only").status_code == 400
    assert client.post(PATH, headers=headers, json={}).status_code == 400
    assert client.post(PATH, headers=headers, json={"identifier": UID, "content": "文" * 4096}).status_code == 400
    assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 0


def test_unconfigured_feature_closes_with_service_error(auth_app, scanner):
    auth_app.config["WEBHOOK_SHARED_SECRET"] = ""
    response = post(scanner)
    assert response.status_code == 503 and response.json["code"] == "service_unavailable"
    assert "Set-Cookie" not in response.headers


@pytest.mark.parametrize("failure_point", ["audit", "commit"])
def test_storage_failure_rolls_back_and_can_be_manually_retried(auth_app, scanner, monkeypatch, failure_point):
    execute = pymysql.cursors.DictCursor.execute
    def fail_execute(cursor, sql, args=None):
        if sql.startswith("INSERT INTO admin_audit"):
            raise pymysql.OperationalError("测试中的保存失败")
        return execute(cursor, sql, args)
    def fail_commit(_connection):
        raise pymysql.OperationalError("测试中的提交失败")
    with monkeypatch.context() as changes:
        if failure_point == "audit":
            changes.setattr(pymysql.cursors.DictCursor, "execute", fail_execute)
        else:
            changes.setattr(pymysql.connections.Connection, "commit", fail_commit)
        assert post(scanner).status_code == 503
    assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 0
    assert query(auth_app, "SELECT COUNT(*) AS n FROM admin_audit")[0]["n"] == 0
    assert post(scanner).json["data"]["is_new"] is True


def test_webpage_and_phone_concurrent_duplicate_preserves_one_record(auth_app, scanner, admin_account):
    browser = auth_app.test_client()
    assert login(browser, auth_app, admin_account).status_code == 200
    csrf = browser.get("/api/admin/auth/session").json["data"]["csrf_token"]
    def attempt(number):
        if number == 0:
            return post(scanner)
        return browser.post("/api/admin/chips", headers={**ORIGIN, "X-CSRF-Token": csrf}, json={"chip_uid": UID})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(response.json["data"]["is_new"] for response in responses) == [False, True]
    assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 1
    assert query(auth_app, "SELECT COUNT(*) AS n FROM admin_audit")[0]["n"] == 1


def test_owner_status_is_rechecked_under_write_lock(auth_app, scanner, monkeypatch):
    original = scan_webhook.get_database
    def disabled_before_transaction():
        connection = original()
        with connection.cursor() as cursor:
            cursor.execute("UPDATE admin_user SET status='disabled'")
        connection.commit()
        return connection
    monkeypatch.setattr(scan_webhook, "get_database", disabled_before_transaction)
    assert post(scanner).status_code == 401
    assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 0
