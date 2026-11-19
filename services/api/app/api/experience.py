from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from app.database.session import get_session
from app.models import ExperienceMarker, ExperienceRating, FeedbackSession, MediaAsset, PairwiseComparison, utcnow
from app.schemas.vocabulary import BODY_KEYS, CONTEXT_FIELDS, DIMENSION_KEYS, MARKER_KEYS, REFLECTION_KEYS

router = APIRouter(prefix="/api", tags=["experience"])


class RatingIn(BaseModel):
    dimensions: dict[str, Optional[float]] = Field(default_factory=dict)
    body_responses: list[str] = Field(default_factory=list)
    reflections: dict[str, str] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dimensions")
    @classmethod
    def _dims(cls, v: dict[str, Optional[float]]) -> dict[str, Optional[float]]:
        out = {}
        for k, val in v.items():
            if k not in DIMENSION_KEYS:
                raise ValueError(f"unknown dimension: {k}")
            if val is not None and not (0 <= val <= 10):
                raise ValueError(f"{k} must be between 0 and 10")
            out[k] = None if val is None else round(float(val), 1)
        return out

    @field_validator("body_responses")
    @classmethod
    def _body(cls, v: list[str]) -> list[str]:
        bad = [b for b in v if b not in BODY_KEYS]
        if bad:
            raise ValueError(f"unknown body responses: {bad}")
        return sorted(set(v))

    @field_validator("reflections")
    @classmethod
    def _refl(cls, v: dict[str, str]) -> dict[str, str]:
        out = {}
        for k, val in v.items():
            if k not in REFLECTION_KEYS:
                raise ValueError(f"unknown reflection: {k}")
            if len(val) > 5000:
                raise ValueError("reflection too long (max 5000 chars)")
            out[k] = val
        return out

    @field_validator("context")
    @classmethod
    def _ctx(cls, v: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, val in v.items():
            if k in CONTEXT_FIELDS:
                allowed = {o["key"] for o in CONTEXT_FIELDS[k]}
                if val is not None and val not in allowed:
                    raise ValueError(f"invalid value for {k}")
                out[k] = val
            elif k == "mood":
                out[k] = None if val is None else str(val)[:200]
            elif k == "assessed_on":
                out[k] = None if val is None else str(val)[:10]
            else:
                raise ValueError(f"unknown context field: {k}")
        return out


def rating_dict(r: ExperienceRating | None, asset_id: int) -> dict[str, Any]:
    if r is None:
        return {"asset_id": asset_id, "dimensions": {}, "body_responses": [], "reflections": {}, "context": {}, "updated_at": None, "exists": False}
    return {
        "asset_id": asset_id,
        "dimensions": r.dimensions,
        "body_responses": r.body_responses,
        "reflections": r.reflections,
        "context": r.context,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
        "exists": True,
    }


def _asset(session: Session, asset_id: int) -> MediaAsset:
    a = session.get(MediaAsset, asset_id)
    if a is None:
        raise HTTPException(404, "Kappaletta ei löytynyt")
    return a


@router.get("/assets/{asset_id}/rating")
def get_rating(asset_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    _asset(session, asset_id)
    r = session.exec(select(ExperienceRating).where(ExperienceRating.asset_id == asset_id)).first()
    return rating_dict(r, asset_id)


@router.put("/assets/{asset_id}/rating")
def put_rating(asset_id: int, body: RatingIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    _asset(session, asset_id)
    r = session.exec(select(ExperienceRating).where(ExperienceRating.asset_id == asset_id)).first()
    if r is None:
        r = ExperienceRating(asset_id=asset_id)
    r.dimensions = {k: v for k, v in body.dimensions.items()}
    r.body_responses = body.body_responses
    r.reflections = {k: v for k, v in body.reflections.items() if v.strip()}
    r.context = body.context
    r.updated_at = utcnow()
    session.add(r)
    # immutable history entry (no silent overwrites)
    session.add(FeedbackSession(asset_id=asset_id, snapshot=body.model_dump()))
    session.commit()
    session.refresh(r)
    return rating_dict(r, asset_id)


@router.get("/assets/{asset_id}/rating/history")
def rating_history(asset_id: int, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    _asset(session, asset_id)
    rows = session.exec(select(FeedbackSession).where(FeedbackSession.asset_id == asset_id).order_by(FeedbackSession.id.desc())).all()
    return [{"id": f.id, "created_at": f.created_at.isoformat(), "snapshot": f.snapshot} for f in rows]


class MarkerIn(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: Optional[float] = Field(default=None, ge=0)
    label: str
    intensity: Optional[float] = Field(default=None, ge=0, le=10)
    note: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("label")
    @classmethod
    def _label(cls, v: str) -> str:
        if v not in MARKER_KEYS:
            raise ValueError("unknown marker label")
        return v


def marker_dict(m: ExperienceMarker) -> dict[str, Any]:
    return {
        "id": m.id,
        "asset_id": m.asset_id,
        "start_seconds": m.start_seconds,
        "end_seconds": m.end_seconds,
        "label": m.label,
        "intensity": m.intensity,
        "note": m.note,
        "created_at": m.created_at.isoformat(),
    }


def _validate_marker(body: MarkerIn, a: MediaAsset) -> None:
    dur = a.duration_seconds or 1e9
    if body.start_seconds > dur + 0.5:
        raise HTTPException(422, "Merkintä on kappaleen keston ulkopuolella")
    if body.end_seconds is not None and body.end_seconds <= body.start_seconds:
        raise HTTPException(422, "Välin lopun on oltava alun jälkeen")


@router.get("/assets/{asset_id}/markers")
def list_markers(asset_id: int, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    _asset(session, asset_id)
    rows = session.exec(select(ExperienceMarker).where(ExperienceMarker.asset_id == asset_id).order_by(ExperienceMarker.start_seconds)).all()
    return [marker_dict(m) for m in rows]


@router.post("/assets/{asset_id}/markers")
def create_marker(asset_id: int, body: MarkerIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    a = _asset(session, asset_id)
    _validate_marker(body, a)
    m = ExperienceMarker(asset_id=asset_id, **body.model_dump())
    session.add(m)
    session.commit()
    session.refresh(m)
    return marker_dict(m)


@router.put("/markers/{marker_id}")
def update_marker(marker_id: int, body: MarkerIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    m = session.get(ExperienceMarker, marker_id)
    if m is None:
        raise HTTPException(404, "Merkintää ei löytynyt")
    _validate_marker(body, _asset(session, m.asset_id))
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    session.add(m)
    session.commit()
    session.refresh(m)
    return marker_dict(m)


@router.delete("/markers/{marker_id}")
def delete_marker(marker_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    m = session.get(ExperienceMarker, marker_id)
    if m is None:
        raise HTTPException(404, "Merkintää ei löytynyt")
    session.delete(m)
    session.commit()
    return {"deleted": marker_id}


class ComparisonIn(BaseModel):
    asset_a_id: int
    asset_b_id: int
    stronger: Optional[Literal["a", "b", "equal"]] = None
    enjoyed: Optional[Literal["a", "b", "equal"]] = None
    note: Optional[str] = Field(default=None, max_length=2000)
    suggested_by_core: bool = False


def comparison_dict(c: PairwiseComparison) -> dict[str, Any]:
    return c.model_dump() | {"created_at": c.created_at.isoformat()}


@router.get("/comparisons")
def list_comparisons(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [comparison_dict(c) for c in session.exec(select(PairwiseComparison).order_by(PairwiseComparison.id.desc())).all()]


@router.post("/comparisons")
def create_comparison(body: ComparisonIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    if body.asset_a_id == body.asset_b_id:
        raise HTTPException(422, "Valitse kaksi eri kappaletta")
    _asset(session, body.asset_a_id)
    _asset(session, body.asset_b_id)
    if body.stronger is None and body.enjoyed is None:
        raise HTTPException(422, "Vastaa vähintään yhteen kysymykseen")
    c = PairwiseComparison(**body.model_dump())
    session.add(c)
    session.commit()
    session.refresh(c)
    return comparison_dict(c)


@router.delete("/comparisons/{comparison_id}")
def delete_comparison(comparison_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    c = session.get(PairwiseComparison, comparison_id)
    if c is None:
        raise HTTPException(404, "Vertailua ei löytynyt")
    session.delete(c)
    session.commit()
    return {"deleted": comparison_id}
