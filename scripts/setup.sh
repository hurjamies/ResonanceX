#!/usr/bin/env bash
# One-time local setup: Python virtualenv + frontend dependencies + production build.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
command -v ffmpeg >/dev/null || { echo "FFmpeg puuttuu – asenna se (esim. brew install ffmpeg / apt install ffmpeg)"; exit 1; }
cd "$ROOT/services/api"
if command -v uv >/dev/null; then
  uv venv .venv -p 3.12 && uv pip install -p .venv -r requirements-dev.txt
else
  python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
fi
cd "$ROOT/apps/web" && npm install && npm run build
echo "Valmis. Käynnistä: ./scripts/start.sh  →  http://127.0.0.1:8000"
