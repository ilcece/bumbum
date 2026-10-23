"""最小后端入口：提供运行检查和管理员认证。"""

from flask import Flask, abort, jsonify, request
from werkzeug.exceptions import HTTPException

from core.db import database_ready, init_database


def create_app(test_config=None):
    """创建应用；测试可单独传入配置，不需要生产凭证。"""
    app = Flask(__name__, static_folder=None)
    app.json.sort_keys = False
    init_database(app, test_config)
    from core.admin_auth import init_auth
    from core.admin_cli import admin_commands
    init_auth(app)
    app.cli.add_command(admin_commands)

    @app.after_request
    def prevent_cache(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.before_request
    def validate_check_parameters():
        if request.path in {"/api/health", "/api/ready"} and request.args:
            abort(400)

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", data={"service": "bumbum", "state": "running"})

    @app.get("/api/ready")
    def ready():
        if not database_ready():
            return jsonify(
                status="error",
                code="service_unavailable",
                message="测试数据库尚未就绪，请按启动说明检查数据库。",
            ), 503
        return jsonify(status="ok", data={"database": "ready"})

    @app.errorhandler(HTTPException)
    def http_error(error):
        descriptions = {
            400: ("invalid_param", "输入不符合接口约定；运行检查不接收查询参数。"),
            404: ("not_found", "地址不存在，或该业务尚未接入。"),
            405: ("method_not_allowed", "此地址不支持这种请求方式。"),
        }
        code, message = descriptions.get(error.code, ("request_failed", "请求未完成。"))
        response = error.get_response()
        response.data = app.json.dumps({"status": "error", "code": code, "message": message})
        response.content_type = "application/json"
        return response

    @app.errorhandler(Exception)
    def unexpected_error(_error):
        # 不向浏览器输出异常详情，避免泄露连接信息或将来的秘密。
        return jsonify(status="error", code="internal_error", message="程序暂时无法处理请求。"), 500

    return app
