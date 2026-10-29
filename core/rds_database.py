"""杭州RDS目标识别与空库初始化；凭证只从操作者终端隐藏输入。"""

import argparse
import getpass
import json
from pathlib import Path
import re
import sys
import uuid

import pymysql
from pymysql.constants import CLIENT

from core.db import TARGET_TABLES, database_tls_options
from core.rds_target import RDS_HOST, SLOTS, validate_target

SCHEMA = Path(__file__).resolve().parents[1] / "db/schema.sql"


class RdsPreparationError(Exception):
    """只返回可公开的准备阶段说明，不输出连接秘密或SQL正文。"""


def schema_for_selected_database(source):
    """只移除唯一建表文件已知的两个定向语句，不替换任意SQL或复制另一份DDL。"""
    source, created = re.subn(
        r"(?m)^CREATE DATABASE IF NOT EXISTS bumbum_digital\s+"
        r"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\s*", "", source,
    )
    source, selected = re.subn(r"(?m)^USE bumbum_digital;\s*", "", source)
    if created != 1 or selected != 1:
        raise RdsPreparationError("唯一建表文件的库定向语句已变化，停止而不猜测替换。")
    if re.search(r"(?im)^\s*(?:USE\s|CREATE\s+DATABASE\s|DROP\s)", source):
        raise RdsPreparationError("建表文件含未认可的跨库或删除语句，未执行。")
    return source


def inspect_target(connection, database):
    """只查询当前连接身份及结构数量，不读取业务行或秘密字段。"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE(), VERSION(), @@server_uuid, CURRENT_USER()")
        selected, version, server_uuid, account = cursor.fetchone()
        expected_users = {target["user"] + "_init" for target in SLOTS.values() if target["database"] == database}
        if account.split("@", 1)[0] not in expected_users:
            raise RdsPreparationError("实际认证身份不是该库的专用初始化账号，未初始化。")
        if selected != database or not re.fullmatch(r"8\.0\.(\d+).*", version) or int(version.split('.')[2].split('-')[0]) < 16:
            raise RdsPreparationError("目标库或MySQL版本不符合已验证范围，未初始化。")
        cursor.execute("SELECT DEFAULT_CHARACTER_SET_NAME,DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (database,))
        charset = cursor.fetchone()
        if charset != ("utf8mb4", "utf8mb4_unicode_ci"):
            raise RdsPreparationError("目标库字符集/排序规则不符，未自动修改已有库。")
        cursor.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s", (database,))
        tables = {row[0] for row in cursor.fetchall()}
        extra = 0
        for table in ("ROUTINES", "TRIGGERS", "EVENTS"):
            field = {"ROUTINES": "ROUTINE_SCHEMA", "TRIGGERS": "TRIGGER_SCHEMA", "EVENTS": "EVENT_SCHEMA"}[table]
            cursor.execute(f"SELECT COUNT(*) FROM information_schema.{table} WHERE {field}=%s", (database,))
            extra += cursor.fetchone()[0]
    # 驱动客户端socket为本次连接提供TLS证据，不依赖RDS服务端Ssl_cipher。
    cipher = connection._sock.cipher() if hasattr(connection._sock, "cipher") else None
    if not cipher:
        raise RdsPreparationError("当前客户端连接没有TLS证据，停止而不尝试明文。")
    return {"database": selected, "mysql_version": version, "server_uuid": server_uuid,
            "account": account, "table_count": len(tables), "other_object_count": extra,
            "tables_complete": tables == TARGET_TABLES, "empty": not tables and not extra,
            "client_tls_cipher": cipher[0]}


def initialize_empty(connection, database, expected_uuid, source):
    """明确锁定实例和空库；DDL失败保留现场，不清库、重跑或自动恢复。"""
    sql = schema_for_selected_database(source)
    lock_name = "bumbum.rds-init." + database
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s,5)", (lock_name,))
        if cursor.fetchone()[0] != 1:
            raise RdsPreparationError("其他初始化正在执行，未继续。")
        try:
            report = inspect_target(connection, database)
            if report["server_uuid"] != expected_uuid or not report["empty"]:
                raise RdsPreparationError("实例标识不符或目标不是空库；未执行任何建表。")
            cursor.execute(sql)
            while cursor.nextset():
                pass
            connection.commit()
            result = inspect_target(connection, database)
            if not result["tables_complete"]:
                raise RdsPreparationError("初始化后结构数量不符，保留现场，不自动删除或重建。")
            return result
        finally:
            cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))


def main(argv=None):
    parser = argparse.ArgumentParser(description="杭州RDS只读识别或显式空库初始化；不迁移或恢复已有数据。")
    parser.add_argument("--slot", required=True, choices=SLOTS)
    parser.add_argument("--ca", required=True)
    parser.add_argument("--initialize-empty", action="store_true")
    parser.add_argument("--confirm-database")
    parser.add_argument("--confirm-server-uuid")
    args = parser.parse_args(argv)
    target = SLOTS[args.slot]
    config = {"APP_ENV": "production", "HANGZHOU_SLOT": args.slot,
              "DB_HOST": RDS_HOST, "DB_PORT": 3306, "DB_NAME": target["database"],
              "DB_USER": target["user"] + "_init", "DB_SSL_MODE": "VERIFY_IDENTITY", "DB_SSL_CA": args.ca}
    try:
        validate_target(config, initialization=True)
        tls = database_tls_options(config)
        if args.initialize_empty:
            if args.confirm_database != target["database"] or not args.confirm_server_uuid:
                raise RdsPreparationError("初始化须明确填写目标库名及先前只读检查的server_uuid。")
            uuid.UUID(args.confirm_server_uuid)
        if not sys.stdin.isatty():
            raise RdsPreparationError("请由操作者在受控终端执行并隐藏输入密码；不从管道、环境或配置文件取密码。")
        password = getpass.getpass("RDS专用初始化账号密码（不回显）：")
        if not password:
            raise RdsPreparationError("未输入密码，未连接。")
        with pymysql.connect(host=RDS_HOST, port=3306, database=target["database"],
                             user=config["DB_USER"], password=password, charset="utf8mb4",
                             connect_timeout=5, read_timeout=30, write_timeout=10,
                             client_flag=CLIENT.MULTI_STATEMENTS if args.initialize_empty else 0,
                             autocommit=False, **tls) as connection:
            if args.initialize_empty:
                report = initialize_empty(connection, target["database"], args.confirm_server_uuid,
                                          SCHEMA.read_text(encoding="utf-8"))
            else:
                report = inspect_target(connection, target["database"])
            print(json.dumps(report, ensure_ascii=False))
        return 0
    except RdsPreparationError as error:
        print("未完成：" + str(error), file=sys.stderr)
    except Exception:
        print("未完成：配置、认证、证书或结构检查失败；未显示秘密或原始SQL。若已开始DDL，保留现场，不自动重跑。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
