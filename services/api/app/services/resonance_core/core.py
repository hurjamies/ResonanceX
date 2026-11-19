"""Resonance Core – personal SonicDNA profile computation.

Principles (see docs/RESEARCH_METHODS.md):
* Structured measurements first; language only describes them.
* Every insight carries its evidence (tracks, values, n, statistics).
* Sparse data is reported honestly with explicit evidence levels:
  ``insufficient`` < ``observation`` < ``preliminary`` < ``supported``.
* Associations are never presented as causes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import numpy as np
import scipy.stats
from sqlmodel import Session, select

from app.models import SonicProfileSnapshot
from app.schemas.vocabulary import (
    DIMENSION_KEYS,
    DIMENSION_LABELS,
    FEATURE_BY_KEY,
    MARKER_LABELS,
    POSITIVE_MARKERS,
    PROFILE_FEATURES,
)
from app.services.audio_analysis.engine import ALGORITHM_VERSION
from app.services.resonance_core.dataset import AFFECT_DIMENSIONS, Dataset, TrackRecord, load_dataset, load_timeseries
from app.services.resonance_core.stats import (
    benjamini_hochberg,
    binomial_sign_p,
    cohens_d,
    robust_scale,
    spearman_with_permutation,
)

CORE_VERSION = "core-1.0.0"

EVIDENCE_ORDER = {"insufficient": 0, "observation": 1, "preliminary": 2, "supported": 3}
EVIDENCE_FI = {
    "insufficient": "Ei riittävästi näyttöä",
    "observation": "Havainto",
    "preliminary": "Alustava hypoteesi",
    "supported": "Toistuvasti tuettu",
}
MARKER_FI = {m["key"]: m["label"] for m in MARKER_LABELS}

# Absolute tolerances for "similar value" comparisons (others use library spread)
ABS_TOLERANCE = {"tempo_bpm": 8.0, "major_mode": 0.0}


def fmt_value(key: str, v: float | None) -> str:
    if v is None:
        return "–"
    f = FEATURE_BY_KEY.get(key)
    unit = f.unit if f else ""
    if key == "tempo_bpm":
        return f"{v:.0f} BPM"
    if key == "major_mode":
        return "duuri" if v >= 0.5 else "molli"
    if unit == "osuus":
        return f"{v * 100:.1f} %"
    if unit == "Hz":
        return f"{v:,.0f} Hz".replace(",", " ")
    if unit in ("LUFS", "LU", "dB"):
        return f"{v:.1f} {unit}"
    if unit == "s":
        return f"{v:.0f} s"
    if unit in ("/min", "iskua/s"):
        return f"{v:.2f} {unit}"
    return f"{v:.2f}"


def _level_from_assoc(rho: float, n: int, p: float, q: float, ci_lo: float, ci_hi: float) -> str:
    a = abs(rho)
    ci_ok = np.isfinite(ci_lo) and np.isfinite(ci_hi) and (ci_lo > 0 or ci_hi < 0)
    if n >= 8 and a >= 0.5 and q < 0.1 and ci_ok:
        return "supported"
    if n >= 5 and a >= 0.5 and p < 0.1:
        return "preliminary"
    if n >= 4 and a >= 0.6:
        return "observation"
    return "insufficient"


def _track_ref(t: TrackRecord, feature: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "asset_id": t.id,
        "title": t.asset.title,
        "artist": t.asset.artist,
        "origin": t.asset.origin,
        "resonance_score": None if t.resonance_score is None else round(t.resonance_score, 2),
        "preference": t.preference,
    }
    if feature:
        v = t.features.get(feature)
        ref["value"] = v
        ref["value_label"] = fmt_value(feature, v)
    if extra:
        ref.update(extra)
    return ref


class ProfileBuilder:
    def __init__(self, ds: Dataset):
        self.ds = ds
        self.tracks = ds.tracks
        self.now = datetime.now(timezone.utc).isoformat()
        self.insights: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    def feature_matrix(self, tracks: list[TrackRecord], key: str) -> np.ndarray:
        return np.array([np.nan if t.features.get(key) is None else float(t.features[key]) for t in tracks])

    def library_stats(self) -> dict[str, Any]:
        out = {}
        for key in PROFILE_FEATURES:
            v = self.feature_matrix(self.tracks, key)
            v = v[np.isfinite(v)]
            if len(v) == 0:
                continue
            out[key] = {
                "n": int(len(v)),
                "median": round(float(np.median(v)), 4),
                "p10": round(float(np.percentile(v, 10)), 4),
                "p25": round(float(np.percentile(v, 25)), 4),
                "p75": round(float(np.percentile(v, 75)), 4),
                "p90": round(float(np.percentile(v, 90)), 4),
                "min": round(float(v.min()), 4),
                "max": round(float(v.max()), 4),
            }
        return out

    def zscores(self) -> dict[int, dict[str, float]]:
        out: dict[int, dict[str, float]] = {t.id: {} for t in self.tracks}
        if len(self.tracks) < 3:
            return out
        for key in PROFILE_FEATURES:
            v = self.feature_matrix(self.tracks, key)
            ok = np.isfinite(v)
            if ok.sum() < 3:
                continue
            med, spread = robust_scale(v[ok])
            for t, val, good in zip(self.tracks, v, ok):
                if good:
                    out[t.id][key] = float(np.clip((val - med) / spread, -4, 4))
        return out

    # ------------------------------------------------------------------
    def groups(self) -> dict[str, Any]:
        scored = [t for t in self.tracks if t.resonance_score is not None]
        basis = "resonance"
        if len(scored) < 3:
            pref = [t for t in self.tracks if t.preference is not None]
            if len(pref) > len(scored):
                scored, basis = pref, "preference"

        def score(t: TrackRecord) -> float:
            return float(t.resonance_score if basis == "resonance" else t.preference)  # type: ignore[arg-type]

        top: list[TrackRecord] = []
        bottom: list[TrackRecord] = []
        if len(scored) >= 3:
            ordered = sorted(scored, key=score, reverse=True)
            k = max(2, round(len(ordered) / 3))
            top = [t for t in ordered[:k] if score(t) >= 5.0]
            bottom = [t for t in ordered[-k:] if score(t) <= 5.0 and t not in top]
        disliked = [t for t in self.tracks if t.preference is not None and t.preference <= 3]
        return {"basis": basis, "scored": scored, "top": top, "bottom": bottom, "disliked": disliked, "score": score}

    # ------------------------------------------------------------------
    def associations(self) -> list[dict[str, Any]]:
        tests: list[dict[str, Any]] = []
        dims = ["resonance_score"] + DIMENSION_KEYS
        for dim in dims:
            if dim == "resonance_score":
                rated = [t for t in self.tracks if t.resonance_score is not None]
                ys = np.array([t.resonance_score for t in rated], dtype=float)
            else:
                rated = [t for t in self.tracks if t.dim(dim) is not None]
                ys = np.array([t.dim(dim) for t in rated], dtype=float)
            if len(rated) < 4 or np.std(ys) == 0:
                continue
            for key in PROFILE_FEATURES:
                xs = self.feature_matrix(rated, key)
                ok = np.isfinite(xs)
                if ok.sum() < 4 or np.std(xs[ok]) == 0:
                    continue
                r = spearman_with_permutation(xs[ok], ys[ok], n_perm=1000, n_boot=400)
                if r["rho"] is None:
                    continue
                tests.append({"dimension": dim, "feature": key, **r})
        q = benjamini_hochberg([t["p"] for t in tests])
        out = []
        for t, qv in zip(tests, q):
            level = _level_from_assoc(t["rho"], t["n"], t["p"], qv, t["ci_low"], t["ci_high"])
            out.append(
                {
                    "dimension": t["dimension"],
                    "dimension_label": "Resonanssipistemäärä" if t["dimension"] == "resonance_score" else DIMENSION_LABELS[t["dimension"]],
                    "feature": t["feature"],
                    "feature_label": FEATURE_BY_KEY[t["feature"]].label,
                    "rho": round(t["rho"], 3),
                    "n": t["n"],
                    "p_permutation": round(t["p"], 4),
                    "q_fdr": round(qv, 4),
                    "ci_low": None if not np.isfinite(t["ci_low"]) else round(t["ci_low"], 3),
                    "ci_high": None if not np.isfinite(t["ci_high"]) else round(t["ci_high"], 3),
                    "evidence_level": level,
                    "tests_total": len(tests),
                }
            )
        out.sort(key=lambda a: (EVIDENCE_ORDER[a["evidence_level"]], abs(a["rho"])), reverse=True)
        return out

    # ------------------------------------------------------------------
    def consistency_insights(self, g: dict[str, Any], lib: dict[str, Any]) -> list[dict[str, Any]]:
        top, scored = g["top"], g["scored"]
        rest = [t for t in scored if t not in top]
        if len(top) < 3:
            return []
        found = []
        for key in PROFILE_FEATURES:
            if key not in lib:
                continue
            vt = self.feature_matrix(top, key)
            if np.isfinite(vt).sum() < 3:
                continue
            spread = lib[key]["p90"] - lib[key]["p10"]
            tol = ABS_TOLERANCE.get(key, 0.2 * spread if spread > 0 else 0.0)
            if tol <= 0 and key != "major_mode":
                continue
            med = float(np.nanmedian(vt))
            if key == "major_mode":
                med = 1.0 if med >= 0.5 else 0.0
            inside_top = [t for t in top if t.features.get(key) is not None and abs(t.features[key] - med) <= tol]
            share = len(inside_top) / len(top)
            if len(inside_top) < 3 or share < 0.6:
                continue
            inside_rest = [t for t in rest if t.features.get(key) is not None and abs(t.features[key] - med) <= tol]
            rest_share = len(inside_rest) / len(rest) if rest else None
            if rest_share is not None and share - rest_share < 0.3:
                continue  # not distinctive: the rest of the library is similar
            if rest_share is None:
                level = "observation"
            else:
                p = binomial_sign_p(len(inside_top), len(top)) if rest_share <= 0.5 else 1.0
                level = "preliminary" if (len(top) >= 5 and share - rest_share >= 0.4) else "observation"
                if len(top) >= 8 and share - rest_share >= 0.4 and p < 0.05 and len(rest) >= 5:
                    level = "supported"
            lo, hi = med - tol, med + tol
            fdef = FEATURE_BY_KEY[key]
            if key == "major_mode":
                range_txt = fmt_value(key, med)
            else:
                range_txt = f"{fmt_value(key, max(lo, lib[key]['min']))} – {fmt_value(key, min(hi, lib[key]['max']))}"
            side = fdef.high_fi if med >= lib[key]["median"] else fdef.low_fi
            outside_top = [t for t in top if t not in inside_top]
            explanation = (
                f"{len(inside_top)}/{len(top)} voimakkaimmin vaikuttaneesta kappaleestasi sijoittuu samalle alueelle "
                f"({fdef.label.lower()}: {range_txt})."
            )
            if rest_share is not None:
                explanation += f" Muista arvioiduista kappaleistasi samalle alueelle osuu {len(inside_rest)}/{len(rest)}."
            else:
                explanation += " Vertailuryhmää heikommin vaikuttaneista kappaleista ei vielä ole."
            found.append(
                {
                    "id": f"consistency:{key}",
                    "kind": "consistency",
                    "feature": key,
                    "title": f"Toistuva piirre: {side}",
                    "explanation": explanation,
                    "evidence_level": level,
                    "evidence": {
                        "top_share": round(share, 3),
                        "rest_share": None if rest_share is None else round(rest_share, 3),
                        "n_top": len(top),
                        "n_rest": len(rest),
                        "range": [round(lo, 4), round(hi, 4)],
                        "group_basis": g["basis"],
                    },
                    "supporting_tracks": [_track_ref(t, key) for t in inside_top],
                    "contrasting_tracks": [_track_ref(t, key, {"role": "top_outside"}) for t in outside_top]
                    + [_track_ref(t, key, {"role": "rest_inside"}) for t in inside_rest],
                    "suggested_experiment": self._experiment_for_feature(key, med, tol),
                    "_strength": share - (rest_share or 0.5),
                }
            )
        found.sort(key=lambda i: (EVIDENCE_ORDER[i["evidence_level"]], i["_strength"]), reverse=True)
        return found[:6]

    def _experiment_for_feature(self, key: str, med: float, tol: float) -> str:
        fdef = FEATURE_BY_KEY[key]
        others = [t for t in self.tracks if t.features.get(key) is not None and abs(t.features[key] - med) > 2 * tol]
        if others:
            o = others[0]
            return (
                f"Kuuntele ja arvioi kappale, joka poikkeaa tästä piirteestä ({o.asset.title}: {fmt_value(key, o.features.get(key))}), "
                f"ja vertaa sitä pareittain johonkin voimakkaimmista kappaleistasi."
            )
        return f"Tuo kirjastoon kappale, jossa {fdef.label.lower()} on selvästi erilainen, ja arvioi kokemuksesi."

    # ------------------------------------------------------------------
    def association_insights(self, assocs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        seen_features: set[str] = set()
        by_id = self.ds.by_id()
        # features that co-vary strongly across the library cannot be told apart;
        # they are grouped into a single insight instead of repeated as separate findings
        chosen: dict[tuple[str, str], dict[str, Any]] = {}

        def collinear(f1: str, f2: str) -> float | None:
            x, y = self.feature_matrix(self.tracks, f1), self.feature_matrix(self.tracks, f2)
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() < 4 or np.std(x[ok]) == 0 or np.std(y[ok]) == 0:
                return None
            return float(scipy.stats.spearmanr(x[ok], y[ok]).statistic)

        for a in assocs:
            if a["evidence_level"] == "insufficient":
                continue
            if a["feature"] in seen_features and a["dimension"] == "resonance_score":
                continue
            grouped = False
            for (dim, feat), ins in chosen.items():
                if dim != a["dimension"]:
                    continue
                r = collinear(feat, a["feature"])
                if r is not None and abs(r) >= 0.8:
                    ins["evidence"].setdefault("covarying_features", []).append(
                        {"feature": a["feature"], "label": FEATURE_BY_KEY[a["feature"]].label, "r_with_main": round(r, 3), "rho": a["rho"]}
                    )
                    grouped = True
                    break
            if grouped:
                continue
            fdef = FEATURE_BY_KEY[a["feature"]]
            side = fdef.high_fi if a["rho"] > 0 else fdef.low_fi
            dim_label = a["dimension_label"]
            if a["dimension"] == "resonance_score":
                dim_text = "Resonanssipistemääräsi (kehollinen resonanssi, tunteen voimakkuus, uppoutuminen ja merkitys)"
            else:
                dim_text = f"Arviosi kohdassa ”{dim_label}”"
            explanation = (
                f"{dim_text} on ollut korkeampi kappaleissa, joissa on {side} "
                f"(Spearman ρ = {a['rho']:+.2f}, n = {a['n']}, permutaatio-p = {a['p_permutation']:.3f}). "
                "Tämä on tilastollinen yhteys, ei osoitus syy-yhteydestä."
            )
            # supporting tracks: the highest-rated tracks with their values
            rated = []
            for t in self.tracks:
                y = t.resonance_score if a["dimension"] == "resonance_score" else t.dim(a["dimension"])
                if y is not None and t.features.get(a["feature"]) is not None:
                    rated.append((y, t))
            rated.sort(key=lambda x: x[0], reverse=True)
            out.append(
                {
                    "id": f"association:{a['dimension']}:{a['feature']}",
                    "kind": "association",
                    "feature": a["feature"],
                    "dimension": a["dimension"],
                    "title": f"{dim_label}: yhteys piirteeseen {fdef.label.lower()}",
                    "explanation": explanation,
                    "evidence_level": a["evidence_level"],
                    "evidence": {k: a[k] for k in ("rho", "n", "p_permutation", "q_fdr", "ci_low", "ci_high", "tests_total")},
                    "supporting_tracks": [_track_ref(t, a["feature"], {"rating": y}) for y, t in rated[:4]],
                    "contrasting_tracks": [_track_ref(t, a["feature"], {"rating": y}) for y, t in rated[-3:]] if len(rated) > 4 else [],
                    "suggested_experiment": "Vertaa kahta kappaletta, jotka ovat muuten samankaltaisia mutta eroavat tässä piirteessä.",
                }
            )
            chosen[(a["dimension"], a["feature"])] = out[-1]
            seen_features.add(a["feature"])
            if len(out) >= 6:
                break
        for ins in out:
            cov = ins["evidence"].get("covarying_features")
            if cov:
                names = ", ".join(c["label"].lower() for c in cov[:4])
                ins["explanation"] += (
                    f" Samaan suuntaan vaihtelevat kirjastossasi myös: {names} – näitä piirteitä ei voi vielä erottaa toisistaan."
                )
                ins["suggested_experiment"] = "Vertaa kappaleita, joissa nämä piirteet eivät kulje yhdessä – vasta silloin voidaan arvioida, mikä niistä on olennainen."
        _ = by_id
        return out

    # ------------------------------------------------------------------
    def divergence_insight(self) -> list[dict[str, Any]]:
        """Enjoyment and intensity are distinct: find tracks where they diverge."""
        both = [t for t in self.tracks if t.preference is not None and t.resonance_score is not None]
        if len(both) < 3:
            return []
        liked_not_moving = [t for t in both if t.preference >= 7 and t.resonance_score <= 4.5]
        moving_not_liked = [t for t in both if t.resonance_score >= 7 and t.preference <= 5]
        if not liked_not_moving and not moving_not_liked:
            return []
        prefs = np.array([t.preference for t in both])
        res = np.array([t.resonance_score for t in both])
        rho = float(np.corrcoef(np.argsort(np.argsort(prefs)), np.argsort(np.argsort(res)))[0, 1]) if np.std(prefs) and np.std(res) else None
        parts = []
        if liked_not_moving:
            parts.append(f"{len(liked_not_moving)} kappaletta, joista pidät mutta jotka eivät vaikuta voimakkaasti")
        if moving_not_liked:
            parts.append(f"{len(moving_not_liked)} kappaletta, jotka vaikuttavat voimakkaasti vaikka mieltymys on maltillinen")
        return [
            {
                "id": "divergence:preference_vs_resonance",
                "kind": "divergence",
                "title": "Mieltymys ja vaikuttavuus eroavat",
                "explanation": "Arvioissasi on " + " ja ".join(parts) + ". Nautinto ja kokemuksen voimakkuus käsitellään siksi erillisinä ulottuvuuksina."
                + (f" Niiden järjestyskorrelaatio on {rho:+.2f} (n = {len(both)})." if rho is not None else ""),
                "evidence_level": "observation",
                "evidence": {"n": len(both), "rank_correlation": None if rho is None else round(rho, 3)},
                "supporting_tracks": [_track_ref(t, extra={"role": "liked_not_moving"}) for t in liked_not_moving]
                + [_track_ref(t, extra={"role": "moving_not_liked"}) for t in moving_not_liked],
                "contrasting_tracks": [],
                "suggested_experiment": "Vertaa pareittain kappaletta, josta pidät, ja kappaletta, joka vaikuttaa voimakkaammin – vastaa kumpaankin kysymykseen erikseen.",
            }
        ]

    # ------------------------------------------------------------------
    def negative_insights(self, g: dict[str, Any], z: dict[int, dict[str, float]], lib: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        disliked = g["disliked"]
        if len(disliked) < 2 or len(self.tracks) < 4:
            return [], []
        tendencies = []
        for key in PROFILE_FEATURES:
            zs = [z[t.id].get(key) for t in disliked if key in z[t.id]]
            if len(zs) < 2:
                continue
            high = sum(1 for v in zs if v >= 0.8)
            low = sum(1 for v in zs if v <= -0.8)
            for count, direction in ((high, "high"), (low, "low")):
                if count >= max(2, int(np.ceil(len(zs) * 2 / 3))):
                    tendencies.append({"feature": key, "direction": direction, "count": count, "n": len(zs)})
        tendencies.sort(key=lambda t: t["count"] / t["n"], reverse=True)
        insights = []
        for tnd in tendencies[:3]:
            fdef = FEATURE_BY_KEY[tnd["feature"]]
            side = fdef.high_fi if tnd["direction"] == "high" else fdef.low_fi
            insights.append(
                {
                    "id": f"negative:{tnd['feature']}:{tnd['direction']}",
                    "kind": "negative",
                    "feature": tnd["feature"],
                    "title": f"Vähemmän mieluisissa: {side}",
                    "explanation": f"{tnd['count']}/{tnd['n']} kappaleesta, joille annoit matalan mieltymyksen (≤ 3), poikkeaa kirjastosi mediaanista suuntaan: {side}.",
                    "evidence_level": "observation" if tnd["n"] < 5 else "preliminary",
                    "evidence": tnd,
                    "supporting_tracks": [_track_ref(t, tnd["feature"]) for t in disliked],
                    "contrasting_tracks": [],
                    "suggested_experiment": "Tämä piirre voidaan lisätä Suno-kehotteen Exclude-kenttään kokeellisesti.",
                }
            )
        return insights, tendencies

    # ------------------------------------------------------------------
    def marker_analysis(self) -> dict[str, Any]:
        """Where do positive moment markers fall, compared with each track's own baseline?"""
        rows = []
        for t in self.tracks:
            pos = [m for m in t.markers if m.label in POSITIVE_MARKERS]
            if not pos:
                continue
            ts = load_timeseries(t.analysis)
            if not ts:
                continue
            dt = ts["dt"]
            env = np.array([np.nan if v is None else v for v in ts["energy_env_db"]], dtype=float)
            bass = np.array(
                [
                    np.nan if (a is None or b is None) else 10 * np.log10(10 ** (a / 10) + 10 ** (b / 10))
                    for a, b in zip(ts["bands"]["sub_bass"], ts["bands"]["bass"])
                ]
            )
            cent = np.array([np.nan if v is None else v for v in ts["centroid_hz"]], dtype=float)
            lag = int(8 / dt)
            if len(env) <= lag + 2:
                continue
            rise = np.full_like(env, np.nan)
            rise[lag:] = env[lag:] - env[:-lag]
            bounds = [s["start"] for s in t.analysis.segments[1:]]
            dur = t.asset.duration_seconds or len(env) * dt
            near_cover = 0.0
            if bounds:
                grid = np.arange(0, dur, 0.25)
                near_cover = float(np.mean([min(abs(g - b) for b in bounds) <= 3.0 for g in grid]))
            for m in pos:
                i = int(min(len(env) - 1, max(0, m.start_seconds / dt)))

                def pct(arr: np.ndarray, idx: int) -> float | None:
                    a = arr[np.isfinite(arr)]
                    if not np.isfinite(arr[idx]) or len(a) < 10:
                        return None
                    return float(np.mean(a < arr[idx]))

                rows.append(
                    {
                        "asset_id": t.id,
                        "title": t.asset.title,
                        "marker_id": m.id,
                        "label": m.label,
                        "time": m.start_seconds,
                        "energy_pct": pct(env, i),
                        "rise_pct": pct(rise, i),
                        "bass_pct": pct(bass, i),
                        "brightness_pct": pct(cent, i),
                        "near_boundary": bool(bounds) and min(abs(m.start_seconds - b) for b in bounds) <= 3.0,
                        "boundary_baseline": near_cover,
                    }
                )
        summary: dict[str, Any] = {"n_markers": len(rows), "n_tracks": len({r["asset_id"] for r in rows}), "rows": rows, "findings": []}
        if len(rows) < 3:
            return summary
        labels = {
            "energy_pct": ("energiataso", "korkean energian hetkiin", "matalan energian hetkiin"),
            "rise_pct": ("energian nousu edeltävään 8 sekuntiin", "energian nousuun", "energian laskuun"),
            "bass_pct": ("bassotaso", "bassovoimakkaisiin hetkiin", "bassoltaan kevyisiin hetkiin"),
            "brightness_pct": ("kirkkaus", "kirkkaisiin hetkiin", "tummiin hetkiin"),
        }
        for key, (name, hi_txt, lo_txt) in labels.items():
            vals = [r[key] for r in rows if r[key] is not None]
            if len(vals) < 3:
                continue
            mean = float(np.mean(vals))
            above = sum(1 for v in vals if v > 0.5)
            p_hi = binomial_sign_p(above, len(vals))
            p_lo = binomial_sign_p(len(vals) - above, len(vals))
            if mean >= 0.65 or mean <= 0.35:
                hi = mean >= 0.5
                p = p_hi if hi else p_lo
                level = "preliminary" if (len(vals) >= 6 and summary["n_tracks"] >= 2 and p < 0.05) else "observation"
                if len(vals) >= 12 and summary["n_tracks"] >= 4 and p < 0.01:
                    level = "supported"
                summary["findings"].append(
                    {
                        "metric": key,
                        "title": f"Merkityt hetket osuvat {hi_txt if hi else lo_txt}",
                        "explanation": f"Positiiviset hetkimerkintäsi sijoittuvat kappaleen oman jakauman {mean * 100:.0f}. persentiiliin ({name}); sattuman odotusarvo on 50. "
                        f"{above if hi else len(vals) - above}/{len(vals)} merkintää on mediaanin {'yläpuolella' if hi else 'alapuolella'} (binomi-p = {p:.3f}).",
                        "mean_percentile": round(mean, 3),
                        "n": len(vals),
                        "p": round(p, 4),
                        "evidence_level": level,
                    }
                )
        nb = [r for r in rows if r["boundary_baseline"] > 0]
        if len(nb) >= 3:
            obs = sum(r["near_boundary"] for r in nb) / len(nb)
            base = float(np.mean([r["boundary_baseline"] for r in nb]))
            if obs - base >= 0.25:
                summary["findings"].append(
                    {
                        "metric": "near_boundary",
                        "title": "Merkityt hetket osuvat rakenteellisiin muutoksiin",
                        "explanation": f"{sum(r['near_boundary'] for r in nb)}/{len(nb)} merkinnästä on 3 sekunnin sisällä havaitusta osanvaihdosta, kun sattumalta odotettu osuus olisi noin {base * 100:.0f} %.",
                        "observed_share": round(obs, 3),
                        "baseline_share": round(base, 3),
                        "n": len(nb),
                        "evidence_level": "preliminary" if len(nb) >= 6 and summary["n_tracks"] >= 2 else "observation",
                    }
                )
        return summary

    def marker_insights(self, ma: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        for f in ma["findings"]:
            rows = ma["rows"]
            out.append(
                {
                    "id": f"markers:{f['metric']}",
                    "kind": "markers",
                    "title": f["title"],
                    "explanation": f["explanation"],
                    "evidence_level": f["evidence_level"],
                    "evidence": {k: v for k, v in f.items() if k not in ("title", "explanation", "evidence_level")},
                    "supporting_tracks": [],
                    "timestamps": [
                        {"asset_id": r["asset_id"], "title": r["title"], "time": r["time"], "label": MARKER_FI.get(r["label"], r["label"])}
                        for r in rows[:12]
                    ],
                    "contrasting_tracks": [],
                    "suggested_experiment": "Merkitse hetkiä useampaan kappaleeseen, jotta havainto voidaan erottaa sattumasta.",
                }
            )
        return out

    # ------------------------------------------------------------------
    def pairwise_analysis(self) -> dict[str, Any]:
        by_id = self.ds.by_id()
        out: dict[str, Any] = {"n": 0, "n_stronger": 0, "n_enjoyed": 0, "agreement": None, "features": []}
        comps = [c for c in self.ds.comparisons if c.asset_a_id in by_id and c.asset_b_id in by_id]
        out["n"] = len(comps)
        decisive = [c for c in comps if c.stronger in ("a", "b")]
        out["n_stronger"] = len(decisive)
        enjoyed = [c for c in comps if c.enjoyed in ("a", "b")]
        out["n_enjoyed"] = len(enjoyed)
        both = [c for c in comps if c.stronger in ("a", "b") and c.enjoyed in ("a", "b")]
        if both:
            out["agreement"] = round(sum(c.stronger == c.enjoyed for c in both) / len(both), 3)
        if len(decisive) < 4:
            return out
        for key in PROFILE_FEATURES:
            diffs = []
            for c in decisive:
                s, w = (by_id[c.asset_a_id], by_id[c.asset_b_id]) if c.stronger == "a" else (by_id[c.asset_b_id], by_id[c.asset_a_id])
                vs, vw = s.features.get(key), w.features.get(key)
                if vs is None or vw is None or vs == vw:
                    continue
                diffs.append(vs - vw)
            if len(diffs) < 4:
                continue
            pos = sum(d > 0 for d in diffs)
            n = len(diffs)
            share = max(pos, n - pos) / n
            if share >= 0.8:
                p = binomial_sign_p(max(pos, n - pos), n)
                out["features"].append(
                    {
                        "feature": key,
                        "label": FEATURE_BY_KEY[key].label,
                        "direction": "higher" if pos > n - pos else "lower",
                        "consistent": max(pos, n - pos),
                        "n": n,
                        "p": round(p, 4),
                        "evidence_level": "preliminary" if (n >= 6 and p < 0.05) else "observation",
                    }
                )
        out["features"].sort(key=lambda f: f["p"])
        return out

    def pairwise_insights(self, pw: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        for f in pw["features"][:3]:
            fdef = FEATURE_BY_KEY[f["feature"]]
            side = fdef.high_fi if f["direction"] == "higher" else fdef.low_fi
            out.append(
                {
                    "id": f"pairwise:{f['feature']}",
                    "kind": "pairwise",
                    "feature": f["feature"],
                    "title": f"Pareittaisvertailut: {side}",
                    "explanation": f"Kun vertasit kahta kappaletta, voimakkaammin vaikuttanut oli {f['consistent']}/{f['n']} kertaa se, jossa on {side} (merkkitesti p = {f['p']:.3f}).",
                    "evidence_level": f["evidence_level"],
                    "evidence": f,
                    "supporting_tracks": [],
                    "contrasting_tracks": [],
                    "suggested_experiment": "Jatka vertailuja kappalepareilla, joissa tämä piirre vaihtelee mutta muut pysyvät samankaltaisina.",
                }
            )
        if pw.get("agreement") is not None and pw["n_stronger"] >= 4 and pw["agreement"] < 0.75:
            out.append(
                {
                    "id": "pairwise:agreement",
                    "kind": "pairwise",
                    "title": "Voimakkain ei aina ole mieluisin",
                    "explanation": f"Vertailuissa voimakkaammin vaikuttanut kappale oli myös mieluisampi vain {pw['agreement'] * 100:.0f} % tapauksista.",
                    "evidence_level": "observation",
                    "evidence": {"agreement": pw["agreement"], "n": pw["n_stronger"]},
                    "supporting_tracks": [],
                    "contrasting_tracks": [],
                    "suggested_experiment": "",
                }
            )
        return out

    # ------------------------------------------------------------------
    def targets(self, g: dict[str, Any], lib: dict[str, Any], z: dict[int, dict[str, float]], assocs: list[dict[str, Any]], consistency: list[dict[str, Any]]) -> dict[str, Any]:
        top = g["top"]
        if len(top) < 2:
            return {"basis": "none", "group_basis": g["basis"], "tracks": [], "features": []}
        assoc_by_feature: dict[str, dict[str, Any]] = {}
        for a in assocs:
            if a["dimension"] in ("resonance_score", *AFFECT_DIMENSIONS):
                cur = assoc_by_feature.get(a["feature"])
                if cur is None or EVIDENCE_ORDER[a["evidence_level"]] > EVIDENCE_ORDER[cur["evidence_level"]]:
                    assoc_by_feature[a["feature"]] = a
        cons_by_feature = {c["feature"]: c for c in consistency}
        feats = []
        for key in PROFILE_FEATURES:
            vt = self.feature_matrix(top, key)
            vt = vt[np.isfinite(vt)]
            if len(vt) < 2 or key not in lib:
                continue
            zt = [z[t.id][key] for t in top if key in z.get(t.id, {})]
            z_med = float(np.median(zt)) if zt else 0.0
            a = assoc_by_feature.get(key)
            c = cons_by_feature.get(key)
            level = "observation" if len(top) >= 2 else "insufficient"
            for src in (a, c):
                if src and EVIDENCE_ORDER[src["evidence_level"]] > EVIDENCE_ORDER[level]:
                    level = src["evidence_level"]
            # direction agreement check: association sign must agree with the top-group deviation
            if a and a["evidence_level"] != "insufficient" and np.sign(a["rho"]) != np.sign(z_med) and abs(z_med) > 0.3:
                level = "observation"
            feats.append(
                {
                    "feature": key,
                    "label": FEATURE_BY_KEY[key].label,
                    "median": round(float(np.median(vt)), 4),
                    "p25": round(float(np.percentile(vt, 25)), 4),
                    "p75": round(float(np.percentile(vt, 75)), 4),
                    "library_median": lib[key]["median"],
                    "z": round(z_med, 3),
                    "direction": "high" if z_med > 0.3 else ("low" if z_med < -0.3 else "typical"),
                    "evidence_level": level,
                    "rho": None if not a else a["rho"],
                    "n": len(vt),
                    "value_label": fmt_value(key, float(np.median(vt))),
                }
            )
        feats.sort(key=lambda f: (EVIDENCE_ORDER[f["evidence_level"]], abs(f["z"])), reverse=True)
        return {
            "basis": "strongest_responses",
            "group_basis": g["basis"],
            "tracks": [_track_ref(t) for t in top],
            "features": feats,
        }

    # ------------------------------------------------------------------
    def hypotheses_and_experiments(
        self, g: dict[str, Any], assocs: list[dict[str, Any]], z: dict[int, dict[str, float]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        hyps: list[dict[str, Any]] = []
        exps: list[dict[str, Any]] = []
        scored = g["scored"]
        # 1) Confounded features → pairwise experiment
        strong = [a for a in assocs if a["dimension"] in ("resonance_score", "bodily_resonance", "preference") and a["evidence_level"] != "insufficient"]
        done_pairs: set[tuple[str, str]] = set()
        rated = [t for t in self.tracks if t.resonance_score is not None or t.preference is not None]
        for a in strong[:5]:
            fa = a["feature"]
            xa = self.feature_matrix(rated, fa)
            for fb in PROFILE_FEATURES:
                if fb == fa or (fb, fa) in done_pairs:
                    continue
                xb = self.feature_matrix(rated, fb)
                ok = np.isfinite(xa) & np.isfinite(xb)
                if ok.sum() < 4 or np.std(xa[ok]) == 0 or np.std(xb[ok]) == 0:
                    continue
                r = float(np.corrcoef(xa[ok], xb[ok])[0, 1])
                if abs(r) < 0.7:
                    continue
                done_pairs.add((fa, fb))
                la, lb = FEATURE_BY_KEY[fa].label.lower(), FEATURE_BY_KEY[fb].label.lower()
                hyp = {
                    "id": f"confound:{fa}:{fb}",
                    "statement": f"Onko ratkaiseva piirre {la} vai {lb}? Arvioiduissa kappaleissasi ne vaihtelevat yhdessä (r = {r:+.2f}), joten niiden vaikutusta ei vielä voi erottaa.",
                    "status": "open",
                    "basis": {"feature_a": fa, "feature_b": fb, "r": round(r, 3), "n": int(ok.sum())},
                }
                hyps.append(hyp)
                pair = self._find_contrast_pair(fa, fb, z)
                if pair:
                    t1, t2 = pair
                    exps.append(
                        {
                            "kind": "pairwise",
                            "title": f"Erota {la} ja {lb}",
                            "description": f"Vertaa kappaleita, joissa {la} on samankaltainen mutta {lb} eroaa: {t1.asset.title} ({fmt_value(fb, t1.features.get(fb))}) ja {t2.asset.title} ({fmt_value(fb, t2.features.get(fb))}).",
                            "asset_ids": [t1.id, t2.id],
                            "hypothesis_id": hyp["id"],
                        }
                    )
                else:
                    exps.append(
                        {
                            "kind": "upload",
                            "title": f"Etsi kappale, joka erottaa piirteet {la} ja {lb}",
                            "description": f"Kirjastossasi ei ole kappaleparia, jossa {la} pysyisi samana ja {lb} muuttuisi. Tuo sellainen kappale ja arvioi se.",
                            "asset_ids": [],
                            "hypothesis_id": hyp["id"],
                        }
                    )
                if len(hyps) >= 3:
                    break
            if len(hyps) >= 3:
                break
        # 2) Open questions from untested features
        if scored and len(scored) < 8:
            hyps.append(
                {
                    "id": "data:more_ratings",
                    "statement": "Profiili perustuu vielä pieneen määrään arvioita; useimmat yhteydet ovat avoimia kysymyksiä.",
                    "status": "open",
                    "basis": {"rated": len(scored)},
                }
            )
        # 3) Rate unrated tracks
        unrated = [t for t in self.tracks if not t.is_rated]
        if unrated:
            exps.append(
                {
                    "kind": "rate",
                    "title": f"Arvioi {min(len(unrated), 5)} arvioimatonta kappaletta",
                    "description": "Jokainen arvio – myös neutraali tai negatiivinen – auttaa erottamaan, mitkä piirteet liittyvät voimakkaisiin kokemuksiin.",
                    "asset_ids": [t.id for t in unrated[:5]],
                }
            )
        # 4) Add markers to strong tracks
        no_markers = [t for t in g["top"] if not t.markers]
        if no_markers:
            exps.append(
                {
                    "kind": "marker",
                    "title": "Merkitse voimakkaimmat hetket",
                    "description": "Merkitse aikajanalle hetket, joissa koet väreitä, kehollisen reaktion tai tunnehuipun. Näin voidaan tutkia, mitä musiikissa tapahtuu juuri silloin.",
                    "asset_ids": [t.id for t in no_markers[:3]],
                }
            )
        # 5) Library diversity
        tempos = [t.features.get("tempo_bpm") for t in self.tracks if t.features.get("tempo_bpm")]
        if len(tempos) >= 4 and (max(tempos) - min(tempos)) < 25:
            exps.append(
                {
                    "kind": "upload",
                    "title": "Laajenna tempojen kirjoa",
                    "description": f"Kaikki kappaleesi ovat välillä {min(tempos):.0f}–{max(tempos):.0f} BPM. Tempon merkitystä ei voi arvioida ilman vaihtelua – tuo myös selvästi hitaampia tai nopeampia kappaleita.",
                    "asset_ids": [],
                }
            )
        # 6) Pairwise where none exist
        if len(self.ds.comparisons) < 3 and len(scored) >= 2:
            top = g["top"][:1]
            other = [t for t in scored if t not in g["top"]][:1]
            if top and other:
                exps.append(
                    {
                        "kind": "pairwise",
                        "title": "Aloita pareittaisvertailut",
                        "description": "Vertaa kahta kappaletta: kumpi vaikuttaa voimakkaammin ja kumpi on mieluisampi? Suora vertailu on usein luotettavampi kuin erilliset numeroarviot.",
                        "asset_ids": [top[0].id, other[0].id],
                    }
                )
        return hyps, exps

    def _find_contrast_pair(self, same: str, differ: str, z: dict[int, dict[str, float]]) -> tuple[TrackRecord, TrackRecord] | None:
        best = None
        best_score = 0.0
        for i, t1 in enumerate(self.tracks):
            for t2 in self.tracks[i + 1:]:
                a1, a2 = z[t1.id].get(same), z[t2.id].get(same)
                b1, b2 = z[t1.id].get(differ), z[t2.id].get(differ)
                if None in (a1, a2, b1, b2):
                    continue
                if abs(a1 - a2) < 0.5 and abs(b1 - b2) > 1.0:
                    score = abs(b1 - b2) - abs(a1 - a2)
                    if score > best_score:
                        best, best_score = (t1, t2), score
        return best

    # ------------------------------------------------------------------
    def qualitative_summary(self, targets: dict[str, Any], g: dict[str, Any]) -> list[dict[str, Any]]:
        lines = []
        for f in targets.get("features", []):
            if f["direction"] == "typical" or f["evidence_level"] == "insufficient":
                continue
            fdef = FEATURE_BY_KEY[f["feature"]]
            phrase = fdef.high_fi if f["direction"] == "high" else fdef.low_fi
            lines.append(
                {
                    "feature": f["feature"],
                    "text": f"{phrase.capitalize()} (tyypillisesti {f['value_label']}; kirjaston mediaani {fmt_value(f['feature'], f['library_median'])})",
                    "evidence_level": f["evidence_level"],
                }
            )
            if len(lines) >= 6:
                break
        return lines

    def field_points(self, z: dict[int, dict[str, float]]) -> dict[str, Any]:
        pts = []
        keys = [k for k in PROFILE_FEATURES if sum(1 for t in self.tracks if k in z[t.id]) == len(self.tracks)]
        pca = None
        if len(self.tracks) >= 3 and len(keys) >= 2:
            X = np.array([[z[t.id][k] for k in keys] for t in self.tracks])
            Xc = X - X.mean(axis=0)
            try:
                U, Sv, Vt = np.linalg.svd(Xc, full_matrices=False)
                coords = Xc @ Vt[:2].T
                var = (Sv ** 2) / max(np.sum(Sv ** 2), 1e-12)
                pca = {
                    "explained_variance": [round(float(v), 3) for v in var[:2]],
                    "loadings": [
                        sorted(
                            [{"feature": k, "label": FEATURE_BY_KEY[k].label, "weight": round(float(w), 3)} for k, w in zip(keys, Vt[i])],
                            key=lambda d: abs(d["weight"]),
                            reverse=True,
                        )[:5]
                        for i in range(min(2, Vt.shape[0]))
                    ],
                }
            except np.linalg.LinAlgError:  # pragma: no cover
                coords = None
        else:
            coords = None
        for i, t in enumerate(self.tracks):
            pts.append(
                {
                    "asset_id": t.id,
                    "title": t.asset.title,
                    "artist": t.asset.artist,
                    "origin": t.asset.origin,
                    "features": {k: t.features.get(k) for k in PROFILE_FEATURES},
                    "ratings": dict(t.rating.dimensions) if t.rating else {},
                    "resonance_score": None if t.resonance_score is None else round(t.resonance_score, 2),
                    "pca": None if coords is None else [round(float(coords[i, 0]), 3), round(float(coords[i, 1]), 3)],
                    "body_responses": list(t.rating.body_responses) if t.rating else [],
                    "markers": len(t.markers),
                }
            )
        return {"points": pts, "pca": pca, "pca_features": keys, "method": "Robust z-scores of SonicDNA features; PCA projection is a declared, reproducible feature-space map — not an emotional or psychological map."}

    # ------------------------------------------------------------------
    def build(self) -> dict[str, Any]:
        lib = self.library_stats()
        z = self.zscores()
        g = self.groups()
        rated = [t for t in self.tracks if t.is_rated]
        n_rated = len(rated)
        stage = "empty" if not self.tracks else ("collecting" if n_rated < 4 else ("preliminary" if n_rated < 8 else "developing"))
        assocs = self.associations()
        consistency = self.consistency_insights(g, lib)
        assoc_ins = self.association_insights(assocs)
        neg_ins, neg_tend = self.negative_insights(g, z, lib)
        ma = self.marker_analysis()
        pw = self.pairwise_analysis()
        targets = self.targets(g, lib, z, assocs, consistency)
        hyps, exps = self.hypotheses_and_experiments(g, assocs, z)

        insights = consistency + assoc_ins + self.marker_insights(ma) + self.pairwise_insights(pw) + self.divergence_insight() + neg_ins
        for ins in insights:
            ins.pop("_strength", None)
            ins.setdefault("timestamps", [])
            ins["evidence_level_label"] = EVIDENCE_FI[ins["evidence_level"]]
            ins["generated_at"] = self.now
            ins["core_version"] = CORE_VERSION
            ins["analysis_version"] = ALGORITHM_VERSION
        insights.sort(key=lambda i: EVIDENCE_ORDER[i["evidence_level"]], reverse=True)

        # contradictions: strongly rated tracks that contradict the main tendencies
        contradictions = []
        for c in consistency[:3]:
            for ref in c["contrasting_tracks"]:
                if ref.get("role") == "top_outside":
                    contradictions.append({"insight_id": c["id"], "feature": c["feature"], "track": ref, "note": "Voimakkaasti vaikuttava kappale, joka ei noudata tätä taipumusta."})

        body_counts: dict[str, int] = {}
        for t in rated:
            for b in t.rating.body_responses:
                body_counts[b] = body_counts.get(b, 0) + 1

        return {
            "core_version": CORE_VERSION,
            "analysis_version": ALGORITHM_VERSION,
            "generated_at": self.now,
            "data_stage": stage,
            "counts": {
                "tracks_analyzed": len(self.tracks),
                "tracks_rated": n_rated,
                "generated_tracks": sum(1 for t in self.tracks if t.asset.origin == "generated"),
                "markers": sum(len(t.markers) for t in self.tracks),
                "comparisons": len(self.ds.comparisons),
                "ratings_by_dimension": {k: sum(1 for t in self.tracks if t.dim(k) is not None) for k in DIMENSION_KEYS},
                "body_responses": body_counts,
            },
            "group_definition": {
                "basis": g["basis"],
                "affect_dimensions": AFFECT_DIMENSIONS,
                "description": (
                    "Voimakkaimmat kokemukset = arvioiduista kappaleista ylin kolmannes resonanssipistemäärän mukaan "
                    "(kehollisen resonanssin, tunteen voimakkuuden, uppoutumisen ja henkilökohtaisen merkityksen keskiarvo, vähintään 5/10)."
                    if g["basis"] == "resonance"
                    else "Resonanssiarvioita on vielä vähän, joten ryhmittely perustuu yleiseen mieltymykseen."
                ),
                "top": [t.id for t in g["top"]],
                "bottom": [t.id for t in g["bottom"]],
                "disliked": [t.id for t in g["disliked"]],
            },
            "library_stats": lib,
            "targets": targets,
            "summary_lines": self.qualitative_summary(targets, g),
            "associations": [a for a in assocs if a["evidence_level"] != "insufficient"][:40],
            "associations_tested": len(assocs),
            "insights": insights,
            "contradictions": contradictions,
            "negative_tendencies": neg_tend,
            "marker_analysis": {k: v for k, v in ma.items() if k != "rows"} | {"rows": ma["rows"][:50]},
            "pairwise": pw,
            "hypotheses": hyps,
            "suggested_experiments": exps,
            "field": self.field_points(z),
        }


# ----------------------------------------------------------------------
def input_hash(ds: Dataset) -> str:
    parts = []
    for t in ds.tracks:
        r = t.rating
        parts.append(
            [
                t.id,
                t.analysis.algorithm_version,
                t.analysis.created_at.isoformat() if t.analysis.created_at else "",
                r.updated_at.isoformat() if r else "",
                [(m.id, m.start_seconds, m.label) for m in t.markers],
            ]
        )
    parts.append([(c.id, c.stronger, c.enjoyed) for c in ds.comparisons])
    parts.append(CORE_VERSION)
    return hashlib.sha256(json.dumps(parts, default=str).encode()).hexdigest()


def compute_profile(session: Session, persist: bool = True) -> dict[str, Any]:
    ds = load_dataset(session)
    h = input_hash(ds)
    latest = session.exec(select(SonicProfileSnapshot).order_by(SonicProfileSnapshot.version.desc())).first()
    if latest is not None and latest.input_hash == h:
        return latest.data | {"version": latest.version, "snapshot_created_at": latest.created_at.isoformat()}
    data = ProfileBuilder(ds).build()
    if not persist or not ds.tracks:
        return data | {"version": latest.version if latest else 0, "snapshot_created_at": None}
    version = (latest.version + 1) if latest else 1
    snap = SonicProfileSnapshot(version=version, input_hash=h, core_version=CORE_VERSION, data=data)
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return data | {"version": version, "snapshot_created_at": snap.created_at.isoformat()}


def similar_tracks(session: Session, asset_id: int, k: int = 5) -> list[dict[str, Any]]:
    """Nearest neighbours in robust-standardised feature space, with the shared
    distinctive features that explain the similarity (cross-genre discovery)."""
    ds = load_dataset(session)
    pb = ProfileBuilder(ds)
    z = pb.zscores()
    if asset_id not in z or not z[asset_id]:
        return []
    me = z[asset_id]
    out = []
    for t in ds.tracks:
        if t.id == asset_id:
            continue
        other = z[t.id]
        common = [f for f in me if f in other]
        if len(common) < 5:
            continue
        a = np.array([me[f] for f in common])
        b = np.array([other[f] for f in common])
        dist = float(np.sqrt(np.mean((a - b) ** 2)))
        shared = [
            {"feature": f, "label": FEATURE_BY_KEY[f].label, "phrase": FEATURE_BY_KEY[f].high_fi if me[f] > 0 else FEATURE_BY_KEY[f].low_fi}
            for f in common
            if abs(me[f]) >= 0.7 and abs(other[f]) >= 0.7 and np.sign(me[f]) == np.sign(other[f]) and abs(me[f] - other[f]) < 0.6
        ]
        out.append({**_track_ref(t), "distance": round(dist, 3), "shared_features": shared[:5], "genre_tag": t.asset.genre_tag})
    out.sort(key=lambda d: d["distance"])
    return out[:k]
