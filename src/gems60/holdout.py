"""Hide-and-recover instruments.

Two instruments, because the repository's own measurement (IR-H77-005, knowledge/76 section 6,
knowledge/82 section 3) is that they answer different questions and only one of them is about the
board:

``catalogue`` — hide whole connected catalogue segments behind a buffer, rebuild every
catalogue-derived feature from the VISIBLE faults only, mask visible faults pixel-exactly, then
score the withheld segments.  This is the instrument every previous round used.  It measures
"can you recover a fault that is in the catalogue from the evidence that is not the catalogue".

``off_catalogue`` — the truth is a population the catalogue does NOT contain (here: USGS State
Geologic Map Compilation fault pixels at least 300 m from every catalogue pixel).  The board scores
exactly that population ("newly identified faults ... not included in the existing USGS fault
database", competition page 967).  This instrument is new in this repository: H83 measured the gap
(its View-B surface keeps only ~7% of its catalogue-population skill here) but H83's off-catalogue
truth was 4x the estimated real prevalence, so it was declared invalid for *budget* choice.  The
fix demanded in knowledge/76 section 6 -- thin the truth to the estimated prevalence -- is
implemented here, so the instrument can now be used for budget choice as well as for ranking.

Both instruments pool TP_w / FP_w / FN_w across folds before taking one DTI, mirroring the
organiser's pooled aggregation, and never average fold ratios.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from . import metric as M

BIG = np.ones((3, 3), dtype=int)


def make_segment_folds(truth: np.ndarray, footprint: np.ndarray, n_folds: int = 5,
                       buffer_px: int = 3, split_px: int = 40, seed: int = 0) -> list[dict]:
    """Split the truth into whole connected segments, then into folds with a buffer.

    Long segments are additionally cut every ``split_px`` along their skeleton-free pixel order, so
    that one very long trace cannot dominate a single fold.  The buffer is applied AFTER assignment:
    a withheld segment's neighbourhood is visible-catalogue-free, so no fold can see the answer
    through the buffer.
    """
    lab, n = ndi.label(truth, structure=BIG)
    segs: list[tuple[np.ndarray, np.ndarray]] = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if ys.size == 0:
            continue
        if ys.size <= split_px:
            segs.append((ys, xs))
            continue
        order = np.lexsort((xs, ys))
        ys, xs = ys[order], xs[order]
        for a in range(0, ys.size, split_px):
            segs.append((ys[a:a + split_px], xs[a:a + split_px]))
    if not segs:
        raise ValueError("no truth segments")
    rng = np.random.default_rng(seed)
    assign = rng.integers(0, n_folds, size=len(segs))
    folds = []
    st = ndi.generate_binary_structure(2, 1)
    for f in range(n_folds):
        t = np.zeros_like(truth)
        for s, a in enumerate(assign):
            if a == f:
                t[segs[s][0], segs[s][1]] = True
        if not t.any():
            continue
        withheld_buf = ndi.binary_dilation(t, structure=st, iterations=buffer_px)
        visible = truth & ~withheld_buf & footprint
        folds.append({"fold": f, "truth": t, "visible": visible, "withheld": withheld_buf,
                      "n_truth": int(t.sum()), "n_visible": int(visible.sum()),
                      "n_segments": int(sum(1 for a in assign if a == f))})
    return folds


def flank_weight(visible: np.ndarray, support_px: float) -> np.ndarray:
    """Quadratic-decay prior from VISIBLE faults only (per fold; never borrowed across folds)."""
    d = ndi.distance_transform_edt(~visible)
    w = np.clip(1.0 - d / float(support_px), 0.0, 1.0) ** 2
    return w.astype(np.float32)


def auc(score: np.ndarray, labels: np.ndarray) -> float:
    """Rank AUC with tie handling by the Mann-Whitney formulation."""
    # ravel: callers pass 2-D grids.  (An earlier version indexed the sorted rank vector with a 2-D
    # boolean mask and tried to broadcast to (h, w, w) -- a 301 GiB allocation, caught at run time.)
    s = np.asarray(score, dtype=np.float64).ravel()
    y = np.asarray(labels).astype(bool).ravel()
    if s.size != y.size:
        raise ValueError(f"score/labels size mismatch: {s.size} vs {y.size}")
    if y.sum() == 0 or (~y).sum() == 0:
        return float("nan")
    r = np.empty(s.size, dtype=np.float64)
    order = np.argsort(s, kind="stable")
    sr = s[order]
    ranks = np.arange(1, s.size + 1, dtype=np.float64)
    i = 0
    while i < sr.size:                      # average ranks inside ties
        j = i
        while j + 1 < sr.size and sr[j + 1] == sr[i]:
            j += 1
        if j > i:
            ranks[i:j + 1] = ranks[i:j + 1].mean()
        i = j + 1
    r[order] = ranks
    n1 = float(y.sum())
    n0 = float((~y).sum())
    return float((r[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def pooled_dti(pred: np.ndarray, g: np.ndarray) -> dict:
    """One exact DTI on the pooled prediction/truth pair, plus its components."""
    r = M.dti(pred.astype(np.float64), g.astype(np.float64))
    return {"dti": r["dti"], "tp_w": r["tpw"], "fp_w": r["fpw"], "fn_w": r["fnw"],
            "n_truth": r["n_truth"], "n_pred_pos": int((pred > 0).sum()), "mass": r["mass"]}


def bootstrap_ci_pooled(fold_dtis: np.ndarray, n: int = 4000, seed: int = 0) -> list[float]:
    x = np.asarray(fold_dtis, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size < 2:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, x.size, size=(n, x.size))].mean(axis=1)
    return [float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


# ------------------------------------------------------------------------------------------------
# the off-catalogue population: what the board actually scores
# ------------------------------------------------------------------------------------------------
def off_catalogue_population(sgmc: np.ndarray, catalogue: np.ndarray, footprint: np.ndarray,
                             min_dist_m: float = 300.0, cell_m: float = 100.0,
                             target_px: int | None = None, seed: int = 0) -> dict:
    """Fault pixels that are in an official state geological-map compilation but NOT in the
    competition catalogue, at least ``min_dist_m`` away from anything the catalogue has.

    ``target_px`` implements the prevalence correction demanded by knowledge/76 section 6: the raw
    SGMC-off-catalogue class is several times the estimated real prevalence |G| ~ 14,000, which
    biases any budget chosen on it.  Thinning to ``target_px`` (maximal-separation thinning, i.e. a
    Poisson-disc downsample) restores the real prevalence while keeping the class's spatial
    structure, which is what makes the instrument usable for budget choice and not only ranking.
    """
    d = ndi.distance_transform_edt(~catalogue, sampling=cell_m)
    pop = sgmc & footprint & (d >= min_dist_m)
    n_raw = int(pop.sum())
    info = {"raw_px": n_raw, "min_dist_m": min_dist_m, "target_px": target_px}
    if target_px is not None and n_raw > target_px:
        ys, xs = np.nonzero(pop)
        rng = np.random.default_rng(seed)
        order = np.argsort(rng.random(ys.size), kind="stable")
        # maximal-separation thinning: greedy over a random order with a radius derived from the
        # target count, which reproduces the density of a Poisson-disc process at that count
        keep = []
        scale = np.sqrt(n_raw / max(target_px, 1))
        radius = max(1.0, scale)
        cell = max(1, int(np.ceil(radius)))
        buckets: dict[tuple[int, int], list[int]] = {}
        for k in order:
            y, x = int(ys[k]), int(xs[k])
            by, bx = y // cell, x // cell
            ok = True
            for oy in (-1, 0, 1):
                for ox in (-1, 0, 1):
                    for q in buckets.get((by + oy, bx + ox), ()):
                        qy, qx = divmod(q, 1_000_000)
                        if (qy - y) ** 2 + (qx - x) ** 2 < radius * radius:
                            ok = False
                            break
                    if not ok:
                        break
                if not ok:
                    break
            if ok:
                keep.append(y * 1_000_000 + x)
                buckets.setdefault((by, bx), []).append(y * 1_000_000 + x)
                if len(keep) >= target_px:
                    break
        thinned = np.zeros_like(pop)
        arr = np.asarray(keep, dtype=np.int64)
        if arr.size:
            thinned[arr // 1_000_000, arr % 1_000_000] = True
        info.update({"thinned_px": int(thinned.sum()), "thinning_radius_px": float(radius),
                     "sampling": "random-order maximal-separation thinning"})
        pop = thinned
    else:
        info["thinned_px"] = n_raw
    return {"mask": pop, "info": info}


def dti_from_components(tp_w: float, fp_w: float, fn_w: float, n_truth: float,
                        alpha: float = 0.2, beta: float = 0.8, eps: float = 0.0) -> float:
    """Metric identity, from summed components only (never a mean of per-fold ratios)."""
    den = tp_w + alpha * fp_w + beta * fn_w + eps
    return float(tp_w / den) if den > 0 else 0.0


def pooled_over_folds(records: list[dict]) -> dict:
    """One DTI over disjoint folds: sum TP/FP/FN mass, then divide once."""
    tp = sum(float(r["tp_w"]) for r in records)
    fp = sum(float(r["fp_w"]) for r in records)
    fn = sum(float(r["fn_w"]) for r in records)
    n = sum(float(r["n_truth"]) for r in records)
    mass = sum(float(r.get("mass", r.get("n_pred_pos", 0.0))) for r in records)
    return {"dti": dti_from_components(tp, fp, fn, n), "tp_w": tp, "fp_w": fp, "fn_w": fn,
            "n_truth": n, "mass": mass, "n_folds": len(records)}


def per_truth_credit(pred: np.ndarray, truth: np.ndarray, r_px: float = 3.0) -> np.ndarray:
    """Credit ``max_x p(x) k(d(x, g))`` for every ground-truth pixel (metric, page 967)."""
    p = np.asarray(pred, dtype=np.float32)
    r = int(np.ceil(r_px))
    pad = np.pad(p, r, mode="constant")
    best = np.zeros_like(p, dtype=np.float32)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d = float(np.hypot(dy, dx))
            if d > r_px:
                continue
            k = np.float32(max(1.0 - d / r_px, 0.0))
            sh = pad[r + dy: r + dy + p.shape[0], r + dx: r + dx + p.shape[1]]
            np.maximum(best, sh * k, out=best)
    return best[np.asarray(truth, dtype=bool)]


def bootstrap_truth_side(pred: np.ndarray, truth: np.ndarray, n_boot: int = 4000,
                         seed: int = 0, r_px: float = 3.0) -> dict:
    """CI on the truth-side of the DTI: the withheld ground-truth pixels are resampled.

    With the metric's own identity T = TP_w = sum over truth pixels of max_x p(x) k(d(x,g)) and
    FN_w = |G| - T (page 967), a resample of the truth pixels moves T and FN together while the
    emission side is held fixed at its measured value (mass S and FP_w).  Holding FP_w fixed
    understates total uncertainty -- a dot near an unsampled truth pixel would become FP -- and the
    interval is reported as a LOWER bound with that label attached.
    """
    p = np.asarray(pred, dtype=np.float64)
    g = np.asarray(truth, dtype=bool)
    n_g = int(g.sum())
    if n_g == 0:
        return {"dti": float("nan"), "ci95": [float("nan")] * 2, "n_truth": 0}
    credit = per_truth_credit(p, g, r_px=r_px).astype(np.float64)
    rr = M.dti(p, g.astype(np.float64))
    fp_fixed = float(rr["fpw"])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_g, size=(n_boot, n_g))
    t_star = credit[idx].sum(axis=1)
    fn_star = float(n_g) - t_star
    den = t_star + 0.2 * fp_fixed + 0.8 * fn_star
    dti = np.where(den > 0, t_star / den, 0.0)
    return {"dti": float(rr["dti"]), "ci95": [float(np.quantile(dti, 0.025)),
                                             float(np.quantile(dti, 0.975))],
            "n_truth": n_g, "n_boot": int(n_boot),
            "note": "LOWER-bound CI: truth-side bootstrap (T and FN resampled), FP_w held fixed"}
