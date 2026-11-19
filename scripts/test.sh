#!/usr/bin/env bash
# Backend tests + frontend typecheck/build. Browser E2E: ./scripts/e2e.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$ROOT/services/api" && .venv/bin/python -m pytest -q)
(cd "$ROOT/apps/web" && npm run build)
