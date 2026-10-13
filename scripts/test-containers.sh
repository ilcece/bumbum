#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Refuse existing deploy configuration; never connect to a cloud database.
for protected in .env .env.migrate secrets/mysql-ca.pem; do
  if [[ -e "$protected" ]]; then
    printf '%s\n' 'Container acceptance requires a dedicated local checkout without deployment configuration.' >&2
    exit 1
  fi
done
[[ -f .local/browser.json ]] || { printf '%s\n' 'Run local-db.sh and test.sh first.' >&2; exit 1; }
export DOCKER_CONFIG=${DOCKER_CONFIG:-/tmp/bumbum-docker}
mkdir -p "$DOCKER_CONFIG"
task_npm_cache=${NPM_CACHE_DIR:-/tmp/bumbum-npm}
npm ci --cache "$task_npm_cache"
docker build --build-context "npm_cache=$task_npm_cache" -t bumbum:1.0.0 .
python scripts/container-test-setup.py
cleanup() {
  docker compose -f compose.yaml -f .local/compose.acceptance.yaml stop app caddy
  # Preserve only fixtures this script created, in an ignored protected folder.
  mv .env .local/acceptance.app.env
  mv .env.migrate .local/acceptance.migrate.env
  mv secrets/mysql-ca.pem .local/acceptance.mysql-ca.pem
}
trap cleanup EXIT
docker compose config --quiet
docker compose -f compose.yaml -f .local/compose.acceptance.yaml run --rm tools migrate
docker compose -f compose.yaml -f .local/compose.acceptance.yaml up -d --wait app caddy
docker cp bumbum-caddy-1:/data/caddy/pki/authorities/local/root.crt .local/caddy-root.crt
NODE_EXTRA_CA_CERTS="$PWD/.local/caddy-root.crt" node scripts/container-acceptance.mjs
docker compose -f compose.yaml -f .local/compose.acceptance.yaml run --rm --entrypoint node \
  -v "$PWD/scripts/tls-test.mjs:/app/tls-test.mjs:ro" \
  -v "$PWD/.local/caddy-root.crt:/run/wrong-ca.pem:ro" tools tls-test.mjs
