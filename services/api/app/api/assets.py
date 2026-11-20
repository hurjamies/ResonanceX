from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.config import get_settings
from app.database.session import get_session
from app.models import (
    AnalysisJob,
    AudioAnalysis,
    CreativeExperiment,
    ExperienceMarker,
    ExperienceRating,
    FeedbackSession,
    GeneratedPrompt,
    GenerationJob,
    MediaAsset,
    MusicFolderEntry,
    PairwiseComparison,
    utcnow,
)
from app.services.audio_analysis.engine import ALGORITHM_VERSION, STAGES
from app.services.ingestion.service import IngestionError, asset_path, ingest_audio
from app.services.resonance_core.core import similar_tracks
from app.services.music_library import folder_or_404, set_folder
from app.workers.jobs import remove_analysis_files, runner

router = APIRouter(prefix="/api/assets", tags=["assets"])

# Provenance values a user upload may declare (API generations set their own provider id)
UPLOAD_SOURCES = {"manual_upload", "suno_manual", "suno_mcp", "other"}


def asset_dict(a: MediaAsset, job: AnalysisJob | None = None, rating: ExperienceRating | None = None, markers: int = 0, folder_id: int | None = None) -> dict[str, Any]:
    d = a.model_dump(exclude={"stored_filename", "tags"})
    d["created_at"] = a.created_at.isoformat()
    d["updated_at"] = a.updated_at.isoformat()
    d["audio_url"] = f"/api/assets/{a.id}/audio"
    d["job"] = None
    if job is not None:
        d["job"] = {
            "id": job.id,
            "status": job.status,
            "stage": job.stage,
            "stages_done": job.stages_done,
            "stages_total": job.stages_total or len(STAGES),
            "error": job.error,
        }
    d["rated"] = bool(rating and any(v is not None for v in rating.dimensions.values()))
    d["rating_summary"] = None
    if rating:
        d["rating_summary"] = {k: v for k, v in rating.dimensions.items() if v is not None}
    d["marker_count"] = markers
    d["folder_id"] = folder_id
    return d


def _latest_jobs(session: Session, ids: list[int]) -> dict[int, AnalysisJob]:
    out: dict[int, AnalysisJob] = {}
    if not ids:
        return out
    for j in session.exec(select(AnalysisJob).where(AnalysisJob.asset_id.in_(ids)).order_by(AnalysisJob.id)).all():
        out[j.asset_id] = j
    return out


def get_asset_or_404(session: Session, asset_id: int) -> MediaAsset:
    a = session.get(MediaAsset, asset_id)
    if a is None:
        raise HTTPException(404, "Kappaletta ei löytynyt")
    return a


@router.get("")
def list_assets(
    origin: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, max_length=200),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(MediaAsset).where(MediaAsset.kind == "audio").order_by(MediaAsset.created_at.desc())
    if origin:
        stmt = stmt.where(MediaAsset.origin == origin)
    if status:
        stmt = stmt.where(MediaAsset.status == status)
    assets = session.exec(stmt).all()
    if q:
        ql = q.lower()
        assets = [a for a in assets if ql in (a.title or "").lower() or ql in (a.artist or "").lower() or ql in a.original_filename.lower()]
    ids = [a.id for a in assets]
    jobs = _latest_jobs(session, ids)
    ratings = {r.asset_id: r for r in session.exec(select(ExperienceRating).where(ExperienceRating.asset_id.in_(ids))).all()} if ids else {}
    mcount: dict[int, int] = {}
    if ids:
        for m in session.exec(select(ExperienceMarker.asset_id).where(ExperienceMarker.asset_id.in_(ids))).all():
            mcount[m] = mcount.get(m, 0) + 1
    folders = {e.asset_id: e.folder_id for e in session.exec(select(MusicFolderEntry)).all()}
    return [asset_dict(a, jobs.get(a.id), ratings.get(a.id), mcount.get(a.id, 0), folders.get(a.id)) for a in assets]


@router.post("/upload")
def upload_assets(
    files: list[UploadFile] = File(...),
    rights_confirmed: bool = Form(False),
    origin: str = Form("library"),
    prompt_id: Optional[int] = Form(None),
    source_provider: Optional[str] = Form(None),
    folder_id: Optional[int] = Form(None),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if source_provider is not None and source_provider not in UPLOAD_SOURCES:
        raise HTTPException(422, f"source_provider must be one of {sorted(UPLOAD_SOURCES)}")
    if origin not in ("library", "generated"):
        raise HTTPException(422, "origin must be 'library' or 'generated'")
    if not rights_confirmed:
        raise HTTPException(422, "Vahvista, että sinulla on oikeus käyttää tiedostoja henkilökohtaiseen analyysiin.")
    if folder_id is not None:
        folder_or_404(session, folder_id)
    if prompt_id is not None:
        if session.get(GeneratedPrompt, prompt_id) is None:
            raise HTTPException(404, "Kehotetta ei löytynyt")
        origin = "generated"
        source_provider = source_provider or "manual_upload"
    elif source_provider is not None:
        raise HTTPException(422, "source_provider requires prompt_id")
    results = []
    for f in files:
        try:
            res = ingest_audio(session, f.file, f.filename or "audio", origin=origin, prompt_id=prompt_id, rights_confirmed=rights_confirmed, source_provider=source_provider)
        except IngestionError as exc:
            results.append({"filename": f.filename, "ok": False, "error": str(exc), "code": exc.code})
            continue
        if folder_id is not None:
            set_folder(session, res.asset.id, folder_id)
            session.commit()
        if res.job is not None:
            runner.submit(res.job.id)
            session.refresh(res.asset)
        elif res.duplicate and prompt_id and res.asset.status == "completed":
            from app.services.prompt_engine.experiments import refresh_experiment

            if res.asset.prompt_id == prompt_id:
                refresh_experiment(session, res.asset)
        job = _latest_jobs(session, [res.asset.id]).get(res.asset.id)
        entry = session.get(MusicFolderEntry, res.asset.id)
        results.append({"filename": f.filename, "ok": True, "duplicate": res.duplicate, "asset": asset_dict(res.asset, job, folder_id=entry.folder_id if entry else None)})
    return {"results": results}


@router.get("/{asset_id}")
def get_asset(asset_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    a = get_asset_or_404(session, asset_id)
    job = _latest_jobs(session, [asset_id]).get(asset_id)
    rating = session.exec(select(ExperienceRating).where(ExperienceRating.asset_id == asset_id)).first()
    n_markers = len(session.exec(select(ExperienceMarker.id).where(ExperienceMarker.asset_id == asset_id)).all())
    entry = session.get(MusicFolderEntry, asset_id)
    d = asset_dict(a, job, rating, n_markers, entry.folder_id if entry else None)
    d["metadata_tags"] = a.tags
    if a.prompt_id:
        p = session.get(GeneratedPrompt, a.prompt_id)
        d["prompt"] = None if p is None else {"id": p.id, "title": (p.edited or {}).get("title") or p.compiled.get("title"), "mode": p.mode}
    return d


class AssetPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    artist: Optional[str] = Field(default=None, max_length=300)
    genre_tag: Optional[str] = Field(default=None, max_length=120)
    folder_id: Optional[int] = None


@router.patch("/{asset_id}")
def patch_asset(asset_id: int, body: AssetPatch, session: Session = Depends(get_session)) -> dict[str, Any]:
    a = get_asset_or_404(session, asset_id)
    if "folder_id" in body.model_fields_set:
        set_folder(session, asset_id, body.folder_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "folder_id":
            continue
        setattr(a, k, v.strip() if isinstance(v, str) else v)
    a.updated_at = utcnow()
    session.add(a)
    session.commit()
    session.refresh(a)
    entry = session.get(MusicFolderEntry, asset_id)
    return asset_dict(a, folder_id=entry.folder_id if entry else None)


@router.delete("/{asset_id}")
def delete_asset(asset_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    a = get_asset_or_404(session, asset_id)
    path = asset_path(a)
    entry = session.get(MusicFolderEntry, asset_id)
    if entry:
        session.delete(entry)
        session.flush()
    for model in (AudioAnalysis, AnalysisJob, ExperienceMarker, ExperienceRating, FeedbackSession):
        for row in session.exec(select(model).where(model.asset_id == asset_id)).all():
            session.delete(row)
    for row in session.exec(select(CreativeExperiment).where(CreativeExperiment.generated_asset_id == asset_id)).all():
        session.delete(row)
    for job in session.exec(select(GenerationJob).where(GenerationJob.result_asset_id == asset_id)).all():
        job.result_asset_id = None
        job.response_meta = {**(job.response_meta or {}), "result_deleted": True}
        session.add(job)
    for row in session.exec(
        select(PairwiseComparison).where((PairwiseComparison.asset_a_id == asset_id) | (PairwiseComparison.asset_b_id == asset_id))
    ).all():
        session.delete(row)
    session.delete(a)
    session.commit()
    path.unlink(missing_ok=True)
    remove_analysis_files(asset_id)
    return {"deleted": asset_id}


@router.get("/{asset_id}/audio")
def get_audio(asset_id: int, session: Session = Depends(get_session)) -> FileResponse:
    a = get_asset_or_404(session, asset_id)
    p = asset_path(a)
    if not p.exists():
        raise HTTPException(404, "Alkuperäinen tiedosto puuttuu")
    return FileResponse(p, media_type=a.mime_type or "application/octet-stream", filename=a.original_filename, content_disposition_type="inline")


@router.post("/{asset_id}/reanalyze")
def reanalyze(asset_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    a = get_asset_or_404(session, asset_id)
    active = session.exec(select(AnalysisJob).where(AnalysisJob.asset_id == asset_id, AnalysisJob.status.in_(["queued", "processing"]))).first()
    if active:
        return {"queued": False, "job_id": active.id, "reason": "already_running"}
    job = AnalysisJob(asset_id=asset_id, status="queued")
    a.status = "pending"
    session.add_all([job, a])
    session.commit()
    session.refresh(job)
    runner.submit(job.id)
    return {"queued": True, "job_id": job.id}


def _analysis_or_404(session: Session, asset_id: int) -> AudioAnalysis:
    an = session.exec(
        select(AudioAnalysis).where(AudioAnalysis.asset_id == asset_id, AudioAnalysis.algorithm_version == ALGORITHM_VERSION)
    ).first()
    if an is None:
        an = session.exec(select(AudioAnalysis).where(AudioAnalysis.asset_id == asset_id).order_by(AudioAnalysis.id.desc())).first()
    if an is None:
        raise HTTPException(404, "Analyysia ei ole vielä saatavilla")
    return an


@router.get("/{asset_id}/analysis")
def get_analysis(asset_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    get_asset_or_404(session, asset_id)
    an = _analysis_or_404(session, asset_id)
    return {
        "id": an.id,
        "asset_id": asset_id,
        "algorithm_version": an.algorithm_version,
        "current_version": ALGORITHM_VERSION,
        "outdated": an.algorithm_version != ALGORITHM_VERSION,
        "created_at": an.created_at.isoformat(),
        "analysis_seconds": an.analysis_seconds,
        "summary": an.summary,
        "segments": an.segments,
        "timeseries_url": f"/api/assets/{asset_id}/timeseries",
        "spectrogram_url": f"/api/assets/{asset_id}/spectrogram.png",
    }


@router.get("/{asset_id}/timeseries")
def get_timeseries(asset_id: int, session: Session = Depends(get_session)) -> Response:
    an = _analysis_or_404(session, asset_id)
    p = get_settings().analysis_dir / an.timeseries_file
    if not p.exists():
        raise HTTPException(404, "Aikasarjatiedosto puuttuu – analysoi kappale uudelleen")
    return Response(p.read_bytes(), media_type="application/json", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{asset_id}/spectrogram.png")
def get_spectrogram(asset_id: int, session: Session = Depends(get_session)) -> Response:
    an = _analysis_or_404(session, asset_id)
    if not an.spectrogram_file:
        raise HTTPException(404, "Spektrogrammi puuttuu")
    p = get_settings().analysis_dir / an.spectrogram_file
    if not p.exists():
        raise HTTPException(404, "Spektrogrammi puuttuu")
    return Response(p.read_bytes(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{asset_id}/similar")
def get_similar(asset_id: int, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    get_asset_or_404(session, asset_id)
    return similar_tracks(session, asset_id)
