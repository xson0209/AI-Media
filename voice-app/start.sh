#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v node >/dev/null 2>&1; then
    echo "Node.js is required. Install Node.js, then run this script again." >&2
    exit 1
fi

exec node scripts/dev-web.js "$@"
