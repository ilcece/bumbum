"""用户触碰路由及按物品核对的临时查看凭证，不提供认领接口。"""

import os
from datetime import timedelta
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, request_json, token_hash
from core.auth_settings import AuthUnavailable, iso_time, utc_now
from core.chip_binding import valid_id
from core.db import get_database, view_grant_schema
from core.diagnostics import record_failure
from core.sdm_verification import InvalidReading, validate_reading
from core.tap_verification import (
    TapRateLimited, consume_rate_limit, lock_target, public_detail, rollback,
    saved_keys, state_reason, verify_tap,
)

blueprint = Blueprint('tap', __name__)


@blueprint.errorhandler(AuthUnavailable)
def unavailable(error):
    message = '资料服务暂时不可用，请稍后重试更新。' if request.endpoint == 'tap.item_view' else '触碰验证服务暂时不可用，请稍后重新触碰。'
    return jsonify(status='error', code='service_unavailable', message=message, error_id=record_failure(error)), 503


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
    reading = request_json({'picc_data', 'cmac'}, {'browser_view'})
    browser_view = reading.pop('browser_view', False)
    if type(browser_view) is not bool:
        raise AuthRequestError(400, 'invalid_param', 'browser_view须为布尔值。')
    if browser_view:
        public_settings(require_origin=True)
        require_view_schema()
    try:
        validate_reading(reading)
    except InvalidReading:
        raise AuthRequestError(400, 'invalid_param', '请提交完整的32位picc_data和16位cmac十六进制参数。') from None
    data = verify_tap(reading, browser_view=browser_view)
    cookie = data.pop('_view_cookie', None)
    response = jsonify(status='ok', data=data)
    if cookie is not None:
        response.set_cookie('bumbum_item_view', cookie, path=f"/api/tap/items/{data['item_id']}",
                            httponly=True, secure=public_settings()['secure'], samesite='Strict')
    return response


def invalid_token(view=False):
    raise AuthRequestError(403, 'invalid_view_session' if view else 'invalid_tap_token', '查看资格已失效，请重新触碰实物。')


def read_detail(item_id, *, view=False):
    if view:
        public_settings()
        require_view_schema()
        if request.content_length or request.headers.get('X-Tap-Token') is not None:
            raise AuthRequestError(400, 'invalid_param', '此查看入口只接受对应物品的Cookie，不接收正文或临时凭证头。')
        cookies = request.cookies.getlist('bumbum_item_view')
        value = cookies[0] if len(cookies) == 1 else None
    else:
        value = request.headers.get('X-Tap-Token')
    digest = token_hash(value)
    if digest is None:
        invalid_token(view)
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute('SELECT chip_id,item_id FROM tap_grant WHERE token_hash=%s', (digest,))
            initial = cursor.fetchone()
            if not initial or initial['item_id'] != item_id:
                invalid_token(view)
            item, chip = lock_target(cursor, initial['chip_id'], initial['item_id'])
            if not chip or not item or chip['item_id'] != item_id:
                if view:
                    raise AuthRequestError(409, 'view_unavailable', '该物品当前暂不可查看。')
                invalid_token(view)
            cursor.execute('SELECT * FROM tap_grant WHERE token_hash=%s FOR UPDATE', (digest,))
            grant = cursor.fetchone()
            if not grant or grant['item_id'] != item_id or grant['chip_id'] != chip['id'] or grant['expires_at'] <= utc_now() or grant['consumed_at'] is not None or grant['allowed_action'] not in ({'view'} if view else {'read', 'bind'}):
                invalid_token(view)
            if chip['project'] != 'fashion':
                raise AuthRequestError(409, 'project_mismatch', '查看许可不属于服装项目。')
            if state_reason(item, chip) or saved_keys(cursor, chip) is None:
                if view:
                    raise AuthRequestError(409, 'view_unavailable', '该物品当前暂不可查看。')
                invalid_token(view)
            detail = public_detail(cursor, item, chip)
            if detail is None:
                if view:
                    raise AuthRequestError(409, 'view_unavailable', '该物品当前暂不可查看。')
                invalid_token(view)
            profile, owner_bound = detail
            data = {'item_uid': item['item_uid'], 'profile': {name: value for name, value in profile.items() if name not in {'trace', 'story', 'channel'}},
                    'trace': profile['trace'], 'story': profile['story'], 'channel': profile['channel'], 'owner_bound': owner_bound}
            if view:
                now = utc_now()
                data = {'project': 'fashion', 'item_id': item_id, 'item_uid': item['item_uid'],
                        'verified_at': iso_time(grant['created_at']), 'retrieved_at': iso_time(now),
                        'profile': {name: profile[name] for name in ('name','description','material','care_instructions','image_urls')}}
                cursor.execute('UPDATE tap_grant SET expires_at=%s WHERE id=%s', (now + timedelta(hours=24), grant['id']))
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


@blueprint.get('/api/tap/items/<int:item_id>/view')
def item_view(item_id):
    if not valid_id(item_id):
        raise AuthRequestError(400, 'invalid_param', '物品ID须为有效正整数。')
    return jsonify(status='ok', data=read_detail(item_id, view=True))


def public_settings(*, require_origin=False):
    """公开网页来源独立于管理端，生产只允许明确HTTPS来源。"""
    origin = current_app.config['PUBLIC_ORIGIN']
    try:
        if current_app.config["APP_ENV"] not in {"development", "production"} or origin == current_app.config["ADMIN_ORIGIN"]:
            raise ValueError
        parts = urlsplit(origin)
        parts.port
        local = parts.hostname in {'127.0.0.1', 'localhost', '::1'}
        if not parts.netloc or parts.path or parts.query or parts.fragment or parts.username or parts.password or parts.scheme not in {'https','http'}:
            raise ValueError
        if parts.scheme == 'http' and not (local and current_app.config['APP_ENV'] == 'development'):
            raise ValueError
        if current_app.config['APP_ENV'] == 'production' and local:
            raise ValueError
    except (TypeError, ValueError):
        raise AuthUnavailable('用户网页来源配置不合法。') from None
    supplied = request.headers.get('Origin')
    if (require_origin and supplied != origin) or (supplied is not None and supplied != origin) or request.headers.get('Sec-Fetch-Site', 'none') not in {'none','same-origin'}:
        raise AuthRequestError(403, 'forbidden', '请从本项目用户页面读取资料。')
    return {'secure': parts.scheme == 'https'}


def require_view_schema():
    with get_database().cursor() as cursor:
        if view_grant_schema(cursor) != 'ready':
            raise AuthUnavailable('请先按运行手册升级持续查看资格。')


def init_tap(app):
    value = os.getenv('TAP_VERIFY_PER_MINUTE', '60')
    app.config.setdefault('TAP_VERIFY_PER_MINUTE', int(value) if len(value) <= 5 and value.isascii() and value.isdecimal() else None)
    app.config.setdefault('PUBLIC_ORIGIN', os.getenv('PUBLIC_ORIGIN', 'http://127.0.0.1:5175' if app.config['APP_ENV'] == 'development' else 'https://nfc.bumbum.cc'))
    app.register_blueprint(blueprint)
