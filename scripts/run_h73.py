#!/usr/bin/env python3
"""H73-1 paired-basin ksn contrast: feature, gates, holdout and production build.

Preregistered in ``registry/preregistration-h73.json`` before measurement. This
runner reuses the shared holdout/evaluator, lane corridor builder and submission
writer. It deliberately has no call to the historical H65 stop guard: H73 is a
new, dual-population-gated basin-scale statistic, not a rerun of H65's local
step statistic. The historical STOP remains in the registry and is not edited.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_lane60 as RL  # noqa: E402
from run_h66 import run_e1_offcat  # noqa: E402
from gems57 import evaluate_holdout as EH  # noqa: E402
from gems57 import grid as G57  # noqa: E402
from gems57 import holdout as HO  # noqa: E402
from gems57 import submission_writer as SW  # noqa: E402
from gems60 import geomorph as GM  # noqa: E402
from gems60 import lane as L  # noqa: E402
from gems61 import dataio, instruments as I  # noqa: E402

EXT = ROOT / "data" / "external"
CACHE = ROOT / ".cache" / "features73"
EVID = ROOT / "evidence"
PREREG = ROOT / "registry" / "preregistration-h73.json"
LATTICE = ROOT / "registry" / "rasters" / "calib_r13lattice_00904.tif"
H68_BEST = 0.171894
TOTAL = 20_000
PRIMARY = 13_800
NOVELTY = 6_200
LOW_VALUE = np.float32(0.05)
BOOT_DRAWS = 1_000
BOOT_SEED = 60_101
DENSITY = TOTAL / 5_106_385
STAMP = "20261011T200117Z"
SLUG = f"gems60-h73-paired-basin-ksn-{TOTAL}-{STAMP}-zeros"
OUT = ROOT / "docs" / "downloads" / f"{SLUG}.tif"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    return o


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), indent=2, allow_nan=False) + "\n")


def pin_check() -> dict:
    manifest = json.loads((EXT / "dem10_chi_100m.manifest.json").read_text())
    rows = {}
    for name, expected in manifest["files"].items():
        path = EXT / name
        got = sha256(path)
        if got != expected["sha256"]:
            raise SystemExit(f"source pin mismatch: {name}: {got} != {expected['sha256']}")
        rows[name] = got
    return {"manifest": "data/external/dem10_chi_100m.manifest.json", "files": rows,
            "tiles": len(manifest["source"]["tiles"]), "blocks_ok": manifest["blocks_ok"],
            "blocks_total": manifest["blocks_total"]}


def weighted_gaussian(values: np.ndarray, mask: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray]:
    w = np.asarray(mask, np.float32)
    num = ndi.gaussian_filter(np.where(mask, values, 0.0).astype(np.float32), sigma=sigma)
    den = ndi.gaussian_filter(w, sigma=sigma)
    out = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-6)
    return out.astype(np.float32), den.astype(np.float32)


def build_features(force: bool = False) -> dict:
    required = [CACHE / f"{name}.npy" for name in
                ("stat", "raw_geo", "channel", "branch", "exclude", "ksn", "dksn",
                 "basin_contrast", "footprint", "catalogue", "lattice_holes")]
    receipt_path = EVID / "h73_feature_cache.json"
    if not force and receipt_path.is_file() and all(p.is_file() for p in required):
        return json.loads(receipt_path.read_text())

    t0 = time.time()
    pins = pin_check()
    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue
    with rasterio.open(EXT / "dem10_chi_100m_i16.tif") as src:
        nod = src.nodata
        raw = src.read()
    step_i, ksn_i, loga_i, zmean_i = raw[0], raw[2], raw[3], raw[4]
    step = np.where(step_i == nod, np.nan, step_i.astype(np.float32) / 1000.0)
    ksn = np.where(ksn_i == nod, np.nan, ksn_i.astype(np.float32))
    loga = np.where(loga_i == nod, np.nan, loga_i.astype(np.float32) / 1000.0)
    zmean = np.where(zmean_i == nod, np.nan, zmean_i.astype(np.float32))
    del raw, step_i, ksn_i, loga_i, zmean_i
    with rasterio.open(EXT / "dem10_chi_100m_sig_i32.tif") as src:
        sig = src.read(1).astype(np.int64)
    with rasterio.open(EXT / "dem10_chi_100m_u8.tif") as src:
        u = src.read()
    raised_n = u[2].astype(np.int16)
    valid_n = u[3].astype(np.int16)
    del u

    channel_all = fp & np.isfinite(step) & np.isfinite(ksn)
    ephemeral = channel_all & (ksn < 10.0)
    playa = fp & (raised_n >= 50)

    # K/Th gradients are lithologic-contact proxies, not map-unit truth.
    with rasterio.open(EXT / "geodawn_rad_u8.tif") as src:
        krad = src.read(1).astype(np.float32)
        th = src.read(2).astype(np.float32)
    def grad(v):
        vv = np.where((v > 0) & fp, v, np.nan)
        fill = np.where(np.isfinite(vv), vv, float(np.nanmedian(vv[fp]))).astype(np.float32)
        gy, gx = np.gradient(ndi.gaussian_filter(fill, sigma=1.0))
        return np.hypot(gy, gx).astype(np.float32)
    gk, gt = grad(krad), grad(th)
    zgk = GM.blockwise_zscore(gk, fp, block_px=400)
    zgt = GM.blockwise_zscore(gt, fp, block_px=400)
    rad_contact = fp & ((np.nan_to_num(zgk, nan=-9.0) > 1.645) |
                        (np.nan_to_num(zgt, nan=-9.0) > 1.645))
    rad_contact = fp & ndi.binary_dilation(rad_contact, iterations=2)
    del krad, th, gk, gt, zgk, zgt

    exclude = playa | ephemeral | rad_contact
    channel = channel_all & ~exclude
    logk = np.log1p(np.maximum(ksn, 0.0)).astype(np.float32)
    basin, support = weighted_gaussian(logk, channel, 8.0)
    gy, gx = np.gradient(basin)
    basin_contrast = (np.hypot(gy, gx) * np.minimum(1.0, support / 0.08)).astype(np.float32)
    del basin, gy, gx

    ku = np.maximum(ksn, 0.0)
    kd = np.maximum(0.0, (ku + 0.5) * np.exp(-np.clip(step, -2.3, 2.3)) - 0.5)
    dksn = (np.log1p(np.maximum(ku - kd, 0.0)) -
            np.log1p(np.maximum(kd - ku, 0.0))).astype(np.float32)
    step_support, _ = weighted_gaussian(np.maximum(dksn, 0.0), channel, 2.0)
    z_basin = GM.blockwise_zscore(basin_contrast, channel, block_px=400)
    z_step = GM.blockwise_zscore(step_support, channel, block_px=400)
    raw_geo = (0.70 * np.nan_to_num(z_basin, nan=0.0) +
               0.30 * np.nan_to_num(z_step, nan=0.0)).astype(np.float32)
    stat = np.where(channel, raw_geo, np.nan).astype(np.float32)

    own = np.arange(fp.size, dtype=np.int64).reshape(fp.shape)
    branch = np.where(channel & (sig >= 0), sig, own + fp.size).astype(np.int64)
    with rasterio.open(LATTICE) as src:
        lattice_arr = src.read(1)
    lattice_dots = np.isfinite(lattice_arr) & (lattice_arr > 0)
    del lattice_arr
    lattice_holes = fp & (ndi.distance_transform_edt(~lattice_dots) > 3.0)

    CACHE.mkdir(parents=True, exist_ok=True)
    arrays = dict(stat=stat, raw_geo=raw_geo, channel=channel, branch=branch,
                  exclude=exclude, ksn=ksn.astype(np.float32), dksn=dksn,
                  basin_contrast=basin_contrast, footprint=fp, catalogue=cat,
                  lattice_holes=lattice_holes, support=support, loga=loga,
                  zmean=zmean, valid_n=valid_n)
    files = []
    for name, arr in arrays.items():
        path = CACHE / f"{name}.npy"
        np.save(path, arr)
        files.append({"name": name, "dtype": str(arr.dtype), "sha256": sha256(path)})
    receipt = {
        "evidence_class": "DATA-MEASUREMENT", "hypothesis": "H73-1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "preregistration": "registry/preregistration-h73.json", "source_pins": pins,
        "diagnostics": {
            "footprint_px": int(fp.sum()), "catalogue_px": int(cat.sum()),
            "channel_all_px": int(channel_all.sum()), "bedrock_unmasked_channel_px": int(channel.sum()),
            "ephemeral_px": int(ephemeral.sum()), "playa_px": int(playa.sum()),
            "radiometric_contact_px": int(rad_contact.sum()), "excluded_px": int(exclude.sum()),
            "candidate_z_ge_0p5_px": int((channel & (raw_geo >= 0.5)).sum()),
            "lattice_holes_in_footprint": int(lattice_holes.sum()),
            "lattice_holes_off_catalogue": int((lattice_holes & ~cat).sum()),
            "stat_p50": float(np.nanpercentile(stat[channel], 50)),
            "stat_p95": float(np.nanpercentile(stat[channel], 95)),
            "basin_contrast_p95": float(np.nanpercentile(basin_contrast[channel], 95)),
            "distinct_branches": int(np.unique(branch[channel]).size),
            "seconds": round(time.time() - t0, 2)
        }, "files": files
    }
    write_json(receipt_path, receipt)
    return receipt


def load(name: str):
    return np.load(CACHE / f"{name}.npy")


def select_weighted(score: np.ndarray, geology: np.ndarray, allowed: np.ndarray,
                    holes: np.ndarray, total: int, primary_n: int, novelty_n: int,
                    seed: int) -> tuple[np.ndarray, dict]:
    """Preregistered two-confidence placement; no output clipping or repair."""
    if primary_n + novelty_n != total:
        raise ValueError("primary + novelty must equal total")
    primary_allowed = allowed & ~holes
    primary = L.top_k_dots(score, primary_allowed, primary_n, seed=seed, min_sep_px=3.0)
    if int(primary.sum()) != primary_n:
        raise RuntimeError(f"only {int(primary.sum())} of {primary_n} primary cells available")
    nov_allowed = allowed & holes & ~primary
    idx = np.flatnonzero(nov_allowed.ravel())
    if idx.size < novelty_n:
        # A cropped holdout cell can contain fewer lattice holes than its scaled quota.
        # The deficit is filled with additional low-confidence geological support and
        # disclosed; production is required to meet the exact preregistered quota.
        inside = idx
        deficit = novelty_n - idx.size
        extra_pool = np.flatnonzero((allowed & ~primary & ~nov_allowed).ravel())
        order_extra = np.argsort(-geology.ravel()[extra_pool], kind="stable")[:deficit]
        idx = np.concatenate([inside, extra_pool[order_extra]])
        hole_deficit = deficit
    else:
        order = np.argsort(-geology.ravel()[idx], kind="stable")[:novelty_n]
        idx = idx[order]
        hole_deficit = 0
    if idx.size != novelty_n:
        raise RuntimeError("novelty placement did not meet declared budget")
    pred = np.zeros(score.shape, np.float32)
    pred[primary] = np.float32(1.0)
    pred.ravel()[idx] = LOW_VALUE
    return pred, {"total_positive": int((pred > 0).sum()), "primary": int((pred == 1).sum()),
                  "low_confidence": int((pred == LOW_VALUE).sum()),
                  "low_confidence_value": float(LOW_VALUE),
                  "low_confidence_hole_deficit": int(hole_deficit),
                  "weighted_mass": float(pred.sum())}


def build_fold_score(z: np.ndarray, cand: np.ndarray, branch: np.ndarray,
                     visible: np.ndarray) -> tuple[np.ndarray, dict]:
    res = L.surface_from_candidates(
        z, cand, branch, visible,
        {"feature": "H73 paired-basin contrast", "candidate_pixels": int(cand.sum())},
        n_drainage_min=3, half_len=10, half_width=2, trace_decay=0.65,
        max_candidates=160_000, include_positive_channels=False,
        strict_aligned_corridors=False,
    )
    d = ndi.distance_transform_edt(~visible)
    continuation = (0.25 + 0.75 * np.exp(-d / 12.0)).astype(np.float32)
    score = (res.p * continuation).astype(np.float32)
    diag = dict(res.diagnostics)
    diag.update(score_positive_px=int((score > 0).sum()), continuation_decay_px=12.0,
                continuation_floor=0.25)
    return score, diag


def first_tests() -> tuple[dict, bool]:
    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue
    stat, channel, exclude = load("stat"), load("channel"), load("exclude")
    ctx = HO.build_holdout(grid)
    truth = {k: v for k, v in ctx.hidden_by_cell.items()}
    visible = {c.key: ctx.visible(c.key) for c in ctx.cells}
    active = {c.key: c.active for c in ctx.cells}
    rows_cat = RL.run_e1(ctx, stat, channel, active, truth, visible,
                         modes=("all",), exclude=exclude)
    cat_summary = RL.paired_bootstrap(rows_cat, draws=BOOT_DRAWS, seed=BOOT_SEED)
    sgmc = dataio.load_sgmc()
    offcat = I.sgmc_off_catalogue(sgmc, cat, fp, buffer_px=3)
    rows_off = run_e1_offcat(stat, channel, fp, offcat, cat)
    off_summary = RL.paired_bootstrap(rows_off, draws=BOOT_DRAWS, seed=BOOT_SEED)
    passed = cat_summary.get("verdict") == "PROCEED" and off_summary.get("verdict") == "PROCEED"
    result = {
        "evidence_class": "MEASUREMENT", "hypothesis": "H73-1",
        "evaluator": "shared same-orientation transect test in scripts/run_lane60.py/run_h66.py",
        "statistic": "0.70 z(paired-basin log1p(ksn) gradient) + 0.30 z(persistent positive dksn)",
        "catalogue_withheld": {"gating": True, "summary": cat_summary,
                                "rows_scored": sum("paired_difference" in r for r in rows_cat),
                                "rows_skipped": sum("skipped" in r for r in rows_cat)},
        "sgmc_offcatalogue_gt300m": {"gating": True, "offcatalogue_px": int(offcat.sum()),
                                      "summary": off_summary,
                                      "rows_scored": sum("paired_difference" in r for r in rows_off),
                                      "rows_skipped": sum("skipped" in r for r in rows_off)},
        "dual_gate_passed": passed,
        "decision": "PROCEED" if passed else "STOP"
    }
    write_json(EVID / "h73_e1_first_test.json", result)
    return result, passed


def leakage_summary(rows: list[dict]) -> list[dict]:
    out = []
    for feature in sorted({r["feature"] for r in rows}):
        vals = [r for r in rows if r["feature"] == feature and np.isfinite(r["auc"])]
        if not vals:
            continue
        worst = max(vals, key=lambda r: max(r["auc"], 1.0 - r["auc"]))
        m = max(worst["auc"], 1.0 - worst["auc"])
        out.append({"feature": feature, "auc": worst["auc"], "max_abs_auc": m,
                    "worst_cell": worst["cell"], "leakage_flag": bool(m > 0.90),
                    "positive_control": feature == "dist_to_visible"})
    return out


def holdout() -> dict:
    grid = G57.load_grid()
    fp = grid.footprint
    stat, raw_geo = load("stat"), load("raw_geo")
    channel, branch = load("channel"), load("branch")
    basin_contrast, dksn = load("basin_contrast"), load("dksn")
    holes = load("lattice_holes")
    z = np.nan_to_num(stat, nan=0.0).astype(np.float32)
    cand = channel & (z >= 0.5)
    ctx = HO.build_holdout(grid)
    truth = {k: v for k, v in ctx.hidden_by_cell.items()}
    visible = {c.key: ctx.visible(c.key) for c in ctx.cells}
    terms = {name: [] for name in ("lane_h73", "distance_only", "random_mass_control")}
    canary_rows, cells_diag = [], []
    for cell in [c for c in ctx.cells if c.mode == "all"]:
        bb = cell.bbox
        vis = visible[cell.key]
        vis_c = vis[bb]
        allowed = cell.active & ~vis_c  # shared holdout contract: pixel-exact known mask
        total = max(100, int(round(DENSITY * int(allowed.sum()))))
        novelty_n = max(1, int(round(total * NOVELTY / TOTAL)))
        primary_n = total - novelty_n
        score, sdiag = build_fold_score(z, cand, branch, vis)
        pred, pdiag = select_weighted(score[bb], raw_geo[bb], allowed, holes[bb],
                                      total, primary_n, novelty_n, seed=7300 + cell.fold)

        d = ndi.distance_transform_edt(~vis_c)
        p_dist = np.where(allowed, np.exp(-d / 12.0), 0.0).astype(np.float32)
        dist_pred, _ = select_weighted(p_dist, p_dist, allowed, holes[bb], total,
                                       primary_n, novelty_n, seed=7400 + cell.fold)
        rng = np.random.default_rng(7500 + cell.fold)
        random_score = np.zeros(allowed.shape, np.float32)
        random_score[allowed] = rng.random(int(allowed.sum())).astype(np.float32)
        rnd_pred, _ = select_weighted(random_score, random_score, allowed, holes[bb], total,
                                      primary_n, novelty_n, seed=7500 + cell.fold)
        fold = RL.cell_fold(cell, truth[cell.key][bb])
        for name, arr in (("lane_h73", pred), ("distance_only", dist_pred),
                          ("random_mass_control", rnd_pred)):
            _, t = EH.evaluate(arr, fold, fp[bb], block_side=200,
                               origin=(bb[0].start, bb[1].start),
                               global_shape=(grid.height, grid.width))
            terms[name].append(t)
        geo_domain = allowed
        for name, feat in (("paired_basin_contrast", basin_contrast[bb]),
                           ("dksn", dksn[bb]), ("combined_stat", stat[bb]),
                           ("lane_p", score[bb]), ("dist_to_visible", -d)):
            canary_rows.append({"cell": cell.key, "feature": name,
                                "auc": RL.auc(feat, truth[cell.key][bb] & cell.active, geo_domain)})
        cells_diag.append({"cell": cell.key, "budget": total, "placement": pdiag,
                           "surface": sdiag})
        del score, pred, p_dist, dist_pred, random_score, rnd_pred, d
        gc.collect()

    pooled = EH.pooled_summary({k: np.sum(v, axis=0) for k, v in terms.items()},
                               draws=BOOT_DRAWS, seed=BOOT_SEED, candidate="lane_h73")
    canary = leakage_summary(canary_rows)
    score = pooled["scores"]["lane_h73"]
    hold_pass = score["dti"] > H68_BEST
    leakage_pass = all(not r["leakage_flag"] for r in canary if not r["positive_control"])
    result = {
        "evidence_class": "HOLDOUT-DTI", "evaluator_version": EH.VERSION,
        "implementation_sha256": EH.implementation_hashes(), "hypothesis": "H73-1",
        "withheld_positive_pixels": score["withheld_positive_pixels"],
        "pooled_binary_weighted": pooled,
        "recorded_current_lane_best": {"run": "H68-1", "dti": H68_BEST,
                                        "ci95": [0.157848, 0.183994],
                                        "same_evaluator": "gems57-pooled-hide-v2"},
        "gate_G4_beats_recorded_h68_point": hold_pass,
        "canary": canary, "gate_G3_no_geological_feature_auc_gt_0p90": leakage_pass,
        "cells": cells_diag,
        "caveat": "Conditional hide-and-recover measurement; not a leaderboard score or projection."
    }
    write_json(EVID / "h73_holdout.json", result)
    return result


def production_prediction() -> tuple[np.ndarray, dict]:
    grid = G57.load_grid()
    raw_geo, holes = load("raw_geo"), load("lattice_holes")
    z = np.nan_to_num(load("stat"), nan=0.0).astype(np.float32)
    channel, branch = load("channel"), load("branch")
    cand = channel & (z >= 0.5)
    score, sdiag = build_fold_score(z, cand, branch, grid.catalogue)
    allowed = grid.footprint & ~grid.catalogue
    pred, pdiag = select_weighted(score, raw_geo, allowed, holes,
                                  TOTAL, PRIMARY, NOVELTY, seed=7373)
    if pdiag["low_confidence_hole_deficit"] != 0:
        raise RuntimeError("production novelty quota did not fit in literal lattice holes")
    return pred, {"surface": sdiag, "placement": pdiag,
                  "positive_on_catalogue": int(((pred > 0) & grid.catalogue).sum()),
                  "positive_outside_footprint": int(((pred > 0) & ~grid.footprint).sum())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force-features", action="store_true")
    ap.add_argument("--first-test-only", action="store_true")
    ap.add_argument("--allow-negative-artifact", action="store_true",
                    help="build the uniquely named TIFF even when scientific promotion gates fail; it remains DO NOT SUBMIT")
    args = ap.parse_args()
    started = time.time()
    print("[H73] preregistration: registry/preregistration-h73.json", flush=True)
    feat = build_features(force=args.force_features)
    print("[H73] feature cache", feat["diagnostics"], flush=True)
    e1, passed = first_tests()
    print("[H73] E1 catalogue", e1["catalogue_withheld"]["summary"], flush=True)
    print("[H73] E1 SGMC off-catalogue", e1["sgmc_offcatalogue_gt300m"]["summary"], flush=True)
    if args.first_test_only:
        return 0 if passed else 2
    if not passed and not args.allow_negative_artifact:
        print("[H73] dual first-test gate STOP; no holdout or TIFF", flush=True)
        return 2
    h = holdout()
    hs = h["pooled_binary_weighted"]["scores"]["lane_h73"]
    print("[H73] holdout", hs, flush=True)
    pred, prod = production_prediction()
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(CACHE / "production_prediction.npy", pred)
    write_json(EVID / "h73_production_cache.json", {
        "hypothesis": "H73-1", "production": prod,
        "first_test_passed": passed,
        "holdout_gate_passed": h["gate_G4_beats_recorded_h68_point"],
        "leakage_gate_passed": h["gate_G3_no_geological_feature_auc_gt_0p90"],
        "output": str(OUT.relative_to(ROOT)), "seconds": round(time.time() - started, 2)
    })
    print("[H73] production array cached; audit registry, then use scripts/emit_h73_negative.py for the fail-closed negative artifact", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
