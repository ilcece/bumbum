"""检查并升级本机测试库；先完整备份，不连接生产，不覆盖配置或业务记录。"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.db import chip_project_schema, get_database, registration_source_schema, tap_event_schema
from core.tap_migration import migrate as migrate_tap, TapMigrationError
from core.registration_migration import migrate as migrate_source, SourceMigrationError

MIGRATIONS = {
    "optional": ROOT / "db/migrations/001_chip_project_optional.sql",
    "required": ROOT / "db/migrations/001_chip_project_optional_rollback.sql",
}


class MigrationError(Exception):
    """只包含可公开的阶段说明，不输出数据库连接或秘密。"""


def validate_local_config(config):
    expected = {"APP_ENV": "development", "DB_PORT": 33306, "DB_USER": "bumbum_dev", "DB_NAME": "bumbum_digital"}
    if config.get("DB_HOST") not in {"127.0.0.1", "localhost"} or any(config.get(key) != value for key, value in expected.items()):
        raise MigrationError("此命令只允许默认本机测试库；未执行升级，请核对本地运行说明。")


def run_docker(arguments, *, output=None, timeout=120):
    try:
        result = subprocess.run([str(part) for part in arguments], stdout=output or subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise MigrationError("Docker命令未完成或超时；请检查Docker，未显示原始连接信息。") from None
    if result.returncode:
        raise MigrationError("数据库检查或备份失败；未继续修改表结构，请检查Docker和本机数据库。")
    return result.stdout.decode("utf-8").strip() if output is None else None


def local_container():
    docker = shutil.which("docker")
    if not docker:
        raise MigrationError("未找到Docker，请先启动本机测试数据库。")
    host = os.environ.get("DOCKER_HOST") if not os.environ.get("DOCKER_CONTEXT") else None
    if not host:
        host = json.loads(run_docker([docker, "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"], timeout=15))
    if not isinstance(host, str) or not host.startswith(("npipe://", "unix://")):
        raise MigrationError("Docker连接不是本机连接，未执行备份或升级。")
    command = [docker, "--host", host]
    ids = run_docker([*command, "ps", "--filter", "label=com.docker.compose.project=bumbum-local",
                      "--filter", "label=com.docker.compose.service=db", "--format", "{{.ID}}"], timeout=15).splitlines()
    if len(ids) != 1:
        raise MigrationError("未找到唯一且已运行的本项目测试库；请先按本地说明启动数据库。")
    metadata = json.loads(run_docker([*command, "inspect", "--format",
        '{"folder":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},"ports":{{json .NetworkSettings.Ports}}}', ids[0]], timeout=15))
    folder = metadata.get("folder")
    if not folder or os.path.normcase(os.path.abspath(folder)) != os.path.normcase(str(ROOT)):
        raise MigrationError("数据库属于另一个目录，未操作。请回原克隆目录核对配套配置。")
    if metadata.get("ports", {}).get("3306/tcp") != [{"HostIp": "127.0.0.1", "HostPort": "33306"}]:
        raise MigrationError("数据库端口不符合本机测试约定，未操作。")
    return command, ids[0]


def backup_database(command, container, destination):
    """在容器内读取既有凭证，完整导出到私有文件；密码不进入命令参数。"""
    partial = destination.with_suffix(".partial")
    created = False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as output:
            run_docker([*command, "exec", container, "sh", "-c",
                'MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump --single-transaction --skip-lock-tables --no-tablespaces --set-gtid-purged=OFF --hex-blob -u "$MYSQL_USER" "$MYSQL_DATABASE"'], output=output)
        with partial.open("rb") as source:
            source.seek(max(0, partial.stat().st_size - 512))
            if b"-- Dump completed on" not in source.read():
                raise MigrationError("备份不完整，未执行表结构升级。")
        # 文件名带随机编号，不覆盖任何已有备份。
        if destination.exists():
            raise MigrationError("备份文件已存在，未覆盖。")
        partial.replace(destination)
        return destination
    except PermissionError:
        raise MigrationError("备份目录或文件无法访问，未继续修改表结构；可使用--backup-dir指定本人可写的私有目录，不要删除旧备份或关闭安全防护。") from None
    finally:
        if created:
            partial.unlink(missing_ok=True)


def migrate(connection, backup, *, rollback=False):
    """将备份与单条原子DDL串起来；失败不执行自动恢复或写入业务资料。"""
    target = "required" if rollback else "optional"
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK('bumbum.chip-project-migration',5)")
        if cursor.fetchone()[0] != 1:
            raise MigrationError("另一个升级正在执行，请稍后重试。")
        try:
            cursor.execute("SELECT VERSION()")
            if not cursor.fetchone()[0].startswith("8.0."):
                raise MigrationError("此升级只在MySQL 8.0验证过，未执行修改。")
            state = chip_project_schema(cursor)
            if state == target:
                return False
            if state == "unknown":
                raise MigrationError("数据库结构不属于本次已知版本，未自动修复，请让AI排查。")
            if rollback:
                cursor.execute("SELECT COUNT(*) FROM chip WHERE project_id IS NULL")
                if cursor.fetchone()[0]:
                    raise MigrationError("已有未分配项目的芯片，不能回退为必填；未删除记录或替你分配项目。")
            connection.commit()
            backup()
            cursor.execute("SET SESSION lock_wait_timeout=10")
            cursor.execute(MIGRATIONS[target].read_text(encoding="utf-8"))
            if chip_project_schema(cursor) != target:
                raise MigrationError("升级后结构检查未通过。请停止操作、保留备份，让AI排查，不要重建数据库。")
            return True
        finally:
            cursor.execute("SELECT RELEASE_LOCK('bumbum.chip-project-migration')")


def main():
    parser = argparse.ArgumentParser(description="检查本机测试库的芯片项目升级；默认只检查。")
    parser.add_argument("--apply", action="store_true", help="完整备份成功后执行升级")
    parser.add_argument("--rollback", action="store_true", help="回退此项结构；已有未分配芯片时拒绝")
    parser.add_argument("--tap-events", action="store_true", help="检查触碰日志结构；配合--apply先备份再升级")
    parser.add_argument("--registration-source", action="store_true", help="检查首次登记来源；配合--apply先备份再升级")
    parser.add_argument("--backup-dir", type=Path, help="可选的私有备份目录；默认仍为仓库backups，只在确需升级时创建备份")
    args = parser.parse_args()
    if args.tap_events and (args.rollback or args.registration_source):
        parser.error("触碰日志升级不与回退或来源升级混用。")
    if args.registration_source and args.rollback:
        parser.error("来源升级不支持此回退参数；旧版本可保留新增字段运行。")
    inspect_schema = tap_event_schema if args.tap_events else registration_source_schema if args.registration_source else chip_project_schema
    try:
        from app import create_app
        app = create_app()
        validate_local_config(app.config)
        with app.app_context():
            connection = get_database()
            with connection.cursor() as cursor:
                cursor.execute("SELECT CURRENT_USER(),@@server_uuid")
                account, server_id = cursor.fetchone()
                if not account.startswith("bumbum_dev@"):
                    raise MigrationError("当前数据库账号不是本机测试账号，未执行操作。")
                state = inspect_schema(cursor)
                if not args.apply:
                    labels = {"required": "需要升级：芯片项目目前必填。", "optional": "已是新版本：芯片项目可以暂不分配。"}
                    if args.registration_source:
                        labels = {"missing": "需要升级：缺少首次登记来源字段。", "ready": "来源字段已存在；--apply会检查是否还有可可靠补齐的历史来源。"}
                    if args.tap_events:
                        labels = {"missing": "需要升级：触碰日志缺少可信关联和去重约束。", "ready": "触碰日志已就绪。"}
                    print(labels.get(state, "数据库结构无法识别，请让AI排查。"))
                    return 0 if state != "unknown" else 1
            target = "required" if args.rollback else "optional"
            if not args.registration_source and not args.tap_events and state == target:
                print("已是目标版本，无需重复执行；没有新建备份或修改数据。")
                return 0
            command, container = local_container()
            actual_id = run_docker([*command, "exec", container, "sh", "-c",
                'MYSQL_PWD="$MYSQL_PASSWORD" exec mysql -N -B -u "$MYSQL_USER" "$MYSQL_DATABASE" --execute="SELECT @@server_uuid"'], timeout=15)
            if actual_id != server_id:
                raise MigrationError("配置连接的数据库与Docker容器不一致，未执行操作。")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            folder = args.backup_dir.expanduser().resolve() if args.backup_dir is not None else ROOT / "backups"
            destination = folder / f"before-{'tap-events' if args.tap_events else 'chip-source' if args.registration_source else 'chip-project'}-{stamp}-{uuid.uuid4().hex[:8]}.sql"

            def backup():
                backup_database(command, container, destination)
                print("完整备份已保存到：" + str(destination))

            changed = migrate_tap(connection, backup) if args.tap_events else migrate_source(connection, backup) if args.registration_source else migrate(connection, backup, rollback=args.rollback)
            print("升级完成，原有账号和芯片资料保留。" if changed and not args.rollback else "回退完成。" if changed else "已是目标版本，无需重复执行。")
            return 0
    except (MigrationError, SourceMigrationError, TapMigrationError) as error:
        print("未完成：" + str(error), file=sys.stderr)
    except Exception:
        print("未完成：数据库升级或检查失败。保留已生成的备份；不要清空数据库或重新执行schema.sql，请让AI按运行手册排查。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
