#!/usr/bin/env bash
# Browser end-to-end test against a throwaway data directory.
# Requires: services/api/.venv, built frontend (apps/web/dist), Node + Playwright with Chromium.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d -t resonancex-e2e-XXXX)"
PORT="${PORT:-8765}"
SHOT_DIR="${SHOT_DIR:-$WORK/shots}"
mkdir -p "$WORK/audio" "$SHOT_DIR"

echo "→ generating synthetic audio in $WORK/audio"
(cd "$ROOT/services/api" && .venv/bin/python - "$WORK/audio" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, ".")
from tests.signals import make_track, write_mp3, write_wav
d = Path(sys.argv[1])
specs = [("Deep Current", 88, "D", True, True, 0.9), ("Night Engine", 124, "A", True, False, 0.7),
         ("Glass Morning", 132, "E", False, False, 0.2), ("Slow Gravity", 80, "C", True, True, 1.0),
         ("Bright Market", 118, "G", False, False, 0.25), ("Undertow", 92, "F", True, True, 0.85),
         ("Paper Sun", 104, "B", False, False, 0.3), ("Ritual Pulse", 96, "G", True, True, 0.8)]
for name, bpm, key, minor, cres, bass in specs:
    write_mp3(d / f"{name}.mp3", make_track(bpm=bpm, seconds=75, key_root=key, minor=minor, crescendo=cres, bass_gain=bass))
write_wav(d / "Suno Result.wav", make_track(bpm=90, seconds=60, key_root="E", minor=True, crescendo=True, bass_gain=0.95))
PY
)

[ -d "$ROOT/apps/web/dist" ] || (cd "$ROOT/apps/web" && npm run build)

FAKE_PORT="${FAKE_PORT:-8766}"
echo "→ starting TEST-ONLY ElevenLabs stand-in on :$FAKE_PORT"
(cd "$ROOT/services/api" && exec .venv/bin/python -m tests.fake_elevenlabs --port "$FAKE_PORT" --key e2e-test-key >"$WORK/fake.log" 2>&1) &
FAKE=$!

echo "→ starting API on :$PORT (data: $WORK/data)"
(cd "$ROOT/services/api" && ELEVENLABS_API_KEY=e2e-test-key RESONANCEX_ELEVENLABS_BASE_URL="http://127.0.0.1:$FAKE_PORT" RESONANCEX_DATA_DIR="$WORK/data" exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >"$WORK/server.log" 2>&1) &
SERVER=$!
trap 'kill $SERVER $FAKE 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && break; sleep 0.5; done

BASE_URL="http://127.0.0.1:$PORT" AUDIO_DIR="$WORK/audio" SHOT_DIR="$SHOT_DIR" node "$ROOT/e2e/workflow.e2e.mjs"
echo "→ screenshots: $SHOT_DIR"
