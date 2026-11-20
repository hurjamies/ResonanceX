from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.database.session import get_session
from app.models import CreativeExperiment, GeneratedPrompt, GenerationJob, MediaAsset, utcnow
from app.services.prompt_engine.builder import OBJECTIVES, PromptBuildError, build_variants
from app.services.prompt_engine.compilers import compile_elevenlabs_plan, compile_suno
from app.services.integrations.registry import provider_infos
from app.services.prompt_engine.experiments import experiment_outcome
from app.services.prompt_engine.specification import PromptControls, PromptSpecification
from app.services.resonance_core.core import compute_profile
from app.services.resonance_core.dataset import load_dataset

router = APIRouter(prefix="/api", tags=["prompts"])

EDITABLE_FIELDS = {"title", "primary_genre", "hybrid_genre", "style", "lyrics", "exclude", "creative_direction", "instrumental"}


class GenerateIn(BaseModel):
    source_asset_ids: list[int] = Field(default_factory=list, max_length=12)
    objective: Optional[str] = None
    controls: PromptControls = Field(default_factory=PromptControls)
    provider: str = "suno"


def prompt_dict(p: GeneratedPrompt, session: Session | None = None) -> dict[str, Any]:
    effective = dict(p.compiled)
    effective.update(p.edited or {})
    d = {
        "id": p.id,
        "batch_id": p.batch_id,
        "parent_id": p.parent_id,
        "mode": p.mode,
        "objective": p.objective,
        "profile_version": p.profile_version,
        "provider": p.provider,
        "provider_model": p.provider_model,
        "source_asset_ids": p.source_asset_ids,
        "controls": p.controls,
        "specification": p.specification,
        "compiled": p.compiled,
        "edited": p.edited,
        "effective": effective,
        "saved": p.saved,
        "notes": p.notes,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }
    if session is not None:
        gens = session.exec(select(MediaAsset).where(MediaAsset.prompt_id == p.id)).all()
        d["generated_assets"] = [{"id": a.id, "title": a.title, "status": a.status} for a in gens]
    return d


@router.get("/prompt-options")
def prompt_options() -> dict[str, Any]:
    return {
        "objectives": [{"key": k, "label": v["label"], "dimension": v["dimension"]} for k, v in OBJECTIVES.items()],
        "providers": provider_infos(),
        "vocal_options": [
            {"key": "instrumental", "label": "Instrumentaali"},
            {"key": "female", "label": "Naisvokaali"},
            {"key": "male", "label": "Miesvokaali"},
            {"key": "duet", "label": "Duetto"},
            {"key": "choir", "label": "Sanaton kuoro"},
            {"key": "any", "label": "Vokaali (vapaa)"},
        ],
    }


@router.post("/prompts/generate")
def generate(body: GenerateIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    if body.provider != "suno":
        raise HTTPException(422, "Vain Suno-kehotteet ovat toteutettu tässä versiossa")
    if body.objective is not None and body.objective not in OBJECTIVES:
        raise HTTPException(422, "Tuntematon tavoite")
    profile = compute_profile(session)
    ds = load_dataset(session)
    by_id = ds.by_id()
    missing = [i for i in body.source_asset_ids if i not in by_id]
    if missing:
        raise HTTPException(422, f"Lähdekappaleita ei ole analysoitu: {missing}")
    sources = [by_id[i] for i in body.source_asset_ids]
    batch = uuid.uuid4().hex[:12]
    try:
        specs = build_variants(profile, sources, body.controls, body.objective, seed=batch)
    except PromptBuildError as exc:
        raise HTTPException(422, str(exc)) from exc
    out = []
    for spec in specs:
        compiled = compile_suno(spec, seed=f"{batch}:{spec.mode}")
        spec.provider_model = compiled["settings"]["model"]
        p = GeneratedPrompt(
            batch_id=batch,
            mode=spec.mode,
            objective=spec.objective,
            profile_version=profile.get("version"),
            provider="suno",
            provider_model=spec.provider_model,
            source_asset_ids=body.source_asset_ids,
            controls=body.controls.model_dump(),
            specification=spec.model_dump(),
            compiled=compiled,
        )
        session.add(p)
        session.commit()
        session.refresh(p)
        out.append(prompt_dict(p, session))
    return {"batch_id": batch, "profile_version": profile.get("version"), "prompts": out}


@router.get("/prompts")
def list_prompts(
    saved: Optional[bool] = Query(default=None),
    batch_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(GeneratedPrompt).order_by(GeneratedPrompt.id.desc()).limit(limit)
    if saved is not None:
        stmt = stmt.where(GeneratedPrompt.saved == saved)
    if batch_id:
        stmt = stmt.where(GeneratedPrompt.batch_id == batch_id)
    return [prompt_dict(p, session) for p in session.exec(stmt).all()]


def _prompt(session: Session, prompt_id: int) -> GeneratedPrompt:
    p = session.get(GeneratedPrompt, prompt_id)
    if p is None:
        raise HTTPException(404, "Kehotetta ei löytynyt")
    return p


@router.get("/prompts/{prompt_id}")
def get_prompt(prompt_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    return prompt_dict(_prompt(session, prompt_id), session)


class PromptPatch(BaseModel):
    edited: Optional[dict[str, Any]] = None
    saved: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=10000)


@router.patch("/prompts/{prompt_id}")
def patch_prompt(prompt_id: int, body: PromptPatch, session: Session = Depends(get_session)) -> dict[str, Any]:
    p = _prompt(session, prompt_id)
    if body.edited is not None:
        bad = set(body.edited) - EDITABLE_FIELDS
        if bad:
            raise HTTPException(422, f"Ei muokattavia kenttiä: {sorted(bad)}")
        edited = dict(p.edited or {})
        for k, v in body.edited.items():
            if v is None or v == p.compiled.get(k):
                edited.pop(k, None)  # back to original
            else:
                if isinstance(v, str) and len(v) > 10000:
                    raise HTTPException(422, f"{k} on liian pitkä")
                edited[k] = v
        p.edited = edited
    if body.saved is not None:
        p.saved = body.saved
    if body.notes is not None:
        p.notes = body.notes
    p.updated_at = utcnow()
    session.add(p)
    session.commit()
    session.refresh(p)
    return prompt_dict(p, session)


@router.post("/prompts/{prompt_id}/duplicate")
def duplicate_prompt(prompt_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    p = _prompt(session, prompt_id)
    compiled = dict(p.compiled)
    compiled.update(p.edited or {})
    q = GeneratedPrompt(
        batch_id=p.batch_id,
        parent_id=p.id,
        mode=p.mode,
        objective=p.objective,
        profile_version=p.profile_version,
        provider=p.provider,
        provider_model=p.provider_model,
        source_asset_ids=list(p.source_asset_ids),
        controls=dict(p.controls),
        specification=dict(p.specification),
        compiled=compiled,
        saved=True,
        notes=f"Kopio kehotteesta #{p.id}",
    )
    session.add(q)
    session.commit()
    session.refresh(q)
    return prompt_dict(q, session)


@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    p = _prompt(session, prompt_id)
    if session.exec(select(MediaAsset).where(MediaAsset.prompt_id == prompt_id)).first():
        raise HTTPException(409, "Kehotteeseen on liitetty generoitu kappale – sitä ei voi poistaa.")
    if session.exec(select(GenerationJob).where(GenerationJob.prompt_id == prompt_id)).first():
        raise HTTPException(409, "Kehotteella on generointihistoriaa – sitä ei voi poistaa.")
    for child in session.exec(select(GeneratedPrompt).where(GeneratedPrompt.parent_id == prompt_id)).all():
        child.parent_id = None
        session.add(child)
    session.delete(p)
    session.commit()
    return {"deleted": prompt_id}


def prompt_text(p: GeneratedPrompt) -> str:
    e = dict(p.compiled)
    e.update(p.edited or {})
    lines = [
        f"RESONANCEX · Prompt Studio · #{p.id} · {e.get('mode_label')}",
        f"Created: {p.created_at.isoformat()} · SonicDNA profile v{p.profile_version}",
        "",
        f"Title: {e.get('title')}",
        f"Primary genre: {e.get('primary_genre') or '-'}",
        f"Hybrid genre: {e.get('hybrid_genre') or '-'}",
        f"Instrumental: {'yes' if e.get('instrumental') else 'no'} ({e.get('vocal')})",
        "",
        "Style of Music:",
        e.get("style") or "",
        "",
        "Lyrics / Structure:",
        e.get("lyrics") or "",
        "",
        f"Exclude: {e.get('exclude') or '-'}",
        "",
        f"Creative direction: {e.get('creative_direction')}",
        "",
        f"Suggested settings: model {e['settings']['model']}, weirdness {e['settings']['weirdness']}%, style influence {e['settings']['style_influence']}%",
        "",
        "Perustelut:",
        *[f"- {x}" for x in e.get("evidence_fi", [])],
        "",
        "Epävarmuus:",
        *[f"- {x}" for x in e.get("uncertainty_fi", [])],
    ]
    return "\n".join(lines)


@router.get("/prompts/{prompt_id}/export")
def export_prompt(prompt_id: int, format: str = Query(default="json", pattern="^(json|text)$"), session: Session = Depends(get_session)):
    p = _prompt(session, prompt_id)
    if format == "text":
        return PlainTextResponse(prompt_text(p), headers={"Content-Disposition": f'attachment; filename="resonancex-prompt-{p.id}.txt"'})
    from fastapi.responses import JSONResponse

    return JSONResponse(prompt_dict(p, session), headers={"Content-Disposition": f'attachment; filename="resonancex-prompt-{p.id}.json"'})


@router.get("/prompts/{prompt_id}/elevenlabs-plan")
def elevenlabs_plan(prompt_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    p = _prompt(session, prompt_id)
    return compile_elevenlabs_plan(PromptSpecification.model_validate(p.specification))


# ---------------------------------------------------------------- experiments
def experiment_dict(session: Session, e: CreativeExperiment, profile: dict[str, Any] | None) -> dict[str, Any]:
    p = session.get(GeneratedPrompt, e.prompt_id)
    a = session.get(MediaAsset, e.generated_asset_id)
    return {
        "id": e.id,
        "prompt": None if p is None else {
            "id": p.id,
            "title": (p.edited or {}).get("title") or p.compiled.get("title"),
            "mode": p.mode,
            "mode_label": p.compiled.get("mode_label"),
            "objective": p.objective,
            "profile_version": p.profile_version,
            "created_at": p.created_at.isoformat(),
            "hypotheses": p.compiled.get("experimental_hypotheses", []),
        },
        "asset": None if a is None else {"id": a.id, "title": a.title, "status": a.status, "duration_seconds": a.duration_seconds},
        "alignment": e.alignment,
        "outcome": experiment_outcome(session, e, profile),
        "outcome_note": e.outcome_note,
        "created_at": e.created_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
    }


@router.get("/experiments")
def list_experiments(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    profile = compute_profile(session)
    rows = session.exec(select(CreativeExperiment).order_by(CreativeExperiment.id.desc())).all()
    return [experiment_dict(session, e, profile) for e in rows]


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    e = session.get(CreativeExperiment, experiment_id)
    if e is None:
        raise HTTPException(404, "Koetta ei löytynyt")
    return experiment_dict(session, e, compute_profile(session))


class ExperimentPatch(BaseModel):
    outcome_note: Optional[str] = Field(default=None, max_length=10000)


@router.patch("/experiments/{experiment_id}")
def patch_experiment(experiment_id: int, body: ExperimentPatch, session: Session = Depends(get_session)) -> dict[str, Any]:
    e = session.get(CreativeExperiment, experiment_id)
    if e is None:
        raise HTTPException(404, "Koetta ei löytynyt")
    e.outcome_note = body.outcome_note
    e.updated_at = utcnow()
    session.add(e)
    session.commit()
    session.refresh(e)
    return experiment_dict(session, e, compute_profile(session))
