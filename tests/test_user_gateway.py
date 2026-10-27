"""本地真实HTTPS用户网关检查，不连接ECS、真实域名或业务库。"""

from datetime import datetime, timedelta, timezone
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import time
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest

from tests.test_admin_auth import query
from tests.test_admin_chips import logged_in
from tests.test_chip_binding import inventory
from tests.test_chip_keys import keyed, reading
from tests.test_tap_verification import ready
from tests.test_cloud_gateway import unused_port

pytestmark=pytest.mark.auth_database
ROOT=Path(__file__).resolve().parents[1]


def test_public_tls_cookie_static_isolation_and_restart(auth_app,ready,auth_database,tmp_path,request):
    image=request.config.getoption('--cloud-image')
    if not image: pytest.skip('需要独立构建镜像及--cloud-image，不访问服务器')
    command=auth_database['TEST_DOCKER_COMMAND']
    env=dict(os.environ)
    for name in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'): env.pop(name,None)
    def docker(args):
        result=subprocess.run(command+args,env=env,capture_output=True,text=True,timeout=120)
        assert result.returncode==0,'独立用户网关测试命令失败，不输出配置或秘密'
        return result.stdout.strip()
    backend='bumbum-user-api-'+uuid.uuid4().hex[:10]; gateway='bumbum-user-gateway-'+uuid.uuid4().hex[:10]
    api_port,tls_port,http_port=unused_port(),unused_port(),unused_port()
    config={name:auth_app.config[name] for name in ('DB_HOST','DB_PORT','DB_USER','DB_PASSWORD','DB_NAME','STORAGE_ENCRYPTION_KEY','IP_HASH_KEY','MASTER_KEY_FASHION','MASTER_KEY_JEWELRY','SDM_META_KEY_V1','SDM_META_KEY_VERSION')}
    config.update(APP_ENV='production',ADMIN_ORIGIN='https://test.bumbum.cc',PUBLIC_ORIGIN='https://nfc.bumbum.cc')
    settings=tmp_path/'gateway.env';settings.write_text(''.join(f'{key}={value}\n' for key,value in config.items()));settings.chmod(0o600)
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'nfc.bumbum.cc')]);now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(private.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('nfc.bumbum.cc'),x509.DNSName('test.bumbum.cc'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(private,hashes.SHA256()))
    (tmp_path/'cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (tmp_path/'key.pem').write_bytes(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));(tmp_path/'key.pem').chmod(0o600)
    for name,domain,root in [('admin','test.bumbum.cc','/usr/share/nginx/html'),('user','nfc.bumbum.cc','/usr/share/nginx/user-html')]:
        path='nginx-https.conf.template' if name=='admin' else 'nginx-user-https.conf.template'
        site=(ROOT/'deploy/cloud_test'/path).read_text().replace('__ADMIN_IP__','192.0.2.10')
        site=site.replace('listen 80;',f'listen 127.0.0.1:{http_port};').replace('listen 443 ssl;',f'listen 127.0.0.1:{tls_port} ssl;').replace('127.0.0.1:15000',f'127.0.0.1:{api_port}').replace(f'/etc/letsencrypt/live/{domain}/fullchain.pem','/etc/nginx/test-cert.pem').replace(f'/etc/letsencrypt/live/{domain}/privkey.pem','/etc/nginx/test-key.pem').replace('/var/www/bumbum-cloud-test',root).replace('/var/www/bumbum-user-test',root)
        (tmp_path/f'{name}.conf').write_text(site)
    (tmp_path/'nginx.conf').write_text('events {}\nhttp { include /etc/nginx/mime.types; include /etc/nginx/admin.conf; include /etc/nginx/user.conf; }\n')
    context=ssl.create_default_context(cafile=str(tmp_path/'cert.pem'))
    created=[]
    def call(path,method='GET',body=None,headers=None):
        connection=http.client.HTTPSConnection('127.0.0.1',tls_port,context=context,timeout=6)
        try:
            connection.request(method,path,body=json.dumps(body).encode() if body is not None else None,headers={'Host':'nfc.bumbum.cc','Content-Type':'application/json',**(headers or {})})
            result=connection.getresponse();return result.status,dict(result.getheaders()),result.read()
        finally: connection.close()
    def backend_ready():
        for _ in range(100):
            connection=http.client.HTTPConnection('127.0.0.1',api_port,timeout=3)
            try:
                connection.request('GET','/api/ready');response=connection.getresponse();response.read()
                if response.status==200:return
            except (OSError,http.client.HTTPException):pass
            finally:connection.close()
            time.sleep(.1)
        pytest.fail('独立后端未就绪，未操作现有服务')
    try:
        runtime=json.loads(docker(['image','inspect','--format','{{json .Config.Cmd}}',image]));runtime[runtime.index('--bind')+1]=f'127.0.0.1:{api_port}'
        docker(['create','--name',backend,'--label','bumbum.test=user-gateway','--network=host','--read-only','--tmpfs','/tmp','--volume','/app/logs','--cap-drop=ALL','--security-opt=no-new-privileges:true','--env-file',str(settings),image,*runtime]);created.append(backend);docker(['start',backend]);backend_ready()
        docker(['create','--name',gateway,'--label','bumbum.test=user-gateway','--network=host','nginx:1.28-alpine']);created.append(gateway)
        for name,dest in [('nginx.conf','nginx.conf'),('admin.conf','admin.conf'),('user.conf','user.conf'),('cert.pem','test-cert.pem'),('key.pem','test-key.pem')]:docker(['cp',str(tmp_path/name),gateway+':/etc/nginx/'+dest])
        docker(['cp',str(ROOT/'deploy/cloud_test/nginx-proxy.conf'),gateway+':/etc/nginx/bumbum-cloud-test-proxy.conf'])
        docker(['cp',backend+':/app/frontend-user-dist',str(tmp_path/'user-page')]);docker(['cp',str(tmp_path/'user-page'),gateway+':/usr/share/nginx/user-html'])
        docker(['start',gateway])
        for _ in range(60):
            try:
                if call('/tap')[0]==200:break
            except (OSError,http.client.HTTPException):time.sleep(.1)
        else:pytest.fail('独立用户HTTPS站点未就绪')
        docker(['exec',gateway,'sh','-c','mkdir -p /usr/share/nginx/user-html/.well-known/acme-challenge; printf challenge-ok > /usr/share/nginx/user-html/.well-known/acme-challenge/check'])
        plain=http.client.HTTPConnection('127.0.0.1',http_port,timeout=3)
        try:
            plain.request('GET','/.well-known/acme-challenge/check',headers={'Host':'nfc.bumbum.cc'})
            challenge=plain.getresponse()
            assert challenge.status==200 and challenge.read()==b'challenge-ok'
        finally:plain.close()
        status,headers,page=call('/tap?picc_data=PRIVATE_TEST_VALUE&cmac=PRIVATE_TEST_VALUE')
        assert status==200 and b'BUMBUM' in page and headers['Referrer-Policy']=='no-referrer'
        asset=re.search(rb'src="([^\"]+\.js)"',page).group(1).decode()
        assert call(asset)[0]==200
        assert call('/assets/missing.js')[0]==404
        for path in ('/api/admin/chips','/api/admin/auth/login','/api/health','/api/ready','/api/webhook/admin/scan','/api/public/bind','/api/fashion/items/1/detail'):
            assert call(path)[0]==404
        assert call('/api/admin/chips',headers={'Host':'test.bumbum.cc'})[0]==403
        payload={**reading(ready[1],ready[0][1]['chip_uid'],9),'browser_view':True}
        status,headers,body=call('/api/tap/verify','POST',payload,{'Origin':'https://nfc.bumbum.cc'})
        assert status==200 and json.loads(body)['data']['verified']
        cookie=headers['Set-Cookie'];assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=Strict' in cookie
        data=json.loads(body)['data'];endpoint=f"/api/tap/items/{data['item_id']}/view";cookie=cookie.split(';',1)[0]
        assert call(data['view_path'])[0]==200
        assert call(endpoint,headers={'Cookie':cookie})[0]==200
        assert call(endpoint,headers={'Cookie':cookie,'Origin':'https://other.example'})[0]==403
        assert call(endpoint,'POST',{}, {'Cookie':cookie})[0]==405
        assert query(auth_app,"SELECT COUNT(*) AS n FROM scan_log WHERE verify_result='pass'")[0]['n']==1
        docker(['restart',backend]);backend_ready()
        assert call(endpoint,headers={'Cookie':cookie})[0]==200
        query(auth_app,"UPDATE item SET status='disabled'")
        assert call(endpoint,headers={'Cookie':cookie})[0]==409
        for _ in range(35):
            status,limited_headers,limited_body=call(endpoint,headers={'Cookie':cookie})
            if status==429:
                assert limited_headers['Retry-After']=='1'
                assert limited_headers['Referrer-Policy']=='no-referrer' and limited_headers['X-Content-Type-Options']=='nosniff'
                assert json.loads(limited_body)['code']=='rate_limited'
                break
        else:pytest.fail('用户查看限频应拒绝超限请求')
        log=docker(['exec',gateway,'cat','/var/log/nginx/bumbum-user-access.log'])
        assert 'PRIVATE_TEST_VALUE' not in log and cookie not in log and data['tap_token'] not in log
    finally:
        for container in reversed(created):docker(['rm','--force','--volumes',container])
