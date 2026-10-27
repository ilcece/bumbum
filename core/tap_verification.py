"""公开触碰的频率限制、可信事件与原子凭证，不依赖管理员会话。"""

from datetime import timedelta
import hashlib
import json
import secrets

from flask import current_app
import pymysql

from core.auth_settings import AuthUnavailable, client_ip, fingerprint, utc_now
from core.chip_keys import checked_saved_keys, configured_key
from core.db import get_database
from core.sdm_verification import InvalidLayout, decode_reading, valid_mac

REASONS = {
    'decrypt_fail': '暂时无法确认本次芯片信息，请重新触碰；仍失败请联系支持。',
    'unknown_chip': '暂未找到可验证的芯片，请联系支持。',
    'cmac_fail': '暂时无法确认本次芯片信息，请重新触碰；仍失败请联系支持。',
    'not_ready': '芯片或物品尚未准备完成，请联系支持。',
    'disabled': '芯片或物品当前不可用，请联系支持。',
    'replay_suspect': '本次触碰链接已使用或较旧，请重新触碰实物。',
}


class TapRateLimited(Exception):
    """请求次数已达上限，携带到窗口结束的等待秒数。"""

    def __init__(self, retry_after):
        self.retry_after = retry_after


def rollback(connection):
    try:
        connection.rollback()
    except pymysql.MySQLError:
        pass


def consume_rate_limit():
    """独立事务计数，验签或业务失败不抵消次数，跨进程共用。"""
    maximum = current_app.config['TAP_VERIFY_PER_MINUTE']
    if type(maximum) is not int or not 1 <= maximum <= 10000:
        raise AuthUnavailable('触碰验证限流配置无效。')
    now = utc_now()
    start = now.replace(second=0, microsecond=0)
    bucket = fingerprint('tap-verify-rate', client_ip(), binary=True)
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 首次唯一键竞争也串行化；不使用先查后插。
            cursor.execute('INSERT INTO security_rate_limit(bucket_key,window_started_at,attempt_count) VALUES (%s,%s,0) ON DUPLICATE KEY UPDATE bucket_key=bucket_key', (bucket, start))
            cursor.execute('SELECT window_started_at,attempt_count FROM security_rate_limit WHERE bucket_key=%s FOR UPDATE', (bucket,))
            row = cursor.fetchone()
            count = row['attempt_count'] if row['window_started_at'] == start else 0
            limited = count >= maximum
            if not limited:
                cursor.execute('UPDATE security_rate_limit SET window_started_at=%s,attempt_count=%s,locked_until=NULL WHERE bucket_key=%s', (start, count + 1, bucket))
        connection.commit()
    except Exception:
        rollback(connection)
        raise
    if limited:
        raise TapRateLimited(max(1, 60 - now.second))


def log_event(cursor, result, chip=None, counter=None):
    """只有完整验签后才能记录可信关联，不保存原文、动态链接或凭证。"""
    cursor.execute(
        'INSERT INTO scan_log(chip_id,item_id,chip_uid,project_id,scan_counter,verify_result,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)',
        (chip['id'] if chip else None, chip['item_id'] if chip else None,
         chip['chip_uid'] if chip else None, chip['project_id'] if chip else None,
         counter if chip else None, result, utc_now()),
    )


def reject(cursor, reason, chip=None, counter=None):
    log_event(cursor, reason, chip, counter)
    return {'verified': False, 'reason': reason, 'message': REASONS[reason]}


def lock_target(cursor, chip_id, item_id):
    """始终先锁物品再锁芯片；定位之后发生换绑不能套用旧物品。"""
    item = None
    if item_id is not None:
        cursor.execute('SELECT * FROM item WHERE id=%s FOR UPDATE', (item_id,))
        item = cursor.fetchone()
    cursor.execute('SELECT * FROM chip WHERE id=%s FOR UPDATE', (chip_id,))
    chip = cursor.fetchone()
    if chip is None or chip['item_id'] != item_id:
        return None, None
    if item and item['project_id'] != chip['project_id']:
        raise AuthUnavailable('芯片与物品项目关联异常。')
    if chip['project_id'] is not None:
        cursor.execute('SELECT code FROM project WHERE id=%s', (chip['project_id'],))
        project = cursor.fetchone()
        if project is None or project['code'] not in {'fashion', 'jewelry'}:
            raise AuthUnavailable('芯片项目不支持。')
        chip['project'] = project['code']
    else:
        chip['project'] = None
    return item, chip


def saved_keys(cursor, chip):
    cursor.execute('SELECT * FROM chip_key WHERE chip_id=%s FOR UPDATE', (chip['id'],))
    stored = cursor.fetchone()
    return checked_saved_keys(stored, chip) if stored is not None else None


def state_reason(item, chip):
    if chip['chip_status'] in {'disabled', 'lost'} or (item and item['status'] in {'disabled', 'archived'}):
        return 'disabled'
    if not item or chip['chip_status'] != 'bound' or item['status'] != 'active' or chip['provisioned_at'] is None or chip['last_verified_counter'] is None:
        return 'not_ready'
    return None


def public_detail(cursor, item, chip):
    """公开字段白名单，绝不把资料表整行或购买订单序列化。"""
    project = chip['project']
    fields = ('name', 'description', 'material', 'care_instructions', 'size_chart', 'image_urls') if project == 'fashion' else ('name', 'description', 'material', 'meaning', 'image_urls')
    table = 'fashion_item_profile' if project == 'fashion' else 'jewelry_item_profile'
    cursor.execute('SELECT ' + ','.join(fields) + ' FROM ' + table + ' WHERE item_id=%s FOR SHARE', (item['id'],))
    profile = cursor.fetchone()
    if not profile or not isinstance(profile['name'], str) or not profile['name'].strip():
        return None
    for name in ('image_urls', 'size_chart'):
        if name in profile:
            profile[name] = json.loads(profile[name]) if isinstance(profile[name], (str, bytes)) else profile[name]
    if profile['image_urls'] is None:
        profile['image_urls'] = []
    if project == 'fashion':
        # 维护入口未开放的扩展内容先返回契约空值，不公开未知来源字段。
        profile.update(trace=[], story=None, channel=[])
    cursor.execute('SELECT id FROM ownership WHERE item_id=%s AND is_active=1 FOR SHARE', (item['id'],))
    return profile, cursor.fetchone() is not None


def issue_grant(cursor, item, chip, owner_bound, *, view=False, at=None):
    token = secrets.token_hex(32)
    now = at or utc_now()
    cursor.execute('INSERT INTO tap_grant(token_hash,chip_id,item_id,allowed_action,expires_at,created_at) VALUES (%s,%s,%s,%s,%s,%s)',
                   (hashlib.sha256(token.encode('ascii')).digest(), chip['id'], item['id'], 'view' if view else 'read' if owner_bound else 'bind', now + timedelta(hours=24) if view else now + timedelta(seconds=300), now))
    return token


def verify_in_transaction(cursor, reading, *, browser_view=False):
    if current_app.config['SDM_META_KEY_VERSION'] != 'v1':
        raise AuthUnavailable('不支持的全局密钥版本。')
    try:
        uid, counter = decode_reading(reading, configured_key('SDM_META_KEY_V1'))
    except InvalidLayout:
        return reject(cursor, 'decrypt_fail')
    cursor.execute('SELECT id,item_id FROM chip WHERE chip_uid=%s', (uid,))
    initial = cursor.fetchone()
    if not initial:
        return reject(cursor, 'unknown_chip')
    item, chip = lock_target(cursor, initial['id'], initial['item_id'])
    if not chip:
        return reject(cursor, 'not_ready')
    if chip['project'] is None:
        return reject(cursor, 'not_ready')
    keys = saved_keys(cursor, chip)
    if keys is None:
        return reject(cursor, 'not_ready')
    if not valid_mac(reading, bytes.fromhex(keys['K2']), uid, counter):
        return reject(cursor, 'cmac_fail')
    reason = state_reason(item, chip)
    if reason:
        return reject(cursor, reason, chip, counter)
    if counter == 0xFFFFFF:
        return reject(cursor, 'not_ready', chip, counter)
    if counter <= chip['last_verified_counter']:
        return reject(cursor, 'replay_suspect', chip, counter)
    detail = public_detail(cursor, item, chip)
    if detail is None:
        return reject(cursor, 'not_ready', chip, counter)
    profile, owner_bound = detail
    token = issue_grant(cursor, item, chip, owner_bound)
    cursor.execute('UPDATE chip SET last_verified_counter=%s WHERE id=%s', (counter, chip['id']))
    log_event(cursor, 'pass', chip, counter)
    result = {'verified': True, 'project': chip['project'], 'item_id': item['id'], 'item_uid': item['item_uid'],
            'owner_bound': owner_bound, 'tap_token': token, 'expires_in': 300, 'item_detail': profile}
    if browser_view and chip['project'] == 'fashion':
        from core.auth_settings import iso_time
        verified_at = utc_now()
        result['_view_cookie'] = issue_grant(cursor, item, chip, owner_bound, view=True, at=verified_at)
        result.update(view_path=f"/tap/items/{item['id']}", verified_at=iso_time(verified_at), retrieved_at=iso_time(verified_at))
    return result


def verify_tap(reading, *, browser_view=False):
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            result = verify_in_transaction(cursor, reading, browser_view=browser_view)
        connection.commit()
        return result
    except Exception:
        rollback(connection)
        raise
