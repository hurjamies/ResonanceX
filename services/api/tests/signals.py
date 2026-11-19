"""Synthetic test signals with known musical properties."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100

NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _env(n: int, attack: float = 0.005, decay: float = 0.15, sr: int = SR) -> np.ndarray:
    t = np.arange(n) / sr
    return np.minimum(1.0, t / attack) * np.exp(-t / decay)


def kick(sr: int = SR, length: float = 0.35) -> np.ndarray:
    n = int(sr * length)
    t = np.arange(n) / sr
    f = 50 + 90 * np.exp(-t * 30)
    phase = 2 * np.pi * np.cumsum(f) / sr
    return np.sin(phase) * _env(n, 0.002, 0.12, sr)


def hat(sr: int = SR, length: float = 0.06, rng: np.random.Generator | None = None) -> np.ndarray:
    rng = rng or np.random.default_rng(0)
    n = int(sr * length)
    noise = rng.standard_normal(n)
    noise = np.diff(noise, prepend=0)  # crude high-pass
    return 0.25 * noise * _env(n, 0.001, 0.015, sr)


def chord_tone(root_midi: int, minor: bool, dur: float, sr: int = SR) -> np.ndarray:
    n = int(sr * dur)
    t = np.arange(n) / sr
    ints = (0, 3, 7) if minor else (0, 4, 7)
    y = np.zeros(n)
    for i in ints:
        f = midi_hz(root_midi + i)
        for h, a in ((1, 1.0), (2, 0.4), (3, 0.2)):
            y += a * np.sin(2 * np.pi * f * h * t)
    fade = np.minimum(1, np.minimum(t / 0.05, (dur - t) / 0.05))
    return 0.08 * y * fade


def make_track(
    bpm: float = 120.0,
    seconds: float = 30.0,
    key_root: str = "C",
    minor: bool = False,
    with_kick: bool = True,
    with_hats: bool = True,
    bass_gain: float = 0.6,
    crescendo: bool = False,
    sr: int = SR,
) -> np.ndarray:
    n = int(sr * seconds)
    y = np.zeros(n)
    beat = 60.0 / bpm
    k = kick(sr)
    rng = np.random.default_rng(1)
    t = 0.0
    while t < seconds:
        i = int(t * sr)
        if with_kick:
            seg = k[: max(0, min(len(k), n - i))]
            y[i:i + len(seg)] += bass_gain * seg
        if with_hats:
            j = int((t + beat / 2) * sr)
            h = hat(sr, rng=rng)
            seg = h[: max(0, min(len(h), n - j))]
            if j < n:
                y[j:j + len(seg)] += seg
        t += beat
    # I–vi–IV–V style progression (relative to key), one chord per bar
    root = 60 + NOTE[key_root]
    prog = [(0, minor), (9 if not minor else 8, not minor), (5, minor), (7, False)]
    bar = 4 * beat
    tb, ci = 0.0, 0
    while tb < seconds:
        off, mnr = prog[ci % len(prog)]
        dur = min(bar, seconds - tb)
        c = chord_tone(root + off - 12 * (1 if off > 6 else 0), mnr, dur, sr)
        i = int(tb * sr)
        y[i:i + len(c)] += c[: n - i]
        tb += bar
        ci += 1
    if crescendo:
        y *= np.linspace(0.15, 1.0, n)
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.9
    return y.astype(np.float32)


def sine(freq: float, seconds: float = 10.0, sr: int = SR, amp: float = 0.5) -> np.ndarray:
    t = np.arange(int(sr * seconds)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def write_wav(path: Path, y: np.ndarray, sr: int = SR, stereo: bool = True) -> Path:
    data = np.stack([y, y], axis=1) if stereo and y.ndim == 1 else y
    sf.write(str(path), data, sr, subtype="PCM_16")
    return path


def write_mp3(path: Path, y: np.ndarray, sr: int = SR) -> Path:
    import subprocess

    wav = path.with_suffix(".tmp.wav")
    write_wav(wav, y, sr)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-b:a", "192k", str(path)], check=True)
    wav.unlink()
    return path
