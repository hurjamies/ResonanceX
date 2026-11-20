"""``rx`` – small command-line client for a running local ResonanceX app.

Designed for the Claude Code + Suno MCP workflow: Claude Code fetches the prompt
brief, creates the song with the user's Suno MCP connection (after the user agrees
to the credit use), and imports the downloaded audio back so that ResonanceX can
analyse it and compare it with the prompt's targets.

Uses only the Python standard library and talks only to the local app
(``RESONANCEX_URL``, default http://127.0.0.1:8000).

Examples::

    ./scripts/rx prompts
    ./scripts/rx prompt 12 --handoff
    ./scripts/rx import ~/Downloads/song.mp3 --prompt 12 --source suno_mcp --i-have-rights
    ./scripts/rx experiments
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

DEFAULT_URL = "http://127.0.0.1:8000"
SOURCES = ("suno_mcp", "suno_manual", "manual_upload", "other")


class CliError(Exception):
    pass


def base_url() -> str:
    return os.environ.get("RESONANCEX_URL", DEFAULT_URL).rstrip("/")


def _request(method: str, path: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> Any:
    url = base_url() + path
    host = urllib.request.urlparse(url).hostname
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise CliError(f"rx only talks to a local ResonanceX app (got host {host!r}).")
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    # never use a proxy for the local app
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=120) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("detail")
        except Exception:
            detail = exc.reason
        raise CliError(f"{method} {path} → {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CliError(f"ResonanceX is not reachable at {base_url()} ({exc.reason}). Start it with ./scripts/start.sh") from exc
    return json.loads(body) if body else None


def _multipart(fields: dict[str, str], file_field: str, path: Path) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    safe_name = path.name.replace('"', "")
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{safe_name}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
        + path.read_bytes()
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def cmd_prompts(args: argparse.Namespace) -> int:
    for p in _request("GET", "/api/prompts")[: args.limit]:
        e = p["effective"]
        flag = "★" if p["saved"] else " "
        print(f"{flag} #{p['id']:<4} {e['mode_label']:<24} {e['title']:<28} {e['style'][:70]}")
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    if args.handoff:
        print(_request("GET", f"/api/prompts/{args.id}/handoff")["markdown"])
    else:
        print(json.dumps(_request("GET", f"/api/prompts/{args.id}")["effective"], ensure_ascii=False, indent=2))
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    path = Path(args.file).expanduser()
    if not path.is_file():
        raise CliError(f"File not found: {path}")
    if not args.i_have_rights:
        raise CliError("Confirm with --i-have-rights that you may use this audio for personal analysis.")
    fields = {"rights_confirmed": "true", "prompt_id": str(args.prompt), "source_provider": args.source}
    body, ctype = _multipart(fields, "files", path)
    res = _request("POST", "/api/assets/upload", data=body, headers={"Content-Type": ctype})["results"][0]
    if not res["ok"]:
        raise CliError(f"Import failed: {res['error']}")
    a = res["asset"]
    state = "already in library – linked" if res.get("duplicate") else f"queued for analysis ({a['status']})"
    print(f"Imported '{a['title']}' as asset #{a['id']} for prompt #{args.prompt}: {state}.")
    print(f"Open {base_url()}/tracks/{a['id']} to listen and rate; results appear under {base_url()}/experiments")
    return 0


def cmd_experiments(args: argparse.Namespace) -> int:
    for e in _request("GET", "/api/experiments"):
        al = e["alignment"]
        o = e["outcome"]
        score = f"{al['matches']}/{al['total']}" if al.get("total") else "-"
        res = f"{o['resonance_score']:.1f}" if o.get("resonance_score") is not None else "unrated"
        print(f"#{e['id']:<4} prompt #{e['prompt']['id'] if e['prompt'] else '?':<4} targets {score:<6} resonance {res:<8} {o['verdict'] or ''}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    a = _request("GET", f"/api/assets/{args.asset}")
    job = a.get("job") or {}
    print(f"asset #{a['id']} {a['title']}: {a['status']}" + (f" (stage {job.get('stage')})" if a["status"] == "processing" else ""))
    return 0 if a["status"] != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rx", description="ResonanceX local CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompts", help="list prompts")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_prompts)
    p = sub.add_parser("prompt", help="show one prompt (effective fields) or its Claude Code hand-off brief")
    p.add_argument("id", type=int)
    p.add_argument("--handoff", action="store_true", help="print the Suno MCP hand-off brief (markdown)")
    p.set_defaults(fn=cmd_prompt)
    p = sub.add_parser("import", help="import generated audio and link it to a prompt")
    p.add_argument("file")
    p.add_argument("--prompt", type=int, required=True)
    p.add_argument("--source", choices=SOURCES, default="suno_mcp")
    p.add_argument("--i-have-rights", action="store_true")
    p.set_defaults(fn=cmd_import)
    p = sub.add_parser("experiments", help="list experiments (alignment + outcome)")
    p.set_defaults(fn=cmd_experiments)
    p = sub.add_parser("status", help="analysis status of an asset")
    p.add_argument("asset", type=int)
    p.set_defaults(fn=cmd_status)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except CliError as exc:
        print(f"rx: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
