"""Local stand-in for the documented ElevenLabs Music endpoints – TESTS ONLY.

Records every request so tests can assert the exact wire format. It is never used
by the application itself.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class FakeElevenLabs:
    def __init__(self, audio: bytes, api_key: str = "test-key"):
        self.audio = audio
        self.api_key = api_key
        self.requests: list[dict] = []
        self.fail_status: int | None = None
        self.plan = {"chunks": [
            {"text": "[Intro]", "duration_ms": 20000, "positive_styles": ["dark ambient"], "negative_styles": [], "context_adherence": "high"},
            {"text": "[Build]", "duration_ms": 40000, "positive_styles": ["rising pulse"], "negative_styles": [], "context_adherence": "high"},
        ]}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def do_POST(self):  # noqa: N802
                u = urlparse(self.path)
                body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
                outer.requests.append({"path": u.path, "query": parse_qs(u.query), "headers": dict(self.headers), "body": body})
                if self.headers.get("xi-api-key") != outer.api_key:
                    return self._json(401, {"detail": {"status": "invalid_api_key"}})
                if outer.fail_status:
                    return self._json(outer.fail_status, {"detail": "forced failure"})
                if u.path == "/v1/music/plan":
                    return self._json(200, outer.plan)
                if u.path == "/v1/music":
                    if ("prompt" in body) == ("composition_plan" in body):
                        return self._json(422, {"detail": "prompt xor composition_plan"})
                    self.send_response(200)
                    self.send_header("content-type", "audio/mpeg")
                    self.send_header("song-id", "fake-song-1")
                    self.send_header("content-length", str(len(outer.audio)))
                    self.end_headers()
                    self.wfile.write(outer.audio)
                    return
                return self._json(404, {"detail": "not found"})

            def _json(self, status, obj):
                data = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def mp3_bytes(tmp: Path) -> bytes:
    from tests.signals import make_track, write_mp3

    return write_mp3(tmp / "fake_el.mp3", make_track(bpm=90, seconds=20, key_root="E", minor=True, crescendo=True)).read_bytes()


if __name__ == "__main__":  # used by scripts/e2e.sh only
    import argparse
    import tempfile

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--key", required=True)
    a = ap.parse_args()
    fake = FakeElevenLabs(mp3_bytes(Path(tempfile.mkdtemp())), api_key=a.key)
    fake.server.server_close()
    fake.server = ThreadingHTTPServer(("127.0.0.1", a.port), fake.server.RequestHandlerClass)
    print(f"fake ElevenLabs on :{a.port}", flush=True)
    fake.server.serve_forever()
