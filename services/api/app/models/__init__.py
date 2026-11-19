"""Persistent data model.

Design rules:
* Measured analysis results (``AudioAnalysis``) are stored separately from user
  experiences (``ExperienceRating``, ``ExperienceMarker``) and from derived
  interpretations (``SonicProfileSnapshot``, ``GeneratedPrompt``).
* Every analysis records the algorithm version that produced it.
* Large time-series data lives in JSON files under ``data/analysis/`` and is
  referenced from the database row.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MediaAsset(SQLModel, table=True):
    __tablename__ = "media_asset"

    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = Field(default="audio", index=True)  # audio | image | video (future)
    origin: str = Field(default="library", index=True)  # library | generated
    original_filename: str
    stored_filename: str
    sha256: str = Field(index=True, unique=True)
    size_bytes: int
    mime_type: Optional[str] = None
    container_format: Optional[str] = None
    codec: Optional[str] = None
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_rate: Optional[int] = None
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    genre_tag: Optional[str] = None  # genre from file metadata (user/publisher supplied)
    tags: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    rights_confirmed: bool = False
    # For generated media: the prompt that produced it.
    prompt_id: Optional[int] = Field(default=None, foreign_key="generated_prompt.id", index=True)
    status: str = Field(default="pending", index=True)  # pending | processing | completed | failed
    status_stage: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AudioAnalysis(SQLModel, table=True):
    __tablename__ = "audio_analysis"
    __table_args__ = (UniqueConstraint("asset_id", "algorithm_version"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="media_asset.id", index=True)
    algorithm_version: str
    created_at: datetime = Field(default_factory=utcnow)
    analysis_seconds: float = 0.0
    # Global scalar features + structured summaries (rhythm, tonality, ...)
    summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # Candidate structural segments
    segments: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    # Relative path (under data/analysis) of the time-series JSON file
    timeseries_file: str
    spectrogram_file: Optional[str] = None


class AnalysisJob(SQLModel, table=True):
    __tablename__ = "analysis_job"

    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="media_asset.id", index=True)
    status: str = Field(default="queued", index=True)  # queued | processing | completed | failed
    stage: Optional[str] = None
    stages_done: int = 0
    stages_total: int = 0
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class ExperienceRating(SQLModel, table=True):
    """Song-level self-reported experience. One current rating per asset;
    history is preserved in ``FeedbackSession`` rows."""

    __tablename__ = "experience_rating"

    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="media_asset.id", index=True, unique=True)
    dimensions: dict[str, Optional[float]] = Field(default_factory=dict, sa_column=Column(JSON))
    body_responses: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    reflections: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    context: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class FeedbackSession(SQLModel, table=True):
    """Immutable history of every rating save (avoids silent overwrites)."""

    __tablename__ = "feedback_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="media_asset.id", index=True)
    snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class ExperienceMarker(SQLModel, table=True):
    __tablename__ = "experience_marker"

    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="media_asset.id", index=True)
    start_seconds: float
    end_seconds: Optional[float] = None
    label: str  # see MARKER_LABELS in schemas
    intensity: Optional[float] = None  # 0-10, optional
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class PairwiseComparison(SQLModel, table=True):
    __tablename__ = "pairwise_comparison"

    id: Optional[int] = Field(default=None, primary_key=True)
    asset_a_id: int = Field(foreign_key="media_asset.id", index=True)
    asset_b_id: int = Field(foreign_key="media_asset.id", index=True)
    # Which affected the user more strongly: "a" | "b" | "equal"
    stronger: Optional[str] = None
    # Which the user enjoyed more: "a" | "b" | "equal"
    enjoyed: Optional[str] = None
    note: Optional[str] = None
    suggested_by_core: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class SonicProfileSnapshot(SQLModel, table=True):
    __tablename__ = "sonic_profile_snapshot"

    id: Optional[int] = Field(default=None, primary_key=True)
    version: int = Field(index=True, unique=True)
    input_hash: str = Field(index=True)
    core_version: str
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class GeneratedPrompt(SQLModel, table=True):
    """A provider-specific prompt package compiled from a PromptSpecification."""

    __tablename__ = "generated_prompt"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True)  # the three variants of one generation share a batch
    parent_id: Optional[int] = Field(default=None, foreign_key="generated_prompt.id")
    mode: str  # deep_resonance | intensification | unknown_territory
    objective: Optional[str] = None
    profile_version: Optional[int] = None
    provider: str = "suno"
    provider_model: Optional[str] = None
    source_asset_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    controls: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    specification: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    compiled: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # User edits of compiled fields (original stays in ``compiled``)
    edited: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    saved: bool = False
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CreativeExperiment(SQLModel, table=True):
    """Links a prompt to a generated result and stores the objective alignment."""

    __tablename__ = "creative_experiment"

    id: Optional[int] = Field(default=None, primary_key=True)
    prompt_id: int = Field(foreign_key="generated_prompt.id", index=True)
    generated_asset_id: int = Field(foreign_key="media_asset.id", index=True, unique=True)
    alignment: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    outcome_note: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


__all__ = [
    "MediaAsset",
    "AudioAnalysis",
    "AnalysisJob",
    "ExperienceRating",
    "FeedbackSession",
    "ExperienceMarker",
    "PairwiseComparison",
    "SonicProfileSnapshot",
    "GeneratedPrompt",
    "CreativeExperiment",
    "utcnow",
]
