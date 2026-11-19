"""Minimal dependency-free PNG encoder and colormap for spectrogram images."""

from __future__ import annotations

import struct
import zlib

import numpy as np

# Obsidian -> resonance violet -> sonic cyan -> human gold -> near white
_STOPS = np.array(
    [
        [0.00, 11, 15, 25],
        [0.25, 45, 30, 95],
        [0.50, 139, 92, 246],
        [0.72, 56, 189, 248],
        [0.90, 217, 187, 129],
        [1.00, 250, 245, 235],
    ],
    dtype=np.float64,
)


def colormap(values: np.ndarray) -> np.ndarray:
    """Map values in [0, 1] to uint8 RGB using the ResonanceX field palette."""
    v = np.clip(values, 0.0, 1.0)
    out = np.empty(v.shape + (3,), dtype=np.float64)
    for c in range(3):
        out[..., c] = np.interp(v, _STOPS[:, 0], _STOPS[:, c + 1])
    return out.astype(np.uint8)


def encode_png(rgb: np.ndarray) -> bytes:
    """Encode an (H, W, 3) uint8 array as PNG bytes."""
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("expected (H, W, 3) uint8 array")
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[row].tobytes() for row in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
