"""End-to-end API workflow: acceptance workflows A–G of the first release."""

from __future__ import annotations

from pathlib import Path


def upload(client, paths: list[Path], **form):
    files = [("files", (p.name, p.read_bytes(), "application/octet-stream")) for p in paths]
    data = {"rights_confirmed": "true", **{k: str(v) for k, v in form.items()}}
    r = client.post("/api/assets/upload", files=files, data=data)
    assert r.status_code == 200, r.text
    return r.json()["results"]


RATINGS = {
    # resonance-heavy slow, bass-heavy builds; weak responses for fast / light bass
    "slow_92_amin_build.mp3": dict(preference=8, bodily_resonance=9, emotional_intensity=8, immersion=9, significance=7, melancholy=7),
    "slow_86_dmin_build.wav": dict(preference=9, bodily_resonance=9, emotional_intensity=9, immersion=8, significance=8, melancholy=8),
    "slow_95_emin.wav": dict(preference=7, bodily_resonance=8, emotional_intensity=7, immersion=8, significance=6, melancholy=6),
    "steady_120_cmaj.wav": dict(preference=6, bodily_resonance=4, emotional_intensity=3, immersion=4, significance=2, melancholy=1),
    "mid_105_gmaj.wav": dict(preference=3, bodily_resonance=2, emotional_intensity=2, immersion=3, significance=1, melancholy=2),
    "fast_140_light_bass.wav": dict(preference=2, bodily_resonance=1, emotional_intensity=2, immersion=1, significance=1, melancholy=0),
}


def test_upload_validation(client, audio_dir):
    r = client.post("/api/assets/upload", files=[("files", ("a.wav", b"x", "audio/wav"))], data={"rights_confirmed": "false"})
    assert r.status_code == 422
    res = upload(client, [audio_dir / "notes.txt", audio_dir / "corrupt.mp3", audio_dir / "steady_120_cmaj.wav"])
    assert res[0]["ok"] is False and res[0]["code"] == "unsupported_format"
    assert res[1]["ok"] is False and res[1]["code"] == "decode_failed"
    assert res[2]["ok"] is True and res[2]["asset"]["status"] == "completed"
    # duplicate detection
    dup = upload(client, [audio_dir / "steady_120_cmaj.wav"])
    assert dup[0]["duplicate"] is True and dup[0]["asset"]["id"] == res[2]["asset"]["id"]
    assert len(client.get("/api/assets").json()) == 1


def test_rating_validation(client, audio_dir):
    aid = upload(client, [audio_dir / "steady_120_cmaj.wav"])[0]["asset"]["id"]
    assert client.put(f"/api/assets/{aid}/rating", json={"dimensions": {"preference": 11}}).status_code == 422
    assert client.put(f"/api/assets/{aid}/rating", json={"dimensions": {"nonsense": 3}}).status_code == 422
    assert client.put(f"/api/assets/{aid}/rating", json={"body_responses": ["telepathy"]}).status_code == 422
    assert client.post(f"/api/assets/{aid}/markers", json={"start_seconds": 9999, "label": "chills"}).status_code == 422
    assert client.post(f"/api/assets/{aid}/markers", json={"start_seconds": 3, "label": "bogus"}).status_code == 422


def test_full_workflow(make_client, tmp_path, audio_dir):
    data_dir = tmp_path / "data"
    with make_client(data_dir) as client:
        # ---- Workflow A: analyse music
        res = upload(client, [audio_dir / n for n in RATINGS])
        ids = {r["filename"]: r["asset"]["id"] for r in res}
        assert all(r["ok"] for r in res)
        a = client.get(f"/api/assets/{ids['slow_92_amin_build.mp3']}/analysis").json()
        assert abs(a["summary"]["rhythm"]["tempo_bpm"] - 92) < 3
        assert a["summary"]["tonality"]["mode"] == "minor"
        ts = client.get(f"/api/assets/{ids['slow_92_amin_build.mp3']}/timeseries").json()
        assert len(ts["rms_db"]) > 100
        audio = client.get(f"/api/assets/{ids['slow_92_amin_build.mp3']}/audio", headers={"Range": "bytes=0-99"})
        assert audio.status_code == 206 and len(audio.content) == 100
        assert client.get(f"/api/assets/{ids['steady_120_cmaj.wav']}/spectrogram.png").content[:4] == b"\x89PNG"

        # ---- Workflow B: evaluate experience (+ markers)
        for name, dims in RATINGS.items():
            body = {"dimensions": dims, "body_responses": ["chills"] if dims["bodily_resonance"] >= 8 else [],
                    "reflections": {"feel": "Testi"}, "context": {"playback": "headphones", "volume": "loud"}}
            r = client.put(f"/api/assets/{ids[name]}/rating", json=body)
            assert r.status_code == 200, r.text
        for name in ("slow_92_amin_build.mp3", "slow_86_dmin_build.wav", "slow_95_emin.wav"):
            for t in (30.0, 36.0):
                assert client.post(f"/api/assets/{ids[name]}/markers", json={"start_seconds": t, "label": "chills", "intensity": 8}).status_code == 200
        c = client.post("/api/comparisons", json={"asset_a_id": ids["slow_86_dmin_build.wav"], "asset_b_id": ids["fast_140_light_bass.wav"], "stronger": "a", "enjoyed": "a"})
        assert c.status_code == 200

        # ---- Workflow C: discover patterns
        prof = client.get("/api/profile").json()
        assert prof["counts"]["tracks_rated"] == 6
        assert prof["data_stage"] == "preliminary"
        assert prof["version"] >= 1
        top_ids = set(prof["group_definition"]["top"])
        assert top_ids and top_ids <= {ids["slow_92_amin_build.mp3"], ids["slow_86_dmin_build.wav"], ids["slow_95_emin.wav"]}
        assert prof["insights"], "expected grounded insights"
        for ins in prof["insights"]:
            assert ins["evidence_level"] in ("observation", "preliminary", "supported")
            assert ins["explanation"]
        tempo_target = next(f for f in prof["targets"]["features"] if f["feature"] == "tempo_bpm")
        assert tempo_target["median"] < 100 and tempo_target["direction"] == "low"
        # the profile is cached per unchanged input
        assert client.get("/api/profile").json()["version"] == prof["version"]
        sim = client.get(f"/api/assets/{ids['slow_92_amin_build.mp3']}/similar").json()
        assert len(sim) >= 3

        # ---- Workflow D: generate Suno prompts
        g = client.post("/api/prompts/generate", json={"source_asset_ids": [ids["slow_86_dmin_build.wav"]], "objective": "melancholy", "controls": {"vocal": "instrumental"}})
        assert g.status_code == 200, g.text
        prompts = g.json()["prompts"]
        assert [p["mode"] for p in prompts] == ["deep_resonance", "intensification", "unknown_territory"]
        styles = [p["compiled"]["style"] for p in prompts]
        assert len(set(styles)) == 3, styles
        for p in prompts:
            comp = p["compiled"]
            assert comp["title"] and comp["style"] and comp["lyrics"].startswith("[")
            assert "BPM" in comp["style"]
            assert comp["evidence_fi"] and comp["uncertainty_fi"]
            assert p["specification"]["target_features"]
        assert prompts[2]["compiled"]["settings"]["model"] == "v6-wild"
        assert prompts[2]["compiled"]["experimental_hypotheses"]
        # edit, duplicate, export
        pid = prompts[0]["id"]
        e = client.patch(f"/api/prompts/{pid}", json={"edited": {"title": "Oma nimi"}, "saved": True})
        assert e.json()["effective"]["title"] == "Oma nimi" and e.json()["compiled"]["title"] != "Oma nimi"
        d = client.post(f"/api/prompts/{pid}/duplicate").json()
        assert d["parent_id"] == pid and d["compiled"]["title"] == "Oma nimi"
        assert "Style of Music:" in client.get(f"/api/prompts/{pid}/export?format=text").text
        assert client.get(f"/api/prompts/{pid}/elevenlabs-plan").json()["sections"]
        assert client.patch(f"/api/prompts/{pid}", json={"edited": {"evil": 1}}).status_code == 422

        # no evidence → honest refusal
        assert client.post("/api/prompts/generate", json={"source_asset_ids": [999]}).status_code == 422

        # ---- Workflow E is external (Suno). Workflow F: import the result
        gen = upload(client, [audio_dir / "slow_95_emin.wav"], prompt_id=pid)  # duplicate content → linking rule
        assert gen[0]["ok"]
        from tests.signals import make_track, write_wav

        result_file = write_wav(tmp_path / "suno_result.wav", make_track(bpm=88, seconds=40, key_root="B", minor=True, crescendo=True, bass_gain=0.8))
        gen = upload(client, [result_file], prompt_id=pid)
        gen_id = gen[0]["asset"]["id"]
        assert gen[0]["asset"]["origin"] == "generated" and gen[0]["asset"]["prompt_id"] == pid
        exps = client.get("/api/experiments").json()
        assert len(exps) == 1
        exp = exps[0]
        assert exp["alignment"]["total"] > 0
        tempo_row = next(r for r in exp["alignment"]["features"] if r["feature"] == "tempo_bpm")
        assert tempo_row["measured"] is not None
        assert exp["outcome"]["rated"] is False
        client.put(f"/api/assets/{gen_id}/rating", json={"dimensions": {"preference": 9, "bodily_resonance": 9, "emotional_intensity": 9, "immersion": 9, "significance": 8}})
        exp = client.get(f"/api/experiments/{exp['id']}").json()
        assert exp["outcome"]["rated"] is True and exp["outcome"]["verdict"] is not None
        prof2 = client.get("/api/profile").json()
        assert prof2["version"] > prof["version"]
        assert prof2["counts"]["generated_tracks"] == 1 and prof2["counts"]["tracks_rated"] == 7

        overview = client.get("/api/overview").json()
        assert overview["counts"]["prompts"] >= 4

    # ---- Workflow G: reopen the application – everything persists
    with make_client(data_dir) as client2:
        assets = client2.get("/api/assets").json()
        assert len(assets) == 7
        r = client2.get(f"/api/assets/{ids['slow_86_dmin_build.wav']}/rating").json()
        assert r["dimensions"]["bodily_resonance"] == 9 and r["reflections"]["feel"] == "Testi"
        assert len(client2.get(f"/api/assets/{ids['slow_86_dmin_build.wav']}/markers").json()) == 2
        assert len(client2.get("/api/prompts").json()) >= 4
        assert len(client2.get("/api/experiments").json()) == 1
        assert client2.get("/api/profile").json()["version"] == prof2["version"]
        assert len(client2.get(f"/api/assets/{ids['slow_86_dmin_build.wav']}/rating/history").json()) == 1
        csv = client2.get("/api/export/ratings.csv").text
        assert csv.count("\n") == 8
        full = client2.get("/api/export/all.json").json()
        assert full["format"] == "resonancex-export" and len(full["media_assets"]) == 7


def test_failed_analysis_does_not_lose_others(client, audio_dir, monkeypatch, tmp_path):
    ok = upload(client, [audio_dir / "steady_120_cmaj.wav"])[0]["asset"]
    import app.workers.jobs as jobs

    def boom(*a, **k):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(jobs, "analyze_file", boom)
    bad = upload(client, [audio_dir / "mid_105_gmaj.wav"])[0]["asset"]
    assert bad["status"] == "failed" and "synthetic failure" in bad["error"]
    assert client.get(f"/api/assets/{ok['id']}/analysis").status_code == 200
    monkeypatch.undo()
    r = client.post(f"/api/assets/{bad['id']}/reanalyze")
    assert r.json()["queued"] is True
    assert client.get(f"/api/assets/{bad['id']}").json()["status"] == "completed"


def test_empty_profile_is_honest(client):
    prof = client.get("/api/profile").json()
    assert prof["data_stage"] == "empty"
    assert prof["insights"] == [] and prof["targets"]["basis"] == "none"
    ov = client.get("/api/overview").json()
    assert ov["next_action"]["kind"] == "upload"
