"""Feature extraction on synthetic signals with known properties."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.audio_analysis.engine import ALGORITHM_VERSION, analyze_file
from app.services.audio_analysis.png import encode_png
from app.services.ingestion.audio_io import AudioDecodeError, decode, probe
from tests.signals import make_track, sine, write_mp3, write_wav


@pytest.mark.parametrize("bpm", [86, 120, 140])
def test_tempo_estimation_within_tolerance(tmp_path, bpm):
    p = write_wav(tmp_path / f"t{bpm}.wav", make_track(bpm=bpm, seconds=30))
    out = analyze_file(p, 2)
    est = out.summary["rhythm"]["tempo_bpm"]
    # accept the exact tempo (±3 %) – metrical ambiguity is reported separately
    assert abs(est - bpm) / bpm < 0.03, est
    assert out.summary["rhythm"]["beat_count"] > 30 * bpm / 60 * 0.8
    assert out.summary["rhythm"]["pulse_clarity"] > 0.5


def test_key_and_mode(tmp_path):
    p = write_wav(tmp_path / "amin.wav", make_track(bpm=100, seconds=30, key_root="A", minor=True, with_kick=False, with_hats=False))
    t = analyze_file(p, 2).summary["tonality"]
    assert (t["key"], t["mode"]) == ("A", "minor")
    p2 = write_wav(tmp_path / "gmaj.wav", make_track(bpm=100, seconds=30, key_root="G", with_kick=False, with_hats=False))
    t2 = analyze_file(p2, 2).summary["tonality"]
    assert (t2["key"], t2["mode"]) == ("G", "major")
    labels = [c["label"] for c in t2["chords"] if c["label"] != "N"]
    assert {"G", "Em", "C", "D"} <= set(labels)


def test_sine_spectral_features(tmp_path):
    p = write_wav(tmp_path / "s1k.wav", sine(1000.0, seconds=6))
    s = analyze_file(p, 2).summary["spectral"]
    assert abs(s["centroid_mean_hz"] - 1000) < 60
    assert s["band_energy_ratio"]["mid"] > 0.95
    p2 = write_wav(tmp_path / "s80.wav", sine(80.0, seconds=6))
    s2 = analyze_file(p2, 2).summary["spectral"]
    assert s2["band_energy_ratio"]["bass"] > 0.9


def test_loudness_and_dynamics(tmp_path):
    loud = write_wav(tmp_path / "loud.wav", sine(1000.0, seconds=6, amp=0.5))
    quiet = write_wav(tmp_path / "quiet.wav", sine(1000.0, seconds=6, amp=0.05))
    l1 = analyze_file(loud, 2).summary["dynamics"]["integrated_loudness_lufs"]
    l2 = analyze_file(quiet, 2).summary["dynamics"]["integrated_loudness_lufs"]
    assert abs((l1 - l2) - 20.0) < 0.5  # 10x amplitude = 20 dB
    d = analyze_file(loud, 2).summary["dynamics"]
    assert abs(d["crest_factor_db"] - 3.01) < 0.3  # sine crest factor
    assert d["stereo_width"] < 0.01  # identical channels


def test_crescendo_detected(tmp_path):
    p = write_wav(tmp_path / "cres.wav", make_track(bpm=96, seconds=60, crescendo=True))
    arc = analyze_file(p, 2).summary["structure"]["energy_arc"]
    assert arc["type"] == "gradual_build"
    assert arc["build_gradualness"] > 0.8
    assert arc["peak_position"] > 0.8


def test_outputs_complete_and_versioned(tmp_path):
    p = write_mp3(tmp_path / "x.mp3", make_track(bpm=110, seconds=30))
    out = analyze_file(p, 2)
    assert out.summary["algorithm_version"] == ALGORITHM_VERSION
    feats = out.summary["features"]
    assert feats["tempo_bpm"] and feats["duration_seconds"] > 29
    ts = out.timeseries
    n = len(ts["rms_db"])
    assert abs(n * ts["dt"] - out.summary["duration_seconds"]) < 0.2
    for band in ("sub_bass", "bass", "low_mid", "mid", "treble"):
        assert len(ts["bands"][band]) == n
    assert len(ts["waveform"]["min"]) == ts["waveform"]["buckets"]
    assert out.spectrogram_png.startswith(b"\x89PNG")
    assert len(out.segments) >= 1 and out.segments[0]["start"] == 0.0


def test_probe_and_decode_errors(tmp_path):
    bad = tmp_path / "bad.mp3"
    bad.write_bytes(b"\x00" * 2000)
    with pytest.raises(AudioDecodeError):
        probe(bad)
    good = write_wav(tmp_path / "g.wav", sine(440, seconds=2))
    info = probe(good)
    assert info.channels == 2 and abs(info.duration_seconds - 2.0) < 0.05
    y = decode(good, 22050)
    assert y.shape[0] == 2 and abs(y.shape[1] / 22050 - 2.0) < 0.05


def test_png_encoder():
    img = np.zeros((4, 5, 3), dtype=np.uint8)
    data = encode_png(img)
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and b"IEND" in data
