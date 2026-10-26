"""只记录允许字段的错误诊断，不格式化异常正文、请求内容或局部变量。"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import secrets

from flask import g, request

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger("bumbum.diagnostics")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.ERROR)
LOGGER.propagate = False


def record_failure(error):
    """记录失败也不能替代原业务结果；编号在同一请求内复用。"""
    if g.get("diagnostic_error_id"):
        return g.diagnostic_error_id
    error_id = secrets.token_hex(12)
    g.diagnostic_error_id = error_id
    try:
        locations = []
        frame = error.__traceback__
        while frame is not None:
            filename = Path(frame.tb_frame.f_code.co_filename).resolve()
            if filename.is_relative_to(ROOT):
                relative = filename.relative_to(ROOT)
                if relative.parts[0] in {"app.py", "core", "tests"}:
                    locations.append({"file": relative.as_posix(), "line": frame.tb_lineno})
            frame = frame.tb_next
        event = {
            "event": "request_failure", "error_id": error_id,
            "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "method": request.method if request.method in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"} else "OTHER",
            "route": request.url_rule.rule if request.url_rule else "unmatched",
            "exception_type": type(error).__name__, "locations": locations[-12:],
        }
        LOGGER.error(json.dumps(event, ensure_ascii=False))
    except Exception:
        # 不打印日志故障原文，也不让它改变原来的提交或回滚结果。
        pass
    return error_id
