"""杭州独立部署入口：准备公开配置，隔离两个环境，不代替数据库与域名授权。"""

import argparse
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.rds_target import RDS_HOST, SLOTS


class DeploymentError(Exception):
    """可公开的部署阶段说明，不包含秘密或原始容器配置。"""


def domain(value):
    """只接受普通HTTPS主机名，拒绝模板或Nginx指令注入。"""
    if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", value):
        raise DeploymentError("域名须为不带协议、端口及路径的小写主机名。")
    return value


def render_manifest(slot, image, image_id, admin_host, user_host):
    """只生成公开Compose配置；密码单独由Docker读取，不经模板插值或输出。"""
    if slot not in SLOTS:
        raise DeploymentError("必须明确test或production。")
    if not re.fullmatch(r"bumbum-hangzhou-backend:[0-9a-f]{40}", image):
        raise DeploymentError("镜像标签须固定到完整Git提交，不使用latest。")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise DeploymentError("须记录已构建/导入镜像的完整内容ID。")
    admin_host, user_host = domain(admin_host), domain(user_host)
    if admin_host == user_host:
        raise DeploymentError("管理与用户域名必须分开。")
    if slot == "test" and ({admin_host, user_host} & {"admin.bumbum.cc", "nfc.bumbum.cc"}):
        raise DeploymentError("测试环境不得占用正式管理或实卡用户域名。")
    target = SLOTS[slot]
    base = f"/opt/bumbum-hangzhou/{slot}"
    env = {"APP_ENV": "production", "HANGZHOU_SLOT": slot,
           "ADMIN_ORIGIN": "https://" + admin_host, "PUBLIC_ORIGIN": "https://" + user_host,
           "ADMIN_TOTP_ISSUER": "BUMBUM-" + slot, "STORAGE_KEY_VERSION": "v1",
           "DB_HOST": RDS_HOST, "DB_PORT": "3306", "DB_NAME": target["database"],
           "DB_USER": target["user"], "DB_SSL_MODE": "VERIFY_IDENTITY",
           "DB_SSL_CA": "/run/bumbum-rds-ca.pem"}
    service = {
        "image": image, "pull_policy": "never", "network_mode": "host",
        "env_file": [{"path": base + "/secrets/runtime.env", "format": "raw"}],
        "environment": env, "user": "10001:10001", "restart": "unless-stopped",
        "read_only": True, "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
        "tmpfs": ["/tmp:size=32m,mode=1777"], "pids_limit": 128,
        "mem_limit": "512m" if slot == "production" else "256m",
        "memswap_limit": "512m" if slot == "production" else "256m",
        "cpus": 1.25 if slot == "production" else 0.5,
        "volumes": ["operation_logs:/app/logs", {"type": "bind",
                    "source": base + "/public/rds-ca.pem", "target": "/run/bumbum-rds-ca.pem",
                    "read_only": True, "bind": {"create_host_path": False}}],
        "command": ["gunicorn", "--no-control-socket", "--bind", f"127.0.0.1:{target['port']}",
                    "--workers", "2" if slot == "production" else "1", "--worker-tmp-dir", "/tmp",
                    "--timeout", "30", "app:create_app()"],
        "healthcheck": {"test": ["CMD", "python", "-c",
                      f"import urllib.request; urllib.request.urlopen('http://127.0.0.1:{target['port']}/api/ready', timeout=3)"],
                      "interval": "15s", "timeout": "5s", "retries": 6, "start_period": "20s"},
        "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
        "labels": {"cc.bumbum.image-id": image_id, "cc.bumbum.slot": slot},
    }
    return {"name": "bumbum-hangzhou-" + slot, "services": {"backend": service},
            "volumes": {"operation_logs": {}}}


def render_nginx(slot, admin_host, user_host, admin_ip):
    """复用已验收网关规则，只替换经过校验的主机、目录、端口及独立限流区。"""
    domain(admin_host)
    domain(user_host)
    try:
        admin_ip = str(ipaddress.ip_address(admin_ip))
    except ValueError:
        raise DeploymentError("管理白名单须为已核对的单个出口IP，不能放宽为所有来源。") from None
    port = SLOTS[slot]["port"]
    admin = (ROOT / "deploy/cloud_test/nginx-https.conf.template").read_text(encoding="utf-8")
    user = (ROOT / "deploy/cloud_test/nginx-user-https.conf.template").read_text(encoding="utf-8")
    admin = admin.replace("test.bumbum.cc", admin_host).replace("__ADMIN_IP__", admin_ip)
    user = user.replace("nfc.bumbum.cc", user_host)
    admin = admin.replace("bumbum_cloud_test", f"bumbum_hz_{slot}").replace("bumbum_test_", f"bumbum_hz_{slot}_")
    user = user.replace("bumbum_user", f"bumbum_hz_{slot}_user")
    for old, new in (("/var/www/bumbum-cloud-test", f"/var/www/bumbum-hangzhou-{slot}-admin"),
                     ("/var/www/bumbum-user-test", f"/var/www/bumbum-hangzhou-{slot}-user"),
                     ("bumbum-cloud-test-proxy.conf", f"bumbum-hangzhou-{slot}-proxy.conf"),
                     ("bumbum-cloud-test-access.log", f"bumbum-hangzhou-{slot}-admin-access.log"),
                     ("bumbum-user-access.log", f"bumbum-hangzhou-{slot}-user-access.log"),
                     ("127.0.0.1:15000", f"127.0.0.1:{port}")):
        admin, user = admin.replace(old, new), user.replace(old, new)
    header = "# 杭州独立环境生成稿；先检查证书、DNS、白名单与nginx -t，再按批准范围启用。\n"
    proxy = (ROOT / "deploy/cloud_test/nginx-proxy.conf").read_text(encoding="utf-8")
    return {"admin.conf": header + admin, "user.conf": header + user, "proxy.conf": proxy}


def write_new(path, text):
    """保留已有配置；不同内容必须另选版本目录，不覆盖人工修改。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or path.read_text(encoding="utf-8") != text:
            raise DeploymentError("输出位置已有不同内容；请另选版本目录，不覆盖。")
        return
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def prepare_test_runtime(destination, password, username):
    """仅为独立测试准备新秘密；不读取、覆盖或复制已有环境配置。"""
    if not password or any(c in password for c in "\r\n\0"):
        raise DeploymentError("数据库密码必须为非空单行，只在隐藏提示输入。")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", username):
        raise DeploymentError("测试管理员账号名须为1—64位字母、数字、下划线或连字符。")
    values = {"DB_PASSWORD": password, "STORAGE_ENCRYPTION_KEY": secrets.token_hex(32),
              "IP_HASH_KEY": secrets.token_hex(32), "WEBHOOK_ADMIN_USERNAME": username,
              "WEBHOOK_SHARED_SECRET": secrets.token_hex(32),
              "MASTER_KEY_FASHION": secrets.token_hex(16), "MASTER_KEY_JEWELRY": secrets.token_hex(16),
              "SDM_META_KEY_V1": secrets.token_hex(16), "SDM_META_KEY_VERSION": "v1", "TAP_VERIFY_PER_MINUTE": "60"}
    if destination.exists() or destination.is_symlink():
        raise DeploymentError("已有测试秘密文件，未读取或覆盖。")
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.parent.is_symlink():
        raise DeploymentError("秘密目录不能为符号链接，未写入。")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write("".join(f"{key}={value}\n" for key, value in values.items()))


def docker(arguments):
    """固定本机Docker socket；只返回必要元数据，失败时不显示含配置的原始输出。"""
    env = {name: value for name, value in os.environ.items()
           if name not in {"DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}
    result = subprocess.run(["docker", "--host=unix:///var/run/docker.sock", *arguments],
                            env=env, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise DeploymentError("本机Docker命令未完成；保留现场，未输出容器配置、环境或原始日志。")
    return result.stdout.strip()


def check_deployment(path, slot, *, require_runtime=True):
    """核对公开清单、镜像内容和已有项目归属，不读取秘密文件内容。"""
    document = json.loads(path.read_text(encoding="utf-8"))
    service = document["services"]["backend"]
    env = service["environment"]
    expected = render_manifest(slot, service["image"], service["labels"]["cc.bumbum.image-id"],
                               env["ADMIN_ORIGIN"].removeprefix("https://"), env["PUBLIC_ORIGIN"].removeprefix("https://"))
    if document != expected:
        raise DeploymentError("Compose配置与对应环境的保护不符，未接管或启动。")
    if docker(["image", "inspect", "--format", "{{.Id}}", service["image"]]) != service["labels"]["cc.bumbum.image-id"]:
        raise DeploymentError("镜像标签指向的内容已变化，停止而不拉取其他版本。")
    ids = docker(["ps", "-aq", "--filter", "label=com.docker.compose.project=" + document["name"]]).splitlines()
    for container in ids:
        # 同一固定清单目录可更新镜像；不接管另一目录启动的同名项目。
        owner = docker(["inspect", "--format", '{{index .Config.Labels "com.docker.compose.project.config_files"}}', container])
        if owner != str(path.resolve()):
            raise DeploymentError("同名环境来自其他Compose路径，停止并先核对其归属。")
    if require_runtime:
        if not ids:
            try:
                with socket.socket() as listener:
                    listener.bind(("127.0.0.1", SLOTS[slot]["port"]))
            except OSError:
                raise DeploymentError("该环境回环端口已被其他服务占用，未接管或停止其他进程。") from None
        runtime = Path(service["env_file"][0]["path"])
        if not runtime.is_file() or runtime.is_symlink() or runtime.stat().st_mode & 0o077:
            raise DeploymentError("须先安全准备非符号链接、仅本人可读的runtime.env；未读取内容。")
        ca = Path(service["volumes"][1]["source"])
        if not ca.is_file():
            raise DeploymentError("公开CA尚未放在专用目录；未创建空目录代替证书。")
        # 只安静验证，不把插值后的秘密或运行配置打印到终端。
        docker(["compose", "-f", str(path.resolve()), "config", "--quiet"])
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(description="杭州独立环境准备及受保护启停；不自动初始化数据库、启用Nginx或切换DNS。")
    parser.add_argument("action", choices=["prepare", "prepare-runtime", "check", "start", "status", "stop"])
    parser.add_argument("--slot", required=True, choices=SLOTS)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--image")
    parser.add_argument("--image-id")
    parser.add_argument("--admin-host")
    parser.add_argument("--user-host")
    parser.add_argument("--admin-ip")
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action != "prepare-runtime" and args.manifest is None:
            raise DeploymentError("此操作须明确指定公开Compose清单的--manifest路径。")
        if args.action == "prepare-runtime":
            if args.slot != "test":
                raise DeploymentError("此入口只生成独立测试配置；生产必须按批准的数据迁移方案安全注入并保留必要原密钥。")
            if not sys.stdin.isatty():
                raise DeploymentError("须由操作者在受控终端隐藏输入数据库密码，不从管道或现有配置读取。")
            username = input("新测试管理员账号名（公开文字）：").strip()
            password = getpass.getpass("bumbum_hz_test数据库账号密码（不回显）：")
            prepare_test_runtime(Path("/opt/bumbum-hangzhou/test/secrets/runtime.env"), password, username)
            print("独立测试配置已按600权限保存，未输出秘密；尚未创建管理员或启动服务。")
            return 0
        if args.action == "prepare":
            if not all((args.image, args.image_id, args.admin_host, args.user_host, args.admin_ip)):
                raise DeploymentError("准备须提供固定镜像及内容ID、两个独立域名和管理出口IP。")
            manifest = render_manifest(args.slot, args.image, args.image_id, args.admin_host, args.user_host)
            nginx = render_nginx(args.slot, args.admin_host, args.user_host, args.admin_ip)
            write_new(args.manifest, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            for name, content in nginx.items():
                write_new(args.manifest.parent / name, content)
            print("公开部署配置已准备；没有生成/读取秘密、建库、安装、启动、启用Nginx或切域名。")
            return 0
        if args.slot == "production" and args.action in {"start", "stop"} and not args.confirm_production:
            raise DeploymentError("生产启停须明确--confirm-production，并按已批准窗口执行。")
        document = check_deployment(args.manifest, args.slot, require_runtime=args.action in {"check", "start"})
        command = ["compose", "-p", document["name"], "-f", str(args.manifest.resolve())]
        if args.action == "start":
            docker([*command, "up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "120"])
            print("指定后端已就绪；未启用公网或切换域名，仍须完成网页、安全及业务验收。")
        elif args.action == "stop":
            docker([*command, "stop", "backend"])
            print("仅停止指定环境后端；数据库、另一环境、Nginx及数据保留。")
        elif args.action == "status":
            print(docker([*command, "ps"]))
        else:
            print("公开清单、镜像、项目归属及私有文件权限检查通过；不代表数据库与业务验收通过。")
        return 0
    except DeploymentError as error:
        print("未完成：" + str(error), file=sys.stderr)
    except Exception:
        print("未完成：输入、文件或本机工具检查失败；未输出秘密，请保留现场核对。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
