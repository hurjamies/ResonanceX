"""Upload ingestion: validation, hashing, duplicate detection and storage."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlmodel import Session, select

from app.config import get_settings
from app.models import AnalysisJob, MediaAsset, utcnow
from app.services.ingestion.audio_io import ALLOWED_EXTENSIONS, MIME_BY_EXT, AudioDecodeError, probe


class IngestionError(Exception):
    def __init__(self, message: str, code: str = "invalid_upload"):
        super().__init__(message)
        self.code = code


@dataclass
class IngestResult:
    asset: MediaAsset
    duplicate: bool
    job: AnalysisJob | None


def _safe_display_name(name: str) -> str:
    base = os.path.basename(name or "audio")
    return "".join(ch for ch in base if ch.isprintable())[:255] or "audio"


def ingest_audio(
    session: Session,
    fileobj: BinaryIO,
    filename: str,
    *,
    origin: str = "library",
    prompt_id: int | None = None,
    rights_confirmed: bool = False,
) -> IngestResult:
    settings = get_settings()
    settings.ensure_dirs()
    display = _safe_display_name(filename)
    ext = Path(display).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestionError(
            f"Tiedostomuotoa '{ext or '?'}' ei tueta. Tuetut: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            "unsupported_format",
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    import hashlib

    h = hashlib.sha256()
    size = 0
    fd, tmp_name = tempfile.mkstemp(dir=settings.uploads_dir, suffix=ext + ".part")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := fileobj.read(1 << 20):
                size += len(chunk)
                if size > max_bytes:
                    raise IngestionError(f"Tiedosto on liian suuri (yli {settings.max_upload_mb} Mt).", "too_large")
                h.update(chunk)
                out.write(chunk)
        if size == 0:
            raise IngestionError("Tiedosto on tyhjä.", "empty")
        digest = h.hexdigest()

        existing = session.exec(select(MediaAsset).where(MediaAsset.sha256 == digest)).first()
        if existing is not None:
            tmp.unlink(missing_ok=True)
            changed = False
            # A library track re-imported as a generated result is linked, not duplicated
            if prompt_id and existing.prompt_id is None and existing.origin == "generated":
                existing.prompt_id = prompt_id
                changed = True
            if changed:
                existing.updated_at = utcnow()
                session.add(existing)
                session.commit()
                session.refresh(existing)
            return IngestResult(existing, True, None)

        try:
            info = probe(tmp)
        except AudioDecodeError as exc:
            raise IngestionError(f"Tiedostoa ei voitu lukea: {exc}", "decode_failed") from exc
        if info.duration_seconds < 1.0:
            raise IngestionError("Ääni on liian lyhyt analysoitavaksi (alle 1 s).", "too_short")
        if info.duration_seconds > settings.max_duration_seconds:
            raise IngestionError(
                f"Ääni on liian pitkä (yli {int(settings.max_duration_seconds // 60)} min).", "too_long"
            )

        rel = Path(digest[:2]) / f"{digest}{ext}"
        dest = settings.uploads_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, dest)

        asset = MediaAsset(
            kind="audio",
            origin=origin,
            original_filename=display,
            stored_filename=str(rel),
            sha256=digest,
            size_bytes=size,
            mime_type=MIME_BY_EXT.get(ext),
            container_format=info.container_format,
            codec=info.codec,
            duration_seconds=info.duration_seconds,
            sample_rate=info.sample_rate,
            channels=info.channels,
            bit_rate=info.bit_rate,
            title=info.title or Path(display).stem,
            artist=info.artist,
            album=info.album,
            genre_tag=info.genre,
            tags=info.tags,
            rights_confirmed=rights_confirmed,
            prompt_id=prompt_id,
            status="pending",
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        job = AnalysisJob(asset_id=asset.id, status="queued")
        session.add(job)
        session.commit()
        session.refresh(job)
        return IngestResult(asset, False, job)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def asset_path(asset: MediaAsset) -> Path:
    settings = get_settings()
    p = (settings.uploads_dir / asset.stored_filename).resolve()
    if settings.uploads_dir.resolve() not in p.parents:
        raise IngestionError("Invalid stored path", "invalid_path")
    return p
