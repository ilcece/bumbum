"""读取数据库配置、按请求连接并检查最小初始化结果。"""

import os
from pathlib import Path
import re

import pymysql
from dotenv import load_dotenv
from flask import current_app, g

ROOT = Path(__file__).resolve().parents[1]
# 表名从唯一建表文件读取，避免在代码里维护第二份表清单。
TARGET_TABLES = frozenset(re.findall(r"CREATE TABLE (\w+)", (ROOT / "db/schema.sql").read_text(encoding="utf-8")))


def init_database(app, overrides=None):
    """环境变量优先于本机配置；这里仅初始化数据库连接配置。"""
    load_dotenv(ROOT / ".env", override=False)
    try:
        port = int(os.getenv("DB_PORT", "33306"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ValueError("DB_PORT 必须是 1 到 65535 的整数。") from None
    app.config.from_mapping(
        DB_HOST=os.getenv("DB_HOST", "127.0.0.1"),
        DB_PORT=port,
        DB_USER=os.getenv("DB_USER", ""),
        DB_PASSWORD=os.getenv("DB_PASSWORD", ""),
        DB_NAME=os.getenv("DB_NAME", "bumbum_digital"),
    )
    if overrides:
        app.config.update(overrides)
    app.teardown_appcontext(close_database)


def get_database():
    """一个请求共用一条连接，结束后关闭；不在启动时写数据或建表。"""
    if "database" not in g:
        config = current_app.config
        if not config["DB_USER"] or not config["DB_PASSWORD"]:
            raise pymysql.OperationalError("本地数据库配置未完成。")
        g.database = pymysql.connect(
            host=config["DB_HOST"],
            port=config["DB_PORT"],
            user=config["DB_USER"],
            password=config["DB_PASSWORD"],
            database=config["DB_NAME"],
            charset="utf8mb4",
            init_command="SET time_zone = '+00:00'",
            connect_timeout=3,
            read_timeout=3,
            write_timeout=3,
            autocommit=False,
        )
    return g.database


def close_database(_error=None):
    connection = g.pop("database", None)
    if connection is not None:
        connection.close()


def database_ready():
    """检查表、初始项目及本次芯片结构版本；只读，不自动建表或修库。"""
    try:
        with get_database().cursor() as cursor:
            cursor.execute("SHOW TABLES")
            actual_tables = {row[0] for row in cursor.fetchall()}
            if not TARGET_TABLES or not TARGET_TABLES.issubset(actual_tables):
                return False
            cursor.execute("SELECT code FROM project ORDER BY id")
            return ([row[0] for row in cursor.fetchall()] == ["fashion", "jewelry"]
                    and chip_project_schema(cursor) == "optional")
    except pymysql.MySQLError:
        return False


def chip_project_schema(cursor):
    """识别本次升级是否完整；只检查项目可空字段与防止空项目绕过绑定的约束。"""
    cursor.execute("SELECT IS_NULLABLE,COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='chip' AND COLUMN_NAME='project_id'")
    column = cursor.fetchone()
    cursor.execute("SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='chip' AND CONSTRAINT_TYPE='CHECK' AND CONSTRAINT_NAME='ck_chip_project_assignment' AND ENFORCED='YES'")
    guarded = cursor.fetchone() is not None
    cursor.execute("SELECT CONSTRAINT_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='chip' AND REFERENCED_TABLE_NAME IS NOT NULL")
    foreign_keys = set(cursor.fetchall())
    old_keys = {("fk_chip_project", "project_id", "project", "id"),
                ("fk_chip_item_project", "item_id", "item", "id"),
                ("fk_chip_item_project", "project_id", "item", "project_id")}
    new_keys = {(name + "_v2", field, table, referenced) for name, field, table, referenced in old_keys}
    if column == ("YES", "tinyint unsigned") and guarded and foreign_keys == new_keys:
        return "optional"
    if column == ("NO", "tinyint unsigned") and not guarded and foreign_keys == old_keys:
        return "required"
    return "unknown"
