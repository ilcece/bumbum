"""杭州测试账号的定向权限收敛；不修改密码、业务数据或其他账号。"""

import argparse
from copy import deepcopy
import getpass
import hashlib
import json
import re
import sys
import uuid

import pymysql

from core.db import TARGET_TABLES, database_tls_options
from core.rds_target import RDS_HOST, SLOTS

DATABASE = SLOTS['test']['database']
APP_USER = SLOTS['test']['user']
INIT_USER = APP_USER + '_init'
OPS_USER = 'bumbum_hz_ops'
USERS = (APP_USER, INIT_USER)
DB_SCOPE = r'`bumbum\_hz\_test`.*'
DML = {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}
DB_EXTRAS = {'CREATE TEMPORARY TABLES', 'LOCK TABLES', 'EXECUTE', 'SHOW VIEW', 'EVENT', 'TRIGGER'}
GLOBAL_STATIC = {'PROCESS', 'REPLICATION SLAVE', 'REPLICATION CLIENT'}
GLOBAL_DYNAMIC = {'XA_RECOVER_ADMIN'}
SYSTEM_TABLES = ('func', 'general_log', 'help_category', 'help_keyword', 'help_relation',
                 'help_topic', 'slow_log', 'time_zone_leap_second', 'time_zone_name',
                 'time_zone_transition', 'time_zone_transition_type', 'time_zone')
SYSTEM_SCOPES = tuple('`mysql`.`' + table + '`' for table in SYSTEM_TABLES)


class AccountPreparationError(Exception):
    """只返回明确、可公开的停止原因，不显示原始异常或认证资料。"""


def parse_grants(user, statements):
    """只认已审阅的两个身份与权限范围；未知角色、授权选项或资源全部拒绝。"""
    if user not in USERS:
        raise AccountPreparationError('账号超出已批准范围。')
    result = {'*.*': set()}
    for statement in statements:
        match = re.fullmatch(r'GRANT (.+) ON (.+) TO `' + re.escape(user) + r'`@`%`', statement)
        if not match:
            raise AccountPreparationError('授权格式、角色或授权选项超出已核对范围。')
        privileges = {part.strip() for part in match[1].split(',')}
        scope = match[2]
        if scope == '*.*':
            allowed = GLOBAL_STATIC | GLOBAL_DYNAMIC | {'USAGE'}
            privileges.discard('USAGE')
        elif scope == DB_SCOPE:
            allowed = DML | DB_EXTRAS if user == APP_USER else {'ALL PRIVILEGES'}
        elif scope in SYSTEM_SCOPES:
            allowed = {'SELECT'}
        else:
            raise AccountPreparationError('发现未批准的数据库、系统表或授权范围。')
        if not privileges <= allowed:
            raise AccountPreparationError('发现未批准的额外权限，停止而不猜测撤回。')
        result.setdefault(scope, set()).update(privileges)
    required = DML if user == APP_USER else {'ALL PRIVILEGES'}
    if not required <= result.get(DB_SCOPE, set()):
        raise AccountPreparationError('目标库基础权限缺失，不自动补权。')
    return {scope: sorted(values) for scope, values in sorted(result.items())}


def inspect_accounts(connection):
    """只读取固定实例、已初始化结构、公开授权及锁定状态，不读认证字段。"""
    with connection.cursor() as cursor:
        cursor.execute('SELECT CURRENT_USER(),@@server_uuid,VERSION()')
        actor, server_uuid, version = cursor.fetchone()
        if actor != OPS_USER + '@%' or not re.fullmatch(r'8\.0\.(\d+).*', version):
            raise AccountPreparationError('维护身份或MySQL版本不符。')
        cursor.execute('SELECT DEFAULT_CHARACTER_SET_NAME,DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s', (DATABASE,))
        if cursor.fetchone() != ('utf8mb4', 'utf8mb4_unicode_ci'):
            raise AccountPreparationError('测试库字符集或排序规则不符。')
        cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s', (DATABASE,))
        if {row[0] for row in cursor.fetchall()} != TARGET_TABLES:
            raise AccountPreparationError('目标测试库不是已确认的24表结构。')
        cursor.execute('SELECT code FROM bumbum_hz_test.project ORDER BY id')
        if cursor.fetchall() != (('fashion',), ('jewelry',)):
            raise AccountPreparationError('初始项目与已验收结果不同。')
        cursor.execute('SELECT User,Host,account_locked FROM mysql.user WHERE User IN (%s,%s,%s)', (*USERS, OPS_USER))
        rows = cursor.fetchall()
        if {(row[0], row[1]) for row in rows} != {(user, '%') for user in (*USERS, OPS_USER)} or len(rows) != 3:
            raise AccountPreparationError('目标账号缺失或存在其他Host条目，停止核对。')
        locks = {row[0]: row[2] for row in rows}
        if locks[APP_USER] != 'N' or locks[OPS_USER] != 'N' or locks[INIT_USER] not in {'N', 'Y'}:
            raise AccountPreparationError('应用、维护或初始化账号锁定状态不符。')
        grants, accounts = {}, {}
        for user in USERS:
            cursor.execute('SHOW GRANTS FOR %s@%s', (user, '%'))
            grants[user] = [row[0] for row in cursor.fetchall()]
            accounts[user] = {'locked': locks[user], 'permissions': parse_grants(user, grants[user])}
    state = {'server_uuid': server_uuid, 'actor': actor, 'accounts': accounts}
    digest = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'database': DATABASE, 'mysql_version': version, 'state': state,
            'grants': grants, 'snapshot_sha256': digest}


def account_plan(report):
    """只生成定向撤回及锁定动作；不提供授予、重置密码或删除入口。"""
    actions = []
    for user in USERS:
        permissions = report['state']['accounts'][user]['permissions']
        scopes = [(DB_SCOPE, DB_EXTRAS)] if user == APP_USER else []
        scopes += [('*.*', GLOBAL_STATIC), ('*.*', GLOBAL_DYNAMIC)]
        scopes += [(scope, {'SELECT'}) for scope in SYSTEM_SCOPES]
        for scope, removable in scopes:
            values = sorted(set(permissions.get(scope, [])) & removable)
            if values:
                actions.append({'user': user, 'scope': scope, 'revoke': values})
    if report['state']['accounts'][INIT_USER]['locked'] == 'N':
        actions.append({'user': INIT_USER, 'lock': True})
    return actions


def apply_accounts(connection, expected_uuid, expected_snapshot):
    """快照必须匹配；加锁后逐项验证，失败保留现场，不自动重跑或补权。"""
    held = []
    with connection.cursor() as cursor:
        try:
            for lock in ('bumbum.rds-accounts.' + DATABASE, 'bumbum.rds-init.' + DATABASE):
                cursor.execute('SELECT GET_LOCK(%s,5)', (lock,))
                if cursor.fetchone()[0] != 1:
                    raise AccountPreparationError('账号维护或初始化锁被占用，未继续。')
                held.append(lock)
            before = inspect_accounts(connection)
            if before['state']['server_uuid'] != expected_uuid or before['snapshot_sha256'] != expected_snapshot:
                raise AccountPreparationError('实例或公开授权快照已变化，未执行权限变更。')
            expected = deepcopy(before['state'])
            actions = account_plan(before)
            after = before
            for action in actions:
                user = action['user']
                if action.get('lock'):
                    cursor.execute('ALTER USER %s@%s ACCOUNT LOCK', (user, '%'))
                    expected['accounts'][user]['locked'] = 'Y'
                else:
                    scope, values = action['scope'], action['revoke']
                    # 权限和资源只来自上方固定白名单，账号仍使用驱动绑定参数。
                    cursor.execute('REVOKE ' + ', '.join(values) + ' ON ' + scope + ' FROM %s@%s', (user, '%'))
                    remaining = set(expected['accounts'][user]['permissions'][scope]) - set(values)
                    if remaining or scope == '*.*':
                        expected['accounts'][user]['permissions'][scope] = sorted(remaining)
                    else:
                        del expected['accounts'][user]['permissions'][scope]
                after = inspect_accounts(connection)
                if after['state'] != expected:
                    raise AccountPreparationError('权限或锁定状态出现预期外变化，停止并保留现场。')
            if account_plan(after):
                raise AccountPreparationError('仍有待收敛权限，保留现场，不自动补权。')
            after.update(changes_applied=len(actions), before_snapshot_sha256=before['snapshot_sha256'])
            return after
        finally:
            for lock in reversed(held):
                cursor.execute('SELECT RELEASE_LOCK(%s)', (lock,))


def main(argv=None):
    parser = argparse.ArgumentParser(description='杭州两个测试账号的公开预检或明确确认后的定向收敛。')
    parser.add_argument('--ca', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-database')
    parser.add_argument('--confirm-server-uuid')
    parser.add_argument('--confirm-snapshot-sha256')
    args = parser.parse_args(argv)
    try:
        if args.apply:
            if args.confirm_database != DATABASE or not re.fullmatch('[0-9a-f]{64}', args.confirm_snapshot_sha256 or ''):
                raise AccountPreparationError('须明确测试库及已保存的公开授权快照SHA256。')
            uuid.UUID(args.confirm_server_uuid or '')
        tls = database_tls_options({'DB_SSL_MODE': 'VERIFY_IDENTITY', 'DB_SSL_CA': args.ca})
        if not sys.stdin.isatty():
            raise AccountPreparationError('请在受控终端隐藏输入维护密码，不从环境、配置或管道取密码。')
        password = getpass.getpass('RDS专用维护账号密码（不回显）：')
        if not password:
            raise AccountPreparationError('未输入密码，未连接。')
        with pymysql.connect(host=RDS_HOST, port=3306, user=OPS_USER, password=password,
                             charset='utf8mb4', connect_timeout=5, read_timeout=30, write_timeout=10,
                             autocommit=True, **tls) as connection:
            cipher = connection._sock.cipher() if hasattr(connection._sock, 'cipher') else None
            if not cipher:
                raise AccountPreparationError('没有客户端TLS证据，未继续。')
            if args.apply:
                report = apply_accounts(connection, args.confirm_server_uuid, args.confirm_snapshot_sha256)
            else:
                report = inspect_accounts(connection)
                report['planned_actions'] = account_plan(report)
            report.update(read_only=not args.apply, client_tls_cipher=cipher[0])
            print(json.dumps(report, ensure_ascii=False))
        return 0
    except AccountPreparationError as error:
        print('未完成：' + str(error), file=sys.stderr)
    except pymysql.MySQLError as error:
        number = error.args[0] if error.args and isinstance(error.args[0], int) else 'unknown'
        print(f'未完成：MySQL错误编号{number}；保留已生效状态，未输出秘密或原始SQL，不自动重跑。', file=sys.stderr)
    except Exception:
        print('未完成：维护配置或账号验证失败，保留现场，未输出秘密或原始异常。', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
