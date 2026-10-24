"""用合成页面检查导出不泄漏、不覆盖，失败不留文件；不访问真实容器。"""

import os
from pathlib import Path
import shutil
import stat
import subprocess

import pytest

pytestmark = pytest.mark.skipif(os.name == "nt", reason="香港部署脚本只在Linux运行")
ROOT = Path(__file__).resolve().parents[1]
SOURCE = "/tmp/bumbum-authenticator-testonly/authenticator.html"
PAGE = "<html>合成的私密页面占位内容</html>"


@pytest.fixture
def export_root(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copyfile(ROOT / "scripts/cloud_test.sh", tmp_path / "scripts/cloud_test.sh")
    (tmp_path / ".env.cloud-test").write_text("# 测试占位配置\n", encoding="utf-8")
    (tmp_path / ".cloud-test").mkdir()
    (tmp_path / "bin").mkdir()
    docker = tmp_path / "bin/docker"
    docker.write_text('''#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
if "ps" in args:
    raise SystemExit(0)
if "exec" in args and "-T" in args and "cat" in args:
    if os.getenv("TEST_QR_MISSING"):
        raise SystemExit(1)
    sys.stdout.write(os.environ["TEST_QR_PAGE"])
else:
    raise SystemExit(2)
''', encoding="utf-8")
    docker.chmod(0o700)
    return tmp_path


def invoke(root, *, missing=False, source=SOURCE):
    env = {**os.environ, "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"], "TEST_QR_PAGE": PAGE}
    env.pop("TEST_QR_MISSING", None)
    if missing:
        env["TEST_QR_MISSING"] = "1"
    return subprocess.run(["bash", str(root / "scripts/cloud_test.sh"), "export-qr", source], env=env, capture_output=True, text=True)


def test_export_is_private_does_not_echo_secret_and_cannot_overwrite(export_root):
    result = invoke(export_root)
    assert result.returncode == 0
    target = export_root / ".cloud-test/authenticator.html"
    assert target.read_text(encoding="utf-8") == PAGE
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert PAGE not in result.stdout + result.stderr
    assert not list(target.parent.glob("*.tmp"))
    assert invoke(export_root).returncode != 0
    assert target.read_text(encoding="utf-8") == PAGE


def test_missing_source_leaves_no_download_file(export_root):
    result = invoke(export_root, missing=True)
    assert result.returncode != 0 and "原设置终端" in result.stderr
    assert not list((export_root / ".cloud-test").iterdir())


def test_invalid_path_is_rejected_before_reading(export_root):
    result = invoke(export_root, source="/etc/passwd")
    assert result.returncode != 0
    assert not list((export_root / ".cloud-test").iterdir())
