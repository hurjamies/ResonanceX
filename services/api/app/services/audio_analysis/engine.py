"""SonicDNA audio analysis engine.

Turns an audio file into:
* ``summary``    – global features grouped by category (rhythm, spectral, tonality,
                   dynamics, structure) plus a flat ``features`` vector used by
                   Resonance Core;
* ``segments``   – candidate structural segments (approximate labels);
* ``timeseries`` – downsampled time-varying features for timeline exploration;
* ``spectrogram``– a mel spectrogram rendered to PNG.

Every value is a deterministic signal-processing measurement or an algorithmic
estimate. No machine-learning genre/mood model is used in this version, so no
semantic labels are produced here. See docs/RESEARCH_METHODS.md.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import pyloudnorm as pyln
import scipy.ndimage
import scipy.signal
import scipy.stats

from app.services.audio_analysis.png import colormap, encode_png
from app.services.ingestion.audio_io import decode

ALGORITHM_VERSION = "sonicdna-1.0.0"

SR = 22050
HOP = 512
N_FFT = 2048
FPS = SR / HOP  # analysis frames per second (~43.07)
SERIES_DT = 0.1  # seconds between exported time-series points
CHROMA_DT = 0.5
WAVEFORM_BUCKETS = 6000

BANDS: dict[str, tuple[float, float]] = {
    "sub_bass": (20.0, 60.0),
    "bass": (60.0, 250.0),
    "low_mid": (250.0, 500.0),
    "mid": (500.0, 4000.0),
    "treble": (4000.0, SR / 2),
}

PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Krumhansl–Kessler key profiles
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

STAGES = ["decode", "rhythm", "spectral", "tonality", "dynamics", "structure", "render"]

ProgressFn = Callable[[str, int, int], None]


@dataclass
class AnalysisOutput:
    summary: dict[str, Any]
    segments: list[dict[str, Any]]
    timeseries: dict[str, Any]
    spectrogram_png: bytes
    analysis_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _f(x: Any, nd: int = 4) -> float | None:
    """JSON-safe rounded float."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v):
        return None
    return round(v, nd)


def _series(x: np.ndarray, nd: int = 3) -> list[float | None]:
    return [None if not np.isfinite(v) else round(float(v), nd) for v in x]


def resample_frames(x: np.ndarray, src_fps: float, dt: float, duration: float, reducer=np.mean) -> np.ndarray:
    """Aggregate a frame-rate series into fixed ``dt`` buckets."""
    n_out = max(1, int(np.ceil(duration / dt)))
    edges = np.minimum((np.arange(n_out + 1) * dt * src_fps).astype(int), len(x))
    out = np.full(n_out, np.nan)
    for i in range(n_out):
        a, b = edges[i], max(edges[i + 1], edges[i] + 1)
        if a < len(x):
            out[i] = reducer(x[a:min(b, len(x))])
    # forward-fill any trailing gaps
    mask = np.isnan(out)
    if mask.any() and (~mask).any():
        idx = np.where(~mask, np.arange(n_out), 0)
        np.maximum.accumulate(idx, out=idx)
        out = out[idx]
    return out


def _db(x: np.ndarray, floor: float = 1e-10) -> np.ndarray:
    return 10.0 * np.log10(np.maximum(x, floor))


def _smooth(x: np.ndarray, size: int) -> np.ndarray:
    if size <= 1 or len(x) < 2:
        return x
    return scipy.ndimage.uniform_filter1d(x, size=min(size, len(x)), mode="nearest")


# ----------------------------------------------------------------------------
# rhythm
# ----------------------------------------------------------------------------

def analyze_rhythm(y: np.ndarray, duration: float) -> tuple[dict[str, Any], dict[str, Any]]:
    onset_env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP, aggregate=np.median)
    onset_env = np.nan_to_num(onset_env)

    # Global onset-envelope autocorrelation → tempo candidates
    max_lag = int(FPS * 4.0)
    ac = librosa.autocorrelate(onset_env - onset_env.mean(), max_size=max_lag)
    ac = ac / (ac[0] + 1e-12)
    lags = np.arange(len(ac))
    min_lag, max_lag_bpm = int(FPS * 60 / 220), int(FPS * 60 / 40)
    region = ac[min_lag:max_lag_bpm]
    peaks, props = scipy.signal.find_peaks(region, height=0.02, distance=3)
    candidates: list[dict[str, float]] = []
    if len(peaks):
        order = np.argsort(props["peak_heights"])[::-1]
        for i in order[:6]:
            lag = peaks[i] + min_lag
            # parabolic interpolation for sub-frame lag precision
            if 1 <= lag < len(ac) - 1:
                a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]
                denom = a - 2 * b + c
                frac = 0.5 * (a - c) / denom if abs(denom) > 1e-12 else 0.0
            else:
                frac = 0.0
            bpm = 60.0 * FPS / (lag + frac)
            candidates.append({"bpm": float(bpm), "strength": float(props["peak_heights"][i])})
    pulse_clarity = float(max((c["strength"] for c in candidates), default=0.0))

    # Dynamic-programming beat tracker for beat positions
    tempo_dp, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=SR, hop_length=HOP, units="frames")
    tempo_dp = float(np.atleast_1d(tempo_dp)[0]) if np.size(tempo_dp) else 0.0
    beat_times = librosa.frames_to_time(beat_frames, sr=SR, hop_length=HOP)

    # Choose the reported tempo: the beat-tracker tempo, refined by the nearest
    # autocorrelation candidate within 4 %.
    tempo = tempo_dp
    for c in candidates:
        if tempo_dp and abs(c["bpm"] - tempo_dp) / tempo_dp < 0.04:
            tempo = c["bpm"]
            break
    if not tempo and candidates:
        tempo = candidates[0]["bpm"]

    # Half/double-time ambiguity: a strong candidate near 2x or 0.5x the tempo
    ambiguity = None
    ref_strength = next((c["strength"] for c in candidates if tempo and abs(c["bpm"] - tempo) / tempo < 0.04), pulse_clarity)
    for c in candidates:
        if not tempo:
            break
        ratio = c["bpm"] / tempo
        if not 50 <= c["bpm"] <= 200:
            continue
        # A periodic onset envelope has autocorrelation peaks at every multiple of the
        # beat period, so a slower (half/two-thirds) reading needs a clearly stronger
        # peak before it counts as a genuine metrical ambiguity.
        for target, kind, need in ((2.0, "double", 0.6), (0.5, "half", 1.15), (1.5, "three_halves", 0.6), (2 / 3, "two_thirds", 1.15)):
            if abs(ratio - target) / target < 0.05 and c["strength"] >= need * ref_strength:
                ambiguity = {"kind": kind, "alternative_bpm": _f(c["bpm"], 1), "relative_strength": _f(c["strength"] / (ref_strength + 1e-9), 2)}
                break
        if ambiguity:
            break

    # Confidence in the tempo estimate: autocorrelation strength at the tempo,
    # reduced when there is an unresolved metrical ambiguity.
    tempo_conf = float(np.clip(ref_strength / 0.5, 0, 1))
    if ambiguity:
        tempo_conf *= 0.85
    if len(beat_times) < 8:
        tempo_conf *= 0.3

    # Local tempo (8 s windows), folded to the global tempo octave
    local = librosa.feature.tempo(onset_envelope=onset_env, sr=SR, hop_length=HOP, aggregate=None)
    local = np.asarray(local, dtype=float)
    if tempo > 0 and local.size:
        k = np.round(np.log2(tempo / np.maximum(local, 1e-6)))
        local_folded = local * (2.0 ** k)
        tempo_variation = float(np.std(local_folded))
    else:
        local_folded = local
        tempo_variation = 0.0

    # Inter-beat-interval regularity
    if len(beat_times) >= 4:
        ibi = np.diff(beat_times)
        cv = float(np.std(ibi) / (np.mean(ibi) + 1e-9))
        # remove the variance caused by frame quantisation of beat positions
        # (difference of two uniform errors of width 1/FPS → variance Δ²/6)
        q = (1.0 / FPS) / np.sqrt(6.0) / (np.mean(ibi) + 1e-9)
        cv = float(np.sqrt(max(0.0, cv ** 2 - q ** 2)))
        regularity = float(np.exp(-cv / 0.06))
    else:
        cv, regularity = None, None

    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=SR, hop_length=HOP, units="frames")
    onset_times = librosa.frames_to_time(onset_frames, sr=SR, hop_length=HOP)
    onset_density = len(onset_times) / max(duration, 1e-6)
    beat_strength = (
        float(np.mean(onset_env[beat_frames]) / (np.mean(onset_env) + 1e-9)) if len(beat_frames) else None
    )

    # Sub-beat analysis: 16th-note grid between consecutive beats
    syncopation = swing_ratio = swing_conf = rhythmic_repetition = None
    if len(beat_frames) >= 8:
        grid = []
        offbeat_pos = []
        thresh = np.median(onset_env) + 0.5 * np.std(onset_env)
        for a, b in zip(beat_frames[:-1], beat_frames[1:]):
            if b - a < 4:
                continue
            seg = onset_env[a:b]
            pos = np.linspace(0, len(seg), 5)[:4].astype(int)
            # max in a small window around each grid point
            vals = [float(np.max(seg[max(0, p - 1):p + 2])) for p in pos]
            grid.append(vals)
            lo, hi = int(0.35 * len(seg)), int(0.80 * len(seg))
            if hi > lo:
                j = int(np.argmax(seg[lo:hi])) + lo
                if seg[j] > thresh:
                    offbeat_pos.append(j / len(seg))
        grid_a = np.array(grid)
        if len(grid_a) >= 4:
            on = grid_a[:, 0]
            off = grid_a[:, 1:].max(axis=1)
            syncopation = float(np.mean(np.clip(off - on, 0, None) / (on + off + 1e-9)))
            # rhythmic repetition: similarity of consecutive 4-beat patterns
            n_bars = len(grid_a) // 4
            if n_bars >= 3:
                bars = grid_a[: n_bars * 4].reshape(n_bars, 16)
                bars = bars / (np.linalg.norm(bars, axis=1, keepdims=True) + 1e-9)
                rhythmic_repetition = float(np.mean(np.sum(bars[1:] * bars[:-1], axis=1)))
        if len(offbeat_pos) >= max(6, len(beat_frames) // 6):
            p = np.median(offbeat_pos)
            swing_ratio = float(p / max(1 - p, 1e-3))
            iqr = float(np.subtract(*np.percentile(offbeat_pos, [75, 25])))
            swing_conf = float(np.clip(len(offbeat_pos) / len(beat_frames), 0, 1) * np.clip(1 - iqr / 0.2, 0, 1))

    summary = {
        "tempo_bpm": _f(tempo, 2),
        "tempo_confidence": _f(tempo_conf, 3),
        "tempo_candidates": [{"bpm": _f(c["bpm"], 1), "strength": _f(c["strength"], 3)} for c in candidates[:4]],
        "tempo_ambiguity": ambiguity,
        "tempo_variation_bpm": _f(tempo_variation, 2),
        "beat_count": int(len(beat_times)),
        "ibi_cv": _f(cv, 4),
        "rhythmic_regularity": _f(regularity, 3),
        "pulse_clarity": _f(pulse_clarity, 3),
        "onset_density": _f(onset_density, 3),
        "beat_strength": _f(beat_strength, 3),
        "syncopation": _f(syncopation, 3),
        "swing_ratio": _f(swing_ratio, 3),
        "swing_confidence": _f(swing_conf, 3),
        "rhythmic_repetition": _f(rhythmic_repetition, 3),
    }
    internals = {
        "onset_env": onset_env,
        "beat_frames": beat_frames,
        "beat_times": beat_times,
        "onset_times": onset_times,
        "local_tempo": local_folded,
    }
    return summary, internals


# ----------------------------------------------------------------------------
# spectral
# ----------------------------------------------------------------------------

def analyze_spectral(S: np.ndarray, tempo: float | None) -> tuple[dict[str, Any], dict[str, Any]]:
    power = S ** 2
    freqs = librosa.fft_frequencies(sr=SR, n_fft=N_FFT)
    centroid = librosa.feature.spectral_centroid(S=S, sr=SR)[0]
    rolloff = librosa.feature.spectral_rolloff(S=S, sr=SR, roll_percent=0.85)[0]
    flatness = librosa.feature.spectral_flatness(S=S)[0]
    bandwidth = librosa.feature.spectral_bandwidth(S=S, sr=SR)[0]
    contrast = librosa.feature.spectral_contrast(S=S, sr=SR)

    frame_energy = power.sum(axis=0)
    active = frame_energy > (np.max(frame_energy) * 1e-6)
    if not active.any():
        active[:] = True

    band_power = {}
    for name, (lo, hi) in BANDS.items():
        idx = (freqs >= lo) & (freqs < hi)
        band_power[name] = power[idx].sum(axis=0)
    total = sum(bp.sum() for bp in band_power.values()) + 1e-12
    band_ratio = {k: float(v.sum() / total) for k, v in band_power.items()}

    # Low-frequency (bass) modulation spectrum
    bass_env = np.sqrt(band_power["sub_bass"] + band_power["bass"])
    bass_env_s = _smooth(bass_env, 3)
    bass_mod = {"rate_hz": None, "strength": None, "depth": None, "beat_relation": None}
    if len(bass_env_s) > FPS * 8:
        x = bass_env_s - np.mean(bass_env_s)
        f, pxx = scipy.signal.welch(x, fs=FPS, nperseg=min(len(x), int(FPS * 16)))
        band = (f >= 0.5) & (f <= 10.0)
        if band.any() and pxx[band].sum() > 0:
            k = int(np.argmax(pxx[band]))
            rate = float(f[band][k])
            strength = float(pxx[band][k] / (np.median(pxx[band]) + 1e-12))
            bass_mod["rate_hz"] = _f(rate, 3)
            bass_mod["strength"] = _f(np.log10(strength + 1e-9), 3)  # log10 peak-to-median ratio
            if tempo:
                bass_mod["beat_relation"] = _f(rate * 60.0 / tempo, 3)
        bass_mod["depth"] = _f(np.std(bass_env_s[active]) / (np.mean(bass_env_s[active]) + 1e-9), 3)

    summary = {
        "centroid_mean_hz": _f(np.mean(centroid[active]), 1),
        "centroid_std_hz": _f(np.std(centroid[active]), 1),
        "rolloff_mean_hz": _f(np.mean(rolloff[active]), 1),
        "flatness_mean": _f(np.mean(flatness[active]), 4),
        "bandwidth_mean_hz": _f(np.mean(bandwidth[active]), 1),
        "contrast_mean": [_f(v, 2) for v in contrast[:, active].mean(axis=1)],
        "band_energy_ratio": {k: _f(v, 4) for k, v in band_ratio.items()},
        "bass_modulation": bass_mod,
        "bands_hz": {k: [v[0], v[1]] for k, v in BANDS.items()},
    }
    internals = {
        "centroid": centroid,
        "flatness": flatness,
        "rolloff": rolloff,
        "band_power": band_power,
    }
    return summary, internals


# ----------------------------------------------------------------------------
# tonality
# ----------------------------------------------------------------------------

def _key_correlations(chroma_vec: np.ndarray) -> list[tuple[float, int, str]]:
    out = []
    if np.allclose(chroma_vec, chroma_vec[0]):
        return [(0.0, 0, "major")]
    for tonic in range(12):
        for mode, prof in (("major", KK_MAJOR), ("minor", KK_MINOR)):
            r = np.corrcoef(chroma_vec, np.roll(prof, tonic))[0, 1]
            out.append((float(r), tonic, mode))
    out.sort(reverse=True)
    return out


def _chord_templates() -> tuple[np.ndarray, list[str]]:
    temps, labels = [], []
    for root in range(12):
        for quality, ints in (("", (0, 4, 7)), ("m", (0, 3, 7))):
            t = np.zeros(12)
            t[[(root + i) % 12 for i in ints]] = 1
            temps.append(t / np.linalg.norm(t))
            labels.append(PITCH_CLASSES[root] + quality)
    return np.array(temps), labels


def analyze_tonality(y_harm: np.ndarray, beat_frames: np.ndarray, duration: float) -> tuple[dict[str, Any], dict[str, Any]]:
    # Start at C2 (65 Hz): sustained sub-bass kick tails (e.g. tuned 808s) otherwise
    # dominate the pitch-class distribution and bias key estimation.
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("C2"), n_octaves=6)
    energy = chroma.sum(axis=0)
    mean_chroma = chroma.mean(axis=1)
    pcd = mean_chroma / (mean_chroma.sum() + 1e-12)
    corrs = _key_correlations(mean_chroma)
    r1, tonic, mode = corrs[0]
    r2 = corrs[1][0] if len(corrs) > 1 else 0.0
    key_conf = float(np.clip((r1 - r2) / 0.15, 0, 1) * np.clip(r1 / 0.75, 0, 1))
    profile = np.roll(KK_MAJOR if mode == "major" else KK_MINOR, tonic)

    # Local key clarity (6 s windows) → tension proxy
    win = int(FPS * 6)
    hop_w = int(FPS * CHROMA_DT)
    tension_t, tension = [], []
    for start in range(0, max(1, chroma.shape[1] - win // 2), hop_w):
        seg = chroma[:, start:start + win].mean(axis=1)
        if np.allclose(seg, seg[0]):
            tension.append(np.nan)
        else:
            tension.append(1.0 - (np.corrcoef(seg, profile)[0, 1] + 1) / 2)
        tension_t.append((start + win / 2) / FPS)
    tension = np.array(tension, dtype=float)

    # Beat-synchronous chroma → chord candidates (major/minor triads only)
    chords: list[dict[str, Any]] = []
    stability = change_rate = harmonic_repetition = None
    vocab = 0
    # beat-synchronous when beats are reliable, otherwise fixed 0.5 s blocks
    # (e.g. ambient material without a percussive pulse)
    sync_frames = beat_frames if len(beat_frames) >= 8 else np.arange(int(FPS * 0.5), chroma.shape[1], int(FPS * 0.5))
    if len(sync_frames) >= 8:
        bs = librosa.util.sync(chroma, sync_frames, aggregate=np.median)
        bs_energy = bs.sum(axis=0)
        bsn = bs / (np.linalg.norm(bs, axis=0, keepdims=True) + 1e-9)
        stability = float(np.mean(np.sum(bsn[:, 1:] * bsn[:, :-1], axis=0)))
        temps, labels = _chord_templates()
        sims = temps @ bsn
        best = np.argmax(sims, axis=0)
        best_sim = sims[best, np.arange(sims.shape[1])]
        bounds = np.concatenate([[0], sync_frames, [chroma.shape[1]]])
        bt = librosa.frames_to_time(bounds, sr=SR, hop_length=HOP)
        seq = []
        low_energy = bs_energy < 0.1 * np.median(bs_energy)
        for i in range(bs.shape[1]):
            lab = "N" if (best_sim[i] < 0.6 or low_energy[i]) else labels[best[i]]
            seq.append(lab)
        # median-filter the label sequence over 3 beats to reduce flicker
        smoothed = seq[:]
        for i in range(1, len(seq) - 1):
            if seq[i - 1] == seq[i + 1] != seq[i]:
                smoothed[i] = seq[i - 1]
        for i, lab in enumerate(smoothed):
            s, e = float(bt[i]), float(bt[min(i + 1, len(bt) - 1)])
            if chords and chords[-1]["label"] == lab:
                chords[-1]["end"] = round(e, 2)
            else:
                chords.append({"start": round(s, 2), "end": round(e, 2), "label": lab})
        named = [c for c in chords if c["label"] != "N"]
        vocab = len({c["label"] for c in named})
        change_rate = 60.0 * max(0, len(named) - 1) / max(duration, 1e-6)
        labs = [c["label"] for c in named]
        if len(labs) >= 8:
            grams = [tuple(labs[i:i + 4]) for i in range(len(labs) - 3)]
            counts: dict[tuple, int] = {}
            for g in grams:
                counts[g] = counts.get(g, 0) + 1
            repeated = sum(c for c in counts.values() if c > 1)
            harmonic_repetition = repeated / len(grams)

    summary = {
        "key": PITCH_CLASSES[tonic],
        "mode": mode,
        "key_label": f"{PITCH_CLASSES[tonic]} {'duuri' if mode == 'major' else 'molli'}",
        "key_confidence": _f(key_conf, 3),
        "key_candidates": [
            {"key": PITCH_CLASSES[t], "mode": m, "correlation": _f(r, 3)} for r, t, m in corrs[:4]
        ],
        "pitch_class_distribution": [_f(v, 4) for v in pcd],
        "harmonic_stability": _f(stability, 3),
        "chord_change_rate_per_min": _f(change_rate, 2),
        "chord_vocabulary_size": int(vocab),
        "harmonic_repetition": _f(harmonic_repetition, 3),
        "tonal_tension_mean": _f(np.nanmean(tension) if np.isfinite(tension).any() else None, 3),
        "chords": chords[:2000],
        "chord_method": "beat-synchronous chroma matched to 24 major/minor triad templates (approximate)",
    }
    internals = {"chroma": chroma, "tension": tension, "tension_t": np.array(tension_t), "chroma_energy": energy}
    return summary, internals


# ----------------------------------------------------------------------------
# dynamics
# ----------------------------------------------------------------------------

def analyze_dynamics(
    stereo: np.ndarray, mono: np.ndarray, H: np.ndarray, P: np.ndarray, S: np.ndarray, source_channels: int | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    meter = pyln.Meter(SR)
    try:
        integrated = float(meter.integrated_loudness(stereo.T.astype(np.float64)))
    except Exception:  # pragma: no cover - extremely short input
        integrated = float("nan")

    # Short-term loudness (3 s windows, 1 s hop)
    win, hop = 3 * SR, SR
    st_vals, st_t = [], []
    for start in range(0, max(1, stereo.shape[1] - win + 1), hop):
        chunk = stereo[:, start:start + win].T.astype(np.float64)
        try:
            v = float(meter.integrated_loudness(chunk))
        except Exception:
            v = float("nan")
        st_vals.append(v if np.isfinite(v) else -70.0)
        st_t.append((start + win / 2) / SR)
    st = np.maximum(np.array(st_vals), -70.0)
    lra = None
    gated = st[st > -70.0]
    if len(gated) >= 3 and np.isfinite(integrated):
        gated = gated[gated > integrated - 20.0]
        if len(gated) >= 3:
            lra = float(np.percentile(gated, 95) - np.percentile(gated, 10))

    rms = librosa.feature.rms(y=mono, frame_length=N_FFT, hop_length=HOP)[0]
    rms_db = 20 * np.log10(np.maximum(rms, 1e-6))
    peak = float(np.max(np.abs(stereo)))
    total_rms = float(np.sqrt(np.mean(mono ** 2)))
    crest = 20 * np.log10((peak + 1e-9) / (total_rms + 1e-9))
    silence_fraction = float(np.mean(rms_db < -55.0))

    h_e, p_e = float(np.sum(H ** 2)), float(np.sum(P ** 2))
    hp_ratio = h_e / (p_e + 1e-12)
    percussive_fraction = p_e / (h_e + p_e + 1e-12)

    width = corr = None
    if (source_channels or 2) >= 2:
        L, R = stereo[0], stereo[1]
        mid, side = (L + R) / 2, (L - R) / 2
        width = float(np.sqrt(np.mean(side ** 2)) / (np.sqrt(np.mean(mid ** 2)) + 1e-9))
        if np.std(L) > 1e-9 and np.std(R) > 1e-9:
            corr = float(np.corrcoef(L, R)[0, 1])

    # Texture density proxy: share of mel bands within 30 dB of the frame's loudest band
    mel = librosa.feature.melspectrogram(S=S ** 2, sr=SR, n_mels=64)
    mel_db = _db(mel)
    frame_max = mel_db.max(axis=0, keepdims=True)
    fullness = np.mean(mel_db > frame_max - 30.0, axis=0)
    nonsilent = rms_db[: fullness.shape[0]] > -55.0
    texture_density = float(np.mean(fullness[nonsilent])) if nonsilent.any() else 0.0

    summary = {
        "integrated_loudness_lufs": _f(integrated, 2),
        "loudness_range_lu": _f(lra, 2),
        "short_term_loudness_std": _f(np.std(gated) if len(gated) else None, 2),
        "peak_dbfs": _f(20 * np.log10(peak + 1e-9), 2),
        "rms_dbfs": _f(20 * np.log10(total_rms + 1e-9), 2),
        "crest_factor_db": _f(crest, 2),
        "silence_fraction": _f(silence_fraction, 4),
        "harmonic_percussive_ratio": _f(hp_ratio, 3),
        "percussive_fraction": _f(percussive_fraction, 4),
        "stereo_width": _f(width, 4),
        "stereo_correlation": _f(corr, 4),
        "texture_density": _f(texture_density, 4),
        "loudness_note": "ITU-R BS.1770 K-weighted loudness computed on a 22.05 kHz analysis copy (approximate).",
    }
    internals = {"rms_db": rms_db, "short_term": st, "short_term_t": np.array(st_t), "mel_db": mel_db}
    return summary, internals


# ----------------------------------------------------------------------------
# structure
# ----------------------------------------------------------------------------

def _checkerboard(n: int) -> np.ndarray:
    sign = np.ones((2 * n, 2 * n))
    sign[:n, n:] = -1
    sign[n:, :n] = -1
    g = scipy.signal.windows.gaussian(2 * n, std=n / 2)
    return sign * np.outer(g, g)


def analyze_structure(
    mono: np.ndarray,
    S: np.ndarray,
    chroma: np.ndarray,
    rms_db: np.ndarray,
    band_power: dict[str, np.ndarray],
    centroid: np.ndarray,
    beat_frames: np.ndarray,
    duration: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    mfcc = librosa.feature.mfcc(S=librosa.power_to_db(librosa.feature.melspectrogram(S=S ** 2, sr=SR, n_mels=64)), n_mfcc=13)
    n = min(mfcc.shape[1], chroma.shape[1], len(rms_db))
    feats = np.vstack([mfcc[:, :n], chroma[:, :n] * 3.0, rms_db[None, :n] / 10.0])

    # frames for the self-similarity analysis: beats when reliable, else 0.5 s blocks
    if len(beat_frames) >= 32:
        sync_frames = beat_frames[beat_frames < n]
        unit = "beat"
    else:
        sync_frames = np.arange(0, n, int(FPS * 0.5))
        unit = "block"
    X = librosa.util.sync(feats, sync_frames, aggregate=np.mean)
    bounds_f = np.concatenate([[0], sync_frames, [n]])
    unit_times = librosa.frames_to_time(bounds_f, sr=SR, hop_length=HOP)
    m = X.shape[1]

    Xz = (X - X.mean(axis=1, keepdims=True)) / (X.std(axis=1, keepdims=True) + 1e-9)
    Xn = Xz / (np.linalg.norm(Xz, axis=0, keepdims=True) + 1e-9)
    ssm = Xn.T @ Xn

    novelty = np.zeros(m)
    boundaries_idx: list[int] = []
    if m >= 16:
        # kernel half-width ≈ 8 s
        unit_len = duration / m
        k = int(np.clip(round(8.0 / max(unit_len, 1e-3)), 4, max(4, m // 4)))
        kern = _checkerboard(k)
        pad = np.pad(ssm, k, mode="edge")
        for i in range(m):
            novelty[i] = np.sum(pad[i:i + 2 * k, i:i + 2 * k] * kern)
        novelty = np.clip(novelty, 0, None)
        if novelty.max() > 0:
            novelty = novelty / novelty.max()
        min_sep = max(2, int(round(8.0 / max(unit_len, 1e-3))))
        pk, _ = scipy.signal.find_peaks(novelty, height=0.15, distance=min_sep, prominence=0.08)
        max_segments = max(2, int(duration / 12))
        if len(pk) > max_segments - 1:
            pk = np.sort(pk[np.argsort(novelty[pk])[::-1][: max_segments - 1]])
        # ignore boundaries in the first/last 4 s (edge effects of the kernel)
        edge_units = int(np.ceil(4.0 / max(unit_len, 1e-3)))
        boundaries_idx = [int(p) for p in pk if edge_units <= p <= m - edge_units]

    edges = [0] + boundaries_idx + [m]
    seg_bounds_t = [float(unit_times[min(e, len(unit_times) - 1)]) for e in edges]
    seg_bounds_t[-1] = duration

    # per-segment descriptors
    track_med_db = float(np.median(rms_db[rms_db > -60])) if (rms_db > -60).any() else float(np.median(rms_db))
    total_low = band_power["sub_bass"] + band_power["bass"]
    total_all = sum(band_power.values()) + 1e-12
    segs: list[dict[str, Any]] = []
    seg_vecs = []
    for i in range(len(edges) - 1):
        t0, t1 = seg_bounds_t[i], seg_bounds_t[i + 1]
        f0, f1 = int(t0 * FPS), max(int(t1 * FPS), int(t0 * FPS) + 1)
        e_db = float(np.mean(rms_db[f0:f1])) if f1 > f0 else -80.0
        first = rms_db[f0:min(f1, f0 + int(FPS * 2))]
        slope = 0.0
        if f1 - f0 > FPS * 2:
            yy = _smooth(rms_db[f0:f1], int(FPS))
            slope = float(np.polyfit(np.arange(len(yy)) / FPS, yy, 1)[0])  # dB / s
        segs.append(
            {
                "index": i,
                "start": round(t0, 2),
                "end": round(t1, 2),
                "energy_db": round(e_db, 2),
                "relative_energy_db": round(e_db - track_med_db, 2),
                "onset_energy_db": round(float(np.mean(first)) if len(first) else e_db, 2),
                "energy_slope_db_per_s": round(slope, 3),
                "bass_ratio": _f(np.sum(total_low[f0:f1]) / (np.sum(total_all[f0:f1]) + 1e-12), 4),
                "brightness_hz": _f(np.mean(centroid[f0:f1]) if f1 > f0 else None, 1),
                "boundary_strength": _f(novelty[edges[i]] if 0 < edges[i] < m else None, 3),
            }
        )
        a, b = edges[i], max(edges[i + 1], edges[i] + 1)
        seg_vecs.append(Xz[:, a:b].mean(axis=1))

    # repetition letters: greedy clustering by correlation of segment means
    letters: list[str] = []
    reps: list[np.ndarray] = []
    for v in seg_vecs:
        assigned = None
        for j, r in enumerate(reps):
            if np.std(v) > 0 and np.std(r) > 0 and np.corrcoef(v, r)[0, 1] > 0.75:
                assigned = j
                break
        if assigned is None:
            reps.append(v)
            assigned = len(reps) - 1
        letters.append(chr(ord("A") + min(assigned, 25)))
    counts = {l: letters.count(l) for l in set(letters)}

    # heuristic roles (approximate)
    energies = [s["energy_db"] for s in segs]
    peak_i = int(np.argmax(energies)) if energies else -1
    for i, s in enumerate(segs):
        s["letter"] = letters[i]
        s["repeated"] = counts[letters[i]] > 1
        role = "section"
        prev_e = energies[i - 1] if i > 0 else None
        next_e = energies[i + 1] if i + 1 < len(segs) else None
        if len(segs) == 1:
            role = "section"
        elif i == 0 and s["relative_energy_db"] < -3:
            role = "intro"
        elif i == len(segs) - 1 and (s["relative_energy_db"] < -3 or s["energy_slope_db_per_s"] < -0.15):
            role = "outro"
        elif i == peak_i and s["relative_energy_db"] > 1.5 and s["end"] - s["start"] >= 6.0:
            role = "climax"
        elif prev_e is not None and next_e is not None and s["energy_db"] < prev_e - 4 and s["energy_db"] < next_e - 3:
            role = "breakdown"
        elif prev_e is not None and i >= 1 and segs[i - 1].get("role") == "breakdown" and s["onset_energy_db"] - prev_e > 4:
            role = "drop"
        elif s["energy_slope_db_per_s"] > 0.12 and next_e is not None and next_e > s["energy_db"]:
            role = "build"
        elif s["repeated"]:
            role = "repeated"
        s["role"] = role
        s["label_confidence"] = "approximate"
    # a drop may also follow a build directly
    for i in range(1, len(segs)):
        if segs[i]["role"] in ("section", "repeated", "climax") and segs[i - 1]["role"] == "build":
            if segs[i]["onset_energy_db"] - segs[i - 1]["energy_db"] > 4:
                segs[i]["role"] = "drop"

    # energy arc from smoothed RMS (5 s)
    env = _smooth(rms_db, int(FPS * 5))
    env_t = np.arange(len(env)) / FPS
    peak_pos = float(np.argmax(env) / max(len(env) - 1, 1))
    gradual = None
    if np.argmax(env) > FPS * 10:
        pre = env[: int(np.argmax(env)) + 1][:: max(1, int(FPS / 2))]
        if len(pre) >= 5:
            gradual = float(scipy.stats.spearmanr(np.arange(len(pre)), pre).statistic)
    # longest crescendo: longest span where the 5 s-smoothed energy rises ≥ 6 dB without
    # falling more than 1.5 dB from its running maximum
    coarse = env[:: max(1, int(FPS / 2))]
    best_len, start_i, run_max = 0.0, 0, coarse[0] if len(coarse) else 0
    for i in range(1, len(coarse)):
        if coarse[i] >= run_max:
            run_max = coarse[i]
        elif coarse[i] < run_max - 1.5:
            start_i, run_max = i, coarse[i]
            continue
        if run_max - coarse[start_i] >= 6.0:
            best_len = max(best_len, (i - start_i) * 0.5)
    # sudden changes: energy jumps of >6 dB within 1 s (0.5 s smoothing)
    fast = _smooth(rms_db, int(FPS * 0.5))
    step = int(FPS)
    jumps = fast[step:] - fast[:-step] if len(fast) > step else np.array([])
    sudden_idx, _ = scipy.signal.find_peaks(jumps, height=6.0, distance=int(FPS * 4)) if len(jumps) else ([], None)
    sudden_per_min = 60.0 * len(sudden_idx) / max(duration, 1e-6)

    env_std = float(np.std(env[env > -60])) if (env > -60).any() else 0.0
    if env_std < 2.0:
        arc = "plateau"
    elif gradual is not None and gradual > 0.6 and peak_pos > 0.45:
        arc = "gradual_build"
    elif len(sudden_idx) >= 2:
        arc = "sudden_contrasts"
    elif peak_pos < 0.3:
        arc = "early_peak"
    else:
        arc = "waves"

    # peak moments: local maxima of 5 s energy, ≥ 15 s apart
    pk, _ = scipy.signal.find_peaks(env, distance=int(FPS * 15))
    pk = sorted(pk, key=lambda i: env[i], reverse=True)[:4]
    peaks = [{"time": round(float(env_t[i]), 2), "kind": "energy_peak", "value_db": round(float(env[i]), 2)} for i in sorted(pk)]
    for j in sudden_idx[:6]:
        peaks.append({"time": round(float((j + step) / FPS), 2), "kind": "sudden_rise", "value_db": round(float(jumps[j]), 2)})
    peaks.sort(key=lambda p: p["time"])

    structural_repetition = float(1.0 - len(set(letters)) / len(letters)) if letters else 0.0
    summary = {
        "segment_count": len(segs),
        "segmentation_unit": unit,
        "boundaries": [round(t, 2) for t in seg_bounds_t[1:-1]],
        "energy_arc": {
            "type": arc,
            "peak_position": _f(peak_pos, 3),
            "build_gradualness": _f(gradual, 3),
            "crescendo_seconds": _f(best_len, 1),
            "sudden_changes": int(len(sudden_idx)),
            "sudden_changes_per_min": _f(sudden_per_min, 3),
            "energy_std_db": _f(env_std, 2),
        },
        "peak_moments": peaks,
        "structural_repetition": _f(structural_repetition, 3),
        "method": "Foote novelty on a beat-synchronous self-similarity matrix (MFCC + chroma + RMS); roles are heuristic.",
    }
    internals = {"novelty": novelty, "novelty_t": unit_times[:m], "energy_env": env}
    return summary, segs, internals


# ----------------------------------------------------------------------------
# rendering helpers
# ----------------------------------------------------------------------------

def render_spectrogram(mel_db: np.ndarray, max_cols: int = 2400) -> bytes:
    m = mel_db - mel_db.max()
    m = np.clip((m + 80.0) / 80.0, 0, 1)
    if m.shape[1] > max_cols:
        factor = int(np.ceil(m.shape[1] / max_cols))
        cols = m.shape[1] // factor
        m = m[:, : cols * factor].reshape(m.shape[0], cols, factor).max(axis=2)
    m = m[::-1]  # low frequencies at the bottom
    return encode_png(colormap(m ** 1.15))


def waveform_peaks(mono: np.ndarray, buckets: int = WAVEFORM_BUCKETS) -> dict[str, Any]:
    n = len(mono)
    buckets = int(min(buckets, max(1, n // 32)))
    size = n // buckets
    x = mono[: size * buckets].reshape(buckets, size)
    scale = float(np.max(np.abs(mono)) + 1e-9)
    return {
        "buckets": buckets,
        "min": _series(x.min(axis=1) / scale, 3),
        "max": _series(x.max(axis=1) / scale, 3),
    }


# ----------------------------------------------------------------------------
# flat feature vector for Resonance Core
# ----------------------------------------------------------------------------

def flatten_features(summary: dict[str, Any], duration: float) -> dict[str, float | None]:
    r, s, t, d, st = (summary[k] for k in ("rhythm", "spectral", "tonality", "dynamics", "structure"))
    br = s["band_energy_ratio"]
    arc = st["energy_arc"]
    return {
        "tempo_bpm": r["tempo_bpm"],
        "pulse_clarity": r["pulse_clarity"],
        "rhythmic_regularity": r["rhythmic_regularity"],
        "onset_density": r["onset_density"],
        "beat_strength": r["beat_strength"],
        "syncopation": r["syncopation"],
        "rhythmic_repetition": r["rhythmic_repetition"],
        "tempo_variation_bpm": r["tempo_variation_bpm"],
        "sub_bass_ratio": br["sub_bass"],
        "bass_ratio": br["bass"],
        "low_mid_ratio": br["low_mid"],
        "mid_ratio": br["mid"],
        "treble_ratio": br["treble"],
        "spectral_centroid_hz": s["centroid_mean_hz"],
        "spectral_flatness": s["flatness_mean"],
        "bass_modulation_strength": s["bass_modulation"]["strength"],
        "bass_modulation_depth": s["bass_modulation"]["depth"],
        "major_mode": 1.0 if t["mode"] == "major" else 0.0,
        "key_confidence": t["key_confidence"],
        "harmonic_stability": t["harmonic_stability"],
        "chord_change_rate": t["chord_change_rate_per_min"],
        "tonal_tension": t["tonal_tension_mean"],
        "loudness_lufs": d["integrated_loudness_lufs"],
        "loudness_range_lu": d["loudness_range_lu"],
        "crest_factor_db": d["crest_factor_db"],
        "percussive_fraction": d["percussive_fraction"],
        "stereo_width": d["stereo_width"],
        "silence_fraction": d["silence_fraction"],
        "texture_density": d["texture_density"],
        "build_gradualness": arc["build_gradualness"],
        "peak_position": arc["peak_position"],
        "crescendo_seconds": arc["crescendo_seconds"],
        "sudden_changes_per_min": arc["sudden_changes_per_min"],
        "structural_repetition": st["structural_repetition"],
        "duration_seconds": _f(duration, 2),
    }


# ----------------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------------

def analyze_file(path: Path, source_channels: int | None = None, progress: ProgressFn | None = None,
                 max_seconds: float | None = None) -> AnalysisOutput:
    t_start = time.perf_counter()
    total = len(STAGES)

    def step(i: int) -> None:
        if progress:
            progress(STAGES[i], i, total)

    step(0)
    stereo = decode(path, SR, max_seconds=max_seconds)
    mono = stereo.mean(axis=0).astype(np.float32)
    duration = len(mono) / SR

    step(1)
    rhythm, r_int = analyze_rhythm(mono, duration)

    step(2)
    D = librosa.stft(mono, n_fft=N_FFT, hop_length=HOP)
    S = np.abs(D)
    spectral, s_int = analyze_spectral(S, rhythm["tempo_bpm"])

    step(3)
    H, P = librosa.decompose.hpss(D)
    y_harm = librosa.istft(H, hop_length=HOP, length=len(mono))
    tonality, t_int = analyze_tonality(y_harm, r_int["beat_frames"], duration)

    step(4)
    dynamics, d_int = analyze_dynamics(stereo, mono, np.abs(H), np.abs(P), S, source_channels)

    step(5)
    structure, segments, st_int = analyze_structure(
        mono, S, t_int["chroma"], d_int["rms_db"], s_int["band_power"], s_int["centroid"], r_int["beat_frames"], duration
    )

    step(6)
    summary: dict[str, Any] = {
        "algorithm_version": ALGORITHM_VERSION,
        "analysis_sample_rate": SR,
        "duration_seconds": _f(duration, 3),
        "rhythm": rhythm,
        "spectral": spectral,
        "tonality": tonality,
        "dynamics": dynamics,
        "structure": structure,
    }
    summary["features"] = flatten_features(summary, duration)

    # time series (downsampled)
    bp = s_int["band_power"]
    band_ref = max(float(np.max(v)) for v in bp.values()) + 1e-12
    bands_series = {
        k: _series(np.clip(_db(resample_frames(v, FPS, SERIES_DT, duration) / band_ref), -80, 0), 2) for k, v in bp.items()
    }
    onset = r_int["onset_env"]
    onset_n = onset / (np.percentile(onset, 99.5) + 1e-9)
    chroma_ds = np.stack([resample_frames(row, FPS, CHROMA_DT, duration) for row in t_int["chroma"]])
    chroma_ds = chroma_ds / (chroma_ds.max(axis=0, keepdims=True) + 1e-9)
    timeseries = {
        "algorithm_version": ALGORITHM_VERSION,
        "duration": _f(duration, 3),
        "dt": SERIES_DT,
        "rms_db": _series(np.clip(resample_frames(d_int["rms_db"], FPS, SERIES_DT, duration), -80, 0), 2),
        "energy_env_db": _series(np.clip(resample_frames(st_int["energy_env"], FPS, SERIES_DT, duration), -80, 0), 2),
        "centroid_hz": _series(resample_frames(s_int["centroid"], FPS, SERIES_DT, duration), 0),
        "flatness": _series(resample_frames(s_int["flatness"], FPS, SERIES_DT, duration), 4),
        "onset_strength": _series(np.clip(resample_frames(onset_n, FPS, SERIES_DT, duration, reducer=np.max), 0, 1.5), 3),
        "bands": bands_series,
        "local_tempo": _series(resample_frames(r_int["local_tempo"], FPS, 1.0, duration), 1) if len(r_int["local_tempo"]) else [],
        "local_tempo_dt": 1.0,
        "short_term_loudness": {"t": _series(d_int["short_term_t"], 2), "v": _series(d_int["short_term"], 2)},
        "tension": {"t": _series(t_int["tension_t"], 2), "v": _series(t_int["tension"], 3)},
        "novelty": {"t": _series(st_int["novelty_t"], 2), "v": _series(st_int["novelty"], 3)},
        "chroma": {"dt": CHROMA_DT, "values": [_series(row, 2) for row in chroma_ds]},
        "beats": _series(r_int["beat_times"], 3),
        "onsets": _series(r_int["onset_times"], 3),
        "waveform": waveform_peaks(mono),
    }
    png = render_spectrogram(d_int["mel_db"])
    return AnalysisOutput(
        summary=summary,
        segments=segments,
        timeseries=timeseries,
        spectrogram_png=png,
        analysis_seconds=time.perf_counter() - t_start,
    )
