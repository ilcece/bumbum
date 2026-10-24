"""临时观察扫码请求；原文模式须由测试者主动开启，不改变认证和业务响应。"""

from datetime import datetime
import json
from pathlib import Path
import re
import secrets
import time

from flask import g, request
from werkzeug.exceptions import HTTPException

PATH = "/api/webhook/admin/scan"


def describe(value):
    """只输出固定类型、长度及格式分类；字段值本身永不进入日志。"""
    names = {str: "文字", dict: "对象", list: "数组", bool: "布尔", int: "数字", float: "数字", type(None): "空值"}
    result = {"类型": names.get(type(value), "其他")}
    if isinstance(value, str):
        result["字符数"] = len(value)
    return result


def shape(value):
    if not isinstance(value, str):
        return "非文字"
    for separator, pattern in (("连续14位", r"[0-9A-Fa-f]{14}"), ("冒号分隔", r"(?:[0-9A-Fa-f]{2}:){6}[0-9A-Fa-f]{2}"),
                               ("空格分隔", r"(?:[0-9A-Fa-f]{2} ){6}[0-9A-Fa-f]{2}"), ("短横线分隔", r"(?:[0-9A-Fa-f]{2}-){6}[0-9A-Fa-f]{2}")):
        if re.fullmatch(pattern, value.strip()):
            return separator
    if value == "NoIdentifierInCompatibilityMode":
        return "兼容模式占位"
    if re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", value):
        return "UUID"
    return "其他格式"


def summary(raw=False):
    auth = request.headers.get("Authorization", "").split(" ", 1)[0].lower()
    media = request.mimetype
    result = {
        "编号": secrets.token_hex(4),
        "方式": request.method if request.method in {"GET", "POST", "HEAD", "OPTIONS", "PUT", "PATCH", "DELETE"} else "其他",
        "认证头存在": bool(request.headers.get("Authorization")),
        "认证方式": auth if auth in {"basic", "bearer", "digest"} else ("其他" if auth else "无"),
        "内容类型": media if media in {"application/json", "text/plain", "application/x-www-form-urlencoded", "multipart/form-data"} else "其他",
        "请求字节数": request.content_length,
        "网址参数存在": bool(request.query_string),
    }
    if request.content_length is None or request.content_length > 8192:
        result["JSON观察"] = "未读取：长度未知、超过8192字节或不是JSON"
        return result
    try:
        body = request.get_data(cache=True)
    except HTTPException:
        result["JSON观察"] = "无法读取请求体"
        return result
    if raw:
        result["请求体原文"] = body.decode("utf-8", errors="backslashreplace")
    if not request.is_json:
        result["JSON观察"] = "不是JSON"
        return result
    try:
        data = json.loads(body)
    except (ValueError, RecursionError, HTTPException):
        result["JSON观察"] = "无法解析"
        return result
    result["JSON类型"] = describe(data)["类型"]
    if isinstance(data, dict):
        allowed = {"identifier", "date", "content", "tagType", "uid", "id", "data", "records", "timestamp", "type", "nfc", "ndef", "message"}
        fields = {key: describe(data[key]) for key in sorted(allowed & data.keys())}
        if "identifier" in fields:
            fields["identifier"]["格式"] = shape(data["identifier"])
        if "date" in fields:
            try:
                value = data["date"]
                fields["date"]["包含T分隔"] = isinstance(value, str) and "T" in value
                fields["date"]["可解析且含时区"] = isinstance(value, str) and datetime.fromisoformat(value).tzinfo is not None
            except ValueError:
                fields["date"]["可解析且含时区"] = False
        result["字段结构"] = fields
        result["未识别字段数"] = len(data.keys() - allowed)
    return result


def init_capture(app):
    app.config.setdefault("SCAN_CAPTURE_FILE", "/run/bumbum-diagnostics/until")
    state = {"until": None, "count": 0}

    @app.before_request
    def capture_request():
        g.pop("scan_observation", None)
        if request.path != PATH:
            return
        try:
            with Path(app.config["SCAN_CAPTURE_FILE"]).open(encoding="ascii") as stream:
                marker = stream.read(64).splitlines()
                until = int(marker[0])
            if not 0 < until - time.time() <= 300:
                return
        except (OSError, ValueError, IndexError):
            return
        if state["until"] != until:
            state.update(until=until, count=0)
        if state["count"] >= 12:
            return
        state["count"] += 1
        g.scan_observation = summary(raw=marker[1:] == ["raw"])

    @app.after_request
    def capture_result(response):
        if hasattr(g, "scan_observation"):
            record = {**g.scan_observation, "响应状态": response.status_code}
            app.logger.warning("扫码请求观察：%s", json.dumps(record, ensure_ascii=False))
        return response
