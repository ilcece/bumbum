"""真实Nginx、TLS、Gunicorn和专属MySQL串联；不访问域名、ECS或真实手机。"""

from datetime import datetime, timedelta, timezone
import http.client
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import time
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pyotp
import pytest

from tests.test_scan_webhook import authorization
from tests.test_admin_auth import query

pytestmark = pytest.mark.auth_database
ROOT = Path(__file__).resolve().parents[1]
UID = "04:A2:7F:1B:5E:80:00"


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.parametrize("allowed", [True, False])
def test_real_cloud_gateway(auth_app, auth_database, admin_account, tmp_path, request, allowed):
    image = request.config.getoption("--cloud-image")
    if not image:
        pytest.skip("未启用真实镜像检查；先构建云测试镜像，再提供 --cloud-image")
    command = auth_database["TEST_DOCKER_COMMAND"]
    env = dict(os.environ)
    for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        env.pop(name, None)
    def docker(args, *, input=None):
        result = subprocess.run(command + args, env=env, capture_output=True, text=True, input=input)
        assert result.returncode == 0, "专属云测试容器操作失败；未操作ECS或既有服务"
        return result.stdout.strip()

    backend, gateway = "bumbum-cloud-api-" + uuid.uuid4().hex[:10], "bumbum-cloud-gateway-" + uuid.uuid4().hex[:10]
    api_port, tls_port, http_port = unused_port(), unused_port(), unused_port()
    password = secrets.token_hex(32)
    config = {name: auth_app.config[name] for name in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME", "STORAGE_ENCRYPTION_KEY", "IP_HASH_KEY")}
    config.update(APP_ENV="production", ADMIN_ORIGIN="https://test.bumbum.cc", WEBHOOK_ADMIN_USERNAME=admin_account["username"], WEBHOOK_SHARED_SECRET=password)
    env_file = tmp_path / "cloud.env"
    env_file.write_text("".join(f"{name}={value}\n" for name, value in config.items()), encoding="utf-8")
    env_file.chmod(0o600)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test.bumbum.cc")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(private_key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("test.bumbum.cc"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .sign(private_key, hashes.SHA256()))
    (tmp_path / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (tmp_path / "key.pem").write_bytes(private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (tmp_path / "key.pem").chmod(0o600)
    template = (ROOT / "deploy/cloud_test/nginx-https.conf.template").read_text(encoding="utf-8")
    site = (template.replace("__ADMIN_IP__", "127.0.0.1" if allowed else "192.0.2.10")
            .replace("listen 80;", f"listen 127.0.0.1:{http_port};").replace("listen 443 ssl;", f"listen 127.0.0.1:{tls_port} ssl;")
            .replace("127.0.0.1:15000", f"127.0.0.1:{api_port}")
            .replace("/etc/letsencrypt/live/test.bumbum.cc/fullchain.pem", "/etc/nginx/test-cert.pem")
            .replace("/etc/letsencrypt/live/test.bumbum.cc/privkey.pem", "/etc/nginx/test-key.pem")
            .replace("/var/www/bumbum-cloud-test", "/usr/share/nginx/html"))
    (tmp_path / "site.conf").write_text(site, encoding="utf-8")
    (tmp_path / "nginx.conf").write_text("events {}\nhttp { include /etc/nginx/mime.types; include /etc/nginx/test-site.conf; }\n", encoding="utf-8")
    context = ssl.create_default_context(cafile=str(tmp_path / "cert.pem"))
    created = []
    try:
        # 使用交付镜像的真实启动参数，只替换专属测试端口，避免漏测默认配置。
        runtime = json.loads(docker(["image", "inspect", "--format", "{{json .Config.Cmd}}", image]))
        runtime[runtime.index("--bind") + 1] = f"127.0.0.1:{api_port}"
        docker(["create", "--name", backend, "--label", "bumbum.test=cloud-gateway", "--network=host", "--read-only", "--tmpfs", "/tmp", "--volume", "/app/logs", "--cap-drop=ALL", "--security-opt=no-new-privileges:true", "--env-file", str(env_file), image,
                *runtime])
        created.append(backend)
        docker(["start", backend])
        docker(["create", "--name", gateway, "--label", "bumbum.test=cloud-gateway", "--network=host", "nginx:1.28-alpine"])
        created.append(gateway)
        for name, destination in (("nginx.conf", "/etc/nginx/nginx.conf"), ("site.conf", "/etc/nginx/test-site.conf"), ("cert.pem", "/etc/nginx/test-cert.pem"), ("key.pem", "/etc/nginx/test-key.pem")):
            docker(["cp", str(tmp_path / name), f"{gateway}:{destination}"])
        docker(["cp", str(ROOT / "deploy/cloud_test/nginx-proxy.conf"), gateway + ":/etc/nginx/bumbum-cloud-test-proxy.conf"])
        docker(["start", gateway])
        def call(path, *, method="GET", body=None, headers=None):
            connection = http.client.HTTPSConnection("127.0.0.1", tls_port, context=context, timeout=3)
            try:
                connection.request(method, path, body=json.dumps(body).encode() if body is not None else None,
                                   headers={"Host": "test.bumbum.cc", "Content-Type": "application/json", **(headers or {})})
                response = connection.getresponse()
                return response.status, dict(response.getheaders()), response.read()
            finally:
                connection.close()
        for _ in range(80):
            try:
                status, _, _ = call("/api/ready")
                if status == (200 if allowed else 403):
                    break
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(0.1)
        else:
            diagnostics = subprocess.run(command + ["logs", "--tail=25", backend], env=env, capture_output=True, text=True)
            pytest.fail("专属HTTPS网关未就绪；合成环境启动记录：\n" + diagnostics.stdout + diagnostics.stderr)
        status, _, _ = call("/")
        assert status == (200 if allowed else 403)
        challenge, headers, _ = call("/api/webhook/admin/scan", method="POST", body={"identifier": UID})
        assert challenge == 401 and headers["WWW-Authenticate"] == 'Basic realm="bumbum-scan"'
        diagnostics = subprocess.run(command + ["logs", backend], env=env, capture_output=True, text=True)
        log_text = diagnostics.stdout + diagnostics.stderr
        assert "扫码认证诊断" not in log_text
        assert "扫码请求观察" not in log_text
        assert "Control server error" not in log_text
        assert password not in log_text and admin_account["password"] not in log_text
        credentials = authorization(admin_account["username"], password)
        saved, _, data = call("/api/webhook/admin/scan", method="POST", body={"identifier": UID}, headers=credentials)
        assert saved == 200 and json.loads(data)["data"]["is_new"] is True
        oversized, _, data = call("/api/webhook/admin/scan", method="POST", body={"identifier": UID, "content": "x" * 9000}, headers=credentials)
        assert oversized == 400 and json.loads(data)["code"] == "invalid_param"
        if allowed:
            code = pyotp.TOTP(admin_account["secret"]).now()
            status, headers, _ = call("/api/admin/auth/login", method="POST", headers={"Origin": "https://test.bumbum.cc"}, body={"username": admin_account["username"], "password": admin_account["password"], "code": code})
            assert status == 200 and "Secure" in headers["Set-Cookie"]
            cookie = headers["Set-Cookie"].split(";", 1)[0]
            status, _, data = call("/api/admin/chips", headers={"Cookie": cookie})
            assert status == 200 and json.loads(data)["data"]["items"][0]["chip_uid"] == UID
            assert docker(["exec", backend, "python", "-c", "import getpass; print(getpass.getuser())"]) == "bumbum"
            docker(["restart", backend])
            for _ in range(80):
                try:
                    if call("/api/ready")[0] == 200:
                        break
                except (OSError, http.client.HTTPException):
                    pass
                time.sleep(0.1)
            status, _, data = call("/api/admin/chips", headers={"Cookie": cookie})
            assert status == 200 and json.loads(data)["data"]["total"] == 1
            # 真实CLI能写受限日志，停用完成后手机和原登录都立即失效。
            docker(["exec", "-i", backend, "python", "-m", "flask", "--app", "app:create_app", "admin", "disable", admin_account["username"]], input="y\n")
            assert call("/api/webhook/admin/scan", method="POST", body={"identifier": UID}, headers=credentials)[0] == 401
            assert call("/api/admin/chips", headers={"Cookie": cookie})[0] == 401
        else:
            assert call("/api/admin/chips", headers={**credentials, "X-Real-IP": "192.0.2.10", "X-Forwarded-For": "192.0.2.10"})[0] == 403
            assert call("/api/admin/auth/login", method="POST", body={}, headers={"Origin": "https://test.bumbum.cc"})[0] == 403
        log = docker(["exec", gateway, "cat", "/var/log/nginx/bumbum-cloud-test-access.log"])
        assert password not in log and UID not in log and admin_account["password"] not in log
        with pytest.raises(ConnectionError):
            call("/api/webhook/admin/scan", method="POST", body={}, headers={"Host": "unknown.example"})
        for _ in range(30):
            status, _, data = call("/api/webhook/admin/scan", method="POST", body={"identifier": UID})
            if status == 429:
                assert json.loads(data)["code"] == "rate_limited"
                break
        else:
            pytest.fail("Nginx扫描入口应拦住超过本次限额的请求")
        assert query(auth_app, "SELECT COUNT(*) AS n FROM chip")[0]["n"] == 1
    finally:
        for container in reversed(created):
            docker(["rm", "--force", "--volumes", container])
