from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from sqlmodel import Session, func, select

from app.config import get_settings
from app.database.session import get_session
from app.models import (
    AnalysisJob,
    GenerationJob,
    AudioAnalysis,
    CreativeExperiment,
    ExperienceMarker,
    ExperienceRating,
    GeneratedPrompt,
    MediaAsset,
    PairwiseComparison,
    SonicProfileSnapshot,
)
from app.schemas.vocabulary import (
    BODY_RESPONSES,
    CONTEXT_FIELDS,
    DIMENSION_KEYS,
    ENERGY_ARC_FI,
    EXPERIENCE_DIMENSIONS,
    FEATURES,
    MARKER_LABELS,
    REFLECTION_PROMPTS,
    SEGMENT_ROLES_FI,
)
from app.services.audio_analysis.engine import ALGORITHM_VERSION, STAGES
from app.services.ingestion.audio_io import ALLOWED_EXTENSIONS, ffmpeg_available
from app.services.resonance_core.core import CORE_VERSION, EVIDENCE_FI, compute_profile

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "ffmpeg": ffmpeg_available(), "analysis_version": ALGORITHM_VERSION, "core_version": CORE_VERSION}


@router.get("/vocabulary")
def vocabulary() -> dict[str, Any]:
    return {
        "dimensions": EXPERIENCE_DIMENSIONS,
        "body_responses": BODY_RESPONSES,
        "reflections": REFLECTION_PROMPTS,
        "context": CONTEXT_FIELDS,
        "markers": MARKER_LABELS,
        "features": [f.__dict__ for f in FEATURES],
        "segment_roles": SEGMENT_ROLES_FI,
        "energy_arcs": ENERGY_ARC_FI,
        "evidence_levels": EVIDENCE_FI,
        "analysis_stages": STAGES,
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
    }


@router.get("/profile")
def profile(session: Session = Depends(get_session)) -> dict[str, Any]:
    return compute_profile(session)


@router.get("/profile/history")
def profile_history(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = session.exec(select(SonicProfileSnapshot).order_by(SonicProfileSnapshot.version.desc()).limit(50)).all()
    return [
        {
            "version": s.version,
            "created_at": s.created_at.isoformat(),
            "core_version": s.core_version,
            "tracks_rated": s.data.get("counts", {}).get("tracks_rated"),
            "tracks_analyzed": s.data.get("counts", {}).get("tracks_analyzed"),
            "insights": len(s.data.get("insights", [])),
            "summary_lines": s.data.get("summary_lines", []),
        }
        for s in rows
    ]


@router.get("/overview")
def overview(session: Session = Depends(get_session)) -> dict[str, Any]:
    prof = compute_profile(session)
    counts = prof.get("counts", {})
    incomplete = session.exec(select(MediaAsset).where(MediaAsset.status.in_(["pending", "processing", "failed"])).order_by(MediaAsset.id.desc())).all()
    prompts = session.exec(select(GeneratedPrompt).order_by(GeneratedPrompt.id.desc()).limit(6)).all()
    exps = session.exec(select(CreativeExperiment).order_by(CreativeExperiment.id.desc()).limit(5)).all()
    total_assets = session.exec(select(func.count()).select_from(MediaAsset)).one()

    # recommended next action – grounded in actual state
    if total_assets == 0:
        action = {"kind": "upload", "title": "Tuo ensimmäiset kappaleesi", "description": "Lataa musiikkia, joka vaikuttaa sinuun – ja myös sellaista, joka ei vaikuta. Molemmat ovat tärkeitä vertailun kannalta.", "href": "/library"}
    elif counts.get("tracks_analyzed", 0) == 0:
        action = {"kind": "wait", "title": "Analyysi käynnissä", "description": "Kappaleita analysoidaan. Voit kuunnella niitä kirjastossa sillä välin.", "href": "/library"}
    elif counts.get("tracks_rated", 0) < 3:
        action = {"kind": "rate", "title": "Arvioi kokemuksesi", "description": f"Olet arvioinut {counts.get('tracks_rated', 0)} kappaletta. Vähintään 4 arviota tarvitaan ensimmäisiin vertailuihin.", "href": "/library"}
    elif not prompts:
        action = {"kind": "prompt", "title": "Luo ensimmäiset Suno-kehotteet", "description": "Profiilissasi on jo alustavia havaintoja. Muunna ne luoviksi ohjeiksi Prompt Studiossa.", "href": "/prompt-studio"}
    elif not exps:
        action = {"kind": "import", "title": "Tuo Sunolla luomasi kappale", "description": "Liitä generoitu kappale kehotteeseen, jotta voit verrata tavoitetta ja tulosta.", "href": "/experiments"}
    else:
        se = prof.get("suggested_experiments") or []
        action = {"kind": "experiment", "title": se[0]["title"] if se else "Jatka tutkimista", "description": se[0]["description"] if se else "Arvioi lisää kappaleita ja tee pareittaisvertailuja.", "href": "/sonic-dna"}

    return {
        "counts": counts | {"assets_total": total_assets, "prompts": session.exec(select(func.count()).select_from(GeneratedPrompt)).one(), "experiments": session.exec(select(func.count()).select_from(CreativeExperiment)).one()},
        "profile_version": prof.get("version"),
        "data_stage": prof.get("data_stage"),
        "summary_lines": prof.get("summary_lines", []),
        "insights": prof.get("insights", [])[:4],
        "recent_prompts": [
            {"id": p.id, "title": (p.edited or {}).get("title") or p.compiled.get("title"), "mode": p.mode, "mode_label": p.compiled.get("mode_label"), "created_at": p.created_at.isoformat(), "style": (p.edited or {}).get("style") or p.compiled.get("style")}
            for p in prompts
        ],
        "recent_experiments": [{"id": e.id, "prompt_id": e.prompt_id, "asset_id": e.generated_asset_id, "score": e.alignment.get("score")} for e in exps],
        "incomplete": [{"id": a.id, "title": a.title, "status": a.status, "stage": a.status_stage, "error": a.error} for a in incomplete],
        "next_action": action,
    }


@router.get("/settings")
def settings_info(session: Session = Depends(get_session)) -> dict[str, Any]:
    s = get_settings()

    def dir_size(p) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0

    return {
        "data_dir": str(s.data_dir),
        "database": s.resolved_database_url.split("///")[-1],
        "uploads_bytes": dir_size(s.uploads_dir),
        "analysis_bytes": dir_size(s.analysis_dir),
        "max_upload_mb": s.max_upload_mb,
        "max_duration_seconds": s.max_duration_seconds,
        "analysis_version": ALGORITHM_VERSION,
        "core_version": CORE_VERSION,
        "ffmpeg": ffmpeg_available(),
        "bind_host": s.host,
        "external_requests": [
            "ElevenLabs (api.elevenlabs.io) – vain kun vahvistat generoinnin tai suunnitelman luonnin",
        ] if s.elevenlabs_api_key else [],
        "max_generation_usd": s.max_generation_usd,
        "llm": {"configured": False, "status_fi": "Ei käytössä. Kaikki analyysit ja kehotteet tuotetaan paikallisesti ilman kielimallia."},
    }


def _all_data(session: Session) -> dict[str, Any]:
    def rows(model):
        out = []
        for r in session.exec(select(model)).all():
            d = r.model_dump()
            for k, v in d.items():
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            out.append(d)
        return out

    analyses = []
    for a in session.exec(select(AudioAnalysis)).all():
        analyses.append({"id": a.id, "asset_id": a.asset_id, "algorithm_version": a.algorithm_version, "created_at": a.created_at.isoformat(), "summary": a.summary, "segments": a.segments})
    return {
        "format": "resonancex-export",
        "format_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "analysis_version": ALGORITHM_VERSION,
        "core_version": CORE_VERSION,
        "media_assets": rows(MediaAsset),
        "audio_analyses": analyses,
        "experience_ratings": rows(ExperienceRating),
        "experience_markers": rows(ExperienceMarker),
        "pairwise_comparisons": rows(PairwiseComparison),
        "generated_prompts": rows(GeneratedPrompt),
        "creative_experiments": rows(CreativeExperiment),
        "generation_jobs": rows(GenerationJob),
        "analysis_jobs": rows(AnalysisJob),
        "sonic_dna_profile": compute_profile(session),
    }


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


@router.get("/export/all.json")
def export_all(session: Session = Depends(get_session)) -> JSONResponse:
    return JSONResponse(_all_data(session), headers={"Content-Disposition": f'attachment; filename="resonancex-export-{_stamp()}.json"'})


@router.get("/export/profile.json")
def export_profile(session: Session = Depends(get_session)) -> JSONResponse:
    return JSONResponse(compute_profile(session), headers={"Content-Disposition": f'attachment; filename="sonicdna-profile-{_stamp()}.json"'})


@router.get("/export/ratings.csv")
def export_ratings(session: Session = Depends(get_session)) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    from app.schemas.vocabulary import BODY_KEYS

    analyses = {a.asset_id: a for a in session.exec(select(AudioAnalysis).where(AudioAnalysis.algorithm_version == ALGORITHM_VERSION)).all()}
    feat_keys = [f.key for f in FEATURES]
    w.writerow(["asset_id", "title", "artist", "origin", *DIMENSION_KEYS, *[f"body_{b}" for b in BODY_KEYS], *feat_keys])
    for r in session.exec(select(ExperienceRating)).all():
        a = session.get(MediaAsset, r.asset_id)
        feats = (analyses.get(r.asset_id).summary.get("features") if analyses.get(r.asset_id) else {}) or {}
        w.writerow([
            r.asset_id, a.title if a else "", a.artist if a else "", a.origin if a else "",
            *[r.dimensions.get(k, "") if r.dimensions.get(k) is not None else "" for k in DIMENSION_KEYS],
            *[1 if b in r.body_responses else 0 for b in BODY_KEYS],
            *[feats.get(k, "") if feats.get(k) is not None else "" for k in feat_keys],
        ])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="resonancex-ratings-{_stamp()}.csv"'})
