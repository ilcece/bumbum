"""浏览器检查拒绝已有服务及缺失隔离开关，不需要启动浏览器。"""

from pathlib import Path
import socket
import subprocess
import sys

import pytest

from tests.browser_support import assert_ports_available, frontend_ready


def test_colored_startup_output():
    assert frontend_ready('Local: \x1b[36mhttp://127.0.0.1:\x1b[1m5174\x1b[22m/\x1b[39m')
    assert not frontend_ready('Local: http://127.0.0.1:5175/')


def test_refuses_an_existing_listener():
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0)); server.listen(1)
        with pytest.raises(pytest.fail.Exception, match='未接管现有服务'):
            assert_ports_available((server.getsockname()[1],))


def test_browser_flag_requires_isolated_database():
    result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pytest', 'tests/test_admin_browser.py', '--browser', '--collect-only', '-q'],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, encoding='utf-8')
    assert result.returncode == 4
    assert '必须同时提供--auth-db' in result.stderr
