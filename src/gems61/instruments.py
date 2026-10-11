"""Selection instruments: does any *local* truth set rank the family's live scores?

Three families of instrument are compared on the same 13 live-scored artifacts:

``catalogue``     the given USGS/INGENIOUS labels as truth.  Biased by construction: the hidden test
                  set is disjoint from it, so it rewards covering mapped traces.
``sgmc_off``      USGS SGMC faults > 300 m from the given catalogue -- the only public population of
                  *real* faults absent from the given catalogue (measured: 61,664 px).
``sgmc_off_bal``  the same population re-sampled so its local-relief distribution matches the
                  footprint's, i.e. the previous session's proposed fix ("relief-stratified
                  thinning"), which removes the anti-relief bias of maximal-separation thinning.

Every score applies the organizer's own mask (DrivenData staff, thread 11516 post #2: predicted mass
on known faults is excluded from the penalty terms) via ``gems52.holdout.mask_visible``.

These are INSTRUMENT numbers, never scores: the truth is a public proxy, not the hidden label set.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems52 import holdout as H          # noqa: E402  shared template, not re-implemented here
from gems52 import metric as M           # noqa: E402


def catalogue_truth(cat: np.ndarray, valid: np.ndarray) -> np.ndarray:
    return cat & valid


def sgmc_off_catalogue(sgmc: np.ndarray, cat: np.ndarray, valid: np.ndarray,
                       buffer_px: int = 3) -> np.ndarray:
    """Real faults 300 m+ from the given catalogue: SGMC minus a 3-px dilation of the catalogue."""
    near = ndimage.binary_dilation(cat, iterations=buffer_px) if buffer_px > 0 else cat
    return sgmc & valid & ~near


def thin_random(mask: np.ndarray, n: int, seed: int = 61) -> np.ndarray:
    """Uniform random pixel subsample to exactly ``n`` pixels (fixed seed, reproducible)."""
    ys, xs = np.nonzero(mask)
    if ys.size <= n:
        return mask.copy()
    rng = np.random.default_rng(seed)
    keep = rng.choice(ys.size, size=n, replace=False)
    out = np.zeros_like(mask)
    out[ys[keep], xs[keep]] = True
    return out


def terrain_balanced_truth(truth: np.ndarray, valid: np.ndarray, terrain: np.ndarray,
                           n_target: int, seed: int = 61, n_strata: int = 5,
                           min_stratum_px: int = 60) -> tuple[np.ndarray, dict]:
    """Re-sample ``truth`` so its terrain distribution matches the footprint's.

    Strata are quantiles of ``terrain`` over the footprint.  The target count in stratum *s* is
    ``n_target * (footprint share of s)``.  Where a stratum holds fewer truth pixels than its target
    the shortfall is redistributed to the strata that can absorb it, proportionally to their
    remaining capacity, so the total is exactly ``n_target`` whenever the population allows.
    Strata holding fewer than ``min_stratum_px`` truth pixels are dropped from the balancing (their
    sampling fraction is meaningless) and treated as "take everything".
    """
    fin = np.isfinite(terrain) & valid
    qs = np.quantile(terrain[fin], np.linspace(0, 1, n_strata + 1)[1:-1])
    strata = np.digitize(terrain, qs)
    strata = np.where(fin, strata, -1)
    fp_share, avail = {}, {}
    for s in range(n_strata):
        fp_share[s] = float(((strata == s) & valid).sum()) / float(valid.sum())
        avail[s] = int((truth & (strata == s)).sum())
    target = {s: n_target * fp_share[s] for s in range(n_strata)}
    small = [s for s in range(n_strata) if avail[s] < min_stratum_px]
    fixed = {s: avail[s] for s in small}
    rest = [s for s in range(n_strata) if s not in small]
    budget = n_target - sum(fixed.values())
    for _ in range(8):                      # water-filling: cap at capacity, redistribute the rest
        total_cap = sum(avail[s] for s in rest)
        if total_cap <= 0 or budget <= 0:
            for s in rest:
                target[s] = 0.0
            break
        excess = 0.0
        for s in rest:
            want = budget * (avail[s] / total_cap) if total_cap > 0 else 0.0
            target[s] = min(want, avail[s])
            excess += max(0.0, want - avail[s])
        used = sum(target[s] for s in rest)
        if excess <= 0 or used >= budget - 1e-9:
            break
        rest = [s for s in rest if target[s] < avail[s]]
        budget = n_target - sum(fixed.values())
    rng = np.random.default_rng(seed)
    out = np.zeros_like(truth)
    for s in range(n_strata):
        ys, xs = np.nonzero(truth & (strata == s))
        want = min(int(round(target.get(s, 0.0))), ys.size)
        if want <= 0:
            continue
        keep = np.arange(ys.size) if want >= ys.size else rng.choice(ys.size, want, replace=False)
        out[ys[keep], xs[keep]] = True
    diag = dict(footprint_share=fp_share, available_px=avail,
                target_px={s: round(float(target.get(s, 0.0)), 1) for s in range(n_strata)},
                kept_px=int(out.sum()), small_strata=small,
                terrain_quantiles=[float(q) for q in qs])
    return out, diag


def balanced_dti(pred: np.ndarray, truth_by_stratum: dict, strata: np.ndarray, valid: np.ndarray,
                 cat: np.ndarray, weights: dict) -> dict:
    """Footprint-area-weighted mean of the official DTI computed inside each terrain stratum.

    Not the official metric (which pools globally) -- it is the terrain-balanced read of the same
    metric, and it is labelled as an instrument wherever it appears.
    """
    mass = np.where(valid, np.asarray(pred, np.float64), 0.0)
    mass = H.mask_visible(mass, cat & valid)          # organizer mask: mass on known faults is free
    out, per = 0.0, {}
    for s, tr in truth_by_stratum.items():
        if tr.sum() == 0:
            continue
        sel = (strata == s) & valid
        r = M.dti(np.where(sel, mass, 0.0), tr)
        per[int(s)] = dict(dti=round(float(r["dti"]), 6), n_truth=int(r["n_truth"]),
                           weight=round(float(weights[s]), 4))
        out += float(weights[s]) * float(r["dti"])
    return dict(balanced_dti=float(out), per_stratum=per)


def global_dti(pred: np.ndarray, truth: np.ndarray, valid: np.ndarray, cat: np.ndarray) -> dict:
    """Official DTI of one artifact against one truth set, with the organizer's catalogue mask."""
    mass = np.where(valid, np.asarray(pred, np.float64), 0.0)
    mass = H.mask_visible(mass, cat & valid)
    r = M.dti(mass, truth)
    return dict(dti=round(float(r["dti"]), 6), tpw=round(float(r["tpw"]), 3),
                fpw=round(float(r["fpw"]), 3), fnw=round(float(r["fnw"]), 3),
                n_truth=int(r["n_truth"]), mass=float(mass[mass > 0].sum()),
                emitted_px=int((mass > 0).sum()),
                credit_per_px=round(float(r["tpw"]) / max(1, int((mass > 0).sum())), 6))


def spearman(a: list[float], b: list[float]) -> float:
    """Spearman rho without scipy.stats (ties averaged), so the audit has no hidden dependency."""
    x = np.asarray(a, float)
    y = np.asarray(b, float)
    if x.size < 3:
        return float("nan")

    def rank(v):
        order = np.argsort(v, kind="mergesort")
        r = np.empty(v.size, float)
        r[order] = np.arange(v.size, dtype=float)
        # average ties
        for val in np.unique(v):
            m = v == val
            if m.sum() > 1:
                r[m] = r[m].mean()
        return r

    rx, ry = rank(x), rank(y)
    rx -= rx.mean(); ry -= ry.mean()
    den = np.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / den) if den > 0 else float("nan")
