from copy import deepcopy

import pytest

from core import order_migration, passkey_migration
from core.catalog_migration import CatalogMigrationError
from core.db import get_database
from core.schema_checks import structure_state
from tests.test_admin_auth import query
from tests.test_admin_catalog import action, ok
from tests.test_admin_chips import logged_in


class MetadataCursor:
    def __init__(self, columns, indexes, references, definitions):
        self.metadata = [columns, indexes, references]
        self.definitions = definitions
        self.calls = []

    def execute(self, statement, args=()):
        assert statement.startswith(('SELECT ', 'SHOW CREATE TABLE '))
        if statement.startswith('SELECT '):
            assert 'DATABASE()' in statement
        else:
            assert not args
        self.calls.append((statement, args))

    def fetchall(self):
        return self.metadata[len(self.calls) - 1]

    def fetchone(self):
        name = self.calls[-1][0].removeprefix('SHOW CREATE TABLE ').strip('`')
        return name, self.definitions[name]


@pytest.fixture
def guarded_structure():
    columns = {
        ('records', 'id'): ('bigint unsigned', 'NO', 'auto_increment'),
        ('records', 'owner_id'): ('bigint unsigned', 'YES', ''),
        ('records', 'code'): ('varchar(64)', 'NO', ''),
        ('records', 'scope'): ('bigint unsigned', 'YES', 'STORED GENERATED'),
        ('records', 'created_at'): ('datetime(6)', 'NO', 'DEFAULT_GENERATED'),
    }
    keys = {('records', 'PRIMARY'): ('id',), ('records', 'unique_code'): ('scope', 'code')}
    references = {('records', 'fk_owner', 'owner_id', 'owners', 'id', 1, 'CASCADE', 'RESTRICT')}
    metadata = [
        [('records', 'id', 'bigint unsigned', 'NO', 'auto_increment', '', None),
         ('records', 'owner_id', 'bigint unsigned', 'YES', '', '', None),
         ('records', 'code', 'varchar(64)', 'NO', '', '', None),
         ('records', 'scope', 'bigint unsigned', 'YES', 'STORED GENERATED', 'coalesce(`owner_id`,0)', None),
         ('records', 'created_at', 'datetime(6)', 'NO', 'DEFAULT_GENERATED', '', 'current_timestamp(6)')],
        [('records', 'PRIMARY', 0, 'id', 1, None),
         ('records', 'unique_code', 0, 'scope', 1, None),
         ('records', 'unique_code', 0, 'code', 2, None)],
        [('records', 'fk_owner', 'owner_id', 'owners', 'id', 1, 'CASCADE', 'NO ACTION')],
    ]
    definition = '''CREATE TABLE `records` (
      `id` bigint unsigned NOT NULL AUTO_INCREMENT,
      `owner_id` bigint unsigned DEFAULT NULL,
      `code` varchar(64) NOT NULL,
      `scope` bigint unsigned GENERATED ALWAYS AS (coalesce(`owner_id`,0)) STORED,
      `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (`id`)
    )'''

    def inspect(values=None, ddl=None):
        cursor = MetadataCursor(*(metadata if values is None else values),
                                definitions={'records': definition if ddl is None else ddl})
        result = structure_state(cursor, columns, keys, references,
                                 generated={('records', 'scope'): 'coalesce(owner_id,0)'},
                                 defaults={('records', 'created_at'): 'CURRENT_TIMESTAMP(6)'})
        return result, cursor

    return metadata, inspect


def test_readiness_accepts_only_complete_metadata_and_reads_without_mutation(guarded_structure):
    _, inspect = guarded_structure
    result, cursor = inspect()
    assert result == 'ready'
    assert len(cursor.calls) == 4
    assert all(args == ['records'] for _, args in cursor.calls[:3])
    assert cursor.calls[-1] == ('SHOW CREATE TABLE `records`', ())


def test_readiness_distinguishes_missing_columns_from_partial_structure(guarded_structure):
    metadata, inspect = guarded_structure
    assert inspect([[], [], []])[0] == 'missing'
    partial = deepcopy(metadata)
    partial[0].pop()
    assert inspect(partial)[0] == 'unknown'


@pytest.mark.parametrize(('section', 'position', 'replacement'), [
    (0, 0, ('records', 'id', 'bigint unsigned', 'NO', '', '', None)),
    (0, 2, ('records', 'code', 'varchar(32)', 'NO', '', '', None)),
    (0, 2, ('records', 'code', 'varchar(64)', 'YES', '', '', None)),
    (0, 3, ('records', 'scope', 'bigint unsigned', 'YES', 'STORED GENERATED', 'coalesce(`owner_id`,1)', None)),
    (0, 4, ('records', 'created_at', 'datetime(6)', 'NO', 'DEFAULT_GENERATED', '', 'current_timestamp(3)')),
    (0, 4, ('records', 'created_at', 'datetime(6)', 'NO', 'DEFAULT_GENERATED', '', 'now(6) + interval 1 day')),
    (0, 2, ('records', 'code', 'varchar(64)', 'NO', '', '', 'NULL')),
    (0, 2, ('records', 'code', 'varchar(64)', 'NO', '', '', '')),
    (1, 2, ('records', 'unique_code', 1, 'code', 2, None)),
    (1, 2, ('records', 'unique_code', 0, 'code', 2, 16)),
    (1, 2, ('records', 'unique_code', 0, 'owner_id', 2, None)),
    (2, 0, ('records', 'fk_owner', 'owner_id', 'owners', 'id', 1, 'RESTRICT', 'NO ACTION')),
    (2, 0, ('records', 'fk_owner', 'owner_id', 'other_owners', 'id', 1, 'CASCADE', 'NO ACTION')),
    (2, 0, ('records', 'fk_owner', 'owner_id', 'owners', 'id', 1, 'CASCADE', 'CASCADE')),
], ids=['missing-auto-increment', 'wrong-type', 'wrong-nullability', 'wrong-generated-scope',
        'wrong-default-precision', 'shifted-time-default', 'literal-null-default', 'empty-default',
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


def test_readiness_rejects_additional_unique_constraints(guarded_structure):
    metadata, inspect = guarded_structure
    damaged = deepcopy(metadata)
    damaged[1].append(('records', 'unexpected_code', 0, 'code', 1, None))
    assert inspect(damaged)[0] == 'unknown'


def test_readiness_allows_additional_non_unique_performance_indexes(guarded_structure):
    metadata, inspect = guarded_structure
    extended = deepcopy(metadata)
    extended[1].extend([
        ('records', 'lookup_code', 1, 'code', 1, 16),
        ('records', 'lookup_expression', 1, None, 1, None),
    ])
    assert inspect(extended)[0] == 'ready'


def test_readiness_accepts_default_expression_case_and_outer_whitespace(guarded_structure):
    metadata, inspect = guarded_structure
    equivalent = deepcopy(metadata)
    equivalent[0][4] = (*equivalent[0][4][:-1], ' CURRENT_TIMESTAMP(6) ')
    assert inspect(equivalent)[0] == 'ready'


@pytest.mark.parametrize('declaration', [
    '`owner_id` bigint unsigned,',
    "`owner_id` bigint unsigned COMMENT 'DEFAULT NULL',",
    '`owner_id_archive` bigint unsigned DEFAULT NULL,',
], ids=['missing-null-default', 'null-only-in-comment', 'null-only-in-another-column'])
def test_readiness_checks_null_default_on_the_exact_column(guarded_structure, declaration):
    _, inspect = guarded_structure
    ddl = 'CREATE TABLE `records` (\n' + declaration + '\n)'
    assert inspect(ddl=ddl)[0] == 'unknown'


@pytest.mark.parametrize('column_name', ['`owner_id`', '"owner_id"', 'owner_id'])
def test_readiness_accepts_known_column_quote_styles(guarded_structure, column_name):
    _, inspect = guarded_structure
    ddl = 'CREATE TABLE `records` (\n' + column_name + ' bigint unsigned DEFAULT NULL,\n)'
    assert inspect(ddl=ddl)[0] == 'ready'


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
    (order_migration.schema, order_migration.migrate,
     'ALTER TABLE sales_order ADD UNIQUE KEY unexpected_global_order_no(external_order_no)',
     'ALTER TABLE sales_order DROP INDEX unexpected_global_order_no'),
    (order_migration.schema, order_migration.migrate,
     'ALTER TABLE sales_order ALTER COLUMN created_at SET DEFAULT (CURRENT_TIMESTAMP(6) + INTERVAL 1 DAY)',
     'ALTER TABLE sales_order MODIFY created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)'),
    (passkey_migration.schema, passkey_migration.migrate,
     'ALTER TABLE admin_passkey ADD UNIQUE KEY unexpected_sign_count(sign_count)',
     'ALTER TABLE admin_passkey DROP INDEX unexpected_sign_count'),
    (order_migration.match_schema, order_migration.migrate,
     'ALTER TABLE sales_order_unit_match ADD UNIQUE KEY unexpected_style_spec(spec,style_id)',
     'ALTER TABLE sales_order_unit_match DROP INDEX unexpected_style_spec'),
    (order_migration.schema, order_migration.migrate,
     "ALTER TABLE sales_order_unit ALTER COLUMN delivered_at SET DEFAULT '2030-01-01 00:00:00'",
     'ALTER TABLE sales_order_unit ALTER COLUMN delivered_at SET DEFAULT NULL'),
    (passkey_migration.schema, passkey_migration.migrate,
     "ALTER TABLE admin_passkey ALTER COLUMN revoked_at SET DEFAULT '2030-01-01 00:00:00'",
     'ALTER TABLE admin_passkey ALTER COLUMN revoked_at SET DEFAULT NULL'),
    (order_migration.schema, order_migration.migrate,
     'ALTER TABLE sales_order_unit ALTER COLUMN delivered_at DROP DEFAULT',
     'ALTER TABLE sales_order_unit ALTER COLUMN delivered_at SET DEFAULT NULL'),
    (passkey_migration.schema, passkey_migration.migrate,
     'ALTER TABLE admin_passkey ALTER COLUMN revoked_at DROP DEFAULT',
     'ALTER TABLE admin_passkey ALTER COLUMN revoked_at SET DEFAULT NULL'),
], ids=['passkey-type', 'passkey-unique', 'passkey-reference', 'passkey-cascade', 'order-generated-scope',
        'order-item-unique', 'match-type', 'match-reference', 'order-extra-global-unique',
        'order-shifted-created-at-default', 'passkey-extra-unique', 'match-extra-unique',
        'order-delivery-default', 'passkey-revocation-default', 'order-missing-null-default',
        'passkey-missing-null-default'])
def test_migration_refuses_real_damaged_schema(auth_app, checker, migration, damage, restore):
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            assert checker(cursor) == 'ready'
            for statement in (damage,) if isinstance(damage, str) else damage:
                cursor.execute(statement)
            try:
                assert auth_app.test_client().get('/api/ready').status_code == 503
                assert checker(cursor) == 'unknown'
                with pytest.raises(CatalogMigrationError):
                    migration(connection, lambda: pytest.fail('未知结构不能备份后自动修复'))
            finally:
                for statement in (restore,) if isinstance(restore, str) else restore:
                    cursor.execute(statement)
            assert checker(cursor) == 'ready'
            assert auth_app.test_client().get('/api/ready').status_code == 200


@pytest.mark.auth_database
def test_readiness_allows_performance_indexes_and_preserves_order_scope_and_time(auth_app, logged_in):
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE sales_order ADD KEY readiness_lookup(external_order_no)')
    try:
        assert logged_in[0].get('/api/ready').status_code == 200
        earliest = query(auth_app, 'SELECT UTC_TIMESTAMP(6) AS moment')[0]['moment']
        request = {'external_order_no': 'SAME-EXTERNAL-NUMBER', 'units': [{'product_name': '测试商品'}]}
        first = ok(action(logged_in, 'createOrder', {'channel': '品牌店铺', **request}))
        second = ok(action(logged_in, 'createOrder', {'channel': '线下展会', **request}))
        assert first['id'] != second['id']
        assert action(logged_in, 'createOrder', {'channel': '品牌店铺', **request}).status_code == 409
        timestamps = query(auth_app, 'SELECT created_at FROM sales_order ORDER BY id')
        latest = query(auth_app, 'SELECT UTC_TIMESTAMP(6) AS moment')[0]['moment']
        assert len(timestamps) == 2
        assert all(earliest <= value['created_at'] <= latest for value in timestamps)
        assert logged_in[0].get('/api/ready').status_code == 200
    finally:
        with auth_app.app_context():
            with get_database().cursor() as cursor:
                cursor.execute('ALTER TABLE sales_order DROP INDEX readiness_lookup')


@pytest.mark.auth_database
def test_readiness_accepts_mysql_unquoted_show_create(auth_app):
    with auth_app.app_context():
        connection = get_database()
        with connection.cursor() as cursor:
            cursor.execute('SELECT @@SESSION.sql_quote_show_create')
            original = cursor.fetchone()[0]
            cursor.execute('SET SESSION sql_quote_show_create=0')
            try:
                assert order_migration.schema(cursor) == 'ready'
                assert order_migration.match_schema(cursor) == 'ready'
                assert passkey_migration.schema(cursor) == 'ready'
                assert auth_app.test_client().get('/api/ready').status_code == 200
            finally:
                cursor.execute('SET SESSION sql_quote_show_create=%s', (original,))
