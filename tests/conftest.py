"""管理功能集成测试使用专属临时MySQL，不连接或修改cece的测试库。"""

from datetime import datetime
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid

import pymysql
import pytest
import pyotp
from werkzeug.security import generate_password_hash

from app import create_app
from core.db import get_database
from core.secret_storage import encrypt_totp_secret

ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption("--auth-db", action="store_true", help="在独立临时MySQL中检查管理员认证和芯片管理；需要Docker")
    parser.addoption("--cloud-image", help="另用已构建的云测试镜像验证真实Gunicorn和HTTPS网关；不会连接ECS")


@pytest.fixture(scope="session")
def auth_database(request):
    if not request.config.getoption("--auth-db"):
        pytest.skip("未启用独立认证数据库检查；使用 --auth-db")
    if not shutil.which("docker"):
        pytest.fail("需要已启动的本机Docker才能执行认证数据库检查")
    env = dict(os.environ)
    command = ["docker"]
    if os.name != "nt" and Path("/var/run/docker.sock").exists():
        for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
            env.pop(name, None)
        command += ["--host=unix:///var/run/docker.sock"]
    container = "bumbum-auth-test-" + uuid.uuid4().hex[:12]
    password = secrets.token_hex(24)
    root_password = secrets.token_hex(24)

    def docker(args):
        result = subprocess.run(command + args, env=env, capture_output=True, text=True)
        if result.returncode:
            pytest.fail("临时认证数据库命令失败；请检查本机Docker和MySQL镜像，未触碰已有数据库")
        return result.stdout.strip()

    created = False
    try:
        with tempfile.TemporaryDirectory(prefix="bumbum-auth-test-") as folder:
            path = Path(folder)
            credentials = path / "mysql.env"
            credentials.write_text(f"MYSQL_DATABASE=bumbum_digital\nMYSQL_USER=bumbum_auth_test\nMYSQL_PASSWORD={password}\nMYSQL_ROOT_PASSWORD={root_password}\n")
            credentials.chmod(0o600)
            schema = path / "schema.sql"
            shutil.copyfile(ROOT / "db/schema.sql", schema)
            schema.chmod(0o644)
            # 仅停止/重启验证使用专属匿名卷；其他检查继续使用随停止清空的临时内存盘。
            mount = ["--volume", "/var/lib/mysql"] if getattr(request, "param", None) == "restartable" else ["--tmpfs", "/var/lib/mysql"]
            docker(["create", "--name", container, "--label", "bumbum.test=admin-auth", "--publish", "127.0.0.1::3306", *mount, "--env-file", str(credentials), "mysql:8.0.46"])
            created = True
            docker(["cp", str(schema), container + ":/docker-entrypoint-initdb.d/001-schema.sql"])
            docker(["start", container])
            port = int(docker(["port", container, "3306/tcp"]).rsplit(":", 1)[1])
            config = {"DB_HOST": "127.0.0.1", "DB_PORT": port, "DB_USER": "bumbum_auth_test", "DB_PASSWORD": password, "DB_NAME": "bumbum_digital"}
            config.update(TEST_CONTAINER=container, TEST_DOCKER_COMMAND=command)
            for _ in range(60):
                try:
                    connection = pymysql.connect(host="127.0.0.1", port=port, user="bumbum_auth_test", password=password, database="bumbum_digital", connect_timeout=1)
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM admin_session")
                    connection.close()
                    break
                except pymysql.MySQLError:
                    time.sleep(0.5)
            else:
                pytest.fail("临时认证数据库在30秒内未就绪；已有数据库未修改")
            yield config
    finally:
        if created:
            docker(["rm", "--force", "--volumes", container])


@pytest.fixture
def auth_app(auth_database, tmp_path):
    clock = [datetime(2026, 10, 24, 3, 0, 0)]
    app = create_app({
        **auth_database, "TESTING": True, "APP_ENV": "development",
        "ADMIN_ORIGIN": "http://localhost:5174",
        "STORAGE_ENCRYPTION_KEY": secrets.token_hex(32), "STORAGE_KEY_VERSION": "v1",
        "IP_HASH_KEY": secrets.token_hex(32),
        "AUTH_CLOCK": lambda: clock[0],
        "ADMIN_CLI_AUDIT_PATH": str(tmp_path / "server-operations.jsonl"),
    })
    app.test_clock = clock
    with app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            for table in ("admin_login_event", "admin_session", "admin_audit", "admin_user", "chip_key", "chip"):
                cursor.execute(f"DELETE FROM {table}")
        connection.commit()
    return app


@pytest.fixture
def admin_account(auth_app):
    secret = pyotp.random_base32()
    password = "test-only-password-2026"
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO admin_user (username,password_hash) VALUES (%s,%s)", ("test-admin", generate_password_hash(password)))
            admin_id = cursor.lastrowid
            cursor.execute("UPDATE admin_user SET totp_enabled=1,totp_secret_encrypted=%s WHERE id=%s", (encrypt_totp_secret(secret, admin_id), admin_id))
        connection.commit()
    return {"username": "test-admin", "password": password, "secret": secret, "id": admin_id}
