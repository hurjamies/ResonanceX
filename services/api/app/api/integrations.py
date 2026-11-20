from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.database.session import get_session
from app.models import GeneratedPrompt, GenerationJob
from app.services.integrations import generation as gen
from app.services.integrations.registry import provider_infos, suno_mcp

router = APIRouter(prefix="/api", tags=["integrations"])


@router.get("/providers")
def providers(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return provider_infos(session)


@router.get("/prompts/{prompt_id}/handoff")
def handoff(prompt_id: int, request: Request, session: Session = Depends(get_session)) -> dict[str, Any]:
    p = session.get(GeneratedPrompt, prompt_id)
    if p is None:
        raise HTTPException(404, "Kehotetta ei löytynyt")
    base = str(request.base_url).rstrip("/")
    return suno_mcp.handoff(p, base)


class GenerationIn(BaseModel):
    prompt_id: int
    provider: Literal["elevenlabs"] = "elevenlabs"
    model_id: Optional[str] = None
    duration_seconds: Optional[float] = Field(default=None, ge=3, le=600)


class ConfirmIn(BaseModel):
    accepted_cost: float = Field(ge=0)
    accept_disclosure: bool = False


class PlanIn(BaseModel):
    accept_disclosure: bool = False


def _job(session: Session, job_id: int) -> GenerationJob:
    j = session.get(GenerationJob, job_id)
    if j is None:
        raise HTTPException(404, "Generointipyyntöä ei löytynyt")
    return j


def _run(fn, *args):
    try:
        return fn(*args)
    except gen.GenerationError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


@router.post("/generations")
def create_generation(body: GenerationIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Prepare a request for review. Nothing is sent to the provider."""
    job = _run(gen.create_job, session, body.prompt_id, body.provider, body.model_dump(exclude={"prompt_id", "provider"}))
    return gen.job_dict(job, session)


@router.get("/generations")
def list_generations(prompt_id: Optional[int] = Query(default=None), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    stmt = select(GenerationJob).order_by(GenerationJob.id.desc()).limit(200)
    if prompt_id is not None:
        stmt = stmt.where(GenerationJob.prompt_id == prompt_id)
    return [gen.job_dict(j, session) for j in session.exec(stmt).all()]


@router.get("/generations/{job_id}")
def get_generation(job_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    return gen.job_dict(_job(session, job_id), session)


@router.post("/generations/{job_id}/plan")
def plan_generation(job_id: int, body: PlanIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Explicit, free plan creation (sends the prompt text to the provider)."""
    job = _run(gen.create_plan, session, _job(session, job_id), body.accept_disclosure)
    return gen.job_dict(job, session)


@router.post("/generations/{job_id}/confirm")
def confirm_generation(job_id: int, body: ConfirmIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    """The only call that can spend money. Requires restating the estimated cost."""
    job = _run(gen.confirm, session, _job(session, job_id), body.accepted_cost, body.accept_disclosure)
    session.refresh(job)
    return gen.job_dict(job, session)


@router.post("/generations/{job_id}/cancel")
def cancel_generation(job_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    job = _run(gen.cancel, session, _job(session, job_id))
    return gen.job_dict(job, session)
