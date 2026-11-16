"""持有档案的可见记录，以及按当前持有关系保存的找回同意。"""

from datetime import datetime, timedelta
from hmac import compare_digest
import re

from core.aliyun_sms import MAINLAND_PHONE
from core.auth_settings import fingerprint, iso_time, utc_now


def consent_hash(owner):
    return fingerprint('item-recovery-contact', f"{owner['ownership_id']}|{owner['phone']}", binary=True)


def contact_enabled(owner):
    return bool(owner and owner['consent_hash'] and owner['phone_verified_at']
                and re.fullmatch(MAINLAND_PHONE, owner['phone'] or '')
                and compare_digest(owner['consent_hash'], consent_hash(owner)))


def active_contact(cursor, item_id):
    cursor.execute('''SELECT o.id AS ownership_id,u.phone,u.phone_verified_at,s.consent_hash
                      FROM ownership o JOIN user u ON u.uid=o.user_id
                      LEFT JOIN item_recovery_contact s ON s.ownership_id=o.id
                      WHERE o.active_item_id=%s FOR SHARE''', (item_id,))
    return cursor.fetchone()


def lost_physical(cursor, item, chip):
    if not item or not chip or chip['project'] != 'fashion' or item['status'] != 'active' or chip['chip_status'] != 'lost' or not chip['provisioned_at']:
        return False
    cursor.execute('''SELECT id FROM whole_item
                      WHERE current_item_id=%s AND chip_id=%s AND (lost_at IS NOT NULL OR loss_evidence IS NOT NULL)
                      FOR SHARE''', (item['id'], chip['id']))
    return cursor.fetchone() is not None


def lifecycle_view(data):
    work = data.pop('pending_kind')
    prepared = data.pop('pending_verified_at')
    completed = data.pop('handover_completed_at')
    kind = data.pop('handover_kind')
    notice_id = data.pop('handover_id')
    dismissed = data.pop('dismissed_handover')
    lost = bool(data.pop('physical_lost'))
    stage = ('resale' if work == 'resale' else 'renewal') if work else None
    notice = None
    if completed and not dismissed and utc_now() < completed + timedelta(days=7) and not (stage or lost):
        notice = {'token': notice_token(notice_id), 'kind': 'received' if kind == 'resale' else 'renewed',
                  'expires_at': iso_time(completed + timedelta(days=7))}
    return {'lost': lost, 'stage': stage, 'awaiting_delivery': bool(prepared), 'notice': notice}


def notice_token(handover_id):
    return fingerprint('item-holder-notice', handover_id)


def records(cursor, user_id, item_id=None):
    """仅从业务事实生成节点，响应中不带对方账户、办理依据或芯片信息。"""
    item_filter = ' AND i.id=%s' if item_id is not None else ''
    args = (user_id,) if item_id is None else (user_id,item_id)
    cursor.execute('''SELECT i.id,i.item_uid,s.name,d.edition_number,r.total AS issue_total,
                             o.bound_at AS at,'claimed' AS event
                      FROM ownership o JOIN item i ON i.id=o.item_id
                      LEFT JOIN digital_item d ON d.item_id=i.id LEFT JOIN product_issue r ON r.id=d.issue_id
                      LEFT JOIN product_style s ON s.id=r.style_id
                      WHERE o.user_id=%s AND NOT EXISTS (SELECT 1 FROM item_handover h
                        WHERE h.item_id=i.id AND h.kind='resale' AND h.recipient_id=o.user_id
                        AND h.completed_at>=o.bound_at AND h.completed_at<o.bound_at+INTERVAL 1 SECOND)'''+item_filter,args)
    events = list(cursor.fetchall())
    cursor.execute('''SELECT i.id,i.item_uid,s.name,d.edition_number,r.total AS issue_total,w.lost_at AS at,'lost' AS event
                      FROM ownership o JOIN item i ON i.id=o.item_id JOIN whole_item w ON w.item_id=i.id
                      LEFT JOIN digital_item d ON d.item_id=i.id LEFT JOIN product_issue r ON r.id=d.issue_id
                      LEFT JOIN product_style s ON s.id=r.style_id
                      WHERE o.user_id=%s AND w.lost_at>=o.bound_at AND (o.unbound_at IS NULL OR w.lost_at<o.unbound_at)'''+item_filter,args)
    events.extend(cursor.fetchall())
    cursor.execute('''SELECT DISTINCT i.id,i.item_uid,s.name,d.edition_number,r.total AS issue_total,
                             JSON_UNQUOTE(JSON_EXTRACT(a.detail,'$.before.lost_at')) AS lost_at,
                             JSON_UNQUOTE(JSON_EXTRACT(a.detail,'$.before.holder_bound_at')) AS holder_bound_at,
                             JSON_UNQUOTE(JSON_EXTRACT(a.detail,'$.cancelled_at')) AS cancelled_at
                      FROM user u JOIN ownership o ON o.user_id=u.uid JOIN item i ON i.id=o.item_id
                      JOIN admin_audit a ON a.target_type='item' AND a.action='catalog.cancelLoss'
                        AND BINARY JSON_UNQUOTE(JSON_EXTRACT(a.detail,'$.before.user_uid'))=BINARY BIN_TO_UUID(u.public_uid)
                        AND a.target_id=CAST(i.id AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_unicode_ci
                      LEFT JOIN digital_item d ON d.item_id=i.id LEFT JOIN product_issue r ON r.id=d.issue_id
                      LEFT JOIN product_style s ON s.id=r.style_id WHERE u.uid=%s'''+item_filter,args)
    for entry in cursor.fetchall():
        cancelled_at=entry.pop('cancelled_at')
        lost_at=entry.pop('lost_at')
        holder_bound_at=entry.pop('holder_bound_at')
        if holder_bound_at and lost_at and lost_at!='null' and datetime.fromisoformat(lost_at)<datetime.fromisoformat(holder_bound_at):
            lost_at=None
        for event, at in (('lost',lost_at),('loss_cancelled',cancelled_at)):
            if at and at!='null':
                events.append(dict(entry,event=event,at=datetime.fromisoformat(at).replace(tzinfo=None)))
    cursor.execute('''SELECT i.id,i.item_uid,s.name,d.edition_number,r.total AS issue_total,h.kind,h.created_at,
                             h.completed_at,h.owner_id,h.recipient_id,ch.provisioned_at
                      FROM item_handover h JOIN item i ON i.id=h.item_id JOIN chip ch ON ch.id=h.chip_id
                      LEFT JOIN digital_item d ON d.item_id=i.id LEFT JOIN product_issue r ON r.id=d.issue_id
                      LEFT JOIN product_style s ON s.id=r.style_id
                      WHERE (h.owner_id=%s OR (h.recipient_id=%s AND h.completed_at IS NOT NULL))'''+item_filter,(user_id,*args))
    for work in cursor.fetchall():
        subject = {key: work[key] for key in ('id','item_uid','name','edition_number','issue_total')}
        resale = work['kind']=='resale'
        if work['owner_id']==user_id:
            events.append(dict(subject,at=work['created_at'],event='resale_started' if resale else 'renewal_started'))
            verified = work['provisioned_at']
            if verified and (not work['completed_at'] or verified <= work['completed_at']):
                events.append(dict(subject,at=max(verified,work['created_at']),event='prepared'))
        if work['completed_at']:
            result = ('resold' if work['owner_id']==user_id else 'received') if resale else 'renewed'
            events.append(dict(subject,at=work['completed_at'],event=result))
    for event in events:
        event.pop('id')
        event['at'] = iso_time(event['at'])
    return sorted(events,key=lambda event:event['at'],reverse=True)


def item_history(cursor, item_id):
    cursor.execute('SELECT r.confirmed_at AS at FROM digital_item d JOIN product_issue r ON r.id=d.issue_id WHERE d.item_id=%s', (item_id,))
    issue = cursor.fetchone()
    events = [dict(at=issue['at'],event='issued')] if issue and issue['at'] else []
    cursor.execute('SELECT started_at,ended_at,spec FROM whole_item WHERE item_id=%s', (item_id,))
    for physical in cursor.fetchall():
        if physical['started_at']:
            events.append(dict(at=physical['started_at'],event='physical_started',spec=physical['spec']))
        if physical['ended_at']:
            events.append(dict(at=physical['ended_at'],event='physical_ended'))
    return [dict(event,at=iso_time(event['at'])) for event in sorted(events,key=lambda event:event['at'],reverse=True)]
