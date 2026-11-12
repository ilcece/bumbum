"""在已冻结写入的环境中配套备份/恢复图片，不启动Flask业务或上传服务。"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import Flask
import pymysql

from core.db import get_database, init_database
from core.media_backup import MediaBackupError, create_bundle, inspect_bundle, restore_files, snapshot, verify_files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['snapshot', 'inspect', 'restore-files', 'verify'])
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--media-root', type=Path)
    parser.add_argument('--dump', type=Path)
    parser.add_argument('--writes-frozen', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.action == 'inspect':
            data = inspect_bundle(args.bundle)
            print('备份文件及清单自校验通过；尚未证明目标数据库已正确恢复。')
            return 0
        if args.media_root is None:
            parser.error('此动作需要--media-root')
        if args.action == 'snapshot' and args.dump is None:
            parser.error('snapshot需要冻结窗口内的原生数据库转储--dump')
        # 只初始化既有数据库/TLS配置；不调用create_app、不注册或依赖上传路由。
        app = Flask('media_backup', static_folder=None)
        init_database(app)
        with app.app_context():
            connection = get_database()
            if args.action == 'snapshot':
                count = create_bundle(connection, args.media_root, args.dump, args.bundle, writes_frozen=args.writes_frozen)
                print(f'已创建配套备份，共{count}个完整图片文件；仍须验证实际恢复。')
            elif args.action == 'restore-files':
                count = restore_files(connection, args.bundle, args.media_root)
                print(f'数据库与文件配套恢复校验通过，共{count}个图片文件；未启用上传。')
            else:
                data = inspect_bundle(args.bundle)
                if snapshot(connection) != data:
                    raise MediaBackupError('目标数据库与备份元数据不一致。')
                verify_files(data, args.media_root)
                print('目标数据库引用、元数据和图片内容一致；未启用上传。')
        return 0
    except (MediaBackupError, ValueError, OSError, pymysql.MySQLError) as error:
        print(str(error) if isinstance(error, MediaBackupError) else '配套备份/恢复未完成；请核对目标、权限和数据库配置，未输出连接或业务详情。', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
