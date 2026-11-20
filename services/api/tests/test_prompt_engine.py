"""Prompt engine: translation, provider compilation and stats helpers."""

from __future__ import annotations

from app.services.prompt_engine.builder import FEATURE_PHRASES, heuristic_genres, tempo_phrase
from app.services.prompt_engine.compilers import SUNO_STYLE_SOFT_LIMIT, compile_elevenlabs_plan, compile_suno
from app.services.prompt_engine.specification import GenreHypothesis, PromptSpecification, StructureSection, TargetFeature
from app.services.resonance_core.stats import benjamini_hochberg, spearman_with_permutation

import numpy as np


def test_tempo_phrase_translation():
    assert tempo_phrase(92.4, 0.8, 0.9, 0.95, False) == "mid-tempo hypnotic pulse around 92 BPM"
    assert tempo_phrase(70, 0.2, None, None, True) == "slow floating, loosely felt pulse around 70 BPM with a half-time feel"
    assert "fast" in tempo_phrase(174, 0.7, 0.9, 0.5, False)


def test_heuristic_genres_are_rule_based():
    dnb = heuristic_genres({"tempo_bpm": 174, "pulse_clarity": 0.8, "sub_bass_ratio": 0.2})
    assert dnb[0] == "drum and bass"
    ambient = heuristic_genres({"tempo_bpm": 70, "pulse_clarity": 0.1, "onset_density": 0.5, "percussive_fraction": 0.1})
    assert "ambient" in ambient
    assert heuristic_genres({}) == ["alternative electronic"]


def _spec(**kw) -> PromptSpecification:
    base = dict(
        mode="deep_resonance",
        rhythm_direction=["slow hypnotic pulse around 88 BPM"],
        texture_direction=["dark, warm tone"] + ["layered texture " * 8] * 2,
        bass_direction=["deep sub-bass"],
        harmonic_direction=["minor key"],
        energy_arc=["gradually evolving arrangement with a prolonged emotional crescendo"],
        genre_hypotheses=[GenreHypothesis(name="trip-hop", basis="heuristic")],
        structure=[StructureSection(tag="Intro", description="sparse", approx_seconds=20), StructureSection(tag="Outro", description="dissolve", approx_seconds=20)],
        negative_constraints=["harsh treble", "harsh treble", "busy drums"],
        target_features=[TargetFeature(feature="tempo_bpm", label="Tempo", target=88, tolerance=6)],
    )
    base.update(kw)
    return PromptSpecification(**base)


def test_suno_compiler_is_concise_and_deduplicated():
    out = compile_suno(_spec(texture_direction=["dark, warm tone"] + ["layered texture " * 12] * 2, bass_direction=["deep sub-bass", "rolling bass " * 10]), seed="s")
    assert len(out["style"]) <= SUNO_STYLE_SOFT_LIMIT + 40
    assert out["style_dropped"], "over-long descriptor lists must be trimmed, not concatenated"
    assert out["style"].endswith("instrumental")
    assert out["exclude"] == "harsh treble, busy drums"
    assert out["lyrics"].startswith("[Intro: sparse]")
    assert out["instrumental"] is True and out["tempo_hint"] == 88
    assert set(out["field_support"]) >= {"title", "style", "lyrics", "exclude"}
    # deterministic for the same seed
    assert compile_suno(_spec(), seed="s")["title"] == out["title"]


def test_unknown_territory_suggests_wild_model():
    out = compile_suno(_spec(mode="unknown_territory", extra={"suggest_wild_model": True, "experimentation": 8}), seed="s")
    assert out["settings"]["model"] == "v6-wild" and out["settings"]["weirdness"] > 50


def test_elevenlabs_plan_shape():
    plan = compile_elevenlabs_plan(_spec())
    assert plan["sections"][0]["section_name"] == "Intro" and plan["sections"][0]["duration_ms"] == 20000
    assert "instrumental" in plan["positive_global_styles"]
    assert plan["_status"] == "legacy-music_v1-offline-export"


def test_no_uninformative_phrases():
    # a low syncopation value must not produce filler such as "straight rhythm"
    assert FEATURE_PHRASES["syncopation"][0] == ""


def test_stats_helpers():
    x = np.arange(10, dtype=float)
    r = spearman_with_permutation(x, x * 2 + 1, n_perm=500, n_boot=200)
    assert abs(r["rho"] - 1.0) < 1e-9 and r["p"] < 0.01
    rng = np.random.default_rng(0)
    noise = spearman_with_permutation(rng.normal(size=10), rng.normal(size=10), n_perm=500, n_boot=200)
    assert noise["p"] > 0.05
    q = benjamini_hochberg([0.01, 0.04, 0.03, 0.5])
    assert q[0] <= q[2] <= q[1] <= q[3] and all(0 <= v <= 1 for v in q)
