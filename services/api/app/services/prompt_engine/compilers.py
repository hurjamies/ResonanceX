"""Provider-specific prompt compilers.

Each compiler turns a ``PromptSpecification`` into a provider package. The
specification stays provider-neutral; adding a provider means adding a
compiler + an adapter in ``app.services.integrations``.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.services.prompt_engine.builder import OBJECTIVES, TITLE_WORDS
from app.services.prompt_engine.specification import PromptSpecification

SUNO_STYLE_SOFT_LIMIT = 450  # keep styles concise; Suno's hard limit should be verified in-app
SUNO_CREATE_URL = "https://suno.com/create"

MODE_LABELS_FI = {
    "deep_resonance": "Syvä resonanssi",
    "intensification": "Tunteen voimistaminen",
    "unknown_territory": "Tuntematon alue",
}

# Where each field goes in Suno and how reliably Suno follows it
SUNO_FIELD_SUPPORT = {
    "title": {"kind": "suno_field", "note_fi": "Suno: Title-kenttä (Custom Mode)."},
    "style": {"kind": "suno_field", "note_fi": "Suno: Styles-kenttä. v6:ssa Variety-liukusäädin muokkaa tyylikehotetta – aseta se 0:aan, jos haluat tagit sellaisinaan."},
    "lyrics": {"kind": "imperfect", "note_fi": "Suno: Lyrics-kenttä. Hakasulkeissa olevat rakennetagit ovat ohjeita, joita Suno voi tulkita epätarkasti."},
    "instrumental": {"kind": "suno_field", "note_fi": "Suno: Instrumental-valinta."},
    "exclude": {"kind": "suno_field", "note_fi": "Suno: Advanced Options → Exclude (Pro/Premier). Muuten tyylikenttään miinusmerkillä, esim. -piano."},
    "primary_genre": {"kind": "free_text_hint", "note_fi": "Sisältyy tyylikenttään."},
    "hybrid_genre": {"kind": "free_text_hint", "note_fi": "Sisältyy tyylikenttään."},
    "creative_direction": {"kind": "free_text_hint", "note_fi": "Ohje omaan käyttöön tai Sunon kuvaukseen (Simple Mode)."},
    "settings": {"kind": "imperfect", "note_fi": "Suositus. Tarkista nykyiset säätimet ja mallit Sunosta – saatavuus riippuu tilauksesta."},
}


def _pick(seed: str, words: list[str], salt: str) -> str:
    h = int(hashlib.sha256((seed + salt).encode()).hexdigest(), 16)
    return words[h % len(words)]


def make_title(spec: PromptSpecification, seed: str) -> str:
    a, b = TITLE_WORDS.get(spec.objective or "", TITLE_WORDS["default"])
    if spec.mode == "unknown_territory":
        a, b = TITLE_WORDS["default"]
    return f"{_pick(seed, a, 'a')} {_pick(seed, b, 'b')}"


def _dedupe(items: list[str]) -> list[str]:
    out, seen = [], set()
    for x in items:
        k = x.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(x.strip())
    return out


def compile_suno(spec: PromptSpecification, seed: str) -> dict[str, Any]:
    genres = [g.name for g in spec.genre_hypotheses]
    primary = genres[0] if genres else None
    hybrid = spec.hybrid_genre
    vocal = spec.vocal_direction
    # prioritised descriptor list – coherent, not exhaustive
    ordered: list[str] = []
    if hybrid:
        ordered.append(hybrid.replace(" × ", " meets ").replace(" / ", " with "))
    elif primary:
        ordered.append(primary)
    ordered += spec.rhythm_direction[:2]
    ordered += spec.bass_direction[:2]
    ordered += spec.harmonic_direction[:2]
    ordered += spec.texture_direction[:3]
    ordered += spec.energy_arc[:1]
    ordered.append(vocal)
    ordered = _dedupe(ordered)
    style_parts: list[str] = []
    length = 0
    dropped: list[str] = []
    for part in ordered:
        if length + len(part) + 2 > SUNO_STYLE_SOFT_LIMIT and part != vocal:
            dropped.append(part)
            continue
        style_parts.append(part)
        length += len(part) + 2
    style = ", ".join(style_parts)

    lyrics_lines = []
    for s in spec.structure:
        lyrics_lines.append(f"[{s.tag}: {s.description}]")
        if vocal != "instrumental" and s.tag in ("Verse", "Chorus", "Bridge"):
            lyrics_lines.append("")
    lyrics = "\n".join(lyrics_lines)

    exclude = ", ".join(_dedupe(spec.negative_constraints)[:8])
    model = spec.provider_model or ("v6-wild" if spec.extra.get("suggest_wild_model") else "v6")
    exp = spec.extra.get("experimentation")
    weirdness = 50
    if spec.mode == "unknown_territory":
        weirdness = int(min(85, 55 + 3 * (exp or 6)))
    elif spec.mode == "deep_resonance":
        weirdness = 35
    style_influence = 75 if spec.mode == "deep_resonance" else (65 if spec.mode == "intensification" else 45)

    tempo = next((t for t in spec.target_features if t.feature == "tempo_bpm"), None)
    package = {
        "mode": spec.mode,
        "mode_label": MODE_LABELS_FI[spec.mode],
        "objective": spec.objective,
        "objective_label": OBJECTIVES[spec.objective]["label"] if spec.objective in OBJECTIVES else None,
        "title": make_title(spec, seed),
        "primary_genre": primary,
        "hybrid_genre": hybrid,
        "style": style,
        "style_dropped": dropped,
        "lyrics": lyrics,
        "lyrics_note_fi": (
            "Instrumentaali: rakennetagit ohjaavat kappaleen kulkua."
            if vocal == "instrumental"
            else "Kirjoita omat sanat tagien alle tai käytä Sunon sanoitustoimintoa. Sovellus ei generoi sanoituksia ilman kielimallia."
        ),
        "instrumental": vocal == "instrumental",
        "vocal": vocal,
        "exclude": exclude,
        "creative_direction": spec.creative_direction,
        "evidence_fi": spec.evidence_fi,
        "uncertainty_fi": spec.uncertainty_fi,
        "experimental_hypotheses": spec.experimental_hypotheses,
        "target_summary": [
            {"feature": t.feature, "label": t.label, "target": t.target, "tolerance": t.tolerance, "unit": t.unit, "source": t.source, "evidence_level": t.evidence_level}
            for t in spec.target_features
        ],
        "tempo_hint": None if not tempo else round(tempo.target),
        "settings": {
            "model": model,
            "weirdness": weirdness,
            "style_influence": style_influence,
            "variety": 0,
            "note_fi": "Suositukset perustuvat Sunon dokumentoimiin säätimiin (Weirdness, Style Influence, v6:n Variety). Saatavuus vaihtelee mallin ja tilauksen mukaan.",
        },
        "field_support": SUNO_FIELD_SUPPORT,
        "suno_url": SUNO_CREATE_URL,
    }
    return package


def compile_elevenlabs_plan(spec: PromptSpecification) -> dict[str, Any]:
    """Legacy ElevenLabs *music_v1* sections-plan export (offline, for reference).

    The shape follows the compose-detailed reference example. music_v1 is deprecated
    (removal 31 Jan 2027); music_v2/v2.5 use a chunk-based plan. The live adapter
    (``app.services.integrations.elevenlabs``) therefore never sends this structure:
    it asks ElevenLabs' free ``/v1/music/plan`` endpoint for a plan and sends that back.
    """
    globals_pos = _dedupe(
        [g.name for g in spec.genre_hypotheses[:2]] + spec.rhythm_direction[:2] + spec.bass_direction[:1] + spec.harmonic_direction[:2] + spec.texture_direction[:2]
    )
    sections = []
    for s in spec.structure:
        sections.append(
            {
                "section_name": s.tag,
                "positive_local_styles": [s.description],
                "negative_local_styles": [],
                "duration_ms": int((s.approx_seconds or 20) * 1000),
                "lines": [],
            }
        )
    return {
        "positive_global_styles": globals_pos + ([] if spec.vocal_direction != "instrumental" else ["instrumental"]),
        "negative_global_styles": _dedupe(spec.negative_constraints)[:8],
        "sections": sections,
        "_status": "legacy-music_v1-offline-export",
    }
