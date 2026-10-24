"""用独立MySQL验证来源升级、证据补齐、失败重跑及首次来源不覆盖。"""

import json

import pymysql
import pytest

from core.db import get_database, registration_source_schema
from core.registration_migration import migrate, SourceMigrationError, validate_cloud_config
from tests.test_admin_auth import query, login, ORIGIN
from tests.test_scan_webhook import scanner, post, UID


@pytest.fixture
def old_source(auth_app):
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE chip DROP COLUMN registration_source")
        try:
            yield connection
        finally:
            connection.rollback()
            # 即使测试中模拟异常，也把专属测试库恢复，避免影响下一项检查。
            migrate(connection, lambda: None)


@pytest.mark.auth_database
def test_migration_recovers_only_unambiguous_sources_and_preserves_times(auth_app, admin_account, old_source):
    with old_source.cursor() as cursor:
        ids = []
        for number in range(5):
            cursor.execute("INSERT INTO chip(chip_uid,created_at,updated_at) VALUES (%s,'2020-01-01','2020-01-02')", (f"04:A2:7F:1B:5E:80:{number:02X}",))
            ids.append(cursor.lastrowid)
        for number, source in [(0, "manual"), (1, "nfc_cool"), (3, "manual"), (3, "nfc_cool"), (4, "untrusted")]:
            cursor.execute("INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail) VALUES (%s,'chip.register','chip',%s,%s)",
                           (admin_account["id"], str(ids[number]), json.dumps({"source": source})))
    old_source.commit()
    assert auth_app.test_client().get("/api/ready").status_code == 503
    called = []
    assert migrate(old_source, lambda: called.append(True)) is True
    with old_source.cursor() as cursor:
        cursor.execute("SELECT registration_source,created_at,updated_at FROM chip ORDER BY id")
        rows = cursor.fetchall()
    assert [row[0] for row in rows] == ["manual", "nfc_cool", "unknown", "unknown", "unknown"]
    assert all(str(row[1]) == "2020-01-01 00:00:00" and str(row[2]) == "2020-01-02 00:00:00" for row in rows)
    assert migrate(old_source, lambda: pytest.fail("已完成时不得再次要求备份")) is False
    assert called == [True]
    assert auth_app.test_client().get("/api/ready").status_code == 200


@pytest.mark.auth_database
def test_backup_failure_prevents_schema_changes(old_source):
    def fail():
        raise OSError("模拟完整备份失败")
    with pytest.raises(OSError):
        migrate(old_source, fail)
    with old_source.cursor() as cursor:
        assert registration_source_schema(cursor) == "missing"


@pytest.mark.auth_database
def test_rerun_after_column_added_finishes_backfill(auth_app, admin_account):
    query(auth_app, "INSERT INTO chip(chip_uid) VALUES (%s)", (UID,))
    chip = query(auth_app, "SELECT * FROM chip")[0]
    query(auth_app, "INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail) VALUES (%s,'chip.register','chip',%s,%s)",
          (admin_account["id"], str(chip["id"]), json.dumps({"source": "nfc_cool"})))
    with auth_app.app_context():
        assert migrate(get_database(), lambda: None) is True
    assert query(auth_app, "SELECT registration_source FROM chip")[0]["registration_source"] == "nfc_cool"


@pytest.mark.auth_database
def test_source_enum_rejects_undefined_values(auth_app):
    with pytest.raises(pymysql.MySQLError):
        query(auth_app, "INSERT INTO chip(chip_uid,registration_source) VALUES (%s,'spoofed')", (UID,))


@pytest.mark.auth_database
@pytest.mark.parametrize("phone_first", [True, False])
def test_first_registration_source_survives_cross_channel_repeat(auth_app, scanner, admin_account, phone_first):
    browser = auth_app.test_client()
    assert login(browser, auth_app, admin_account).status_code == 200
    csrf = browser.get("/api/admin/auth/session").json["data"]["csrf_token"]
    def manual():
        return browser.post("/api/admin/chips", headers={**ORIGIN, "X-CSRF-Token": csrf}, json={"chip_uid": UID})
    first, repeat = (lambda: post(scanner), manual) if phone_first else (manual, lambda: post(scanner))
    assert first().json["data"]["is_new"] is True
    before = query(auth_app, "SELECT * FROM chip")[0]
    assert repeat().json["data"]["is_new"] is False
    assert query(auth_app, "SELECT * FROM chip")[0] == before
    listed = browser.get("/api/admin/chips").json["data"]["items"][0]
    assert listed["registration_source"] == ("nfc_cool" if phone_first else "manual")


@pytest.mark.parametrize("changes", [{"DB_HOST": "remote.invalid"}, {"DB_PORT": 3306}, {"DB_USER": "root"}, {"ADMIN_ORIGIN": "https://admin.bumbum.cc"}])
def test_cloud_migration_refuses_other_targets(changes):
    with pytest.raises(SourceMigrationError):
        validate_cloud_config({"APP_ENV": "production", "DB_HOST": "127.0.0.1", "DB_PORT": 33307,
                               "DB_USER": "bumbum_test", "DB_NAME": "bumbum_digital", "ADMIN_ORIGIN": "https://test.bumbum.cc", **changes})
