"""检查杭州生产/测试隔离、公开配置注入与错误目标拒绝；不访问云端。"""

import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import hangzhou
from tests.test_database_tls import certificates


def manifest(slot):
    return hangzhou.render_manifest(slot, "bumbum-hangzhou-backend:" + "a" * 40, "sha256:" + "b" * 64,
                                    "hz-test-admin.bumbum.cc" if slot == "test" else "admin.bumbum.cc",
                                    "hz-test-nfc.bumbum.cc" if slot == "test" else "nfc.bumbum.cc")


def production_pilot_manifest():
    document = manifest("production")
    service = document["services"]["backend"]
    service["environment"].update({"MEDIA_ENABLED": "false", "SMS_PROVIDER": "aliyun_pilot",
                                    "H5_LEGACY_ITEM_UNTIL": "2026-11-17T10:37:57+00:00"})
    service["env_file"] = [
        {"path": "/opt/bumbum-hangzhou/production/secrets/runtime.env", "format": "raw"},
        {"path": "/opt/bumbum-hangzhou/production/secrets/sms-pilot.env", "format": "raw", "required": False},
    ]
    return document


@pytest.mark.parametrize("slot,pilot", [("test", False), ("production", False), ("production", True)])
def test_manifest_validation_is_pure_and_preserves_approved_profiles(slot, pilot, monkeypatch):
    document = production_pilot_manifest() if pilot else manifest(slot)
    before = deepcopy(document)
    monkeypatch.setattr(hangzhou, "docker", lambda args: pytest.fail("不得调用Docker"))
    monkeypatch.setattr(hangzhou, "Path", lambda *args: pytest.fail("不得读取文件"))
    assert hangzhou.validate_manifest(document, slot) == before
    assert document == before


@pytest.mark.parametrize("keys,value", [
    (("environment", "DB_NAME"), "bumbum_hz_test"),
    (("environment", "DB_USER"), "bumbum_hz_test"),
    (("environment", "DB_SSL_MODE"), "DISABLED"),
    (("environment", "ADMIN_ORIGIN"), "https://test.bumbum.cc"),
    (("environment", "MEDIA_ENABLED"), "true"),
    (("environment", "SMS_PROVIDER"), "aliyun"),
    (("environment", "H5_LEGACY_ITEM_UNTIL"), "2099-11-17T10:37:57+00:00"),
    (("environment", "ARBITRARY_EXTRA"), "unsupported"),
    (("env_file", 1, "path"), "/opt/bumbum-hangzhou/test/secrets/sms-pilot.env"),
    (("env_file", 1, "format"), "default"),
    (("env_file", 1, "required"), True),
    (("env_file", 1, "required"), 0),
    (("command", 3), "0.0.0.0:15000"),
    (("volumes", 2, "source"), "/opt/bumbum-hangzhou/test/media"),
])
def test_unapproved_production_profile_is_rejected_before_docker(keys, value, tmp_path, monkeypatch):
    document = production_pilot_manifest()
    target = document["services"]["backend"]
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    path = tmp_path / "compose.json"
    path.write_text(json.dumps(document))
    monkeypatch.setattr(hangzhou, "docker", lambda args: pytest.fail("错误配置不得调用Docker"))
    with pytest.raises(hangzhou.DeploymentError):
        hangzhou.check_deployment(path, "production", require_runtime=False)


def test_production_pilot_requires_the_complete_profile_and_file_order():
    document = production_pilot_manifest()
    document["services"]["backend"]["env_file"].reverse()
    with pytest.raises(hangzhou.DeploymentError):
        hangzhou.validate_manifest(document, "production")
    document = production_pilot_manifest()
    del document["services"]["backend"]["environment"]["H5_LEGACY_ITEM_UNTIL"]
    with pytest.raises(hangzhou.DeploymentError):
        hangzhou.validate_manifest(document, "production")
    with pytest.raises(hangzhou.DeploymentError):
        hangzhou.validate_manifest(production_pilot_manifest(), "test")


def test_approved_production_pilot_uses_existing_image_and_project_checks(tmp_path, monkeypatch):
    document = production_pilot_manifest()
    path = tmp_path / "compose.json"
    path.write_text(json.dumps(document))
    calls = []

    def docker(args):
        calls.append(args)
        if args[:2] == ["image", "inspect"]:
            return "sha256:" + "b" * 64
        if args[:2] == ["ps", "-aq"]:
            return "owned-container"
        return str(path.resolve())

    monkeypatch.setattr(hangzhou, "docker", docker)
    assert hangzhou.check_deployment(path, "production", require_runtime=False) == document
    assert any(args[:2] == ["image", "inspect"] for args in calls)
    assert any(args[0] == "inspect" and args[-1] == "owned-container" for args in calls)
    monkeypatch.setattr(hangzhou, "docker", lambda args: "sha256:" + "c" * 64)
    with pytest.raises(hangzhou.DeploymentError, match="镜像标签"):
        hangzhou.check_deployment(path, "production", require_runtime=False)


@pytest.mark.parametrize("slot,pilot", [("test", False), ("production", False), ("production", True)])
def test_prepare_update_changes_only_image_identity_without_docker_or_private_reads(slot, pilot, tmp_path, monkeypatch):
    document = production_pilot_manifest() if pilot else manifest(slot)
    source = tmp_path / "current.json"
    source.write_text(json.dumps(document))
    original = source.read_bytes()
    output = tmp_path / "candidate/compose.json"
    private_paths = {entry["path"] for entry in document["services"]["backend"]["env_file"]}
    read_text = Path.read_text

    def public_read(path, *args, **kwargs):
        assert str(path) not in private_paths, "不得读取私有配置内容"
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", public_read)
    monkeypatch.setattr(hangzhou, "docker", lambda args: pytest.fail("生成候选不得调用Docker"))
    assert hangzhou.main(["prepare-update", "--slot", slot, "--manifest", str(source),
                          "--output", str(output), "--image", "bumbum-hangzhou-backend:" + "c" * 40,
                          "--image-id", "sha256:" + "d" * 64]) == 0
    candidate = json.loads(output.read_text())
    assert candidate["services"]["backend"]["image"] == "bumbum-hangzhou-backend:" + "c" * 40
    assert candidate["services"]["backend"]["labels"]["cc.bumbum.image-id"] == "sha256:" + "d" * 64
    candidate["services"]["backend"]["image"] = document["services"]["backend"]["image"]
    candidate["services"]["backend"]["labels"]["cc.bumbum.image-id"] = document["services"]["backend"]["labels"]["cc.bumbum.image-id"]
    assert candidate == document and source.read_bytes() == original
    assert sorted(path.name for path in tmp_path.iterdir()) == ["candidate", "current.json"]


@pytest.mark.parametrize("output_kind", ["source", "symlink-to-source", "private-file", "same-content",
                                        "symlink-to-private", "dangling-symlink"])
def test_prepare_update_refuses_every_existing_output_without_reading_it(output_kind, tmp_path, monkeypatch):
    source = tmp_path / "current.json"
    document = production_pilot_manifest()
    source.write_text(json.dumps(document))
    original = source.read_bytes()
    output = source if output_kind == "source" else tmp_path / ("runtime.env" if output_kind == "private-file" else "candidate.json")
    if output_kind == "symlink-to-source":
        output.symlink_to(source)
    elif output_kind in {"symlink-to-private", "dangling-symlink"}:
        target = tmp_path / "private.env"
        if output_kind == "symlink-to-private":
            target.write_text("synthetic-private-content")
        output.symlink_to(target)
    elif output_kind == "same-content":
        document["services"]["backend"]["image"] = "bumbum-hangzhou-backend:" + "c" * 40
        document["services"]["backend"]["labels"]["cc.bumbum.image-id"] = "sha256:" + "d" * 64
        output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    elif output_kind == "private-file":
        output.write_text("synthetic-private-content")
    original_output = output.read_bytes() if output.exists() else None
    original_link = output.readlink() if output.is_symlink() else None
    read_text = Path.read_text

    def public_source_only(path, *args, **kwargs):
        assert path != output, "不得读取已有输出，即使内容相同或误指私有文件"
        return read_text(path, *args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(Path, "read_text", public_source_only)
        patched.setattr(hangzhou, "docker", lambda args: pytest.fail("不得调用Docker"))
        with pytest.raises(hangzhou.DeploymentError):
            hangzhou.prepare_update(source, output, "production", "bumbum-hangzhou-backend:" + "c" * 40, "sha256:" + "d" * 64)
    assert source.read_bytes() == original
    if original_output is not None:
        assert output.read_bytes() == original_output
    if original_link is not None:
        assert output.is_symlink() and output.readlink() == original_link


@pytest.mark.parametrize("source_kind", ["env-file", "json-alias-to-env"])
def test_prepare_update_rejects_nonjson_source_before_reading(source_kind, tmp_path, monkeypatch):
    private = tmp_path / "runtime.env"
    private.write_text("synthetic-private-content")
    source = private
    if source_kind == "json-alias-to-env":
        source = tmp_path / "alias.json"
        source.symlink_to(private)
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: pytest.fail("不得读取私有源"))
    monkeypatch.setattr(hangzhou, "docker", lambda args: pytest.fail("不得调用Docker"))
    output = tmp_path / "candidate.json"
    with pytest.raises(hangzhou.DeploymentError, match=".json公开Compose清单"):
        hangzhou.prepare_update(source, output, "production", "bumbum-hangzhou-backend:" + "c" * 40, "sha256:" + "d" * 64)
    assert not output.exists() and private.read_bytes() == b"synthetic-private-content"


@pytest.mark.parametrize("created_kind", ["file", "symlink"])
def test_prepare_update_preserves_output_created_after_existence_check(created_kind, tmp_path, monkeypatch):
    source = tmp_path / "current.json"
    source.write_text(json.dumps(production_pilot_manifest()))
    output = tmp_path / "candidate.json"
    target = tmp_path / "private.env"
    target.write_text("synthetic-private-content")
    original_open, original_read = Path.open, Path.read_text

    def raced_open(path, mode="r", *args, **kwargs):
        if path == output and mode == "x":
            if created_kind == "symlink":
                path.symlink_to(target)
            else:
                with original_open(path, "x", encoding="utf-8") as stream:
                    stream.write("concurrent-user-work")
        return original_open(path, mode, *args, **kwargs)

    def public_source_only(path, *args, **kwargs):
        assert path != output and path != target, "竞态失败后不得读取已有文件"
        return original_read(path, *args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(Path, "open", raced_open)
        patched.setattr(Path, "read_text", public_source_only)
        patched.setattr(hangzhou, "docker", lambda args: pytest.fail("不得调用Docker"))
        with pytest.raises(hangzhou.DeploymentError, match="已被创建"):
            hangzhou.prepare_update(source, output, "production", "bumbum-hangzhou-backend:" + "c" * 40, "sha256:" + "d" * 64)
    assert target.read_text() == "synthetic-private-content"
    if created_kind == "file":
        assert output.read_text() == "concurrent-user-work"
    else:
        assert output.is_symlink() and output.readlink() == target


@pytest.mark.parametrize("image,image_id", [("bumbum-hangzhou-backend:latest", "sha256:" + "d" * 64),
                                             ("bumbum-hangzhou-backend:" + "c" * 40, "sha256:short")])
def test_prepare_update_rejects_unfixed_image_identity_before_writing(image, image_id, tmp_path, monkeypatch):
    source = tmp_path / "current.json"
    source.write_text(json.dumps(production_pilot_manifest()))
    output = tmp_path / "candidate.json"
    monkeypatch.setattr(hangzhou, "docker", lambda args: pytest.fail("不得调用Docker"))
    with pytest.raises(hangzhou.DeploymentError):
        hangzhou.prepare_update(source, output, "production", image, image_id)
    assert not output.exists()


def test_env_file_checks_only_metadata_for_every_present_file_and_optional_absence(tmp_path, monkeypatch):
    first, second = tmp_path / "runtime.env", tmp_path / "sms-pilot.env"
    for path in [first, second]:
        path.write_text("synthetic-private-content")
        path.chmod(0o600)
    entries = [{"path": str(first), "format": "raw"},
               {"path": str(second), "format": "raw", "required": False}]
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: pytest.fail("不得读取私有配置内容"))
    hangzhou.check_env_files(entries)
    second.chmod(0o644)
    with pytest.raises(hangzhou.DeploymentError, match="普通文件"):
        hangzhou.check_env_files(entries)
    second.unlink()
    hangzhou.check_env_files(entries)
    first.unlink()
    with pytest.raises(hangzhou.DeploymentError, match="必要"):
        hangzhou.check_env_files(entries)


@pytest.mark.parametrize("kind", ["directory", "symlink", "dangling-symlink"])
def test_optional_env_file_rejects_nonregular_or_symlink_metadata(kind, tmp_path):
    path = tmp_path / "sms-pilot.env"
    if kind == "directory":
        path.mkdir(mode=0o700)
    else:
        target = tmp_path / "target.env"
        if kind == "symlink":
            target.touch(mode=0o600)
        path.symlink_to(target)
    with pytest.raises(hangzhou.DeploymentError, match="普通文件"):
        hangzhou.check_env_files([{"path": str(path), "format": "raw", "required": False}])


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
        media = service['volumes'][2]
        assert media['source'] == '/opt/bumbum-hangzhou/' + service['environment']['HANGZHOU_SLOT'] + '/media'
        assert media['target'] == service['environment']['MEDIA_ROOT'] == '/app/media'
        assert media['bind']['create_host_path'] is False and 'MEDIA_ENABLED' not in service['environment']
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


@pytest.mark.parametrize("admin,user", [
    ("test.bumbum.cc", "nfc-test.bumbum.cc"),
    ("admin.bumbum.cc", "nfc-test.bumbum.cc"),
    ("test.bumbum.cc", "nfc.bumbum.cc"),
    ("nfc.bumbum.cc", "admin.bumbum.cc"),
])
def test_production_rendering_refuses_test_or_swapped_domains(admin, user):
    """两种公开产物都必须拒绝错误目标，不留可独立绕过的生成入口。"""
    with pytest.raises(hangzhou.DeploymentError, match="生产入口"):
        hangzhou.render_manifest("production", "bumbum-hangzhou-backend:" + "a" * 40,
                                 "sha256:" + "b" * 64, admin, user)
    with pytest.raises(hangzhou.DeploymentError, match="生产入口"):
        hangzhou.render_nginx("production", admin, user, "192.0.2.1")


def test_rendered_gateways_keep_user_allowlist_and_separate_limits():
    a = hangzhou.render_nginx("test", "test.bumbum.cc", "nfc-test.bumbum.cc", "192.0.2.1")
    b = hangzhou.render_nginx("production", "admin.bumbum.cc", "nfc.bumbum.cc", "192.0.2.1")
    assert "127.0.0.1:15001" in a["user.conf"] and "127.0.0.1:15000" in b["user.conf"]
    assert "zone=bumbum_hz_test_user_view" in a["user.conf"]
    assert "zone=bumbum_hz_production_user_view" in b["user.conf"]
    assert 'zone=bumbum_hz_test_user_image' in a['user.conf'] and 'burst=40 nodelay' in a['user.conf']
    assert 'client_max_body_size 9m;' in a['admin.conf'] and 'return 413' in a['admin.conf']
    assert "location / { return 404; }" in a["user.conf"]
    assert "location = /api/webhook/admin/scan" in a["admin.conf"]
    assert "allow 192.0.2.1;" in a["admin.conf"]
    assert "bumbum-cloud-test" not in a["admin.conf"] + a["user.conf"]
    assert "$request_uri" not in a["admin.conf"].split("log_format", 1)[1].split(";", 1)[0]
    with pytest.raises(hangzhou.DeploymentError):
        hangzhou.render_nginx("test", "test.bumbum.cc", "nfc-test.bumbum.cc", "0.0.0.0/0")


def test_media_directory_only_creates_new_private_target_and_preserves_unknown(tmp_path,monkeypatch):
    import os
    calls = []
    monkeypatch.setattr(hangzhou.os,'chown',lambda path,uid,gid: calls.append((path,uid,gid)))
    path = tmp_path / 'media'
    hangzhou.prepare_media_directory(path)
    assert calls == [(path,10001,10001)] and path.stat().st_mode & 0o077 == 0
    # 测试操作者不拥有容器UID；已有错误属主不能被悄悄接管。
    if os.getuid() != 10001:
        with pytest.raises(hangzhou.DeploymentError):
            hangzhou.prepare_media_directory(path)
    link = tmp_path / 'link'; link.symlink_to(path,target_is_directory=True)
    with pytest.raises(hangzhou.DeploymentError):
        hangzhou.prepare_media_directory(link)


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
