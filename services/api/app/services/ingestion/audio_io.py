"""Audio file probing and decoding via FFmpeg.

FFmpeg is used (rather than relying on libsndfile alone) so that MP3, M4A/AAC,
FLAC, WAV, OGG, Opus and AIFF all decode through a single well-tested pipeline.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".aif", ".aiff"}

MIME_BY_EXT = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".aif": "audio/aiff",
    ".aiff": "audio/aiff",
}


class AudioDecodeError(Exception):
    """Raised when a file cannot be probed or decoded."""


@dataclass
class ProbeResult:
    duration_seconds: float
    sample_rate: int | None
    channels: int | None
    codec: str | None
    container_format: str | None
    bit_rate: int | None
    tags: dict[str, Any] = field(default_factory=dict)

    @property
    def title(self) -> str | None:
        return _tag(self.tags, "title")

    @property
    def artist(self) -> str | None:
        return _tag(self.tags, "artist") or _tag(self.tags, "album_artist")

    @property
    def album(self) -> str | None:
        return _tag(self.tags, "album")

    @property
    def genre(self) -> str | None:
        return _tag(self.tags, "genre")


def _tag(tags: dict[str, Any], key: str) -> str | None:
    for k, v in tags.items():
        if k.lower() == key and isinstance(v, str) and v.strip():
            return v.strip()[:300]
    return None


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def probe(path: Path) -> ProbeResult:
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", "-select_streams", "a:0", str(path),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True, timeout=60)
    except subprocess.CalledProcessError as exc:  # corrupted / unsupported
        msg = exc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise AudioDecodeError(msg[-1] if msg else "ffprobe failed") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioDecodeError("ffprobe timed out") from exc
    data = json.loads(out.stdout or b"{}")
    streams = data.get("streams") or []
    if not streams:
        raise AudioDecodeError("No audio stream found")
    st = streams[0]
    fmt = data.get("format") or {}
    duration = st.get("duration") or fmt.get("duration")
    if duration is None:
        raise AudioDecodeError("Could not determine duration")
    tags: dict[str, Any] = {}
    tags.update(fmt.get("tags") or {})
    tags.update(st.get("tags") or {})

    def _int(v: Any) -> int | None:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return ProbeResult(
        duration_seconds=float(duration),
        sample_rate=_int(st.get("sample_rate")),
        channels=_int(st.get("channels")),
        codec=st.get("codec_name"),
        container_format=fmt.get("format_name"),
        bit_rate=_int(st.get("bit_rate") or fmt.get("bit_rate")),
        tags={str(k): str(v)[:500] for k, v in tags.items()},
    )


def decode(path: Path, sr: int, max_seconds: float | None = None) -> np.ndarray:
    """Decode to float32 stereo array with shape (2, n) at sample rate ``sr``.

    Mono sources are duplicated to two identical channels.
    """
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path)]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
    cmd += ["-vn", "-ac", "2", "-ar", str(sr), "-f", "f32le", "-acodec", "pcm_f32le", "-"]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True, timeout=600)
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise AudioDecodeError(msg[-1] if msg else "ffmpeg decode failed") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioDecodeError("ffmpeg decode timed out") from exc
    raw = np.frombuffer(out.stdout, dtype="<f4")
    if raw.size < 2 * sr // 2:
        raise AudioDecodeError("Decoded audio is too short (under 0.5 s)")
    raw = raw[: raw.size - raw.size % 2]
    y = raw.reshape(-1, 2).T.copy()
    if not np.all(np.isfinite(y)):
        y = np.nan_to_num(y)
    return y
