"""Simple genre folders and one-click, local Suno prompt creation."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.prompts import prompt_dict
from app.database.session import get_session
from app.models import AudioAnalysis, GeneratedPrompt, MediaAsset, MusicFolder, MusicFolderEntry
from app.services.audio_analysis.engine import ALGORITHM_VERSION
from app.services.music_library import folder_or_404, folder_sources, personal_suggestion
from app.services.prompt_engine.builder import SpecBuilder
from app.services.prompt_engine.compilers import compile_suno
from app.services.prompt_engine.specification import GenreHypothesis, PromptControls
from app.services.resonance_core.core import compute_profile
from app.services.resonance_core.dataset import TrackRecord, load_dataset

router = APIRouter(prefix="/api/music", tags=["music"])


class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Anna lokerolle nimi")
        return value


@router.get("/folders")
def list_folders(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    entries = session.exec(select(MusicFolderEntry, MediaAsset).join(MediaAsset, MediaAsset.id == MusicFolderEntry.asset_id)).all()
    current_ids = set(session.exec(select(AudioAnalysis.asset_id).where(AudioAnalysis.algorithm_version == ALGORITHM_VERSION)).all())
    return [
        {"id": f.id, "name": f.name, "genre": f.genre,
         "track_count": sum(1 for e, _ in entries if e.folder_id == f.id),
         "pending_count": sum(1 for e, a in entries if e.folder_id == f.id and a.status in ("pending", "processing")),
         "ready_count": sum(1 for e, a in entries if e.folder_id == f.id and a.status == "completed" and a.id in current_ids)}
        for f in session.exec(select(MusicFolder).order_by(MusicFolder.id)).all()
    ]


@router.post("/folders", status_code=201)
def create_folder(body: FolderIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    key = body.name.casefold()
    translations = {"metalli": "metal", "metallimusiikki": "metal", "elektroninen": "electronic", "elektroninen musiikki": "electronic"}
    folder = MusicFolder(name=body.name, name_key=key, genre=translations.get(key, body.name))
    session.add(folder)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Tämän niminen lokero on jo olemassa.") from exc
    session.refresh(folder)
    return {"id": folder.id, "name": folder.name, "genre": folder.genre, "track_count": 0, "ready_count": 0, "pending_count": 0}


def _create_prompt(session: Session, sources: list[TrackRecord], genres: list[str], evidence: list[str], label: str, context: dict[str, Any], genre_directions: list[dict[str, str]] | None = None) -> dict[str, Any]:
    profile = compute_profile(session)
    # A folder's sound must not be replaced by a stronger profile from a different
    # genre. Personal recommendations likewise use enjoyed songs, not affect alone.
    scoped_profile = {**profile, "targets": {}}
    controls = PromptControls(genre=", ".join(genres)[:120] or None, vocal="any")
    batch = uuid.uuid4().hex[:12]
    spec = SpecBuilder(scoped_profile, sources, controls, None, batch).deep_resonance()
    if genres:
        directions = genre_directions or [{"name": g, "basis": "user"} for g in genres]
        spec.genre_hypotheses = [GenreHypothesis.model_validate(g) for g in directions]
        spec.hybrid_genre = " / ".join(genres) if len(genres) > 1 else None
        spec.uncertainty_fi = [s for s in spec.uncertainty_fi if not s.startswith("Genre-ehdotukset ovat sääntöpohjaisia")]
    spec.evidence_fi = evidence + spec.evidence_fi
    spec.extra["music_library"] = context
    spec.creative_direction = "An original piece inspired by the rhythm, tonal colour and energy development of the listener's chosen references, without imitating an existing song."
    spec.uncertainty_fi.append("Tämä on luova ehdotus. Henkilökohtaista sopivuutta ei voi taata etukäteen.")
    compiled = compile_suno(spec, seed=batch)
    compiled["mode_label"] = label
    spec.provider_model = compiled["settings"]["model"]
    prompt = GeneratedPrompt(
        batch_id=batch, mode=spec.mode, profile_version=profile.get("version"),
        provider="suno", provider_model=spec.provider_model,
        source_asset_ids=[t.id for t in sources], controls=controls.model_dump(),
        specification=spec.model_dump(), compiled=compiled,
    )
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    return {"batch_id": batch, "prompt": prompt_dict(prompt, session)}


@router.post("/folders/{folder_id}/prompt")
def folder_prompt(folder_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    folder = folder_or_404(session, folder_id)
    sources = folder_sources(session, folder_id)
    return _create_prompt(session, sources, [folder.genre],
                          [f"Valittu tyylilokero: {folder.name}. Lähteet ovat tästä lokerosta; myönteiset mieltymysarviot ohjaavat valintaa."],
                          f"Oma versio · {folder.name}", {"folder_id": folder.id, "folder_name": folder.name})


@router.get("/suggestion")
def suggestion(session: Session = Depends(get_session)) -> dict[str, Any]:
    return personal_suggestion(session)


@router.post("/suggestion/prompt")
def suggestion_prompt(session: Session = Depends(get_session)) -> dict[str, Any]:
    proposal = personal_suggestion(session)
    if not proposal["ready"]:
        raise HTTPException(422, "Arvioi ensin vähintään yksi analysoitu kappale mieltymyksellä 6/10 tai enemmän.")
    by_id = load_dataset(session).by_id()
    sources = [by_id[i] for i in proposal["source_asset_ids"]]
    # Keep genre strings whole, even for a custom folder name containing commas.
    genres = proposal["genre_styles"]
    return _create_prompt(session, sources, genres, proposal["reasons"], "Sinulle",
                          {"kind": "personal_suggestion", "tracks_considered": proposal["tracks_considered"], "ratings_count": proposal["ratings_count"]}, proposal["genre_directions"])
