"""仅测试目标的真实照片验收包；默认预览，清理后可重建，不改既有业务。"""
import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import secrets
import sys
import uuid

import pymysql

from core.catalog_testdata import validate_test_target
from core.test_batches import cleanup, mark, preview

PACK = 'acceptance-v3-assembly-h5'
SCENARIOS = ['待配套', '待配置', '已准备未启用', '启用未售出', '售出未认领',
             '已有持有人', '整套挂失', '换新准备中', '换新完成', '转售完成',
             '零触碰', '售出前后触碰', '物品与芯片已停用', '挂失换新准备中']


def catalog():
    """只读取已查看并固定摘要的公开照片，灌入过程不联网。"""
    folder = Path(__file__).with_name('acceptance_assets')
    result = json.loads((folder / 'catalog.json').read_text(encoding='utf-8'))
    for record in result:
        photo = record['photo']
        path = folder / photo['file']
        if path.parent != folder or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != photo['sha256']:
            raise ValueError('验收照片缺失或摘要不符，未灌入。')
    return result


def seed(connection, username, *, apply=False, replace_batch=None):
    from core.admin_catalog import style_save, issue_save, issue_action, create_item, create_physical, item_action, chip_action, complete, now, row
    records = catalog()
    connection.begin()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as c:
            c.execute("SELECT GET_LOCK('bumbum.acceptance-seed',5) AS n")
            if c.fetchone()['n'] != 1:
                raise ValueError('另一验收数据命令正在执行。')
            c.execute("SELECT id FROM admin_user WHERE username=%s AND status='active' AND totp_enabled=1 FOR UPDATE", (username,))
            admin = c.fetchone()
            if not admin:
                raise ValueError('请使用已有且启用验证器的管理员。')
            c.execute("SELECT * FROM test_batch WHERE JSON_UNQUOTE(JSON_EXTRACT(manifest,'$.pack'))=%s AND status='active' ORDER BY id DESC LIMIT 1 FOR UPDATE", (PACK,))
            existing = c.fetchone()
            old_preview=None
            if replace_batch is not None:
                old=row(c,'SELECT manifest FROM test_batch WHERE id=%s FOR UPDATE',(replace_batch,))
                manifest=json.loads(old['manifest']) if old else {}
                if manifest.get('synthetic') is not True or manifest.get('pack')!='acceptance-v2':
                    raise ValueError('仅可替换明确的旧模拟验收包 acceptance-v2。')
                old_preview=preview(c,replace_batch)
            if existing:
                if old_preview and old_preview['status']!='deleted':raise ValueError('已有活动新版验收批次；请先核对旧批次和新版的用途。')
                connection.rollback()
                return {'reused': True, 'batch_id': existing['id'], 'manifest': json.loads(existing['manifest'])}
            if not apply:
                connection.rollback()
                return {'apply': False, 'pack': PACK, 'scenarios': SCENARIOS, 'styles': len(records), 'items': len(records) * len(SCENARIOS), 'replacing':old_preview, 'note': '将创建真实照片款式、编号实体、独立虚拟芯片和合成账户。'}
            replaced=cleanup(c,replace_batch) if old_preview and old_preview['status']!='deleted' else None
            c.execute('INSERT INTO test_batch(code,name,manifest) VALUES (%s,%s,%s)', ('acceptance-' + uuid.uuid4().hex[:12], '真实照片·后台全流程验收', json.dumps({'pack': PACK})))
            batch = c.lastrowid

            def tag(kind, ident):
                mark(c, kind, ident, batch)
                return ident

            stamp = now()
            year = (stamp + timedelta(hours=8)).year
            entries, styles, issues, users, photos = [], [], [], [], []
            for name in ('林澄', '周予', '许禾', '陈屿', '宋岚', '陆遥'):
                c.execute('INSERT INTO user(phone,nickname,phone_verified_at) VALUES (%s,%s,%s)', ('TEST' + uuid.uuid4().hex[:16], f'模拟·{name}', stamp))
                users.append(tag('user', c.lastrowid))
            for index, record in enumerate(records):
                style = style_save(c, {'project': record['project'], 'code': f'SIM-{batch}-{record["slug"].upper()}', 'name': '验收·' + record['name'], 'description': record['description'], 'material': record['material'], 'care_instructions': record['care'], 'specs': record['specs'], 'image_urls': []})['id']
                styles.append(tag('style', style))
                photo = record['photo']
                content = (Path(__file__).with_name('acceptance_assets') / photo['file']).read_bytes()
                asset = uuid.uuid4().hex
                c.execute('INSERT INTO style_image(asset_id,style_id,created_by,source_sha256,content) VALUES (%s,%s,%s,%s,%s)', (asset, style, admin['id'], photo['sha256'], content))
                c.execute('UPDATE product_style SET image_urls=%s WHERE id=%s', (json.dumps([f'/api/admin/catalog/styles/{style}/images/{asset}']), style))
                photos.append({**photo, 'style_id': style, 'style_name': record['name']})
                p = {'style_id': style, 'name': record['name'] + ' · 秋冬发行', 'series': '2026秋冬·日常佩戴', 'mode': record['mode'], 'description': '模拟发行：按对应发行方式分配数字身份与编号。'}
                if p['mode'] == 'fixed':
                    p['total'] = 50
                if p['mode'] == 'period':
                    p.update(counting_rule='按窗口内外部渠道有效售出汇总人工核定，退款剔除', total=100, starts_at=(stamp - timedelta(days=35)).isoformat() + 'Z', ends_at=(stamp - timedelta(days=5)).isoformat() + 'Z')
                issue = issue_save(c, p)['id']
                issues.append(tag('issue', issue))
                issue_action(c, 'confirmIssue', {'issue_id': issue})

            def chip(project, number):
                from core.chip_registry import save_chip, normalize_uid
                uid = normalize_uid('04' + uuid.uuid4().hex[:12].upper())
                r, is_new = save_chip(c, uid, project=project, batch=f'SIM-{batch}-{project or "待分类"}-{number % 3 + 1}', admin_id=admin['id'], source='manual' if number % 2 else 'nfc_cool')
                if not is_new:
                    raise ValueError('虚拟UID冲突，事务已撤销。')
                ident = tag('chip', r['id'])
                c.execute('INSERT INTO chip_validation(chip_id,is_validation) VALUES (%s,%s)', (ident, number % 2 == 0))
                return ident

            def configured(ident):
                # 仅导入显式合成配置事实；不生成chip_key，不能通过真实验签。
                c.execute('UPDATE chip SET provisioned_at=%s,last_verified_counter=2 WHERE id=%s', (stamp, ident))

            def owner(ident, account):
                c.execute("INSERT INTO ownership(item_id,user_id,bind_source,bound_at) VALUES (%s,%s,'import',%s)", (ident, account, stamp - timedelta(days=4)))
                c.execute("INSERT INTO ownership_history(item_id,to_user_id,action,note) VALUES (%s,%s,'bind','模拟持有关系，不代表首次认领已交付')", (ident, account))

            def event(ident, ch, at):
                r = row(c, 'SELECT chip_uid,project_id FROM chip WHERE id=%s', (ch,))
                count = row(c, 'SELECT COALESCE(MAX(scan_counter),2)+1 AS n FROM scan_log WHERE chip_id=%s', (ch,))['n']
                c.execute("INSERT INTO scan_log(chip_uid,project_id,chip_id,item_id,scan_counter,verify_result,user_agent,created_at) VALUES (%s,%s,%s,%s,%s,'pass','SYNTHETIC_ACCEPTANCE_IMPORT',%s)", (r['chip_uid'], r['project_id'], ch, ident, count, at))
                tag('scan', c.lastrowid)

            # 交错创建，让默认第一页就能看到不同商品与状态，而非连续同款。
            for turn in range(len(SCENARIOS)):
                for index, record in enumerate(records):
                    phase = (turn + index * 3) % len(SCENARIOS)
                    scenario = SCENARIOS[phase]
                    n = index * len(SCENARIOS) + phase
                    project = record['project']
                    uid = ('JEW' if project == 'jewelry' else 'FASH') + f'-{stamp.year}-{batch * 100 + n + 1:06d}'
                    number = None if record['mode'] == 'period' else phase + 1
                    ident = create_item(c, {'issue_id': issues[index], 'item_uid': uid, 'edition_number': number, 'is_validation': phase in (0, 1, 12)})['id']
                    spec = record['specs'][phase % len(record['specs'])]
                    physical_uid=f'SIM-PHY-{batch}-{n+1:03d}'
                    physical=create_physical(c,{'style_id':styles[index],'physical_uid':physical_uid,'spec':spec})['id']
                    ch = None
                    if phase:
                        ch = chip(project, n)
                        item_action(c,'installAssembly',{'item_id':ident,'chip_id':ch,'physical_item_id':physical,'installed':True},installed_by=admin['id'])
                        if phase != 1:
                            configured(ch)
                        if phase >= 3:
                            item_action(c, 'toggleItem', {'item_id': ident, 'status': 'active'})
                        if phase >= 4:
                            item_action(c, 'sale', {'item_id': ident, 'confirmed': True, 'evidence': '模拟已核对外部售出事实，非实际订单'})
                            c.execute('UPDATE digital_item SET first_sold_at=%s WHERE item_id=%s', (stamp - timedelta(days=4), ident))
                        if phase >= 5:
                            owner(ident, users[index])
                        if phase == 4:
                            c.execute('INSERT INTO item_claim_code(item_id,code_hash,issued_by,delivery_reference,issued_at,expires_at) VALUES (%s,%s,%s,%s,%s,%s)',(ident,secrets.token_bytes(32),admin['id'],'模拟首次交付；此码仅用于展示待认领状态',stamp,stamp+timedelta(days=30)))
                        if phase in (6, 13):
                            whole = row(c, 'SELECT id FROM whole_item WHERE item_id=%s', (ident,))['id']
                            item_action(c, 'loseItem', {'item_id': ident, 'whole_id': whole, 'evidence': '模拟原持有人报告整套丢失，历史关系保留'})
                        if phase in (7, 8, 9, 13):
                            target = chip(project, n + 100)
                            kind = 'resale' if phase == 9 else 'loss' if phase == 13 else 'periodic'
                            next_uid=f'{physical_uid}-R'
                            next_physical=create_physical(c,{'style_id':styles[index],'physical_uid':next_uid,'spec':record['specs'][(phase+1)%len(record['specs'])]})['id']
                            payload = {'item_id': ident, 'chip_id': target, 'kind': kind, 'physical_item_id':next_physical,'installed':True,'evidence': '模拟已核对整套替换资格及实际规格'}
                            if phase == 9:
                                payload.update(recipient_id=users[(index+1)%len(users)],seller_confirmation='模拟原持有人已确认',recipient_confirmation='模拟接收人已接受')
                                c.execute('UPDATE digital_item SET quota_used=1 WHERE item_id=%s',(ident,))
                            event(ident, ch, stamp - timedelta(days=3))
                            item_action(c,'prepare',payload,installed_by=admin['id'])
                            if phase in (8, 9):
                                configured(target)
                                work = row(c, 'SELECT id FROM item_handover WHERE item_id=%s', (ident,))['id']
                                if phase==8:
                                    c.execute('UPDATE item_handover SET created_at=%s WHERE id=%s',(datetime(year-1,12,31,15,50),work))
                                complete(c, {'work_id': work, 'checked': True, 'evidence': '模拟核对新实物及芯片已交付，不代表真实发货'})
                                ch = target
                                physical,physical_uid=next_physical,next_uid
                        if phase == 11:
                            event(ident, ch, stamp - timedelta(days=6))
                        if phase >= 4 and phase != 10:
                            for step in range(1 + index % 3):
                                event(ident, ch, stamp - timedelta(days=step + 1, hours=phase))
                        if phase == 12:
                            item_action(c, 'toggleItem', {'item_id': ident, 'status': 'disabled'})
                            chip_action(c, 'chipState', {'chip_id': ch, 'state': 'disabled', 'evidence': '模拟技术停用，与挂失及退役区分'})
                    entries.append({'item_id': ident, 'uid': uid, 'style_id': styles[index], 'style_name': record['name'], 'scenario': scenario, 'spec': spec, 'chip_id': ch,'physical_item_id':physical,'physical_uid':physical_uid})

            # 已核定发行不虚构137件身份；草案留给验收者确认。
            for index, record in enumerate(records):
                if record['mode'] == 'period':
                    extra = issue_save(c, {'style_id': styles[index], 'name': record['name'] + ' · 最终核定137', 'series': '2026夏季·已结束', 'counting_rule': '按有效售出数量核定，退款不计入', 'mode': 'period', 'total': 100, 'starts_at': (stamp - timedelta(days=70)).isoformat() + 'Z', 'ends_at': (stamp - timedelta(days=40)).isoformat() + 'Z', 'description': '模拟销售预估100，最终137；不凭空新增身份。', 'rights': ['renewal', 'resale']})['id']
                    tag('issue', extra)
                    issue_action(c, 'confirmIssue', {'issue_id': extra})
                    issue_action(c, 'seal', {'issue_id': extra, 'total': 137, 'evidence': '模拟有效售出汇总137'})
            for index in (0, 1):
                draft = issue_save(c, {'style_id': styles[index], 'name': records[index]['name'] + ' · 留作确认草案', 'series': '下一季·准备中', 'mode': 'fixed', 'total': 20, 'description': '留给验收者确认发行后从零建档，不自动生效。', 'rights': ['renewal', 'resale']})['id']
                tag('issue', draft)
            for index, project in enumerate(('fashion', 'jewelry', None)):
                for state in range(4):
                    ident = chip(project, 200 + index * 4 + state)
                    if state == 2 and project is not None:
                        configured(ident)
                    if state == 3:
                        chip_action(c, 'chipState', {'chip_id': ident, 'state': 'disabled', 'evidence': '模拟未绑定芯片暂停使用'})
            c.execute("UPDATE chip c JOIN (SELECT s.chip_id,MAX(s.scan_counter) AS counter FROM scan_log s JOIN test_batch_object tb ON tb.kind='scan' AND tb.object_id=s.id WHERE tb.batch_id=%s GROUP BY s.chip_id) x ON x.chip_id=c.id SET c.last_verified_counter=GREATEST(COALESCE(c.last_verified_counter,0),x.counter)", (batch,))
            lifecycle = row(c, "SELECT COUNT(*) AS n FROM scan_log s JOIN test_batch_object tb ON tb.kind='scan' AND tb.object_id=s.id WHERE tb.batch_id=%s", (batch,))['n']
            sold = row(c, "SELECT COUNT(*) AS n FROM scan_log s JOIN digital_item d ON d.item_id=s.item_id JOIN test_batch_object tb ON tb.kind='scan' AND tb.object_id=s.id WHERE tb.batch_id=%s AND d.sold=1 AND s.created_at>=d.first_sold_at", (batch,))['n']
            manifest = {'pack': PACK, 'synthetic': True, 'warning': '照片为网上真实实物照片；业务资料、配置、持有、交付及触碰为独立模拟导入。虚拟芯片没有密钥，不能证明实卡、首次认领、真实销售或交付通过。', 'items': entries, 'photos': photos, 'expected_initial': {'styles': len(records), 'issues': 10, 'items': len(entries), 'chips': 114, 'users': len(users), 'lifecycle_taps': lifecycle, 'sold_taps': sold}, 'real_cards': []}
            c.execute('UPDATE test_batch SET manifest=%s WHERE id=%s', (json.dumps(manifest, ensure_ascii=False), batch))
            c.execute("INSERT INTO admin_audit(admin_id,action,target_type,target_id,detail) VALUES (%s,'catalog.test_seed','test_batch',%s,%s)", (admin['id'], str(batch), json.dumps({'origin': 'test_command', 'batch_id': batch, 'pack': PACK})))
        connection.commit()
        return {'batch_id': batch, 'manifest': manifest, 'applied': True,'replaced':replaced}
    except Exception:
        connection.rollback()
        raise
    finally:
        with connection.cursor() as c:
            c.execute("SELECT RELEASE_LOCK('bumbum.acceptance-seed')")


def main(argv=None):
    parser = argparse.ArgumentParser(description='仅明确测试目标：真实照片验收包，默认预览。')
    parser.add_argument('--admin-username', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--replace-batch', type=int, help='明确要替换的旧模拟批次 ID，默认预览')
    parser.add_argument('--backup-confirmed', action='store_true', help='确认已备份目标测试槽的数据库与媒体')
    args = parser.parse_args(argv)
    if args.replace_batch is not None and (args.replace_batch<1 or (args.apply and not args.backup_confirmed)):
        parser.error('替换时须提供正整数批次 ID，应用前须确认已完成测试备份。')
    try:
        from app import create_app
        from core.db import get_database
        app = create_app()
        validate_test_target(app.config)
        with app.test_request_context():
            result = seed(get_database(), args.admin_username, apply=args.apply,replace_batch=args.replace_batch)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except ValueError as error:
        print('未执行：' + str(error), file=sys.stderr)
    except Exception:
        print('未完成：验收数据事务失败；未输出配置、SQL或秘密。请核对原批次后重试。', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
