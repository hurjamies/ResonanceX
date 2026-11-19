"""Provider-independent creative specification.

The specification is the single source of truth for a prompt variant. Provider
compilers (Suno, ElevenLabs, …) only translate it into their own format.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Mode = Literal["deep_resonance", "intensification", "unknown_territory"]
Source = Literal["profile", "sources", "user", "objective_convention", "personal_association", "exploration"]


class TargetFeature(BaseModel):
    feature: str
    label: str
    target: float
    tolerance: float
    unit: str = ""
    priority: int = 1  # 1 = highest
    evidence_level: str = "observation"
    source: Source = "sources"
    descriptor: Optional[str] = None  # English phrase used in the prompt


class GenreHypothesis(BaseModel):
    name: str
    basis: Literal["user", "file_metadata", "heuristic", "exploration"]
    note: str = ""


class StructureSection(BaseModel):
    tag: str  # Suno metatag, e.g. "Intro"
    description: str
    approx_seconds: Optional[float] = None


class EvidenceReference(BaseModel):
    kind: str  # insight | association | track | profile_target | convention
    ref: str
    title: str
    evidence_level: Optional[str] = None


class PromptControls(BaseModel):
    """User controls. ``None`` means "derive from evidence" – never invented."""

    genre: Optional[str] = Field(default=None, max_length=120)
    target_bpm: Optional[float] = Field(default=None, ge=40, le=220)
    rhythmic_intensity: Optional[float] = Field(default=None, ge=0, le=10)
    bass_emphasis: Optional[float] = Field(default=None, ge=0, le=10)
    harmonic_darkness: Optional[float] = Field(default=None, ge=0, le=10)
    melancholy: Optional[float] = Field(default=None, ge=0, le=10)
    euphoria: Optional[float] = Field(default=None, ge=0, le=10)
    hypnotic_repetition: Optional[float] = Field(default=None, ge=0, le=10)
    tension: Optional[float] = Field(default=None, ge=0, le=10)
    texture_density: Optional[float] = Field(default=None, ge=0, le=10)
    vocal: Optional[Literal["instrumental", "female", "male", "duet", "choir", "any"]] = None
    experimentation: Optional[float] = Field(default=None, ge=0, le=10)
    duration_seconds: Optional[float] = Field(default=None, ge=30, le=480)
    extra_exclude: list[str] = Field(default_factory=list)
    provider_model: Optional[str] = None


class PromptSpecification(BaseModel):
    profile_version: Optional[int] = None
    mode: Mode
    objective: Optional[str] = None
    source_analysis_ids: list[int] = Field(default_factory=list)
    source_asset_ids: list[int] = Field(default_factory=list)
    target_features: list[TargetFeature] = Field(default_factory=list)
    genre_hypotheses: list[GenreHypothesis] = Field(default_factory=list)
    hybrid_genre: Optional[str] = None
    instrumentation: list[str] = Field(default_factory=list)
    rhythm_direction: list[str] = Field(default_factory=list)
    bass_direction: list[str] = Field(default_factory=list)
    harmonic_direction: list[str] = Field(default_factory=list)
    texture_direction: list[str] = Field(default_factory=list)
    energy_arc: list[str] = Field(default_factory=list)
    vocal_direction: str = "instrumental"
    structure: list[StructureSection] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)
    experimental_hypotheses: list[str] = Field(default_factory=list)
    evidence_references: list[EvidenceReference] = Field(default_factory=list)
    evidence_fi: list[str] = Field(default_factory=list)
    uncertainty_fi: list[str] = Field(default_factory=list)
    creative_direction: str = ""
    target_duration_seconds: Optional[float] = None
    provider: str = "suno"
    provider_model: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)
