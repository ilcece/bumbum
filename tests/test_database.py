"""按显式开关检查本地真实 MySQL；不向业务表写入测试数据。"""

import os
from pathlib import Path
import re

import pytest

from app import create_app
from core.db import get_database

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="需显式启用本地数据库检查"),
]


def test_local_mysql_is_initialized_and_uses_utc():
    app = create_app({"TESTING": True})
    assert app.config["DB_HOST"] in {"127.0.0.1", "localhost"}, "此检查只允许本机测试数据库"
    assert app.config["DB_PORT"] == 33306, "此检查只允许文档定义的测试端口"
    assert app.config["DB_USER"] == "bumbum_dev", "此检查只允许本地测试账号"
    assert app.config["DB_NAME"] == "bumbum_digital"
    with app.app_context():
        with get_database().cursor() as cursor:
            cursor.execute("SELECT VERSION(), @@session.time_zone, CURRENT_USER()")
            version, timezone, user = cursor.fetchone()
            assert version.startswith("8.0.")
            assert timezone == "+00:00"
            assert user.startswith("bumbum_dev@")
            cursor.execute("SHOW TABLES")
            actual = {row[0] for row in cursor.fetchall()}
        schema = (Path(__file__).resolve().parents[1] / "db/schema.sql").read_text(encoding="utf-8")
        assert actual == set(re.findall(r"CREATE TABLE (\w+)", schema))
    response = app.test_client().get("/api/ready")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "data": {"database": "ready"}}
