#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .local
chmod 700 .local
if [[ ! -f .local/db.env ]]; then
  node --input-type=module - <<'JS'
import {randomBytes} from 'node:crypto';import {writeFileSync} from 'node:fs';
const root=randomBytes(24).toString('hex'),app=randomBytes(24).toString('hex'),migration=randomBytes(24).toString('hex');
writeFileSync('.local/db.env',`MYSQL_ROOT_PASSWORD=${root}\nMYSQL_DATABASE=bumbum_test\n`,{mode:0o600});
writeFileSync('.local/app.env',`DATABASE_URL=mysql://bumbum_app:${app}@127.0.0.1:3307/bumbum_test\nPUBLIC_BASE_URL=http://localhost:3000\nSESSION_SECRET=${randomBytes(32).toString('hex')}\nDB_TLS=false\nNODE_ENV=development\n`,{mode:0o600});
writeFileSync('.local/migrate.env',`DATABASE_URL=mysql://bumbum_migrate:${migration}@127.0.0.1:3307/bumbum_test\nDB_TLS=false\nNODE_ENV=development\n`,{mode:0o600});
writeFileSync('.local/accounts.sql',`CREATE USER IF NOT EXISTS 'bumbum_app'@'%' IDENTIFIED BY '${app}';\nCREATE USER IF NOT EXISTS 'bumbum_migrate'@'%' IDENTIFIED BY '${migration}';\nGRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,INDEX,REFERENCES ON bumbum_test.* TO 'bumbum_migrate'@'%';\n`,{mode:0o600});
JS
fi
docker compose -f compose.local.yaml up -d --wait
docker compose -f compose.local.yaml exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot' < .local/accounts.sql
set -a
source .local/migrate.env
set +a
npm run migrate
cat <<'SQL' | docker compose -f compose.local.yaml exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot'
GRANT SELECT,INSERT,UPDATE ON bumbum_test.garments TO 'bumbum_app'@'%';
GRANT SELECT,INSERT,UPDATE ON bumbum_test.tags TO 'bumbum_app'@'%';
GRANT SELECT ON bumbum_test.admins TO 'bumbum_app'@'%';
GRANT SELECT,INSERT,UPDATE,DELETE ON bumbum_test.admin_sessions TO 'bumbum_app'@'%';
GRANT SELECT,INSERT,UPDATE,DELETE ON bumbum_test.login_attempts TO 'bumbum_app'@'%';
GRANT SELECT,INSERT ON bumbum_test.audit_logs TO 'bumbum_app'@'%';
GRANT SELECT ON bumbum_test.schema_migrations TO 'bumbum_app'@'%';
SQL
printf '%s\n' 'Local database prepared; credentials are in ignored .local files.'
