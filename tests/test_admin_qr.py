"""只用合成资料验证离线二维码、手动添加和临时文件清理。"""

import stat
import os
import xml.etree.ElementTree as ET

import click
import pyotp
import pytest

from core import admin_qr


@pytest.fixture
def setup_uri(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":test-only")
    monkeypatch.setattr(admin_qr.webbrowser, "open", lambda *_args, **_kwargs: False)
    return pyotp.TOTP(pyotp.random_base32()).provisioning_uri(name="test-admin", issuer_name="BUMBUM Test")


def test_setup_page_is_offline_and_files_are_cleaned(setup_uri, capsys):
    otp = pyotp.parse_uri(setup_uri)
    with admin_qr.show_qr(setup_uri) as path:
        folder = path.parent
        text = path.read_text(encoding="utf-8")
        assert otp.secret in text and "手动添加账号" in text
        assert "default-src 'none'" in text
        assert "<script" not in text and "<img" not in text
        assert "width: min(440px, 100%)" in text
        start, end = text.index("<svg"), text.index("</svg>") + len("</svg>")
        picture = ET.fromstring(text[start:end])
        width, height = picture.attrib["width"], picture.attrib["height"]
        assert width == height and "viewBox" in picture.attrib
        assert picture.find("{http://www.w3.org/2000/svg}rect").attrib["fill"] == "white"
        if os.name != "nt":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            assert stat.S_IMODE(folder.stat().st_mode) == 0o700
        output = capsys.readouterr().out
        assert otp.secret not in output and setup_uri not in output
        assert "未能自动打开" in output
    assert not path.exists() and not folder.exists()


def test_cancelling_setup_cleans_secret_file(setup_uri):
    with pytest.raises(click.Abort):
        with admin_qr.show_qr(setup_uri) as path:
            assert path.exists()
            raise click.Abort()
    assert not path.exists()


def test_browser_launch_failure_keeps_manual_file_access(setup_uri, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise admin_qr.webbrowser.Error("测试中的浏览器启动失败")
    monkeypatch.setattr(admin_qr.webbrowser, "open", unavailable)
    with admin_qr.show_qr(setup_uri) as path:
        assert path.is_file()
    assert not path.exists()


def test_account_text_cannot_add_scripts():
    uri = pyotp.TOTP(pyotp.random_base32()).provisioning_uri(name="<script>test-only</script>", issuer_name="Test & Test")
    text = admin_qr.setup_page(uri)
    assert "<script>" not in text
    assert "&lt;script&gt;test-only&lt;/script&gt;" in text
    assert "Test &amp; Test" in text


def test_file_failure_does_not_echo_secret(setup_uri, monkeypatch):
    original_open = os.open
    def denied(path, *_args, **_kwargs):
        if str(path).endswith("authenticator.html"):
            raise PermissionError("测试中的写入失败")
        return original_open(path, *_args, **_kwargs)
    monkeypatch.setattr(admin_qr.os, "open", denied)
    with pytest.raises(click.ClickException) as caught:
        with admin_qr.show_qr(setup_uri):
            pytest.fail("文件写入失败时不能继续设置")
    assert pyotp.parse_uri(setup_uri).secret not in str(caught.value)
