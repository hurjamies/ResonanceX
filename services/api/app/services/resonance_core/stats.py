"""Small, transparent statistics helpers (no opaque models)."""

from __future__ import annotations

import math

import numpy as np
import scipy.stats


def rankdata_cols(X: np.ndarray) -> np.ndarray:
    return np.apply_along_axis(scipy.stats.rankdata, 0, X)


def spearman_with_permutation(
    x: np.ndarray, y: np.ndarray, n_perm: int = 2000, n_boot: int = 1000, seed: int = 7
) -> dict[str, float | None]:
    """Spearman rho, two-sided permutation p-value and percentile bootstrap CI."""
    n = len(x)
    if n < 3 or np.std(x) == 0 or np.std(y) == 0:
        return {"rho": None, "p": None, "ci_low": None, "ci_high": None, "n": n}
    rx = scipy.stats.rankdata(x)
    ry = scipy.stats.rankdata(y)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    rng = np.random.default_rng(seed)
    perms = np.array([rng.permutation(ry) for _ in range(n_perm)])
    rxc = (rx - rx.mean()) / (rx.std() + 1e-12)
    pc = (perms - perms.mean(axis=1, keepdims=True)) / (perms.std(axis=1, keepdims=True) + 1e-12)
    null = (pc @ rxc) / n
    p = float((np.sum(np.abs(null) >= abs(rho) - 1e-12) + 1) / (n_perm + 1))
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        bx, by = x[idx], y[idx]
        if np.std(bx) == 0 or np.std(by) == 0:
            continue
        boots.append(np.corrcoef(scipy.stats.rankdata(bx), scipy.stats.rankdata(by))[0, 1])
    if len(boots) >= 50:
        lo, hi = np.percentile(boots, [2.5, 97.5])
    else:
        lo = hi = float("nan")
    return {"rho": rho, "p": p, "ci_low": float(lo), "ci_high": float(hi), "n": n}


def benjamini_hochberg(pvals: list[float]) -> list[float]:
    m = len(pvals)
    if m == 0:
        return []
    order = np.argsort(pvals)
    q = np.empty(m)
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        prev = min(prev, pvals[i] * m / rank)
        q[i] = prev
    return [float(v) for v in q]


def binomial_sign_p(successes: int, n: int) -> float:
    """One-sided binomial test p-value for P(success) > 0.5."""
    if n == 0:
        return 1.0
    return float(scipy.stats.binomtest(successes, n, 0.5, alternative="greater").pvalue)


def cohens_d(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    va, vb = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    if pooled == 0:
        return None
    return float((np.mean(a) - np.mean(b)) / pooled)


def robust_scale(values: np.ndarray) -> tuple[float, float]:
    """Median and a robust spread (IQR/1.349, falling back to std)."""
    med = float(np.median(values))
    q75, q25 = np.percentile(values, [75, 25])
    spread = float((q75 - q25) / 1.349)
    if spread <= 1e-12:
        spread = float(np.std(values))
    if spread <= 1e-12:
        spread = 1.0
    return med, spread
