"""检查杭州生产/测试隔离、公开配置注入与错误目标拒绝；不访问云端。"""

import json
import os
import subprocess

import pytest

from scripts import hangzhou
from tests.test_database_tls import certificates


def manifest(slot):
    return hangzhou.render_manifest(slot, "bumbum-hangzhou-backend:" + "a" * 40, "sha256:" + "b" * 64,
                                    "hz-test-admin.bumbum.cc" if slot == "test" else "admin.bumbum.cc",
                                    "hz-test-nfc.bumbum.cc" if slot == "test" else "nfc.bumbum.cc")


def test_slots_have_distinct_database_identity_ports_directories_and_volumes():
    prod, test = manifest("production"), manifest("test")
    assert prod["name"] != test["name"]
    for key in ("DB_NAME", "DB_USER", "ADMIN_ORIGIN", "PUBLIC_ORIGIN", "HANGZHOU_SLOT"):
        assert prod["services"]["backend"]["environment"][key] != test["services"]["backend"]["environment"][key]
    for document in (prod, test):
        service = document["services"]["backend"]
        assert set(document["services"]) == {"backend"}
        assert service["environment"]["DB_SSL_MODE"] == "VERIFY_IDENTITY"
        assert "DB_PASSWORD" not in service["environment"]
        assert service["env_file"][0]["format"] == "raw"
        assert service["read_only"] and service["cap_drop"] == ["ALL"]
        assert service["mem_limit"] == service["memswap_limit"]
        assert service["command"][3].startswith("127.0.0.1:")
        assert service["volumes"][1]["bind"]["create_host_path"] is False
    assert prod["services"]["backend"]["env_file"] != test["services"]["backend"]["env_file"]
    assert prod["services"]["backend"]["command"][3] != test["services"]["backend"]["command"][3]


@pytest.mark.parametrize("admin,user", [("admin.bumbum.cc", "test-user.bumbum.cc"),
                                      ("test-admin.bumbum.cc", "nfc.bumbum.cc"),
                                      ("test.bumbum.cc;include /tmp/x", "test-user.bumbum.cc"),
                                      ("test.bumbum.cc", "test.bumbum.cc")])
def test_invalid_or_production_test_domain_is_refused(admin, user):
    with pytest.raises(hangzhou.DeploymentError):
        hangzhou.render_manifest("test", "bumbum-hangzhou-backend:" + "a" * 40,
                                 "sha256:" + "b" * 64, admin, user)


def test_rendered_gateways_keep_user_allowlist_and_separate_limits():
    a = hangzhou.render_nginx("test", "test.bumbum.cc", "nfc-test.bumbum.cc", "192.0.2.1")
    b = hangzhou.render_nginx("production", "admin.bumbum.cc", "nfc.bumbum.cc", "192.0.2.1")
    assert "127.0.0.1:15001" in a["user.conf"] and "127.0.0.1:15000" in b["user.conf"]
    assert "zone=bumbum_hz_test_user_view" in a["user.conf"]
    assert "zone=bumbum_hz_production_user_view" in b["user.conf"]
    assert "location / { return 404; }" in a["user.conf"]
    assert "location = /api/webhook/admin/scan" in a["admin.conf"]
    assert "allow 192.0.2.1;" in a["admin.conf"]
    assert "bumbum-cloud-test" not in a["admin.conf"] + a["user.conf"]
    assert "$request_uri" not in a["admin.conf"].split("log_format", 1)[1].split(";", 1)[0]
    with pytest.raises(hangzhou.DeploymentError):
        hangzhou.render_nginx("test", "test.bumbum.cc", "nfc-test.bumbum.cc", "0.0.0.0/0")


def test_existing_generated_or_manual_configuration_is_not_overwritten(tmp_path):
    p = tmp_path / "compose.json"
    hangzhou.write_new(p, "original")
    hangzhou.write_new(p, "original")
    with pytest.raises(hangzhou.DeploymentError):
        hangzhou.write_new(p, "different")
    assert p.read_text() == "original"


def test_changed_image_content_and_modified_target_are_refused(tmp_path, monkeypatch):
    document = manifest("test")
    path = tmp_path / "compose.json"
    path.write_text(json.dumps(document))
    monkeypatch.setattr(hangzhou, "docker", lambda args: "sha256:" + "c" * 64)
    with pytest.raises(hangzhou.DeploymentError, match="镜像标签"):
        hangzhou.check_deployment(path, "test", require_runtime=False)
    document["services"]["backend"]["environment"]["DB_NAME"] = "bumbum_hz_production"
    path.write_text(json.dumps(document))
    with pytest.raises(hangzhou.DeploymentError, match="保护不符"):
        hangzhou.check_deployment(path, "test", require_runtime=False)


def test_other_directory_project_is_not_adopted(tmp_path, monkeypatch):
    document = manifest("test")
    path = tmp_path / "compose.json"
    path.write_text(json.dumps(document))
    def docker(args):
        if args[:2] == ["image", "inspect"]:
            return "sha256:" + "b" * 64
        if args[:2] == ["ps", "-aq"]:
            return "synthetic-container-id"
        return "/other-session/compose.json"
    monkeypatch.setattr(hangzhou, "docker", docker)
    with pytest.raises(hangzhou.DeploymentError, match="其他Compose路径"):
        hangzhou.check_deployment(path, "test", require_runtime=False)


def test_production_start_requires_explicit_confirmation_before_docker(tmp_path, monkeypatch):
    monkeypatch.setattr(hangzhou, "docker", lambda args: pytest.fail("不得调用Docker"))
    assert hangzhou.main(["start", "--slot", "production", "--manifest", str(tmp_path / "none")]) == 1


def test_new_test_runtime_is_private_unique_and_existing_config_is_not_read_or_overwritten(tmp_path, capsys):
    path = tmp_path / "secrets/runtime.env"
    hangzhou.prepare_test_runtime(path, "synthetic$#only=password", "test-admin")
    assert path.stat().st_mode & 0o777 == 0o600
    content = path.read_text()
    assert "DB_PASSWORD=synthetic$#only=password\n" in content
    values = dict(line.split("=", 1) for line in content.splitlines())
    keys = [values[name] for name in ("STORAGE_ENCRYPTION_KEY", "IP_HASH_KEY", "WEBHOOK_SHARED_SECRET",
                                     "MASTER_KEY_FASHION", "MASTER_KEY_JEWELRY", "SDM_META_KEY_V1")]
    assert len(set(keys)) == 6
    assert all(value not in capsys.readouterr().out for value in keys)
    with pytest.raises(hangzhou.DeploymentError, match="未读取或覆盖"):
        hangzhou.prepare_test_runtime(path, "other-test-only", "test-admin")
    assert path.read_text() == content


def test_production_never_generates_replacement_secrets(tmp_path):
    assert hangzhou.main(["prepare-runtime", "--slot", "production", "--manifest", str(tmp_path / "none")]) == 1


@pytest.mark.parametrize('action', ['admin-create', 'export-qr'])
def test_test_account_setup_never_touches_production(action, tmp_path, monkeypatch):
    monkeypatch.setattr(hangzhou, 'docker', lambda args: pytest.fail('不得调用Docker'))
    assert hangzhou.main([action, '--slot', 'production', '--manifest', str(tmp_path / 'none')]) == 1


def test_authenticator_export_is_private_and_never_prints_or_overwrites(tmp_path, monkeypatch, capsys):
    parent = tmp_path / 'secrets'
    parent.mkdir(mode=0o700)
    destination = parent / 'authenticator.html'
    page = b'<html>synthetic-authenticator-page-only</html>'
    calls = []

    def run(command, *, env, stdout, stderr, timeout):
        calls.append(command)
        stdout.write(page)
        return subprocess.CompletedProcess(command, 0, stderr=b'')

    monkeypatch.setattr(hangzhou.subprocess, 'run', run)
    hangzhou.export_authenticator(['exec', 'synthetic-container'], '/tmp/bumbum-authenticator-test/authenticator.html', destination)
    assert destination.read_bytes() == page
    assert destination.stat().st_mode & 0o777 == 0o600
    assert page.decode() not in capsys.readouterr().out
    with pytest.raises(hangzhou.DeploymentError, match='已有'):
        hangzhou.export_authenticator(['exec', 'synthetic-container'], '/tmp/bumbum-authenticator-test/authenticator.html', destination)
    assert len(calls) == 1 and destination.read_bytes() == page
    assert list(parent.iterdir()) == [destination]


def test_failed_authenticator_export_removes_partial_and_hides_stderr(tmp_path, monkeypatch, capsys):
    parent = tmp_path / 'secrets'
    parent.mkdir(mode=0o700)

    def run(command, *, env, stdout, stderr, timeout):
        stdout.write(b'synthetic-partial-page')
        return subprocess.CompletedProcess(command, 1, stderr=b'synthetic-private-marker')

    monkeypatch.setattr(hangzhou.subprocess, 'run', run)
    with pytest.raises(hangzhou.DeploymentError, match='未完成'):
        hangzhou.export_authenticator(['exec', 'synthetic-container'], '/tmp/bumbum-authenticator-test/authenticator.html', parent / 'authenticator.html')
    assert list(parent.iterdir()) == []
    assert 'synthetic-private-marker' not in capsys.readouterr().out


@pytest.mark.parametrize('source', ['/etc/shadow', '/tmp/other.html', '/tmp/bumbum-authenticator-../authenticator.html'])
def test_authenticator_export_rejects_other_paths_before_docker(source, tmp_path, monkeypatch):
    monkeypatch.setattr(hangzhou.subprocess, 'run', lambda *a, **kw: pytest.fail('不得读取'))
    with pytest.raises(hangzhou.DeploymentError, match='完整临时页面路径'):
        hangzhou.export_authenticator([], source, tmp_path / 'authenticator.html')


@pytest.mark.auth_database
def test_authenticator_export_from_real_tmpfs_refuses_symlink(request, tmp_path):
    """只用合成页面和无网络容器，验证真实内存盘导出与符号链接拒绝。"""
    if not request.config.getoption('--auth-db'):
        pytest.skip('需显式--auth-db，用专属无网络容器验证私有页面传输')
    import time
    import uuid
    name = 'bumbum-qr-export-test-' + uuid.uuid4().hex[:12]
    folder = '/tmp/bumbum-authenticator-synthetic'
    page = b'<html>synthetic-tmpfs-page-only</html>'
    program = ('from pathlib import Path; import signal; '
               f'p=Path({folder!r}); p.mkdir(mode=0o700); '
               f'q=p/"authenticator.html"; q.write_bytes({page!r}); q.chmod(0o600); '
               'signal.pause()')
    env = {name: value for name, value in os.environ.items()
           if name not in {'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'}}
    command = ['docker', '--host=unix:///var/run/docker.sock']

    def docker(args):
        return subprocess.run([*command, *args], env=env, capture_output=True, text=True, timeout=60)

    try:
        assert docker(['run', '-d', '--name', name, '--label', 'bumbum.test=qr-export', '--network', 'none',
                       '--read-only', '--user', '10001:10001', '--tmpfs', '/tmp:mode=1777',
                       'python:3.12.14-slim-bookworm', 'python', '-c', program]).returncode == 0
        for _ in range(50):
            if docker(['exec', name, 'test', '-f', folder + '/authenticator.html']).returncode == 0:
                break
            time.sleep(0.1)
        else:
            pytest.fail('合成页面未就绪，不输出容器配置或原始日志')
        destination = tmp_path / 'authenticator.html'
        hangzhou.export_authenticator(['exec', name], folder + '/authenticator.html', destination)
        assert destination.read_bytes() == page and destination.stat().st_mode & 0o777 == 0o600
        destination.unlink()
        replace = ('from pathlib import Path; '
                   f'p=Path({folder + "/authenticator.html"!r}); p.rename(p.with_name("synthetic-original.html")); '
                   'p.symlink_to(p.with_name("synthetic-original.html"))')
        assert docker(['exec', name, 'python', '-c', replace]).returncode == 0
        with pytest.raises(hangzhou.DeploymentError, match='未完成'):
            hangzhou.export_authenticator(['exec', name], folder + '/authenticator.html', destination)
        assert not destination.exists() and list(tmp_path.iterdir()) == []
    finally:
        docker(['rm', '-f', name])


@pytest.mark.auth_database
def test_both_slot_nginx_configurations_parse_together(request, certificates, tmp_path):
    if not request.config.getoption("--auth-db"):
        pytest.skip("需显式--auth-db，使用专属无网络Nginx容器检查合并配置")
    folder = tmp_path / "nginx"
    folder.mkdir()
    for slot, admin, user in (("test", "test.bumbum.cc", "nfc-test.bumbum.cc"),
                               ("production", "admin.bumbum.cc", "nfc.bumbum.cc")):
        config = hangzhou.render_nginx(slot, admin, user, "192.0.2.1")
        for name, content in config.items():
            for host in (admin, user):
                content = content.replace(f"/etc/letsencrypt/live/{host}/fullchain.pem", "/tls/server.crt")
                content = content.replace(f"/etc/letsencrypt/live/{host}/privkey.pem", "/tls/server.key")
            content = content.replace(f"/etc/nginx/bumbum-hangzhou-{slot}-proxy.conf", f"/generated/{slot}-proxy.inc")
            (folder / (slot + "-proxy.inc" if name == "proxy.conf" else slot + "-" + name)).write_text(content)
    (folder / "nginx.conf").write_text("pid /tmp/nginx.pid;\nerror_log stderr;\nevents {}\nhttp {\n"
                                     "include /etc/nginx/mime.types; include /generated/*-admin.conf; "
                                     "include /generated/*-user.conf; }\n")
    env = {k: v for k, v in os.environ.items() if k not in {
        "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}
    result = subprocess.run(["docker", "--host=unix:///var/run/docker.sock", "run", "--rm", "--network", "none",
                             "--read-only", "--tmpfs", "/tmp", "--tmpfs", "/var/log/nginx", "--tmpfs", "/var/cache/nginx", "--entrypoint", "nginx",
                             "--mount", f"type=bind,src={folder},dst=/generated,readonly",
                             "--mount", f"type=bind,src={certificates},dst=/tls,readonly", "nginx:1.28-alpine",
                             "-t", "-c", "/generated/nginx.conf"], env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, "独立Nginx合并配置检查失败（仅生成配置与合成证书）：" + result.stderr
