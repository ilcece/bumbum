"""仅测试目标的验收数据包：默认预览，重复执行复用，清理后可新建同一套场景。"""
import argparse
from datetime import timedelta
from io import BytesIO
import hashlib
import json
import sys
import uuid

from flask import current_app
from PIL import Image,ImageDraw
import pymysql

from core.catalog_testdata import validate_test_target
from core.test_batches import mark

PACK='acceptance-v1'
SCENARIOS=['待配套','待配置','已准备','已启用','售出未认领','已有持有人','整套挂失','换新准备中','换新完成','转售完成','零触碰','售出前后触碰','草稿留作操作','非限定样本','限时待核定','限时最终137','待绑定芯片']

def seed(connection,username,*,apply=False):
    from core.admin_catalog import style_save,issue_save,issue_action,create_item,item_action,complete,now,row
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as c:
            c.execute("SELECT GET_LOCK('bumbum.acceptance-seed',5) AS n")
            if c.fetchone()['n']!=1:raise ValueError('另一验收数据命令正在执行。')
            c.execute("SELECT id FROM admin_user WHERE username=%s AND status='active' AND totp_enabled=1 FOR UPDATE",(username,));admin=c.fetchone()
            if not admin:raise ValueError('请使用已有且启用验证器的管理员。')
            c.execute("SELECT * FROM test_batch WHERE JSON_UNQUOTE(JSON_EXTRACT(manifest,'$.pack'))=%s AND status='active' ORDER BY id DESC LIMIT 1 FOR UPDATE",(PACK,));existing=c.fetchone()
            if existing:
                connection.rollback();return {'reused':True,'batch_id':existing['id'],'manifest':json.loads(existing['manifest'])}
            if not apply:
                connection.rollback();return {'apply':False,'pack':PACK,'scenarios':SCENARIOS,'note':'将创建三类款式、20身份、专用虚拟芯片和合成账户；不会写真实芯片。'}
            c.execute('INSERT INTO test_batch(code,name,manifest) VALUES (%s,%s,%s)',('acceptance-'+uuid.uuid4().hex[:12],'后台核心流程验收',json.dumps({'pack':PACK},ensure_ascii=False)));batch=c.lastrowid
            def tag(kind,ident):mark(c,kind,ident,batch);return ident
            stamp=now();entries=[];styles=[];issues=[];users=[]
            for role in ('A','B'):
                c.execute('INSERT INTO user(phone,nickname) VALUES (%s,%s)',('TEST'+role+uuid.uuid4().hex[:12],f'验收{batch}持有人{role}'));users.append(tag('user',c.lastrowid))
            for index,(name,project,mode) in enumerate([('紫檀手串','jewelry','fixed'),('T恤','fashion','unlimited'),('棒球帽','fashion','period')]):
                style=style_save(c,{'project':project,'code':f'TEST-{batch}-{index}','name':'验收·'+name,'description':'合成验收样本，可按批次剔除或清理。','material':'测试材质','care_instructions':'测试说明','specs':['标准款','大号'],'image_urls':[]})['id'];tag('style',style);styles.append(style)
                image=Image.new('RGB',(720,480),['#a57248','#4069ad','#447b66'][index]);draw=ImageDraw.Draw(image);draw.rounded_rectangle((150,120,570,360),radius=50,fill='white');draw.text((245,220),['BRACELET','T-SHIRT','CAP'][index],fill='#172339');out=BytesIO();image.save(out,format='WEBP');content=out.getvalue();asset=uuid.uuid4().hex
                c.execute('INSERT INTO style_image(asset_id,style_id,created_by,source_sha256,content) VALUES (%s,%s,%s,%s,%s)',(asset,style,admin['id'],hashlib.sha256(content).hexdigest(),content))
                c.execute('UPDATE product_style SET image_urls=%s WHERE id=%s',(json.dumps([f'/api/admin/catalog/styles/{style}/images/{asset}']),style))
                p={'style_id':style,'name':f'验收·{name}发行','mode':mode,'description':'换新与转售交付新整套，身份延续。','rights':['renewal','resale']}
                if mode=='fixed':p['total']=50
                if mode=='period':p.update(counting_rule='按销售窗口内外部渠道有效售出数量人工核定',total=100,starts_at=(stamp-timedelta(days=35)).isoformat()+'Z',ends_at=(stamp-timedelta(days=5)).isoformat()+'Z')
                issue=issue_save(c,p)['id'];issues.append(issue);tag('issue',issue);issue_action(c,'confirmIssue',{'issue_id':issue})
            def chip(project):
                # 随机专用虚拟UID；不为真实卡生成、覆盖密钥或计数。
                from core.chip_registry import save_chip,normalize_uid
                uid='04'+uuid.uuid4().hex[:12].upper()
                r,is_new=save_chip(c,normalize_uid(uid),project=project,batch=f'验收-{batch}',admin_id=admin['id'],source='manual')
                if not is_new:raise ValueError('虚拟UID冲突，事务已撤销。')
                ident=tag('chip',r['id']);c.execute('INSERT INTO chip_validation(chip_id,is_validation) VALUES (%s,1)',(ident,));return ident
            def configured(ident):
                # 显式合成配置事实，仅供后台状态/售后验收；没有chip_key，不能通过真实用户验签。
                c.execute('UPDATE chip SET provisioned_at=%s,last_verified_counter=2 WHERE id=%s',(stamp,ident))
            def owner(ident):
                c.execute("INSERT INTO ownership(item_id,user_id,bind_source,bound_at) VALUES (%s,%s,'import',%s)",(ident,users[0],stamp-timedelta(days=4)))
                c.execute("INSERT INTO ownership_history(item_id,to_user_id,action,note) VALUES (%s,%s,'bind','合成验收导入，不是真实认领')",(ident,users[0]))
            def event(ident,ch,at):
                c.execute('SELECT chip_uid,project_id FROM chip WHERE id=%s',(ch,));r=c.fetchone()
                c.execute("SELECT COALESCE(MAX(scan_counter),2)+1 AS n FROM scan_log WHERE chip_id=%s",(ch,));n=c.fetchone()['n']
                c.execute("INSERT INTO scan_log(chip_uid,project_id,chip_id,item_id,scan_counter,verify_result,user_agent,created_at) VALUES (%s,%s,%s,%s,%s,'pass','SYNTHETIC_ACCEPTANCE_IMPORT',%s)",(r['chip_uid'],r['project_id'],ch,ident,n,at));tag('scan',c.lastrowid)
            for n in range(20):
                index=0 if n<12 else 1 if n<16 else 2;project='jewelry' if index==0 else 'fashion'
                number=n+1 if index==0 else n-11 if index==1 else None
                uid=('JEW' if project=='jewelry' else 'FASH')+f'-{stamp.year}-{batch*100+n+1:06d}'
                ident=create_item(c,{'issue_id':issues[index],'item_uid':uid,'edition_number':number,'is_validation':True})['id']
                scenario=SCENARIOS[n] if n<12 else '从草稿开始操作' if n==12 else '非限定样本' if index==1 else '限时待核定'
                ch=None
                if n!=0 and n!=12:
                    ch=chip(project);item_action(c,'bind',{'item_id':ident,'chip_id':ch,'spec':'合成实物·标准款'})
                    if n!=1:configured(ch)
                    if n>=3:item_action(c,'toggleItem',{'item_id':ident,'status':'active'})
                    if n>=4 and n!=12:
                        item_action(c,'sale',{'item_id':ident,'confirmed':True,'evidence':'合成验收售出，非实际订单'})
                        c.execute('UPDATE digital_item SET first_sold_at=%s WHERE item_id=%s',(stamp-timedelta(days=4),ident))
                    if 5<=n<=9:owner(ident)
                    if n in (6,7,8,9):
                        if n==6:
                            whole=row(c,'SELECT id FROM whole_item WHERE item_id=%s',(ident,))['id'];item_action(c,'loseItem',{'item_id':ident,'whole_id':whole,'evidence':'合成整套挂失'})
                        else:
                            target=chip(project);kind='resale' if n==9 else 'periodic'
                            payload={'item_id':ident,'chip_id':target,'kind':kind,'spec':'合成新整套','evidence':'合成准备'}
                            if n==9:payload['recipient_id']=users[1]
                            event(ident,ch,stamp-timedelta(days=3));item_action(c,'prepare',payload)
                            if n in (8,9):
                                configured(target);w=row(c,'SELECT id FROM item_handover WHERE item_id=%s',(ident,))['id'];complete(c,{'work_id':w,'checked':True,'evidence':'合成导入交付，不代表实物已寄送'});ch=target
                    if n==11:event(ident,ch,stamp-timedelta(days=6))
                    if n>=4 and n!=10:event(ident,ch,stamp-timedelta(days=1))
                entries.append({'item_id':ident,'uid':uid,'scenario':scenario,'chip_id':ch})
            # 同一帽子款式保留待核定案例，并另外提供已核定137的发行，不虚构137件身份。
            extra=issue_save(c,{'style_id':styles[2],'name':'验收·最终核定137','counting_rule':'按有效售出数量核定','mode':'period','total':100,'starts_at':(stamp-timedelta(days=40)).isoformat()+'Z','ends_at':(stamp-timedelta(days=10)).isoformat()+'Z','description':'销售预估100，期末实际137。','rights':['renewal','resale']})['id'];tag('issue',extra);issue_action(c,'confirmIssue',{'issue_id':extra});issue_action(c,'seal',{'issue_id':extra,'total':137,'evidence':'合成多渠道汇总137'})
            draft=issue_save(c,{'style_id':styles[1],'name':'验收·留作确认的草稿','mode':'fixed','total':20,'description':'留给验收者确认发行','rights':['renewal','resale']})['id'];tag('issue',draft)
            for project in ('fashion','jewelry'):
                for _ in range(3):chip(project)
            c.execute("SELECT COUNT(*) AS total FROM scan_log s JOIN test_batch_object tb ON tb.kind='item' AND tb.object_id=s.item_id WHERE tb.batch_id=%s",(batch,));lifecycle=c.fetchone()['total']
            c.execute("SELECT COUNT(*) AS total FROM scan_log s JOIN digital_item d ON d.item_id=s.item_id JOIN test_batch_object tb ON tb.kind='item' AND tb.object_id=s.item_id WHERE tb.batch_id=%s AND d.sold=1 AND s.created_at>=d.first_sold_at",(batch,));sold=c.fetchone()['total']
            manifest={'pack':PACK,'synthetic':True,'warning':'配置、持有、交付、触碰为合成导入，不是真实卡/认领证据；虚拟芯片没有密钥，不能通过真实验签。','items':entries,'expected_initial':{'items':20,'users':2,'lifecycle_taps':lifecycle,'sold_taps':sold},'real_cards':[]}
            c.execute('UPDATE test_batch SET manifest=%s WHERE id=%s',(json.dumps(manifest,ensure_ascii=False),batch))
            c.execute("INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail) VALUES (%s,'catalog.test_seed','test_batch',%s,%s)",(admin['id'],str(batch),json.dumps({'origin':'test_command','batch_id':batch,'pack':PACK},ensure_ascii=False)))
        connection.commit();return {'batch_id':batch,'manifest':manifest,'applied':True}
    except Exception:connection.rollback();raise
    finally:
        with connection.cursor() as c:c.execute("SELECT RELEASE_LOCK('bumbum.acceptance-seed')")


def main(argv=None):
    parser=argparse.ArgumentParser(description='仅明确测试目标：后台验收数据包，默认预览。')
    parser.add_argument('--admin-username',required=True);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args(argv)
    try:
        from app import create_app
        from core.db import get_database
        app=create_app();validate_test_target(app.config)
        with app.test_request_context():result=seed(get_database(),args.admin_username,apply=args.apply)
        print(json.dumps(result,ensure_ascii=False));return 0
    except ValueError as error:print('未执行：'+str(error),file=sys.stderr)
    except Exception:print('未完成：验收数据事务失败；未输出配置、SQL或秘密。请核对原批次后重试。',file=sys.stderr)
    return 1

if __name__=='__main__':sys.exit(main())
