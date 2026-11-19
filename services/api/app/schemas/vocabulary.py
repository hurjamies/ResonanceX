"""Shared vocabulary: experience dimensions, bodily responses, marker labels and
the audio feature registry used by Resonance Core and Prompt Studio.

User-facing labels are Finnish; identifiers are English.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Experience dimensions (0–10, all optional) -----------------------------
EXPERIENCE_DIMENSIONS: list[dict[str, str]] = [
    {"key": "preference", "label": "Yleinen mieltymys", "hint": "Kuinka paljon pidät kappaleesta"},
    {"key": "bodily_resonance", "label": "Kehollinen resonanssi", "hint": "Kuinka voimakkaasti tunnet musiikin kehossasi"},
    {"key": "movement", "label": "Halu liikkua", "hint": "Saako musiikki sinut liikkumaan"},
    {"key": "emotional_intensity", "label": "Tunteen voimakkuus", "hint": "Kuinka voimakas tunnereaktio on"},
    {"key": "immersion", "label": "Uppoutuminen", "hint": "Kuinka syvälle musiikki vie"},
    {"key": "power", "label": "Voiman tunne", "hint": ""},
    {"key": "calm", "label": "Rauhallisuus", "hint": ""},
    {"key": "melancholy", "label": "Melankolia", "hint": ""},
    {"key": "longing", "label": "Kaipaus", "hint": ""},
    {"key": "euphoria", "label": "Euforia", "hint": ""},
    {"key": "sensual", "label": "Aistillisuus / eroottinen tunnelma", "hint": ""},
    {"key": "mystery", "label": "Mystisyys", "hint": ""},
    {"key": "awe", "label": "Kunnioittava ihmetys", "hint": "Suuruuden tai ihmetyksen kokemus"},
    {"key": "transcendence", "label": "Koettu transsendenssi", "hint": "Oma kokemus itsensä ylittämisestä – subjektiivinen"},
    {"key": "significance", "label": "Henkilökohtainen merkitys", "hint": ""},
]
DIMENSION_KEYS = [d["key"] for d in EXPERIENCE_DIMENSIONS]
DIMENSION_LABELS = {d["key"]: d["label"] for d in EXPERIENCE_DIMENSIONS}

# --- Bodily responses (self-reported, not physiological measurements) -------
BODY_RESPONSES: list[dict[str, str]] = [
    {"key": "chills", "label": "Kylmät väreet / kananliha"},
    {"key": "chest", "label": "Tuntemus rintakehässä"},
    {"key": "vibration", "label": "Koettu värinä"},
    {"key": "tension", "label": "Lihasjännitys"},
    {"key": "release", "label": "Jännityksen laukeaminen"},
    {"key": "relaxation", "label": "Rentoutuminen"},
    {"key": "movement_impulse", "label": "Liikkeen impulssi"},
    {"key": "breathing", "label": "Koettu hengityksen muutos"},
    {"key": "alertness", "label": "Vireyden nousu"},
    {"key": "heaviness", "label": "Raskauden tunne"},
    {"key": "lightness", "label": "Keveyden tunne"},
]
BODY_KEYS = [b["key"] for b in BODY_RESPONSES]

# --- Free-form reflection prompts ------------------------------------------
REFLECTION_PROMPTS: list[dict[str, str]] = [
    {"key": "feel", "label": "Mitä tämä musiikki saa minut tuntemaan?"},
    {"key": "images", "label": "Mitä mielikuvia tai muistoja se herättää?"},
    {"key": "body", "label": "Mitä kehossani tapahtuu?"},
    {"key": "moment", "label": "Mikä hetki vaikuttaa minuun voimakkaimmin?"},
    {"key": "why", "label": "Miksi juuri tämä osa tuntuu erilaiselta?"},
]
REFLECTION_KEYS = [r["key"] for r in REFLECTION_PROMPTS]

# --- Listening context -------------------------------------------------------
CONTEXT_FIELDS: dict[str, list[dict[str, str]]] = {
    "playback": [
        {"key": "headphones", "label": "Kuulokkeet"},
        {"key": "speakers", "label": "Kaiuttimet"},
        {"key": "car", "label": "Auto"},
        {"key": "live", "label": "Livenä"},
    ],
    "volume": [
        {"key": "quiet", "label": "Hiljainen"},
        {"key": "moderate", "label": "Kohtalainen"},
        {"key": "loud", "label": "Kova"},
    ],
    "familiarity": [
        {"key": "first", "label": "Ensikuuntelu"},
        {"key": "some", "label": "Tuttu"},
        {"key": "very", "label": "Hyvin tuttu"},
    ],
    "environment": [
        {"key": "home", "label": "Koti"},
        {"key": "outdoors", "label": "Ulkona"},
        {"key": "transit", "label": "Liikkeellä"},
        {"key": "work", "label": "Työ"},
        {"key": "other", "label": "Muu"},
    ],
}

# --- Timeline marker labels --------------------------------------------------
MARKER_LABELS: list[dict[str, str]] = [
    {"key": "body_reaction", "label": "Voimakas kehollinen reaktio"},
    {"key": "chills", "label": "Kylmät väreet"},
    {"key": "emotional_peak", "label": "Tunnehuippu"},
    {"key": "favorite_rhythm", "label": "Lempirytmi"},
    {"key": "important_harmony", "label": "Tärkeä harmonia"},
    {"key": "unpleasant", "label": "Epämiellyttävä kohta"},
    {"key": "unexpected", "label": "Odottamaton vaikutus"},
    {"key": "symbolism", "label": "Henkilökohtainen symboliikka"},
]
MARKER_KEYS = [m["key"] for m in MARKER_LABELS]
POSITIVE_MARKERS = {"body_reaction", "chills", "emotional_peak", "favorite_rhythm", "important_harmony", "unexpected", "symbolism"}


# --- Audio feature registry --------------------------------------------------
@dataclass(frozen=True)
class FeatureDef:
    key: str
    label: str  # Finnish
    unit: str
    category: str  # "measured" | "estimated"
    group: str  # rhythm | spectral | tonality | dynamics | structure
    low_fi: str  # Finnish phrase for a low value
    high_fi: str  # Finnish phrase for a high value
    in_profile: bool = True
    log_scale: bool = False


FEATURES: list[FeatureDef] = [
    FeatureDef("tempo_bpm", "Tempo", "BPM", "estimated", "rhythm", "hitaampi tempo", "nopeampi tempo"),
    FeatureDef("pulse_clarity", "Pulssin selkeys", "0–1", "estimated", "rhythm", "epäselvä pulssi", "selkeä, vahva pulssi"),
    FeatureDef("rhythmic_regularity", "Rytminen säännöllisyys", "0–1", "estimated", "rhythm", "vapaa, joustava ajoitus", "tasainen, koneellinen ajoitus"),
    FeatureDef("onset_density", "Iskutiheys", "iskua/s", "measured", "rhythm", "harva rytmitys", "tiheä rytmitys"),
    FeatureDef("beat_strength", "Iskun voimakkuus", "suhde", "estimated", "rhythm", "pehmeät iskut", "korostuneet iskut"),
    FeatureDef("syncopation", "Synkopointi (arvio)", "0–1", "estimated", "rhythm", "suora rytmi", "synkopoitu rytmi"),
    FeatureDef("rhythmic_repetition", "Rytminen toisto", "0–1", "estimated", "rhythm", "vaihteleva rytmikuvio", "toistuva rytmikuvio"),
    FeatureDef("tempo_variation_bpm", "Tempon vaihtelu", "BPM", "estimated", "rhythm", "vakaa tempo", "vaihteleva tempo"),
    FeatureDef("sub_bass_ratio", "Sub-basson osuus", "osuus", "measured", "spectral", "vähän sub-bassoa", "paljon sub-bassoa"),
    FeatureDef("bass_ratio", "Basson osuus", "osuus", "measured", "spectral", "kevyt basso", "vahva basso"),
    FeatureDef("low_mid_ratio", "Alakeskiäänten osuus", "osuus", "measured", "spectral", "ohut alakeskialue", "täyteläinen alakeskialue"),
    FeatureDef("mid_ratio", "Keskiäänten osuus", "osuus", "measured", "spectral", "vetäytyvät keskiäänet", "korostuneet keskiäänet"),
    FeatureDef("treble_ratio", "Diskanttien osuus", "osuus", "measured", "spectral", "pehmeä yläpää", "kirkas yläpää"),
    FeatureDef("spectral_centroid_hz", "Spektrin kirkkaus (sentroidi)", "Hz", "measured", "spectral", "tumma, lämmin sointi", "kirkas sointi", log_scale=True),
    FeatureDef("spectral_flatness", "Spektrin tasaisuus", "0–1", "measured", "spectral", "sävyisä sointi", "kohinainen sointi", log_scale=True),
    FeatureDef("bass_modulation_strength", "Bassopulssin voimakkuus", "log-suhde", "measured", "spectral", "tasainen basso", "sykkivä basso"),
    FeatureDef("bass_modulation_depth", "Bassovaihtelun syvyys", "suhde", "measured", "spectral", "tasainen bassotaso", "voimakkaasti vaihteleva basso"),
    FeatureDef("major_mode", "Duuri (1) / molli (0)", "arvio", "estimated", "tonality", "molli", "duuri"),
    FeatureDef("key_confidence", "Sävellajin selkeys", "0–1", "estimated", "tonality", "monitulkintainen sävellaji", "selkeä sävelkeskus"),
    FeatureDef("harmonic_stability", "Harmoninen vakaus", "0–1", "estimated", "tonality", "liikkuva harmonia", "pysähtynyt, vakaa harmonia"),
    FeatureDef("chord_change_rate", "Sointuvaihdokset", "/min", "estimated", "tonality", "harvat sointuvaihdokset", "tiheät sointuvaihdokset"),
    FeatureDef("tonal_tension", "Tonaalinen jännite (proksi)", "0–1", "estimated", "tonality", "tonaalisesti vakaa", "tonaalisesti jännitteinen"),
    FeatureDef("loudness_lufs", "Äänekkyys", "LUFS", "measured", "dynamics", "hiljaisempi master", "äänekäs master"),
    FeatureDef("loudness_range_lu", "Äänekkyyden vaihteluväli", "LU", "measured", "dynamics", "tasainen dynamiikka", "laaja dynamiikka"),
    FeatureDef("crest_factor_db", "Huippukerroin", "dB", "measured", "dynamics", "tiivis, kompressoitu", "transienttinen, avoin"),
    FeatureDef("percussive_fraction", "Perkussiivisuus", "osuus", "estimated", "dynamics", "harmoninen, soiva", "perkussiivinen"),
    FeatureDef("stereo_width", "Stereoleveys", "S/M", "measured", "dynamics", "kapea stereokuva", "leveä stereokuva"),
    FeatureDef("silence_fraction", "Hiljaisuuden osuus", "osuus", "measured", "dynamics", "jatkuva äänimatto", "paljon hiljaisuutta", in_profile=False),
    FeatureDef("texture_density", "Tekstuurin tiheys", "0–1", "estimated", "dynamics", "harva tekstuuri", "tiheä, kerroksellinen tekstuuri"),
    FeatureDef("build_gradualness", "Nousun asteittaisuus", "−1–1", "estimated", "structure", "ei pitkää nousua", "asteittainen, pitkä nousu"),
    FeatureDef("peak_position", "Huipun sijainti", "0–1", "estimated", "structure", "huippu alussa", "huippu lopussa"),
    FeatureDef("crescendo_seconds", "Pisin crescendo", "s", "estimated", "structure", "lyhyet nousut", "pitkät crescendot"),
    FeatureDef("sudden_changes_per_min", "Äkilliset muutokset", "/min", "estimated", "structure", "tasainen kehitys", "äkilliset energiahypyt"),
    FeatureDef("structural_repetition", "Rakenteellinen toisto", "0–1", "estimated", "structure", "läpisävelletty", "toistuvat osat"),
    FeatureDef("duration_seconds", "Kesto", "s", "measured", "structure", "lyhyt", "pitkä", in_profile=False),
]
FEATURE_BY_KEY = {f.key: f for f in FEATURES}
PROFILE_FEATURES = [f.key for f in FEATURES if f.in_profile]

SEGMENT_ROLES_FI = {
    "intro": "Intro",
    "outro": "Outro",
    "climax": "Huipennus",
    "breakdown": "Breakdown",
    "drop": "Drop",
    "build": "Nousu",
    "repeated": "Toistuva osa",
    "section": "Osa",
}

ENERGY_ARC_FI = {
    "plateau": "Tasainen energia",
    "gradual_build": "Asteittainen nousu",
    "sudden_contrasts": "Äkilliset kontrastit",
    "early_peak": "Varhainen huippu",
    "waves": "Aaltoileva energia",
}
