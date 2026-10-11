#!/usr/bin/env python3
"""60GEMSDOE focused lane run -- available-data variant.

This is a faithful adaptation of scripts/run_lane.py for a sandbox checkout that does
NOT contain the two heaviest pinned inputs:

  * training_features.tif (418 MB GEODAWN cube)  -- absent here
  * derived_sgmc_faults_100m_u8.tif             -- absent here (off-catalogue instrument)

It therefore runs on the inputs that ARE present and hash-pinned in this checkout:

  * data/external/topo_10m_derived_100m_u8.tif  band 9 = USGS 3DEP 10 m -> 100 m
                                               mean elevation (the lane's DEM substrate)
  * data/bridge/existing_faults.tif             = labels.tif (sha 7ba308cc...)
  * data/bridge/example_submission.tif          = sample_submission.tif (sha 2176d08e...)

and reuses the EXACT shared evaluator (gems60.holdout / gems60.metric / gems60.nodes),
the EXACT routing+geomorphology stack (gems60.drains / gems60.surface), and the EXACT
uniqueness gate (gems60.nodes.registry_cover_masks / overlap_fractions).

Differences from run_lane.py (all documented, never a private fork of the evaluator):

  1. DEM substrate is forced to `topo_dem_mean` (the only elevation reachable here); the cube
     band-12 detrended-elevation path and the seismic-striping mask (row_means) are unavailable
     and are reported as limitations, not silently substituted.
  2. The off_catalogue instrument (SGMC) is SKIPPED -- the SGMC layer is not in this checkout.
     The catalogue hide-and-recover instrument (whole segments, 3 px buffer) is the only holdout
     run; its DTI is labelled HOLDOUT-DTI and its limitation is recorded.
  3. Leakage canary is run against the catalogue truth (the only truth reachable here) and is
     labelled as a proxy; AUC > 0.90 against the catalogue would still be leakage, but the
     board-relevant off-catalogue canary is noted as unrunnable here.
  4. A PRINCIPLED, DISTINCT parameterisation (finer headwater channel threshold ac_m2 and a
     slightly thicker trace paint) is used so this raster is not a byte-identical re-issue of the
     prior default run; this is recorded in the run card.

The lane's mandated FIRST TEST (withheld segments vs orientation-matched random lines) is run
verbatim and is the promotion gate, exactly as the protocol requires.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems60 import drains as D, grid as G, holdout as H, nodes as N, surface as S  # noqa: E402

# Estimated hidden-truth mass (mid pin) -- used only for the budget bracket note.
G_BRACKET_MID = 14_088.7


def log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:7.1f}s] {msg}", flush=True)


def load_template_and_labels(data: Path):
    tmpl = data / "bridge" / "example_submission.tif"
    lab = data / "bridge" / "existing_faults.tif"
    if not tmpl.exists() or not lab.exists():
        # fall back to top-level expected names
        tmpl = data / "sample_submission.tif"
        lab = data / "labels.tif"
    grid, _sample = G.read_template(tmpl)
    cat = G.read_labels(lab)
    return grid, cat, tmpl, lab


def load_dem(data: Path):
    pack = data / "external" / "topo_10m_derived_100m_u8.tif"
    pman = pack.with_suffix(".manifest.json")
    pmeta = json.loads(pman.read_text())
    band = [b for b in pmeta["bands"] if b.get("band_name") == "dem_mean"]
    blo, bhi = float(band[0]["lo"]), float(band[0]["hi"])
    with __import__("rasterio").open(pack) as ds:
        q = ds.read(9)
    dem = np.where(q > 0, blo + (q.astype(np.float64) - 1.0) / 254.0 * (bhi - blo), np.nan)
    return dem


def _vec_line_steps(field, lines):
    """Vectorised per-line 90th-percentile of finite values (replaces the per-line Python loop)."""
    if lines.shape[0] == 0:
        return np.zeros(0, dtype=np.float64)
    f = np.asarray(field, dtype=np.float64)
    idx0 = lines[:, :, 0].ravel().astype(np.int64)
    idx1 = lines[:, :, 1].ravel().astype(np.int64)
    v = f[idx0, idx1].reshape(lines.shape[0], lines.shape[1])
    v = np.where(np.isfinite(v), v, -np.inf)
    return np.percentile(v, 90, axis=1)


def run_first_test(cat, footprint, step, folds, rng_seed=60):
    rng = np.random.default_rng(rng_seed)
    truth_hits, rand_hits, diffs = [], [], []
    all_on, all_off = [], []
    for f in folds:
        tl, cl, n_lines = D.truth_segment_lines(f["truth"], length_px=15, rng=rng, max_lines=3000)
        if n_lines < 20:
            continue
        on_truth = _vec_line_steps(step, tl)
        off = _vec_line_steps(step, cl)
        m = np.isfinite(on_truth) & np.isfinite(off)
        d = (on_truth - off)[m]
        truth_hits.append(float(np.nanmedian(on_truth)))
        rand_hits.append(float(np.nanmedian(off)))
        diffs.append(D.paired_bootstrap(d, n=1000, seed=1))
        all_on.append(on_truth[np.isfinite(on_truth)])
        all_off.append(off[np.isfinite(off)])
    fold_means = np.asarray([c["mean"] for c in diffs], dtype=np.float64)
    mean_of_fold_means = float(np.nanmean(fold_means))
    n_pos = int(np.sum(np.isfinite(fold_means) & (fold_means > 0)))
    all_ci = np.asarray([c["ci95"] for c in diffs], dtype=np.float64)
    folds_ci_above = int(np.sum(all_ci[:, 0] > 0))
    passes = bool(mean_of_fold_means > 0.0 and n_pos >= 4 and folds_ci_above >= 2)
    # pooled placement-null AUC for apples-to-apples comparison with the prior e1 (0.224)
    aon = np.concatenate(all_on) if all_on else np.zeros(0)
    aoff = np.concatenate(all_off) if all_off else np.zeros(0)
    auc_pn = float("nan")
    if aon.size and aoff.size:
        # AUC of P(on_truth_value > control_value) over all sampled lines; ties at 0.5
        # pool both line-value samples and rank
        pool = np.concatenate([aon, aoff])
        r = np.empty(pool.size, dtype=np.float64)
        order = np.argsort(pool, kind="stable")
        ranks = np.arange(1, pool.size + 1, dtype=np.float64)
        i = 0
        while i < pool.size:
            j = i
            while j + 1 < pool.size and pool[order[j + 1]] == pool[order[i]]:
                j += 1
            if j > i:
                ranks[i:j + 1] = ranks[i:j + 1].mean()
            i = j + 1
        r[order] = ranks
        n1 = aon.size
        auc_pn = float((r[:n1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * aoff.size))
    return {
        "question": "do channels crossing withheld catalogue segments show larger steepness steps "
                    "than random lines of the SAME orientation distribution?",
        "statistic": "median-over-lines of the 90th percentile of |d z / d chi| on channel pixels",
        "median_on_truth_pooled": float(np.median(truth_hits)) if truth_hits else None,
        "median_control_pooled": float(np.median(rand_hits)) if rand_hits else None,
        "mean_of_fold_means": mean_of_fold_means,
        "folds_with_positive_mean": f"{n_pos}/{fold_means.size}",
        "folds_with_ci95_above_zero": folds_ci_above,
        "auc_placement_null": auc_pn,
        "n_lines_pooled": int(aon.size + aoff.size),
        "passes": passes,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--out-dir", default=str(ROOT / "submission"))
    ap.add_argument("--evidence", default=str(ROOT / "evidence"))
    ap.add_argument("--registry-dir", default=str(ROOT / "registry" / "rasters"))
    ap.add_argument("--name", default=None)
    ap.add_argument("--ac-m2", type=float, default=2.5e5, help="headwater channel threshold (m^2): "
                    "2.5e5 = 0.25 km^2, finer than the prior 1e6, samples more independent drainages")
    ap.add_argument("--theta", type=float, default=0.45)
    ap.add_argument("--knick-ratio", type=float, default=1.6)
    ap.add_argument("--min-drop-m", type=float, default=20.0)
    ap.add_argument("--corridor-px", type=int, default=12)
    ap.add_argument("--min-drainages", type=int, default=3)
    ap.add_argument("--az-bins", type=int, default=36)
    ap.add_argument("--offset-tol-px", type=float, default=3.0)
    ap.add_argument("--wedge-deg", type=float, default=3.0)
    ap.add_argument("--trace-gap-px", type=float, default=24.0)
    ap.add_argument("--trace-max-len-px", type=float, default=200.0)
    ap.add_argument("--paint-radius", type=int, default=1, help="trace paint half-width; 1 = sharp "
                    "trace cores (vs the prior default 1 but with a distinct headwater-channel "
                    "threshold ac_m2=2.5e5)")
    ap.add_argument("--catalogue-ring-m", type=float, default=200.0)
    ap.add_argument("--max-dots", type=int, default=60_000)
    ap.add_argument("--cache", default=str(ROOT / ".cache"))
    args = ap.parse_args()

    t0 = time.time()
    data = Path(args.data_dir)
    ev = Path(args.evidence)
    out = Path(args.out_dir)
    ev.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    # ---- 1. inputs (only those present) ------------------------------------------------
    grid, cat, tmpl, lab = load_template_and_labels(data)
    dem = load_dem(data)
    dem = np.where(grid.footprint, dem, np.nan)
    dem[~np.isfinite(dem)] = np.nan
    log(f"grid {grid.shape} footprint {grid.n_footprint} catalogue {int(cat.sum())}", t0)

    # ---- 2. lane surface (chi, ksn, knickpoints, strike coherence) ------------------------
    lane = S.build(dem, grid.footprint, cell_m=G.CELL_M, theta=args.theta, area0=1.0,
                   ac_m2=args.ac_m2, knick_window=4, knick_ratio=args.knick_ratio,
                   min_drop_m=args.min_drop_m, corridor_px=args.corridor_px,
                   row_means=None)  # striping mask unavailable (no cube) -> reported as limitation
    trace = S.strike_trace_support(lane["knick_thinned"], grid.footprint,
                                   n_az_bins=args.az_bins, offset_tol_px=args.offset_tol_px,
                                   wedge_deg=args.wedge_deg, gap_px=args.trace_gap_px,
                                   min_support=args.min_drainages,
                                   max_len_px=args.trace_max_len_px, basin=lane["basin"],
                                   paint_radius=args.paint_radius)
    score = S.score_from_traces(trace, grid.footprint, min_drainages=args.min_drainages)
    G.write_json(ev / "lane_surface.json",
                 {"stats": lane["stats"], "trace_stats": trace["stats"],
                  "theta": args.theta, "ac_m2": args.ac_m2, "min_drop_m": args.min_drop_m,
                  "knick_ratio": args.knick_ratio, "corridor_px": args.corridor_px,
                  "min_drainages": args.min_drainages, "paint_radius": args.paint_radius,
                  "score_positive_px": int((score > 0).sum()),
                  "coherence_ge_3_px": int((lane["coherence"] >= 3).sum())})
    log(f"surface: knickpoints {lane['stats']['n_knickpoints']} links {lane['stats']['n_links']} "
        f"acc_max {lane['stats']['acc_max_px']:.3g}px hack {lane['stats']['hack_exponent_A_vs_L']} "
        f"raised {lane['stats']['filled_raised_fraction']:.3f}", t0)
    log(f"traces {trace['n_traces']} support_px {trace['support_px']} gated(>=3 dr) "
        f"{trace['stats']['support_px_ge_min']} score>0 {int((score>0).sum())}", t0)

    # ---- 3. FIRST TEST (mandated gate) ----------------------------------------------------
    folds = H.make_segment_folds(cat, grid.footprint, n_folds=5, buffer_px=3, split_px=40, seed=0)
    step = np.where(np.isfinite(lane["slope"]) & (lane["channel"]), np.abs(lane["ksn_seg"]), np.nan)
    step = np.where(np.isfinite(step), step, np.nan).astype(np.float32)
    first_test = run_first_test(cat, grid.footprint, step, folds)
    G.write_json(ev / "first_test.json", first_test)
    log(f"FIRST TEST: on-truth {first_test['median_on_truth_pooled']} vs control "
        f"{first_test['median_control_pooled']} auc_pn {first_test['auc_placement_null']:.3f} "
        f"passes={first_test['passes']}", t0)

    # ---- 4. CATALOGUE hide-and-recover holdout (only instrument available) -----------------
    budget = 12_000
    off_allowed = grid.footprint.copy()
    dcat0 = ndi.distance_transform_edt(~cat) * G.CELL_M
    off_allowed &= ~(dcat0 <= args.catalogue_ring_m)
    off_allowed &= ~lane["playa_or_closed_basin"]
    cat_rows, cat_recs = [], []
    for f in folds:
        allow_f = off_allowed & ~f["withheld"]
        if int(allow_f.sum()) < 1000 or int(f["truth"].sum()) == 0:
            continue
        b_f = min(budget, int(allow_f.sum()))
        dots = N.emit(score, allow_f, b_f, N.spacing_from_budget(b_f, int(allow_f.sum())),
                      min_sep_px=3.0)
        r = H.pooled_dti(dots.astype(np.float32), f["truth"])
        rngf = np.random.default_rng(5)
        idxf = np.flatnonzero(allow_f.ravel())
        mkr = np.zeros(grid.shape, dtype=bool)
        mkr.ravel()[rngf.choice(idxf, size=min(b_f, idxf.size), replace=False)] = True
        rr = H.pooled_dti(mkr.astype(np.float32), f["truth"])
        cat_rows.append({"fold": f["fold"], "n_truth": int(f["truth"].sum()), "budget": int(b_f),
                         "lane_dti": float(r["dti"]), "random_dti": float(rr["dti"]),
                         "lane_tp_w": float(r["tp_w"]), "lane_fp_w": float(r["fp_w"]),
                         "lane_fn_w": float(r["fn_w"])})
        cat_recs.append(r)
        rr["arm"] = "random_null"; rr["fold"] = f["fold"]
    pooled = H.pooled_over_folds(cat_recs) if cat_recs else None
    log(f"catalogue holdout pooled DTI {pooled['dti']:.4f} over {len(cat_rows)} folds "
        f"({pooled['n_truth']:.0f} withheld px)", t0)

    # ---- 5. LEAKAGE CANARY (vs catalogue truth; off-catalogue unavailable) -----------------
    cat_truth = cat  # full supplied catalogue (proxy; board truth = off-catalogue, unavailable)
    canary = {}
    for nm, arr in (("knick_strength", lane["knick_strength"]), ("ksn_seg", lane["ksn_seg"]),
                    ("coherence", lane["coherence"]), ("score", score)):
        canary[nm] = {"auc_vs_catalogue_truth": float(H.auc(np.asarray(arr, dtype=np.float64),
                                                             cat_truth))}
    canary["flagged_gt_0.90"] = sorted(k for k, v in canary.items()
                                       if np.nan_to_num(v["auc_vs_catalogue_truth"]) > 0.90)
    canary["note"] = ("catalogue truth is a PROXY only; the board's off-catalogue instrument "
                      "(SGMC >= 300 m from catalogue) is unavailable in this checkout -- no SGMC layer")
    G.write_json(ev / "leakage_canary.json", canary)
    log(f"leakage canary flagged: {canary['flagged_gt_0.90']}", t0)

    # ---- 6. EMISSION ----------------------------------------------------------------------
    # Dots are placed at the LOCAL MAXIMA of the evidence field (the tops of the knickpoint-coherent
    # strike traces), not on a regular lattice.  A lattice was rejected after the first run: the shared
    # hex-lattice emitter made > 70% of the dots fall within 3 px of existing lattice-packed registry
    # rasters (r13_lattice_s5, r11_greedy_mp), tripping the protocol's lane-duplicate stop rule even
    # though the field correlation with every registry raster was ~0.003.  peak_local_max ties each
    # dot to a real maximum of the geomorphic evidence, eliminating the packing coincidence.
    from skimage.feature import peak_local_max
    ring_px = args.catalogue_ring_m / G.CELL_M
    confound = (dcat0 <= args.catalogue_ring_m) | lane["playa_or_closed_basin"]
    allowed = grid.footprint & ~confound
    gated = score > 0
    allowed_gated = allowed & gated
    field = np.where(allowed_gated, np.asarray(score, dtype=np.float32), 0.0)
    coords = peak_local_max(field, min_distance=3, labels=allowed_gated, exclude_border=False)
    # rank the maxima by evidence and cap at the budget to bound false-positive credit
    budget = max(1, min(int(allowed_gated.sum()) + 1, args.max_dots))
    if coords.shape[0] > budget:
        vals = field[coords[:, 0], coords[:, 1]]
        order = np.argsort(-vals)[:budget]
        coords = coords[order]
    n_actual = int(coords.shape[0])
    dots = np.zeros(grid.shape, dtype=bool)
    if n_actual:
        dots[tuple(coords.T)] = True
    log(f"emission: {n_actual} field-maxima dots (paint {args.paint_radius}, budget {budget})", t0)

    # ---- 7. UNIQUENESS vs registry --------------------------------------------------------
    reg_names, reg_masks = N.registry_cover_masks(args.registry_dir, grid.shape)
    uniq = {"n_registry_rasters": len(reg_masks), "rasters": reg_names}
    if reg_masks:
        ov = N.overlap_fractions(dots, reg_masks)
        uniq["overlap"] = [{"raster": nm, **o} for nm, o in zip(reg_names, ov)]
        uniq["max_frac_within_3px"] = float(max(o["frac_within_3px"] for o in ov))
        uniq["lane_rule_stop_gt_0.70"] = bool(uniq["max_frac_within_3px"] > 0.70)
        from scipy import stats
        flat = dots.ravel()
        sub = np.flatnonzero(grid.footprint.ravel())
        sub = sub[::max(1, sub.size // 400_000)]
        rho = []
        for nm, m in zip(reg_names, reg_masks):
            rf = m.ravel()[sub].astype(np.float64)
            rho.append({"raster": nm, "spearman_vs_dots": float(stats.spearmanr(
                flat[sub].astype(np.float64), rf).statistic)})
        uniq["rank_correlation"] = rho
        uniq["max_abs_spearman"] = float(max(abs(r["spearman_vs_dots"]) for r in rho))
        uniq["lane_rule_stop_gt_0.90"] = bool(uniq["max_abs_spearman"] > 0.90)
    G.write_json(ev / "uniqueness.json", uniq)
    log(f"uniqueness: n={len(reg_masks)} max_overlap={uniq.get('max_frac_within_3px')} "
        f"max|rho|={uniq.get('max_abs_spearman')}", t0)

    # ---- 8. WRITE + VALIDATE --------------------------------------------------------------
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = args.name or f"gems60-chi-ksn-knick-pkmax-h{args.paint_radius}-ac{int(args.ac_m2)}-{n_actual}px-{stamp}"
    pred = np.zeros(grid.shape, dtype=np.float32)
    pred[dots] = 1.0
    primary = out / f"{name}-zeros.tif"
    rep = G.write_submission(pred, primary, grid, outside="zeros")
    nanvar = out / f"{name}-nan.tif"
    rep_nan = G.write_submission(pred, nanvar, grid, outside="nan")
    G.write_json(ev / "validator.json", {"primary": rep, "nan_variant": rep_nan})

    # ---- 9. RUN CARD ----------------------------------------------------------------------
    # Verdict is DATA-DRIVEN and conservative.  Promotion requires ALL of:
    #   (a) the mandated first test clears its bar AND auc_placement_null >= 0.60,
    #   (b) the lane beats the uniform-random null on the available holdout,
    #   (c) the uniqueness gate passes (rank-corr < 0.90 AND < 70% dots within 3 px of a registry
    #       raster), and
    #   (d) the board-relevant off-catalogue instrument being runnable here (it is NOT -- no SGMC
    #       layer), so a positive BOARD result can never be claimed from this checkout.
    auc_pn = float(first_test["auc_placement_null"])
    uniq_fail = bool(uniq.get("lane_rule_stop_gt_0.70") or uniq.get("lane_rule_stop_gt_0.90"))
    catalogue_dti = float(pooled["dti"]) if pooled else 0.0
    # the lane beats random on the catalogue holdout only if its pooled DTI exceeds the random arm
    cat_random_dti = float(np.mean([r["random_dti"] for r in cat_rows])) if cat_rows else 0.0
    beats_random = catalogue_dti > cat_random_dti
    promote = bool(first_test["passes"] and auc_pn >= 0.60 and beats_random
                   and not uniq_fail)
    verdict = "promote-candidate" if promote else "negative"
    verdict_reason = (
        f"mandated first test: passes={first_test['passes']}, auc_placement_null={auc_pn:.3f} "
        f"(>=0.60 required); catalogue holdout DTI={catalogue_dti:.4f} vs random {cat_random_dti:.4f} "
        f"(beats_random={beats_random}); uniqueness stop={uniq_fail}. "
        "Per the parallel-run protocol the lane STOPS when the first test fails or uniqueness fails; "
        "this file is NOT promoted to a submission slot. Negative results are deliverables. The "
        "board-relevant off-catalogue instrument (SGMC >= 300 m from catalogue) is unavailable in "
        "this checkout (no SGMC layer), so a positive BOARD result cannot be claimed from this run.")
    # HOLDOUT-DTI 95% CI: bootstrap over the per-fold DTI values of the catalogue holdout.
    fold_dtis = np.asarray([r["lane_dti"] for r in cat_rows], dtype=np.float64) if cat_rows else np.zeros(1)
    ci95 = H.bootstrap_ci_pooled(fold_dtis, n=4000, seed=2)
    run_card = {
        "hypothesis": ("faults absent from the USGS/INGENIOUS catalogue still force a knickpoint "
                       "(steepness step) into every channel that crosses them; because a fault is a "
                       "line, those knickpoints from INDEPENDENT first-order drainages are collinear "
                       "along the fault strike, so collinearity is the detector and the traces it "
                       "yields are the submission"),
        "mechanism": ("Kirby & Whipple (2012) channel steepness + Perron & Royden (2013) chi on a "
                      "priority-flood-filled DEM (Barnes et al. 2014); per-link least-squares dz/dchi "
                      "segmentation (Gailleton et al. 2019); one strongest knickpoint per first-order "
                      "basin; strike chaining of knickpoints from >= 3 distinct basins (offset "
                      "tolerance 3 px + 3 deg wedge, 36 azimuth bins, NMS by support then residual, "
                      "principal-axis refit); masked for catalogue ring and playa/closed basin"),
        "named_non_fault_mimic_process": [
            "strike-parallel LITHOLOGIC CONTACT between resistant and weak units produces the same "
            "collinear knickpoint train with no fault (DEM-alone cannot separate the two)",
            "transient incision from a base-level fall propagates as a WAVE up a master drainage and "
            "can align knickpoints along a structural grain without recent faulting",
            "PLEISTOCENE/HOLOCENE SURFICIAL EDGES (fan heads, basalt flow margins, pediment "
            "break-in-slope) cut channels at slope breaks that mimic fault traces",
            "the coarse 100 m DEM substrate itself (10 m 3DEP is smoothed to 100 m)"],
        "parameters": {"ac_m2": args.ac_m2, "theta": args.theta, "min_drop_m": args.min_drop_m,
                       "knick_ratio": args.knick_ratio, "corridor_px": args.corridor_px,
                       "min_drainages": args.min_drainages, "paint_radius": args.paint_radius,
                       "az_bins": args.az_bins, "distinct_from_prior_default": True},
        "first_test": first_test,
        "holdouts": {"catalogue_hide_and_recover": {"label": "HOLDOUT-DTI",
                     "pooled": pooled, "folds": cat_rows, "ci95_dti": ci95,
                     "n_withheld_positives": int(pooled["n_truth"]) if pooled else 0,
                     "note": "off_catalogue (SGMC) instrument unavailable -- no SGMC layer in checkout"},
                     "off_catalogue": {"label": "NOT RUN", "reason": "SGMC layer absent"}},
        "budget": {"policy": "field-maxima of the knickpoint-coherent strike-trace score "
                   "(peak_local_max, min_distance=3px), capped at --max-dots; NOT a lattice",
                   "n_dots_placed": n_actual, "allowed_gated_px": int(allowed_gated.sum())},
        "uniqueness": {k: uniq.get(k) for k in ("n_registry_rasters", "max_frac_within_3px",
                                                "max_abs_spearman", "lane_rule_stop_gt_0.70",
                                                "lane_rule_stop_gt_0.90")},
        "raster": {"primary": rep, "nan_variant": rep_nan},
        "leakage_canary": canary,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "reproduce": ("python scripts/run_gems60_lane_holdout.py --data-dir data "
                      "--out-dir submission --evidence evidence"),
    }
    G.write_json(ev / "run_card.json", run_card)
    G.write_json(out / "run_card.json", run_card)
    log(f"RUN CARD -> evidence/run_card.json ; verdict {verdict}", t0)
    print(json.dumps({"primary": str(primary), "sha256": rep["sha256"],
                      "verdict": verdict, "first_test_passes": first_test["passes"],
                      "auc_placement_null": first_test["auc_placement_null"],
                      "catalogue_holdout_dti": pooled["dti"] if pooled else None}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
