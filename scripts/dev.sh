#!/usr/bin/env bash
# Development: API with auto-reload on :8000 and Vite dev server on :5173.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$ROOT/services/api" && exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
API=$!
trap 'kill $API 2>/dev/null || true' EXIT
cd "$ROOT/apps/web" && npm run dev
