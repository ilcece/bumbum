"""用独立 MySQL 验证旧物品补标识及默认生成规则。"""

from uuid import UUID

import pytest

from core.db import get_database
from core.h5_identity_migration import migrate, schema
from tests.test_admin_auth import query


@pytest.mark.auth_database
def test_existing_items_keep_identity_and_new_items_get_uuid4(auth_app):
    query(auth_app, "ALTER TABLE scan_log DROP FOREIGN KEY fk_scan_actor, DROP COLUMN actor_user_uid, DROP COLUMN actor_state")
    query(auth_app, "ALTER TABLE item DROP COLUMN public_id")
    query(auth_app, "INSERT INTO item(project_id,item_uid) VALUES (1,'IDENTITY-OLD-A'),(1,'IDENTITY-OLD-B')")
    original = query(auth_app, "SELECT id,item_uid,updated_at FROM item ORDER BY id")
    with auth_app.app_context():
        db = get_database()
        with db.cursor() as cursor:
            assert schema(cursor) == 'missing'
        backups = []
        assert migrate(db, lambda: backups.append(True))
        assert not migrate(db, lambda: pytest.fail('完成后不重复备份或回填'))
        assert backups == [True]
        with db.cursor() as cursor:
            assert schema(cursor) == 'ready'
    assert query(auth_app, "SELECT id,item_uid,updated_at FROM item ORDER BY id") == original
    query(auth_app, "INSERT INTO item(project_id,item_uid) VALUES (1,'IDENTITY-NEW')")
    ids = [UUID(row['public_id']) for row in query(auth_app, "SELECT public_id FROM item ORDER BY id")]
    assert len(set(ids)) == 3 and all(identifier.version == 4 for identifier in ids)
