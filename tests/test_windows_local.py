"""检查启动工具的本地边界、依赖更新和停止范围；不接触 cece 的配置或数据库。"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from scripts import windows_local as local


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(local, "ROOT", tmp_path)
    monkeypatch.setattr(local, "RUNTIME", tmp_path / ".local-run")
    monkeypatch.setattr(local, "PYTHON", tmp_path / ".venv/Scripts/python.exe")
    local.RUNTIME.mkdir()
    return tmp_path


def test_ports_are_checked_without_stopping_the_owner():
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        with pytest.raises(local.LocalError, match="端口被占用"):
            local.assert_port_free(port)
        assert occupied.getsockname()[1] == port


@pytest.mark.parametrize("host", ["tcp://192.0.2.1:2376", "ssh://server", "unix:///tmp/docker.sock"])
def test_remote_docker_is_rejected_before_database_operations(monkeypatch, host):
    monkeypatch.setenv("DOCKER_HOST", host)
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    calls = []
    monkeypatch.setattr(local, "command", lambda args, *_a, **_kw: calls.append(args) or "v2")
    with pytest.raises(local.LocalError, match="本机连接"):
        local.check_docker_location("docker")
    assert calls == [["docker", "compose", "version"]]


def test_docker_context_takes_precedence_over_host(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "ssh://ignored")
    monkeypatch.setenv("DOCKER_CONTEXT", "desktop-linux")
    monkeypatch.setattr(local, "command", lambda args, *_a, **_kw: json.dumps("npipe:////./pipe/dockerDesktopLinuxEngine") if "inspect" in args else "v2")
    local.check_docker_location("docker")


def test_foreign_clone_database_is_not_modified(workspace, monkeypatch):
    calls = []

    def invoke(args, *_a, **_kw):
        calls.append(args)
        return "abc" if "ps" in args else '"abc"|true|"/another/clone"'

    monkeypatch.setattr(local, "command", invoke)
    with pytest.raises(local.LocalError, match="另一个目录"):
        local.database_container("docker")
    assert not any("stop" in args or "start" in args for args in calls)


def test_running_manual_database_is_reused_but_not_marked_owned(workspace, monkeypatch):
    monkeypatch.setattr(local, "database_container", lambda _: {"id": "manual", "running": True})
    monkeypatch.setattr(local, "command", lambda *_a, **_kw: pytest.fail("不能启动或停止原本已运行的库"))
    local.ensure_database("docker")
    assert not (local.RUNTIME / "database.json").exists()
    local.stop_database("docker")


def test_database_start_failure_keeps_exact_ownership_for_later_stop(workspace, monkeypatch):
    monkeypatch.setattr(local, "database_container", lambda _: {"id": "owned", "running": False})
    monkeypatch.setattr(local, "assert_port_free", lambda _: None)
    monkeypatch.setattr(local, "command", lambda *_a, **_kw: (_ for _ in ()).throw(local.LocalError("超时")))
    with pytest.raises(local.LocalError, match="超时"):
        local.ensure_database("docker")
    assert local.read_json(local.RUNTIME / "database.json") == {"id": "owned"}


def test_new_database_creation_failure_still_records_created_container(workspace, monkeypatch):
    states = iter([None, {"id": "just-created", "running": True}])
    monkeypatch.setattr(local, "database_container", lambda _: next(states))
    monkeypatch.setattr(local, "assert_port_free", lambda _: None)
    calls = []

    def fail(args, *_a, **_kw):
        calls.append(args)
        raise local.LocalError("创建未完成")

    monkeypatch.setattr(local, "command", fail)
    with pytest.raises(local.LocalError):
        local.ensure_database("docker")
    assert local.read_json(local.RUNTIME / "database.json") == {"id": "just-created"}
    assert "--no-recreate" in calls[0] and "--env-file" in calls[0]


@pytest.mark.parametrize("current_id, stopped", [("owned", True), ("replacement", False), (None, False)])
def test_stop_only_uses_the_exact_recorded_container(workspace, monkeypatch, current_id, stopped):
    local.write_json(local.RUNTIME / "database.json", {"id": "owned"})
    monkeypatch.setattr(local, "database_container", lambda _: {"id": current_id} if current_id else None)
    calls = []
    monkeypatch.setattr(local, "command", lambda args, *_a, **_kw: calls.append(args) or "")
    local.stop_database("docker")
    assert bool(calls) is stopped
    if stopped:
        assert calls == [["docker", "stop", "--time", "10", "owned"]]
    assert not (local.RUNTIME / "database.json").exists()


def test_failed_stop_keeps_ownership_to_retry(workspace, monkeypatch):
    local.write_json(local.RUNTIME / "database.json", {"id": "owned"})
    monkeypatch.setattr(local, "database_container", lambda _: {"id": "owned"})
    monkeypatch.setattr(local, "command", lambda *_a, **_kw: (_ for _ in ()).throw(local.LocalError("停止失败")))
    with pytest.raises(local.LocalError):
        local.stop_database("docker")
    assert local.read_json(local.RUNTIME / "database.json") == {"id": "owned"}


def test_unchanged_dependencies_skip_install_but_changed_or_missing_ones_update(workspace, monkeypatch):
    local.PYTHON.parent.mkdir(parents=True)
    local.PYTHON.touch()
    for path in ("requirements.in", "requirements.txt", "requirements-dev.in", "requirements-dev.txt", "frontend/admin/package.json", "frontend/admin/package-lock.json", "frontend/user/package.json", "frontend/user/package-lock.json"):
        target = workspace / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("first", encoding="utf-8")
    calls, missing = [], [False]

    def invoke(args, *_a, **kw):
        args = [str(part) for part in args]
        calls.append(args)
        if "--version" in args:
            return "v24.19.0"
        if any("sys.version_info.major" in arg for arg in args):
            return "3.12"
        if missing[0] and "ls" in args:
            missing[0] = False
            return None
        return ""

    monkeypatch.setattr(local, "command", invoke)
    installs = lambda: [args for args in calls if "install" in args or "ci" in args]
    local.dependencies("node", "npm-cli.js")
    assert len(installs()) == 3
    calls.clear()
    local.dependencies("node", "npm-cli.js")
    assert installs() == []
    (workspace / "frontend/admin/package-lock.json").write_text("second", encoding="utf-8")
    local.dependencies("node", "npm-cli.js")
    assert len(installs()) == 1 and "ci" in installs()[0]
    calls.clear()
    missing[0] = True
    local.dependencies("node", "npm-cli.js")
    assert len(installs()) == 1 and "ci" in installs()[0]


def test_dependency_install_failure_does_not_record_success(workspace, monkeypatch):
    local.PYTHON.parent.mkdir(parents=True)
    local.PYTHON.touch()
    for path in ("requirements.in", "requirements.txt", "requirements-dev.in", "requirements-dev.txt"):
        (workspace / path).write_text("first", encoding="utf-8")

    def invoke(args, *_a, **_kw):
        if "install" in args:
            raise local.LocalError("安装失败")
        return "3.12" if "-c" in args else "v24.19.0"

    monkeypatch.setattr(local, "command", invoke)
    with pytest.raises(local.LocalError):
        local.dependencies("node", "npm")
    assert not (local.RUNTIME / "dependencies.json").exists()


def test_stale_stop_request_does_not_stop_a_new_run(workspace):
    local.write_json(local.RUNTIME / "stop.json", {"run_id": "old"})
    assert not local.stop_requested("new")
    assert local.stop_requested("old")


@contextmanager
def unavailable_lock(_name):
    yield False


def test_repeated_start_does_not_open_browser_or_start_more_services(workspace, monkeypatch):
    version = {"branch": "feature", "revision": "abc"}
    local.write_json(local.RUNTIME / "services.json", {**version, "phase": "ready"})
    monkeypatch.setattr(local, "file_lock", unavailable_lock)
    monkeypatch.setattr(local, "version_info", lambda: version)
    monkeypatch.setattr(local, "ready", lambda: True)
    monkeypatch.setattr(local, "tools", lambda: pytest.fail("重复启动不应安装依赖或启动服务"))
    opened = []
    monkeypatch.setattr(local.webbrowser, "open", opened.append)
    assert local.start() == local.ALREADY_RUNNING
    assert opened == []
    local.write_json(local.RUNTIME / "services.json", {**version, "revision": "old", "phase": "ready"})
    with pytest.raises(local.LocalError, match="版本已变化"):
        local.start()
    assert opened == []


@pytest.mark.parametrize("phase", [None, "preparing", "starting"])
def test_repeated_start_during_preparation_exits_normally(workspace, monkeypatch, phase):
    version = {"branch": "feature", "revision": "abc"}
    if phase:
        local.write_json(local.RUNTIME / "services.json", {**version, "phase": phase})
    monkeypatch.setattr(local, "file_lock", unavailable_lock)
    monkeypatch.setattr(local, "version_info", lambda: version)
    monkeypatch.setattr(local, "ready", lambda: pytest.fail("准备中的重复入口不应查询网页或启动服务"))
    assert local.start() == local.ALREADY_RUNNING


def test_real_service_failure_still_keeps_an_explanation(workspace, monkeypatch):
    version = {"branch": "feature", "revision": "abc"}
    local.write_json(local.RUNTIME / "services.json", {**version, "phase": "ready"})
    monkeypatch.setattr(local, "file_lock", unavailable_lock)
    monkeypatch.setattr(local, "version_info", lambda: version)
    monkeypatch.setattr(local, "ready", lambda: False)
    with pytest.raises(local.LocalError, match="运行检查未通过"):
        local.start()


def test_busy_lock_never_reads_the_locked_byte(workspace, monkeypatch):
    # 模拟Windows强制字节锁：已有持锁者时，读字节会先于尝试加锁而失败。
    held = [False]
    original_open = Path.open

    class GuardedFile:
        def __init__(self, handle):
            self.handle = handle

        def __getattr__(self, name):
            return getattr(self.handle, name)

        def read(self, *args):
            if held[0]:
                raise PermissionError("模拟读取另一进程锁住的字节")
            return self.handle.read(*args)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

    def guarded_open(path, *args, **kwargs):
        handle = original_open(path, *args, **kwargs)
        return GuardedFile(handle) if path.name == "services.lock" else handle

    def locking(_fd, mode, _length):
        if mode == 0:
            held[0] = False
        elif held[0]:
            raise PermissionError("模拟字节锁已被占用")
        else:
            held[0] = True

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(locking=locking, LK_NBLCK=1, LK_UNLCK=0))
    with local.file_lock("services.lock") as acquired:
        assert acquired
        assert local.running()
        with local.file_lock("services.lock") as second:
            assert second is False
    assert not local.running()


def test_successful_stop_explains_that_data_is_retained(workspace, monkeypatch, capsys):
    @contextmanager
    def available(_name):
        yield True

    monkeypatch.setattr(local, "file_lock", available)
    monkeypatch.setattr(local, "running", lambda: False)
    local.stop()
    assert "停止完成；配置、管理员账号和测试数据保留。" in capsys.readouterr().out


@pytest.mark.auth_database
@pytest.mark.parametrize("auth_database", ["restartable"], indirect=True)
def test_database_stop_and_restart_keep_account_session_and_test_records(workspace, monkeypatch, auth_database, auth_app, admin_account):
    import pymysql
    from tests.test_admin_auth import login, query

    docker, container = auth_database["TEST_DOCKER_COMMAND"], auth_database["TEST_CONTAINER"]
    environment = dict(os.environ)
    if os.name != "nt" and Path("/var/run/docker.sock").exists():
        for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
            environment.pop(name, None)
    config = workspace / ".env"
    config.write_text("LOCAL_TEST_MARKER=preserved\n", encoding="utf-8")
    client = auth_app.test_client()
    assert login(client, auth_app, admin_account).status_code == 200
    uid = "04:A2:7F:1B:5E:80:FE"
    query(auth_app, "INSERT INTO chip(chip_uid,project_id,batch_no) VALUES (%s,1,'临时停止验证')", (uid,))
    tables = ("admin_user", "admin_session", "chip")
    before = [query(auth_app, f"SELECT * FROM {table} ORDER BY id") for table in tables]
    local.write_json(local.RUNTIME / "database.json", {"id": container})
    monkeypatch.setattr(local, "database_container", lambda _: {"id": container})

    def invoke(arguments, _description, timeout=30, **_kwargs):
        result = subprocess.run([*docker, *arguments[1:]], env=environment, capture_output=True, text=True, timeout=timeout)
        assert result.returncode == 0, "专属临时数据库停止或启动失败"
        return result.stdout.strip()

    monkeypatch.setattr(local, "command", invoke)
    try:
        local.stop_database("docker")
        assert not (local.RUNTIME / "database.json").exists()
    finally:
        invoke(["docker", "start", container], "恢复专属临时库")
        # 临时容器使用随机测试端口，重启后Docker可能重新分配；真实工具端口固定为33306。
        port = int(invoke(["docker", "port", container, "3306/tcp"], "读取临时测试端口").rsplit(":", 1)[1])
        auth_database["DB_PORT"] = auth_app.config["DB_PORT"] = port
        deadline = time.monotonic() + 30
        while True:
            try:
                after = [query(auth_app, f"SELECT * FROM {table} ORDER BY id") for table in tables]
                break
            except pymysql.MySQLError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)
    try:
        assert after == before
        assert client.get("/api/admin/auth/session").status_code == 200
        assert config.read_text(encoding="utf-8") == "LOCAL_TEST_MARKER=preserved\n"
    finally:
        query(auth_app, "DELETE FROM chip WHERE chip_uid=%s", (uid,))


@pytest.mark.parametrize("key,value", [("DB_HOST", "db.example.com"), ("APP_ENV", "production"), ("ADMIN_ORIGIN", "http://127.0.0.1:5174"), ("DB_PORT", "3306")])
def test_nonlocal_config_and_inherited_overrides_are_rejected_before_app_load(workspace, monkeypatch, key, value):
    configuration = {"APP_ENV": "development", "DB_HOST": "127.0.0.1", "DB_PORT": "33306", "DB_USER": "bumbum_dev", "DB_NAME": "bumbum_digital", "ADMIN_ORIGIN": local.URL, "VITE_API_BASE_URL": "/api"}
    for name in configuration:
        monkeypatch.delenv(name, raising=False)
    (workspace / ".env").write_text("\n".join(f"{name}={setting}" for name, setting in configuration.items()), encoding="utf-8")
    monkeypatch.setenv(key, value)
    with pytest.raises(local.LocalError, match=key):
        local.validate_config()


def test_command_failure_and_timeout_do_not_print_raw_output(monkeypatch, capsys):
    monkeypatch.setattr(local.subprocess, "run", lambda *_a, **_kw: subprocess.CompletedProcess([], 1, stdout="secret-value", stderr="password"))
    with pytest.raises(local.LocalError) as failure:
        local.command(["tool"], "测试阶段")
    assert "secret-value" not in str(failure.value)
    assert "password" not in capsys.readouterr().out
    monkeypatch.setattr(local.subprocess, "run", lambda *_a, **_kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("tool", 1)))
    with pytest.raises(local.LocalError, match="超时"):
        local.command(["tool"], "测试阶段", 1)


@pytest.mark.parametrize("successful", [True, False])
def test_service_lifecycle_closes_only_owned_job_and_cleans_state(workspace, monkeypatch, successful):
    events = []

    class Job:
        def launch(self, args, root, log):
            events.append(("launch", args))

        def healthy(self):
            return False

        def close(self):
            events.append(("close",))

    monkeypatch.setitem(sys.modules, "windows_process", SimpleNamespace(WindowsJob=Job))
    monkeypatch.setattr(local, "ready", lambda: successful)
    monkeypatch.setattr(local, "stop_requested", lambda _: successful)
    monkeypatch.setattr(local.webbrowser, "open", lambda url: events.append(("open", url)))
    if successful:
        local.serve("node", {"branch": "test", "revision": "abc"})
        assert ("open", local.URL) in events
    else:
        with pytest.raises(local.LocalError, match="未能启动"):
            local.serve("node", {"branch": "test", "revision": "abc"})
        assert not any(event[0] == "open" for event in events)
    assert sum(event[0] == "launch" for event in events) == 3
    assert events[-1] == ("close",)
    assert not (local.RUNTIME / "services.json").exists()
    assert not (local.RUNTIME / "stop.json").exists()


def test_ctrl_c_after_start_closes_owned_services_as_normal_stop(workspace, monkeypatch, capsys):
    events = []

    class Job:
        def launch(self, *_args):
            events.append("launch")

        def close(self):
            events.append("closed")

    def interrupted(_run_id):
        raise KeyboardInterrupt

    monkeypatch.setitem(sys.modules, "windows_process", SimpleNamespace(WindowsJob=Job))
    monkeypatch.setattr(local, "ready", lambda: True)
    monkeypatch.setattr(local, "stop_requested", interrupted)
    monkeypatch.setattr(local.webbrowser, "open", lambda _: None)
    assert local.serve("node", {"branch": "test", "revision": "abc"}) is None
    assert events == ["launch", "launch", "launch", "closed"]
    assert not (local.RUNTIME / "services.json").exists()
    assert not (local.RUNTIME / "stop.json").exists()
    output = capsys.readouterr().out
    assert "已收到手动停止指令" in output and "前后端已停止" in output
    assert "操作已取消" not in output and "未完成：" not in output


def test_native_tool_refuses_non_windows_without_changes(workspace, monkeypatch):
    if os.name == "nt":
        pytest.skip("此项验证其他系统拒绝误运行")
    monkeypatch.setattr(sys, "argv", ["windows_local.py", "start"])
    assert local.main() == 1
    assert list(local.RUNTIME.iterdir()) == []


@pytest.mark.skipif(os.name != "nt", reason="需要真实 Windows 文件锁")
def test_windows_file_lock_releases_after_process_exit(workspace):
    root = Path(__file__).resolve().parents[1]
    source = (
        "from scripts import windows_local as m; from pathlib import Path; import sys,time; "
        f"m.RUNTIME=Path({str(local.RUNTIME)!r}); "
        "lock=m.file_lock('services.lock'); print(lock.__enter__(),flush=True); time.sleep(30)"
    )
    child = subprocess.Popen([sys.executable, "-X", "utf8", "-c", source], cwd=root, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "True"
        assert local.running()
    finally:
        child.terminate()
        child.wait(timeout=10)
    assert not local.running()


@pytest.mark.skipif(os.name != "nt", reason="需要真实 Windows 作业对象")
def test_windows_job_closes_only_its_own_child_tree(tmp_path):
    import ctypes
    from ctypes import wintypes as w
    from scripts.windows_process import WindowsJob

    folder = tmp_path / "中文 空格 & 括号(验证)"
    folder.mkdir()
    pid_file = folder / "grandchild.pid"
    source = "import subprocess,sys,time; from pathlib import Path; " + f"p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); Path({str(pid_file)!r}).write_text(str(p.pid)); time.sleep(60)"
    outsider = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    job = WindowsJob()
    api = job.api
    api.OpenProcess.argtypes, api.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    api.WaitForSingleObject.argtypes, api.WaitForSingleObject.restype = [w.HANDLE, w.DWORD], w.DWORD
    grandchild = None
    try:
        with (folder / "service.log").open("wb") as log:
            job.launch([sys.executable, "-c", source], folder, log)
            deadline = time.monotonic() + 10
            while not pid_file.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            assert pid_file.exists() and job.healthy()
            grandchild = api.OpenProcess(0x100000, False, int(pid_file.read_text()))
            assert grandchild
            job.close()
            assert api.WaitForSingleObject(grandchild, 5000) == 0
            assert outsider.poll() is None
    finally:
        job.close()
        if grandchild:
            api.CloseHandle(grandchild)
        outsider.terminate()
        outsider.wait(timeout=10)
