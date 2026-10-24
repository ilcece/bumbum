"""只启动专属日志占位进程，验证监听超时和Ctrl+C会关闭标志及查看进程。"""

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest

from scripts.scan_capture import listen

pytestmark = pytest.mark.skipif(os.name == "nt", reason="香港监听工具仅用于Linux")
ROOT = Path(__file__).resolve().parents[1]


def test_timeout_disables_capture_and_returns_success(tmp_path):
    assert listen(tmp_path, [sys.executable, "-c", "import time; time.sleep(60)"], seconds=0.1) == 0
    assert not (tmp_path / ".cloud-test/diagnostics/until").exists()


def test_interrupt_cleans_up_only_the_owned_log_process(tmp_path):
    (tmp_path / "scripts").mkdir()
    script = tmp_path / "scripts/scan_capture.py"
    shutil.copyfile(ROOT / "scripts/scan_capture.py", script)
    ready = tmp_path / "ready"
    code = "from pathlib import Path; import time; Path(" + repr(str(ready)) + ").touch(); time.sleep(60)"
    process = subprocess.Popen([sys.executable, str(script), "listen", sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        for _ in range(100):
            if ready.exists():
                break
            time.sleep(0.02)
        assert ready.exists()
        process.send_signal(signal.SIGINT)
        output, error = process.communicate(timeout=6)
        assert process.returncode == 0 and "结构监听已关闭" in output
        assert not (tmp_path / ".cloud-test/diagnostics/until").exists()
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            process.wait(timeout=6)
