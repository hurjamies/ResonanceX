"""Loading the user's analysed tracks, experiences and comparisons."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.config import get_settings
from app.models import AudioAnalysis, ExperienceMarker, ExperienceRating, MediaAsset, PairwiseComparison
from app.schemas.vocabulary import DIMENSION_KEYS
from app.services.audio_analysis.engine import ALGORITHM_VERSION

# Dimensions that describe *how strongly* music affects the user (as opposed to
# simple enjoyment). Their mean defines the "resonance score".
AFFECT_DIMENSIONS = ["bodily_resonance", "emotional_intensity", "immersion", "significance"]


@dataclass
class TrackRecord:
    asset: MediaAsset
    analysis: AudioAnalysis
    features: dict[str, float | None]
    rating: ExperienceRating | None
    markers: list[ExperienceMarker] = field(default_factory=list)

    @property
    def id(self) -> int:
        return int(self.asset.id)

    @property
    def title(self) -> str:
        a = self.asset
        return f"{a.title}" + (f" – {a.artist}" if a.artist else "")

    def dim(self, key: str) -> float | None:
        if not self.rating:
            return None
        v = self.rating.dimensions.get(key)
        return None if v is None else float(v)

    @property
    def resonance_score(self) -> float | None:
        vals = [self.dim(k) for k in AFFECT_DIMENSIONS]
        vals = [v for v in vals if v is not None]
        if vals:
            return sum(vals) / len(vals)
        return None

    @property
    def preference(self) -> float | None:
        return self.dim("preference")

    @property
    def is_rated(self) -> bool:
        return bool(self.rating and any(self.rating.dimensions.get(k) is not None for k in DIMENSION_KEYS))


@dataclass
class Dataset:
    tracks: list[TrackRecord]
    comparisons: list[PairwiseComparison]

    def by_id(self) -> dict[int, TrackRecord]:
        return {t.id: t for t in self.tracks}


def load_dataset(session: Session) -> Dataset:
    rows = session.exec(
        select(MediaAsset, AudioAnalysis)
        .join(AudioAnalysis, AudioAnalysis.asset_id == MediaAsset.id)
        .where(MediaAsset.status == "completed", AudioAnalysis.algorithm_version == ALGORITHM_VERSION)
        .order_by(MediaAsset.id)
    ).all()
    ratings = {r.asset_id: r for r in session.exec(select(ExperienceRating)).all()}
    markers: dict[int, list[ExperienceMarker]] = {}
    for m in session.exec(select(ExperienceMarker).order_by(ExperienceMarker.start_seconds)).all():
        markers.setdefault(m.asset_id, []).append(m)
    tracks = [
        TrackRecord(asset=a, analysis=an, features=dict(an.summary.get("features") or {}), rating=ratings.get(a.id), markers=markers.get(a.id, []))
        for a, an in rows
    ]
    comps = list(session.exec(select(PairwiseComparison).order_by(PairwiseComparison.id)).all())
    return Dataset(tracks=tracks, comparisons=comps)


@lru_cache(maxsize=64)
def _load_ts(path: str, mtime: float) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def load_timeseries(analysis: AudioAnalysis) -> dict[str, Any] | None:
    p = get_settings().analysis_dir / analysis.timeseries_file
    if not p.exists():
        return None
    return _load_ts(str(p), p.stat().st_mtime)
