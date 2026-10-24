"""开启或关闭五分钟的结构观察；控制文件不包含秘密，不改.env或数据库。"""

import argparse
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def set_capture(root, enabled):
    folder = root / ".cloud-test/diagnostics"
    target = folder / "until"
    if folder.is_symlink() or target.is_symlink():
        raise ValueError("监听控制路径不能是软链接。")
    folder.mkdir(mode=0o755, parents=True, exist_ok=True)
    if enabled:
        descriptor = os.open(target, os.O_CREAT | os.O_WRONLY | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o644)
        with os.fdopen(descriptor, "w", encoding="ascii") as stream:
            stream.write(str(int(time.time()) + 300))
        target.chmod(0o644)
        print("结构监听已开启：最多5分钟，每个工作进程最多12条；请在手机读取并保存一次标签，Ctrl+C可提前结束。")
    else:
        target.unlink(missing_ok=True)
        print("结构监听已关闭；服务继续运行。")


def listen(root, command, seconds=300):
    """只管理新建的日志查看进程组；超时或Ctrl+C后关闭采集，不停止容器。"""
    process = None
    set_capture(root, True)
    try:
        process = subprocess.Popen(command, start_new_session=True)
        return process.wait(timeout=seconds)
    except (KeyboardInterrupt, subprocess.TimeoutExpired):
        return 0
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            except ProcessLookupError:
                pass
        set_capture(root, False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "listen"])
    parser.add_argument("command", nargs=argparse.REMAINDER, help="监听时运行的日志命令，不包含凭证值")
    args = parser.parse_args()
    try:
        if args.action == "listen":
            if not args.command:
                parser.error("缺少日志查看命令")
            raise SystemExit(listen(ROOT, args.command))
        set_capture(ROOT, args.action == "start")
    except (OSError, ValueError):
        raise SystemExit("监听控制文件无法更新，请检查目录权限及路径；未修改配置或数据。") from None
