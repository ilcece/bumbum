"""从同一只读快照聚合有效事件，不更新业务、凭证、审计或芯片计数。"""

from datetime import datetime, time, timedelta, timezone

import pymysql

from core.auth_settings import iso_time
from core.db import get_database, tap_event_schema

BEIJING = timezone(timedelta(hours=8))


class StatisticsUnavailable(Exception):
    """已有库结构未就绪；不能把缺字段或约束当成零记录。"""


def snapshot_time(cursor):
    """数据库是本次截点的唯一来源；测试只替换此函数，不改业务库时钟。"""
    cursor.execute('SELECT UTC_TIMESTAMP(6) AS as_of')
    return cursor.fetchone()['as_of']


def load_statistics(cursor, filters):
    as_of = snapshot_time(cursor)
    today = as_of.replace(tzinfo=timezone.utc).astimezone(BEIJING).date()
    conditions = ["s.verify_result='pass'", 's.created_at<=%s']
    values = [as_of]
    if filters['project'] is not None:
        cursor.execute('SELECT id FROM project WHERE code=%s', (filters['project'],))
        project = cursor.fetchone()
        if project is None:
            raise StatisticsUnavailable
        conditions.append('s.project_id=%s')
        values.append(project['id'])
    coverage_where = ' AND '.join(conditions)
    cursor.execute('SELECT MIN(s.created_at) AS first_recorded_at FROM scan_log s WHERE ' + coverage_where, values)
    first = cursor.fetchone()['first_recorded_at']
    first_day = first.replace(tzinfo=timezone.utc).astimezone(BEIJING).date() if first else None
    start_day = first_day if filters['range'] == 'all' else today - timedelta(days=6 if filters['range'] == '7d' else 29)
    if start_day is not None:
        start = datetime.combine(start_day, time.min, BEIJING).astimezone(timezone.utc).replace(tzinfo=None)
        conditions.append('s.created_at>=%s')
        values.append(start)
    end = datetime.combine(today + timedelta(days=1), time.min, BEIJING).astimezone(timezone.utc).replace(tzinfo=None)
    conditions.append('s.created_at<%s')
    values.append(end)
    where = ' AND '.join(conditions)
    cursor.execute('SELECT COUNT(*) AS valid_taps,COUNT(DISTINCT s.item_id) AS touched_items FROM scan_log s WHERE ' + where, values)
    summary = cursor.fetchone()
    cursor.execute('SELECT DATE(s.created_at + INTERVAL 8 HOUR) AS day,COUNT(*) AS valid_taps FROM scan_log s WHERE ' + where + ' GROUP BY day ORDER BY day', values)
    days = {row['day']: row['valid_taps'] for row in cursor.fetchall()}
    daily = []
    if start_day is not None:
        for offset in range((today - start_day).days + 1):
            day = start_day + timedelta(days=offset)
            daily.append({'date': day.isoformat(), 'valid_taps': days.get(day, 0)})

    # 先聚合事件再关联唯一资料行；不能按当前芯片绑定反推，也不能让资料JOIN放大次数。
    grouped = 'SELECT s.project_id,s.item_id,COUNT(*) AS valid_taps,MAX(s.created_at) AS last_tap_at FROM scan_log s WHERE ' + where + ' GROUP BY s.project_id,s.item_id'
    joined = (' FROM (' + grouped + ") a JOIN item i ON i.id=a.item_id JOIN project p ON p.id=a.project_id "
              "LEFT JOIN fashion_item_profile f ON f.item_id=a.item_id AND p.code='fashion' "
              "LEFT JOIN jewelry_item_profile j ON j.item_id=a.item_id AND p.code='jewelry'")
    name = "CASE WHEN p.code='fashion' THEN f.name WHEN p.code='jewelry' THEN j.name ELSE NULL END"
    detail_values = list(values)
    if filters['q']:
        pattern = '%' + filters['q'].replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
        joined += " WHERE (i.item_uid LIKE %s ESCAPE '!' OR (" + name + ") LIKE %s ESCAPE '!')"
        detail_values.extend((pattern, pattern))
    cursor.execute('SELECT COUNT(*) AS total_items' + joined, detail_values)
    total = cursor.fetchone()['total_items']
    page_size = filters['page_size']
    total_pages = (total + page_size - 1) // page_size
    page = min(filters['page'], max(1, total_pages))
    cursor.execute('SELECT p.code AS project,i.item_uid,' + name + ' AS name,a.valid_taps,a.last_tap_at' + joined
                   + ' ORDER BY a.valid_taps DESC,a.last_tap_at DESC,i.item_uid ASC LIMIT %s OFFSET %s',
                   (*detail_values, page_size, (page - 1) * page_size))
    items = [{'project': row['project'], 'item_uid': row['item_uid'], 'name': row['name'].strip() or None if row['name'] is not None else None,
              'valid_taps': row['valid_taps'], 'last_tap_at': iso_time(row['last_tap_at'])} for row in cursor.fetchall()]
    return {'filters': {key: filters[key] for key in ('project', 'range', 'q')}, 'timezone': 'Asia/Shanghai', 'as_of': iso_time(as_of),
            'period': {'from_date': start_day.isoformat() if start_day else None, 'to_date': today.isoformat()},
            'first_recorded_at': iso_time(first) if first else None, 'summary': summary, 'daily': daily, 'items': items,
            'total_items': total, 'page': page, 'page_size': page_size, 'total_pages': total_pages, 'page_adjusted': page != filters['page']}


def read_statistics(filters):
    connection = get_database()
    # 门禁已进行只读会话查询，结束其隐式事务，不把旧快照带入统计。
    connection.rollback()
    try:
        with connection.cursor() as cursor:
            if tap_event_schema(cursor) != 'ready':
                raise StatisticsUnavailable
        connection.rollback()
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cursor.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            result = load_statistics(cursor, filters)
        connection.commit()
        return result
    except Exception:
        try:
            connection.rollback()
        except pymysql.MySQLError:
            pass
        raise
