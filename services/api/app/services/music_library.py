"""Genre organization and a transparent, local creative suggestion.

Every current analysis is considered; positive enjoyment ratings select the
references. Affect alone never implies that the user liked a song.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, median
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import MediaAsset, MusicFolder, MusicFolderEntry
from app.schemas.vocabulary import ENERGY_ARC_FI
from app.services.prompt_engine.builder import usable_genre_tag
from app.services.resonance_core.dataset import TrackRecord, load_dataset


def folder_or_404(session: Session, folder_id: int) -> MusicFolder:
    folder = session.get(MusicFolder, folder_id)
    if folder is None:
        raise HTTPException(404, "Lokeroa ei löytynyt")
    return folder


def set_folder(session: Session, asset_id: int, folder_id: int | None) -> None:
    if folder_id is not None:
        folder_or_404(session, folder_id)
    entry = session.get(MusicFolderEntry, asset_id)
    if folder_id is None:
        if entry:
            session.delete(entry)
    elif entry:
        entry.folder_id = folder_id
        session.add(entry)
    else:
        session.add(MusicFolderEntry(asset_id=asset_id, folder_id=folder_id))


def enjoyment_order(track: TrackRecord) -> tuple[float, float, int]:
    return (track.preference if track.preference is not None else -1,
            track.resonance_score if track.resonance_score is not None else -1, -track.id)


def folder_sources(session: Session, folder_id: int) -> list[TrackRecord]:
    folder_or_404(session, folder_id)
    ids = set(session.exec(select(MusicFolderEntry.asset_id).where(MusicFolderEntry.folder_id == folder_id)).all())
    tracks = [t for t in load_dataset(session).tracks if t.id in ids]
    if not tracks:
        raise HTTPException(422, "Lisää lokeroon musiikkia ja odota analyysin valmistumista.")
    liked = [t for t in tracks if t.preference is not None and t.preference >= 6]
    # Unrated tracks are usable references, but a disliked track is never selected
    # just because its emotional impact was strong.
    eligible = liked or [t for t in tracks if t.preference is None or t.preference >= 5]
    if not eligible:
        raise HTTPException(422, "Et ole pitänyt lokeron arvioiduista kappaleista. Lisää mieluisa kappale tai päivitä arviosi.")
    return sorted(eligible, key=enjoyment_order, reverse=True)


def personal_suggestion(session: Session) -> dict[str, Any]:
    tracks = load_dataset(session).tracks
    folders = {f.id: f for f in session.exec(select(MusicFolder)).all()}
    entries = {e.asset_id: e.folder_id for e in session.exec(select(MusicFolderEntry)).all()}
    groups: dict[str, list[TrackRecord]] = defaultdict(list)
    labels: dict[str, str] = {}
    genres: dict[str, str] = {}
    genre_bases: dict[str, str] = {}
    for track in tracks:
        folder = folders.get(entries.get(track.id))
        # Unfiled tracks fall back to the file's tag only when it names a musical style.
        genre = folder.genre if folder else (usable_genre_tag(track.asset.genre_tag) or "")
        key = genre.casefold()
        groups[key].append(track)
        if key not in labels or folder:
            labels[key] = folder.name if folder else genre or "Ilman lokeroa"
            genre_bases[key] = "user" if folder else "file_metadata"
        genres[key] = genre

    liked = [t for t in tracks if t.preference is not None and t.preference >= 6]
    rated = [t for t in tracks if t.preference is not None]
    result: dict[str, Any] = {
        "ready": bool(liked),
        "pending_count": len(session.exec(select(MediaAsset.id).where(MediaAsset.status.in_(["pending", "processing"]))).all()),
        "title": "Löydetään sinun soundisi",
        "description": "Arvioi, kuinka paljon pidät kappaleistasi. Ehdotus kokoaa suosikeistasi uuden luovan suunnan yli genrerajojen.",
        "genres": [],
        "genre_prompt": "",
        "genre_styles": [],
        "genre_directions": [],
        "sound_summary": [],
        "source_asset_ids": [],
        "sources": [],
        "tracks_considered": len(tracks),
        "genres_considered": len([k for k in groups if k]),
        "ratings_count": len(rated),
        "reasons": [],
        "note": "Ehdotus tarkentuu arvioidesi myötä. Sopivuus selviää kuuntelemalla ja arvioimalla tulos.",
        "rate_asset_id": next((t.id for t in tracks if t.preference is None), tracks[0].id if tracks else None),
    }
    if not liked:
        if tracks and rated:
            result["description"] = "Yksikään mieltymysarviosi ei vielä ole vähintään 6/10. Lisää musiikkia, josta pidät, tai päivitä arviotasi."
        return result

    # Compare average enjoyment, rather than letting the biggest folder win.
    scored = []
    for key, members in groups.items():
        positive = sorted([t for t in members if t.preference is not None and t.preference >= 6], key=enjoyment_order, reverse=True)
        if positive:
            all_ratings = [t.preference for t in members if t.preference is not None]
            scored.append((mean(all_ratings), positive[0].preference, key, positive))
    scored.sort(key=lambda group: (-group[0], -group[1], group[2]))
    # Keep the proposal coherent: up to three genres, each explicitly represented.
    selected = scored[:3]
    references: list[TrackRecord] = []
    for index in range(12):
        for _, _, _, members in selected:
            if index < len(members) and len(references) < 12:
                references.append(members[index])
    named = [key for _, _, key, _ in selected if genres[key]]
    sound_summary = []
    tempos = [t.features["tempo_bpm"] for t in references if t.features.get("tempo_bpm") is not None]
    if tempos:
        sound_summary.append(f"Rytminen pohja noin {median(tempos):.0f} BPM")
    arcs = Counter(t.analysis.summary.get("structure", {}).get("energy_arc", {}).get("type") for t in references)
    if arcs:
        arc = arcs.most_common(1)[0][0]
        if arc in ENERGY_ARC_FI:
            sound_summary.append(ENERGY_ARC_FI[arc])
    result.update(
        title="Sinun oma yhdistelmäsi" if len(named) > 1 else "Uusi suunta suosikeistasi",
        description=("Yhdistetään " + ", ".join(labels[k].lower() for k in named) + " omaksi uudeksi soundiksesi.")
        if named else "Luodaan uusi suunta eniten pitämiesi kappaleiden rytmistä, soinnista ja rakenteesta.",
        genres=[labels[k] for k in named],
        genre_prompt=", ".join(genres[k] for k in named),
        genre_styles=[genres[k] for k in named],
        genre_directions=[{"name": genres[k], "basis": genre_bases[k]} for k in named],
        sound_summary=sound_summary,
        source_asset_ids=[t.id for t in references],
        sources=[{"id": t.id, "title": t.asset.title or t.asset.original_filename, "preference": t.preference} for t in references],
        reasons=[
            f"Vertailussa {len(tracks)} analysoitua kappaletta ja {len(rated)} mieltymysarviota kaikista lokeroista, myös lajittelemattomista kappaleista.",
            "Lähteiksi valitaan vähintään 6/10 pitämäsi kappaleet. Tyylien järjestys perustuu niiden kaikkien mieltymysarvioiden keskiarvoon.",
            f"Kehotteessa käytetään {len(references)} suosikkia enintään kolmesta tyyliryhmästä. Rytmi, sointi ja rakenne johdetaan näiden analyyseistä.",
        ],
    )
    return result
