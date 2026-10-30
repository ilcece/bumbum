"""独立临时MySQL验证定向撤权、快照保护及初始化账号锁定。"""

import secrets
import subprocess
import uuid

import pymysql
from pymysql.constants import CLIENT
import pytest

from core import rds_accounts as accounts
from core.rds_database import schema_for_selected_database
from tests.conftest import ROOT


def grant(user, privileges, scope):
    return f'GRANT {privileges} ON {scope} TO `{user}`@`%`'


def baseline_grants(user):
    database = ', '.join(sorted(accounts.DML | accounts.DB_EXTRAS)) if user == accounts.APP_USER else 'ALL PRIVILEGES'
    return [grant(user, ', '.join(sorted(accounts.GLOBAL_STATIC)), '*.*'),
            grant(user, 'XA_RECOVER_ADMIN', '*.*'), grant(user, database, accounts.DB_SCOPE),
            *[grant(user, 'SELECT', scope) for scope in accounts.SYSTEM_SCOPES]]


@pytest.mark.parametrize('extra', [
    'GRANT SELECT ON `other_database`.* TO `bumbum_hz_test`@`%`',
    'GRANT SELECT ON `bumbum_hz_test`.* TO `bumbum_hz_test`@`%`',
    'GRANT FILE ON *.* TO `bumbum_hz_test`@`%`',
    'GRANT `unexpected_role`@`%` TO `bumbum_hz_test`@`%`',
    'GRANT SELECT ON `mysql`.`user` TO `bumbum_hz_test`@`%`',
    'GRANT SELECT ON *.* TO `bumbum_hz_test`@`%` WITH GRANT OPTION',
])
def test_unknown_authorization_never_becomes_revoke_sql(extra):
    with pytest.raises(accounts.AccountPreparationError):
        accounts.parse_grants(accounts.APP_USER, baseline_grants(accounts.APP_USER) + [extra])


def test_missing_application_dml_never_automatically_granted():
    with pytest.raises(accounts.AccountPreparationError, match='基础权限缺失'):
        accounts.parse_grants(accounts.APP_USER, [grant(accounts.APP_USER, 'SELECT', accounts.DB_SCOPE)])


def test_apply_requires_explicit_snapshot_before_password(monkeypatch):
    monkeypatch.setattr(accounts.getpass, 'getpass', lambda *args: pytest.fail('不能请求密码'))
    monkeypatch.setattr(pymysql, 'connect', lambda **kwargs: pytest.fail('不能连接'))
    assert accounts.main(['--ca', '/unused-public-ca', '--apply', '--confirm-database', 'production']) == 1


@pytest.fixture
def account_database(auth_database):
    """只在现有夹具新建的独占容器中添加合成账号和第二个专属库。"""
    command = auth_database['TEST_DOCKER_COMMAND']
    container = auth_database['TEST_CONTAINER']
    passwords = {user: secrets.token_hex(24) for user in (*accounts.USERS, accounts.OPS_USER)}

    def root_sql(sql):
        result = subprocess.run([*command, 'exec', '-i', container, 'sh', '-c',
                                 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot --protocol=socket'],
                                input=sql, text=True, capture_output=True, timeout=30)
        assert result.returncode == 0, '专属合成账号准备失败，不输出SQL或凭证'

    static = ('SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, RELOAD, PROCESS, REFERENCES, INDEX, ALTER, '
              'SHOW DATABASES, CREATE TEMPORARY TABLES, LOCK TABLES, EXECUTE, REPLICATION SLAVE, '
              'REPLICATION CLIENT, CREATE VIEW, SHOW VIEW, CREATE ROUTINE, ALTER ROUTINE, CREATE USER, EVENT, TRIGGER')
    setup = ['CREATE DATABASE bumbum_hz_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci',
             'USE bumbum_hz_test', schema_for_selected_database((ROOT / 'db/schema.sql').read_text())]
    setup += [f"CREATE USER '{user}'@'%' IDENTIFIED BY '{password}'" for user, password in passwords.items()]
    setup += [f'GRANT {static} ON *.* TO `{accounts.OPS_USER}`@`%` WITH GRANT OPTION']
    # 维护账号刻意不授予XA_RECOVER_ADMIN，模拟实际RDS高权限账号公开权限。
    for user in accounts.USERS:
        setup += baseline_grants(user)
    root_sql(';\n'.join(setup) + ';')

    def connect(user=accounts.OPS_USER):
        return pymysql.connect(host=auth_database['DB_HOST'], port=auth_database['DB_PORT'],
                               user=user, password=passwords[user], charset='utf8mb4',
                               connect_timeout=3, read_timeout=10, autocommit=True,
                               client_flag=CLIENT.MULTI_STATEMENTS)
    try:
        yield connect, root_sql
    finally:
        root_sql('DROP DATABASE bumbum_hz_test;\n' + '\n'.join(
            f"DROP USER IF EXISTS '{user}'@'%';" for user in passwords))


@pytest.mark.auth_database
def test_actual_revoke_lock_and_application_dml(account_database):
    connect, _ = account_database
    with connect() as connection:
        before = accounts.inspect_accounts(connection)
        assert len(accounts.account_plan(before)) == 30
        result = accounts.apply_accounts(connection, before['state']['server_uuid'], before['snapshot_sha256'])
        assert result['changes_applied'] == 30
        assert result['state']['accounts'][accounts.APP_USER] == {
            'locked': 'N', 'permissions': {'*.*': [], accounts.DB_SCOPE: sorted(accounts.DML)}}
        assert result['state']['accounts'][accounts.INIT_USER] == {
            'locked': 'Y', 'permissions': {'*.*': [], accounts.DB_SCOPE: ['ALL PRIVILEGES']}}
        assert accounts.account_plan(result) == []
        repeated = accounts.apply_accounts(connection, result['state']['server_uuid'], result['snapshot_sha256'])
        assert repeated['changes_applied'] == 0
    with connect(accounts.APP_USER) as connection, connection.cursor() as cursor:
        cursor.execute('START TRANSACTION')
        cursor.execute("UPDATE bumbum_hz_test.project SET name='synthetic-application-update' WHERE code='fashion'")
        assert cursor.rowcount == 1
        connection.rollback()
        with pytest.raises(pymysql.OperationalError) as error:
            cursor.execute('CREATE TABLE bumbum_hz_test.forbidden_table (id INT)')
        assert error.value.args[0] == 1142
    with pytest.raises(pymysql.OperationalError) as error:
        connect(accounts.INIT_USER)
    assert error.value.args[0] == 3118


@pytest.mark.auth_database
def test_wrong_uuid_or_stale_snapshot_preserves_all_grants(account_database):
    connect, root_sql = account_database
    with connect() as connection:
        before = accounts.inspect_accounts(connection)
        with pytest.raises(accounts.AccountPreparationError, match='快照已变化'):
            accounts.apply_accounts(connection, str(uuid.uuid4()), before['snapshot_sha256'])
        assert accounts.inspect_accounts(connection) == before
        root_sql(f'REVOKE EVENT ON {accounts.DB_SCOPE} FROM `{accounts.APP_USER}`@`%`;')
        changed = accounts.inspect_accounts(connection)
        with pytest.raises(accounts.AccountPreparationError, match='快照已变化'):
            accounts.apply_accounts(connection, before['state']['server_uuid'], before['snapshot_sha256'])
        assert accounts.inspect_accounts(connection) == changed


@pytest.mark.auth_database
def test_unapproved_grant_or_partial_failure_stops_without_regrant(account_database, monkeypatch):
    connect, root_sql = account_database
    with connect() as connection:
        root_sql(f'GRANT SELECT ON mysql.user TO `{accounts.APP_USER}`@`%`;')
        with pytest.raises(accounts.AccountPreparationError, match='未批准'):
            accounts.inspect_accounts(connection)
        root_sql(f'REVOKE SELECT ON mysql.user FROM `{accounts.APP_USER}`@`%`;')
        before = accounts.inspect_accounts(connection)
        execute = pymysql.cursors.Cursor.execute
        calls = []

        def fail_second_revoke(cursor, sql, args=None):
            if sql.startswith('REVOKE '):
                calls.append(sql)
                if len(calls) == 2:
                    raise pymysql.OperationalError(1227, '合成权限不足')
            return execute(cursor, sql, args)

        with monkeypatch.context() as patch:
            patch.setattr(pymysql.cursors.Cursor, 'execute', fail_second_revoke)
            with pytest.raises(pymysql.OperationalError):
                accounts.apply_accounts(connection, before['state']['server_uuid'], before['snapshot_sha256'])
        after = accounts.inspect_accounts(connection)
        assert len(calls) == 2
        assert after['state']['accounts'][accounts.APP_USER]['permissions'][accounts.DB_SCOPE] == sorted(accounts.DML)
        assert after['state']['accounts'][accounts.INIT_USER] == before['state']['accounts'][accounts.INIT_USER]
        assert set(after['state']['accounts'][accounts.APP_USER]['permissions']['*.*']) == accounts.GLOBAL_STATIC | accounts.GLOBAL_DYNAMIC
        with connection.cursor() as cursor:
            cursor.execute("SELECT IS_USED_LOCK('bumbum.rds-accounts.bumbum_hz_test'),IS_USED_LOCK('bumbum.rds-init.bumbum_hz_test')")
            assert cursor.fetchone() == (None, None)
