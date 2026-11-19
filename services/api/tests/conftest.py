from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.signals import make_track, write_mp3, write_wav  # noqa: E402


@pytest.fixture(scope="session")
def audio_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("audio")
    write_wav(d / "steady_120_cmaj.wav", make_track(bpm=120, seconds=40, key_root="C"))
    write_mp3(d / "slow_92_amin_build.mp3", make_track(bpm=92, seconds=45, key_root="A", minor=True, crescendo=True))
    write_wav(d / "fast_140_light_bass.wav", make_track(bpm=140, seconds=35, key_root="F#", bass_gain=0.15))
    write_wav(d / "slow_86_dmin_build.wav", make_track(bpm=86, seconds=40, key_root="D", minor=True, crescendo=True, bass_gain=0.8))
    write_wav(d / "mid_105_gmaj.wav", make_track(bpm=105, seconds=35, key_root="G", bass_gain=0.3))
    write_wav(d / "slow_95_emin.wav", make_track(bpm=95, seconds=40, key_root="E", minor=True, crescendo=True, bass_gain=0.9))
    (d / "corrupt.mp3").write_bytes(b"ID3\x03\x00not really an mp3" * 50)
    (d / "notes.txt").write_text("hello")
    return d


def _make_client(data_dir: Path):
    import os

    os.environ["RESONANCEX_DATA_DIR"] = str(data_dir)
    os.environ["RESONANCEX_SYNCHRONOUS_JOBS"] = "true"
    os.environ["RESONANCEX_SERVE_FRONTEND"] = "false"
    from app.config import get_settings
    from app.database import session as dbs

    get_settings.cache_clear()
    dbs.reset_engine()
    from fastapi.testclient import TestClient

    from app.main import create_app

    return TestClient(create_app())


@pytest.fixture()
def make_client():
    return _make_client


@pytest.fixture()
def client(tmp_path):
    with _make_client(tmp_path / "data") as c:
        yield c
