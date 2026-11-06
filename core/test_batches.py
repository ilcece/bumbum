"""测试来源、统一筛选与整批清理；仅明确测试目标提供写入口。"""
import json
from core.admin_auth import AuthRequestError
from core.catalog_testdata import validate_test_target

TABLES={'style':'product_style','issue':'product_issue','item':'item','chip':'chip','user':'user','scan':'scan_log'}

def require_test_environment(config):
    try:validate_test_target(config)
    except ValueError as error:raise AuthRequestError(403,'test_only',str(error)) from None

def source(c,kind,ident):
    c.execute('SELECT batch_id FROM test_batch_object WHERE kind=%s AND object_id=%s',(kind,ident))
    r=c.fetchone()
    return r['batch_id'] if r else None

def lock_batch(c,batch):
    if batch is None:return
    c.execute('SELECT status FROM test_batch WHERE id=%s FOR UPDATE',(batch,));r=c.fetchone()
    if not r or r['status']!='active':raise AuthRequestError(409,'batch_unavailable','测试批次已清理，不能继续写入。')

def mark(c,kind,ident,batch):
    if batch is None:return
    lock_batch(c,batch)
    old=source(c,kind,ident)
    if old is not None and old!=batch:raise AuthRequestError(409,'batch_conflict','对象已有其他测试来源，不能改写。')
    c.execute('INSERT IGNORE INTO test_batch_object(kind,object_id,batch_id) VALUES (%s,%s,%s)',(kind,ident,batch))

def same_source(c,left_kind,left,right_kind,right):
    a,b=source(c,left_kind,left),source(c,right_kind,right)
    if a!=b:raise AuthRequestError(409,'batch_conflict','测试批次与业务数据不能混用，请选择同批次对象。')
    return a

def select_source(kind,alias):
    if kind not in TABLES:raise ValueError('未知来源类型')
    return f"(SELECT batch_id FROM test_batch_object tb WHERE tb.kind='{kind}' AND tb.object_id={alias}.id) AS test_batch_id"

def filter_source(kind,column,scope,batch):
    if scope not in {'business','test','all'}:raise AuthRequestError(400,'invalid_param','数据范围只支持business、test、all。')
    sql=f"SELECT 1 FROM test_batch_object tb WHERE tb.kind=%s AND tb.object_id={column}"
    values=[kind]
    if batch is not None:
        if scope=='business':raise AuthRequestError(400,'invalid_param','选择批次时请切换测试或全部数据。')
        if not str(batch).isascii() or not str(batch).isdigit() or not 1<=int(batch)<=2147483647:raise AuthRequestError(400,'invalid_param','测试批次编号无效。')
        sql+=' AND tb.batch_id=%s';values.append(int(batch))
    if scope=='all' and batch is None:return '1=1',[]
    return ('NOT EXISTS' if scope=='business' else 'EXISTS')+' ('+sql+')',values

def objects(c,batch,*,lock=False):
    result={}
    for kind,table in TABLES.items():
        c.execute(f'SELECT x.id FROM {table} x JOIN test_batch_object tb ON tb.object_id=x.id AND tb.kind=%s WHERE tb.batch_id=%s ORDER BY x.id'+(' FOR UPDATE' if lock else ''),(kind,batch))
        result[kind]=[r['id'] for r in c.fetchall()]
    return result

def conflicts(c,ids):
    # 少量验收数据直接核对关系，避免为清理建立第二套业务模型。
    checks=[('product_issue','id','style_id','issue','style'),('product_issue','style_id','id','style','issue'),('digital_item','item_id','issue_id','item','issue'),('digital_item','issue_id','item_id','issue','item'),('chip','id','item_id','chip','item'),('whole_item','item_id','chip_id','item','chip'),('whole_item','chip_id','item_id','chip','item'),('item_handover','item_id','chip_id','item','chip'),('item_handover','chip_id','item_id','chip','item'),('scan_log','item_id','chip_id','item','chip'),('scan_log','chip_id','item_id','chip','item'),('jewelry_user_progress','item_id','user_id','item','user'),('jewelry_user_progress','user_id','item_id','user','item'),('jewelry_task_record','user_id','item_id','user','item'),('ownership','item_id','user_id','item','user'),('ownership','user_id','item_id','user','item'),('ownership_history','item_id','from_user_id','item','user'),('ownership_history','item_id','to_user_id','item','user'),('ownership_history','from_user_id','item_id','user','item'),('ownership_history','to_user_id','item_id','user','item'),('item_handover','owner_id','item_id','user','item'),('item_handover','recipient_id','item_id','user','item')]
    bad=[]
    for table,left,right,lk,rk in checks:
        c.execute(f'SELECT {left} AS a,{right} AS b FROM {table}')
        for r in c.fetchall():
            if r['a'] in ids[lk] and r['b'] is not None and r['b'] not in ids[rk]:bad.append({'kind':lk,'id':r['a'],'related_kind':rk,'related_id':r['b']})
    return bad

def preview(c,batch,*,lock=False):
    c.execute('SELECT * FROM test_batch WHERE id=%s'+(' FOR UPDATE' if lock else ''),(batch,));b=c.fetchone()
    if not b:raise AuthRequestError(404,'not_found','测试批次不存在。')
    ids=objects(c,batch,lock=lock)
    return {'id':batch,'status':b['status'],'counts':{k:len(v) for k,v in ids.items()},'conflicts':conflicts(c,ids),'objects':ids}

def cleanup(c,batch):
    from core.admin_catalog import item_action,chip_action
    p=preview(c,batch,lock=True)
    if p['status']=='deleted':return p
    if p['conflicts']:raise AuthRequestError(409,'batch_conflict','批次存在外部关联，请先查看清理预览；没有删除任何对象。')
    ids=p['objects']
    # 单条删除规则不改；整批显式清理本批拥有的双方对象。
    for ident in ids['item']:
        c.execute('UPDATE digital_item SET is_validation=1 WHERE item_id=%s',(ident,));item_action(c,'deleteItem',{'item_id':ident})
    for ident in ids['chip']:
        c.execute('INSERT INTO chip_validation(chip_id,is_validation) VALUES (%s,1) ON DUPLICATE KEY UPDATE is_validation=1',(ident,));chip_action(c,'deleteChip',{'chip_id':ident})
    for kind in ('scan','issue','style','user'):
        for ident in ids[kind]:
            if kind=='style':c.execute('DELETE FROM style_image WHERE style_id=%s',(ident,))
            c.execute(f'DELETE FROM {TABLES[kind]} WHERE id=%s',(ident,))
    c.execute("UPDATE test_batch SET status='deleted',deleted_at=UTC_TIMESTAMP(6) WHERE id=%s",(batch,))
    return {'id':batch,'status':'deleted','removed':p['counts']}
