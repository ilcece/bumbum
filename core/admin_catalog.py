"""数字档案管理：真实分页、独立发行、整套物品事务与可核对写回执。"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re

from flask import Blueprint, Response, current_app, g, jsonify, request
import pymysql

from core.admin_auth import AuthRequestError, lock_admin_session, request_json
from core.admin_queries import check_parameters, consistent_read, contains, pagination, positive_integer, invalid
from core.admin_items import normalized_profile
from core.auth_settings import client_ip, fingerprint, iso_time, utc_now
from core.chip_binding import valid_id
from core.chip_registry import normalize_uid, save_chip
from core.db import get_database

from core.test_batches import select_source,filter_source,source,mark,same_source,lock_batch,require_test_environment

blueprint = Blueprint('admin_catalog', __name__, url_prefix='/api/admin/catalog')
KINDS = {'periodic', 'loss', 'resale'}


def fail(message, status=409, code='invalid_state'):
    raise AuthRequestError(status, code, message)


def text(data, name, limit, *, required=False):
    value = data.get(name)
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        invalid(f'{name}须为最多{limit}字符的文字。')
    return value.strip() or None


def integer(data, name, *, optional=False):
    value = data.get(name)
    if optional and value is None:
        return None
    if not valid_id(value) or value > 2147483647:
        invalid(f'{name}须为有效正整数。')
    return value


def boolean(data, name, default=False):
    value = data.get(name, default)
    if type(value) is not bool:
        invalid(f'{name}须为布尔值。')
    return value


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


def view(row):
    if row is None:
        fail('记录不存在，请重新查询。', 404, 'not_found')
    return {k: iso_time(v) if isinstance(v, datetime) else decoded(v) if k in {'specs', 'image_urls', 'rights', 'detail', 'result', 'manifest'} else v for k, v in row.items()}


def row(cursor, sql, args=()):
    cursor.execute(sql, args)
    return cursor.fetchone()


def locked(cursor, table, ident):
    if table not in {'product_style', 'product_issue', 'item', 'chip', 'item_handover'}:
        raise ValueError('不支持的锁目标')
    return view(row(cursor, f'SELECT * FROM {table} WHERE id=%s FOR UPDATE', (ident,)))


def audit(cursor, action, target, detail):
    cursor.execute('INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail,ip_hash) VALUES (%s,%s,%s,%s,%s,%s)',
                   (g.admin_session['admin_id'], 'catalog.'+action, 'digital_catalog', str(target), json.dumps(detail, ensure_ascii=False), fingerprint('ip', client_ip())))


def field_set(data, required=(), optional=()):
    if set(data)-set(required)-set(optional) or set(required)-set(data):
        invalid('字段不符合当前操作约定。')


def now():
    return utc_now()


def sale_time(data):
    """解析有依据的成交时间；操作审计仍独立记录后台处理时刻。"""
    if data.get('first_sold_at') is None:return now()
    try:
        value=datetime.fromisoformat(data['first_sold_at'].replace('Z','+00:00'))
        if value.tzinfo is None or value.year<1000:raise ValueError()
        value=value.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError,TypeError,AttributeError,OverflowError):invalid('首次售出时间须为数据库支持范围内、带时区的有效时间。')
    if value>now():invalid('首次售出时间不能晚于当前时间。')
    return value


def project_id(cursor, project):
    if not isinstance(project,str) or project not in {'fashion', 'jewelry'}:
        invalid('类别仅支持fashion或jewelry。')
    return row(cursor, 'SELECT id FROM project WHERE code=%s', (project,))['id']


def current(cursor, item_id, *, required=True):
    found = row(cursor, 'SELECT * FROM whole_item WHERE item_id=%s AND ended_at IS NULL FOR UPDATE', (item_id,))
    if not found and required:
        fail('当前整套物品缺失，请核对历史后补齐。')
    return found


def digital(cursor, item_id):
    cursor.execute('INSERT INTO digital_item(item_id) VALUES (%s) ON DUPLICATE KEY UPDATE item_id=item_id', (item_id,))
    return row(cursor, 'SELECT * FROM digital_item WHERE item_id=%s FOR UPDATE', (item_id,))


def revoke(cursor, item_id):
    # 永久撤销现有短许可与持续查看，后续恢复也不能复活旧资格。
    cursor.execute('UPDATE tap_grant SET consumed_at=COALESCE(consumed_at,%s) WHERE item_id=%s', (now(), item_id))


def list_page(cursor, select, joined, conditions, values, *, order='id DESC', select_values=()):
    page, size = positive_integer('page', 1, 2147483647), positive_integer('page_size', 10, 100)
    where = ' WHERE '+ ' AND '.join(conditions) if conditions else ''
    total = row(cursor, 'SELECT COUNT(*) AS total '+joined+where, values)['total']
    paging = pagination(total, page, size)
    cursor.execute(select+' '+joined+where+' ORDER BY '+order+' LIMIT %s OFFSET %s', (*select_values,*values, size, (paging['page']-1)*size))
    return {'items':[view(x) for x in cursor.fetchall()], **paging}


STYLE_SELECT = 'SELECT '+select_source('style','s')+',s.*,p.code AS project,(SELECT COUNT(*) FROM product_issue r WHERE r.style_id=s.id) AS issue_count,(SELECT COUNT(*) FROM digital_item d JOIN product_issue r ON r.id=d.issue_id WHERE r.style_id=s.id) AS item_count,(SELECT COUNT(*) FROM digital_item d JOIN product_issue r ON r.id=d.issue_id JOIN item i ON i.id=d.item_id WHERE r.style_id=s.id AND i.status=\'active\') AS active_item_count'
STYLE_JOIN = 'FROM product_style s JOIN project p ON p.id=s.project_id'
ISSUE_SELECT = 'SELECT '+select_source('issue','r')+',r.*,s.name AS style_name,s.code AS style_code,p.code AS project,(SELECT COUNT(*) FROM digital_item d WHERE d.issue_id=r.id) AS item_count'
ISSUE_JOIN = 'FROM product_issue r JOIN product_style s ON s.id=r.style_id JOIN project p ON p.id=s.project_id'
ITEM_SELECT = 'SELECT '+select_source('item','i')+''',i.*,p.code AS project,d.issue_id,d.edition_number,d.sold,d.first_sold_at,d.sale_evidence,d.is_validation,d.quota_year,d.quota_used,d.quota_review,
 r.name AS issue_name,r.mode AS issue_mode,r.total AS issue_total,r.style_id,s.name,s.material,s.image_urls,
 (SELECT nickname FROM user WHERE id=o.user_id) AS owner_name,w.id AS whole_id,w.generation,w.spec,w.lost_at,w.loss_evidence,c.id AS chip_id,c.chip_uid,c.chip_status,c.provisioned_at,
 (k.chip_id IS NOT NULL) AS keys_generated,o.user_id AS owner_id'''
ITEM_JOIN = '''FROM item i JOIN project p ON p.id=i.project_id LEFT JOIN digital_item d ON d.item_id=i.id
 LEFT JOIN product_issue r ON r.id=d.issue_id LEFT JOIN product_style s ON s.id=r.style_id
 LEFT JOIN whole_item w ON w.current_item_id=i.id LEFT JOIN chip c ON c.item_id=i.id LEFT JOIN chip_key k ON k.chip_id=c.id
 LEFT JOIN ownership o ON o.active_item_id=i.id'''
CHIP_SELECT = 'SELECT '+select_source('chip','c')+''',c.*,p.code AS project,i.item_uid,(k.chip_id IS NOT NULL) AS keys_generated,
 COALESCE(v.is_validation,0) AS is_validation,w.id AS candidate_id,w.item_id AS candidate_item_id'''
CHIP_JOIN = '''FROM chip c LEFT JOIN project p ON p.id=c.project_id LEFT JOIN item i ON i.id=c.item_id
 LEFT JOIN chip_key k ON k.chip_id=c.id LEFT JOIN chip_validation v ON v.chip_id=c.id
 LEFT JOIN item_handover w ON w.pending_chip_id=c.id'''


@blueprint.get('/<resource>')
def listing(resource):
    allowed={'styles':{'project'},'issues':{'project','style_id','status','mode'},'items':{'project','status','issue_id','is_validation','sold','whole_status','style_id','owner','bindable'},'chips':{'project','status','is_validation','available','configured','registration_source','compatible_project'},'users':{'exclude_id'},'audit':set()}
    if resource not in allowed:fail('未知查询资源。',404,'not_found')
    check_parameters({'page','page_size','keyword','data_scope','test_batch_id'}|allowed[resource])
    keyword = request.args.get('keyword','').strip()
    if len(keyword)>128:
        invalid('关键词最长128字符。')
    conditions, values, select_values = [], [], []
    if resource == 'styles':
        select, joined, order = STYLE_SELECT, STYLE_JOIN, 's.id DESC'
        if keyword:
            conditions.append('(s.name LIKE %s ESCAPE \'!\' OR s.code LIKE %s ESCAPE \'!\')');values.extend([contains(keyword)]*2)
    elif resource == 'issues':
        select, joined, order = ISSUE_SELECT, ISSUE_JOIN, 'r.id DESC'
        if keyword:
            conditions.append('(r.name LIKE %s ESCAPE \'!\' OR s.name LIKE %s ESCAPE \'!\' OR r.series LIKE %s ESCAPE \'!\' OR s.code LIKE %s ESCAPE \'!\')');values.extend([contains(keyword)]*4)
        if request.args.get('style_id'):
            conditions.append('r.style_id=%s');values.append(positive_integer('style_id',1,2147483647))
        if request.args.get('status'):
            if request.args['status'] not in {'draft','confirmed'}:invalid('发行状态只支持draft或confirmed。')
            conditions.append('r.confirmed_at IS '+('NOT NULL' if request.args['status']=='confirmed' else 'NULL'))
        if request.args.get('mode'):
            if request.args['mode'] not in {'fixed','period','unlimited'}:invalid('发行方式不支持。')
            conditions.append('r.mode=%s');values.append(request.args['mode'])
    elif resource == 'items':
        select, joined, order = ITEM_SELECT, ITEM_JOIN, 'i.id DESC'
        if keyword:
            conditions.append('(i.item_uid LIKE %s ESCAPE \'!\' OR s.name LIKE %s ESCAPE \'!\' OR c.chip_uid LIKE %s ESCAPE \'!\')');values.extend([contains(keyword)]*3)
        for name, column in [('status','i.status'),('issue_id','d.issue_id'),('style_id','r.style_id')]:
            if request.args.get(name):
                if name=='status' and request.args[name] not in {'draft','active','disabled','archived'}:invalid('档案状态不支持。')
                conditions.append(column+'=%s');values.append(positive_integer(name,1,2147483647) if name in {'issue_id','style_id'} else request.args[name])
        for name,column in [('is_validation','d.is_validation'),('sold','d.sold')]:
            if name in request.args:
                if request.args[name] not in {'true','false'}: invalid('布尔筛选须为true或false。')
                conditions.append('COALESCE('+column+',0)=%s');values.append(request.args[name]=='true')
        if 'bindable' in request.args:
            if request.args['bindable']!='true':invalid('bindable仅接受true。')
            conditions.extend(["i.status!='archived'",'d.issue_id IS NOT NULL','w.id IS NULL','c.id IS NULL'])
        state=request.args.get('whole_status')
        if state:
            if state not in {'lost','normal','missing'}: invalid('整套物品状态不支持。')
            conditions.append({'lost':"w.id IS NOT NULL AND (w.lost_at IS NOT NULL OR w.loss_evidence IS NOT NULL)",'normal':"w.id IS NOT NULL AND w.lost_at IS NULL AND w.loss_evidence IS NULL",'missing':'w.id IS NULL'}[state])
        if request.args.get('owner'):
            if request.args['owner'] not in {'yes','no'}:invalid('持有筛选须为yes或no。')
            conditions.append('o.user_id IS '+('NOT NULL' if request.args['owner']=='yes' else 'NULL'))
    elif resource == 'chips':
        select, joined, order = CHIP_SELECT, CHIP_JOIN, 'c.id DESC'
        if keyword:
            conditions.append('(c.chip_uid LIKE %s ESCAPE \'!\' OR i.item_uid LIKE %s ESCAPE \'!\' OR c.batch_no LIKE %s ESCAPE \'!\')');values.extend([contains(keyword)]*3)
        if request.args.get('status'):
            if request.args['status'] not in {'pending','bound','disabled','lost','retired'}: invalid('芯片状态不支持。')
            conditions.append('c.chip_status=%s');values.append(request.args['status'])
        if request.args.get('compatible_project'):
            if request.args['compatible_project'] not in {'fashion','jewelry'}:invalid('类别不支持。')
            conditions.append('(p.code=%s OR c.project_id IS NULL)');values.append(request.args['compatible_project'])
        if 'available' in request.args:
            if request.args['available']!='true': invalid('available仅接受true。')
            conditions.extend(["c.chip_status='pending'",'c.item_id IS NULL','w.id IS NULL'])
        if 'is_validation' in request.args:
            if request.args['is_validation'] not in {'true','false'}: invalid('验证筛选须为布尔值。')
            conditions.append('COALESCE(v.is_validation,0)=%s');values.append(request.args['is_validation']=='true')
        if request.args.get('configured'):
            if request.args['configured'] not in {'yes','no'}:invalid('配置筛选须为yes或no。')
            conditions.append('c.provisioned_at IS '+('NOT NULL' if request.args['configured']=='yes' else 'NULL'))
        if request.args.get('registration_source'):
            if request.args['registration_source'] not in {'manual','nfc_cool','unknown'}:invalid('登记来源不支持。')
            conditions.append('c.registration_source=%s');values.append(request.args['registration_source'])
    elif resource == 'users':
        if request.args.get('exclude_id'):
            conditions.append('u.id<>%s');values.append(positive_integer('exclude_id',1,2147483647))
        select,joined,order='SELECT '+select_source('user','u')+',u.id,u.nickname,CONCAT(LEFT(u.phone,3),\'****\',RIGHT(u.phone,4)) AS phone,(SELECT COUNT(*) FROM ownership o WHERE o.user_id=u.id AND o.is_active=1) AS held_items','FROM user u','u.id DESC'
        held_filter,held_args=filter_source('item','o.item_id',request.args.get('data_scope','business'),request.args.get('test_batch_id'))
        select=select.replace('o.is_active=1)', 'o.is_active=1 AND '+held_filter+')');select_values=held_args
        if keyword:
            conditions.append('(u.nickname LIKE %s ESCAPE \'!\' OR CAST(u.id AS CHAR)=%s)');values.extend([contains(keyword),keyword])
    elif resource == 'audit':
        select,joined,order='SELECT a.id,a.action,a.target_type,a.target_id,a.detail,a.created_at,u.username','FROM admin_audit a LEFT JOIN admin_user u ON u.id=a.admin_id','a.id DESC'
        if keyword:
            conditions.append('(a.action LIKE %s ESCAPE \'!\' OR a.target_id=%s)');values.extend([contains(keyword),keyword])
    else:
        fail('未知查询资源。',404,'not_found')
    if resource!='audit':
        kind,alias={'styles':('style','s'),'issues':('issue','r'),'items':('item','i'),'chips':('chip','c'),'users':('user','u')}[resource]
        clause,args=filter_source(kind,alias+'.id',request.args.get('data_scope','business'),request.args.get('test_batch_id'))
        conditions.append(clause);values.extend(args)
    if request.args.get('project'):
        if resource not in {'styles','issues','items','chips'}: invalid('此资源不支持类别。')
        if request.args['project'] not in {'fashion','jewelry','unassigned'}: invalid('类别不支持。')
        if request.args['project']=='unassigned':
            if resource!='chips':invalid('只有芯片可暂不分配类别。')
            conditions.append('p.id IS NULL')
        else: conditions.append('p.code=%s');values.append(request.args['project'])
    with consistent_read() as cursor:
        result=list_page(cursor,select,joined,conditions,values,order=order,select_values=select_values)
    return jsonify(status='ok',data=result)


@blueprint.get('/<resource>/<int:ident>')
def detail(resource,ident):
    check_parameters(set())
    if not valid_id(ident) or ident>2147483647:invalid('记录ID超出当前页面可处理范围。')
    with consistent_read() as c:
        if resource=='styles': result=view(row(c,STYLE_SELECT+' '+STYLE_JOIN+' WHERE s.id=%s',(ident,)))
        elif resource=='issues':
            result=view(row(c,ISSUE_SELECT+' '+ISSUE_JOIN+' WHERE r.id=%s',(ident,)))
            # 建议不预占身份或序号，事务提交仍检查唯一性与数量。
            c.execute('SELECT edition_number FROM digital_item WHERE issue_id=%s AND edition_number IS NOT NULL',(ident,))
            occupied={x['edition_number'] for x in c.fetchall()};number=1
            while number in occupied:number+=1
            result['suggested_edition_number']=number
            prefix=('FASH' if result['project']=='fashion' else 'JEW')+'-'+str((now()+timedelta(hours=8)).year)+'-'
            c.execute('SELECT item_uid FROM item WHERE item_uid LIKE %s',(prefix+'%',))
            used={x['item_uid'].casefold() for x in c.fetchall()};candidate=1
            while (prefix+str(candidate).zfill(6)).casefold() in used:candidate+=1
            while row(c,'SELECT id FROM item WHERE item_uid=%s',(prefix+str(candidate).zfill(6),)):candidate+=1
            result['suggested_item_uid']=prefix+str(candidate).zfill(6)
        elif resource=='chips': result=view(row(c,CHIP_SELECT+' '+CHIP_JOIN+' WHERE c.id=%s',(ident,)))
        elif resource=='items':
            result=view(row(c,ITEM_SELECT+' '+ITEM_JOIN+' WHERE i.id=%s',(ident,)))
            for key,sql in [('wholes','SELECT w.*,c.chip_uid,c.chip_status FROM whole_item w JOIN chip c ON c.id=w.chip_id WHERE w.item_id=%s ORDER BY w.generation DESC'),('handovers','SELECT w.*,c.chip_uid,c.provisioned_at,(SELECT nickname FROM user WHERE id=w.owner_id) AS owner_name,(SELECT nickname FROM user WHERE id=w.recipient_id) AS recipient_name FROM item_handover w JOIN chip c ON c.id=w.chip_id WHERE w.item_id=%s ORDER BY w.id DESC'),('owners','SELECT o.id,o.user_id,o.bound_at,o.unbound_at,o.is_active,u.nickname FROM ownership o JOIN user u ON u.id=o.user_id WHERE o.item_id=%s ORDER BY o.id DESC')]:
                c.execute(sql,(ident,));result[key]=[view(x) for x in c.fetchall()]
            if result['style_id']: result['style']=view(row(c,STYLE_SELECT+' '+STYLE_JOIN+' WHERE s.id=%s',(result['style_id'],)))
            if result['issue_id']: result['issue']=view(row(c,ISSUE_SELECT+' '+ISSUE_JOIN+' WHERE r.id=%s',(result['issue_id'],)))
            if not result.get('style'):
                table='fashion_item_profile' if result['project']=='fashion' else 'jewelry_item_profile'
                legacy=row(c,f'SELECT * FROM {table} WHERE item_id=%s',(ident,))
                if legacy:
                    from core.media_assets import map_profile_images
                    legacy=view(legacy);map_profile_images(c,{ident:legacy},context='admin')
                result['legacy_profile']=legacy
        else: fail('未知查询资源。',404,'not_found')
    return jsonify(status='ok',data=result)


def style_save(c,p):
    field_set(p,{'code','project','name','specs','image_urls'}, {'id','description','material','care_instructions','shared_confirmed','test_batch_id'})
    ident=integer(p,'id',optional=True);old=locked(c,'product_style',ident) if ident else None
    if old and p.get('test_batch_id') is not None and integer(p,'test_batch_id')!=source(c,'style',ident):fail('测试来源固定，不能改写。')
    lock_batch(c,source(c,'style',ident))
    pid=project_id(c,p['project']);code=text(p,'code',64,required=True)
    profile=normalized_profile({**{k:p[k] for k in ('name','description','material','care_instructions') if k in p},'image_urls':[]})
    images=p['image_urls']
    if not isinstance(images,list) or len(images)>20:invalid('最多20张共用图片。')
    for url in images:
        match=re.fullmatch(r'/api/admin/catalog/styles/([1-9][0-9]*)/images/([a-f0-9]{32})',url) if isinstance(url,str) else None
        if not match or not ident or int(match[1])!=ident or not row(c,'SELECT asset_id FROM style_image WHERE style_id=%s AND asset_id=%s AND (expires_at IS NULL OR expires_at>%s)',(ident,match[2],now())):invalid('请选择本款式已上传的真实图片。')
    profile['image_urls']=images
    specs=p['specs']
    if not isinstance(specs,list) or len(specs)>100 or any(not isinstance(x,str) or not x.strip() or len(x)>128 for x in specs): invalid('规格须为最多100项、每项128字符的列表。')
    if old:
        used=row(c,'SELECT COUNT(*) AS n FROM product_issue WHERE style_id=%s',(ident,))['n']
        if used and (old['project_id']!=pid or old['code']!=code): fail('已有引用，类别和款式编号不能普通修改。')
        count=row(c,'SELECT COUNT(*) AS n FROM digital_item d JOIN product_issue r ON r.id=d.issue_id WHERE r.style_id=%s',(ident,))['n']
        if count and p.get('shared_confirmed') is not True: fail('请确认本次共用保存将影响所有引用物品。')
    vals=(pid,code,profile['name'],profile['description'],profile['material'],profile['care_instructions'],json.dumps(specs,ensure_ascii=False),json.dumps(profile['image_urls']))
    if ident: c.execute('UPDATE product_style SET project_id=%s,code=%s,name=%s,description=%s,material=%s,care_instructions=%s,specs=%s,image_urls=%s WHERE id=%s',(*vals,ident))
    else:
        c.execute('INSERT INTO product_style(project_id,code,name,description,material,care_instructions,specs,image_urls) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',vals);ident=c.lastrowid
    c.execute('UPDATE style_image SET expires_at=COALESCE(expires_at,%s) WHERE style_id=%s',(now()+timedelta(hours=24),ident))
    for url in images:
        c.execute('UPDATE style_image SET expires_at=NULL WHERE style_id=%s AND asset_id=%s',(ident,url.rsplit('/',1)[-1]))
    if not old and p.get('test_batch_id') is not None:
        require_test_environment(current_app.config);mark(c,'style',ident,integer(p,'test_batch_id'))
    return {'id':ident}


def issue_save(c,p):
    field_set(p,{'style_id','name','mode','description','rights'}, {'id','series','total','starts_at','ends_at','counting_rule'})
    ident=integer(p,'id',optional=True)
    if ident and locked(c,'product_issue',ident)['confirmed_at']: fail('发行已确认，不能普通重写。')
    style=locked(c,'product_style',integer(p,'style_id'))
    if ident:same_source(c,'issue',ident,'style',style['id'])
    mode=p['mode'];total=integer(p,'total',optional=True)
    if not isinstance(mode,str) or mode not in {'fixed','period','unlimited'} or (mode=='fixed' and total is None): invalid('请选择发行方式，固定发行须提供总量。')
    rights=p['rights']
    if not isinstance(rights,list) or any(not isinstance(x,str) for x in rights) or len(rights)!=len(set(rights)) or set(rights)-{'renewal','resale'}: invalid('权益仅接受换新和转售。')
    start=end=None
    if mode=='period':
        try:
            start=datetime.fromisoformat(p['starts_at'].replace('Z','+00:00'));end=datetime.fromisoformat(p['ends_at'].replace('Z','+00:00'))
            if not start.tzinfo or not end.tzinfo or start>=end: raise ValueError
            start=start.astimezone(timezone.utc).replace(tzinfo=None);end=end.astimezone(timezone.utc).replace(tzinfo=None)
        except (KeyError,ValueError,TypeError,AttributeError): invalid('限时发行须提供带时区的起止时间。')
    vals=(style['id'],text(p,'name',128,required=True),text(p,'series',128),mode,total if mode=='fixed' else None,start,end,text(p,'counting_rule',4000),text(p,'description',4000,required=True),json.dumps(rights))
    if ident:c.execute('UPDATE product_issue SET style_id=%s,name=%s,series=%s,mode=%s,total=%s,starts_at=%s,ends_at=%s,counting_rule=%s,description=%s,rights=%s WHERE id=%s',(*vals,ident))
    else:
        c.execute('INSERT INTO product_issue(style_id,name,series,mode,total,starts_at,ends_at,counting_rule,description,rights) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',vals);ident=c.lastrowid
    mark(c,'issue',ident,source(c,'style',style['id']))
    return {'id':ident}


def issue_action(c,action,p):
    field_set(p,{'issue_id'}, {'total','evidence'})
    r=locked(c,'product_issue',integer(p,'issue_id'))
    if action=='confirmIssue':
        if r['confirmed_at']: fail('约定已确认，请查询结果。')
        if r['mode']=='period' and not r['counting_rule']: fail('请填写有效数量核定规则。')
        c.execute('UPDATE product_issue SET confirmed_at=%s WHERE id=%s',(now(),r['id']))
    elif action=='deleteIssue':
        if r['ever_used'] or row(c,'SELECT item_id FROM digital_item WHERE issue_id=%s LIMIT 1',(r['id'],)): fail('发行曾被引用，不能删除。')
        c.execute('DELETE FROM product_issue WHERE id=%s',(r['id'],))
    else:
        if r['mode']!='period' or not r['confirmed_at'] or r['sealed_at']: fail('仅已确认且未核定的限时发行可核定。')
        total=integer(p,'total');evidence=text(p,'evidence',1000,required=True)
        # 本机时钟可在独立测试中固定；没有未到期提前封版入口。
        if datetime.fromisoformat(r['ends_at'].replace('Z','+00:00')).replace(tzinfo=None)>now(): fail('销售窗口尚未结束，不能确认最终发行量。')
        c.execute('SELECT item_id,edition_number FROM digital_item WHERE issue_id=%s ORDER BY item_id FOR UPDATE',(r['id'],));items=c.fetchall()
        if len(items)>total or any(x['edition_number'] and x['edition_number']>total for x in items): fail('最终量少于已建身份或已有编号，请先核对冲突。')
        occupied={x['edition_number'] for x in items if x['edition_number']};number=1
        for item in items:
            if item['edition_number']:continue
            while number in occupied:number+=1
            c.execute('UPDATE digital_item SET edition_number=%s WHERE item_id=%s',(number,item['item_id']));occupied.add(number)
        c.execute('UPDATE product_issue SET total=%s,sealed_at=%s,seal_evidence=%s WHERE id=%s',(total,now(),evidence,r['id']))
    return {'id':r['id'],'issue_snapshot':r if action=='deleteIssue' else None}


def create_item(c,p):
    field_set(p,{'issue_id','item_uid'}, {'edition_number','is_validation'})
    r=locked(c,'product_issue',integer(p,'issue_id'))
    if not r['confirmed_at']:fail('请先确认发行约定。')
    s=locked(c,'product_style',r['style_id']);pid=s['project_id']
    project=row(c,'SELECT code FROM project WHERE id=%s',(pid,))['code'];uid=text(p,'item_uid',32,required=True)
    if any(ord(x)<32 or ord(x)==127 for x in uid):invalid('物品编号不能含控制字符。')
    number=integer(p,'edition_number',optional=True)
    if r['mode']=='period' and not r['sealed_at']:
        if number is not None:invalid('限时核定前正式编号待定，不能手填。')
    elif number is None:invalid('请填写发行内正式序号。')
    if r['total'] and number and number>r['total']:fail('编号超过已确认总量。')
    count=row(c,'SELECT COUNT(*) AS n FROM digital_item WHERE issue_id=%s',(r['id'],))['n']
    if r['total'] and count>=r['total']:fail('已达到数字身份发行上限。')
    c.execute('INSERT INTO item(project_id,item_uid) VALUES (%s,%s)',(pid,uid));ident=c.lastrowid
    c.execute('INSERT INTO digital_item(item_id,issue_id,edition_number,is_validation,quota_year) VALUES (%s,%s,%s,%s,%s)',(ident,r['id'],number,boolean(p,'is_validation'),(now()+timedelta(hours=8)).year))
    mark(c,'item',ident,source(c,'issue',r['id']))
    c.execute('UPDATE product_issue SET ever_used=1 WHERE id=%s',(r['id'],))
    return {'id':ident}


def item_action(c,action,p):
    ident=integer(p,'item_id');i=locked(c,'item',ident);d=digital(c,ident)
    lock_batch(c,source(c,'item',ident))
    if action=='validationItem':
        field_set(p,{'item_id','enabled'});c.execute('UPDATE digital_item SET is_validation=%s WHERE item_id=%s',(boolean(p,'enabled'),ident));return {'id':ident}
    if action=='deleteItem':
        field_set(p,{'item_id'})
        if not d['is_validation']:fail('仅生产验证物品可以直接删除。')
        c.execute('DELETE FROM item_handover WHERE item_id=%s',(ident,));c.execute('DELETE FROM whole_item WHERE item_id=%s',(ident,))
        c.execute("UPDATE chip SET item_id=NULL,chip_status=IF(chip_status='retired','retired','pending') WHERE item_id=%s",(ident,))
        for table,column in [('sms_challenge','tap_grant_id')]:
            c.execute('DELETE FROM sms_challenge WHERE tap_grant_id IN (SELECT id FROM tap_grant WHERE item_id=%s)',(ident,))
        for table in ('tap_grant','scan_log','ownership_history','ownership','jewelry_task_record','jewelry_user_progress','fashion_item_profile','jewelry_item_profile'):
            c.execute(f'DELETE FROM {table} WHERE item_id=%s',(ident,))
        # 保留媒体文件与记录的到期回收；附件不因删除档案立即覆盖或清盘。
        c.execute("UPDATE media_asset SET state='retired',expires_at=UTC_TIMESTAMP()+INTERVAL 24 HOUR WHERE item_id=%s AND state='attached'",(ident,))
        c.execute('DELETE FROM media_asset WHERE item_id=%s',(ident,))
        c.execute('DELETE FROM item WHERE id=%s',(ident,));return {'id':ident,'deleted_uid':i['item_uid']}
    if i['status']=='archived':fail('归档物品只读。')
    if action=='legacyProfile':
        field_set(p,{'item_id','profile'})
        if d['issue_id'] or i['project_id']!=project_id(c,'fashion'):fail('已关联款式或非服装旧资料不能从旧入口维护。')
        profile=normalized_profile(p['profile'])
        c.execute('INSERT INTO fashion_item_profile(item_id,name,description,material,care_instructions,image_urls) VALUES (%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name),description=VALUES(description),material=VALUES(material),care_instructions=VALUES(care_instructions),image_urls=VALUES(image_urls)',(ident,profile['name'],profile['description'],profile['material'],profile['care_instructions'],json.dumps(profile['image_urls'])))
    elif action=='linkIssue':
        field_set(p,{'item_id','issue_id','edition_number','evidence'})
        same_source(c,'item',ident,'issue',integer(p,'issue_id'))
        if d['issue_id']:fail('已有发行关联不能普通改写。')
        r=locked(c,'product_issue',integer(p,'issue_id'));s=locked(c,'product_style',r['style_id'])
        if not r['confirmed_at'] or s['project_id']!=i['project_id']:fail('请选择同类别且已确认的发行，先核对原承诺。')
        text(p,'evidence',1000,required=True);number=integer(p,'edition_number',optional=True)
        if r['mode']=='period' and not r['sealed_at']:
            if number is not None:invalid('未核定正式编号待定。')
        elif number is None or (r['total'] and number>r['total']):fail('编号不符合发行约定。')
        if r['total'] and row(c,'SELECT COUNT(*) AS n FROM digital_item WHERE issue_id=%s',(r['id'],))['n']>=r['total']:fail('发行身份上限已满。')
        c.execute('UPDATE digital_item SET issue_id=%s,edition_number=%s WHERE item_id=%s',(r['id'],number,ident));c.execute('UPDATE product_issue SET ever_used=1 WHERE id=%s',(r['id'],))
    elif action=='sale':
        field_set(p,{'item_id','confirmed','evidence'},{'first_sold_at'});evidence=text(p,'evidence',1000,required=True)
        sold_at=sale_time(p)
        if p.get('first_sold_at') is not None and d['first_sold_at'] and sold_at!=d['first_sold_at']:
            fail('已有首次售出时间不能通过普通维护改写。')
        c.execute('UPDATE digital_item SET sold=%s,first_sold_at=IF(%s,COALESCE(first_sold_at,%s),first_sold_at),sale_evidence=%s WHERE item_id=%s',(boolean(p,'confirmed'),boolean(p,'confirmed'),sold_at,evidence,ident))
    elif action=='toggleItem':
        field_set(p,{'item_id','status'})
        if not isinstance(p['status'],str) or p['status'] not in {'active','disabled'}:invalid('只支持启用或停用。')
        if p['status']=='active':
            e=current(c,ident);chip=locked(c,'chip',e['chip_id'])
            if not d['issue_id'] or not chip['provisioned_at'] or chip['chip_status']!='bound' or e['lost_at'] or e['loss_evidence']:fail('请先补齐发行、整套物品及有效配置核验。')
        c.execute('UPDATE item SET status=%s WHERE id=%s',(p['status'],ident))
        if p['status']=='disabled':revoke(c,ident)
    elif action=='bind':
        field_set(p,{'item_id','chip_id'},{'spec'})
        if current(c,ident,required=False):fail('已有当前整套物品，换新/转售请办理接续。')
        chip=locked(c,'chip',integer(p,'chip_id'));same_source(c,'item',ident,'chip',chip['id']);available_chip(c,chip,i['project_id'])
        if not d['issue_id']:fail('请先补齐发行约定。')
        generation=row(c,'SELECT COALESCE(MAX(generation),0)+1 AS n FROM whole_item WHERE item_id=%s',(ident,))['n']
        c.execute("UPDATE chip SET project_id=%s,item_id=%s,chip_status='bound' WHERE id=%s",(i['project_id'],ident,chip['id']))
        c.execute('INSERT INTO whole_item(item_id,chip_id,generation,spec,started_at) VALUES (%s,%s,%s,%s,%s)',(ident,chip['id'],generation,text(p,'spec',256) or '',now()))
    elif action=='loseItem':
        field_set(p,{'item_id','whole_id','evidence'});e=current(c,ident)
        if integer(p,'whole_id')!=e['id']:fail('当前物品已变化，请重新核对。')
        chip=locked(c,'chip',e['chip_id'])
        if e['lost_at'] or e['loss_evidence'] or chip['chip_status'] not in {'bound','disabled'}:fail('当前物品已挂失或不可挂失。')
        c.execute('UPDATE whole_item SET lost_at=%s,loss_evidence=%s WHERE id=%s',(now(),text(p,'evidence',1000,required=True),e['id']))
        c.execute("UPDATE chip SET chip_status='lost' WHERE id=%s",(chip['id'],))
        c.execute("UPDATE item_handover SET kind='loss' WHERE item_id=%s AND completed_at IS NULL AND kind='periodic'",(ident,));revoke(c,ident)
    elif action=='prepare':
        field_set(p,{'item_id','kind','chip_id','evidence'}, {'recipient_id','spec'})
        kind=p['kind'];e=current(c,ident)
        if not isinstance(kind,str) or kind not in KINDS:invalid('办理类型不支持。')
        if not d['issue_id']:fail('请先补齐发行。')
        # 已确认权益不可改写；只读约定，避免与限时封版形成反向锁等待。
        r=view(row(c,'SELECT * FROM product_issue WHERE id=%s',(d['issue_id'],)))
        if ('resale' if kind=='resale' else 'renewal') not in decoded(r['rights']):fail('发行未约定该权益。')
        if kind!='resale' and d['quota_year'] is None:fail('旧身份的年度事实尚未核对，不能猜测可用余额。')
        if kind!='resale' and d['quota_year']<(now()+timedelta(hours=8)).year and not d['quota_review']:
            c.execute('UPDATE digital_item SET quota_year=%s,quota_used=0 WHERE item_id=%s',((now()+timedelta(hours=8)).year,ident));d['quota_used']=0
        if kind!='resale' and (d['quota_used']>=1 or d['quota_review']):fail('年度余额不足或上次计次待核。')
        if kind!='resale' and ((kind=='loss')!=bool(e['lost_at'] or e['loss_evidence'])):fail('请选择与整套物品挂失事实一致的换新类型。')
        chip=locked(c,'chip',integer(p,'chip_id'));same_source(c,'item',ident,'chip',chip['id']);available_chip(c,chip,i['project_id'])
        owner=row(c,'SELECT * FROM ownership WHERE active_item_id=%s FOR UPDATE',(ident,))
        if not owner:fail('尚无正式持有人，不能办理换新/转售。')
        recipient=integer(p,'recipient_id') if kind=='resale' else owner['user_id']
        if kind=='resale' and (recipient==owner['user_id'] or not row(c,'SELECT id FROM user WHERE id=%s',(recipient,))):fail('请选择已建立的其他接收账户。')
        same_source(c,'item',ident,'user',recipient)
        generation=row(c,'SELECT MAX(generation)+1 AS n FROM whole_item WHERE item_id=%s',(ident,))['n']
        c.execute('INSERT INTO item_handover(item_id,source_id,chip_id,kind,generation,spec,owner_id,recipient_id,prepare_evidence,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(ident,e['id'],chip['id'],kind,generation,text(p,'spec',256) or '',owner['user_id'],recipient,text(p,'evidence',1000,required=True),now()))
        c.execute('UPDATE chip SET project_id=%s WHERE id=%s',(i['project_id'],chip['id']))
    else:fail('操作不支持。',404,'not_found')
    c.execute('UPDATE item SET updated_at=CURRENT_TIMESTAMP WHERE id=%s',(ident,))
    return {'id':ident}


def available_chip(c,chip,pid):
    if chip['chip_status']!='pending' or chip['item_id'] is not None or chip['project_id'] not in {None,pid}:fail('芯片已占用、状态不可用或类别不一致。')
    if row(c,'SELECT id FROM item_handover WHERE pending_chip_id=%s',(chip['id'],)):fail('芯片已用于其他整套物品准备。')


def complete(c,p):
    field_set(p,{'work_id','evidence','checked'})
    # 先定位物品，再按物品→办理→芯片→持有关系锁定；定位后重查。
    initial=row(c,'SELECT item_id FROM item_handover WHERE id=%s',(integer(p,'work_id'),))
    if not initial:fail('办理记录不存在。',404,'not_found')
    i=locked(c,'item',initial['item_id']);d=digital(c,i['id']);w=locked(c,'item_handover',p['work_id']);e=current(c,i['id'])
    if w['completed_at'] or w['source_id']!=e['id'] or i['status']=='archived':fail('原物品已变化或办理已完成，请核对结果。')
    c.execute('SELECT * FROM chip WHERE id IN (%s,%s) ORDER BY id FOR UPDATE',(e['chip_id'],w['chip_id']));chips={x['id']:x for x in c.fetchall()};old,new=chips[e['chip_id']],chips[w['chip_id']]
    owner=row(c,'SELECT * FROM ownership WHERE active_item_id=%s FOR UPDATE',(i['id'],))
    if not owner or owner['user_id']!=w['owner_id'] or old['item_id']!=i['id'] or new['item_id'] is not None or new['chip_status']!='pending' or not new['provisioned_at'] or new['project_id']!=i['project_id']:fail('物品、持有人或新物品配置已变化，请重新核对。')
    if p['checked'] is not True:invalid('请明确确认整套交付及接收人。')
    evidence=text(p,'evidence',1000,required=True)
    if w['kind']!='resale' and (d['quota_used']>=1 or d['quota_review']):fail('余额或待核状态已变化。')
    c.execute("UPDATE chip SET item_id=NULL,chip_status='retired' WHERE id=%s",(old['id'],))
    c.execute('UPDATE whole_item SET ended_at=%s,exit_reason=%s WHERE id=%s',(now(),w['kind'],e['id']))
    c.execute("UPDATE chip SET item_id=%s,chip_status='bound' WHERE id=%s",(i['id'],new['id']))
    c.execute('INSERT INTO whole_item(item_id,chip_id,generation,spec,started_at) VALUES (%s,%s,%s,%s,%s)',(i['id'],new['id'],w['generation'],w['spec'],now()));target=c.lastrowid
    if w['kind']=='resale':
        c.execute('UPDATE ownership SET is_active=0,unbound_at=%s WHERE id=%s',(now(),owner['id']))
        c.execute("INSERT INTO ownership(item_id,user_id,bind_source,bound_at) VALUES (%s,%s,'admin',%s)",(i['id'],w['recipient_id'],now()))
        c.execute("INSERT INTO ownership_history(item_id,from_user_id,to_user_id,action,note) VALUES (%s,%s,%s,'transfer',%s)",(i['id'],w['owner_id'],w['recipient_id'],'管理员核对整套交付，办理记录'+str(w['id'])))
    else:c.execute('UPDATE digital_item SET quota_review=1 WHERE item_id=%s',(i['id'],))
    c.execute('UPDATE item_handover SET target_id=%s,delivery_evidence=%s,completed_at=%s WHERE id=%s',(target,evidence,now(),w['id']))
    revoke(c,i['id']);return {'id':i['id'],'work_id':w['id']}


def chip_action(c,action,p):
    ident=integer(p,'chip_id')
    found=row(c,'SELECT c.item_id,w.item_id AS candidate_item_id FROM chip c LEFT JOIN item_handover w ON w.pending_chip_id=c.id WHERE c.id=%s',(ident,))
    if not found:fail('芯片不存在。',404,'not_found')
    if found['item_id'] or found['candidate_item_id']:locked(c,'item',found['item_id'] or found['candidate_item_id'])
    chip=locked(c,'chip',ident)
    if chip['item_id']!=found['item_id']:fail('关联已变化，请重新查询。')
    if action=='chipBatch':
        field_set(p,{'chip_id','batch_no'});c.execute('UPDATE chip SET batch_no=%s WHERE id=%s',(text(p,'batch_no',64),ident))
    elif action=='validationChip':
        field_set(p,{'chip_id','enabled'});c.execute('INSERT INTO chip_validation(chip_id,is_validation) VALUES (%s,%s) ON DUPLICATE KEY UPDATE is_validation=VALUES(is_validation)',(ident,boolean(p,'enabled')))
    elif action=='deleteChip':
        field_set(p,{'chip_id'})
        flag=row(c,'SELECT is_validation FROM chip_validation WHERE chip_id=%s',(ident,))
        if not flag or not flag['is_validation']:fail('仅生产验证芯片可以直接删除。')
        c.execute('DELETE FROM item_handover WHERE chip_id=%s OR source_id IN (SELECT id FROM whole_item WHERE chip_id=%s)',(ident,ident))
        c.execute('DELETE FROM whole_item WHERE chip_id=%s',(ident,))
        c.execute('DELETE FROM sms_challenge WHERE tap_grant_id IN (SELECT id FROM tap_grant WHERE chip_id=%s)',(ident,))
        for table in ('tap_grant','scan_log'):c.execute(f'DELETE FROM {table} WHERE chip_id=%s',(ident,))
        c.execute('DELETE FROM chip WHERE id=%s',(ident,))
    else:
        field_set(p,{'chip_id','state','evidence'});text(p,'evidence',1000,required=True)
        if chip['chip_status'] in {'lost','retired'} or row(c,'SELECT id FROM item_handover WHERE pending_chip_id=%s',(ident,)):fail('挂失、退役或候选芯片不能普通恢复或停用。')
        if chip['item_id']:
            e=current(c,chip['item_id'],required=False)
            if e and (e['lost_at'] or e['loss_evidence']):fail('整套物品已挂失，技术恢复不能解除。')
        if p['state']=='disabled' and chip['chip_status'] in {'pending','bound'}:state='disabled'
        elif p['state']=='restore' and chip['chip_status']=='disabled':state='bound' if chip['item_id'] else 'pending'
        else:fail('当前状态不允许该技术操作。')
        c.execute('UPDATE chip SET chip_status=%s WHERE id=%s',(state,ident))
        if chip['item_id']:revoke(c,chip['item_id'])
    return {'id':ident}


@blueprint.post('/actions/<action>')
def command(action):
    check_parameters(set())
    envelope=request_json({'request_id','payload'},max_bytes=100000)
    if action=='receipt':
        payload=envelope['payload']
        if not isinstance(payload,dict) or set(payload)!={'request_id'} or not isinstance(payload['request_id'],str):invalid('核对须提供原请求编号。')
        with consistent_read() as c:
            found=row(c,'SELECT result FROM admin_operation WHERE request_id=%s AND admin_id=%s',(payload['request_id'],g.admin_session['admin_id']))
            if not found:fail('尚无已提交回执，请明确重试原请求。',404,'not_found')
        return jsonify(status='ok',data=decoded(found['result']))
    token=envelope['request_id'];p=envelope['payload']
    if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}',token) or not isinstance(p,dict):invalid('请提供有效请求编号和字段对象。')
    digest=hashlib.sha256(json.dumps(p,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    connection=get_database();connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as c:
            lock_admin_session(c)
            prior=row(c,'SELECT * FROM admin_operation WHERE request_id=%s FOR UPDATE',(token,))
            if prior:
                if prior['admin_id']!=g.admin_session['admin_id'] or prior['action']!=action or prior['payload_hash']!=digest:fail('请求编号已用于其他操作，禁止替换输入重试。')
                result=decoded(prior['result'])
            else:
                if action=='clearTestBatch':
                    from core.test_batches import cleanup
                    require_test_environment(current_app.config);field_set(p,{'batch_id','confirmed'})
                    if p['confirmed'] is not True:invalid('请明确确认整批清理。')
                    result=cleanup(c,integer(p,'batch_id'))
                elif action=='register':
                    field_set(p,{'chip_uid'},{'project','batch_no','is_validation','test_batch_id'})
                    project=p.get('project')
                    if project is not None:project_id(c,project)
                    batch=text(p,'batch_no',64)
                    chip,is_new=save_chip(c,normalize_uid(p['chip_uid']),project=project,batch=batch,admin_id=g.admin_session['admin_id'],source='manual')
                    if is_new and boolean(p,'is_validation'):c.execute('INSERT INTO chip_validation(chip_id,is_validation) VALUES (%s,1)',(chip['id'],))
                    if p.get('test_batch_id') is not None:
                        require_test_environment(current_app.config)
                        if not is_new and source(c,'chip',chip['id'])!=integer(p,'test_batch_id'):fail('既有芯片不能改写测试来源。')
                        mark(c,'chip',chip['id'],integer(p,'test_batch_id'))
                    result={'id':chip['id'],'is_new':is_new}
                elif action=='saleBatch':
                    field_set(p,{'item_ids','confirmed','evidence'},{'first_sold_at'})
                    sale_time(p)
                    ids=p['item_ids']
                    if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not valid_id(n) or n>2147483647 for n in ids) or len(set(ids))!=len(ids):invalid('请选择1至100个不同的有效物品。')
                    origins={source(c,'item',ident) for ident in ids}
                    if len(origins)!=1:fail('一次操作不能混用业务或不同测试批次对象。')
                    for ident in sorted(ids):item_action(c,'sale',{'item_id':ident,'confirmed':p['confirmed'],'evidence':p['evidence'],**({'first_sold_at':p['first_sold_at']} if p.get('first_sold_at') is not None and not digital(c,ident)['first_sold_at'] else {})})
                    result={'ids':sorted(ids)}
                elif action=='style':result=style_save(c,p)
                elif action=='issue':result=issue_save(c,p)
                elif action in {'confirmIssue','deleteIssue','seal'}:result=issue_action(c,action,p)
                elif action=='item':result=create_item(c,p)
                elif action=='complete':result=complete(c,p)
                elif action in {'linkIssue','validationItem','deleteItem','sale','toggleItem','bind','loseItem','prepare','legacyProfile'}:result=item_action(c,action,p)
                elif action in {'validationChip','deleteChip','chipState','chipBatch'}:result=chip_action(c,action,p)
                else:fail('当前操作尚未开放。',404,'not_found')
                audit(c,action,result.get('id'),{'request_id':token,**p,**result})
                c.execute('INSERT INTO admin_operation(request_id,admin_id,action,payload_hash,result) VALUES (%s,%s,%s,%s,%s)',(token,g.admin_session['admin_id'],action,digest,json.dumps(result,ensure_ascii=False)))
        connection.commit()
    except pymysql.IntegrityError as error:
        connection.rollback()
        if error.args[0] in {1062,1452}:fail('编号已存在、对象已占用或关联已变化，请重新查询。',409,'conflict')
        raise
    except Exception:
        connection.rollback();raise
    return jsonify(status='ok',data=result)


@blueprint.get('/statistics')
def statistics():
    check_parameters({'scope','range','project','item_id','chip_id','data_scope','test_batch_id','style_id','issue_id','page','page_size'})
    scope=request.args.get('scope','sold');period=request.args.get('range','30d')
    if scope not in {'sold','all'} or period not in {'7d','30d','all'}:invalid('统计口径或时间范围不支持。')
    with consistent_read() as c:
        timestamp=row(c,'SELECT UTC_TIMESTAMP(6) AS t')['t'];conditions=["s.verify_result='pass'",'s.created_at<=%s'];values=[timestamp]
        data_scope=request.args.get('data_scope','business');batch=request.args.get('test_batch_id')
        clause,args=filter_source('item','s.item_id',data_scope,batch);conditions.append(clause);values.extend(args)
        if scope=='sold':conditions.extend(['d.sold=1','d.first_sold_at IS NOT NULL','s.created_at>=d.first_sold_at'])
        if period!='all':
            day=(timestamp+timedelta(hours=8)).replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=6 if period=='7d' else 29,hours=8)
            conditions.append('s.created_at>=%s');values.append(day)
        for key,column in [('item_id','s.item_id'),('chip_id','s.chip_id')]:
            if request.args.get(key):conditions.append(column+'=%s');values.append(positive_integer(key,1,2147483647))
        if request.args.get('project'):
            conditions.append('i.project_id=%s');values.append(project_id(c,request.args['project']))
        for key,column in [('style_id','(SELECT style_id FROM product_issue WHERE id=d.issue_id)'),('issue_id','d.issue_id')]:
            if request.args.get(key):conditions.append(column+'=%s');values.append(positive_integer(key,1,2147483647))
        joined=' FROM scan_log s JOIN item i ON i.id=s.item_id LEFT JOIN digital_item d ON d.item_id=s.item_id WHERE '+' AND '.join(conditions)
        summary=row(c,'SELECT COUNT(*) AS total,COUNT(DISTINCT s.item_id) AS touched_items'+joined,values)
        c.execute('SELECT DATE(s.created_at+INTERVAL 8 HOUR) AS day,COUNT(*) AS total'+joined+' GROUP BY day ORDER BY day',values);daily=[{'day':str(x['day']),'total':x['total']} for x in c.fetchall()]
        today=(timestamp+timedelta(hours=8)).date()
        first=today-timedelta(days=6 if period=='7d' else 29) if period!='all' else datetime.fromisoformat(daily[0]['day']).date() if daily else None
        if first:
            counts_by_day={x['day']:x['total'] for x in daily}
            daily=[{'day':(first+timedelta(days=n)).isoformat(),'total':counts_by_day.get((first+timedelta(days=n)).isoformat(),0)} for n in range((today-first).days+1)]
        c.execute('SELECT s.chip_id,s.chip_uid,COUNT(*) AS total'+joined+' GROUP BY s.chip_id,s.chip_uid ORDER BY s.chip_id',values);by_chip=c.fetchall()
        item_filter,item_args=filter_source('item','i.id',data_scope,batch)
        inventory=row(c,"SELECT COUNT(*) AS items,COALESCE(SUM(i.status='active'),0) AS active_items FROM item i WHERE "+item_filter,item_args)
        chip_filter,chip_args=filter_source('chip','x.id',data_scope,batch)
        inventory.update(row(c,"SELECT COALESCE(SUM(x.chip_status='pending' AND x.item_id IS NULL AND NOT EXISTS(SELECT 1 FROM item_handover h WHERE h.pending_chip_id=x.id)),0) AS pending_chips,COALESCE(SUM(x.item_id IS NOT NULL AND x.provisioned_at IS NULL AND x.chip_status<>'retired'),0) AS unconfigured_chips FROM chip x WHERE "+chip_filter,chip_args))
        item_conditions=[item_filter]
        for key,column in [('style_id','r.style_id'),('issue_id','d.issue_id'),('item_id','i.id')]:
            if request.args.get(key):item_conditions.append(column+'=%s');item_args.append(positive_integer(key,1,2147483647))
        if request.args.get('project'):item_conditions.append('i.project_id=%s');item_args.append(project_id(c,request.args['project']))
        item_join=' FROM item i LEFT JOIN digital_item d ON d.item_id=i.id LEFT JOIN product_issue r ON r.id=d.issue_id LEFT JOIN ownership o ON o.active_item_id=i.id LEFT JOIN user u ON u.id=o.user_id'
        item_where=' AND '.join(item_conditions)
        counts=row(c,'SELECT COUNT(*) AS items,COALESCE(SUM(COALESCE(d.sold,0)),0) AS sold_items,COUNT(o.user_id) AS claimed_items,COUNT(DISTINCT o.user_id) AS holders'+item_join+' WHERE '+item_where,item_args)
        event_query='SELECT s.item_id,COUNT(*) AS tap_count,MAX(s.created_at) AS last_tap'+joined+' GROUP BY s.item_id'
        eligible=item_conditions+(['d.sold=1'] if scope=='sold' else [])
        page,size=positive_integer('page',1,2147483647),positive_integer('page_size',10,100)
        total=row(c,'SELECT COUNT(*) AS total'+item_join+' WHERE '+' AND '.join(eligible),item_args)['total']
        paging=pagination(total,page,size)
        c.execute('SELECT i.id,i.item_uid,d.edition_number,d.issue_id,d.sold,r.total AS issue_total,u.id AS owner_id,u.nickname AS owner_name,COALESCE(events.tap_count,0) AS tap_count,events.last_tap'+item_join+' LEFT JOIN ('+event_query+') events ON events.item_id=i.id WHERE '+' AND '.join(eligible)+' ORDER BY i.id DESC LIMIT %s OFFSET %s',(*values,*item_args,size,(paging['page']-1)*size))
        details={'items':[view(x) for x in c.fetchall()],**paging}
        holder_filter,holder_args=filter_source('user','u.id',data_scope,batch)
        holder_query='SELECT u.id,u.nickname,COUNT(*) AS held_items'+item_join+' WHERE '+item_where+' AND u.id IS NOT NULL AND '+holder_filter+' GROUP BY u.id,u.nickname'
        holder_total=row(c,'SELECT COUNT(*) AS total FROM ('+holder_query+') holder_groups',(*item_args,*holder_args))['total']
        holder_paging=pagination(holder_total,page,size)
        c.execute(holder_query+' ORDER BY u.id DESC LIMIT %s OFFSET %s',(*item_args,*holder_args,size,(holder_paging['page']-1)*size))
        holders={'items':c.fetchall(),**holder_paging}
        for kind in ('chip','user'):
            clause,args=filter_source(kind,'x.id',data_scope,batch)
            counts[kind+'s']=row(c,'SELECT COUNT(*) AS n FROM '+kind+' x WHERE '+clause,args)['n']
    return jsonify(status='ok',data={**summary,'daily':daily,'by_chip':by_chip,'counts':counts,'inventory':inventory,'details':details,'holders':holders,'as_of':iso_time(timestamp),'scope':scope,'range':period,'timezone':'Asia/Shanghai','claim_service_available':False})


@blueprint.route('/styles/<int:style_id>/images/<asset_id>',methods=['GET','POST'])
def style_image(style_id,asset_id):
    from core.admin_media import encode_image,UploadFormDataParser
    from core.media_assets import MAX_FILE
    check_parameters(set())
    if not re.fullmatch(r'[a-f0-9]{32}',asset_id):invalid('图片编号须为随机32位十六进制。')
    if request.method=='GET':
        with consistent_read() as c:
            image=row(c,'SELECT content FROM style_image WHERE style_id=%s AND asset_id=%s',(style_id,asset_id))
            if not image:fail('图片不存在。',404,'not_found')
        response=Response(image['content'],mimetype='image/webp');response.headers['X-Content-Type-Options']='nosniff';return response
    # 小规模共用图片随数据库一起备份；规模增大时迁回文件存储，不能公开数据URL。
    if current_app.config.get('MEDIA_ENABLED') is not True:fail('图片上传未启用。',503,'service_unavailable')
    request.max_content_length=9*1024**2;request.max_form_parts=1;request.max_form_memory_size=64*1024
    request.form_data_parser_class=UploadFormDataParser
    if set(request.files)!={'file'} or len(request.files.getlist('file'))!=1 or request.form:invalid('仅接受一个图片文件。')
    raw=request.files['file'].stream.read(MAX_FILE+1)
    if not raw or len(raw)>MAX_FILE:invalid('单张图片最多8MiB。')
    digest=hashlib.sha256(raw).hexdigest();encoded,_=encode_image(raw)
    connection=get_database()
    with connection.cursor() as guard:
        guard.execute("SELECT GET_LOCK(CONCAT(DATABASE(),':media-admission'),0)")
        if guard.fetchone()[0]!=1:fail('另一张图片正在处理，请稍后明确重试。',409,'media_busy')
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as c:
            lock_admin_session(c);locked(c,'product_style',style_id);lock_batch(c,source(c,'style',style_id))
            found=row(c,'SELECT asset_id,style_id,source_sha256,expires_at FROM style_image WHERE asset_id=%s FOR UPDATE',(asset_id,))
            if found:
                if found['expires_at'] and found['expires_at']<=now():fail('暂存已过期，请放弃本次上传后重新选择。')
                if found['style_id']!=style_id or found['source_sha256']!=digest:fail('图片请求编号已被其他上传使用。')
            else:
                c.execute('DELETE FROM style_image WHERE style_id=%s AND expires_at<%s',(style_id,now()))
                count=row(c,'SELECT COUNT(*) AS n FROM style_image WHERE style_id=%s',(style_id,))['n']
                if count>=100:fail('本款已上传图片达到100张，请先核对资料。')
                cap=current_app.config.get('MEDIA_MAX_TOTAL_BYTES')
                size=row(c,'SELECT COALESCE(SUM(OCTET_LENGTH(content)),0) AS n FROM style_image')['n']
                file_size=row(c,'SELECT COALESCE(SUM(GREATEST(byte_size,reserved_bytes)),0) AS n FROM media_asset')['n']
                if type(cap) is not int or int(size)+int(file_size)+len(encoded)>cap:fail('图片容量不足，未接收新图片。',409,'media_quota_exceeded')
                c.execute('INSERT INTO style_image(asset_id,style_id,created_by,source_sha256,content,expires_at) VALUES (%s,%s,%s,%s,%s,%s)',(asset_id,style_id,g.admin_session['admin_id'],digest,encoded,now()+timedelta(hours=24)))
                audit(c,'image.upload',style_id,{'asset_id':asset_id})
        connection.commit()
    except Exception:connection.rollback();raise
    finally:
        with connection.cursor() as guard:guard.execute("SELECT RELEASE_LOCK(CONCAT(DATABASE(),':media-admission'))")
    return jsonify(status='ok',data={'url':f'/api/admin/catalog/styles/{style_id}/images/{asset_id}'})


def shared_image(cursor,item_id,asset_id):
    found=row(cursor,'SELECT s.image_urls,a.content FROM digital_item d JOIN product_issue r ON r.id=d.issue_id JOIN product_style s ON s.id=r.style_id JOIN style_image a ON a.style_id=s.id WHERE d.item_id=%s AND a.asset_id=%s',(item_id,asset_id))
    if not found or not any(url.endswith('/images/'+asset_id) for url in decoded(found['image_urls'])):fail('该图片不属于当前物品的已保存共用资料。',404,'not_found')
    return {'content':found['content']}


@blueprint.get('/styles/<int:style_id>/images/<asset_id>/status')
def style_image_status(style_id,asset_id):
    check_parameters(set())
    with consistent_read() as c:
        found=row(c,'SELECT asset_id FROM style_image WHERE style_id=%s AND asset_id=%s',(style_id,asset_id))
        if not found:fail('尚无已提交上传记录。',404,'not_found')
    return jsonify(status='ok',data={'url':f'/api/admin/catalog/styles/{style_id}/images/{asset_id}'})


@blueprint.get('/test-batches')
def test_batches():
    check_parameters({'page','page_size','keyword','data_scope'})
    with consistent_read() as c:
        result=list_page(c,'SELECT b.*','FROM test_batch b',[],[],order='b.id DESC')
    try:require_test_environment(current_app.config);result['writable']=True
    except AuthRequestError:result['writable']=False
    return jsonify(status='ok',data=result)

@blueprint.get('/test-batches/<int:batch>/preview')
def batch_preview(batch):
    from core.test_batches import preview
    check_parameters(set());require_test_environment(current_app.config)
    with consistent_read() as c:result=preview(c,batch)
    return jsonify(status='ok',data=result)
