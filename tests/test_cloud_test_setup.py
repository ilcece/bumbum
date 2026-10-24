"""检查云测试配置的秘密隔离、原文件保留及管理IP输入，不启动真实服务器。"""

from pathlib import Path
import shutil
import stat
import json
import os
import subprocess
import ssl

import pytest

from scripts.setup_cloud_test import prepare, prepare_build_ca

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cloud_root(tmp_path):
    target = tmp_path / "deploy/cloud_test"
    target.mkdir(parents=True)
    shutil.copyfile(ROOT / "deploy/cloud_test/nginx-https.conf.template", target / "nginx-https.conf.template")
    (tmp_path / "db").mkdir()
    shutil.copyfile(ROOT / "db/schema.sql", tmp_path / "db/schema.sql")
    return tmp_path


def test_cloud_secrets_are_separate_private_and_never_overwritten(cloud_root, capsys):
    local = cloud_root / ".env"
    local.write_text("DB_PASSWORD=本机测试占位内容\n", encoding="utf-8")
    prepare(cloud_root, "1.1.1.1", "cece")
    config = cloud_root / ".env.cloud-test"
    first = config.read_bytes()
    prepare(cloud_root, "8.8.8.8", "other-name")
    assert config.read_bytes() == first
    assert local.read_text(encoding="utf-8") == "DB_PASSWORD=本机测试占位内容\n"
    values = dict(line.split("=", 1) for line in first.decode().splitlines() if "=" in line)
    assert values["ADMIN_ORIGIN"] == "https://test.bumbum.cc"
    assert values["WEBHOOK_ADMIN_USERNAME"] == "cece"
    assert values["APP_ENV"] == "production" and values["DB_PORT"] == "33307"
    passwords = [values[name] for name in ("DB_PASSWORD", "CLOUD_DB_ROOT_PASSWORD", "STORAGE_ENCRYPTION_KEY", "IP_HASH_KEY", "WEBHOOK_SHARED_SECRET")]
    assert len(set(passwords)) == len(passwords)
    output = capsys.readouterr().out
    assert all(password not in output for password in passwords)
    if os.name != "nt":
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
        assert stat.S_IMODE((cloud_root / "db/schema.sql").stat().st_mode) == 0o644
    assert "allow 8.8.8.8;" in (cloud_root / ".cloud-test/nginx-https.conf").read_text(encoding="utf-8")


@pytest.mark.parametrize("address", ["127.0.0.1", "192.168.1.2", "192.0.2.1", "1.1.1.1; allow all", "0.0.0.0/0", "224.0.0.1"])
def test_invalid_admin_ip_cannot_open_access_or_create_secrets(cloud_root, address):
    with pytest.raises(ValueError):
        prepare(cloud_root, address, "cece")
    assert not (cloud_root / ".env.cloud-test").exists()


def test_symlink_configuration_never_overwrites_other_file(cloud_root):
    target = cloud_root / "other"
    target.write_text("保留", encoding="utf-8")
    try:
        (cloud_root / ".env.cloud-test").symlink_to(target)
    except OSError:
        pytest.skip("当前系统未允许创建软链接；云服务器仍须执行此检查")
    with pytest.raises(ValueError):
        prepare(cloud_root, "1.1.1.1", "cece")
    assert target.read_text(encoding="utf-8") == "保留"


@pytest.fixture
def system_ca():
    source = ssl.get_default_verify_paths().cafile
    if source is None:
        pytest.skip("本机没有可读取的CA文件；服务器仍须执行构建检查")
    return Path(source)


def test_build_ca_stays_inside_project_and_preserves_configuration(cloud_root, system_ca):
    prepare(cloud_root, "1.1.1.1", "cece")
    config = (cloud_root / ".env.cloud-test").read_bytes()
    nginx = (cloud_root / ".cloud-test/nginx-https.conf").read_bytes()
    source = system_ca.read_bytes()
    for _ in range(2):
        prepare_build_ca(cloud_root, system_ca)
    target = cloud_root / ".cloud-test/build-ca.crt"
    assert target.read_bytes() == source and system_ca.read_bytes() == source
    assert (cloud_root / ".env.cloud-test").read_bytes() == config
    assert (cloud_root / ".cloud-test/nginx-https.conf").read_bytes() == nginx
    assert not list(target.parent.glob("build-ca-*"))
    ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).load_verify_locations(cafile=str(target))
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_invalid_ca_does_not_replace_previous_trust(cloud_root, system_ca):
    prepare_build_ca(cloud_root, system_ca)
    target = cloud_root / ".cloud-test/build-ca.crt"
    before = target.read_bytes()
    invalid = cloud_root / "invalid-ca"
    invalid.write_text("无效证书占位内容", encoding="utf-8")
    with pytest.raises(ValueError, match="证书包"):
        prepare_build_ca(cloud_root, invalid)
    assert target.read_bytes() == before


@pytest.mark.auth_database
def test_actual_compose_keeps_root_password_out_of_backend(cloud_root, auth_database, system_ca):
    prepare(cloud_root, "1.1.1.1", "cece")
    prepare_build_ca(cloud_root, system_ca)
    env = dict(os.environ)
    for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH",
                 "DB_USER", "DB_PASSWORD", "CLOUD_DB_ROOT_PASSWORD", "STORAGE_ENCRYPTION_KEY", "IP_HASH_KEY", "WEBHOOK_ADMIN_USERNAME", "WEBHOOK_SHARED_SECRET"):
        env.pop(name, None)
    result = subprocess.run(auth_database["TEST_DOCKER_COMMAND"] + ["compose", "--env-file", str(cloud_root / ".env.cloud-test"), "-f", str(ROOT / "deploy/cloud_test/compose.yaml"), "config", "--format", "json"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, "Compose配置解析失败；不输出包含测试秘密的展开配置"
    config = json.loads(result.stdout)
    api, db = config["services"]["backend"], config["services"]["db"]
    assert "CLOUD_DB_ROOT_PASSWORD" not in api["environment"]
    assert "MYSQL_ROOT_PASSWORD" not in api["environment"]
    assert api["environment"]["DB_HOST"] == "127.0.0.1" and api["environment"]["DB_PORT"] == "33307"
    assert api["environment"]["ADMIN_ORIGIN"] == "https://test.bumbum.cc"
    assert db["ports"][0]["host_ip"] == "127.0.0.1" and db["ports"][0]["published"] == "33307"
    assert api["read_only"] is True and "ALL" in api["cap_drop"]
    # 构建只读取项目内的暂存CA，不要求访问/etc等额外目录。
    source = Path(config["secrets"]["proxy_ca"]["file"])
    assert source.is_relative_to(ROOT) and source.name == "build-ca.crt"
