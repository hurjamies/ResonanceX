"""Provider registry with truthful, data-backed status."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models import GenerationJob
from app.services.integrations.elevenlabs import ElevenLabsAdapter
from app.services.integrations.suno import SunoManualProvider, SunoMcpProvider

elevenlabs = ElevenLabsAdapter()
suno_manual = SunoManualProvider()
suno_mcp = SunoMcpProvider()

PROVIDERS = {p.id: p for p in (suno_manual, suno_mcp, elevenlabs)}
GENERATION_PROVIDERS = {"elevenlabs": elevenlabs}


def provider_infos(session: Session | None = None) -> list[dict[str, Any]]:
    out = []
    for p in PROVIDERS.values():
        info = p.info()
        if session is not None and p.id in GENERATION_PROVIDERS:
            last = session.exec(
                select(GenerationJob)
                .where(GenerationJob.provider == p.id, GenerationJob.status == "completed")
                .order_by(GenerationJob.finished_at.desc())
            ).first()
            info["last_success_at"] = last.finished_at.isoformat() if last and last.finished_at else None
            if info.get("configured") and last:
                info["status"] = "verified"
                info["status_fi"] = "Yhteys toiminut – viimeisin onnistunut generointi tallessa"
            elif info.get("configured"):
                info["status_fi"] += " · yhteyttä ei ole vielä varmennettu onnistuneella pyynnöllä"
        out.append(info)
    return out
