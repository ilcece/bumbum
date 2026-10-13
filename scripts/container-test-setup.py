"""Prepare only local isolated TLS/container acceptance fixtures. Never use cloud DB."""
from pathlib import Path
import subprocess,os
p=Path('.local');p.mkdir(exist_ok=True)
for protected in ['.env','.env.migrate','secrets/mysql-ca.pem']:
 if Path(protected).exists():raise Exception('Preserve existing '+protected+' before preparing isolated acceptance fixtures')
def run(args,**kwargs):return subprocess.run(args,check=True,stdout=subprocess.DEVNULL,**kwargs)
def values(path):return dict(line.split('=',1) for line in Path(path).read_text().splitlines() if '=' in line and not line.startswith('#'))
if not (p/'tls/ca.pem').exists():
 (p/'tls').mkdir(exist_ok=True)
 run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(p/'tls/ca.key'),'-out',str(p/'tls/ca.pem'),'-days','30','-subj','/CN=bumbum isolated test CA'],stderr=subprocess.DEVNULL)
 run(['openssl','req','-newkey','rsa:2048','-nodes','-keyout',str(p/'tls/server.key'),'-out',str(p/'tls/server.csr'),'-subj','/CN=mysql'],stderr=subprocess.DEVNULL)
 (p/'tls/ext.cnf').write_text('subjectAltName=DNS:mysql,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n')
 run(['openssl','x509','-req','-in',str(p/'tls/server.csr'),'-CA',str(p/'tls/ca.pem'),'-CAkey',str(p/'tls/ca.key'),'-CAcreateserial','-out',str(p/'tls/server.pem'),'-days','30','-extfile',str(p/'tls/ext.cnf')],stderr=subprocess.DEVNULL)
 for x in (p/'tls').iterdir():x.chmod(0o600)
for src,dest in [('server.pem','server-cert.pem'),('server.key','server-key.pem'),('ca.pem','ca.pem')]:run(['docker','cp',str(p/'tls'/src),'bumbum-local-mysql-1:/var/lib/mysql/'+dest])
run(['docker','exec','bumbum-local-mysql-1','sh','-c','chown mysql:mysql /var/lib/mysql/server-cert.pem /var/lib/mysql/server-key.pem /var/lib/mysql/ca.pem; chmod 600 /var/lib/mysql/server-key.pem; MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "ALTER INSTANCE RELOAD TLS"'])
app=values(p/'app.env');migration=values(p/'migrate.env')
app['DATABASE_URL']=app['DATABASE_URL'].replace('@127.0.0.1:3307','@mysql:3306');app.update(PUBLIC_BASE_URL='https://localhost:8443',DB_TLS='true',DB_CA_FILE='/run/db-ca.pem',NODE_ENV='production',APP_IMAGE='bumbum:1.0.0',SITE_DOMAIN='localhost',ACME_EMAIL='test@example.com')
migration['DATABASE_URL']=migration['DATABASE_URL'].replace('@127.0.0.1:3307','@mysql:3306');migration.update(DB_TLS='true',DB_CA_FILE='/run/db-ca.pem',NODE_ENV='production')
for name,data in [('.env',app),('.env.migrate',migration)]:
 if Path(name).exists():raise Exception('Preserve existing configuration; move local acceptance files before rerunning')
 Path(name).write_text(''.join(k+'='+v+'\n' for k,v in data.items()));Path(name).chmod(0o600)
Path('secrets').mkdir(exist_ok=True);Path('secrets/mysql-ca.pem').write_bytes((p/'tls/ca.pem').read_bytes())
# Public test CA is readable by the non-root app; private key stays ignored in .local.
Path('secrets/mysql-ca.pem').chmod(0o644)
(p/'Caddyfile.test').write_text('{\n admin off\n}\nlocalhost {\n tls internal\n header Strict-Transport-Security "max-age=31536000"\n reverse_proxy app:3000\n}\n')
ip=subprocess.check_output(['docker','inspect','bumbum-local-mysql-1','--format','{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'],text=True).strip()
(p/'compose.acceptance.yaml').write_text('''services:
  app:
    networks: [default, testdb]
  tools:
    networks: [default, testdb]
    extra_hosts: ["wrong-mysql:__TEST_MYSQL_IP__"]
  caddy:
    ports: !override ["127.0.0.1:8443:443", "127.0.0.1:8080:80"]
    volumes: !override
      - ./.local/Caddyfile.test:/etc/caddy/Caddyfile:ro
      - acceptance_caddy_data:/data
      - acceptance_caddy_config:/config
networks:
  testdb:
    external: true
    name: bumbum-local_default
volumes:
  acceptance_caddy_data:
  acceptance_caddy_config:
'''.replace('__TEST_MYSQL_IP__',ip))
print('Isolated TLS/Compose fixture prepared; credentials not printed.')
