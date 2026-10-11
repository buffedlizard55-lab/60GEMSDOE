#!/usr/bin/env python3
"""PRE-REGISTERED FIRST TEST (the lane's go / no-go).

Question, verbatim from the lane brief:

    "First test: do channels crossing withheld segments show larger steepness
     steps than random lines of the same orientation?  If not, stop."

Design (fixed before looking at the answer)
-------------------------------------------
* Truth = the visible catalogue (``data/labels.tif``), partitioned into whole
  connected components and split into 4 spatial quadrants
  (:mod:`gems60.holdout`, 3 px = 300 m buffer).
* Detector = the chi-profile steepness-step statistic
  ``Sigma(cell) = log10( ksn_up(cell) / ksn_dn(cell) )`` from
  :func:`gems60.knick.channel_step_statistic`, computed **only** from the DEM.
  No label information enters the statistic (leakage canary reported anyway).
* Arm A ("crossing")  = channel pixels within 1.5 px of a *withheld* component.
* Arm B ("control")   = channel pixels within 1.5 px of the *same component
  translated by a random offset* - identical shape, length and orientation,
  different place.  Offsets are redrawn until the translated component does not
  touch the visible catalogue, so the control is never contaminated by real faults.
* Statistic: one-sided Mann-Whitney U (A > B) plus a fold-block bootstrap of
  mean(A) - mean(B).
* Decision rule, pre-declared: **proceed only if** the one-sided p < 0.01 AND the
  bootstrap CI95 of mean(A) - mean(B) excludes 0.  Otherwise STOP and publish the
  negative result.

Usage:  PYTHONPATH=src python3 scripts/exp1_first_test.py [--cache DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage, stats
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems60.hydro import (bfs_levels, chi_transform, d8_flow_directions,  # noqa: E402
                          fill_depressions, flow_accumulation)
from gems60.holdout import build_holdout  # noqa: E402
from gems60.knick import channel_mask, channel_step_statistic, extract_profiles  # noqa: E402

W = 31                  # segmentation window (samples), declared
A_THRESHOLD_PX = 100    # 1 km2 channel initiation, declared
THETA = 0.45            # reference concavity (Wobus et al. 2006), declared
RADIUS_PX = 1.5         # crossing radius around a component
N_CONTROL_DRAWS = 20
SEED = 2026


def _flatten(hits):
    """``cKDTree.query_ball_point`` on an (n, 2) query returns a list/object array
    of per-point index lists; flatten it to a single int64 index array."""
    parts = [np.asarray(h, dtype=np.int64).ravel() for h in hits if len(h)]
    if not parts:
        return np.zeros(0, dtype=np.int64)
    return np.concatenate(parts).astype(np.int64)


def log(*a):
    print(*a, flush=True)


def routed(cache: Path, dem, valid, shape):
    """Routed hydrology, cached to .npy so repeat runs are cheap."""
    names = ["filled", "down", "acc", "chi", "dist"]
    if all((cache / f"{n}.npy").exists() for n in names):
        log("    (loading cached routing)")
        return tuple(np.load(cache / f"{n}.npy") for n in names)
    filled, is_filled = fill_depressions(dem, valid)
    down = d8_flow_directions(filled, valid)
    dist, levels = bfs_levels(down, valid)
    acc = flow_accumulation(down, valid, levels)
    chi = chi_transform(down, acc, valid, shape, theta=THETA, step_m=100.0)
    cache.mkdir(parents=True, exist_ok=True)
    for n, a in zip(names, (filled, down, acc, chi, dist)):
        np.save(cache / f"{n}.npy", a)
    np.save(cache / "is_filled.npy", is_filled)
    return filled, down, acc, chi, dist


def component_pixels(comp_ids: np.ndarray, n_comp: int):
    """Return (sorted_px, starts) so component c's pixels are
    sorted_px[starts[c]:starts[c+1]] - one O(N log N) pass."""
    flat = comp_ids.ravel()
    px = np.nonzero(flat > 0)[0]
    ids = flat[px]
    order = np.argsort(ids, kind="stable")
    sorted_px = px[order]
    sorted_ids = ids[order]
    starts = np.searchsorted(sorted_ids, np.arange(n_comp + 2))
    return sorted_px, starts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="/tmp/study/work")
    args = ap.parse_args()
    cache = Path(args.cache)

    out_dir = ROOT / "evidence"
    out_dir.mkdir(exist_ok=True)

    with rasterio.open(ROOT / "data" / "geodawn_dem_a2_100m.tif") as ds:
        dem = ds.read(1).astype(np.float64)
        shape = ds.shape
    labels = rasterio.open(ROOT / "data" / "labels.tif").read(1)
    footprint = labels >= 0
    valid = footprint & (dem > -99999)
    dem = np.where(valid, dem, np.nan)
    log(f"[1/6] grid {shape}, footprint {int(footprint.sum()):,} px, valid {int(valid.sum()):,} px")

    t = time.time()
    filled, down, acc, chi, dist = routed(cache, dem, valid, shape)
    log(f"[2/6] routed in {time.time()-t:.0f} s: max accumulation {acc.max():,.0f} px, "
        f"max chi {chi.max():,.1f} m")

    chan = channel_mask(acc, valid, A_THRESHOLD_PX)
    profiles = extract_profiles(down, chan, acc, chi, valid, min_len=W + 2)
    log(f"[3/6] channels: {int(chan.sum()):,} px, {len(profiles):,} profiles")

    t = time.time()
    flats, sigma, _c = channel_step_statistic(profiles, down, chi, filled, valid, w=W)
    log(f"[4/6] steepness-step statistic on {flats.size:,} channel px ({time.time()-t:.0f} s)")

    hd = build_holdout(catalogue=labels == 1, footprint=footprint, n_folds=4, buffer_px=3)
    log(f"[5/6] holdout: {len(hd.folds)} folds, {hd.n_withheld_total:,} withheld positive px")
    px_sorted, px_starts = component_pixels(hd.component_ids, hd.n_components)

    rows, cols = np.unravel_index(flats, shape)
    tree = cKDTree(np.c_[rows, cols].astype(np.float64))
    sigma_by_flat = np.full(down.size, np.nan)
    sigma_by_flat[flats] = sigma

    rng = np.random.default_rng(SEED)
    per_fold, A_all, B_all = [], [], []
    for fold in hd.folds:
        a_vals, b_vals = [], []
        for cid in np.unique(hd.component_ids[fold.withheld]).tolist():
            pxs = px_sorted[px_starts[cid]:px_starts[cid + 1]]
            if pxs.size < 20:
                continue
            cy, cx = np.unravel_index(pxs, shape)
            # --- arm A: channel pixels within RADIUS_PX of the withheld trace
            a_hit = tree.query_ball_point(np.c_[cy, cx].astype(np.float64), r=RADIUS_PX)
            a_idx = np.unique(_flatten(a_hit))
            if a_idx.size:
                a_vals.append(sigma_by_flat[flats[a_idx]])
            # --- arm B: the same component, translated
            got = 0
            for _ in range(N_CONTROL_DRAWS):
                dy = int(rng.integers(-1600, 1600))
                dx = int(rng.integers(-1600, 1600))
                ty, tx = cy + dy, cx + dx
                ok = (ty >= 0) & (ty < shape[0]) & (tx >= 0) & (tx < shape[1])
                if ok.mean() < 0.6:
                    continue
                ty, tx = ty[ok], tx[ok]
                if labels[ty, tx].max() > 0:
                    continue                       # control must miss real faults
                b_hit = tree.query_ball_point(np.c_[ty, tx].astype(np.float64), r=RADIUS_PX)
                b_idx = np.unique(_flatten(b_hit))
                if b_idx.size:
                    b_vals.append(sigma_by_flat[flats[b_idx]])
                    got += 1
                    if got >= 3:
                        break
        if a_vals and b_vals:
            a = np.concatenate(a_vals).astype(float)
            b = np.concatenate(b_vals).astype(float)
            a = a[np.isfinite(a)]
            b = b[np.isfinite(b)]
            if a.size < 10 or b.size < 10:
                continue
            A_all.append(a)
            B_all.append(b)
            u, p = stats.mannwhitneyu(a, b, alternative="greater")
            per_fold.append(dict(
                fold=fold.name, n_crossing=int(a.size), n_control=int(b.size),
                mean_crossing=float(a.mean()), mean_control=float(b.mean()),
                median_crossing=float(np.median(a)), median_control=float(np.median(b)),
                delta_mean=float(a.mean() - b.mean()),
                mannwhitney_U=float(u), p_one_sided=float(p)))
            log(f"    {fold.name}: n_A={a.size:6d} n_B={b.size:6d} "
                f"meanA={a.mean():+.4f} meanB={b.mean():+.4f} "
                f"d={a.mean()-b.mean():+.4f} p={p:.3g}")

    if not per_fold:
        log("NO DATA: no fold produced both arms")
        return 2

    A = np.concatenate(A_all)
    B = np.concatenate(B_all)
    u_all, p_all = stats.mannwhitneyu(A, B, alternative="greater")
    rng2 = np.random.default_rng(SEED + 1)
    nf = len(A_all)
    boot = np.empty(4000)
    for i in range(4000):
        k = rng2.integers(0, nf, size=nf)
        boot[i] = (np.concatenate([A_all[j] for j in k]).mean()
                   - np.concatenate([B_all[j] for j in k]).mean())
    ci = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]

    auc = float("nan")
    try:
        from sklearn.metrics import roc_auc_score
        n = min(A.size, B.size, 40000)
        auc = float(roc_auc_score(
            np.concatenate([np.ones(n), np.zeros(n)]),
            np.concatenate([A[:n], B[:n]])))
    except Exception as exc:                                    # pragma: no cover
        log("AUC skipped:", exc)

    verdict = "proceed" if (p_all < 0.01 and ci[0] > 0.0) else "STOP"
    result = dict(
        evidence_class="HOLDOUT-DTI", evaluator_version="gems60-exp1-v1",
        question="do channels crossing withheld segments show larger steepness steps "
                 "than random lines of the same orientation?",
        statistic="Sigma = log10(ksn_up / ksn_dn) on the chi-profile segmentation window",
        parameters=dict(window_samples=W, area_threshold_px=A_THRESHOLD_PX,
                        theta_ref=THETA, control="translated identical component",
                        radius_px=RADIUS_PX, n_control_draws=N_CONTROL_DRAWS,
                        seed=SEED, buffer_px=3, min_component_px=8),
        pooled=dict(n_crossing=int(A.size), n_control=int(B.size),
                    mean_crossing=float(A.mean()), mean_control=float(B.mean()),
                    median_crossing=float(np.median(A)), median_control=float(np.median(B)),
                    delta_mean=float(A.mean() - B.mean()), ci95_delta=ci,
                    mannwhitney_U=float(u_all), p_one_sided=float(p_all),
                    leakage_canary_auc=auc),
        per_fold=per_fold,
        predeclared_rule="proceed iff p_one_sided < 0.01 AND ci95_delta lower bound > 0",
        verdict=verdict,
        withheld_positive_pixels=int(hd.n_withheld_total),
    )
    (out_dir / "exp1_first_test.json").write_text(json.dumps(result, indent=1))
    log(json.dumps(result["pooled"], indent=1))
    log("VERDICT: " + verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
