"""Phase 3: provider integrations, user-controlled generation, migrations, CLI."""

from __future__ import annotations

import json
import socket
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from tests.fake_elevenlabs import FakeElevenLabs, mp3_bytes
from tests.test_workflow import upload

KEY = "test-key"


def _prompt(client, audio_dir) -> int:
    aid = upload(client, [audio_dir / "slow_86_dmin_build.wav"])[0]["asset"]["id"]
    r = client.post("/api/prompts/generate", json={"source_asset_ids": [aid], "objective": "melancholy", "controls": {"duration_seconds": 120}})
    assert r.status_code == 200, r.text
    return r.json()["prompts"][0]["id"]


@pytest.fixture(scope="module")
def fake_audio(tmp_path_factory) -> bytes:
    return mp3_bytes(tmp_path_factory.mktemp("el"))


def test_provider_status_without_key(client):
    ps = {p["id"]: p for p in client.get("/api/providers").json()}
    assert ps["suno"]["status"] == "available"
    assert ps["suno_mcp"]["status"] == "external" and ps["suno_mcp"]["generation"] is False
    el = ps["elevenlabs"]
    assert el["status"] == "not_configured" and el["configured"] is False and el["generation"] is False
    assert "music_v2_5" == el["default_model"]


def test_preview_without_key_sends_nothing_and_cannot_confirm(client, audio_dir):
    pid = _prompt(client, audio_dir)
    job = client.post("/api/generations", json={"prompt_id": pid}).json()
    assert job["status"] == "awaiting_confirmation"
    body = job["request"]["body"]
    assert body["model_id"] == "music_v2_5" and body["music_length_ms"] == 120_000
    assert "BPM" in body["prompt"] and len(body["prompt"]) <= 4100
    assert job["disclosure"] and job["cost_estimate"]["amount"] == pytest.approx(2 * 0.15)
    r = client.post(f"/api/generations/{job['id']}/confirm", json={"accepted_cost": job["cost_estimate"]["amount"], "accept_disclosure": True})
    assert r.status_code == 409 and "API-avain" in r.json()["detail"]


def test_generation_end_to_end_with_fake_provider(make_client, tmp_path, audio_dir, fake_audio):
    with FakeElevenLabs(fake_audio, api_key=KEY) as fake, make_client(
        tmp_path / "data", ELEVENLABS_API_KEY=KEY, RESONANCEX_ELEVENLABS_BASE_URL=fake.url
    ) as client:
        pid = _prompt(client, audio_dir)
        job = client.post("/api/generations", json={"prompt_id": pid, "model_id": "music_v2", "duration_seconds": 60}).json()
        assert fake.requests == [], "preparing a request must not contact the provider"
        cost = job["cost_estimate"]["amount"]
        jid = job["id"]
        # confirmation guards
        assert client.post(f"/api/generations/{jid}/confirm", json={"accepted_cost": cost, "accept_disclosure": False}).status_code == 422
        assert client.post(f"/api/generations/{jid}/confirm", json={"accepted_cost": cost + 1, "accept_disclosure": True}).status_code == 409
        assert fake.requests == []
        done = client.post(f"/api/generations/{jid}/confirm", json={"accepted_cost": cost, "accept_disclosure": True}).json()
        assert done["status"] == "completed", done
        # exact wire format
        req = fake.requests[-1]
        assert req["path"] == "/v1/music" and req["query"]["output_format"] == ["mp3_44100_128"]
        assert req["headers"]["xi-api-key"] == KEY
        assert set(req["body"]) == {"prompt", "music_length_ms", "model_id"} and req["body"]["model_id"] == "music_v2"
        # secret never leaves the server in responses
        assert KEY not in json.dumps(client.get(f"/api/generations/{jid}").json())
        assert KEY not in json.dumps(client.get("/api/providers").json())
        # result became a generated asset linked to the prompt, analysed, with an experiment
        asset = client.get(f"/api/assets/{done['result_asset_id']}").json()
        assert asset["origin"] == "generated" and asset["prompt_id"] == pid and asset["source_provider"] == "elevenlabs"
        assert asset["status"] == "completed"
        exps = client.get("/api/experiments").json()
        assert len(exps) == 1 and exps[0]["asset"]["id"] == asset["id"] and exps[0]["alignment"]["total"] > 0
        assert done["response_meta"]["song-id"] == "fake-song-1"
        el = {p["id"]: p for p in client.get("/api/providers").json()}["elevenlabs"]
        assert el["status"] == "verified" and el["last_success_at"]
        # a completed job cannot be confirmed again
        assert client.post(f"/api/generations/{jid}/confirm", json={"accepted_cost": cost, "accept_disclosure": True}).status_code == 409


def test_plan_flow_uses_provider_plan_unchanged(make_client, tmp_path, audio_dir, fake_audio):
    with FakeElevenLabs(fake_audio, api_key=KEY) as fake, make_client(
        tmp_path / "data", ELEVENLABS_API_KEY=KEY, RESONANCEX_ELEVENLABS_BASE_URL=fake.url
    ) as client:
        pid = _prompt(client, audio_dir)
        jid = client.post("/api/generations", json={"prompt_id": pid}).json()["id"]
        assert client.post(f"/api/generations/{jid}/plan", json={"accept_disclosure": False}).status_code == 422
        job = client.post(f"/api/generations/{jid}/plan", json={"accept_disclosure": True}).json()
        assert fake.requests[-1]["path"] == "/v1/music/plan"
        assert job["request"]["mode"] == "plan" and job["request"]["body"]["composition_plan"] == fake.plan
        assert "prompt" not in job["request"]["body"]
        assert job["cost_estimate"]["basis"] == "plan_length" and job["cost_estimate"]["minutes"] == pytest.approx(1.0)
        done = client.post(f"/api/generations/{jid}/confirm", json={"accepted_cost": job["cost_estimate"]["amount"], "accept_disclosure": True}).json()
        assert done["status"] == "completed"
        assert fake.requests[-1]["body"] == {"composition_plan": fake.plan, "model_id": "music_v2_5"}


def test_cost_cap_and_provider_errors(make_client, tmp_path, audio_dir, fake_audio):
    with FakeElevenLabs(fake_audio, api_key=KEY) as fake, make_client(
        tmp_path / "data", ELEVENLABS_API_KEY=KEY, RESONANCEX_ELEVENLABS_BASE_URL=fake.url, RESONANCEX_MAX_GENERATION_USD="0.2"
    ) as client:
        pid = _prompt(client, audio_dir)
        big = client.post("/api/generations", json={"prompt_id": pid, "duration_seconds": 300}).json()
        assert big["cost_estimate"]["exceeds_cap"] is True
        r = client.post(f"/api/generations/{big['id']}/confirm", json={"accepted_cost": big["cost_estimate"]["amount"], "accept_disclosure": True})
        assert r.status_code == 409 and "ylittää" in r.json()["detail"] and fake.requests == []
        # provider rejects the key
        fake.api_key = "other"
        small = client.post("/api/generations", json={"prompt_id": pid, "duration_seconds": 30}).json()
        failed = client.post(f"/api/generations/{small['id']}/confirm", json={"accepted_cost": small["cost_estimate"]["amount"], "accept_disclosure": True}).json()
        assert failed["status"] == "failed" and "401" in failed["error"] and failed["result_asset_id"] is None
        # rate limited
        fake.api_key = KEY
        fake.fail_status = 429
        j3 = client.post("/api/generations", json={"prompt_id": pid, "duration_seconds": 30}).json()
        f3 = client.post(f"/api/generations/{j3['id']}/confirm", json={"accepted_cost": j3["cost_estimate"]["amount"], "accept_disclosure": True}).json()
        assert f3["status"] == "failed" and f3["response_meta"]["error"]["retryable"] is True
        # cancel
        j4 = client.post("/api/generations", json={"prompt_id": pid, "duration_seconds": 30}).json()
        assert client.post(f"/api/generations/{j4['id']}/cancel").json()["status"] == "cancelled"
        assert client.post(f"/api/generations/{j4['id']}/confirm", json={"accepted_cost": j4["cost_estimate"]["amount"], "accept_disclosure": True}).status_code == 409
        # prompts with generation history cannot be deleted
        assert client.delete(f"/api/prompts/{pid}").status_code == 409


def test_restart_never_resends(client, audio_dir):
    from sqlmodel import Session

    from app.database.session import get_engine
    from app.models import GenerationJob
    from app.services.integrations.generation import recover_on_startup

    pid = _prompt(client, audio_dir)
    with Session(get_engine()) as s:
        q = GenerationJob(provider="elevenlabs", prompt_id=pid, status="queued", request={}, cost_estimate={"amount": 0.1})
        r = GenerationJob(provider="elevenlabs", prompt_id=pid, status="running", request={}, cost_estimate={"amount": 0.1})
        s.add_all([q, r])
        s.commit()
        qid, rid = q.id, r.id
    recover_on_startup()
    assert client.get(f"/api/generations/{qid}").json()["status"] == "awaiting_confirmation"
    rj = client.get(f"/api/generations/{rid}").json()
    assert rj["status"] == "failed" and "historia" in rj["error"]


def test_upload_source_validation(client, audio_dir):
    pid = _prompt(client, audio_dir)
    f = audio_dir / "mid_105_gmaj.wav"
    files = [("files", (f.name, f.read_bytes(), "audio/wav"))]
    assert client.post("/api/assets/upload", files=files, data={"rights_confirmed": "true", "source_provider": "suno_mcp"}).status_code == 422
    assert client.post("/api/assets/upload", files=files, data={"rights_confirmed": "true", "prompt_id": str(pid), "source_provider": "evil"}).status_code == 422
    r = client.post("/api/assets/upload", files=files, data={"rights_confirmed": "true", "prompt_id": str(pid), "source_provider": "suno_mcp"})
    assert r.json()["results"][0]["asset"]["source_provider"] == "suno_mcp"


def test_handoff_brief(client, audio_dir):
    pid = _prompt(client, audio_dir)
    h = client.get(f"/api/prompts/{pid}/handoff").json()
    md = h["markdown"]
    assert "Do not guess tool names" in md and "explicit" in md and f"--prompt {pid}" in h["import_command"]
    assert "Styles:" in md and "Never upload reference audio" in md


def test_legacy_database_is_adopted_without_data_loss(make_client, tmp_path):
    """A Phase 1–2 database (created with create_all, no alembic_version) is stamped and upgraded."""
    from alembic import command

    from app.database.migrate import alembic_config

    data = tmp_path / "data"
    data.mkdir()
    db = data / "resonancex.db"
    import sqlalchemy as sa

    eng = sa.create_engine(f"sqlite:///{db}")
    cfg = alembic_config()
    with eng.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0001_baseline")
        conn.exec_driver_sql("DROP TABLE alembic_version")
        conn.exec_driver_sql(
            "INSERT INTO media_asset (kind, origin, original_filename, stored_filename, sha256, size_bytes, tags, rights_confirmed, status, created_at, updated_at) "
            "VALUES ('audio','library','old.wav','aa/old.wav','abc',10,'{}',1,'completed','2026-01-01 00:00:00','2026-01-01 00:00:00')"
        )
    eng.dispose()
    with make_client(data) as client:
        assets = client.get("/api/assets").json()
        assert [a["original_filename"] for a in assets] == ["old.wav"] and assets[0]["source_provider"] is None
    con = sqlite3.connect(db)
    assert con.execute("select version_num from alembic_version").fetchone()[0] == "0003_music_folders"
    assert "generation_job" in {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    con.close()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_cli_import_against_running_app(make_client, tmp_path, audio_dir, monkeypatch, capsys):
    import uvicorn

    from app import cli

    with make_client(tmp_path / "data") as client:
        pid = _prompt(client, audio_dir)
        port = _free_port()
        from app.main import create_app

        server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
        t = threading.Thread(target=server.run, daemon=True)
        t.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        try:
            monkeypatch.setenv("RESONANCEX_URL", f"http://127.0.0.1:{port}")
            assert cli.main(["prompt", str(pid), "--handoff"]) == 0
            assert "ResonanceX → Suno" in capsys.readouterr().out
            song = audio_dir / "slow_95_emin.wav"
            assert cli.main(["import", str(song), "--prompt", str(pid)]) == 2  # rights flag required
            assert cli.main(["import", str(song), "--prompt", str(pid), "--source", "suno_mcp", "--i-have-rights"]) == 0
            out = capsys.readouterr().out
            assert f"for prompt #{pid}" in out
            monkeypatch.setenv("RESONANCEX_URL", "http://example.com")
            assert cli.main(["prompts"]) == 2  # refuses non-local hosts
        finally:
            server.should_exit = True
            t.join(timeout=10)
        gen = [a for a in client.get("/api/assets?origin=generated").json()]
        assert gen and gen[0]["source_provider"] == "suno_mcp" and gen[0]["prompt_id"] == pid


def test_concurrent_profile_requests_create_one_snapshot(client, audio_dir):
    """Regression: parallel requests used to race on sonic_profile_snapshot.version (HTTP 500)."""
    from concurrent.futures import ThreadPoolExecutor

    aid = upload(client, [audio_dir / "slow_86_dmin_build.wav"])[0]["asset"]["id"]
    client.put(f"/api/assets/{aid}/rating", json={"dimensions": {"preference": 7}})
    with ThreadPoolExecutor(8) as ex:
        responses = list(ex.map(lambda _: client.get("/api/profile"), range(16)))
    assert all(r.status_code == 200 for r in responses)
    assert len({r.json()["version"] for r in responses}) == 1
    assert len(client.get("/api/profile/history").json()) == 1
