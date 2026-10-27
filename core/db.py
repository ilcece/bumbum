"""读取数据库配置、按请求连接并检查最小初始化结果。"""

import os
from pathlib import Path
import re

import pymysql
from dotenv import load_dotenv
from flask import current_app, g

from core.diagnostics import record_failure

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
                    and chip_project_schema(cursor) == "optional"
                    and registration_source_schema(cursor) == "ready"
                    and tap_event_schema(cursor) == "ready")
    except pymysql.MySQLError as error:
        record_failure(error)
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


def registration_source_schema(cursor):
    """只识别来源列的已知定义；缺列时引导升级，不猜测已有列的用途。"""
    cursor.execute("SELECT COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='chip' AND COLUMN_NAME='registration_source'")
    column = cursor.fetchone()
    if column is None:
        return "missing"
    return "ready" if column == ("enum('unknown','manual','nfc_cool')", "NO", "unknown") else "unknown"


def tap_event_schema(cursor):
    """识别完整触碰事件结构；部分升级或约束被改动时不冒充就绪。"""
    cursor.execute("SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,GENERATION_EXPRESSION FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='scan_log'")
    columns = {row[0]: row[1:] for row in cursor.fetchall()}
    old_names = {'id', 'chip_uid', 'project_id', 'picc_data', 'cmac', 'scan_counter', 'verify_result', 'user_agent', 'ip_hash', 'created_at'}
    old_enum = "enum('pass','cmac_fail','decrypt_fail','unknown_chip','replay_suspect','disabled')"
    base_types = {'id': ('bigint unsigned', 'NO'), 'chip_uid': ('varchar(32)', 'YES'),
                  'project_id': ('tinyint unsigned', 'YES'), 'picc_data': ('varchar(256)', 'YES'),
                  'cmac': ('varchar(64)', 'YES'), 'scan_counter': ('bigint unsigned', 'YES'),
                  'user_agent': ('varchar(512)', 'YES'), 'ip_hash': ('varchar(64)', 'YES'),
                  'created_at': ('timestamp', 'YES')}
    if any(name not in columns or columns[name][:2] != expected for name, expected in base_types.items()):
        return 'unknown'
    if set(columns) == old_names and columns['verify_result'][:2] == (old_enum, 'NO'):
        return 'missing'
    new_names = {'chip_id', 'item_id', 'accepted_counter'}
    if set(columns) != old_names | new_names or columns['verify_result'][:2] != (old_enum[:-1] + ",'not_ready')", 'NO'):
        return 'unknown'
    if any(columns[name][:2] != ('bigint unsigned', 'YES') for name in new_names):
        return 'unknown'

    def compact(value):
        normalized = value.lower().replace("\\'", "'").replace('_utf8mb4', '').replace('_latin1', '')
        return ''.join(character for character in normalized if not character.isspace() and character not in " `")

    # MySQL按创建连接可能输出latin1或utf8mb4常量及转义引号；只规范化已知等价形式。
    expression = compact(columns['accepted_counter'][2])
    if expression != "(casewhen(verify_result='pass')thenscan_counterelsenullend)":
        return 'unknown'
    cursor.execute("SELECT INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SEQ_IN_INDEX FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='scan_log' ORDER BY INDEX_NAME,SEQ_IN_INDEX")
    indexes = {}
    for name, non_unique, column, position in cursor.fetchall():
        indexes.setdefault(name, []).append((non_unique, column))
    expected = {
        'PRIMARY': [(0, 'id')],
        'uk_scan_accepted': [(0, 'chip_id'), (0, 'accepted_counter')],
        'idx_scan_success_time': [(1, 'verify_result'), (1, 'created_at')],
        'idx_scan_project_success': [(1, 'project_id'), (1, 'verify_result'), (1, 'created_at')],
        'idx_scan_item_success': [(1, 'item_id'), (1, 'verify_result'), (1, 'created_at')],
    }
    if any(indexes.get(name) != values for name, values in expected.items()):
        return 'unknown'
    cursor.execute("SELECT CONSTRAINT_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='scan_log' AND REFERENCED_TABLE_NAME IS NOT NULL")
    if set(cursor.fetchall()) != {('fk_scan_chip', 'chip_id', 'chip', 'id'), ('fk_scan_item_project', 'item_id', 'item', 'id'), ('fk_scan_item_project', 'project_id', 'item', 'project_id')}:
        return 'unknown'
    cursor.execute("SELECT c.CHECK_CLAUSE,t.ENFORCED FROM information_schema.CHECK_CONSTRAINTS c JOIN information_schema.TABLE_CONSTRAINTS t ON t.CONSTRAINT_SCHEMA=c.CONSTRAINT_SCHEMA AND t.CONSTRAINT_NAME=c.CONSTRAINT_NAME WHERE t.TABLE_SCHEMA=DATABASE() AND t.TABLE_NAME='scan_log' AND t.CONSTRAINT_NAME='ck_scan_pass'")
    check = cursor.fetchone()
    clause = "((verify_result<>'pass') OR ((chip_id IS NOT NULL) AND (item_id IS NOT NULL) AND (project_id IS NOT NULL) AND (chip_uid IS NOT NULL) AND (scan_counter IS NOT NULL) AND (scan_counter<16777215)))"
    return 'ready' if check and check[1] == 'YES' and compact(check[0]) == compact(clause) else 'unknown'
