"""用独立临时数据库验证旧库升级、完整备份恢复与失败保护。"""

import os
from pathlib import Path
import subprocess

import pymysql
import pytest

from core.db import chip_project_schema, get_database
from scripts import migrate_local as upgrade


@pytest.mark.parametrize("changes", [{"DB_HOST": "db.example.com"}, {"APP_ENV": "production"}, {"DB_PORT": 3306}, {"DB_USER": "root"}, {"DB_NAME": "production"}])
def test_migration_refuses_nonlocal_configuration(changes):
    with pytest.raises(upgrade.MigrationError, match="本机测试库"):
        upgrade.validate_local_config({"APP_ENV": "development", "DB_HOST": "127.0.0.1", "DB_PORT": 33306, "DB_USER": "bumbum_dev", "DB_NAME": "bumbum_digital", **changes})


@pytest.mark.parametrize("incomplete", [False, True])
def test_failed_backup_is_removed_and_never_published(tmp_path, monkeypatch, incomplete):
    destination = tmp_path / "backups/before.sql"

    def failed(_args, *, output, **_kwargs):
        output.write(b"partial")
        if not incomplete:
            raise upgrade.MigrationError("模拟备份失败")

    monkeypatch.setattr(upgrade, "run_docker", failed)
    with pytest.raises(upgrade.MigrationError):
        upgrade.backup_database(["docker"], "test-container", destination)
    assert not destination.exists()
    assert not destination.with_suffix(".partial").exists()


def test_existing_partial_backup_is_never_removed_or_overwritten(tmp_path):
    destination = tmp_path / "before.sql"
    partial = destination.with_suffix(".partial")
    partial.write_bytes(b"existing-private-backup")
    with pytest.raises(FileExistsError):
        upgrade.backup_database(["docker"], "test-container", destination)
    assert partial.read_bytes() == b"existing-private-backup"


@pytest.fixture
def old_schema(auth_app):
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            assert chip_project_schema(cursor) == "optional"
            cursor.execute(upgrade.MIGRATIONS["required"].read_text(encoding="utf-8"))
        try:
            yield connection
        finally:
            connection.rollback()
            with connection.cursor() as cursor:
                if chip_project_schema(cursor) == "required":
                    cursor.execute(upgrade.MIGRATIONS["optional"].read_text(encoding="utf-8"))


def schema(connection):
    with connection.cursor() as cursor:
        return chip_project_schema(cursor)


def snapshot(connection):
    with connection.cursor() as cursor:
        result = []
        for table in ("chip", "admin_user"):
            cursor.execute(f"SELECT * FROM {table} ORDER BY id")
            result.append(cursor.fetchall())
    connection.commit()
    return result


@pytest.mark.auth_database
def test_old_schema_upgrade_backup_restore_and_idempotence(auth_app, admin_account, old_schema, auth_database, tmp_path, monkeypatch):
    connection = old_schema
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO chip(chip_uid,project_id,batch_no) VALUES ('04:A2:7F:1B:5E:80:00',1,'原有中文批次')")
    connection.commit()
    before = snapshot(connection)
    assert auth_app.test_client().get("/api/ready").status_code == 503
    for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        monkeypatch.delenv(name, raising=False)
    command, container = auth_database["TEST_DOCKER_COMMAND"], auth_database["TEST_CONTAINER"]
    backup_file = tmp_path / "中文 备份/before.sql"
    assert upgrade.migrate(connection, lambda: upgrade.backup_database(command, container, backup_file)) is True
    assert schema(connection) == "optional"
    assert snapshot(connection) == before
    assert auth_app.test_client().get("/api/ready").status_code == 200
    assert upgrade.migrate(connection, lambda: pytest.fail("已经升级时不能重复备份或执行DDL")) is False
    assert backup_file.is_file()
    if os.name != "nt":
        assert backup_file.stat().st_mode & 0o777 == 0o600
    # 仅在专属临时容器内恢复真实导出，验证备份能还原旧结构及原有加密账号资料。
    connection.commit()
    with backup_file.open("rb") as source:
        restored = subprocess.run([*command, "exec", "-i", container, "sh", "-c",
            'MYSQL_PWD="$MYSQL_PASSWORD" exec mysql -u "$MYSQL_USER" "$MYSQL_DATABASE"'], stdin=source, capture_output=True, timeout=120)
    assert restored.returncode == 0, "独立临时数据库备份恢复失败"
    assert schema(connection) == "required"
    assert snapshot(connection) == before
    # finally恢复新结构，后面的认证和芯片测试继续使用目标版本。


@pytest.mark.auth_database
def test_backup_failure_leaves_old_schema_and_data_unchanged(old_schema):
    connection = old_schema

    def failed():
        raise upgrade.MigrationError("备份未完成")

    with pytest.raises(upgrade.MigrationError, match="备份未完成"):
        upgrade.migrate(connection, failed)
    assert schema(connection) == "required"


@pytest.mark.auth_database
def test_atomic_ddl_failure_preserves_old_column_and_foreign_keys(old_schema, tmp_path, monkeypatch):
    connection = old_schema
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO chip(chip_uid,project_id) VALUES ('04:A2:7F:1B:5E:80:00',1)")
    connection.commit()
    before = snapshot(connection)
    invalid_sql = tmp_path / "invalid.sql"
    sql = upgrade.MIGRATIONS["optional"].read_text(encoding="utf-8").rstrip().removesuffix(";")
    invalid_sql.write_text(sql + ", ADD CONSTRAINT ck_test_impossible CHECK (project_id IS NULL);", encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.setitem(upgrade.MIGRATIONS, "optional", invalid_sql)
        with pytest.raises(pymysql.MySQLError):
            upgrade.migrate(connection, lambda: None)
    assert schema(connection) == "required"
    assert snapshot(connection) == before
    with connection.cursor() as cursor:
        cursor.execute("SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='chip' AND CONSTRAINT_TYPE='FOREIGN KEY'")
        assert {row[0] for row in cursor.fetchall()} == {"fk_chip_project", "fk_chip_item_project"}


@pytest.mark.auth_database
def test_rollback_never_deletes_or_assigns_unassigned_chip(auth_app):
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO chip(chip_uid) VALUES ('04:A2:7F:1B:5E:80:00')")
        connection.commit()
        before = snapshot(connection)
        with pytest.raises(upgrade.MigrationError, match="已有未分配"):
            upgrade.migrate(connection, lambda: pytest.fail("拒绝回退时不应执行备份或DDL"), rollback=True)
        assert schema(connection) == "optional" and snapshot(connection) == before
