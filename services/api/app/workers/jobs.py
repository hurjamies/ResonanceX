"""Background analysis job runner.

A small thread pool keeps the API responsive while audio is analysed. Jobs are
persisted in the ``analysis_job`` table, so interrupted jobs are re-queued on
startup. Progress is reported as named analysis stages (no fake percentages).
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlmodel import Session, select

from app.config import get_settings
from app.database.session import get_engine
from app.models import AnalysisJob, AudioAnalysis, MediaAsset, utcnow
from app.services.audio_analysis.engine import ALGORITHM_VERSION, STAGES, analyze_file
from app.services.ingestion.service import asset_path

log = logging.getLogger("resonancex.jobs")


class JobRunner:
    def __init__(self) -> None:
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        settings = get_settings()
        if settings.synchronous_jobs:
            return
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=max(1, settings.analysis_workers), thread_name_prefix="analysis")
        # Re-queue jobs interrupted by a previous shutdown
        with Session(get_engine()) as s:
            jobs = s.exec(select(AnalysisJob).where(AnalysisJob.status.in_(["queued", "processing"]))).all()
            for j in jobs:
                j.status = "queued"
                j.stage = None
                s.add(j)
            s.commit()
            ids = [j.id for j in jobs]
        for jid in ids:
            self.submit(jid)

    def shutdown(self) -> None:
        with self._lock:
            if self._executor is not None:
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None

    def submit(self, job_id: int) -> None:
        if get_settings().synchronous_jobs:
            run_job(job_id)
            return
        if self._executor is None:
            self.start()
        assert self._executor is not None
        self._executor.submit(_safe_run, job_id)


def _safe_run(job_id: int) -> None:
    try:
        run_job(job_id)
    except Exception:  # pragma: no cover - logged, job marked failed in run_job
        log.exception("analysis job %s crashed", job_id)


def run_job(job_id: int) -> None:
    engine = get_engine()
    settings = get_settings()
    with Session(engine) as s:
        job = s.get(AnalysisJob, job_id)
        if job is None:
            return
        asset = s.get(MediaAsset, job.asset_id)
        if asset is None:
            job.status = "failed"
            job.error = "Asset missing"
            s.add(job)
            s.commit()
            return
        job.status = "processing"
        job.started_at = utcnow()
        job.stages_total = len(STAGES)
        job.stages_done = 0
        asset.status = "processing"
        asset.error = None
        s.add_all([job, asset])
        s.commit()
        asset_id, channels = asset.id, asset.channels
        path = asset_path(asset)

    def progress(stage: str, index: int, total: int) -> None:
        with Session(engine) as ps:
            j = ps.get(AnalysisJob, job_id)
            a = ps.get(MediaAsset, asset_id)
            if j:
                j.stage, j.stages_done, j.stages_total = stage, index, total
                ps.add(j)
            if a:
                a.status_stage = stage
                ps.add(a)
            ps.commit()

    try:
        out = analyze_file(path, source_channels=channels, progress=progress)
        rel_dir = Path(str(asset_id)) / ALGORITHM_VERSION
        out_dir = settings.analysis_dir / rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        ts_rel = rel_dir / "timeseries.json"
        sp_rel = rel_dir / "spectrogram.png"
        (settings.analysis_dir / ts_rel).write_text(json.dumps(out.timeseries, separators=(",", ":")))
        (settings.analysis_dir / sp_rel).write_bytes(out.spectrogram_png)

        with Session(engine) as s:
            old = s.exec(
                select(AudioAnalysis).where(AudioAnalysis.asset_id == asset_id, AudioAnalysis.algorithm_version == ALGORITHM_VERSION)
            ).first()
            if old is not None:
                s.delete(old)
                s.commit()
            analysis = AudioAnalysis(
                asset_id=asset_id,
                algorithm_version=ALGORITHM_VERSION,
                analysis_seconds=round(out.analysis_seconds, 2),
                summary=out.summary,
                segments=out.segments,
                timeseries_file=str(ts_rel),
                spectrogram_file=str(sp_rel),
            )
            s.add(analysis)
            job = s.get(AnalysisJob, job_id)
            asset = s.get(MediaAsset, asset_id)
            job.status = "completed"
            job.stage = None
            job.stages_done = len(STAGES)
            job.finished_at = utcnow()
            asset.status = "completed"
            asset.status_stage = None
            # use the precise decoded duration
            asset.duration_seconds = out.summary.get("duration_seconds") or asset.duration_seconds
            asset.updated_at = utcnow()
            s.add_all([job, asset])
            s.commit()
            if asset.prompt_id:
                from app.services.prompt_engine.experiments import refresh_experiment

                refresh_experiment(s, asset)
    except Exception as exc:
        log.exception("analysis failed for asset %s", asset_id)
        with Session(engine) as s:
            job = s.get(AnalysisJob, job_id)
            asset = s.get(MediaAsset, asset_id)
            msg = str(exc)[:500] or exc.__class__.__name__
            if job:
                job.status = "failed"
                job.error = msg
                job.finished_at = utcnow()
                s.add(job)
            if asset:
                asset.status = "failed"
                asset.status_stage = None
                asset.error = msg
                s.add(asset)
            s.commit()


def remove_analysis_files(asset_id: int) -> None:
    d = get_settings().analysis_dir / str(asset_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


runner = JobRunner()
