"""用真实Gunicorn容器量测既定配额，全部使用专属数据库与合成图。"""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from PIL import Image
import pyotp
import pytest

from tests.test_admin_auth import query
from tests.test_cloud_gateway import unused_port

pytestmark = pytest.mark.auth_database
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('workers,memory,cpus', [(1,256,.5), (2,512,1.25)])
def test_bounded_upload_and_restart(auth_app, admin_account, auth_database, tmp_path, request, workers, memory, cpus):
    image = request.config.getoption('--cloud-image')
    if not image:
        pytest.skip('需要--cloud-image的独立本地构建镜像，不连接服务器')
    command = auth_database['TEST_DOCKER_COMMAND']
    env = {key: value for key, value in os.environ.items() if key not in {'DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'}}
    def docker(args):
        result = subprocess.run(command + args, env=env, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, '专属媒体资源容器命令失败，未输出配置或秘密'
        return result.stdout.strip()
    backend = 'bumbum-media-resource-' + uuid.uuid4().hex[:12]
    volume, port = backend + '-files', unused_port()
    config = {key: auth_app.config[key] for key in ('DB_HOST','DB_PORT','DB_USER','DB_PASSWORD','DB_NAME','STORAGE_ENCRYPTION_KEY','IP_HASH_KEY')}
    config.update(APP_ENV='development', ADMIN_ORIGIN='http://localhost:5174', PUBLIC_ORIGIN='http://127.0.0.1:5175',
                  MEDIA_ENABLED='true', MEDIA_ROOT='/app/media')
    settings = tmp_path / 'synthetic-runtime.env'
    settings.write_text(''.join(f'{key}={value}\n' for key,value in config.items()))
    settings.chmod(0o600)
    runtime_code = tmp_path / 'runtime-code'
    runtime_code.mkdir(mode=0o755)
    shutil.copytree(ROOT / 'core', runtime_code / 'core', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(ROOT / 'app.py', runtime_code / 'app.py')
    for path in runtime_code.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    cookie, csrf = '', ''
    def call(path, method='GET', body=None, content='application/json'):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=35)
        try:
            connection.request(method, path, body=body, headers={'Origin':config['ADMIN_ORIGIN'], 'Content-Type':content, 'Cookie':cookie, 'X-CSRF-Token':csrf})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()
    def ready():
        for _ in range(100):
            try:
                if call('/api/ready')[0] == 200:
                    return
            except (OSError,http.client.HTTPException):
                pass
            time.sleep(.1)
        pytest.fail('专属媒体后端未就绪')
    def send(raw, asset_id):
        boundary = 'bumbum-' + uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="client_upload_id"\r\n\r\n{asset_id}\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.png"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                + raw + f'\r\n--{boundary}--\r\n'.encode())
        return call(f'/api/admin/items/{item_id}/images', 'POST', body, 'multipart/form-data; boundary=' + boundary)
    created = False
    docker(['volume','create','--label','bumbum.test=media-resources',volume])
    try:
        docker(['run','--rm','--network=none','--user','0:0','--volume',volume+':/app/media','--entrypoint','python',image,
                '-c',"import os; os.chown('/app/media',10001,10001); os.chmod('/app/media',0o700)"])
        runtime = ['gunicorn','--no-control-socket','--bind',f'127.0.0.1:{port}','--workers',str(workers),'--worker-tmp-dir','/tmp','--timeout','30','app:create_app()']
        create_args = ['create','--name',backend,'--label','bumbum.test=media-resources','--network=host','--read-only',
                '--memory',f'{memory}m','--memory-swap',f'{memory}m','--cpus',str(cpus),'--pids-limit','128',
                '--tmpfs','/tmp:size=32m,mode=1777','--volume','/app/logs','--volume',volume+':/app/media',
                '--mount',f'type=bind,src={runtime_code / "core"},dst=/app/core,readonly',
                '--mount',f'type=bind,src={runtime_code / "app.py"},dst=/app/app.py,readonly',
                '--cap-drop=ALL','--security-opt=no-new-privileges:true','--env-file',str(settings),image,*runtime]
        docker(create_args)
        created = True
        # 只读挂载当前代码，避免基础镜像构建时间差掩盖最新修改。
        docker(['start',backend]); ready()
        status, headers, body = call('/api/admin/auth/login','POST',json.dumps({'username':admin_account['username'],'password':admin_account['password'],'code':pyotp.TOTP(admin_account['secret']).now()}).encode())
        assert status == 200
        cookie = headers['Set-Cookie'].split(';',1)[0]
        status, _, body = call('/api/admin/auth/session')
        assert status == 200
        csrf = json.loads(body)['data']['csrf_token']
        status, _, body = call('/api/admin/items','POST',json.dumps({'project':'fashion','item_uid':'FASH-2026-'+str(970000+workers)}).encode())
        assert status == 200
        item_id = json.loads(body)['data']['id']
        timings = []
        for format, mode in [('JPEG','RGB'), ('PNG','RGBA'), ('WEBP','RGBA')]:
            output = BytesIO()
            if format == 'JPEG':
                source = Image.effect_noise((4000,4000),100).convert('RGB')
            else:
                source = Image.new(mode, (4000,2000) if format == 'WEBP' else (4000,4000), (30,120,70,100))
            exif = source.getexif(); exif[274] = 6
            source.save(output, format, exif=exif, quality=60)
            del source
            raw, uid = output.getvalue(), uuid.uuid4().hex
            assert len(raw) <= 8 * 1024**2
            if format == 'JPEG':
                assert len(raw) > 4 * 1024**2
            print(f'开始资源边界：{memory}MiB，{format}，输入{len(raw)}字节。',flush=True)
            started = time.monotonic()
            if workers == 2:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending = pool.submit(send,raw,uid)
                    for _ in range(300):
                        rows = query(auth_app,"SELECT state FROM media_asset WHERE asset_id=%s",(uid,))
                        if rows and rows[0]['state'] == 'uploading':
                            break
                        if pending.done():
                            pytest.fail('未观察到处理窗口，不能宣称已验证跨worker并发拒绝')
                        time.sleep(.005)
                    assert send(raw,uuid.uuid4().hex)[0] == 429
                    status, _, body = pending.result(timeout=30)
            else:
                try:
                    status, _, body = send(raw,uid)
                except (OSError,http.client.HTTPException):
                    print('本次容器峰值字节：'+docker(['exec',backend,'cat','/sys/fs/cgroup/memory.peak']),flush=True)
                    print('本次容器内存事件：'+docker(['exec',backend,'cat','/sys/fs/cgroup/memory.events']),flush=True)
                    raise
            elapsed = time.monotonic() - started
            assert status == 200, '既定资源下1600万像素上传失败，须先处理而非提高配额'
            assert elapsed < 15, '处理超过既有网关等待时间'
            result = json.loads(body)['data']
            status, _, saved = call(f'/api/admin/items/{item_id}','PATCH',json.dumps({'profile':{'name':'合成资源验证','image_urls':[result['url']]}}).encode())
            assert status == 200
            status, _, encoded = call(f'/api/admin/items/{item_id}/images/{uid}')
            assert status == 200
            with Image.open(BytesIO(encoded)) as reduced:
                assert reduced.size == ((1024,2048) if format == 'WEBP' else (2048,2048)) and not reduced.info.get('exif')
            timings.append(round(elapsed,3))
        # 原16MP透明WebP已实测OOM，收紧格式限制后须在解码前正常拒绝而非杀死worker。
        output = BytesIO(); Image.new('RGBA',(4000,4000),(30,120,70,100)).save(output,'WEBP')
        assert send(output.getvalue(),uuid.uuid4().hex)[0] == 400
        peak = int(docker(['exec',backend,'cat','/sys/fs/cgroup/memory.peak']))
        events = docker(['exec',backend,'cat','/sys/fs/cgroup/memory.events'])
        assert 'oom_kill 0' in events and peak < memory * 1024**2
        docker(['restart',backend]); ready()
        assert call(f'/api/admin/items/{item_id}/images/{uid}')[2] == encoded
        assert docker(['inspect','--format','{{.State.OOMKilled}}',backend]) == 'false'
        docker(['rm','--force','--volumes',backend]); created = False
        docker(create_args); created = True
        docker(['start',backend]); ready()
        assert call(f'/api/admin/items/{item_id}/images/{uid}')[2] == encoded
        print(f'媒体配额实测：{memory}MiB/{workers}worker，峰值{peak/1024**2:.1f}MiB，JPEG/PNG/WebP耗时{timings}秒，重启和重建后文件保留。')
    finally:
        if created:
            docker(['rm','--force','--volumes',backend])
        docker(['volume','rm',volume])
