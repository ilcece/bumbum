"""由操作者在杭州 Workbench 交互终端填写测试短信配置。"""

import getpass
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tempfile
import warnings

from core.aliyun_sms import ALIYUN_SMS_SETTINGS, valid_settings


TEST_ROOT = Path('/opt/bumbum-hangzhou/test')
RUNTIME = TEST_ROOT / 'secrets/runtime.env'


def merge_runtime(original, settings):
    updates = {name.encode(): value.encode() for name, value in settings.items()}
    key = b'SMS_CODE_HASH_KEY'
    gateway = {b'SMS_GATEWAY_URL', b'SMS_GATEWAY_TOKEN'}
    tracked = updates.keys() | {key} | gateway
    saved, kept = {}, []
    for line in original.splitlines(keepends=True):
        name, equal, value = line.rstrip(b'\r\n').partition(b'=')
        name = name.strip()
        if not equal or name not in tracked:
            kept.append(line)
            continue
        if name in saved:
            raise ValueError('私有配置含重复短信字段，请先核对。')
        saved[name] = value
        if name in gateway:
            kept.append(line)
    if any(saved.get(name) for name in gateway):
        raise ValueError('已有通用网关配置，需单独核对切换范围。')
    if any(saved.get(name) and saved[name] != value for name, value in updates.items()):
        raise ValueError('已有短信配置与本次输入不一致，请先核对。')
    if saved.get(key) and not re.fullmatch(b'[0-9a-fA-F]{64}', saved[key]):
        raise ValueError('已有验证码密钥格式异常，请先核对。')
    if saved.get(key) and all(saved.get(name) == value for name, value in updates.items()):
        return original
    updates[key] = saved.get(key) or secrets.token_hex(32).encode()
    prefix = b''.join(kept)
    if prefix and not prefix.endswith(b'\n'):
        prefix += b'\n'
    return prefix + b''.join(name + b'=' + value + b'\n' for name, value in updates.items())


def write_runtime(path, settings):
    directory = path.parent.stat()
    if path.parent.resolve() != path.parent or directory.st_uid != 0 or directory.st_mode & 0o077:
        raise ValueError('测试秘密目录的归属或权限不符合要求。')
    lock = path.with_name('.sms-setup.lock')
    lock.touch(mode=0o600, exist_ok=False)
    try:
        original_info = path.lstat()
        if not stat.S_ISREG(original_info.st_mode) or original_info.st_uid != 0 or stat.S_IMODE(original_info.st_mode) != 0o600:
            raise ValueError('测试运行配置必须是 root 所有、权限 600 的普通文件。')
        original = path.read_bytes()
        contents = merge_runtime(original, settings)
        if contents == original:
            return False
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.sms-setup-', delete=False) as stream:
            staged = Path(stream.name)
            try:
                os.fchown(stream.fileno(), original_info.st_uid, original_info.st_gid)
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
                current = path.lstat()
                if (current.st_ino != original_info.st_ino or current.st_mode != original_info.st_mode
                        or current.st_uid != original_info.st_uid or current.st_gid != original_info.st_gid
                        or path.read_bytes() != original):
                    raise ValueError('配置在填写期间发生变化，请先核对。')
                staged.replace(path)
            finally:
                staged.unlink(missing_ok=True)
        return True
    finally:
        lock.unlink()


def main():
    if len(sys.argv) != 1 or not sys.stdin.isatty() or not sys.stderr.isatty():
        raise ValueError('请在 Workbench 交互终端运行，不接受命令参数或重定向输入。')
    if os.geteuid() != 0 or os.uname().nodename != 'iZbp1cj6pt88wbxmhlsp1nZ':
        raise ValueError('只接受已确认的杭州实例及其 root 维护终端。')
    manifest = json.loads((TEST_ROOT / 'compose.json').read_text())
    env = manifest['services']['backend']['environment']
    if manifest['name'] != 'bumbum-hangzhou-test' or env['HANGZHOU_SLOT'] != 'test' or env['DB_NAME'] != 'bumbum_hz_test':
        raise ValueError('Compose 清单不属于杭州 test。')
    settings = {'SMS_PROVIDER': 'aliyun'}
    settings['SMS_ALIYUN_SIGN_NAME'] = input('完整短信签名：').strip()
    settings['SMS_ALIYUN_TEMPLATE_CODE'] = input('已通过审核的短信模板 CODE：').strip()
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        for name in (ALIYUN_SMS_SETTINGS[0], ALIYUN_SMS_SETTINGS[1], ALIYUN_SMS_SETTINGS[-1]):
            settings[name] = getpass.getpass(f'{name}（隐藏输入）：')
    if not valid_settings(settings):
        raise ValueError('签名、模板、凭据或唯一验收号码格式不符。')
    changed = write_runtime(RUNTIME, settings)
    print('杭州 test 短信配置已保存，等待服务加载。' if changed else '杭州 test 短信配置已存在且一致。')


if __name__ == '__main__':
    try:
        main()
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        sys.exit('停止：未完成隐藏输入。')
    except json.JSONDecodeError:
        sys.exit('停止：无法核对测试 Compose 清单。')
    except ValueError as error:
        sys.exit(f'停止：{error}')
    except (OSError, KeyError, TypeError):
        sys.exit('停止：目标、权限或配置写入检查未通过。')
