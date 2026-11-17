from copy import deepcopy

import pytest

from core import order_migration, passkey_migration
from core.catalog_migration import CatalogMigrationError
from core.db import get_database
from core.schema_checks import structure_state


class MetadataCursor:
    def __init__(self, columns, indexes, references):
        self.metadata = [columns, indexes, references]
        self.calls = []

    def execute(self, statement, args):
        assert statement.startswith('SELECT ')
        assert 'DATABASE()' in statement
        self.calls.append((statement, args))

    def fetchall(self):
        return self.metadata[len(self.calls) - 1]


@pytest.fixture
def guarded_structure():
    columns = {
        ('records', 'id'): ('bigint unsigned', 'NO', 'auto_increment'),
        ('records', 'owner_id'): ('bigint unsigned', 'YES', ''),
        ('records', 'code'): ('varchar(64)', 'NO', ''),
        ('records', 'scope'): ('bigint unsigned', 'YES', 'STORED GENERATED'),
    }
    keys = {('records', 'PRIMARY'): ('id',), ('records', 'unique_code'): ('scope', 'code')}
    references = {('records', 'fk_owner', 'owner_id', 'owners', 'id', 1, 'CASCADE', 'RESTRICT')}
    metadata = [
        [('records', 'id', 'bigint unsigned', 'NO', 'auto_increment', ''),
         ('records', 'owner_id', 'bigint unsigned', 'YES', '', ''),
         ('records', 'code', 'varchar(64)', 'NO', '', ''),
         ('records', 'scope', 'bigint unsigned', 'YES', 'STORED GENERATED', 'coalesce(`owner_id`,0)')],
        [('records', 'PRIMARY', 0, 'id', 1, None),
         ('records', 'unique_code', 0, 'scope', 1, None),
         ('records', 'unique_code', 0, 'code', 2, None)],
        [('records', 'fk_owner', 'owner_id', 'owners', 'id', 1, 'CASCADE', 'NO ACTION')],
    ]

    def inspect(values=None):
        cursor = MetadataCursor(*(metadata if values is None else values))
        result = structure_state(cursor, columns, keys, references,
                                 generated={('records', 'scope'): 'coalesce(owner_id,0)'})
        return result, cursor

    return metadata, inspect


def test_readiness_accepts_only_complete_metadata_and_reads_without_mutation(guarded_structure):
    _, inspect = guarded_structure
    result, cursor = inspect()
    assert result == 'ready'
    assert len(cursor.calls) == 3
    assert all(args == ['records'] for _, args in cursor.calls)


def test_readiness_distinguishes_missing_columns_from_partial_structure(guarded_structure):
    metadata, inspect = guarded_structure
    assert inspect([[], [], []])[0] == 'missing'
    partial = deepcopy(metadata)
    partial[0].pop()
    assert inspect(partial)[0] == 'unknown'


@pytest.mark.parametrize(('section', 'position', 'replacement'), [
    (0, 0, ('records', 'id', 'bigint unsigned', 'NO', '', '')),
    (0, 2, ('records', 'code', 'varchar(32)', 'NO', '', '')),
    (0, 2, ('records', 'code', 'varchar(64)', 'YES', '', '')),
    (0, 3, ('records', 'scope', 'bigint unsigned', 'YES', 'STORED GENERATED', 'coalesce(`owner_id`,1)')),
    (1, 2, ('records', 'unique_code', 1, 'code', 2, None)),
    (1, 2, ('records', 'unique_code', 0, 'code', 2, 16)),
    (1, 2, ('records', 'unique_code', 0, 'owner_id', 2, None)),
    (2, 0, ('records', 'fk_owner', 'owner_id', 'owners', 'id', 1, 'RESTRICT', 'NO ACTION')),
    (2, 0, ('records', 'fk_owner', 'owner_id', 'other_owners', 'id', 1, 'CASCADE', 'NO ACTION')),
    (2, 0, ('records', 'fk_owner', 'owner_id', 'owners', 'id', 1, 'CASCADE', 'CASCADE')),
], ids=['missing-auto-increment', 'wrong-type', 'wrong-nullability', 'wrong-generated-scope',
        'non-unique-index', 'prefix-only-index', 'wrong-index-column', 'wrong-delete-rule',
        'wrong-referenced-table', 'wrong-update-rule'])
def test_readiness_rejects_incompatible_metadata(guarded_structure, section, position, replacement):
    metadata, inspect = guarded_structure
    damaged = deepcopy(metadata)
    damaged[section][position] = replacement
    assert inspect(damaged)[0] == 'unknown'


@pytest.mark.parametrize('section', [1, 2], ids=['missing-unique-index', 'missing-foreign-key'])
def test_readiness_requires_key_and_reference_metadata(guarded_structure, section):
    metadata, inspect = guarded_structure
    damaged = deepcopy(metadata)
    damaged[section] = []
    assert inspect(damaged)[0] == 'unknown'


@pytest.mark.auth_database
@pytest.mark.parametrize(('checker', 'migration', 'damage', 'restore'), [
    (passkey_migration.schema, passkey_migration.migrate,
     'ALTER TABLE admin_passkey MODIFY public_key VARBINARY(2048) NOT NULL',
     'ALTER TABLE admin_passkey MODIFY public_key VARBINARY(4096) NOT NULL'),
    (passkey_migration.schema, passkey_migration.migrate,
     'ALTER TABLE admin_passkey DROP INDEX credential_hash, ADD KEY credential_hash(credential_hash)',
     'ALTER TABLE admin_passkey DROP INDEX credential_hash, ADD UNIQUE KEY credential_hash(credential_hash)'),
    (passkey_migration.schema, passkey_migration.migrate,
     'ALTER TABLE admin_passkey DROP FOREIGN KEY fk_passkey_admin',
     'ALTER TABLE admin_passkey ADD CONSTRAINT fk_passkey_admin FOREIGN KEY(admin_id) REFERENCES admin_user(id) ON DELETE CASCADE'),
    (passkey_migration.schema, passkey_migration.migrate,
     ('ALTER TABLE admin_passkey DROP FOREIGN KEY fk_passkey_admin',
      'ALTER TABLE admin_passkey ADD CONSTRAINT fk_passkey_admin FOREIGN KEY(admin_id) REFERENCES admin_user(id)'),
     ('ALTER TABLE admin_passkey DROP FOREIGN KEY fk_passkey_admin',
      'ALTER TABLE admin_passkey ADD CONSTRAINT fk_passkey_admin FOREIGN KEY(admin_id) REFERENCES admin_user(id) ON DELETE CASCADE')),
    (order_migration.schema, order_migration.migrate,
     'ALTER TABLE sales_order MODIFY source_scope BIGINT UNSIGNED GENERATED ALWAYS AS (COALESCE(test_batch_id,1)) STORED',
     'ALTER TABLE sales_order MODIFY source_scope BIGINT UNSIGNED GENERATED ALWAYS AS (COALESCE(test_batch_id,0)) STORED'),
    (order_migration.schema, order_migration.migrate,
     'ALTER TABLE sales_order_unit ADD KEY readiness_item(item_id), DROP INDEX item_id',
     'ALTER TABLE sales_order_unit ADD UNIQUE KEY item_id(item_id), DROP INDEX readiness_item'),
    (order_migration.match_schema, order_migration.migrate,
     'ALTER TABLE sales_order_unit_match MODIFY spec VARCHAR(128) NULL',
     'ALTER TABLE sales_order_unit_match MODIFY spec VARCHAR(256) NULL'),
    (order_migration.match_schema, order_migration.migrate,
     'ALTER TABLE sales_order_unit_match DROP FOREIGN KEY fk_order_match_unit',
     'ALTER TABLE sales_order_unit_match ADD CONSTRAINT fk_order_match_unit FOREIGN KEY(unit_id) REFERENCES sales_order_unit(id) ON DELETE CASCADE'),
], ids=['passkey-type', 'passkey-unique', 'passkey-reference', 'passkey-cascade', 'order-generated-scope',
        'order-item-unique', 'match-type', 'match-reference'])
def test_migration_refuses_real_damaged_schema(auth_app, checker, migration, damage, restore):
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            assert checker(cursor) == 'ready'
            for statement in (damage,) if isinstance(damage, str) else damage:
                cursor.execute(statement)
            try:
                assert checker(cursor) == 'unknown'
                with pytest.raises(CatalogMigrationError):
                    migration(connection, lambda: pytest.fail('未知结构不能备份后自动修复'))
            finally:
                for statement in (restore,) if isinstance(restore, str) else restore:
                    cursor.execute(statement)
            assert checker(cursor) == 'ready'
