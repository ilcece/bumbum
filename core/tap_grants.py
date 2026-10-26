"""用户触碰路由及按物品核对的临时查看凭证，不提供认领接口。"""

import os

from flask import Blueprint, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, request_json, token_hash
from core.auth_settings import AuthUnavailable, utc_now
from core.chip_binding import valid_id
from core.db import get_database
from core.diagnostics import record_failure
from core.sdm_verification import InvalidReading, validate_reading
from core.tap_verification import (
    TapRateLimited, consume_rate_limit, lock_target, public_detail, rollback,
    saved_keys, state_reason, verify_tap,
)

blueprint = Blueprint('tap', __name__)


@blueprint.errorhandler(AuthUnavailable)
def unavailable(error):
    return jsonify(status='error', code='service_unavailable', message='触碰验证服务暂时不可用，请稍后重新触碰。', error_id=record_failure(error)), 503


@blueprint.errorhandler(TapRateLimited)
def limited(error):
    response = jsonify(status='error', code='rate_limited', message='请求较多，请稍后重新触碰。')
    response.headers['Retry-After'] = str(error.retry_after)
    return response, 429


@blueprint.before_request
def reject_query_parameters():
    if request.args:
        raise AuthRequestError(400, 'invalid_param', '此接口不接收链接查询参数。')


@blueprint.post('/api/tap/verify')
def verify():
    consume_rate_limit()
    if request.mimetype != 'application/json':
        raise AuthRequestError(400, 'invalid_param', '请使用JSON提交。')
    reading = request_json({'picc_data', 'cmac'})
    try:
        validate_reading(reading)
    except InvalidReading:
        raise AuthRequestError(400, 'invalid_param', '请提交完整的32位picc_data和16位cmac十六进制参数。') from None
    return jsonify(status='ok', data=verify_tap(reading))


def invalid_token():
    raise AuthRequestError(403, 'invalid_tap_token', '查看许可已失效，请重新触碰实物。')


def read_detail(item_id):
    digest = token_hash(request.headers.get('X-Tap-Token'))
    if digest is None:
        invalid_token()
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute('SELECT chip_id,item_id FROM tap_grant WHERE token_hash=%s', (digest,))
            initial = cursor.fetchone()
            if not initial or initial['item_id'] != item_id:
                invalid_token()
            item, chip = lock_target(cursor, initial['chip_id'], initial['item_id'])
            if not chip or not item or chip['item_id'] != item_id:
                invalid_token()
            cursor.execute('SELECT * FROM tap_grant WHERE token_hash=%s FOR UPDATE', (digest,))
            grant = cursor.fetchone()
            if not grant or grant['item_id'] != item_id or grant['chip_id'] != chip['id'] or grant['expires_at'] <= utc_now() or grant['consumed_at'] is not None or grant['allowed_action'] not in {'read', 'bind'}:
                invalid_token()
            if chip['project'] != 'fashion':
                raise AuthRequestError(409, 'project_mismatch', '查看许可不属于服装项目。')
            if state_reason(item, chip) or saved_keys(cursor, chip) is None:
                invalid_token()
            detail = public_detail(cursor, item, chip)
            if detail is None:
                invalid_token()
            profile, owner_bound = detail
            data = {'item_uid': item['item_uid'], 'profile': {name: value for name, value in profile.items() if name not in {'trace', 'story', 'channel'}},
                    'trace': profile['trace'], 'story': profile['story'], 'channel': profile['channel'], 'owner_bound': owner_bound}
        connection.commit()
        return data
    except Exception:
        rollback(connection)
        raise


@blueprint.get('/api/fashion/items/<int:item_id>/detail')
def fashion_detail(item_id):
    if not valid_id(item_id):
        raise AuthRequestError(400, 'invalid_param', '物品ID须为有效正整数。')
    return jsonify(status='ok', data=read_detail(item_id))


def init_tap(app):
    value = os.getenv('TAP_VERIFY_PER_MINUTE', '60')
    app.config.setdefault('TAP_VERIFY_PER_MINUTE', int(value) if len(value) <= 5 and value.isascii() and value.isdecimal() else None)
    app.register_blueprint(blueprint)
