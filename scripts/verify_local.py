"""检查已启动的后端；任一检查失败时以非零状态结束。"""

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

BASE_URL = "http://127.0.0.1:5000"


def main():
    # 本机检查不经过外部代理；不访问任何生产服务。
    opener = build_opener(ProxyHandler({}))
    checks = (
        ("/api/health", {"service": "bumbum", "state": "running"}, "后端运行正常"),
        ("/api/ready", {"database": "ready"}, "测试数据库已就绪"),
    )
    success = True
    for path, expected, description in checks:
        try:
            with opener.open(BASE_URL + path, timeout=8) as response:
                result = json.load(response)
            if result != {"status": "ok", "data": expected}:
                raise ValueError("返回内容不符合检查约定")
            print("通过：" + description)
        except HTTPError as error:
            success = False
            print(f"未通过：{description}，HTTP {error.code}。请按启动说明排查。")
        except (URLError, TimeoutError, OSError, ValueError):
            success = False
            print(f"未通过：{description}。请确认后端正在运行，并按启动说明排查。")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
