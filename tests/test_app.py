"""检查运行状态、故障返回和本地配置保护，不需要真实密钥。"""

from unittest.mock import MagicMock

import pytest
import pymysql

from core import db

from app import create_app
from scripts.setup_local import prepare_local_config


@pytest.fixture
def app():
    return create_app({"TESTING": True, "DB_USER": "", "DB_PASSWORD": ""})


def test_health_does_not_require_database(app, monkeypatch):
    def must_not_connect(**_kwargs):
        raise AssertionError("运行检查不应连接数据库")
    monkeypatch.setattr(pymysql, "connect", must_not_connect)
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "data": {"service": "bumbum", "state": "running"}}
    assert response.headers["Cache-Control"] == "no-store"


def test_missing_database_configuration_is_not_reported_as_success(app):
    response = app.test_client().get("/api/ready")
    assert response.status_code == 503
    assert response.json["code"] == "service_unavailable"


def test_database_errors_do_not_expose_connection_details(app, monkeypatch):
    app.config.update(DB_USER="test-only", DB_PASSWORD="test-only")
    def fail(**_kwargs):
        raise pymysql.OperationalError("测试中的敏感连接详情，不应返回给浏览器")
    monkeypatch.setattr(pymysql, "connect", fail)
    response = app.test_client().get("/api/ready")
    assert response.status_code == 503
    assert "敏感连接详情" not in response.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/api/admin/chips", "/api/tap/verify", "/missing"])
def test_unimplemented_addresses_do_not_return_fake_business_data(app, path):
    response = app.test_client().get(path)
    assert response.status_code == 404
    assert response.json["code"] == "not_found"


def test_wrong_method_returns_json_and_keeps_allow_header(app):
    response = app.test_client().post("/api/health")
    assert response.status_code == 405
    assert response.json["code"] == "method_not_allowed"
    assert "GET" in response.headers["Allow"]


def test_existing_local_configuration_is_preserved(tmp_path):
    (tmp_path / ".env.example").write_text("DB_PASSWORD=\n", encoding="utf-8")
    (tmp_path / ".env").write_text("DB_PASSWORD=测试占位内容\n", encoding="utf-8")
    assert prepare_local_config(tmp_path) is False
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "DB_PASSWORD=测试占位内容\n"


def test_new_local_configuration_only_generates_database_passwords(tmp_path):
    (tmp_path / ".env.example").write_text(
        "DB_USER=\nDB_PASSWORD=\nDEV_DB_ROOT_PASSWORD=\nSDM_META_KEY_V1=\n",
        encoding="utf-8",
    )
    assert prepare_local_config(tmp_path) is True
    values = dict(line.split("=", 1) for line in (tmp_path / ".env").read_text().splitlines())
    assert len(bytes.fromhex(values["DB_PASSWORD"])) == 24
    assert len(bytes.fromhex(values["DEV_DB_ROOT_PASSWORD"])) == 24
    assert values["DB_PASSWORD"] != values["DEV_DB_ROOT_PASSWORD"]
    assert values["SDM_META_KEY_V1"] == ""


@pytest.mark.parametrize("rows", [
    [[], []],
    [[(table,) for table in db.TARGET_TABLES], [("fashion",)]],
])
def test_partial_initialization_is_not_reported_as_ready(app, monkeypatch, rows):
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchall.side_effect = rows
    monkeypatch.setattr(db, "get_database", lambda: connection)
    response = app.test_client().get("/api/ready")
    assert response.status_code == 503
    assert response.json["code"] == "service_unavailable"


def test_health_rejects_undeclared_query_parameters(app):
    response = app.test_client().get("/api/health?unknown=1")
    assert response.status_code == 400
    assert response.json["code"] == "invalid_param"
