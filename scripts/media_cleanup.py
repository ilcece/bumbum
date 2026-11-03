"""预览或清理到期媒体技术资源；不启动上传服务，不处理业务数据清理。"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import Flask
import pymysql

from core.db import get_database, init_database
from core.media_assets import MediaUnavailable, init_media_settings
from core.media_backup import MediaBackupError
from core.media_cleanup import cleanup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--media-root', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-bundle', type=Path)
    args = parser.parse_args(argv)
    if args.apply and args.backup_bundle is None:
        parser.error('--apply必须提供已验证的--backup-bundle')
    try:
        app = Flask('media_cleanup', static_folder=None)
        init_database(app)
        init_media_settings(app)
        app.config['MEDIA_ROOT'] = str(args.media_root)
        with app.app_context():
            result = cleanup(get_database(), apply=args.apply, backup_bundle=args.backup_bundle)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (MediaUnavailable, MediaBackupError) as error:
        print(str(error), file=sys.stderr)
    except (OSError, ValueError, pymysql.MySQLError):
        print('媒体维护未完成；请核对目标、权限及配套备份，未输出路径或连接详情。', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
