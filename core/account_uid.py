"""按 RFC 9562 生成账户 UUIDv7，供现有 Python 运行时使用。"""

import re
from secrets import randbits
from time import time_ns
from uuid import UUID, uuid4


ACCOUNT_UID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}')


def new_account_uid():
    milliseconds = time_ns() // 1_000_000
    random_a = randbits(12)
    random_b = randbits(62)
    value = (milliseconds << 80) | (7 << 76) | (random_a << 64) | (2 << 62) | random_b
    return str(UUID(int=value))


def new_account_identity():
    return new_account_uid(), uuid4().bytes
