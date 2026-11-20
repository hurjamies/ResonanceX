"""User-controlled generation jobs.

State machine::

    awaiting_confirmation ──confirm──▶ queued ──▶ running ──▶ completed
            │                            │            └──────▶ failed
            └──────────cancel────────────┴──▶ cancelled

* Nothing is sent to a provider before ``confirm`` – which requires the caller to
  restate the exact estimated cost and to accept the data disclosure.
* The optional plan step (ElevenLabs ``/v1/music/plan``, free) is also an explicit
  user action.
* After a restart nothing is re-sent automatically: queued jobs return to
  ``awaiting_confirmation`` and interrupted running jobs are marked failed with an
  instruction to check the provider history (the provider may have charged).
"""

from __future__ import annotations

import io
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlmodel import Session, select

from app.config import get_settings
from app.database.session import get_engine
from app.models import GeneratedPrompt, GenerationJob, MediaAsset, utcnow
from app.services.ingestion.service import IngestionError, ingest_audio
from app.services.integrations.base import ProviderError
from app.services.integrations.registry import GENERATION_PROVIDERS

log = logging.getLogger("resonancex.generation")

_executor: ThreadPoolExecutor | None = None
_lock = threading.Lock()


class GenerationError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


def _adapter(provider: str):
    a = GENERATION_PROVIDERS.get(provider)
    if a is None:
        raise GenerationError(f"Palveluntarjoaja '{provider}' ei tue generointia tästä sovelluksesta.")
    return a


def create_job(session: Session, prompt_id: int, provider: str, options: dict[str, Any]) -> GenerationJob:
    prompt = session.get(GeneratedPrompt, prompt_id)
    if prompt is None:
        raise GenerationError("Kehotetta ei löytynyt", 404)
    adapter = _adapter(provider)
    try:
        prepared = adapter.prepare(prompt, options)
    except ProviderError as exc:
        raise GenerationError(str(exc)) from exc
    job = GenerationJob(
        provider=provider,
        prompt_id=prompt_id,
        provider_model=prepared.provider_model,
        request=prepared.request,
        disclosure=prepared.disclosure,
        cost_estimate=prepared.cost_estimate,
        response_meta={"warnings": prepared.warnings},
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def create_plan(session: Session, job: GenerationJob, accept_disclosure: bool) -> GenerationJob:
    if job.status != "awaiting_confirmation":
        raise GenerationError("Suunnitelman voi luoda vain hyväksyntää odottavalle pyynnölle.", 409)
    if not accept_disclosure:
        raise GenerationError("Hyväksy ensin, mitä tietoja lähetetään palveluntarjoajalle.")
    adapter = _adapter(job.provider)
    if not hasattr(adapter, "create_plan"):
        raise GenerationError("Tämä palveluntarjoaja ei tue suunnitelmia.")
    if not adapter.configured():
        raise GenerationError("Palveluntarjoajaa ei ole määritetty (API-avain puuttuu).", 409)
    try:
        plan = adapter.create_plan(job.request)
    except ProviderError as exc:
        raise GenerationError(str(exc), 502) from exc
    request, cost = adapter.request_with_plan(job.request, plan)
    job.request = request
    job.cost_estimate = cost
    job.response_meta = {**(job.response_meta or {}), "plan_created_at": utcnow().isoformat()}
    job.updated_at = utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def confirm(session: Session, job: GenerationJob, accepted_cost: float | None, accept_disclosure: bool) -> GenerationJob:
    settings = get_settings()
    if job.status != "awaiting_confirmation":
        raise GenerationError(f"Pyyntöä ei voi vahvistaa tilassa '{job.status}'.", 409)
    adapter = _adapter(job.provider)
    if not adapter.configured():
        raise GenerationError("Palveluntarjoajaa ei ole määritetty (API-avain puuttuu palvelimelta).", 409)
    if not accept_disclosure:
        raise GenerationError("Hyväksy ensin, mitä tietoja lähetetään palveluntarjoajalle.")
    est = float(job.cost_estimate.get("amount") or 0)
    if accepted_cost is None or abs(float(accepted_cost) - est) > 0.005:
        raise GenerationError("Hyväksytty kustannus ei vastaa nykyistä arviota – tarkista arvio ja vahvista uudelleen.", 409)
    if est > settings.max_generation_usd:
        raise GenerationError(
            f"Arvio {est:.2f} $ ylittää pyyntökohtaisen rajan {settings.max_generation_usd:.2f} $ (RESONANCEX_MAX_GENERATION_USD).", 409
        )
    job.status = "queued"
    job.confirmed_at = utcnow()
    job.updated_at = utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    submit(job.id)
    session.refresh(job)
    return job


def cancel(session: Session, job: GenerationJob) -> GenerationJob:
    if job.status not in ("awaiting_confirmation", "queued"):
        raise GenerationError("Käynnissä olevaa tai valmista pyyntöä ei voi perua.", 409)
    job.status = "cancelled"
    job.updated_at = utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def submit(job_id: int) -> None:
    if get_settings().synchronous_jobs:
        run(job_id)
        return
    global _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="generation")
    _executor.submit(_safe_run, job_id)


def _safe_run(job_id: int) -> None:
    try:
        run(job_id)
    except Exception:  # pragma: no cover - logged; job marked failed in run()
        log.exception("generation job %s crashed", job_id)


def run(job_id: int) -> None:
    engine = get_engine()
    with Session(engine) as s:
        job = s.get(GenerationJob, job_id)
        if job is None or job.status != "queued":
            return  # cancelled or already handled
        job.status = "running"
        job.started_at = utcnow()
        job.updated_at = utcnow()
        s.add(job)
        s.commit()
        provider, request, prompt_id = job.provider, dict(job.request), job.prompt_id
    adapter = _adapter(provider)
    try:
        result = adapter.generate(request)
    except ProviderError as exc:
        _fail(job_id, str(exc), {"status": exc.status, "detail": exc.detail, "retryable": exc.retryable})
        return
    except Exception as exc:  # defensive
        log.exception("unexpected provider failure")
        _fail(job_id, f"Odottamaton virhe: {exc.__class__.__name__}", {})
        return

    with Session(engine) as s:
        prompt = s.get(GeneratedPrompt, prompt_id)
        title = ((prompt.edited or {}).get("title") or (prompt.compiled or {}).get("title") or "generated") if prompt else "generated"
        filename = f"{title} · {provider} #{job_id}{result.file_extension}"
        try:
            res = ingest_audio(
                s,
                io.BytesIO(result.audio),
                filename,
                origin="generated",
                prompt_id=prompt_id,
                rights_confirmed=True,  # created with the user's own provider account
                source_provider=provider,
            )
        except IngestionError as exc:
            _fail(job_id, f"Palveluntarjoajan palauttamaa ääntä ei voitu tuoda: {exc}", result.meta)
            return
        job = s.get(GenerationJob, job_id)
        job.status = "completed"
        job.finished_at = utcnow()
        job.updated_at = utcnow()
        job.result_asset_id = res.asset.id
        job.response_meta = {**(job.response_meta or {}), **result.meta, "duplicate": res.duplicate}
        s.add(job)
        s.commit()
        analysis_job_id = res.job.id if res.job else None
    if analysis_job_id:
        from app.workers.jobs import runner

        runner.submit(analysis_job_id)


def _fail(job_id: int, message: str, meta: dict[str, Any]) -> None:
    with Session(get_engine()) as s:
        job = s.get(GenerationJob, job_id)
        if job is None:
            return
        job.status = "failed"
        job.error = message[:500]
        job.finished_at = utcnow()
        job.updated_at = utcnow()
        job.response_meta = {**(job.response_meta or {}), "error": {k: v for k, v in meta.items() if v is not None}}
        s.add(job)
        s.commit()


def recover_on_startup() -> None:
    """Never re-send automatically after a restart."""
    with Session(get_engine()) as s:
        for job in s.exec(select(GenerationJob).where(GenerationJob.status.in_(["queued", "running"]))).all():
            if job.status == "queued":
                job.status = "awaiting_confirmation"
                job.confirmed_at = None
                job.response_meta = {**(job.response_meta or {}), "requeued_note": "Sovellus käynnistyi uudelleen ennen lähetystä – vahvista uudelleen."}
            else:
                job.status = "failed"
                job.error = (
                    "Sovellus pysähtyi kesken pyynnön. Pyyntö on voinut ehtiä palveluntarjoajalle – tarkista sen historia ennen uutta yritystä."
                )
                job.finished_at = utcnow()
            job.updated_at = utcnow()
            s.add(job)
        s.commit()


def shutdown() -> None:
    global _executor
    with _lock:
        if _executor is not None:
            _executor.shutdown(wait=False, cancel_futures=True)
            _executor = None


def job_dict(job: GenerationJob, session: Session | None = None) -> dict[str, Any]:
    d = job.model_dump()
    for k in ("confirmed_at", "started_at", "finished_at", "created_at", "updated_at"):
        d[k] = getattr(job, k).isoformat() if getattr(job, k) else None
    if session is not None:
        p = session.get(GeneratedPrompt, job.prompt_id)
        d["prompt_title"] = ((p.edited or {}).get("title") or (p.compiled or {}).get("title")) if p else None
        if job.result_asset_id:
            a = session.get(MediaAsset, job.result_asset_id)
            d["result_asset"] = None if a is None else {"id": a.id, "title": a.title, "status": a.status}
    return d
