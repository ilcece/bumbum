"""仅在明确测试库准备合成持有人，供验收售后；不是首次认领服务。"""
import argparse
import json
import sys
import uuid

import pymysql

from core.db import get_database
from core.rds_target import validate_target


def validate_test_target(config):
    if config.get('HANGZHOU_SLOT') == 'test':
        validate_target(config)
        return
    expected={'APP_ENV':'development','DB_NAME':'bumbum_digital','DB_USER':'bumbum_dev','DB_PORT':33306}
    if config.get('HANGZHOU_SLOT') or config.get('DB_HOST') not in {'127.0.0.1','localhost'} or any(config.get(k)!=v for k,v in expected.items()):
        raise ValueError('仅允许固定杭州test槽或原本机开发测试库，不连接生产/未知目标。')


def seed_holders(connection,item_id,username,*,apply=False):
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as c:
            c.execute("SELECT id FROM admin_user WHERE username=%s AND status='active' AND totp_enabled=1 FOR UPDATE",(username,))
            admin=c.fetchone()
            if not admin:raise ValueError('请使用已有且启用验证器的测试管理员账号。')
            c.execute('SELECT id FROM item WHERE id=%s FOR UPDATE',(item_id,))
            if not c.fetchone():raise ValueError('物品不存在，请从完整详情URL核对内部ID。')
            c.execute('SELECT is_validation,issue_id FROM digital_item WHERE item_id=%s FOR UPDATE',(item_id,));d=c.fetchone()
            if not d or not d['is_validation'] or not d['issue_id']:raise ValueError('仅对已关联发行、已标记生产验证的物品准备测试数据。')
            c.execute('SELECT id FROM ownership WHERE active_item_id=%s FOR UPDATE',(item_id,))
            if c.fetchone():raise ValueError('当前已有持有人，不覆盖或重复准备。')
            result={'test_only':True,'applied':apply,'item_id':item_id}
            if apply:
                suffix=uuid.uuid4().hex[:12];ids=[];names=[]
                for role in ('A','B'):
                    name='测试持有人'+role+'-'+suffix[-4:]
                    c.execute('INSERT INTO user(phone,nickname) VALUES (%s,%s)',('TEST'+role+suffix,name));ids.append(c.lastrowid);names.append(name)
                c.execute("INSERT INTO ownership(item_id,user_id,bind_source) VALUES (%s,%s,'import')",(item_id,ids[0]))
                c.execute("INSERT INTO ownership_history(item_id,from_user_id,to_user_id,action,note) VALUES (%s,NULL,%s,'bind','仅测试库的合成持有关系，不是用户认领')",(item_id,ids[0]))
                result.update(owner_id=ids[0],recipient_id=ids[1],owner_name=names[0],recipient_name=names[1])
                c.execute("INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail) VALUES (%s,'catalog.test_seed','item',%s,%s)",(admin['id'],str(item_id),json.dumps({'origin':'server_testdata_command',**result},ensure_ascii=False)))
        if apply:connection.commit()
        else:connection.rollback()
        return result
    except Exception:
        connection.rollback()
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description='仅测试库：为已标记验证物品准备两个合成账户及首个持有人，默认只检查。')
    parser.add_argument('--item-id',required=True,type=int)
    parser.add_argument('--admin-username',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args(argv)
    try:
        from app import create_app
        app=create_app();validate_test_target(app.config)
        if not 1<=args.item_id<=2147483647:raise ValueError('物品ID超出允许范围。')
        with app.app_context():result=seed_holders(get_database(),args.item_id,args.admin_username,apply=args.apply)
        print(json.dumps(result,ensure_ascii=False));return 0
    except ValueError as error:print('未执行：'+str(error),file=sys.stderr)
    except Exception:print('未完成：测试数据准备失败，未输出配置或SQL；请核对原记录，不覆盖现有持有人。',file=sys.stderr)
    return 1


if __name__=='__main__':sys.exit(main())
