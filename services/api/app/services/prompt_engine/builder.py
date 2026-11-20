"""Builds PromptSpecifications for the three Prompt Studio modes.

Translation principle: numerical analysis → descriptions a generative model can
reasonably follow ("slow hypnotic pulse around 90 BPM"). Values always come from
measured reference tracks, the user's profile, or explicit user controls –
never invented. General musical conventions used for an objective are marked as
such (``objective_convention``) and kept separate from personal evidence.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.schemas.vocabulary import DIMENSION_LABELS, FEATURE_BY_KEY, PROFILE_FEATURES
from app.services.prompt_engine.specification import (
    EvidenceReference,
    GenreHypothesis,
    PromptControls,
    PromptSpecification,
    StructureSection,
    TargetFeature,
)
from app.services.resonance_core.core import EVIDENCE_FI, EVIDENCE_ORDER, fmt_value
from app.services.resonance_core.dataset import TrackRecord


class PromptBuildError(Exception):
    pass


OBJECTIVES: dict[str, dict[str, Any]] = {
    "bodily_intensity": {
        "label": "Kehollinen intensiteetti",
        "dimension": "bodily_resonance",
        "tempo_factor": 1.0,
        "rhythm": ["physical, body-moving groove"],
        "bass": ["massive sub-bass weight", "bass felt in the chest"],
        "texture": ["punchy transients"],
        "arc": [],
        "exclude": ["thin low end"],
        "shift": {"bass_ratio": +1, "sub_bass_ratio": +1, "pulse_clarity": +1, "beat_strength": +1},
    },
    "melancholy": {
        "label": "Melankolia",
        "dimension": "melancholy",
        "tempo_factor": 0.9,
        "harmony": ["minor key", "bittersweet harmonies"],
        "texture": ["intimate, reverb-soaked space", "fragile melodic lines"],
        "arc": [],
        "exclude": ["upbeat party energy"],
        "mode": "minor",
        "shift": {"spectral_centroid_hz": -1, "major_mode": -1, "onset_density": -1},
    },
    "hypnotic": {
        "label": "Hypnoottinen uppoutuminen",
        "dimension": "immersion",
        "tempo_factor": 1.0,
        "rhythm": ["hypnotic repetition", "locked, unwavering pulse"],
        "texture": ["slowly evolving textures", "subtle modulation over time"],
        "arc": ["trance-like continuity without abrupt breaks"],
        "exclude": ["abrupt genre switches"],
        "shift": {"rhythmic_repetition": +1, "rhythmic_regularity": +1, "sudden_changes_per_min": -1},
    },
    "mystery": {
        "label": "Mystisyys",
        "dimension": "mystery",
        "tempo_factor": 0.95,
        "harmony": ["modal, ambiguous harmony", "unresolved tension"],
        "texture": ["dark, shadowy atmosphere", "unusual sound design details"],
        "arc": [],
        "exclude": ["cheerful major-key pop"],
        "shift": {"key_confidence": -1, "tonal_tension": +1, "spectral_centroid_hz": -1},
    },
    "release": {
        "label": "Tunteellinen vapautuminen",
        "dimension": "emotional_intensity",
        "tempo_factor": 1.0,
        "arc": ["long patient build to a cathartic climax", "emotional release after sustained tension"],
        "texture": ["swelling layers"],
        "exclude": ["flat, static energy"],
        "shift": {"build_gradualness": +1, "crescendo_seconds": +1, "loudness_range_lu": +1},
    },
    "calm": {
        "label": "Rauhallisuus",
        "dimension": "calm",
        "tempo_factor": 0.85,
        "rhythm": ["gentle, unhurried pulse"],
        "texture": ["soft, warm textures", "spacious mix"],
        "arc": ["gentle, gradual development"],
        "exclude": ["aggressive drums", "harsh distortion"],
        "shift": {"onset_density": -1, "percussive_fraction": -1, "loudness_lufs": -1, "sudden_changes_per_min": -1},
    },
    "power": {
        "label": "Voima",
        "dimension": "power",
        "tempo_factor": 1.0,
        "rhythm": ["driving, forceful rhythm"],
        "bass": ["heavy low end"],
        "texture": ["dense, powerful wall of sound"],
        "arc": ["commanding peaks"],
        "exclude": ["timid, thin arrangement"],
        "shift": {"loudness_lufs": +1, "texture_density": +1, "beat_strength": +1},
    },
    "awe": {
        "label": "Ihmetys ja suuruus",
        "dimension": "awe",
        "tempo_factor": 0.95,
        "texture": ["vast, wide stereo space", "monumental layered swells"],
        "arc": ["slow ascent to an overwhelming, expansive peak"],
        "exclude": ["small, dry room sound"],
        "shift": {"stereo_width": +1, "crescendo_seconds": +1, "texture_density": +1},
    },
    "euphoria": {
        "label": "Euforia",
        "dimension": "euphoria",
        "tempo_factor": 1.05,
        "harmony": ["uplifting, luminous harmonies"],
        "texture": ["bright, shimmering layers"],
        "arc": ["soaring euphoric peak"],
        "exclude": ["gloomy, muddy mix"],
        "shift": {"spectral_centroid_hz": +1, "major_mode": +1},
    },
    "longing": {
        "label": "Kaipaus",
        "dimension": "longing",
        "tempo_factor": 0.92,
        "harmony": ["yearning melodic lines", "suspended, unresolved chords"],
        "texture": ["distant, nostalgic atmosphere"],
        "arc": [],
        "exclude": ["cheerful novelty sounds"],
        "shift": {"tonal_tension": +1},
    },
    "sensual": {
        "label": "Aistillisuus",
        "dimension": "sensual",
        "tempo_factor": 0.95,
        "rhythm": ["slow, sensual groove", "laid-back swing"],
        "bass": ["round, warm bass"],
        "texture": ["intimate, velvety textures"],
        "arc": [],
        "exclude": ["harsh, aggressive sounds"],
        "shift": {"spectral_centroid_hz": -1, "syncopation": +1},
    },
}

# English prompt phrases for low/high feature values
FEATURE_PHRASES: dict[str, tuple[str, str]] = {
    "pulse_clarity": ("loose, floating rhythm", "clear, strong pulse"),
    "rhythmic_regularity": ("human, elastic timing", "steady, machine-tight timing"),
    "onset_density": ("sparse, spacious rhythm", "busy, intricate rhythm"),
    "beat_strength": ("soft, understated beats", "hard-hitting beats"),
    "syncopation": ("", "syncopated groove"),  # a low value is not informative
    "rhythmic_repetition": ("varied rhythmic patterns", "hypnotic rhythmic repetition"),
    "tempo_variation_bpm": ("rock-steady tempo", "fluid, shifting tempo"),
    "sub_bass_ratio": ("light sub-bass", "deep sub-bass"),
    "bass_ratio": ("light low end", "heavy, weighty bass"),
    "low_mid_ratio": ("lean low-mids", "full, warm low-mids"),
    "mid_ratio": ("scooped mids", "forward midrange"),
    "treble_ratio": ("soft, rolled-off highs", "crisp, airy highs"),
    "spectral_centroid_hz": ("dark, warm tone", "bright, glassy tone"),
    "spectral_flatness": ("pure, tonal sounds", "noisy, gritty textures"),
    "bass_modulation_strength": ("smooth sustained bass", "pulsing bassline"),
    "bass_modulation_depth": ("even bass level", "surging, dynamic bass"),
    "major_mode": ("minor key", "major key"),
    "key_confidence": ("modal, ambiguous tonality", "clear tonal center"),
    "harmonic_stability": ("restless, moving harmony", "static, drone-like harmony"),
    "chord_change_rate": ("slow-moving harmony", "frequent chord changes"),
    "tonal_tension": ("consonant, resolved harmony", "unresolved harmonic tension"),
    "loudness_lufs": ("soft, quiet mix", "loud, dense master"),
    "loudness_range_lu": ("even dynamics", "wide dynamics with quiet and loud passages"),
    "crest_factor_db": ("compressed, solid sound", "open, transient-rich sound"),
    "percussive_fraction": ("lush sustained tones", "percussion-forward mix"),
    "stereo_width": ("focused, narrow image", "wide, immersive stereo field"),
    "texture_density": ("sparse, minimal arrangement", "dense, layered textures"),
    "build_gradualness": ("no long build", "gradually evolving arrangement"),
    "peak_position": ("opens at full intensity", "peak arrives late"),
    "crescendo_seconds": ("short swells", "prolonged emotional crescendo"),
    "sudden_changes_per_min": ("smooth continuous development", "sudden dramatic drops and contrasts"),
    "structural_repetition": ("through-composed structure", "repeating sections"),
}

ARC_PHRASES = {
    "gradual_build": "gradually evolving arrangement with a prolonged emotional crescendo",
    "sudden_contrasts": "dramatic contrasts with sudden drops and surges",
    "plateau": "steady, continuous trance-like energy",
    "waves": "waves of tension and release",
    "early_peak": "opens at full intensity and slowly dissolves",
}

TOLERANCES = {
    "tempo_bpm": 6.0,
    "bass_ratio": 0.08,
    "sub_bass_ratio": 0.06,
    "treble_ratio": 0.03,
    "spectral_centroid_hz": 400.0,
    "pulse_clarity": 0.15,
    "onset_density": 0.8,
    "texture_density": 0.12,
    "loudness_range_lu": 3.0,
    "loudness_lufs": 3.0,
    "stereo_width": 0.12,
    "percussive_fraction": 0.1,
    "rhythmic_repetition": 0.1,
    "major_mode": 0.0,
    "build_gradualness": 0.35,
    "harmonic_stability": 0.1,
    "chord_change_rate": 4.0,
    "crescendo_seconds": 25.0,
}

GENRE_FAMILIES = [
    "ambient", "downtempo", "trip-hop", "deep house", "techno", "trance", "dubstep", "drum and bass",
    "cinematic orchestral", "neoclassical", "post-rock", "shoegaze", "darkwave", "synthwave", "trap",
    "R&B", "dream pop", "industrial", "folk", "world fusion", "jazz", "doom metal", "minimal electronic",
]

CONTRAST_GENRES = {
    "ambient": ["breakbeat", "industrial", "Afrobeat"],
    "downtempo": ["post-rock", "Balkan brass", "drum and bass"],
    "trip-hop": ["Nordic folk", "techno", "gospel"],
    "deep house": ["neoclassical", "dub", "shoegaze"],
    "techno": ["Gregorian chant", "cinematic orchestral", "flamenco"],
    "trance": ["doom metal", "trip-hop", "throat singing"],
    "dubstep": ["string quartet", "dream pop", "Celtic folk"],
    "drum and bass": ["ambient choir", "jazz", "gamelan"],
    "cinematic orchestral": ["techno", "trap", "industrial"],
    "post-rock": ["UK garage", "synthwave", "Afrobeat"],
    "default": ["neoclassical", "industrial", "world fusion"],
}

# File "genre" tags that describe no musical style. Downloads (e.g. from YouTube) often carry the
# platform's video category instead of a genre; sent to Suno they would steer the style field.
# The original tag is kept on the asset; it is only ignored as a style hint.
NON_MUSICAL_GENRE_TAGS = {
    "music", "musiikki", "audio", "song", "songs", "other", "others", "misc", "miscellaneous", "unknown",
    "genre", "none", "n/a", "na", "-", "various", "default", "general", "uncategorized", "unclassified",
    # YouTube video categories
    "film & animation", "autos & vehicles", "pets & animals", "sports", "travel & events", "gaming",
    "people & blogs", "comedy", "entertainment", "news & politics", "howto & style", "education",
    "science & technology", "nonprofits & activism", "shows", "trailers", "movies",
}


def usable_genre_tag(tag: str | None) -> str | None:
    """Return a file genre tag only if it plausibly names a musical style."""
    if not tag:
        return None
    clean = " ".join(tag.split())
    key = clean.casefold()
    if not clean or key in NON_MUSICAL_GENRE_TAGS or len(clean) > 40:
        return None
    # ID3v1 numeric genre codes such as "17" or "(17)" carry no readable style.
    if key.strip("()").isdigit():
        return None
    return clean

TITLE_WORDS = {
    "default": (["Low", "Deep", "Distant", "Hidden", "Slow", "Quiet", "Inner", "Silver", "Midnight", "Hollow"],
                ["Current", "Signal", "Field", "Horizon", "Pulse", "Tide", "Orbit", "Threshold", "Echo", "Drift"]),
    "melancholy": (["Faded", "Grey", "Last", "Cold", "Pale", "Lost"], ["Letters", "Rain", "Light", "Harbor", "Winter", "Shore"]),
    "bodily_intensity": (["Heavy", "Iron", "Deep", "Pressure", "Gravity", "Engine"], ["Pulse", "Weight", "Body", "Core", "Wave", "Ground"]),
    "hypnotic": (["Endless", "Circular", "Slow", "Inner", "Spiral", "Liquid"], ["Motion", "Loop", "Mantra", "Orbit", "Drift", "Tide"]),
    "mystery": (["Veiled", "Hidden", "Black", "Unknown", "Night", "Shadow"], ["Door", "Signal", "Archive", "Garden", "Room", "Mirror"]),
    "release": (["Breaking", "Open", "Rising", "Burning", "First", "Final"], ["Light", "Sky", "Water", "Dawn", "Release", "Flood"]),
    "calm": (["Still", "Soft", "Slow", "Morning", "Pale", "Quiet"], ["Water", "Field", "Air", "Snow", "Room", "Breath"]),
    "power": (["Iron", "Titan", "Storm", "Steel", "Thunder", "Atlas"], ["March", "Engine", "Crown", "Ground", "Force", "Wall"]),
    "awe": (["Vast", "Cathedral", "Endless", "Celestial", "High", "Ancient"], ["Sky", "Light", "Ocean", "Altitude", "Vault", "Horizon"]),
    "euphoria": (["Golden", "Bright", "Wild", "Electric", "Rising", "Radiant"], ["Hour", "Sun", "Heart", "Bloom", "Sky", "Fire"]),
    "longing": (["Far", "Lost", "Northern", "Fading", "Distant", "Old"], ["Shore", "Lights", "Home", "Letters", "Summer", "Road"]),
    "sensual": (["Velvet", "Warm", "Slow", "Amber", "Silk", "Night"], ["Skin", "Heat", "Hours", "Smoke", "Room", "Tide"]),
}


@dataclass
class Reference:
    values: dict[str, float]
    sources: dict[str, str]  # feature -> "sources" | "profile"
    evidence: dict[str, str]  # feature -> evidence level
    arc_type: str | None
    half_time: bool
    genre_tags: list[str]
    segments_roles: list[str]


def _median(vals: list[float]) -> float | None:
    vals = [v for v in vals if v is not None]
    return float(np.median(vals)) if vals else None


def build_reference(sources: list[TrackRecord], profile: dict[str, Any] | None) -> Reference:
    values: dict[str, float] = {}
    src: dict[str, str] = {}
    evidence: dict[str, str] = {}
    for key in PROFILE_FEATURES + ["tempo_bpm"]:
        m = _median([t.features.get(key) for t in sources])
        if m is not None:
            values[key] = m
            src[key] = "sources"
            evidence[key] = "observation"
    targets = (profile or {}).get("targets") or {}
    if targets.get("basis") == "strongest_responses":
        for f in targets.get("features", []):
            lvl = f["evidence_level"]
            # profile values override source values only when the evidence is stronger
            if f["feature"] not in values or EVIDENCE_ORDER[lvl] >= EVIDENCE_ORDER["preliminary"]:
                values[f["feature"]] = f["median"]
                src[f["feature"]] = "profile"
                evidence[f["feature"]] = lvl
    arcs = [t.analysis.summary["structure"]["energy_arc"]["type"] for t in sources]
    arc = max(set(arcs), key=arcs.count) if arcs else None
    if arc is None and targets.get("basis") == "strongest_responses":
        gb = values.get("build_gradualness")
        if gb is not None and gb > 0.6:
            arc = "gradual_build"
    half = any((t.analysis.summary["rhythm"].get("tempo_ambiguity") or {}).get("kind") == "half" for t in sources)
    usable = [g for g in (usable_genre_tag(t.asset.genre_tag) for t in sources) if g]
    tags = sorted({g.casefold(): g for g in usable}.values(), key=str.casefold)
    roles: list[str] = []
    for t in sources[:1]:
        roles = [s.get("role", "section") for s in t.analysis.segments]
    return Reference(values, src, evidence, arc, half, tags, roles)


def tempo_phrase(bpm: float, clarity: float | None, regularity: float | None, repetition: float | None, half_time: bool) -> str:
    if bpm < 70:
        word = "very slow"
    elif bpm < 92:
        word = "slow"
    elif bpm < 110:
        word = "mid-tempo"
    elif bpm < 128:
        word = "upbeat"
    elif bpm < 150:
        word = "driving"
    else:
        word = "fast"
    pulse = "pulse"
    if clarity is not None and clarity >= 0.6 and (repetition or 0) >= 0.85:
        pulse = "hypnotic pulse"
    elif clarity is not None and clarity >= 0.6:
        pulse = "steady pulse"
    elif clarity is not None and clarity < 0.3:
        pulse = "floating, loosely felt pulse"
    rounded = int(round(bpm / 2) * 2)
    phrase = f"{word} {pulse} around {rounded} BPM"
    if half_time:
        phrase += " with a half-time feel"
    return phrase


def heuristic_genres(v: dict[str, float]) -> list[str]:
    """Rule-based genre-family suggestions from measured features.

    These are *heuristic creative hypotheses*, not classifications: no genre
    model is used in this version.
    """
    def g(k: str) -> float | None:
        x = v.get(k)
        return None if x is None else float(x)

    def has(*keys: str) -> bool:
        return all(g(k) is not None for k in keys)

    bpm, sub, bass, clarity = g("tempo_bpm"), g("sub_bass_ratio"), g("bass_ratio"), g("pulse_clarity")
    perc, rep, centroid, flat = g("percussive_fraction"), g("rhythmic_repetition"), g("spectral_centroid_hz"), g("spectral_flatness")
    dens, lra, sync, lufs = g("onset_density"), g("loudness_range_lu"), g("syncopation"), g("loudness_lufs")
    out: list[str] = []
    # missing measurements never imply a genre: every rule requires its inputs
    if has("pulse_clarity", "onset_density", "percussive_fraction") and clarity < 0.3 and dens < 1.5 and perc < 0.25:
        out.append("ambient")
    if has("tempo_bpm", "pulse_clarity") and 160 <= bpm <= 182 and clarity >= 0.4:
        out.append("drum and bass")
    if has("tempo_bpm", "sub_bass_ratio") and (135 <= bpm <= 146 or 67 <= bpm <= 73) and sub >= 0.15:
        out.append("dubstep")
    if has("tempo_bpm", "pulse_clarity", "rhythmic_repetition", "bass_ratio") and 118 <= bpm <= 132 and clarity >= 0.5 and rep >= 0.8 and bass >= 0.3:
        out.append("deep house" if (centroid or 2000) < 2200 else "techno")
    if has("tempo_bpm", "rhythmic_repetition", "spectral_centroid_hz") and 128 <= bpm <= 145 and rep >= 0.85 and centroid >= 2000:
        out.append("trance")
    if has("tempo_bpm", "sub_bass_ratio", "percussive_fraction") and 60 <= bpm <= 100 and sub >= 0.15 and perc >= 0.3:
        out.append("trap" if (sync or 0) > 0.15 else "trip-hop")
    if has("tempo_bpm", "percussive_fraction", "pulse_clarity") and 60 <= bpm <= 105 and perc < 0.35 and clarity >= 0.3 and "trip-hop" not in out:
        out.append("downtempo")
    if has("percussive_fraction", "loudness_range_lu") and perc < 0.25 and lra >= 8:
        out.append("cinematic orchestral")
    if has("spectral_centroid_hz", "spectral_flatness", "loudness_lufs") and centroid >= 3000 and flat >= 0.05 and lufs > -10:
        out.append("industrial")
    if not out:
        out.append("alternative electronic")
    seen: list[str] = []
    for g in out:
        if g not in seen:
            seen.append(g)
    return seen[:3]


def _dir(value: float | None, key: str, lib: dict[str, Any]) -> int:
    """-1 low, 0 typical, +1 high – relative to the library when possible,
    otherwise to broad absolute reference ranges for recorded music."""
    if value is None:
        return 0
    stats = lib.get(key)
    if stats and stats.get("n", 0) >= 5 and stats["p75"] > stats["p25"]:
        if value >= stats["p75"]:
            return 1
        if value <= stats["p25"]:
            return -1
        return 0
    absolute = {
        "pulse_clarity": (0.3, 0.6), "rhythmic_regularity": (0.4, 0.75), "onset_density": (1.5, 3.5),
        "beat_strength": (1.1, 1.6), "syncopation": (0.05, 0.2), "rhythmic_repetition": (0.75, 0.9),
        "sub_bass_ratio": (0.06, 0.16), "bass_ratio": (0.25, 0.45), "treble_ratio": (0.01, 0.05),
        "spectral_centroid_hz": (1400, 2800), "spectral_flatness": (0.005, 0.05),
        "bass_modulation_strength": (0.8, 1.6), "key_confidence": (0.25, 0.6),
        "harmonic_stability": (0.75, 0.92), "chord_change_rate": (8, 25), "tonal_tension": (0.25, 0.4),
        "loudness_lufs": (-16, -9), "loudness_range_lu": (4, 10), "percussive_fraction": (0.2, 0.45),
        "stereo_width": (0.15, 0.45), "texture_density": (0.35, 0.6), "build_gradualness": (0.2, 0.6),
        "crescendo_seconds": (20, 60), "sudden_changes_per_min": (0.2, 1.0), "structural_repetition": (0.2, 0.5),
        "major_mode": (0.5, 0.5),
    }
    lo_hi = absolute.get(key)
    if not lo_hi:
        return 0
    if key == "major_mode":
        return 1 if value >= 0.5 else -1
    if value >= lo_hi[1]:
        return 1
    if value <= lo_hi[0]:
        return -1
    return 0


class SpecBuilder:
    def __init__(self, profile: dict[str, Any] | None, sources: list[TrackRecord], controls: PromptControls, objective: str | None, seed: str):
        self.profile = profile or {}
        self.sources = sources
        self.controls = controls
        self.objective = objective if objective in OBJECTIVES else None
        self.seed = seed
        self.lib = self.profile.get("library_stats") or {}
        self.ref = build_reference(sources, profile)
        if not self.ref.values:
            raise PromptBuildError(
                "Kehotteen pohjaksi tarvitaan vähintään yksi analysoitu lähdekappale tai arvioituja kappaleita profiilissa."
            )

    def _rng_pick(self, options: list[str], salt: str) -> str:
        h = int(hashlib.sha256((self.seed + salt).encode()).hexdigest(), 16)
        return options[h % len(options)]

    # ------------------------------------------------------------------
    def _base_spec(self, mode: str) -> PromptSpecification:
        c = self.controls
        v = dict(self.ref.values)
        spec = PromptSpecification(
            mode=mode,  # type: ignore[arg-type]
            objective=self.objective,
            profile_version=self.profile.get("version"),
            source_asset_ids=[t.id for t in self.sources],
            source_analysis_ids=[int(t.analysis.id) for t in self.sources],
            target_duration_seconds=c.duration_seconds,
            provider_model=c.provider_model,
        )
        # Evidence statements
        if self.sources:
            names = ", ".join(t.asset.title for t in self.sources[:4])
            spec.evidence_fi.append(f"Lähdekappaleet ({len(self.sources)}): {names}. Niiden mitatut piirteet muodostavat pohjan.")
            for t in self.sources:
                spec.evidence_references.append(EvidenceReference(kind="track", ref=str(t.id), title=t.asset.title))
        tg = self.profile.get("targets") or {}
        if tg.get("basis") == "strongest_responses":
            spec.evidence_fi.append(
                f"SonicDNA-profiili v{self.profile.get('version')}: voimakkaimmin vaikuttaneet {len(tg.get('tracks', []))} kappaletta."
            )
        # Tempo
        bpm = c.target_bpm or v.get("tempo_bpm")
        if bpm:
            src = "user" if c.target_bpm else self.ref.sources.get("tempo_bpm", "sources")
            phrase = tempo_phrase(bpm, v.get("pulse_clarity"), v.get("rhythmic_regularity"), v.get("rhythmic_repetition"), self.ref.half_time and not c.target_bpm)
            spec.rhythm_direction.append(phrase)
            spec.target_features.append(
                TargetFeature(feature="tempo_bpm", label="Tempo", target=round(bpm, 1), tolerance=TOLERANCES["tempo_bpm"], unit="BPM", priority=1,
                              evidence_level="user" if c.target_bpm else self.ref.evidence.get("tempo_bpm", "observation"), source=src, descriptor=phrase)  # type: ignore[arg-type]
            )
        # Feature-derived descriptors
        groups = {
            "rhythm": ["syncopation", "onset_density", "beat_strength", "rhythmic_regularity"],
            "bass": ["sub_bass_ratio", "bass_ratio", "bass_modulation_strength"],
            "harmonic": ["major_mode", "key_confidence", "harmonic_stability", "tonal_tension"],
            "texture": ["spectral_centroid_hz", "texture_density", "percussive_fraction", "stereo_width", "spectral_flatness", "loudness_range_lu"],
        }
        target_list = {f["feature"]: f for f in tg.get("features", [])}
        for group, keys in groups.items():
            for key in keys:
                val = v.get(key)
                d = _dir(val, key, self.lib)
                if d == 0:
                    continue
                phrase = FEATURE_PHRASES[key][1 if d > 0 else 0]
                if not phrase:
                    continue
                if key == "bass_modulation_strength" and d > 0:
                    rel = None
                    for t in self.sources:
                        rel = t.analysis.summary["spectral"]["bass_modulation"].get("beat_relation")
                    if rel:
                        if 0.85 <= rel <= 1.15:
                            phrase = "pulsing bassline locked to every beat"
                        elif 0.42 <= rel <= 0.58:
                            phrase = "slow bass pulses every two beats"
                        elif 1.8 <= rel <= 2.2:
                            phrase = "driving eighth-note bass pulse"
                getattr(spec, {"rhythm": "rhythm_direction", "bass": "bass_direction", "harmonic": "harmonic_direction", "texture": "texture_direction"}[group]).append(phrase)
                lvl = self.ref.evidence.get(key, "observation")
                pri = 1 if EVIDENCE_ORDER.get(lvl, 1) >= 2 else (2 if key in target_list else 3)
                if key in TOLERANCES:
                    spec.target_features.append(
                        TargetFeature(feature=key, label=FEATURE_BY_KEY[key].label, target=round(float(val), 4), tolerance=TOLERANCES[key],
                                      unit=FEATURE_BY_KEY[key].unit, priority=pri, evidence_level=lvl, source=self.ref.sources.get(key, "sources"), descriptor=phrase)  # type: ignore[arg-type]
                    )
        if (v.get("rhythmic_repetition") or 0) >= 0.9 and "hypnotic" not in " ".join(spec.rhythm_direction):
            spec.rhythm_direction.append("hypnotic rhythmic repetition")
        # Energy arc
        if self.ref.arc_type:
            spec.energy_arc.append(ARC_PHRASES[self.ref.arc_type])
        gb = v.get("build_gradualness")
        if gb is not None and "build_gradualness" in TOLERANCES and self.ref.arc_type == "gradual_build":
            spec.target_features.append(TargetFeature(feature="build_gradualness", label=FEATURE_BY_KEY["build_gradualness"].label, target=round(gb, 3),
                                                      tolerance=TOLERANCES["build_gradualness"], unit="", priority=2,
                                                      evidence_level=self.ref.evidence.get("build_gradualness", "observation"),
                                                      source=self.ref.sources.get("build_gradualness", "sources"), descriptor=spec.energy_arc[-1]))  # type: ignore[arg-type]
        # Genres
        if c.genre:
            for g in [x.strip() for x in c.genre.replace("/", ",").split(",") if x.strip()][:3]:
                spec.genre_hypotheses.append(GenreHypothesis(name=g, basis="user"))
        for g in self.ref.genre_tags[:2]:
            spec.genre_hypotheses.append(GenreHypothesis(name=g, basis="file_metadata", note="Lähdetiedoston metatieto"))
        for g in heuristic_genres(v):
            if all(g.lower() != h.name.lower() for h in spec.genre_hypotheses):
                spec.genre_hypotheses.append(GenreHypothesis(name=g, basis="heuristic", note="Sääntöpohjainen arvio mitatuista piirteistä – ei genreluokitin"))
        # Vocals
        spec.vocal_direction = {
            None: "instrumental", "instrumental": "instrumental", "female": "female vocals", "male": "male vocals",
            "duet": "male and female duet vocals", "choir": "wordless choir", "any": "vocals",
        }[c.vocal]
        # Negative constraints from the profile's negative tendencies
        for tnd in (self.profile.get("negative_tendencies") or [])[:3]:
            low, high = FEATURE_PHRASES.get(tnd["feature"], (None, None))
            phrase = high if tnd["direction"] == "high" else low
            if phrase:
                spec.negative_constraints.append(phrase)
                spec.evidence_fi.append(
                    f"Exclude: {FEATURE_BY_KEY[tnd['feature']].label.lower()} – {tnd['count']}/{tnd['n']} vähemmän mieluisista kappaleistasi poikkeaa tähän suuntaan."
                )
        for x in c.extra_exclude:
            if x.strip():
                spec.negative_constraints.append(x.strip()[:60])
        self._apply_controls(spec)
        return spec

    def _apply_controls(self, spec: PromptSpecification) -> None:
        c = self.controls

        def add(lst: list[str], phrase: str, replace_prefix: tuple[str, ...] = ()) -> None:
            if replace_prefix:
                lst[:] = [p for p in lst if not any(w in p for w in replace_prefix)]
            if phrase not in lst:
                lst.insert(0, phrase)

        if c.rhythmic_intensity is not None:
            if c.rhythmic_intensity >= 7:
                add(spec.rhythm_direction, "intense, driving drums")
            elif c.rhythmic_intensity <= 3:
                add(spec.rhythm_direction, "minimal, restrained percussion")
        if c.bass_emphasis is not None:
            if c.bass_emphasis >= 7:
                add(spec.bass_direction, "heavy sub-bass emphasis", ("light", "bass"))
            elif c.bass_emphasis <= 3:
                add(spec.bass_direction, "restrained low end", ("bass",))
        if c.harmonic_darkness is not None:
            if c.harmonic_darkness >= 7:
                add(spec.harmonic_direction, "dark minor harmonies", ("major key", "minor key"))
            elif c.harmonic_darkness <= 3:
                add(spec.harmonic_direction, "bright, open harmonies", ("minor key", "major key"))
        if c.melancholy is not None and c.melancholy >= 6:
            add(spec.harmonic_direction, "melancholic, bittersweet mood")
        if c.euphoria is not None and c.euphoria >= 6:
            add(spec.harmonic_direction, "euphoric, uplifting mood")
        if c.hypnotic_repetition is not None:
            if c.hypnotic_repetition >= 7:
                add(spec.rhythm_direction, "hypnotic repetition")
            elif c.hypnotic_repetition <= 3:
                add(spec.rhythm_direction, "constantly evolving patterns", ("hypnotic",))
        if c.tension is not None:
            if c.tension >= 7:
                add(spec.harmonic_direction, "sustained musical tension")
            elif c.tension <= 3:
                add(spec.harmonic_direction, "relaxed, resolved harmony")
        if c.texture_density is not None:
            if c.texture_density >= 7:
                add(spec.texture_direction, "dense, layered textures", ("sparse", "dense"))
            elif c.texture_density <= 3:
                add(spec.texture_direction, "sparse, minimal arrangement", ("dense", "sparse"))
        for fld, val in c.model_dump(exclude={"extra_exclude", "provider_model", "genre", "vocal"}).items():
            if val is not None:
                spec.evidence_fi.append(f"Käyttäjän säätö: {fld} = {val:g}")

    # ------------------------------------------------------------------
    def _structure(self, spec: PromptSpecification, arc: str | None) -> None:
        dur = spec.target_duration_seconds or 210.0
        vocal = spec.vocal_direction != "instrumental"
        if arc == "gradual_build" or (self.objective in ("release", "awe")):
            plan = [("Intro", "sparse, distant atmosphere", 0.12), ("Build", "layers enter gradually", 0.2),
                    ("Verse" if vocal else "Build", "rising intensity, pulse becomes clearer", 0.2),
                    ("Climax", "full arrangement, emotional peak", 0.3), ("Outro", "slow dissolve", 0.18)]
        elif arc == "sudden_contrasts":
            plan = [("Intro", "tension-setting atmosphere", 0.1), ("Build-Up", "rising energy", 0.15), ("Drop", "full-force impact", 0.2),
                    ("Breakdown", "stripped-back, spacious", 0.15), ("Build-Up", "tension returns", 0.12), ("Drop", "biggest impact", 0.18), ("Outro", "release", 0.1)]
        elif arc == "plateau" or self.objective == "hypnotic":
            plan = [("Intro", "pulse emerges", 0.12), ("Verse" if vocal else "Instrumental", "steady, hypnotic groove", 0.28),
                    ("Bridge", "subtle textural shift, same pulse", 0.2), ("Instrumental", "groove deepens with new layers", 0.28), ("Outro", "gradual fade", 0.12)]
        elif arc == "early_peak":
            plan = [("Intro", "immediate full intensity", 0.15), ("Verse" if vocal else "Instrumental", "sustained energy", 0.3),
                    ("Breakdown", "energy thins out", 0.25), ("Outro", "long dissolve into silence", 0.3)]
        else:
            plan = [("Intro", "atmospheric opening", 0.12), ("Verse" if vocal else "Instrumental", "main groove", 0.22),
                    ("Chorus" if vocal else "Build", "tension rises", 0.18), ("Bridge", "contrast section", 0.16),
                    ("Chorus" if vocal else "Climax", "peak", 0.2), ("Outro", "release", 0.12)]
        spec.structure = [StructureSection(tag=t, description=d, approx_seconds=round(dur * f)) for t, d, f in plan]

    # ------------------------------------------------------------------
    def deep_resonance(self) -> PromptSpecification:
        spec = self._base_spec("deep_resonance")
        spec.objective = None
        self._structure(spec, self.ref.arc_type)
        g = [h for h in spec.genre_hypotheses]
        if len(g) >= 2:
            spec.hybrid_genre = f"{g[0].name} / {g[1].name}"
        spec.creative_direction = (
            "An original piece that recreates the structural qualities of the listener's strongest musical experiences "
            "— rhythm, low-end weight, harmonic colour and energy development — without imitating any existing song."
        )
        self._uncertainty(spec)
        return spec

    def intensification(self, objective: str | None) -> PromptSpecification:
        obj_key = objective if objective in OBJECTIVES else "release"
        obj = OBJECTIVES[obj_key]
        spec = self._base_spec("intensification")
        spec.objective = obj_key
        # 1) personal associations for the matching rating dimension
        dim = obj["dimension"]
        personal = [a for a in (self.profile.get("associations") or []) if a["dimension"] == dim and a["evidence_level"] != "insufficient"]
        used = set()
        for a in personal[:3]:
            key = a["feature"]
            if key not in FEATURE_PHRASES:
                continue
            phrase = FEATURE_PHRASES[key][1 if a["rho"] > 0 else 0]
            if not phrase:
                continue
            spec.texture_direction.insert(0, phrase)
            used.add(key)
            spec.evidence_fi.append(
                f"Henkilökohtainen havainto: arviosi ”{DIMENSION_LABELS[dim]}” on ollut korkeampi, kun {FEATURE_BY_KEY[key].label.lower()} on "
                f"{'korkeampi' if a['rho'] > 0 else 'matalampi'} (ρ = {a['rho']:+.2f}, n = {a['n']}, {EVIDENCE_FI[a['evidence_level']].lower()})."
            )
            spec.evidence_references.append(EvidenceReference(kind="association", ref=f"{dim}:{key}", title=f"{DIMENSION_LABELS[dim]} ~ {FEATURE_BY_KEY[key].label}", evidence_level=a["evidence_level"]))
        if not personal:
            spec.uncertainty_fi.append(
                f"Sinulla ei vielä ole riittävästi arvioita ulottuvuudesta ”{DIMENSION_LABELS[dim]}”, joten painotus perustuu yleisiin musiikillisiin konventioihin – ei henkilökohtaiseen näyttöön."
            )
        # 2) general conventions for the objective (explicitly labelled)
        for fld, key in (("rhythm_direction", "rhythm"), ("bass_direction", "bass"), ("harmonic_direction", "harmony"), ("texture_direction", "texture"), ("energy_arc", "arc")):
            for phrase in obj.get(key, []):
                lst = getattr(spec, fld)
                if phrase not in lst:
                    lst.insert(0, phrase)
        if obj.get("mode") == "minor":
            spec.harmonic_direction = [p for p in spec.harmonic_direction if p != "major key"]
        spec.evidence_fi.append(f"Tavoite ”{obj['label']}”: painotukset perustuvat yleisiin musiikillisiin konventioihin (merkitty erikseen henkilökohtaisesta näytöstä).")
        spec.evidence_references.append(EvidenceReference(kind="convention", ref=obj_key, title=obj["label"]))
        # tempo shift
        for tf in spec.target_features:
            if tf.feature == "tempo_bpm" and tf.source != "user" and obj["tempo_factor"] != 1.0:
                new = tf.target * obj["tempo_factor"]
                tf.target = round(new, 1)
                tf.source = "objective_convention"
                tf.descriptor = tempo_phrase(new, self.ref.values.get("pulse_clarity"), self.ref.values.get("rhythmic_regularity"), self.ref.values.get("rhythmic_repetition"), False)
                spec.rhythm_direction = [tf.descriptor] + [p for p in spec.rhythm_direction if "BPM" not in p]
        for x in obj.get("exclude", []):
            if x not in spec.negative_constraints:
                spec.negative_constraints.append(x)
        self._structure(spec, self.ref.arc_type)
        g = spec.genre_hypotheses
        if len(g) >= 2:
            spec.hybrid_genre = f"{g[0].name} / {g[1].name}"
        spec.creative_direction = (
            f"Keep the listener's core musical preferences but intensify the experience of {obj_key.replace('_', ' ')}: "
            "shift rhythm, harmony and texture towards that feeling while staying coherent and original."
        )
        self._uncertainty(spec)
        return spec

    def unknown_territory(self) -> PromptSpecification:
        spec = self._base_spec("unknown_territory")
        spec.objective = None
        # anchors: the strongest available target features
        tg = (self.profile.get("targets") or {}).get("features") or []
        anchors = [f for f in tg if f["direction"] != "typical" and EVIDENCE_ORDER[f["evidence_level"]] >= 1][:2]
        anchor_phrases: list[str] = []
        for f in anchors:
            if f["feature"] in FEATURE_PHRASES:
                anchor_phrases.append(FEATURE_PHRASES[f["feature"]][1 if f["direction"] == "high" else 0])
        if not anchor_phrases:
            # without profile evidence use the reference tempo and bass as anchors
            anchor_phrases = [p for p in spec.rhythm_direction[:1] + spec.bass_direction[:1]]
        # exploration: contrast genre + an untested feature pushed to the opposite side
        base_genre = next((g.name for g in spec.genre_hypotheses), "default")
        options = CONTRAST_GENRES.get(base_genre.lower(), CONTRAST_GENRES["default"])
        exp_level = self.controls.experimentation if self.controls.experimentation is not None else 6
        contrast = self._rng_pick(options, "genre")
        spec.genre_hypotheses.insert(1, GenreHypothesis(name=contrast, basis="exploration", note="Tarkoituksellinen kontrasti"))
        spec.hybrid_genre = f"{base_genre} × {contrast}" if base_genre != "default" else contrast
        untested = [k for k in ("syncopation", "stereo_width", "harmonic_stability", "spectral_flatness", "percussive_fraction", "tonal_tension")
                    if k not in {f["feature"] for f in anchors}]
        explore_key = self._rng_pick(untested, "feature")
        cur = _dir(self.ref.values.get(explore_key), explore_key, self.lib)
        new_phrase = FEATURE_PHRASES[explore_key][0 if cur > 0 else 1] or FEATURE_PHRASES[explore_key][1]
        # remove any phrase from the same feature and add the exploratory one
        lo, hi = FEATURE_PHRASES[explore_key]
        for fld in ("rhythm_direction", "bass_direction", "harmonic_direction", "texture_direction"):
            setattr(spec, fld, [p for p in getattr(spec, fld) if p not in (lo, hi)])
        spec.texture_direction.insert(0, new_phrase)
        spec.target_features = [t for t in spec.target_features if t.feature != explore_key]
        spec.rhythm_direction = anchor_phrases[:1] + [p for p in spec.rhythm_direction if p not in anchor_phrases]
        if len(anchor_phrases) > 1:
            spec.bass_direction = anchor_phrases[1:2] + [p for p in spec.bass_direction if p not in anchor_phrases]
        hypothesis = (
            f"Does the strong response to {' and '.join(anchor_phrases) or 'the core pulse'} persist when combined with "
            f"{contrast} elements and {new_phrase}?"
        )
        spec.experimental_hypotheses.append(hypothesis)
        spec.evidence_fi.append(
            f"Ankkurit (säilytetään): {', '.join(anchor_phrases) or 'lähdekappaleiden pulssi ja basso'}. "
            f"Kokeilu: kontrastigenre ”{contrast}” ja piirre ”{FEATURE_BY_KEY[explore_key].label}” vastakkaiseen suuntaan."
        )
        spec.uncertainty_fi.append("Tämä on tarkoituksellinen kokeilu: tulos voi vahvistaa tai kumota nykyisiä hypoteeseja – kumpikin on arvokasta tietoa.")
        arcs = [a for a in ARC_PHRASES if a != self.ref.arc_type]
        arc = self._rng_pick(arcs, "arc") if exp_level >= 7 else self.ref.arc_type
        spec.energy_arc = [ARC_PHRASES[arc]] if arc else []
        self._structure(spec, arc)
        spec.extra["suggest_wild_model"] = True
        spec.extra["experimentation"] = exp_level
        spec.creative_direction = (
            "A controlled experiment: keep the anchors of the listener's strongest responses, but place them in unfamiliar "
            f"territory ({contrast}) to discover new sources of resonance."
        )
        self._uncertainty(spec)
        return spec

    def _uncertainty(self, spec: PromptSpecification) -> None:
        lv = [t.evidence_level for t in spec.target_features if t.source in ("profile", "sources")]
        if not lv or all(EVIDENCE_ORDER.get(x, 0) <= 1 for x in lv):
            spec.uncertainty_fi.append("Kohdepiirteet perustuvat lähdekappaleiden mittauksiin tai yksittäisiin havaintoihin, eivät toistuvasti tuettuihin yhteyksiin.")
        if any(h.basis == "heuristic" for h in spec.genre_hypotheses):
            spec.uncertainty_fi.append("Genre-ehdotukset ovat sääntöpohjaisia hypoteeseja mitatuista piirteistä – sovellus ei käytä genreluokitinta.")
        spec.uncertainty_fi.append("Suno ei välttämättä noudata tarkkaa tempoa, sävellajia tai taajuussisältöä; tulos kannattaa tuoda takaisin analysoitavaksi.")
        if self.profile.get("data_stage") in ("empty", "collecting"):
            spec.uncertainty_fi.append("Profiilissa on vielä vähän arvioita, joten henkilökohtaiset painotukset ovat alustavia.")


def build_variants(profile: dict[str, Any] | None, sources: list[TrackRecord], controls: PromptControls, objective: str | None, seed: str) -> list[PromptSpecification]:
    b = SpecBuilder(profile, sources, controls, objective, seed)
    return [b.deep_resonance(), b.intensification(objective), b.unknown_territory()]


def describe_targets_fi(spec: PromptSpecification) -> list[str]:
    return [f"{t.label}: {fmt_value(t.feature, t.target)} (±{t.tolerance:g})" for t in spec.target_features]
