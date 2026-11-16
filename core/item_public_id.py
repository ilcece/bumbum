"""H5 的随机物品标识与限期兼容的旧持有地址。"""

from datetime import datetime, timezone
from uuid import UUID

from flask import current_app


def resolve_item_id(cursor, ref):
    try:
        public_id = UUID(ref)
    except ValueError:
        return None
    if public_id.version != 4 or str(public_id) != ref:
        return None
    cursor.execute('SELECT id FROM item WHERE public_id=%s', (ref,))
    row = cursor.fetchone()
    return row['id'] if row else None


def legacy_holder_link_allowed():
    until = current_app.config['H5_LEGACY_ITEM_UNTIL']
    try:
        return datetime.now(timezone.utc) < datetime.fromisoformat(until)
    except (TypeError, ValueError):
        return False
