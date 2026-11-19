"""Creation feedback loop: compare requested targets with measured results.

Objective feature alignment and subjective resonance are deliberately kept as
two separate evaluations.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models import AudioAnalysis, CreativeExperiment, ExperienceRating, GeneratedPrompt, MediaAsset, utcnow
from app.schemas.vocabulary import FEATURE_BY_KEY
from app.services.audio_analysis.engine import ALGORITHM_VERSION
from app.services.resonance_core.core import fmt_value
from app.services.resonance_core.dataset import AFFECT_DIMENSIONS

ARC_TARGETS = {
    "gradually evolving arrangement with a prolonged emotional crescendo": "gradual_build",
    "dramatic contrasts with sudden drops and surges": "sudden_contrasts",
    "steady, continuous trance-like energy": "plateau",
    "waves of tension and release": "waves",
    "opens at full intensity and slowly dissolves": "early_peak",
}


def compute_alignment(spec: dict[str, Any], analysis: AudioAnalysis) -> dict[str, Any]:
    feats = analysis.summary.get("features") or {}
    rows = []
    for t in spec.get("target_features", []):
        key = t["feature"]
        measured = feats.get(key)
        row: dict[str, Any] = {
            "feature": key,
            "label": t["label"],
            "target": t["target"],
            "tolerance": t["tolerance"],
            "measured": measured,
            "target_label": fmt_value(key, t["target"]),
            "measured_label": fmt_value(key, measured),
            "source": t.get("source"),
            "note": None,
        }
        if measured is None:
            row["status"] = "unmeasured"
        else:
            delta = measured - t["target"]
            row["delta"] = round(delta, 4)
            tol = t["tolerance"]
            if key == "major_mode":
                row["status"] = "match" if round(measured) == round(t["target"]) else "miss"
            elif abs(delta) <= tol:
                row["status"] = "match"
            elif abs(delta) <= 2 * tol:
                row["status"] = "near"
            else:
                row["status"] = "miss"
            if key == "tempo_bpm" and row["status"] != "match":
                for ratio in (2.0, 0.5):
                    if abs(measured * ratio - t["target"]) <= tol:
                        row["status"] = "metrical_equivalent"
                        row["note"] = f"Mitattu tempo vastaa kohdetta {'puoli' if ratio == 2.0 else 'tupla'}nopeudella tulkittuna."
        rows.append(row)
    # energy arc
    arc_target = next((ARC_TARGETS[a] for a in spec.get("energy_arc", []) if a in ARC_TARGETS), None)
    arc_measured = analysis.summary["structure"]["energy_arc"]["type"]
    arc = None
    if arc_target:
        arc = {"target": arc_target, "measured": arc_measured, "status": "match" if arc_target == arc_measured else "miss"}
    scored = [r for r in rows if r["status"] != "unmeasured"]
    matches = sum(1 for r in scored if r["status"] in ("match", "metrical_equivalent"))
    near = sum(1 for r in scored if r["status"] == "near")
    total = len(scored) + (1 if arc else 0)
    matches += 1 if arc and arc["status"] == "match" else 0
    return {
        "analysis_version": ALGORITHM_VERSION,
        "features": rows,
        "energy_arc": arc,
        "matches": matches,
        "near": near,
        "total": total,
        "score": round(matches / total, 3) if total else None,
    }


def refresh_experiment(session: Session, asset: MediaAsset) -> CreativeExperiment | None:
    if not asset.prompt_id:
        return None
    prompt = session.get(GeneratedPrompt, asset.prompt_id)
    analysis = session.exec(
        select(AudioAnalysis).where(AudioAnalysis.asset_id == asset.id, AudioAnalysis.algorithm_version == ALGORITHM_VERSION)
    ).first()
    if prompt is None or analysis is None:
        return None
    alignment = compute_alignment(prompt.specification, analysis)
    exp = session.exec(select(CreativeExperiment).where(CreativeExperiment.generated_asset_id == asset.id)).first()
    if exp is None:
        exp = CreativeExperiment(prompt_id=prompt.id, generated_asset_id=asset.id, alignment=alignment)
    else:
        exp.prompt_id = prompt.id
        exp.alignment = alignment
        exp.updated_at = utcnow()
    session.add(exp)
    session.commit()
    session.refresh(exp)
    return exp


def experiment_outcome(session: Session, exp: CreativeExperiment, profile: dict[str, Any] | None) -> dict[str, Any]:
    """Combine objective alignment with the (separate) subjective rating."""
    rating = session.exec(select(ExperienceRating).where(ExperienceRating.asset_id == exp.generated_asset_id)).first()
    dims = rating.dimensions if rating else {}
    affect = [dims.get(k) for k in AFFECT_DIMENSIONS if dims.get(k) is not None]
    resonance = sum(affect) / len(affect) if affect else None
    pref = dims.get("preference")
    lib_scores = []
    for p in (profile or {}).get("field", {}).get("points", []):
        if p["asset_id"] != exp.generated_asset_id and p.get("resonance_score") is not None:
            lib_scores.append(p["resonance_score"])
    lib_mean = sum(lib_scores) / len(lib_scores) if lib_scores else None
    align = exp.alignment.get("score")
    verdict = None
    verdict_fi = "Arvioi kokemuksesi, jotta tulosta voidaan tulkita."
    if resonance is not None and align is not None:
        strong = resonance >= 7 or (lib_mean is not None and resonance >= lib_mean + 1.5)
        weak = resonance <= 4 or (lib_mean is not None and resonance <= lib_mean - 1.5)
        if align >= 0.6 and strong:
            verdict, verdict_fi = "supports", "Tukee hypoteeseja: tavoitellut piirteet toteutuivat ja kokemus oli voimakas."
        elif align >= 0.6 and weak:
            verdict, verdict_fi = "challenges", "Haastaa hypoteeseja: piirteet toteutuivat, mutta kokemus jäi heikoksi – kohdepiirteet eivät yksin riitä."
        elif align < 0.4 and strong:
            verdict, verdict_fi = "surprise", "Odottamaton onnistuminen: tulos poikkesi tavoitteesta mutta vaikutti voimakkaasti. Poikkeavat piirteet voivat olla merkityksellisiä."
        elif align < 0.4 and weak:
            verdict, verdict_fi = "inconclusive", "Ei johtopäätöstä: Suno ei toteuttanut tavoitteita, joten kokemus ei kerro kohdepiirteistä."
        else:
            verdict, verdict_fi = "mixed", "Osittainen: tulos ja kokemus ovat välimaastossa."
    deviations = [
        {"feature": r["feature"], "label": FEATURE_BY_KEY[r["feature"]].label if r["feature"] in FEATURE_BY_KEY else r["label"], "delta": r.get("delta")}
        for r in exp.alignment.get("features", [])
        if r["status"] == "miss"
    ]
    return {
        "resonance_score": None if resonance is None else round(resonance, 2),
        "preference": pref,
        "library_mean_resonance": None if lib_mean is None else round(lib_mean, 2),
        "alignment_score": align,
        "verdict": verdict,
        "verdict_fi": verdict_fi,
        "deviations": deviations,
        "rated": rating is not None,
    }
