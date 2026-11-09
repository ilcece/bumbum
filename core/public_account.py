"""手机号账户、一次性认领和持有资料；所有写入由服务端校验。"""

from contextlib import contextmanager
from datetime import timedelta
import hmac
import json
import os
import re
import secrets
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from flask import Blueprint, Response, current_app, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, request_json, token_hash
from core.auth_settings import client_ip, fingerprint, iso_time, secret_key, utc_now
from core.db import get_database
from core.tap_grants import public_settings


blueprint = Blueprint('public_account', __name__, url_prefix='/api/public')
COOKIE = 'bumbum_user'
COOKIE_PATH = '/api/public'
SESSION_SECONDS = 7 * 24 * 3600


def fail(status, code, message):
    raise AuthRequestError(status, code, message)


def row(cursor, sql, args=()):
    cursor.execute(sql, args)
    return cursor.fetchone()


@contextmanager
def transaction():
    connection = get_database()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise


@blueprint.before_request
def protect():
    write = request.method == 'POST'
    public_settings(require_origin=write)
    if request.args or (write and request.mimetype != 'application/json'):
        fail(400, 'invalid_param', '请使用页面提交有效资料。')


def ok(**data):
    return jsonify(status='ok', data=data)


def code_digest(purpose, identity, code):
    return hmac.digest(secret_key('SMS_CODE_HASH_KEY'), f'{purpose}|{identity}|{code}'.encode(), 'sha256')


def limited(purpose, identity, maximum, window=60):
    key = fingerprint('public-account:' + purpose, str(identity), binary=True)
    now = utc_now()
    with transaction() as c:
        c.execute('INSERT INTO security_rate_limit(bucket_key,window_started_at,attempt_count) VALUES (%s,%s,0) ON DUPLICATE KEY UPDATE bucket_key=bucket_key',(key,now))
        data = row(c,'SELECT window_started_at,attempt_count FROM security_rate_limit WHERE bucket_key=%s FOR UPDATE',(key,))
        start = data['window_started_at']
        count = data['attempt_count']
        if now - start >= timedelta(seconds=window):
            start, count = now, 0
        if count >= maximum:
            fail(429, 'rate_limited', '操作较频繁，请稍后再试。')
        c.execute('UPDATE security_rate_limit SET window_started_at=%s,attempt_count=%s WHERE bucket_key=%s',(start,count+1,key))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send_code(phone, code):
    sender = current_app.config.get('TEST_SMS_SENDER') if current_app.testing else None
    if sender:
        sender(phone, code)
        return
    url = current_app.config['SMS_GATEWAY_URL']
    token = current_app.config['SMS_GATEWAY_TOKEN']
    target = urlsplit(url)
    if target.scheme != 'https' or not target.hostname or target.username or target.password or target.query or target.fragment or not token:
        fail(503, 'sms_unavailable', '短信服务暂未就绪。')
    payload = json.dumps({'phone':phone, 'code':code, 'purpose':'bumbum_login'}).encode()
    req = Request(url, data=payload, headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    with build_opener(NoRedirect).open(req, timeout=5) as response:
        if response.status not in {200, 202, 204}:
            fail(503, 'sms_unavailable', '短信发送未完成，请稍后重试。')


@blueprint.post('/sms/send')
def sms_send():
    phone = request_json({'phone'}, max_bytes=1024)['phone']
    if not isinstance(phone,str) or not re.fullmatch(r'1[3-9][0-9]{9}',phone):
        fail(400,'invalid_param','请输入有效的中国大陆手机号。')
    limited('sms-ip', client_ip(), 6)
    limited('sms-phone', phone, 1)
    challenge = secrets.token_hex(16)
    code = f'{secrets.randbelow(1000000):06d}'
    digest = code_digest('sms',challenge,code)
    expires = utc_now()+timedelta(minutes=5)
    with transaction() as c:
        c.execute('INSERT INTO user_sms_challenge(phone,challenge_id,code_hash,expires_at) VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE challenge_id=VALUES(challenge_id),code_hash=VALUES(code_hash),expires_at=VALUES(expires_at),consumed_at=NULL,failed_attempts=0',(phone,challenge,digest,expires))
    try:
        send_code(phone,code)
    except Exception:
        with transaction() as c:
            c.execute('UPDATE user_sms_challenge SET consumed_at=%s WHERE challenge_id=%s',(utc_now(),challenge))
        fail(503,'sms_unavailable','短信发送未完成，请稍后重试。')
    return ok(challenge_id=challenge, retry_after=60)


def current_user(c, *, required=True, write=False):
    values = request.cookies.getlist(COOKIE)
    digest = token_hash(values[0]) if len(values)==1 else None
    session = None
    if digest:
        session = row(c,'SELECT u.id,u.phone FROM user_session s JOIN user u ON u.id=s.user_id WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>%s AND u.phone_verified_at IS NOT NULL'+(' FOR UPDATE' if write else ''),(digest,utc_now()))
    if not session and required:
        fail(401,'login_required','请先验证手机号并登录。')
    return session, digest


def account(user):
    phone = user['phone']
    return {'uid':user['id'],'phone':phone[:3]+'****'+phone[-4:]}


@blueprint.post('/sms/verify')
def sms_verify():
    payload = request_json({'challenge_id','code'}, max_bytes=1024)
    challenge, code = payload['challenge_id'], payload['code']
    if not isinstance(challenge,str) or not re.fullmatch(r'[0-9a-f]{32}',challenge) or not isinstance(code,str) or not re.fullmatch(r'[0-9]{6}',code):
        fail(400,'invalid_param','请填写有效的短信验证码。')
    limited('verify-ip',client_ip(),18)
    result = None
    token = secrets.token_hex(32)
    now = utc_now()
    with transaction() as c:
        challenge_row = row(c,'SELECT * FROM user_sms_challenge WHERE challenge_id=%s FOR UPDATE',(challenge,))
        if challenge_row and not challenge_row['consumed_at'] and challenge_row['expires_at']>now and challenge_row['failed_attempts']<5:
            if hmac.compare_digest(challenge_row['code_hash'],code_digest('sms',challenge,code)):
                phone=challenge_row['phone']
                c.execute('UPDATE user_sms_challenge SET consumed_at=%s WHERE challenge_id=%s',(now,challenge))
                c.execute('INSERT INTO user(phone,phone_verified_at) VALUES (%s,%s) ON DUPLICATE KEY UPDATE phone_verified_at=VALUES(phone_verified_at)',(phone,now))
                result=row(c,'SELECT id,phone FROM user WHERE phone=%s',(phone,))
                c.execute('INSERT INTO user_session(token_hash,user_id,expires_at) VALUES (%s,%s,%s)',(token_hash(token),result['id'],now+timedelta(seconds=SESSION_SECONDS)))
            else:
                c.execute('UPDATE user_sms_challenge SET failed_attempts=failed_attempts+1 WHERE challenge_id=%s',(challenge,))
    if not result:
        fail(400,'invalid_sms_code','验证码错误、已失效或尝试次数过多，请核对后重新发送。')
    response=ok(account=account(result))
    response.set_cookie(COOKIE,token,max_age=SESSION_SECONDS,httponly=True,secure=public_settings()['secure'],samesite='Lax',path=COOKIE_PATH)
    return response


@blueprint.get('/account/session')
def session():
    with transaction() as c:
        user,_=current_user(c,required=False)
    return ok(account=account(user) if user else None)


@blueprint.post('/account/logout')
def logout():
    request_json(set(), max_bytes=1024)
    with transaction() as c:
        _,digest=current_user(c,required=False)
        if digest:
            c.execute('UPDATE user_session SET revoked_at=%s WHERE token_hash=%s',(utc_now(),digest))
    response=ok(account=None)
    response.delete_cookie(COOKIE,path=COOKIE_PATH,secure=public_settings()['secure'],httponly=True,samesite='Lax')
    return response


def item_metadata(c,item_id,owner_bound=False):
    data=row(c,'''SELECT r.name AS issue_name,d.edition_number,r.total AS issue_total
                  FROM digital_item d JOIN product_issue r ON r.id=d.issue_id WHERE d.item_id=%s''',(item_id,))
    if not data:
        return {}
    c.execute('SELECT kind,rule_version FROM digital_item_right WHERE item_id=%s ORDER BY kind',(item_id,))
    data['rights']=c.fetchall()
    open_code=row(c,'SELECT expires_at FROM item_claim_code WHERE open_item_id=%s',(item_id,))
    data['claim_state']='claimed' if owner_bound else 'unavailable'
    if not owner_bound and open_code:
        data['claim_state']='available' if open_code['expires_at']>utc_now() else 'expired'
    return data


def record_claim_code(c, item_id, admin_id, reference):
    code=secrets.token_hex(8).upper()
    now=utc_now()
    c.execute('INSERT INTO item_claim_code(item_id,code_hash,issued_by,delivery_reference,issued_at,expires_at) VALUES (%s,%s,%s,%s,%s,%s)',(item_id,code_digest('claim',item_id,code),admin_id,reference,now,now+timedelta(days=30)))
    return {'id':item_id,'claim_code_id':c.lastrowid,'claim_code':code,'expires_at':iso_time(now+timedelta(days=30))}


def claimable_item(c, item_id):
    return row(c,'''SELECT i.id,w.chip_id FROM item i JOIN whole_item w ON w.current_item_id=i.id
                    JOIN chip ch ON ch.id=w.chip_id AND ch.item_id=i.id
                    WHERE i.id=%s AND i.status='active' AND w.physical_item_id IS NOT NULL
                    AND w.lost_at IS NULL AND w.loss_evidence IS NULL AND ch.chip_status='bound'
                    AND ch.provisioned_at IS NOT NULL AND ch.last_verified_counter IS NOT NULL FOR UPDATE''',(item_id,))


def issue_claim_code(c, item_id, admin_id, reference, *, reissue=False):
    row(c,'SELECT id FROM item WHERE id=%s FOR UPDATE',(item_id,))
    if not claimable_item(c,item_id):fail(409,'item_unavailable','请先完成实体安装、芯片核验及物品启用。')
    if row(c,'SELECT id FROM ownership WHERE active_item_id=%s FOR UPDATE',(item_id,)):
        fail(409,'already_claimed','物品已有持有人，请按持有争议流程处理。')
    issued=row(c,'SELECT id FROM item_claim_code WHERE item_id=%s ORDER BY id DESC LIMIT 1 FOR UPDATE',(item_id,))
    if bool(issued)!=reissue:
        fail(409,'claim_code_state','请按发放状态选择首次发放或核对后补发。')
    if reissue:
        c.execute('UPDATE item_claim_code SET revoked_at=%s WHERE open_item_id=%s',(utc_now(),item_id))
    return record_claim_code(c,item_id,admin_id,reference)


@blueprint.get('/items/<int:item_id>/claim-status')
def claim_status(item_id):
    with transaction() as c:
        user,_=current_user(c)
        owner=row(c,'SELECT user_id FROM ownership WHERE active_item_id=%s',(item_id,))
        state='mine' if owner and owner['user_id']==user['id'] else 'claimed' if owner else 'pending'
    return ok(state=state)


@blueprint.post('/items/<int:item_id>/claim')
def claim(item_id):
    payload=request_json({'tap_token','claim_code'},max_bytes=2048)
    code=payload['claim_code']
    if not isinstance(code,str) or len(code)>24:
        fail(400,'invalid_claim_code','请核对交付认领码。')
    code=code.replace('-','').replace(' ','').upper()
    if not re.fullmatch(r'[0-9A-F]{16}',code):
        fail(400,'invalid_claim_code','请核对交付认领码。')
    limited('claim-ip',client_ip(),20)
    with transaction() as c:
        user,_=current_user(c)
    limited('claim-user',user['id'],8)
    with transaction() as c:
        if not row(c,'SELECT id FROM item WHERE id=%s FOR UPDATE',(item_id,)):
            fail(404,'not_found','物品不存在。')
        user,_=current_user(c,write=True)
        owner=row(c,'SELECT user_id FROM ownership WHERE active_item_id=%s FOR UPDATE',(item_id,))
        if owner:
            if owner['user_id']==user['id']:return ok(state='mine',item_id=item_id)
            fail(409,'already_claimed','这件物品已认领，如有疑问请联系 BUMBUM。')
        item=claimable_item(c,item_id)
        grant=row(c,"SELECT id FROM tap_grant WHERE token_hash=%s AND item_id=%s AND chip_id=%s AND allowed_action='bind' AND consumed_at IS NULL AND expires_at>%s FOR UPDATE",(token_hash(payload['tap_token']),item_id,item['chip_id'],utc_now())) if item else None
        if not grant:fail(403,'retap_required','请重新碰一下物品，再继续认领。')
        from core.test_batches import same_source
        same_source(c,'item',item_id,'user',user['id'])
        issued=row(c,'SELECT id,code_hash,expires_at FROM item_claim_code WHERE open_item_id=%s FOR UPDATE',(item_id,))
        if not issued or issued['expires_at']<=utc_now():fail(409,'claim_code_unavailable','请联系 BUMBUM 核对交付后补发。')
        if not hmac.compare_digest(issued['code_hash'],code_digest('claim',item_id,code)):
            fail(400,'invalid_claim_code','认领码与这件物品不匹配，请核对交付时收到的认领码。')
        now=utc_now()
        c.execute("INSERT INTO ownership(item_id,user_id,bind_source,bound_at) VALUES (%s,%s,'user_self',%s)",(item_id,user['id'],now))
        c.execute("INSERT INTO ownership_history(item_id,to_user_id,action,occurred_at) VALUES (%s,%s,'bind',%s)",(item_id,user['id'],now))
        c.execute('UPDATE item_claim_code SET consumed_at=%s WHERE id=%s',(now,issued['id']))
        c.execute('UPDATE tap_grant SET consumed_at=%s WHERE id=%s',(now,grant['id']))
    return ok(state='mine',item_id=item_id)


def owned_query(c,user_id,item_id=None):
    args=(user_id,) if item_id is None else (user_id,item_id)
    c.execute('''SELECT i.id AS item_id,i.item_uid,o.bound_at,p.code AS project,s.name,s.description,s.material,
                 s.care_instructions,s.image_urls,r.name AS issue_name,r.total AS issue_total,d.edition_number,
                 d.quota_year,d.quota_used,d.quota_review,w.spec,w.generation
                 FROM ownership o JOIN item i ON i.id=o.item_id JOIN project p ON p.id=i.project_id
                 LEFT JOIN digital_item d ON d.item_id=i.id LEFT JOIN product_issue r ON r.id=d.issue_id
                 LEFT JOIN product_style s ON s.id=r.style_id LEFT JOIN whole_item w ON w.current_item_id=i.id
                 WHERE o.user_id=%s AND o.is_active=1'''+(' AND i.id=%s' if item_id is not None else ' ORDER BY o.bound_at DESC,o.id DESC'),args)
    return c.fetchall()


def owned_view(c,data):
    item_id=data['item_id']
    images=json.loads(data['image_urls']) if data['image_urls'] else []
    public_images=[]
    for image in images:
        match=re.fullmatch(r'/api/admin/catalog/styles/[1-9][0-9]*/images/([a-f0-9]{32})',image)
        if match:public_images.append(f'/api/public/me/items/{item_id}/images/{match[1]}')
        elif image.startswith(('https://','http://')):public_images.append(image)
    data.update(item_metadata(c,item_id,True),image_urls=public_images,bound_at=iso_time(data['bound_at']))
    year=(utc_now()+timedelta(hours=8)).year
    if data['quota_year'] and data['quota_year']<year and not data['quota_review']:
        data.update(quota_year=year,quota_used=0)
    return data


@blueprint.get('/me/items')
def my_items():
    with transaction() as c:
        user,_=current_user(c)
        result=[owned_view(c,item) for item in owned_query(c,user['id'])]
    return ok(items=result)


@blueprint.get('/me/items/<int:item_id>')
def my_item(item_id):
    with transaction() as c:
        user,_=current_user(c)
        items=owned_query(c,user['id'],item_id)
        if not items:fail(404,'not_found','未找到你当前持有的该物品。')
        result=owned_view(c,items[0])
    return ok(item=result)


@blueprint.get('/me/items/<int:item_id>/images/<asset_id>')
def my_image(item_id,asset_id):
    from core.admin_catalog import shared_image
    if not re.fullmatch(r'[a-f0-9]{32}',asset_id):fail(404,'not_found','图片不存在。')
    with transaction() as c:
        user,_=current_user(c)
        if not owned_query(c,user['id'],item_id):fail(404,'not_found','图片不存在。')
        image=shared_image(c,item_id,asset_id)
    return Response(image['content'],mimetype='image/webp')


def init_public_account(app):
    for name in ('SMS_CODE_HASH_KEY','SMS_GATEWAY_URL','SMS_GATEWAY_TOKEN'):
        app.config.setdefault(name,os.getenv(name,''))
    app.register_blueprint(blueprint)
