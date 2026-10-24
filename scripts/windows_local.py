"""Windows 本地准备、启动和停止入口；不自动同步 Git 或修改业务数据。"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import uuid
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".local-run"
PYTHON = ROOT / ".venv/Scripts/python.exe"
URL = "http://localhost:5174"
OPENER = build_opener(ProxyHandler({}))
# 仅供双击入口识别“无需重复启动”，最终对用户返回成功，不保留多余窗口。
ALREADY_RUNNING = 10


class LocalError(Exception):
    """可以直接向 cece 展示的失败说明，不包含配置值。"""


def command(arguments, description, timeout=30, *, required=True, public_error=False):
    """隐藏可能带连接信息的原始输出，只显示操作名称和明确的失败阶段。"""
    try:
        result = subprocess.run([str(part) for part in arguments], cwd=ROOT,
                                capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        if required:
            raise LocalError(f"{description}未完成或等待超时；请按本地运行说明排查后重试。") from None
        return None
    if result.returncode:
        if required:
            if public_error and result.stdout.startswith("未完成："):
                raise LocalError(result.stdout.strip().removeprefix("未完成："))
            raise LocalError(f"{description}失败（退出码 {result.returncode}）；请按本地运行说明排查。")
        return None
    return result.stdout.strip()


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


@contextmanager
def file_lock(name):
    """系统文件锁随进程退出释放，旧记录不会被当作仍在运行的依据。"""
    import msvcrt
    RUNTIME.mkdir(exist_ok=True)
    with (RUNTIME / name).open("a+b") as handle:
        handle.seek(0)
        # Windows会禁止读取被另一进程锁住的字节；判断大小不读取锁区。
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            yield False
        else:
            try:
                yield True
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def running():
    with file_lock("services.lock") as available:
        return not available


def version_info():
    git = shutil.which("git")
    if not git:
        # GitHub Desktop 自带 Git；常规安装后不一定会把它加入 PATH。
        bundled = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "GitHubDesktop").glob("app-*/resources/app/git/cmd/git.exe"))
        git = str(bundled[-1]) if bundled else None
    if not git:
        raise LocalError("未找到 Git。请先用 GitHub Desktop 克隆仓库；安装 Git for Windows 后重开窗口。")
    branch = command([git, "branch", "--show-current"], "读取分支") or "未命名版本"
    revision = command([git, "rev-parse", "--short", "HEAD"], "读取版本")
    dirty = command([git, "status", "--porcelain"], "检查本地修改")
    print(f"当前分支：{branch}；版本：{revision}" + ("；有本地修改，请留意验收版本。" if dirty else ""), flush=True)
    return {"branch": branch, "revision": revision}


def tools():
    if sys.version_info[:2] != (3, 12):
        raise LocalError("需要 Python 3.12。请从 https://www.python.org/downloads/ 安装后重试；不要删除已有环境。")
    node, docker = shutil.which("node"), shutil.which("docker")
    if not node:
        raise LocalError("未找到 Node.js，请从 https://nodejs.org/ 安装 24 LTS，然后重开窗口。")
    node_version = command([node, "--version"], "检查 Node.js")
    if not node_version.startswith("v24."):
        raise LocalError("需要 Node.js 24 LTS。请安装对应版本后重开窗口。")
    npm = Path(node).parent / "node_modules/npm/bin/npm-cli.js"
    if not npm.is_file():
        raise LocalError("找不到 Node.js 配套的 npm。请修复 Node.js 24 官方安装，然后重开窗口。")
    if not docker:
        raise LocalError("未找到 Docker，请从 https://www.docker.com/products/docker-desktop/ 安装 Docker Desktop。")
    check_docker_location(docker)
    return node, npm, docker


def check_docker_location(docker):
    command([docker, "compose", "version"], "检查 Docker Compose")
    # 运行前先确认 Docker 指向本机，不能把已有远端环境当测试库。
    host = os.environ.get("DOCKER_HOST") if not os.environ.get("DOCKER_CONTEXT") else None
    if not host:
        endpoint = command([docker, "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"], "检查 Docker 连接位置")
        try:
            host = json.loads(endpoint)
        except ValueError:
            raise LocalError("无法确认 Docker 连接位置，未启动数据库。") from None
    if not isinstance(host, str) or not host.startswith("npipe://"):
        raise LocalError("Docker 未指向 Windows 本机连接。请在 Docker Desktop 选择本机 Linux 容器环境。")


def docker_tool():
    docker = shutil.which("docker")
    if not docker:
        raise LocalError("找不到 Docker；数据库未删除，请修复 Docker Desktop 后重试。")
    check_docker_location(docker)
    return docker


def dependencies(node, npm):
    """用锁定文件指纹和实际依赖检查决定是否安装；失败不更新完成标记。"""
    if not PYTHON.is_file():
        if (ROOT / ".venv").exists():
            raise LocalError("已有 .venv 无法在当前目录使用，请保留它并让 AI 排查，不复制或覆盖。")
        command([sys.executable, "-X", "utf8", "-m", "venv", ROOT / ".venv"], "建立 Python 环境", 120)
    probe = command([PYTHON, "-X", "utf8", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], "检查项目 Python")
    if probe != "3.12":
        raise LocalError("已有 .venv 不是 Python 3.12，未重建；请让 AI 协助处理。")
    state = read_json(RUNTIME / "dependencies.json") or {}
    identity = str(ROOT) + str(PYTHON)
    for name, files, install, verify in (
        ("python", ["requirements.in", "requirements.txt", "requirements-dev.in", "requirements-dev.txt"],
         [PYTHON, "-X", "utf8", "-m", "pip", "install", "--disable-pip-version-check", "--retries", "1", "--timeout", "30", "-r", "requirements-dev.txt"],
         [PYTHON, "-X", "utf8", "-c", "from importlib.metadata import version; from packaging.requirements import Requirement; from pathlib import Path; import sys; r=[Requirement(x) for x in Path('requirements-dev.txt').read_text(encoding='utf-8').splitlines() if x.strip() and not x.startswith('#')]; sys.exit(any(version(x.name) not in x.specifier for x in r if not x.marker or x.marker.evaluate()))"]),
        ("frontend", ["frontend/admin/package.json", "frontend/admin/package-lock.json"],
         [node, npm, "--prefix", "frontend/admin", "ci", "--no-audit", "--no-fund"],
         [node, npm, "--prefix", "frontend/admin", "ls", "--depth=0"]),
    ):
        digest = hashlib.sha256(identity.encode())
        digest.update((command([node, "--version"], "检查 Node.js") if name == "frontend" else sys.version).encode())
        for file in files:
            digest.update((ROOT / file).read_bytes())
        fingerprint = digest.hexdigest()
        healthy = command(verify, "检查已安装依赖", 30, required=False) is not None
        if name == "python" and healthy:
            healthy = command([PYTHON, "-X", "utf8", "-m", "pip", "check"], "检查 Python 依赖兼容性", required=False) is not None
        if state.get(name) != fingerprint or not healthy:
            print("正在安装或更新" + (" Python 依赖……" if name == "python" else "网页依赖……"), flush=True)
            command(install, "安装 Python 依赖" if name == "python" else "安装网页依赖", 900)
            command(verify, "复查依赖")
            state[name] = fingerprint
            write_json(RUNTIME / "dependencies.json", state)
        else:
            print(("Python" if name == "python" else "网页") + "依赖未变化，已跳过安装。", flush=True)


def check_config():
    """在项目解释器中按后端实际优先级检查；只返回变量名，不输出秘密。"""
    command([PYTHON, "-X", "utf8", __file__, "_check-config"], "检查本机配置", public_error=True)


def validate_config():
    sys.path.insert(0, str(ROOT))
    from dotenv import dotenv_values
    if not (ROOT / ".env").is_file():
        raise LocalError("未找到 .env，请先双击首次准备。")
    values = dotenv_values(ROOT / ".env")
    values.update({key: os.environ[key] for key in values if key in os.environ})
    expected = {"APP_ENV": "development", "DB_HOST": {"127.0.0.1", "localhost"}, "DB_PORT": "33306",
                "DB_USER": "bumbum_dev", "DB_NAME": "bumbum_digital", "ADMIN_ORIGIN": URL,
                "VITE_API_BASE_URL": "/api"}
    for key, target in expected.items():
        actual = values.get(key, os.environ.get(key))
        matches = actual in target if isinstance(target, set) else actual == target
        if not matches:
            raise LocalError(f"{key} 不符合本机工具约定；保留现有值，让 AI 按本地说明排查。")
    for key in ("DB_PASSWORD", "DEV_DB_ROOT_PASSWORD"):
        if not values.get(key):
            raise LocalError(f"缺少 {key}；已有数据库请保留原配置，不重新生成密码。")
    from app import create_app
    from core.auth_settings import auth_settings
    with create_app().app_context():
        auth_settings()


def ensure_docker(docker):
    kind = command([docker, "info", "--format", "{{.OSType}}"], "检查 Docker", 8, required=False)
    if kind is None:
        locations = [Path(os.environ.get(key, "")) / relative for key, relative in (
            ("ProgramFiles", "Docker/Docker/Docker Desktop.exe"),
            ("LOCALAPPDATA", "Programs/DockerDesktop/Docker Desktop.exe"),
        )]
        desktop = next((path for path in locations if path.is_file()), None)
        if not desktop:
            raise LocalError("Docker 未运行，未找到默认安装位置。请手动打开 Docker Desktop 后重试。")
        subprocess.Popen([str(desktop)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("正在等待 Docker Desktop，最多120秒；首次安装的系统提示请本人完成。", flush=True)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            kind = command([docker, "info", "--format", "{{.OSType}}"], "等待 Docker", 5, required=False)
            if kind:
                break
            time.sleep(2)
    if kind != "linux":
        raise LocalError("Docker 尚未就绪或未使用 Linux 容器。请检查 Docker Desktop 后重试。")


def database_container(docker):
    """只取必要元数据，避免 docker inspect 输出数据库密码。"""
    ids = command([docker, "ps", "-a", "--filter", "label=com.docker.compose.project=bumbum-local",
                   "--filter", "label=com.docker.compose.service=db", "--format", "{{.ID}}"], "查找本项目数据库").splitlines()
    if len(ids) > 1:
        raise LocalError("发现多个同名测试数据库容器，请让 AI 排查，未自动停止或删除。")
    if not ids:
        return None
    raw = command([docker, "inspect", "--format",
                   '{{json .Id}}|{{json .State.Running}}|{{json (index .Config.Labels "com.docker.compose.project.working_dir")}}', ids[0]], "核对数据库所属目录")
    container, active, folder = (json.loads(part) for part in raw.split("|"))
    if not folder or os.path.normcase(os.path.abspath(folder)) != os.path.normcase(str(ROOT)):
        raise LocalError("已有 bumbum-local 数据库属于另一个目录。请使用原克隆目录，未修改该数据库。")
    return {"id": container, "running": active}


def ensure_database(docker):
    before = database_container(docker)
    if before and before["running"]:
        owned = read_json(RUNTIME / "database.json") or {}
        print("复用本工具之前启动的数据库。" if owned.get("id") == before["id"] else "复用已运行的本项目数据库，停止工具不会关闭它。", flush=True)
        return
    assert_port_free(33306)
    # 只启动已有容器，避免 Compose 因文件变化自动重建；空库才创建。
    if before:
        write_json(RUNTIME / "database.json", {"id": before["id"]})
        command([docker, "start", before["id"]], "启动已有测试数据库", 30)
    else:
        try:
            command([docker, "compose", "--project-directory", ROOT, "--env-file", ROOT / ".env",
                     "-f", ROOT / "compose.yaml", "--project-name", "bumbum-local",
                     "up", "-d", "--no-recreate", "db"], "下载镜像并创建本机测试数据库", 600)
        finally:
            created = database_container(docker)
            if created:
                write_json(RUNTIME / "database.json", {"id": created["id"]})
    after = database_container(docker)
    if not after:
        raise LocalError("数据库容器未创建成功，请检查 Docker Desktop。")
    write_json(RUNTIME / "database.json", {"id": after["id"]})
    print("等待测试数据库就绪，最多120秒；已有数据不会重新建表。", flush=True)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        status = command([docker, "inspect", "--format", "{{.State.Health.Status}}", after["id"]], "检查数据库状态", required=False)
        if status == "healthy":
            return
        if status == "unhealthy":
            break
        time.sleep(2)
    raise LocalError("测试数据库未在120秒内就绪，数据已保留；请按本地运行说明排查，或双击停止项目。")


def stop_database(docker):
    owned = read_json(RUNTIME / "database.json")
    if not owned:
        print("没有本工具启动的数据库需要停止。", flush=True)
        return
    current = database_container(docker)
    if current and current["id"] == owned.get("id"):
        command([docker, "stop", "--time", "10", current["id"]], "停止本工具启动的测试数据库", 30)
        print("测试数据库已停止，数据已保留。", flush=True)
    else:
        print("原数据库容器已变化，未操作其他容器。", flush=True)
    (RUNTIME / "database.json").unlink(missing_ok=True)


def assert_port_free(port):
    with socket.socket() as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise LocalError(f"{port} 端口被占用。请先停止自己之前启动的服务；工具不会换端口或结束其他程序。") from None


def ready():
    try:
        for path, data in (("health", {"service": "bumbum", "state": "running"}), ("ready", {"database": "ready"})):
            with OPENER.open(URL + "/api/" + path, timeout=2) as response:
                if json.load(response) != {"status": "ok", "data": data}:
                    return False
        with OPENER.open(URL, timeout=2) as response:
            return response.status == 200 and b"/@vite/client" in response.read(65536)
    except (OSError, URLError, ValueError):
        return False


def stop_requested(run_id):
    return read_json(RUNTIME / "stop.json") == {"run_id": run_id}


def serve(node, version):
    from windows_process import WindowsJob
    run_id = uuid.uuid4().hex
    state = {**version, "run_id": run_id, "phase": "starting"}
    (RUNTIME / "stop.json").unlink(missing_ok=True)
    write_json(RUNTIME / "services.json", state)
    job = WindowsJob()
    try:
        with (RUNTIME / "backend.log").open("wb") as backend, (RUNTIME / "frontend.log").open("wb") as frontend:
            job.launch([PYTHON, "-X", "utf8", "-u", "-m", "flask", "--app", "app:create_app", "--no-debug",
                        "run", "--host", "127.0.0.1", "--port", "5000", "--no-reload"], ROOT, backend)
            job.launch([node, ROOT / "frontend/admin/node_modules/vite/bin/vite.js",
                        "--host", "127.0.0.1", "--port", "5174", "--strictPort"], ROOT / "frontend/admin", frontend)
            deadline = time.monotonic() + 60
            while not ready():
                if stop_requested(run_id):
                    return
                if not job.healthy() or time.monotonic() >= deadline:
                    raise LocalError("后端或网页未能启动。请查看 .local-run 中的 backend.log / frontend.log；分享前隐藏个人信息。")
                time.sleep(1)
            state["phase"] = "ready"
            write_json(RUNTIME / "services.json", state)
            print("[5/5] 检查通过，正在打开 " + URL, flush=True)
            webbrowser.open(URL)
            print("保持此窗口运行。验收结束双击停止项目，或在此按 Ctrl+C；关闭浏览器不会停止项目。", flush=True)
            while not stop_requested(run_id):
                if not job.healthy():
                    raise LocalError("后端或网页已退出；已停止本工具的其余网页服务，请检查本机日志后重新启动。")
                time.sleep(0.5)
    finally:
        job.close()
        (RUNTIME / "services.json").unlink(missing_ok=True)
        (RUNTIME / "stop.json").unlink(missing_ok=True)
        print("本工具启动的前后端已停止；数据库请使用停止项目入口处理。", flush=True)


def start():
    with file_lock("services.lock") as available:
        if not available:
            existing = read_json(RUNTIME / "services.json") or {}
            if not existing:
                # 首个窗口刚取得锁、尚未写入状态时，重复入口也直接退出。
                return ALREADY_RUNNING
            current = version_info()
            if not all(existing.get(key) == value for key, value in current.items()):
                raise LocalError("运行版本已变化。请先双击停止项目，再启动；未重复启动服务。")
            if existing.get("phase") in {"preparing", "starting"}:
                return ALREADY_RUNNING
            if existing.get("phase") == "ready" and ready():
                return ALREADY_RUNNING
            raise LocalError("项目已在运行，但运行检查未通过。请查看原启动窗口，必要时先停止再启动。")
        (RUNTIME / "services.json").unlink(missing_ok=True)
        with file_lock("operation.lock") as operation:
            if not operation:
                raise LocalError("另一个准备或停止操作正在进行，请稍后重试。")
            version = version_info()
            write_json(RUNTIME / "services.json", {**version, "phase": "preparing"})
            print("[1/5] 检查运行环境和端口", flush=True)
            node, npm, docker = tools()
            assert_port_free(5000)
            assert_port_free(5174)
            if not PYTHON.is_file() or not (ROOT / ".env").is_file():
                raise LocalError("请先双击首次准备，再双击启动项目。")
            print("[2/5] 检查依赖；有变化时更新", flush=True)
            dependencies(node, npm)
            check_config()
            print("[3/5] 检查 Docker 和本项目测试数据库", flush=True)
            ensure_docker(docker)
            ensure_database(docker)
            print("[4/5] 启动后端和管理网页", flush=True)
            # 操作锁在进入服务循环前释放，让停止入口可以提交停止请求。
        serve(node, version)


def prepare():
    with file_lock("operation.lock") as operation:
        if not operation or running():
            raise LocalError("项目正在运行或另一个操作未结束。请先停止，再执行首次准备。")
        version_info()
        node, npm, _docker = tools()
        dependencies(node, npm)
        command([PYTHON, "-X", "utf8", "scripts/setup_local.py"], "准备本机数据库配置")
        command([PYTHON, "-X", "utf8", "scripts/setup_auth_local.py"], "补齐本机认证配置")
        check_config()
        print("准备完成，已有配置和密钥已保留。下一步双击启动项目；已有管理员直接登录。", flush=True)


def stop():
    with file_lock("operation.lock") as operation:
        if not operation:
            raise LocalError("准备或启动步骤正在进行，请等待该窗口完成或按 Ctrl+C 后再停止。")
        if running():
            state = read_json(RUNTIME / "services.json")
            if not isinstance(state, dict) or not isinstance(state.get("run_id"), str):
                raise LocalError("启动窗口尚未写好运行记录，请稍后重试；工具不会按旧 PID 强制结束程序。")
            write_json(RUNTIME / "stop.json", {"run_id": state["run_id"]})
            deadline = time.monotonic() + 20
            while running() and time.monotonic() < deadline:
                time.sleep(0.25)
            if running():
                raise LocalError("启动窗口未在20秒内响应。请在原启动窗口按 Ctrl+C，再重试停止项目。")
        print("前后端已停止，或没有本工具运行的前后端。", flush=True)
        if (RUNTIME / "database.json").is_file():
            stop_database(docker_tool())
        else:
            print("原本已运行的数据库继续保留；Docker Desktop 保持开启。", flush=True)
        print("停止完成；配置、管理员账号和测试数据保留。", flush=True)


def main():
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "start", "stop", "_check-config"}:
            raise LocalError("请使用仓库根目录的三个双击入口。")
        if sys.argv[1] == "_check-config":
            validate_config()
            return 0
        if os.name != "nt":
            raise LocalError("双击工具仅适用于 Windows；其他系统按 docs/LOCAL_DEVELOPMENT.md 操作。")
        RUNTIME.mkdir(exist_ok=True)
        return {"prepare": prepare, "start": start, "stop": stop}[sys.argv[1]]() or 0
    except KeyboardInterrupt:
        print("操作已取消，配置和数据已保留；如需停止数据库，请双击停止项目。", flush=True)
        return 130
    except LocalError as error:
        print("未完成：" + str(error), flush=True)
        return 1
    except Exception:
        print("未完成：本机操作遇到异常，配置和数据已保留。请记录发生阶段，让 AI 按本地运行说明排查。", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
