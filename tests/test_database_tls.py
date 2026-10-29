"""使用合成证书、回环握手及专属临时MySQL验证TLS和空库保护。"""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import threading
import time
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pymysql
from pymysql.constants import CLIENT, CR
import pytest

from app import create_app
from core.db import TARGET_TABLES, database_tls_options
from core.rds_database import RdsPreparationError, initialize_empty, inspect_target, schema_for_selected_database
from core.rds_target import RDS_HOST, SLOTS, validate_target

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def certificates(tmp_path):
    """所有私钥均为本次测试随机生成，不使用任何现有身份或真实配置。"""
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Bumbum temporary test CA")])
    ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
          .not_valid_after(now + timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                         data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
                         encipher_only=False, decipher_only=False), critical=True).sign(ca_key, hashes.SHA256()))
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
              .issuer_name(name).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=1))
              .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
              .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
              .sign(ca_key, hashes.SHA256()))
    folder = tmp_path / "tls"
    folder.mkdir(mode=0o755)
    folder.chmod(0o755)
    for name, data in (("ca.crt", ca.public_bytes(serialization.Encoding.PEM)),
                       ("server.crt", server.public_bytes(serialization.Encoding.PEM)),
                       ("server.key", server_key.private_bytes(serialization.Encoding.PEM,
                        serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))):
        (folder / name).write_bytes(data)
        (folder / name).chmod(0o444)
    return folder


def test_remote_production_requires_verified_tls():
    with pytest.raises(ValueError, match="VERIFY_IDENTITY"):
        create_app({"TESTING": True, "APP_ENV": "production", "DB_HOST": RDS_HOST,
                    "DB_SSL_MODE": "LOCAL", "DB_SSL_CA": ""})
    for host in ("127.0.0.1", "localhost", "::1"):
        assert database_tls_options({"APP_ENV": "production", "DB_HOST": host}) == {}


@pytest.mark.parametrize("mode", ["PREFERRED", "REQUIRED", "VERIFY_CA", "garbage", ""])
def test_tls_downgrade_modes_are_not_accepted(mode):
    with pytest.raises(ValueError):
        database_tls_options({"DB_HOST": RDS_HOST, "DB_SSL_MODE": mode})


def test_ca_is_required_valid_and_not_silently_ignored(tmp_path):
    for value in ("", "relative.crt", str(tmp_path / "missing.crt")):
        with pytest.raises(ValueError, match="CA"):
            database_tls_options({"DB_SSL_MODE": "VERIFY_IDENTITY", "DB_SSL_CA": value})
    invalid = tmp_path / "invalid.crt"
    invalid.write_text("invalid public certificate")
    with pytest.raises(ValueError, match="CA"):
        database_tls_options({"DB_SSL_MODE": "VERIFY_IDENTITY", "DB_SSL_CA": str(invalid)})
    with pytest.raises(ValueError, match="忽略"):
        database_tls_options({"DB_SSL_MODE": "LOCAL", "DB_SSL_CA": str(invalid)})


def test_test_slot_cannot_connect_production_or_use_initialization_identity():
    config = {"APP_ENV": "production", "HANGZHOU_SLOT": "test", "DB_HOST": RDS_HOST,
              "DB_PORT": 3306, "DB_NAME": "bumbum_hz_test", "DB_USER": "bumbum_hz_test",
              "DB_SSL_MODE": "VERIFY_IDENTITY"}
    assert validate_target(config) == SLOTS["test"]
    for name, value in (("DB_NAME", "bumbum_hz_production"), ("DB_USER", "bumbum_hz_test_init"),
                        ("DB_HOST", "127.0.0.1"), ("HANGZHOU_SLOT", "production"),
                        ("DB_SSL_MODE", "LOCAL"), ("APP_ENV", "development")):
        with pytest.raises(ValueError, match="不匹配"):
            validate_target({**config, name: value})


def test_fixed_driver_refuses_server_without_tls_before_sending_authentication(certificates):
    captured = []
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(5)
    port = listener.getsockname()[1]
    capabilities = CLIENT.PROTOCOL_41 | CLIENT.SECURE_CONNECTION | CLIENT.PLUGIN_AUTH
    payload = (b"\x0a8.0.36\0" + struct.pack("<I", 1) + b"12345678\0" +
               struct.pack("<HBHHB10s", capabilities & 0xffff, 45, 2, capabilities >> 16, 21, b"\0" * 10) +
               b"abcdefghijkl\0mysql_native_password\0")
    def server():
        with listener:
            with listener.accept()[0] as peer:
                peer.settimeout(5)
                peer.sendall(len(payload).to_bytes(3, "little") + b"\x00" + payload)
                captured.append(peer.recv(4096))
    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    with pytest.raises(pymysql.OperationalError) as error:
        pymysql.connect(host="127.0.0.1", port=port, user="synthetic-test-user", password="synthetic-only",
                        connect_timeout=3, **database_tls_options({"DB_SSL_MODE": "VERIFY_IDENTITY",
                                                                "DB_SSL_CA": str(certificates / "ca.crt")}))
    thread.join(timeout=6)
    assert not thread.is_alive()
    assert error.value.args[0] == CR.CR_SSL_CONNECTION_ERROR
    assert captured == [b""], "服务器不支持TLS时，不能发送任何账号认证响应"


def test_selected_schema_keeps_only_current_database_and_all_tables():
    source = (ROOT / "db/schema.sql").read_text(encoding="utf-8")
    result = schema_for_selected_database(source)
    assert "CREATE DATABASE" not in result and "USE bumbum_digital" not in result
    assert result.count("CREATE TABLE ") == len(TARGET_TABLES) == 24
    with pytest.raises(RdsPreparationError):
        schema_for_selected_database(source.replace("USE bumbum_digital;", "USE another_database;"))


@pytest.fixture
def tls_mysql(request, certificates, tmp_path):
    if not request.config.getoption("--auth-db"):
        pytest.skip("需显式--auth-db，在独立临时MySQL验证TLS和空库保护")
    env = {k: v for k, v in os.environ.items() if k not in {
        "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}
    command = ["docker", "--host=unix:///var/run/docker.sock"]
    def docker(args):
        r = subprocess.run(command + args, env=env, capture_output=True, text=True, timeout=90)
        if r.returncode:
            pytest.fail("独立TLS测试容器命令失败；不显示测试凭证或原始日志")
        return r.stdout.strip()
    name = "bumbum-rds-tls-test-" + uuid.uuid4().hex[:12]
    password = secrets.token_hex(24)
    credentials = tmp_path / "synthetic-mysql.env"
    credentials.write_text("MYSQL_DATABASE=bumbum_hz_test\nMYSQL_USER=bumbum_hz_test_init\n"
                           f"MYSQL_PASSWORD={password}\nMYSQL_ROOT_PASSWORD={secrets.token_hex(24)}\n")
    credentials.chmod(0o600)
    try:
        docker(["run", "-d", "--name", name, "--env-file", str(credentials), "--tmpfs", "/var/lib/mysql",
                "-p", "127.0.0.1::3306", "--mount", f"type=bind,src={certificates},dst=/tls,readonly",
                "mysql:8.0.46", "--ssl-ca=/tls/ca.crt", "--ssl-cert=/tls/server.crt", "--ssl-key=/tls/server.key",
                "--require-secure-transport=ON", "--character-set-server=utf8mb4", "--collation-server=utf8mb4_unicode_ci"])
        port = int(json.loads(docker(["inspect", "--format", "{{json .NetworkSettings.Ports}}", name]))["3306/tcp"][0]["HostPort"])
        options = {"host": "localhost", "port": port, "user": "bumbum_hz_test_init", "password": password,
                   "database": "bumbum_hz_test", "charset": "utf8mb4", "connect_timeout": 3,
                   "read_timeout": 5, "client_flag": CLIENT.MULTI_STATEMENTS,
                   **database_tls_options({"DB_SSL_MODE": "VERIFY_IDENTITY", "DB_SSL_CA": str(certificates / "ca.crt")})}
        for _ in range(90):
            try:
                with pymysql.connect(**options):
                    break
            except pymysql.MySQLError:
                time.sleep(0.5)
        else:
            pytest.fail("独立TLS MySQL未在45秒内就绪，未触碰现有数据库")
        yield options, certificates
    finally:
        docker(["rm", "-f", "-v", name])


@pytest.mark.auth_database
def test_real_mysql_verified_tls_wrong_identity_ca_and_guarded_initialization(tls_mysql, tmp_path):
    options, certificates = tls_mysql
    with pytest.raises(pymysql.OperationalError):
        pymysql.connect(**{**options, "host": "127.0.0.1"})
    # 使用系统公开CA集合代替合成CA，必须拒绝这个自签名测试服务。
    with pytest.raises(pymysql.OperationalError):
        pymysql.connect(**{**options, "ssl_ca": "/etc/ssl/certs/ca-certificates.crt"})
    with pymysql.connect(**options) as connection:
        report = inspect_target(connection, "bumbum_hz_test")
        assert report["empty"] and report["client_tls_cipher"]
        with pytest.raises(RdsPreparationError, match="标识不符"):
            initialize_empty(connection, "bumbum_hz_test", str(uuid.uuid4()), (ROOT / "db/schema.sql").read_text())
        assert inspect_target(connection, "bumbum_hz_test")["empty"]
        result = initialize_empty(connection, "bumbum_hz_test", report["server_uuid"], (ROOT / "db/schema.sql").read_text())
        assert result["tables_complete"] and result["table_count"] == 24
        with pytest.raises(RdsPreparationError, match="不是空库"):
            initialize_empty(connection, "bumbum_hz_test", report["server_uuid"], (ROOT / "db/schema.sql").read_text())
        assert inspect_target(connection, "bumbum_hz_test")["table_count"] == 24
        with connection.cursor() as cursor:
            cursor.execute("SELECT code FROM project ORDER BY id")
            assert cursor.fetchall() == (("fashion",), ("jewelry",))
        # 应用用相同连接封装验证完整ready，测试身份不进入任何真实环境。
        app = create_app({"TESTING": True, "APP_ENV": "production", "DB_HOST": "localhost",
                          "DB_PORT": options["port"], "DB_USER": options["user"], "DB_PASSWORD": options["password"],
                          "DB_NAME": "bumbum_hz_test", "DB_SSL_MODE": "VERIFY_IDENTITY",
                          "DB_SSL_CA": str(certificates / "ca.crt"), "HANGZHOU_SLOT": ""})
        assert app.test_client().get("/api/ready").status_code == 200
