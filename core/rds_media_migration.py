"""杭州已有库的005升级入口；固定目标、验证TLS、隐藏输入并先完整转储。"""

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import uuid

import pymysql

from core.testdata_migration import TABLES as TEST_TABLES, schema as testdata_schema, migrate as migrate_testdata
from core.catalog_migration import TABLES as CATALOG_TABLES, catalog_schema, migrate as migrate_catalog, CatalogMigrationError
from core.db import TARGET_TABLES, database_tls_options, media_asset_schema
from core.media_migration import MediaMigrationError, migrate
from core.rds_database import RdsPreparationError, inspect_target
from core.rds_target import RDS_HOST, SLOTS, validate_target


def inspect_media(connection, database, expected_uuid=None):
    report = inspect_target(connection, database)
    with connection.cursor() as cursor:
        cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')
        tables = {row[0] for row in cursor.fetchall()}
        state = media_asset_schema(cursor)
    base=TARGET_TABLES-set(CATALOG_TABLES)-TEST_TABLES
    if report['other_object_count'] or tables not in (TARGET_TABLES, TARGET_TABLES-{'media_asset'},base,base-{'media_asset'},TARGET_TABLES-TEST_TABLES) or state == 'unknown':
        raise MediaMigrationError('已有库结构无法完整识别，未升级；先核对旧版本及005。')
    if expected_uuid is not None and report['server_uuid'] != expected_uuid:
        raise MediaMigrationError('实际实例标识与确认值不同，未升级。')
    report['media_assets'] = state
    return report


def native_backup(config, password, connection, expected_uuid, directory, purpose="media-assets"):
    """凭证只进入子进程环境；不自动恢复、覆盖文件或输出原生错误。"""
    program = shutil.which('mysqldump')
    if not program:
        raise MediaMigrationError('需要受控终端的MySQL 8.0 mysqldump客户端，未升级。')
    version = subprocess.run([program,'--version'],capture_output=True,text=True,timeout=10)
    if version.returncode or not re.search(r'\b8\.0\.',version.stdout):
        raise MediaMigrationError('转储客户端不是已验证MySQL 8.0，未升级。')
    directory = Path(directory)
    if not directory.is_absolute() or directory.resolve() != directory:
        raise MediaMigrationError('备份须为不经过符号链接的私有绝对目录。')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir() or directory.stat().st_uid != os.getuid() or stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise MediaMigrationError('备份目录须为当前操作者持有且仅本人可访问，未自动改权限。')
    inspect_media(connection, config['DB_NAME'], expected_uuid)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = directory / f'before-{purpose}-{stamp}-{uuid.uuid4().hex}.sql'
    partial = destination.with_suffix('.partial')
    flags = [program,'--no-defaults','--host='+config['DB_HOST'],'--port=3306','--user='+config['DB_USER'],
             '--ssl-mode=VERIFY_IDENTITY','--ssl-ca='+config['DB_SSL_CA'],'--single-transaction',
             '--skip-lock-tables','--no-tablespaces','--set-gtid-purged=OFF','--hex-blob',
             '--routines','--events','--triggers',config['DB_NAME']]
    # 覆盖任何继承的MYSQL_PWD，仅使用本次隐藏输入；不打印环境或命令错误正文。
    environment = {**os.environ, 'MYSQL_PWD': password}
    descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            result = subprocess.run(flags,env=environment,stdout=stream,stderr=subprocess.PIPE,timeout=300)
            stream.flush(); os.fsync(stream.fileno())
        if result.returncode:
            raise MediaMigrationError('完整转储未成功，保留私有partial供核对，未升级。')
        with partial.open('rb') as stream:
            stream.seek(max(0,partial.stat().st_size-512))
            if b'-- Dump completed on' not in stream.read():
                raise MediaMigrationError('完整转储结束标记缺失，未升级。')
        # 再建独立TLS连接核对端点没有切到其他实例；不靠转储文件名判断归属。
        with connect(config,password) as fresh:
            inspect_media(fresh,config['DB_NAME'],expected_uuid)
        os.link(partial,destination,follow_symlinks=False)
        partial.unlink()
        print('完整私有备份已保存：'+str(destination))
        return destination
    finally:
        environment.pop('MYSQL_PWD',None)


def connect(config, password):
    return pymysql.connect(host=config['DB_HOST'],port=3306,user=config['DB_USER'],password=password,
                           database=config['DB_NAME'],charset='utf8mb4',connect_timeout=5,read_timeout=30,
                           write_timeout=10,autocommit=False,**database_tls_options(config))


def main(argv=None):
    parser = argparse.ArgumentParser(description='杭州已有库媒体005检查；显式apply在停止写入并备份后升级，不启用上传。')
    parser.add_argument('--test-batches',action='store_true',help='检查/升级验收批次007，先完成006')
    parser.add_argument('--digital-catalog',action='store_true',help='改为检查/升级数字档案006，仍须先完成媒体005')
    parser.add_argument('--slot',required=True,choices=SLOTS)
    parser.add_argument('--ca',required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--confirm-database')
    parser.add_argument('--confirm-server-uuid')
    parser.add_argument('--writes-stopped',action='store_true')
    parser.add_argument('--backup-dir',type=Path)
    args = parser.parse_args(argv)
    if args.test_batches and args.digital_catalog:parser.error("007与006不能同时执行。")
    target = SLOTS[args.slot]
    config = {'APP_ENV':'production','HANGZHOU_SLOT':args.slot,'DB_HOST':RDS_HOST,'DB_PORT':3306,
              'DB_NAME':target['database'],'DB_USER':target['user']+'_init','DB_SSL_MODE':'VERIFY_IDENTITY','DB_SSL_CA':args.ca}
    try:
        validate_target(config,initialization=True)
        database_tls_options(config)
        if args.apply:
            if args.confirm_database != target['database'] or not args.confirm_server_uuid or not args.writes_stopped or args.backup_dir is None:
                raise MediaMigrationError('执行升级须确认库名、实例UUID、停止写入及私有备份目录，未连接。')
            uuid.UUID(args.confirm_server_uuid)
        if not sys.stdin.isatty():
            raise MediaMigrationError('须由操作者在受控终端隐藏输入初始化账号密码，不从管道或已有秘密文件读取。')
        password = getpass.getpass('RDS对应库_init账号密码（不回显）：')
        if not password:
            raise MediaMigrationError('未输入密码，未连接。')
        with connect(config,password) as connection:
            report = inspect_media(connection,config['DB_NAME'],args.confirm_server_uuid if args.apply else None)
            if args.test_batches:
                with connection.cursor() as cursor:
                    report['test_batches']=testdata_schema(cursor)
                    if catalog_schema(cursor)!='ready':raise CatalogMigrationError('先完成006，再升级007。')
                if args.apply:
                    report['changed']=migrate_testdata(connection,lambda:native_backup(config,password,connection,args.confirm_server_uuid,args.backup_dir,purpose="test-batches"))
                    report['test_batches']='ready'
            if args.digital_catalog:
                with connection.cursor() as cursor: report['digital_catalog']=catalog_schema(cursor)
                if report['media_assets']!='ready':raise CatalogMigrationError('先完成媒体005，再升级数字档案006。')
            if args.apply and args.digital_catalog:
                report['changed']=migrate_catalog(connection,lambda:native_backup(config,password,connection,args.confirm_server_uuid,args.backup_dir,purpose='digital-catalog'))
                with connection.cursor() as cursor:report['digital_catalog']=catalog_schema(cursor)
            elif args.apply and not args.test_batches:
                report['changed'] = migrate(connection,lambda: native_backup(config,password,connection,args.confirm_server_uuid,args.backup_dir))
                report['media_assets'] = inspect_media(connection,config['DB_NAME'],args.confirm_server_uuid)['media_assets']
            print(json.dumps(report,ensure_ascii=False))
        return 0
    except (MediaMigrationError,RdsPreparationError,CatalogMigrationError) as error:
        print('未完成：'+str(error),file=sys.stderr)
    except Exception:
        print('未完成：目标、认证、TLS、转储或结构检查失败；未显示秘密或SQL，保留现场，不自动恢复或重跑。',file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
