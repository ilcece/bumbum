"""管理列表的严格参数、北京时间范围与一致性分页。"""

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
import re

from flask import request
import pymysql

from core.admin_auth import AuthRequestError
from core.db import get_database


def invalid(message):
    raise AuthRequestError(400, "invalid_param", message)


def positive_integer(name, default, maximum):
    value = request.args.get(name, str(default))
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value) or int(value) > maximum:
        invalid(f"{name}须为1到{maximum}之间的整数。")
    return int(value)


def check_parameters(allowed):
    if set(request.args) - allowed or any(len(request.args.getlist(name)) != 1 for name in request.args):
        invalid("查询参数不符合约定，不能重复或增加字段。")


def boolean_parameter(name):
    value = request.args.get(name)
    if value is not None and value not in {"true", "false"}:
        invalid(f"{name}仅接受true或false。")
    return None if value is None else value == "true"


def contains(value):
    return "%" + value.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


def date_conditions(fields, conditions, values):
    """北京时间含首尾整日，转为UTC半开区间；边界不能超出MySQL日期范围。"""
    for name, column in fields.items():
        bounds = {}
        for suffix in ("from", "to"):
            raw = request.args.get(f"{name}_{suffix}")
            if raw is None:
                continue
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
                    raise ValueError
                day = date.fromisoformat(raw)
                bound = datetime.combine(day, time()) + (timedelta(days=1) if suffix == "to" else timedelta()) - timedelta(hours=8)
                if bound.year < 1000:
                    raise ValueError
            except (ValueError, OverflowError):
                invalid(f"{name}_{suffix}须为可转换的YYYY-MM-DD日期。")
            bounds[suffix] = day
            conditions.append(column + (">=%s" if suffix == "from" else "<%s"))
            values.append(bound)
        if "from" in bounds and "to" in bounds and bounds["from"] > bounds["to"]:
            invalid(f"{name}起日不能晚于末日。")


@contextmanager
def consistent_read():
    """结束门禁只读查询的隐式事务，总数与页面从同一快照读取。"""
    connection = get_database()
    connection.rollback()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def pagination(total, requested, page_size):
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(requested, total_pages)
    return {"total": total, "page": page, "page_size": page_size,
            "total_pages": total_pages, "page_adjusted": page != requested}
