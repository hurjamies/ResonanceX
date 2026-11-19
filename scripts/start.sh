#!/usr/bin/env bash
# Run ResonanceX locally (API + built frontend on one port).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -d "$ROOT/apps/web/dist" ] || (cd "$ROOT/apps/web" && npm run build)
cd "$ROOT/services/api"
exec .venv/bin/uvicorn app.main:app --host "${RESONANCEX_HOST:-127.0.0.1}" --port "${RESONANCEX_PORT:-8000}"
