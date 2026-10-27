"""管理员工作台的只读触碰统计，沿用现有会话与来源门禁。"""

from flask import Blueprint, jsonify, request

from core.admin_auth import AuthRequestError
from core.admin_chips import positive_integer
from core.diagnostics import record_failure
from core.tap_statistics import StatisticsUnavailable, read_statistics

blueprint = Blueprint('admin_stats', __name__, url_prefix='/api/admin/stats')


@blueprint.errorhandler(StatisticsUnavailable)
def unavailable(error):
    return jsonify(status='error', code='service_unavailable', message='触碰记录尚未就绪，请先按本地或云运行手册检查003日志升级；不要重建数据库。', error_id=record_failure(error)), 503


def parse_filters():
    allowed = {'project', 'range', 'q', 'page', 'page_size'}
    if set(request.args) - allowed or any(len(request.args.getlist(name)) != 1 for name in request.args):
        raise AuthRequestError(400, 'invalid_param', '查询参数不能重复或增加字段。')
    project = request.args.get('project')
    period = request.args.get('range', '7d')
    keyword = request.args.get('q', '')
    if project is not None and project not in {'fashion', 'jewelry'}:
        raise AuthRequestError(400, 'invalid_param', '项目仅支持fashion/jewelry；全部项目请省略。')
    if period not in {'7d', '30d', 'all'} or len(keyword) > 128:
        raise AuthRequestError(400, 'invalid_param', '时间范围须为7d/30d/all，关键词最多128字符。')
    return {'project': project, 'range': period, 'q': keyword.strip(),
            'page': positive_integer('page', 1, 2147483647), 'page_size': positive_integer('page_size', 20, 100)}


@blueprint.get('/taps')
def taps():
    return jsonify(status='ok', data=read_statistics(parse_filters()))
