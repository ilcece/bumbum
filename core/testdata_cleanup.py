"""旧样例/历史图片清理：只读清单、明确对象、配套备份和冻结窗口；拒绝生产。"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import pymysql

from core.account_uid import ACCOUNT_UID
from core.catalog_testdata import validate_test_target
from core.media_assets import media_root
from core.media_backup import create_bundle,inspect_bundle,digest


def inventory(connection):
    with connection.cursor(pymysql.cursors.DictCursor) as c:
        c.execute('SELECT @@server_uuid AS server_uuid,DATABASE() AS database_name');target=c.fetchone()
        c.execute('SELECT i.id,i.item_uid,i.status,EXISTS(SELECT 1 FROM ownership o WHERE o.item_id=i.id) AS has_owner_history FROM item i ORDER BY i.id');items=c.fetchall()
        c.execute('SELECT c.id,c.chip_uid,c.item_id,c.chip_status,c.provisioned_at IS NOT NULL AS configured,c.last_verified_counter IS NOT NULL AS has_counter,EXISTS(SELECT 1 FROM chip_key k WHERE k.chip_id=c.id) AS has_keys FROM chip c ORDER BY c.id');chips=c.fetchall()
        c.execute('SELECT asset_id,storage_key,sha256 FROM media_asset ORDER BY asset_id');images=c.fetchall()
        c.execute('SELECT id,image_urls FROM product_style ORDER BY id');styles=c.fetchall()
        c.execute('SELECT uid AS id,EXISTS(SELECT 1 FROM ownership o WHERE o.user_id=u.uid) AS has_holdings FROM user u ORDER BY uid');users=c.fetchall()
        c.execute('SELECT id,style_id,name FROM product_issue ORDER BY id');issues=c.fetchall()
        c.execute('SELECT item_id,chip_id FROM whole_item ORDER BY id');wholes=c.fetchall()
        result={**target,'wholes':wholes,'users':users,'issues':issues,'items':items,'chips':chips,'legacy_images':images,'styles':styles}
        result['snapshot_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,default=str).encode()).hexdigest()
        return result


def cleanup(connection,plan,admin_id):
    """调用者已经核对目标、冻结写入并完成配套备份；数据库改动原子提交。"""
    from core.admin_catalog import item_action,chip_action
    connection.begin()
    try:
        current=inventory(connection)
        with connection.cursor() as guard:
            guard.execute("SELECT COUNT(*) FROM test_batch WHERE status='active'")
            if guard.fetchone()[0]:raise ValueError('已有活动测试批次，请先按批次清理；旧图片全清理仅在新数据包建立前执行。')
        if plan.get('snapshot_sha256')!=current['snapshot_sha256']:raise ValueError('清单生成后对象已变化，请重新盘点；未清理。')
        ids=plan.get('delete_items',[]);chips=plan.get('delete_chips',[])
        extras={kind:plan.get('delete_'+kind+'s',[]) for kind in ('user','issue','style')}
        if any(not isinstance(v,list) for v in [ids,chips,*extras.values()]):raise ValueError('清理对象须为ID列表。')
        if any(type(n) is not int or n<1 for n in [*ids,*chips,*extras['issue'],*extras['style']]):raise ValueError('清理清单只接受明确正整数物品、芯片、发行和款式ID。')
        if any(not isinstance(uid,str) or not ACCOUNT_UID.fullmatch(uid) for uid in extras['user']):raise ValueError('清理清单必须使用账户UID。')
        known_items={r['id']:r for r in current['items']};known_chips={r['id']:r for r in current['chips']}
        if not set(ids)<=set(known_items) or not set(chips)<=set(known_chips):raise ValueError('清理对象不属于盘点清单。')
        protected={r['id'] for r in current['chips'] if r['configured'] or r['has_counter'] or r['has_keys'] or r['chip_status'] in {'lost','retired'}}
        protected_items={r['id'] for r in current['items'] if r['has_owner_history']}|{r['item_id'] for r in current['chips'] if r['id'] in protected}
        protected_items|={r['item_id'] for r in current['wholes'] if r['chip_id'] in protected}
        protected|={r['id'] for r in current['chips'] if r['item_id'] in protected_items}
        protected|={r['chip_id'] for r in current['wholes'] if r['item_id'] in protected_items}
        if protected&set(chips) or protected_items&set(ids):raise ValueError('清单包含配置卡、验证计数、密钥或持有历史等受保护对象，未删除。')
        with connection.cursor(pymysql.cursors.DictCursor) as c:
            for ident in ids:
                c.execute('INSERT INTO digital_item(item_id,is_validation) VALUES (%s,1) ON DUPLICATE KEY UPDATE is_validation=1',(ident,));item_action(c,'deleteItem',{'item_id':ident})
            for ident in chips:
                c.execute('INSERT INTO chip_validation(chip_id,is_validation) VALUES (%s,1) ON DUPLICATE KEY UPDATE is_validation=1',(ident,));chip_action(c,'deleteChip',{'chip_id':ident})
            for kind,table in [('user','user'),('issue','product_issue'),('style','product_style')]:
                known={r['id'] for r in current[{'user':'users','issue':'issues','style':'styles'}[kind]]}
                if not set(extras[kind])<=known:raise ValueError('清理对象不属于原清单。')
                for ident in extras[kind]:
                    if kind=='user':
                        c.execute('SELECT id FROM ownership_history WHERE from_user_id=%s OR to_user_id=%s LIMIT 1',(ident,ident))
                        if c.fetchone():raise ValueError('用户仍有持有历史，未清理。')
                    if kind=='style':c.execute('DELETE FROM style_image WHERE style_id=%s',(ident,))
                    key='uid' if kind=='user' else 'id'
                    c.execute(f'DELETE FROM {table} WHERE {key}=%s',(ident,))
            # 所有历史图片已明确获准清理，新数据包在本命令之后创建。
            for table in ('fashion_item_profile','jewelry_item_profile','product_style'):c.execute(f'UPDATE {table} SET image_urls=JSON_ARRAY()')
            c.execute('DELETE FROM style_image');c.execute('DELETE FROM media_asset')
            result={'removed_users':extras['user'],'removed_issues':extras['issue'],'removed_styles':extras['style'],'removed_items':ids,'removed_chips':chips,'legacy_images':len(current['legacy_images']),'cleared_style_images':True}
            c.execute("INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail) VALUES (%s,'catalog.legacy_cleanup','test_environment','snapshot',%s)",(admin_id,json.dumps({'snapshot_sha256':current['snapshot_sha256'],**result},ensure_ascii=False)))
        connection.commit();return result,current['legacy_images']
    except Exception:connection.rollback();raise


def backup(connection,config,destination):
    program=shutil.which('mysqldump')
    if not program:raise ValueError('需要MySQL8.0原生mysqldump，未清理。')
    version=subprocess.run([program,'--version'],capture_output=True,text=True,timeout=10)
    if version.returncode or not re.search(r'\b8\.0\.',version.stdout):raise ValueError('备份客户端须为MySQL8.0。')
    root=Path(destination)
    if not root.is_absolute() or root.resolve()!=root:raise ValueError('备份位置须为私有绝对目录。')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if root.is_symlink() or (os.name!='nt' and root.stat().st_mode&0o077):raise ValueError('备份目录须仅本人可访问。')
    dump=root/('before-testdata-'+uuid.uuid4().hex+'.sql')
    flags=[program,'--no-defaults','--host='+config['DB_HOST'],'--port='+str(config['DB_PORT']),'--user='+config['DB_USER'],'--single-transaction','--skip-lock-tables','--no-tablespaces','--set-gtid-purged=OFF','--hex-blob']
    if config['DB_SSL_MODE']=='VERIFY_IDENTITY':flags+=['--ssl-mode=VERIFY_IDENTITY','--ssl-ca='+config['DB_SSL_CA']]
    else:flags+=['--ssl-mode=DISABLED']
    with dump.open('xb') as out:
        os.chmod(dump,0o600)
        r=subprocess.run([*flags,config['DB_NAME']],env={**os.environ,'MYSQL_PWD':config['DB_PASSWORD']},stdout=out,stderr=subprocess.PIPE,timeout=300)
    with dump.open('rb') as check:
        check.seek(max(0,dump.stat().st_size-512));finished=b'-- Dump completed on' in check.read()
    if r.returncode or not finished:raise ValueError('完整转储未完成；保留私有文件，未清理。')
    bundle=root/('images-and-database-'+uuid.uuid4().hex)
    create_bundle(connection,media_root(),dump,bundle,writes_frozen=True);inspect_bundle(bundle)
    return bundle


def remove_backed_up_files(images,bundle):
    root=media_root();errors=[]
    for r in images:
        name=r['storage_key']
        if not re.fullmatch(r'[a-f0-9]{32}\.webp',name):errors.append(r['asset_id']);continue
        path=root/name;saved=Path(bundle)/'images'/name
        if not path.exists():continue
        if path.is_symlink() or not saved.is_file() or digest(path)!=digest(saved):errors.append(r['asset_id']);continue
        path.unlink()
    return errors


def main(argv=None):
    parser=argparse.ArgumentParser(description='仅测试：盘点旧样例；apply需明确清单、冻结、配套备份，图片全清理。')
    parser.add_argument('--plan',type=Path);parser.add_argument('--apply',action='store_true');parser.add_argument('--admin-username');parser.add_argument('--writes-stopped',action='store_true');parser.add_argument('--confirm-server-uuid');parser.add_argument('--backup-dir',type=Path)
    args=parser.parse_args(argv)
    try:
        from app import create_app
        from core.db import get_database
        app=create_app();validate_test_target(app.config)
        with app.test_request_context():
            conn=get_database();report=inventory(conn)
            if not args.apply:print(json.dumps(report,ensure_ascii=False,default=str));return 0
            if not args.plan or not args.writes_stopped or not args.backup_dir or report['server_uuid']!=args.confirm_server_uuid:raise ValueError('须提供明确计划、已停止写入、实例UUID和私有备份目录。')
            plan=json.loads(args.plan.read_text());
            if plan.get('snapshot_sha256')!=report['snapshot_sha256']:raise ValueError('计划与当前盘点不一致，未清理。')
            with conn.cursor() as c:
                c.execute("SELECT id FROM admin_user WHERE username=%s AND status='active' AND totp_enabled=1",(args.admin_username,));admin=c.fetchone()
            if not admin:raise ValueError('须使用已有启用验证器的管理员。')
            conn.rollback();bundle=backup(conn,app.config,args.backup_dir)
            result,images=cleanup(conn,plan,admin[0]);remaining=remove_backed_up_files(images,bundle)
            print(json.dumps({'database_cleanup':'committed','backup':str(bundle),'files_needing_review':remaining,**result},ensure_ascii=False));return 1 if remaining else 0
    except ValueError as error:print('未完成：'+str(error),file=sys.stderr)
    except Exception:print('未完成：保留备份和现场；清理提交状态及文件需核对，未输出秘密或SQL。',file=sys.stderr)
    return 1

if __name__=='__main__':sys.exit(main())
