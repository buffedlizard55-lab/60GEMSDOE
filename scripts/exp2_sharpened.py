#!/usr/bin/env python3
"""EXPERIMENT 2 - the corrected first test plus the channel-normal cast field.

Why a second test is legitimate (declared before running)
---------------------------------------------------------
Experiment 1 (``scripts/exp1_first_test.py``, evidence ``exp1_first_test.json``)
returned STOP: pooled Delta-mean = -0.0229, CI95 [-0.166, +0.162], p = 1.0,
AUC = 0.459.  Reading the log shows the primary cause is a **design defect, not a
property of the geology**: the segmentation window was 31 samples = **3.1 km**
along the channel, i.e. about ten times longer than the base-level step it was
supposed to localise.  A 3.1 km window that is free to place its own breakpoint
anywhere inside it cannot resolve a step at the window centre, so the statistic
being tested was not the statistic the hypothesis is about.

Experiment 2 therefore re-runs the *same* pre-registered question with
(a) a statistic localised to ~700 m (``w_ksn = 7`` samples, ``gap = 2``), and
(b) a **position-matched** control: random channel positions on the *same*
profiles, binned on log-drainage-area, instead of an unrelated translated line.
Both defects were named before the run; the decision rule is unchanged.

It additionally measures the two surfaces that a submission would be built from
(:mod:`gems60.field`): the sharpened step ``Sigma`` and the **channel-normal cast
count**, scored as AUC over the whole holdout (all withheld components pooled).

Usage:  PYTHONPATH=src python3 scripts/exp2_sharpened.py
"""

from __future__ import annotations

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

from gems60.field import cast_field, surface_statistics  # noqa: E402
from gems60.holdout import build_holdout  # noqa: E402
from gems60.hydro import (bfs_levels, chi_transform, d8_flow_directions,  # noqa: E402
                          fill_depressions, flow_accumulation)
from gems60.knick import channel_mask, extract_profiles  # noqa: E402

W_KSN = 7
GAP = 2
THETA = 0.45
A_THRESHOLD_PX = 100
CAST_HALF = 12
RADIUS_PX = 1.5
SEED = 2026


def log(*a):
    print(*a, flush=True)


def main() -> int:
    out_dir = ROOT / "evidence"
    out_dir.mkdir(exist_ok=True)
    cache = Path("/tmp/study/work")

    with rasterio.open(ROOT / "data" / "geodawn_dem_a2_100m.tif") as ds:
        dem = ds.read(1).astype(np.float64)
        shape = ds.shape
    labels = rasterio.open(ROOT / "data" / "labels.tif").read(1)
    footprint = labels >= 0
    valid = footprint & (dem > -99999)
    dem = np.where(valid, dem, np.nan)

    if (cache / "filled.npy").exists():
        filled = np.load(cache / "filled.npy")
        down = np.load(cache / "down.npy")
        acc = np.load(cache / "acc.npy")
        chi = np.load(cache / "chi.npy")
    else:                                                       # pragma: no cover
        filled, _ = fill_depressions(dem, valid)
        down = d8_flow_directions(filled, valid)
        _, levels = bfs_levels(down, valid)
        acc = flow_accumulation(down, valid, levels)
        chi = chi_transform(down, acc, valid, shape, theta=THETA)
    log(f"[1/5] grid {shape}; routed (max acc {acc.max():,.0f} px)")

    chan = channel_mask(acc, valid, A_THRESHOLD_PX)
    profiles = extract_profiles(down, chan, acc, chi, valid, min_len=20)
    log(f"[2/5] {len(profiles):,} channel profiles, {int(chan.sum()):,} channel px")

    t = time.time()
    S = surface_statistics(profiles, chi, filled, shape, w_ksn=W_KSN, gap=GAP,
                           w_resid=61, min_profile_len=16)
    log(f"[3/5] surfaces built in {time.time()-t:.0f} s "
        f"(sigma defined on {int(np.isfinite(S['sigma']).sum()):,} px)")

    hd = build_holdout(catalogue=labels == 1, footprint=footprint, n_folds=4, buffer_px=3)
    comp = hd.component_ids
    withheld_all = np.zeros(shape, bool)
    for f in hd.folds:
        withheld_all |= f.withheld
    log(f"[4/5] holdout: {len(hd.folds)} folds, {hd.n_withheld_total:,} withheld px")

    # ---------------- Arm A vs position-matched control -----------------
    chan_flat = np.nonzero(np.isfinite(S["sigma"]))[0]
    cr, cc = np.unravel_index(chan_flat, shape)
    tree = cKDTree(np.c_[cr, cc].astype(float))
    acc_log = np.log10(np.maximum(acc[chan_flat], 1.0))
    sigma_c = S["sigma"][chan_flat]
    # area-matched control pool: bin channel pixels by log10(accumulation)
    bins = np.digitize(acc_log, np.linspace(2.0, 6.2, 22))

    rng = np.random.default_rng(SEED)
    per_fold, A_all, B_all = [], [], []
    for f in hd.folds:
        px = np.nonzero(f.withheld.ravel())[0]
        wy, wx = np.unravel_index(px, shape)
        hit = np.unique(_flat(tree.query_ball_point(np.c_[wy, wx].astype(float), r=RADIUS_PX)))
        a_val = sigma_c[hit]
        keep = np.isfinite(a_val)
        a_val, hit = a_val[keep], hit[keep]
        if a_val.size < 10:
            continue
        # matched control: 6 draws, same area bin, random position on a channel
        b_val = []
        for b in bins[hit]:
            pool = np.nonzero(bins == b)[0]
            if pool.size < 5:
                continue
            sel = rng.choice(pool, size=min(6, pool.size), replace=False)
            b_val.append(sigma_c[sel])
        b_val = np.concatenate(b_val) if b_val else np.zeros(0)
        b_val = b_val[np.isfinite(b_val)]
        if a_val.size < 10 or b_val.size < 10:
            continue
        A_all.append(a_val)
        B_all.append(b_val)
        u, p = stats.mannwhitneyu(a_val, b_val, alternative="greater")
        try:
            from sklearn.metrics import roc_auc_score
            auc_f = float(roc_auc_score(
                np.r_[np.ones(a_val.size), np.zeros(b_val.size)], np.r_[a_val, b_val]))
        except Exception:
            auc_f = float("nan")
        per_fold.append(dict(fold=f.name, n_crossing=int(a_val.size),
                             n_control=int(b_val.size),
                             mean_crossing=float(a_val.mean()),
                             mean_control=float(b_val.mean()),
                             median_crossing=float(np.median(a_val)),
                             median_control=float(np.median(b_val)),
                             delta_mean=float(a_val.mean() - b_val.mean()),
                             auc=auc_f, p_one_sided=float(p)))
        log(f"    {f.name}: nA={a_val.size:6d} nB={b_val.size:6d} "
            f"medA={np.median(a_val):+.4f} medB={np.median(b_val):+.4f} "
            f"AUC={auc_f:.4f} p={p:.3g}")

    A = np.concatenate(A_all)
    B = np.concatenate(B_all)
    u_all, p_all = stats.mannwhitneyu(A, B, alternative="greater")
    rng2 = np.random.default_rng(SEED + 1)
    nf = len(A_all)
    boot = np.array([(np.concatenate([A_all[j] for j in rng2.integers(0, nf, nf)]).mean()
                      - np.concatenate([B_all[j] for j in rng2.integers(0, nf, nf)]).mean())
                     for _ in range(2000)])
    ci = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
    auc_pool = float("nan")
    try:
        from sklearn.metrics import roc_auc_score
        n = min(A.size, B.size, 60000)
        auc_pool = float(roc_auc_score(np.r_[np.ones(n), np.zeros(n)], np.r_[A[:n], B[:n]]))
    except Exception:
        pass
    verdict_a = "proceed" if (p_all < 0.01 and ci[0] > 0) else "STOP"

    # ---------------- holdout AUC of the candidate surfaces ---------------
    res_auc = {}
    rng3 = np.random.default_rng(SEED + 2)
    for key in ("sigma", "resid"):
        vals = np.full(shape, np.nan)
        vals.ravel()[:] = S[key]
        pos = vals[withheld_all & np.isfinite(vals)]
        neg_all = vals[footprint & ~withheld_all & np.isfinite(vals)]
        if pos.size < 50 or neg_all.size < 50:
            res_auc[key] = None
            continue
        neg = neg_all if neg_all.size <= 20 * pos.size else rng3.choice(
            neg_all, size=20 * pos.size, replace=False)
        y = np.r_[np.ones(pos.size), np.zeros(neg.size)]
        x = np.r_[pos, neg]
        # the field must point the *right way*: a fault crossing puts a step, so
        # both large positive and large negative Sigma are informative; report
        # the signed AUC and the absolute-value AUC
        from sklearn.metrics import roc_auc_score
        res_auc[key] = dict(
            n_pos=int(pos.size), n_neg=int(neg.size),
            auc_signed=float(roc_auc_score(y, x)),
            auc_abs=float(roc_auc_score(y, np.abs(x))))
        log(f"    holdout AUC[{key}]: signed={res_auc[key]['auc_signed']:.4f} "
            f"abs={res_auc[key]['auc_abs']:.4f} (n_pos={pos.size:,})")

    # ---------------- channel-normal cast field -------------------------
    thr = float(np.nanpercentile(S["sigma"][chan_flat], 97.5))
    t = time.time()
    cast, n_cast = cast_field(profiles, chi, filled, shape, S["sigma"], threshold=thr,
                              cast_half_length_px=CAST_HALF, weight_mode="step")
    log(f"[5/5] cast field: threshold Sigma >= {thr:.4f}, {n_cast:,} casts, "
        f"{time.time()-t:.0f} s, max {cast.max():.2f}")
    pos = cast[withheld_all & footprint]
    neg_all = cast[footprint & ~withheld_all]
    neg = neg_all if neg_all.size <= 20 * pos.size else rng3.choice(
        neg_all, size=20 * pos.size, replace=False)
    from sklearn.metrics import roc_auc_score
    cast_auc = float(roc_auc_score(np.r_[np.ones(pos.size), np.zeros(neg.size)],
                                   np.r_[pos, neg]))
    log(f"    holdout AUC[cast]: {cast_auc:.4f} (n_pos={pos.size:,}, n_neg={neg.size:,})")

    result = dict(
        evidence_class="HOLDOUT-DTI", evaluator_version="gems60-exp2-v1",
        experiment="corrected first test: sharpened statistic + position-matched control",
        why_re_run=("Experiment 1's window was 31 samples = 3.1 km, ~10x the length of the "
                    "base-level step under test, and its control was an unrelated translated "
                    "line.  Both defects were named before this run; the rule is unchanged."),
        parameters=dict(window_samples=W_KSN, gap=GAP, theta_ref=THETA,
                        area_threshold_px=A_THRESHOLD_PX, cast_half_length_px=CAST_HALF,
                        cast_threshold_sigma=thr, radius_px=RADIUS_PX, seed=SEED),
        armA_vs_control=dict(
            n_crossing=int(A.size), n_control=int(B.size),
            mean_crossing=float(A.mean()), mean_control=float(B.mean()),
            median_crossing=float(np.median(A)), median_control=float(np.median(B)),
            delta_mean=float(A.mean() - B.mean()), ci95_delta=ci,
            auc=auc_pool, mannwhitney_U=float(u_all), p_one_sided=float(p_all),
            per_fold=per_fold),
        holdout_auc_surfaces=res_auc,
        cast_field=dict(auc=cast_auc, n_casts=int(n_cast),
                        threshold=thr, n_pos=int(pos.size), n_neg=int(neg.size),
                        max_value=float(cast.max())),
        predeclared_rule="proceed iff p_one_sided < 0.01 AND ci95_delta lower bound > 0",
        verdict=verdict_a,
    )
    (out_dir / "exp2_sharpened.json").write_text(json.dumps(result, indent=1))
    np.save(cache / "sigma.npy", S["sigma"])
    np.save(cache / "resid.npy", S["resid"])
    np.save(cache / "ksn7.npy", S["ksn"])
    np.save(cache / "cast.npy", cast)
    log("\narm A vs matched control: " + json.dumps(
        {k: v for k, v in result["armA_vs_control"].items() if k != "per_fold"}, indent=1))
    log("VERDICT: " + verdict_a)
    return 0


def _flat(hits):
    parts = [np.asarray(h, dtype=np.int64).ravel() for h in hits if len(h)]
    if not parts:
        return np.zeros(0, dtype=np.int64)
    return np.concatenate(parts).astype(np.int64)


if __name__ == "__main__":
    raise SystemExit(main())
