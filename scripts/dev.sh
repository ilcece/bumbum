#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .local/app.env
set +a
exec node dist/server.js
