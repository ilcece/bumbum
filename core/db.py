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
    """环境变量优先于本机配置；当前不加载芯片或管理员密钥。"""
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
    """检查目标表清单与两个初始项目；只读，不自动建表或修库。"""
    try:
        with get_database().cursor() as cursor:
            cursor.execute("SHOW TABLES")
            actual_tables = {row[0] for row in cursor.fetchall()}
            if not TARGET_TABLES or not TARGET_TABLES.issubset(actual_tables):
                return False
            cursor.execute("SELECT code FROM project ORDER BY id")
            return [row[0] for row in cursor.fetchall()] == ["fashion", "jewelry"]
    except pymysql.MySQLError:
        return False
