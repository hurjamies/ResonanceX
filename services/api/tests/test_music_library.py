"""Persistent folders and the genre → Suno / whole library → suggestion flows."""

from __future__ import annotations

import io
import math
import struct
import wave

from sqlmodel import Session

from app.database.session import get_engine
from app.models import AudioAnalysis, ExperienceRating, MediaAsset, MusicFolderEntry
from app.services.audio_analysis.engine import ALGORITHM_VERSION


def seed_track(title, *, folder_id=None, preference=None, affect=5, bpm=100, status="completed", version=ALGORITHM_VERSION, genre_tag="original metadata"):
    with Session(get_engine()) as session:
        asset = MediaAsset(original_filename=f"{title}.wav", stored_filename=f"{title}.wav", sha256=title,
                           size_bytes=100, title=title, status=status, genre_tag=genre_tag)
        session.add(asset)
        session.commit()
        session.refresh(asset)
        session.add(AudioAnalysis(asset_id=asset.id, algorithm_version=version, timeseries_file="unused.json",
                                  summary={"features": {"tempo_bpm": bpm, "bass_ratio": 0.4, "pulse_clarity": 0.7},
                                           "rhythm": {}, "structure": {"energy_arc": {"type": "gradual_build"}}}))
        if folder_id:
            session.add(MusicFolderEntry(asset_id=asset.id, folder_id=folder_id))
        if preference is not None:
            session.add(ExperienceRating(asset_id=asset.id, dimensions={"preference": preference, "emotional_intensity": affect}))
        session.commit()
        return asset.id


def test_folders_validate_names_and_persist(make_client, tmp_path):
    data = tmp_path / "persistent"
    with make_client(data) as client:
        folders = client.get("/api/music/folders").json()
        assert [f["name"] for f in folders] == ["Metalli", "Elektroninen", "Country"]
        assert client.post("/api/music/folders", json={"name": "  "}).status_code == 422
        assert client.post("/api/music/folders", json={"name": "mEtAlLi"}).status_code == 409
        assert client.post("/api/music/folders", json={"name": "x" * 61}).status_code == 422
        response = client.post("/api/music/folders", json={"name": "  Progressiivinen   metalli  "})
        assert response.status_code == 201
        folder = response.json()
        assert folder["name"] == "Progressiivinen metalli"
        aid = seed_track("Own song")
        assert client.patch(f"/api/assets/{aid}", json={"folder_id": folder["id"]}).json()["folder_id"] == folder["id"]
        assert client.patch(f"/api/assets/{aid}", json={"folder_id": 999}).status_code == 404
        assert client.get(f"/api/assets/{aid}").json()["genre_tag"] == "original metadata"
    with make_client(data) as reopened:
        assert reopened.get(f"/api/assets/{aid}").json()["folder_id"] == folder["id"]
        assert reopened.get("/api/assets").json()[0]["folder_id"] == folder["id"]
        exported = reopened.get("/api/export/all.json").json()
        assert exported["music_folder_entries"] == [{"asset_id": aid, "folder_id": folder["id"]}]
        assert len(exported["music_folders"]) == 4
        assert reopened.patch(f"/api/assets/{aid}", json={"folder_id": None}).json()["folder_id"] is None
        reopened.patch(f"/api/assets/{aid}", json={"folder_id": folder["id"]})
        assert reopened.delete(f"/api/assets/{aid}").status_code == 200
        assert reopened.get("/api/export/all.json").json()["music_folder_entries"] == []


def test_upload_into_folder_and_move_duplicate(client, monkeypatch):
    # Exercise real decoding, hashing, duplicate detection, and folder persistence;
    # the analysis worker is tested separately and need not run here.
    monkeypatch.setattr("app.api.assets.runner.submit", lambda _: None)
    samples = b"".join(struct.pack("<h", int(4000 * math.sin(2 * math.pi * 220 * i / 22050))) for i in range(33075))
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        wav.writeframes(samples)
    def upload(folder_id, rights="true"):
        return client.post("/api/assets/upload", files=[("files", ("song.wav", audio.getvalue(), "audio/wav"))],
                           data={"rights_confirmed": rights, "folder_id": str(folder_id)})
    assert upload(999).status_code == 404
    assert upload(1, "false").status_code == 422
    first = upload(1).json()["results"][0]
    assert first["ok"] and first["asset"]["folder_id"] == 1
    duplicate = upload(2).json()["results"][0]
    assert duplicate["duplicate"] and duplicate["asset"]["id"] == first["asset"]["id"]
    assert duplicate["asset"]["folder_id"] == 2
    folders = client.get("/api/music/folders").json()
    assert folders[0]["track_count"] == 0 and folders[1]["track_count"] == 1
    assert folders[1]["pending_count"] == 1 and folders[1]["ready_count"] == 0


def test_folder_prompt_uses_only_that_genre_and_enjoyed_tracks(client):
    metal = seed_track("Metal favourite", folder_id=1, preference=9, bpm=140)
    seed_track("Unpleasant metal", folder_id=1, preference=2, affect=10, bpm=60)
    seed_track("Electronic favourite", folder_id=2, preference=10, bpm=100)
    seed_track("Outdated metal", folder_id=1, preference=10, version="obsolete")
    result = client.post("/api/music/folders/1/prompt")
    assert result.status_code == 200, result.text
    prompt = result.json()["prompt"]
    assert prompt["source_asset_ids"] == [metal]
    assert prompt["compiled"]["primary_genre"] == "metal"
    assert prompt["compiled"]["hybrid_genre"] is None
    assert prompt["compiled"]["style"].startswith("metal,")
    assert prompt["compiled"]["tempo_hint"] == 140
    assert prompt["specification"]["extra"]["music_library"]["folder_id"] == 1
    assert client.get(f"/api/prompts?batch_id={result.json()['batch_id']}").json()[0]["id"] == prompt["id"]
    assert client.post("/api/music/folders/3/prompt").status_code == 422
    assert client.post("/api/music/folders/999/prompt").status_code == 404
    seed_track("Disliked country", folder_id=3, preference=1)
    assert client.post("/api/music/folders/3/prompt").status_code == 422


def test_suggestion_compares_all_genres_but_never_confuses_affect_and_enjoyment(client):
    metal = seed_track("Metal", folder_id=1, preference=9, bpm=140)
    electronic = seed_track("Electronic", folder_id=2, preference=8, bpm=100)
    seed_track("Country disliked", folder_id=3, preference=2, affect=10, bpm=60)
    seed_track("Unrated", bpm=90)
    proposal = client.get("/api/music/suggestion").json()
    assert proposal["ready"] and proposal["tracks_considered"] == 4 and proposal["ratings_count"] == 3
    assert proposal["genres"] == ["Metalli", "Elektroninen"]
    assert set(proposal["source_asset_ids"]) == {metal, electronic}
    result = client.post("/api/music/suggestion/prompt")
    assert result.status_code == 200, result.text
    prompt = result.json()["prompt"]
    assert set(prompt["source_asset_ids"]) == {metal, electronic}
    assert prompt["compiled"]["hybrid_genre"] == "metal / electronic"
    assert prompt["compiled"]["tempo_hint"] == 120
    assert prompt["compiled"]["mode_label"] == "Sinulle"
    assert any("sopivuutta" in s for s in prompt["compiled"]["uncertainty_fi"])
    assert proposal["sound_summary"] == ["Rytminen pohja noin 120 BPM", "Asteittainen nousu"]
    # It changes after feedback, without a stale saved proposal.
    client.put(f"/api/assets/{electronic}/rating", json={"dimensions": {"preference": 2}})
    assert client.get("/api/music/suggestion").json()["source_asset_ids"] == [metal]


def test_suggestion_empty_negative_only_and_unfiled_music(client):
    assert client.get("/api/music/suggestion").json()["ready"] is False
    assert client.post("/api/music/suggestion/prompt").status_code == 422
    seed_track("Disliked", folder_id=1, preference=1, affect=10)
    assert client.get("/api/music/suggestion").json()["ready"] is False
    liked = seed_track("Unfiled favourite", preference=8)
    proposal = client.get("/api/music/suggestion").json()
    assert proposal["source_asset_ids"] == [liked]
    assert proposal["genres"] == ["original metadata"]
    prompt = client.post("/api/music/suggestion/prompt").json()["prompt"]
    assert prompt["specification"]["genre_hypotheses"][0]["basis"] == "file_metadata"


def test_suggestion_does_not_let_a_large_folder_hide_other_favourites(client):
    for i in range(14):
        seed_track(f"Metal {i}", folder_id=1, preference=8)
    electronic = seed_track("Electronic", folder_id=2, preference=9)
    country = seed_track("Country", folder_id=3, preference=8)
    proposal = client.get("/api/music/suggestion").json()
    assert proposal["tracks_considered"] == 16 and len(proposal["source_asset_ids"]) == 12
    assert electronic in proposal["source_asset_ids"] and country in proposal["source_asset_ids"]
    assert proposal["genres"][0] == "Elektroninen"


def test_usable_genre_tag_rejects_non_musical_metadata():
    from app.services.prompt_engine.builder import usable_genre_tag
    for junk in ["Music", "News & Politics", "  people &  blogs ", "Other", "(17)", "17", "", None, "x" * 41]:
        assert usable_genre_tag(junk) is None, junk
    assert usable_genre_tag("  Progressive   Trance ") == "Progressive Trance"
    assert usable_genre_tag("Soundtrack") == "Soundtrack"


def test_platform_categories_never_become_suno_styles(client):
    # Typical YouTube downloads: the "genre" tag is the video category.
    liked = seed_track("Downloaded favourite", preference=9, genre_tag="News & Politics")
    other = seed_track("Downloaded other", preference=8, genre_tag="Music")
    proposal = client.get("/api/music/suggestion").json()
    assert proposal["ready"] and set(proposal["source_asset_ids"]) == {liked, other}
    assert proposal["genres"] == [] and proposal["genre_styles"] == []
    prompt = client.post("/api/music/suggestion/prompt").json()["prompt"]
    # Prompt Studio's own generator must ignore them as well.
    studio = client.post("/api/prompts/generate", json={"source_asset_ids": [liked, other], "objective": None, "controls": {}})
    assert studio.status_code == 200, studio.text
    for p in [prompt] + studio.json()["prompts"]:
        text = " ".join(str(p["compiled"].get(k) or "") for k in ("style", "primary_genre", "hybrid_genre")).casefold()
        assert "politics" not in text and "music with" not in text, p["compiled"]["style"]
        assert all(h["name"].casefold() not in {"music", "news & politics"} for h in p["specification"]["genre_hypotheses"])
