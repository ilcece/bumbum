#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .local/app.env
set +a
TEST_MIGRATION_URL=$(sed -n 's/^DATABASE_URL=//p' .local/migrate.env) npm test
