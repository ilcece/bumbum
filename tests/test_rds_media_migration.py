"""RDS媒体升级的目标保护、备份拒绝和凭证传递；不连接真实RDS。"""

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import rds_media_migration as cli
from core.media_migration import MediaMigrationError
from core.rds_target import RDS_HOST


@pytest.mark.parametrize('extra', [[],['--writes-stopped'],['--confirm-database','wrong']])
def test_apply_requires_complete_target_before_password(monkeypatch,extra):
    monkeypatch.setattr(cli,'database_tls_options',lambda config: {})
    monkeypatch.setattr(cli.getpass,'getpass',lambda *_: pytest.fail('参数不足不应索取密码'))
    monkeypatch.setattr(cli,'connect',lambda *_: pytest.fail('参数不足不应连接'))
    assert cli.main(['--slot','production','--ca','/public/ca.pem','--apply',*extra]) == 1


@pytest.mark.parametrize('slot', ['test','production'])
def test_check_uses_only_fixed_tls_target_and_no_ddl(monkeypatch,capsys,slot):
    seen = []
    def connect(config,password):
        assert password == 'synthetic-input'
        seen.append(config)
        return nullcontext(object())
    monkeypatch.setattr(cli,'database_tls_options',lambda config: {})
    monkeypatch.setattr(cli.sys.stdin,'isatty',lambda: True)
    monkeypatch.setattr(cli.getpass,'getpass',lambda *_: 'synthetic-input')
    monkeypatch.setattr(cli,'connect',connect)
    monkeypatch.setattr(cli,'inspect_media',lambda *_: {'media_assets':'missing'})
    monkeypatch.setattr(cli,'migrate',lambda *_: pytest.fail('检查不得执行DDL'))
    assert cli.main(['--slot',slot,'--ca','/public/ca.pem']) == 0
    assert seen[0]['DB_HOST'] == RDS_HOST and seen[0]['DB_USER'] == f'bumbum_hz_{slot}_init'
    assert seen[0]['DB_NAME'] == f'bumbum_hz_{slot}' and seen[0]['DB_SSL_MODE'] == 'VERIFY_IDENTITY'
    assert 'synthetic-input' not in capsys.readouterr().out


@pytest.mark.parametrize('failure', [None,'dump','incomplete','changed-target'])
def test_native_backup_is_private_verified_and_hides_password(tmp_path,monkeypatch,capsys,failure):
    config = {'DB_HOST':RDS_HOST,'DB_USER':'bumbum_hz_test_init','DB_NAME':'bumbum_hz_test','DB_SSL_CA':'/public/ca.pem'}
    secret = 'synthetic-private-input'
    destination = tmp_path / 'private'
    monkeypatch.setattr(cli.shutil,'which',lambda _: '/usr/bin/mysqldump')
    monkeypatch.setattr(cli,'connect',lambda *_: nullcontext('fresh'))
    def inspect(connection,*_):
        if failure == 'changed-target' and connection == 'fresh':
            raise MediaMigrationError('合成实例变化')
    monkeypatch.setattr(cli,'inspect_media',inspect)
    def run(command,**options):
        assert secret not in ' '.join(command)
        if command[-1] == '--version':
            return SimpleNamespace(returncode=0,stdout='mysqldump Ver 8.0.46')
        assert command[1] == '--no-defaults' and '--ssl-mode=VERIFY_IDENTITY' in command
        assert command[-1] == 'bumbum_hz_test' and options['env']['MYSQL_PWD'] == secret
        options['stdout'].write(b'-- synthetic\n'+(b'' if failure == 'incomplete' else b'-- Dump completed on synthetic\n'))
        return SimpleNamespace(returncode=1 if failure == 'dump' else 0)
    monkeypatch.setattr(cli.subprocess,'run',run)
    if failure:
        with pytest.raises(MediaMigrationError):
            cli.native_backup(config,secret,'source','synthetic-uuid',destination)
        assert not list(destination.glob('*.sql')) and list(destination.glob('*.partial'))
    else:
        path = cli.native_backup(config,secret,'source','synthetic-uuid',destination)
        assert path.is_file() and path.stat().st_mode & 0o077 == 0 and destination.stat().st_mode & 0o077 == 0
    assert secret not in capsys.readouterr().out


def test_native_backup_refuses_public_or_symlink_directory(tmp_path,monkeypatch):
    monkeypatch.setattr(cli.shutil,'which',lambda _: '/usr/bin/mysqldump')
    monkeypatch.setattr(cli.subprocess,'run',lambda *_args,**_kw: SimpleNamespace(returncode=0,stdout='mysqldump Ver 8.0.46'))
    public = tmp_path / 'public'; public.mkdir(mode=0o755); public.chmod(0o755)
    link = tmp_path / 'link'; link.symlink_to(public,target_is_directory=True)
    for directory in (public,link,Path('relative')):
        with pytest.raises(MediaMigrationError):
            cli.native_backup({},'synthetic',None,'synthetic',directory)
