#!/usr/bin/env python3
"""H62-1 — under-cover basement-step x gravity-step concordance (preregistered experiment).

The preregistration (registry/preregistration-h62.json, written BEFORE this script first ran) is
the contract: this script reads it back, hashes it into the receipt, and implements it line for
line.  Three stages, in protocol order:

  1. SURFACE GATE (G0): rank-correlate the built field against every registry raster BEFORE any
     dot is placed — > 0.90 means lane drift/duplication, stop.
  2. VALIDATION: leakage canary (per-feature AUC vs the off-catalogue truth, flag > 0.90),
     budget ladder on the prevalence-corrected off-catalogue instrument, then the spatially
     blocked hide-and-recover (gems52-pooled-hide-v1, 4 whole-segment folds, visible catalogue
     masked pixel-exactly, paired 20 km-block bootstrap CI).
  3. EMISSION + DOTS GATE (G4) + fail-closed writer (gems52.submission_writer): the artifact is
     written even when the verdict is NEGATIVE — a validated, unique GeoTIFF whose receipt says
     plainly whether it may be submitted.

Nothing here spends a submission slot; promotion is the separate selector step.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems60 import grid as G60            # noqa: E402
from gems60 import holdout as H60         # noqa: E402
from gems60 import nodes as N60           # noqa: E402
from gems60 import surface as S60         # noqa: E402
from gems52 import evaluate_holdout as EH  # noqa: E402
from gems52 import holdout as HO          # noqa: E402
from gems52 import submission_writer as SW  # noqa: E402

DATA = ROOT / "data"
EVID = ROOT / "evidence"
REGDIR = ROOT / "registry" / "rasters"
OUTDIR = ROOT / "docs" / "downloads"
PREREG = ROOT / "registry" / "preregistration-h62.json"
G_BRACKET_MID = 14088.7
SEED = 20261011
RANDOM_SEED = 777
CANARY_FLAG = 0.90
STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:7.1f}s] {msg}", flush=True)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def decode_topo_u8(q: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """The pack's own quantisation rule (manifest), verbatim: q=0 -> NaN."""
    return np.where(q > 0, lo + (q.astype(np.float64) - 1.0) / 254.0 * (hi - lo), np.nan)


def main() -> int:
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "H62 preregistered experiment runner"):
        return 0
    t0 = time.time()
    EVID.mkdir(exist_ok=True)
    OUTDIR.mkdir(exist_ok=True)

    # ---------------------------------------------------------------- prereg contract
    prereg = json.loads(PREREG.read_text())
    assert prereg["id"] == "60H62-PREREG-1" and prereg["written_before_results"] is True
    prereg_sha = sha(PREREG)
    (EVID / "h62_prereg_receipt.json").write_text(json.dumps({
        "prereg": str(PREREG.relative_to(ROOT)), "sha256": prereg_sha,
        "id": prereg["id"], "written_utc": prereg["written_utc"],
        "read_back_utc": STAMP,
        "assertion": "this receipt was written by run_h62.py before any field was computed",
    }, indent=2) + "\n")
    LADDER = [int(b) for b in prereg["budget_ladder_px"]]
    RING_M = float(prereg["masks"]["catalogue_ring_m"])
    log(f"prereg read back: {prereg['id']} sha {prereg_sha[:16]}", t0)

    # ---------------------------------------------------------------- inputs (sha-pinned)
    pins = {}
    for fname in ("training_features.tif", "labels.tif", "sample_submission.tif"):
        p = DATA / fname
        if not p.exists():
            print(f"FATAL: missing {p} (run scripts/restore_data.py)", file=sys.stderr)
            return 2
        pins[fname] = sha(p)
    grid, _ = G60.read_template(DATA / "sample_submission.tif")
    cat = G60.read_labels(DATA / "labels.tif")
    valid = grid.footprint
    sgmc_path = DATA / "derived_sgmc_faults_100m_u8.tif"
    if not sgmc_path.exists():  # manifest destination is external/; the lane reads data/
        sgmc_path = DATA / "external" / "derived_sgmc_faults_100m_u8.tif"
    import rasterio
    with rasterio.open(sgmc_path) as ds:
        sgmc = ds.read(1) > 0
    log(f"grid {grid.shape} footprint {int(valid.sum())} catalogue {int(cat.sum())} sgmc {int(sgmc.sum())}", t0)

    # ---------------------------------------------------------------- cube bands + row means
    import rasterio as rio
    with rio.open(DATA / "training_features.tif") as ds:
        band_desc = list(ds.descriptions)
        def read_masked(b):
            a = ds.read(b, out_dtype="float32", masked=True).filled(np.nan)
            return a
        depth = read_masked(15).astype(np.float64)
        grav = read_masked(13).astype(np.float64)
        det_slope = read_masked(19).astype(np.float32)
        det_elev = read_masked(12).astype(np.float32)
        row_means = np.empty((ds.count, ds.height), dtype=np.float32)
        for b in range(1, ds.count + 1):
            a = ds.read(b, out_dtype="float32", masked=True).filled(np.nan)
            m = valid & np.isfinite(a)
            cnt = m.sum(axis=1)
            row_means[b - 1] = np.where(cnt > 0, np.nansum(np.where(m, a, 0.0), axis=1) / np.maximum(cnt, 1), np.nan)
            del a
    log(f"cube streamed; band descriptions: {band_desc}", t0)

    # ---------------------------------------------------------------- topo pack (gate)
    pack = DATA / "external" / "topo_10m_derived_100m_u8.tif"
    pman = json.loads(pack.with_suffix(".manifest.json").read_text())
    pb = {b["band_name"]: b for b in pman["bands"]}
    with rio.open(pack) as ds:
        slope_p90 = decode_topo_u8(ds.read(1), pb["slope_p90"]["lo"], pb["slope_p90"]["hi"])
        relief_local = decode_topo_u8(ds.read(5), pb["relief_local"]["lo"], pb["relief_local"]["hi"])
        dem_mean = decode_topo_u8(ds.read(9), pb["dem_mean"]["lo"], pb["dem_mean"]["hi"])
    slope_thr_note = prereg["field"]["construction"][4]  # gate line, asserted below
    SLOPE_MAX_DEG, RELIEF_MAX_M = 8.0, 25.0
    assert "slope_p90 <= 8 deg" in slope_thr_note

    # ---------------------------------------------------------------- build the field (prereg)
    def sobel_mag(a: np.ndarray) -> np.ndarray:
        m = np.isfinite(a) & valid
        fill = float(np.nanmedian(a[m])) if m.any() else 0.0
        z = np.where(m, a, fill)
        gx = np.zeros_like(z); gy = np.zeros_like(z)
        from scipy import ndimage as ndi
        gx[:, 1:-1] = (z[:, 2:] - z[:, :-2]) / 2.0
        gy[1:-1, :] = (z[2:, :] - z[:-2, :]) / 2.0
        out = np.hypot(gx, gy)
        out[~m] = np.nan
        return out

    def pctile_rank(a: np.ndarray) -> np.ndarray:
        m = np.isfinite(a) & valid
        v = a[m]
        order = np.argsort(v, kind="stable")
        r = np.empty(v.size, dtype=np.float64)
        r[order] = np.arange(1, v.size + 1, dtype=np.float64)
        out = np.full(a.shape, np.nan, dtype=np.float64)
        out[m] = (r - 0.5) / v.size
        return out

    g_depth = sobel_mag(depth)
    g_grav = sobel_mag(grav)
    r_depth = pctile_rank(np.where(np.isfinite(g_depth) & valid, g_depth, np.nan))
    r_grav = pctile_rank(np.where(np.isfinite(g_grav) & valid, g_grav, np.nan))
    conj = np.where(valid, np.fmin(r_depth, r_grav), 0.0)
    gate = np.where(valid & np.isfinite(slope_p90) & np.isfinite(relief_local)
                    & (slope_p90 <= SLOPE_MAX_DEG) & (relief_local <= RELIEF_MAX_M), 1.0, 0.0)
    field_h62 = np.where(valid, conj * gate, 0.0)
    field_ungated = np.where(valid, conj, 0.0)
    field_h62 = np.nan_to_num(field_h62, nan=0.0).astype(np.float32)
    field_ungated = np.nan_to_num(field_ungated, nan=0.0).astype(np.float32)
    del depth, grav, g_depth, g_grav, r_depth, r_grav, conj
    log(f"fields built: primary>0 {int((field_h62 > 0).sum())} ungated>0 {int((field_ungated > 0).sum())} "
        f"gate px {int(gate.sum())}", t0)

    stripe = S60.detect_striped_rows(row_means)
    stripe_rows = stripe["rows"]
    del row_means
    log(f"striped rows flagged: {stripe['rows_flagged']}", t0)

    # ---------------------------------------------------------------- masks + instruments
    from scipy import ndimage as ndi
    dcat = ndi.distance_transform_edt(~cat, sampling=G60.CELL_M)
    allowed = valid & ~(dcat <= RING_M) & ~(stripe_rows[:, None])
    log(f"allowed px: {int(allowed.sum())} (ring {RING_M} m + {stripe_rows.sum()} striped rows removed)", t0)

    off = H60.off_catalogue_population(sgmc, cat, valid, min_dist_m=300.0, cell_m=G60.CELL_M,
                                       target_px=int(round(G_BRACKET_MID)), seed=0)
    off_truth = off["mask"]
    log(f"off-catalogue truth: {int(off_truth.sum())} px (raw {off['info']['raw_px']})", t0)

    # ---------------------------------------------------------------- G0: surface uniqueness
    reg_names, reg_masks = N60.registry_cover_masks(REGDIR, grid.shape)
    rng_sub = np.random.default_rng(2026)
    sub_idx = np.flatnonzero(valid.ravel())
    sub_idx = sub_idx[rng_sub.choice(sub_idx.size, size=min(500_000, sub_idx.size), replace=False)]
    from scipy import stats as sps
    surf_gate = {"n_registry": len(reg_masks), "per_raster": [], "pass": None}
    for nm, m in zip(reg_names, reg_masks):
        x = field_h62.ravel()[sub_idx].astype(np.float64)
        y = m.ravel()[sub_idx].astype(np.float64)
        rho = float(sps.spearmanr(x, y).statistic) if np.unique(y).size > 1 else 0.0
        surf_gate["per_raster"].append({"raster": nm, "spearman_field_vs_raster": rho})
    surf_gate["max_abs_spearman"] = float(max(abs(r["spearman_field_vs_raster"]) for r in surf_gate["per_raster"]))
    surf_gate["pass"] = bool(surf_gate["max_abs_spearman"] <= 0.90)
    G60.write_json(EVID / "h62_gate_G0_surface.json", surf_gate)
    log(f"G0 surface uniqueness: max|rho| = {surf_gate['max_abs_spearman']:.4f} -> {'PASS' if surf_gate['pass'] else 'FAIL'}", t0)
    if not surf_gate["pass"]:
        G60.write_json(EVID / "h62_validation.json", {"verdict": "NEGATIVE-STOP",
                                                      "reason": "G0 failed: field duplicates a registry raster",
                                                      "G0": surf_gate})
        print("STOP: G0 failed (duplicate of a registry raster) — no raster emitted.")
        return 0

    # ---------------------------------------------------------------- canary (G1)
    canary = {}
    feats = {
        "field_h62_primary": field_h62,
        "field_h62_ungated": field_ungated,
        "gate_slope_inv": np.where(valid & np.isfinite(slope_p90), -slope_p90, np.nan),
        "gate_relief_inv": np.where(valid & np.isfinite(relief_local), -relief_local, np.nan),
        "det_elev": det_elev,
        "abs_det_elev_slope": np.abs(det_slope),
        "dem_mean": dem_mean,
    }
    for nm, arr in feats.items():
        a = np.asarray(arr, dtype=np.float64)
        v = H60.auc(a, off_truth)
        # allow_nan=False JSON: a degenerate AUC must be null, never NaN
        canary[nm] = {"auc_vs_off_catalogue_truth": float(v) if np.isfinite(v) else None}
    canary["flagged_gt_0_90"] = sorted(k for k, v in canary.items()
                                       if np.nan_to_num(v["auc_vs_off_catalogue_truth"]) > CANARY_FLAG)
    primary_barred = bool(np.nan_to_num(canary["field_h62_primary"]["auc_vs_off_catalogue_truth"]) > CANARY_FLAG)
    ungated_barred = bool(np.nan_to_num(canary["field_h62_ungated"]["auc_vs_off_catalogue_truth"]) > CANARY_FLAG)
    canary["primary_barred"] = primary_barred
    canary["ungated_barred"] = ungated_barred
    G60.write_json(EVID / "h62_leakage_canary.json", canary)
    if primary_barred and ungated_barred:
        G60.write_json(EVID / "h62_validation.json", {"verdict": "NEGATIVE-STOP",
                                                      "reason": "G1 failed: both arms barred by canary",
                                                      "canary": canary})
        print("STOP: both arms barred by the canary — no raster emitted.")
        return 0
    eligible_field, eligible_arm = ((field_h62, "h62_primary") if not primary_barred
                                    else (field_ungated, "h62_ungated_fallback"))
    log(f"canary: primary AUC {canary['field_h62_primary']['auc_vs_off_catalogue_truth']:.4f} "
        f"ungated {canary['field_h62_ungated']['auc_vs_off_catalogue_truth']:.4f} "
        f"flagged {canary['flagged_gt_0_90']} -> arm {eligible_arm}", t0)

    # ---------------------------------------------------------------- budget ladder (offcat)
    def budget_curve(field, ladder):
        rows = []
        rng_b = np.random.default_rng(4242)
        idx_all = np.flatnonzero(allowed.ravel())
        for b in ladder:
            if b > idx_all.size:
                break
            dots = N60.emit(field, allowed, b, N60.spacing_from_budget(b, int(allowed.sum())),
                            min_sep_px=3.0)
            r = H60.pooled_dti(dots.astype(np.float32), off_truth)
            mk = np.zeros(field.shape, dtype=bool)
            mk.ravel()[rng_b.choice(idx_all, size=b, replace=False)] = True
            rn = H60.pooled_dti(mk.astype(np.float32), off_truth)
            rows.append({"budget": int(b), "lane_dti": float(r["dti"]), "random_dti": float(rn["dti"]),
                         "lane_minus_random": float(r["dti"] - rn["dti"]),
                         "lane_mass": float(r["mass"]), "random_mass": float(rn["mass"])})
        return rows

    ladder_rows = budget_curve(eligible_field, LADDER)
    best = max(ladder_rows, key=lambda z: z["lane_dti"]) if ladder_rows else {"budget": 12000, "lane_dti": 0.0}
    chosen_budget = int(best["budget"])
    offcat_at_budget = next((r for r in ladder_rows if r["budget"] == chosen_budget), None)
    beats_random_offcat = bool(offcat_at_budget and offcat_at_budget["lane_minus_random"] > 0)
    G60.write_json(EVID / "h62_budget_ladder.json",
                   {"arm": eligible_arm, "ladder": ladder_rows, "argmax_budget": chosen_budget,
                    "argmax_dti": float(best["lane_dti"]),
                    "budgets_beating_random": sum(1 for r in ladder_rows if r["lane_minus_random"] > 0),
                    "n_budgets": len(ladder_rows)})
    log(f"budget ladder argmax: {chosen_budget} px @ DTI {best['lane_dti']:.4f} "
        f"(beats random at {sum(1 for r in ladder_rows if r['lane_minus_random'] > 0)}/{len(ladder_rows)} rungs)", t0)

    # ---------------------------------------------------------------- final emission
    spacing = N60.spacing_from_budget(chosen_budget, int(allowed.sum()))
    dots = N60.emit(eligible_field, allowed, chosen_budget, spacing, min_sep_px=3.0, seed=60)
    n_dots = int(dots.sum())
    pred = np.zeros(grid.shape, dtype=np.float32)
    pred[dots] = 1.0
    log(f"final emission: {n_dots} dots @ spacing {spacing:.2f} px", t0)

    # random matched raster (same mass, same masks, seed 777)
    rng_r = np.random.default_rng(RANDOM_SEED)
    idx_all = np.flatnonzero(allowed.ravel())
    rnd = np.zeros(grid.shape, dtype=bool)
    rnd.ravel()[rng_r.choice(idx_all, size=min(n_dots, idx_all.size), replace=False)] = True
    rnd_pred = rnd.astype(np.float32)

    # ---------------------------------------------------------------- spatially blocked hideout
    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                          seed=SEED, mode="hide")
    log(f"folds: {[(f['fold'], f['n_truth']) for f in folds]}", t0)

    anchors = {
        "champion": REGDIR / "dotted_b2_prune_02778.tif",
        "d28": REGDIR / "dotted_d2_8_02600.tif",
        "h274r1": REGDIR / "dotted_d2_8_02708.tif",
        "h16topo": DATA / "scored" / "gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif",
    }
    def read_anchor(p):
        with rio.open(p) as ds:
            return np.nan_to_num(ds.read(1).astype(np.float32), nan=0.0)

    terms_by_arm: dict[str, list] = {}
    per_fold: dict[str, list] = {}
    for f in folds:
        for arm, arr in (("h62_candidate", pred), ("random_matched", rnd_pred)):
            res, terms = EH.evaluate(arr, f, valid, block_side=200)
            terms_by_arm.setdefault(arm, []).append(terms)
            per_fold.setdefault(arm, []).append({"fold": f["fold"], "dti": res["dti"],
                                                 "tpw": res["tpw"], "fpw": res["fpw"],
                                                 "n_truth": res["n_truth"]})
        # label-free upper bound: raw field re-emitted inside the fold's own allowed region
        allow_e = valid & ~f["visible"] & f["region"]
        em = HO.emit_topk(np.where(allow_e, eligible_field, 0.0).astype(np.float32), allow_e, n_dots)
        res, terms = EH.evaluate(em, f, valid, block_side=200)
        terms_by_arm.setdefault("field_topk_canary", []).append(terms)
        per_fold.setdefault("field_topk_canary", []).append({"fold": f["fold"], "dti": res["dti"],
                                                             "tpw": res["tpw"], "fpw": res["fpw"],
                                                             "n_truth": res["n_truth"]})
    for name, p in anchors.items():
        g = read_anchor(p)
        for f in folds:
            res, terms = EH.evaluate(g, f, valid, block_side=200)
            terms_by_arm.setdefault(name, []).append(terms)
            per_fold.setdefault(name, []).append({"fold": f["fold"], "dti": res["dti"],
                                                  "tpw": res["tpw"], "fpw": res["fpw"],
                                                  "n_truth": res["n_truth"]})
    terms_by_arm = {k: np.concatenate(v, axis=0) for k, v in terms_by_arm.items()}
    pooled = EH.pooled_summary(terms_by_arm, draws=2000, seed=SEED, candidate="h62_candidate")

    # G2: beats random, fold-consistency >= 3/4 + offcat at emission budget
    h_folds = [r["dti"] for r in per_fold["h62_candidate"]]
    r_folds = [r["dti"] for r in per_fold["random_matched"]]
    folds_beating = int(sum(1 for a, b in zip(h_folds, r_folds) if a > b))
    g2_hideout = bool(pooled["scores"]["h62_candidate"]["dti"] > pooled["scores"]["random_matched"]["dti"]
                      and folds_beating >= 3)
    g2 = {"hideout_beats_random": g2_hideout, "folds_candidate_gt_random": f"{folds_beating}/{len(h_folds)}",
          "offcat_at_emission_budget": offcat_at_budget, "offcat_beats_random": beats_random_offcat}
    g2["pass"] = bool(g2_hideout and beats_random_offcat)

    # G3: candidate strictly greater than EVERY comparable arm
    others = {k: v["dti"] for k, v in pooled["scores"].items() if k != "h62_candidate"}
    g3 = {"candidate_dti": pooled["scores"]["h62_candidate"]["dti"], "best_other_dti": max(others.values()),
          "best_other_arm": max(others, key=others.get), "all_arms": others}
    g3["pass"] = bool(g3["candidate_dti"] > g3["best_other_dti"])

    # ---------------------------------------------------------------- G4: dots uniqueness
    ov = N60.overlap_fractions(dots, reg_masks)
    uniq = {"n_registry_rasters": len(reg_masks),
            "overlap": [{"raster": nm, **o} for nm, o in zip(reg_names, ov)],
            "max_frac_within_3px": float(max(o["frac_within_3px"] for o in ov))}
    uniq["G4_overlap_pass"] = bool(uniq["max_frac_within_3px"] <= 0.70)
    flat = pred.ravel()
    rho = []
    for nm, m in zip(reg_names, reg_masks):
        x = flat[sub_idx].astype(np.float64)
        y = m.ravel()[sub_idx].astype(np.float64)
        r = float(sps.spearmanr(x, y).statistic) if np.unique(y).size > 1 else 0.0
        rho.append({"raster": nm, "spearman_vs_dots": r})
    uniq["rank_correlation"] = rho
    uniq["max_abs_spearman"] = float(max(abs(r["spearman_vs_dots"]) for r in rho))
    uniq["G4_rank_pass"] = bool(uniq["max_abs_spearman"] <= 0.90)
    uniq["pass"] = bool(uniq["G4_overlap_pass"] and uniq["G4_rank_pass"])
    G60.write_json(EVID / "h62_uniqueness.json", uniq)

    # ---------------------------------------------------------------- verdict
    g1 = {"candidate_arm": eligible_arm,
          "candidate_auc": canary[("field_h62_primary" if eligible_arm == "h62_primary"
                                   else "field_h62_ungated")]["auc_vs_off_catalogue_truth"],
          "flagged": canary["flagged_gt_0_90"], "pass": not (primary_barred and ungated_barred)}
    gates = {"G0_surface_uniqueness": surf_gate["pass"], "G1_canary": g1["pass"],
             "G2_beats_random": g2["pass"], "G3_beats_holdout_best": g3["pass"],
             "G4_dots_uniqueness": uniq["pass"]}
    verdict = "PROMOTE-CANDIDATE" if all(gates.values()) else "NEGATIVE"
    failed = [k for k, v in gates.items() if not v]

    # ---------------------------------------------------------------- write the artifact
    stem = f"gems60-h62-1-undercover-step-{n_dots}px-{STAMP}-zeros"
    sub_name = f"h62-1-undercover-step-{n_dots}px-{STAMP}"
    hold = pooled["scores"]["h62_candidate"]
    note = (f"H62-1 buried basement-step x gravity-step; {n_dots} dots; HOLDOUT-DTI {hold['dti']:.4f}; "
            f"{verdict} - {'selector may consider' if verdict.startswith('PROMOTE') else 'do not submit'}")
    assert len(sub_name) <= 140 and len(note) <= 140, (len(sub_name), len(note))
    sample_path = DATA / "sample_submission.tif"
    receipt = SW.write_submission(OUTDIR / f"{stem}.tif", pred, sample_path, valid,
                                  note=note, name=sub_name,
                                  metadata=dict(hypothesis="H62-1", arm=eligible_arm,
                                               prereg_sha256=prereg_sha, gates=gates,
                                               verdict=verdict, evidence_class="HOLDOUT-DTI",
                                               evaluator_version=EH.VERSION))
    twin = OUTDIR / f"{stem.replace('-zeros', '-nan')}.tif"
    twin_rep = G60.write_submission(pred, twin, grid, outside="nan")
    sub_dir = ROOT / "submission"
    sub_dir.mkdir(exist_ok=True)
    (sub_dir / Path(receipt["file"]).name).write_bytes((OUTDIR / receipt["file"]).read_bytes())
    log(f"wrote {receipt['file']} sha {receipt['sha256'][:16]} ({receipt['bytes']} B)", t0)

    # ---------------------------------------------------------------- validation bundle + run card
    validation = {
        "prereg": {"id": prereg["id"], "sha256": prereg_sha},
        "instruments": {
            "spatially_blocked_hideout": {
                "label": "HOLDOUT-DTI", "evaluator_version": EH.VERSION,
                "folds": 4, "mode": "hide", "prevalence": 0.002, "seed": SEED,
                "block_side_px": 200, "draws": 2000,
                "withheld_positive_pixels_per_fold": [f["n_truth"] for f in folds],
            },
            "off_catalogue": {"label": "HOLDOUT-DTI", "n_withheld_positives": int(off_truth.sum()),
                              "raw_px": off["info"]["raw_px"], "min_dist_m": 300,
                              "target_px": G_BRACKET_MID},
        },
        "canary": canary, "budget_ladder": ladder_rows, "chosen_budget": chosen_budget,
        "pooled_hideout": pooled, "per_fold": per_fold,
        "G2": g2, "G3": g3, "gates": gates, "verdict": verdict, "failed_gates": failed,
        "dots": {"n": n_dots, "spacing_px": spacing},
        "uniqueness": {"max_frac_within_3px": uniq["max_frac_within_3px"],
                       "max_abs_spearman": uniq["max_abs_spearman"], "pass": uniq["pass"]},
        "artifact": {"file": receipt["file"], "sha256": receipt["sha256"], "bytes": receipt["bytes"],
                     "note": note, "submission_name": sub_name,
                     "nan_twin": twin_rep["file"], "nan_twin_sha256": twin_rep["sha256"]},
        "inputs_sha256": pins,
        "evidence_class": "HOLDOUT-DTI",
    }
    G60.write_json(EVID / "h62_validation.json", validation)

    runcard = {
        "hypothesis": prereg["statement"],
        "mechanism": ("depth_to_base_surf and iso_grav_anom Sobel gradients -> percentile ranks -> "
                      "min() conjunctive step field -> low-relief gate (slope_p90 <= 8 deg, "
                      "relief_local <= 25 m) -> 200 m catalogue ring + striped-row mask -> "
                      "hex-lattice top-k emission, 3 px NMS"),
        "named_non_fault_mimic_process": [
            "buried unconformities and basin-fill thickness edges (lithology/draping) produce "
            "coincident basement-depth and gravity steps with no fault",
            "Quaternary alluvial-fan/delta depocentre edges locally deepen the cover and bend both "
            "gradients without rupture",
            "the maximal-separation thinning of the off-catalogue instrument itself spreads truth "
            "into basin floors, rewarding any basin-prior field (the measured instrument bias)",
        ],
        "holdout": {"label": "HOLDOUT-DTI", "evaluator_version": EH.VERSION,
                    "candidate": hold, "all_arms": {k: v for k, v in pooled["scores"].items()},
                    "paired_differences_vs_candidate": pooled["paired_differences"]},
        "gates": gates, "failed_gates": failed, "verdict": verdict,
        "correlation_vs_registry": {"max_abs_spearman_surface": surf_gate["max_abs_spearman"],
                                    "max_abs_spearman_dots": uniq["max_abs_spearman"],
                                    "max_frac_dots_within_3px": uniq["max_frac_within_3px"]},
        "raster_sha256": receipt["sha256"],
        "validator": {"ok": receipt["validator"].get("ok"),
                      "problems": receipt["validator"].get("problems"),
                      "validation_class": receipt["validator"].get("validation_class"),
                      "nan_pixels": receipt["validator"].get("nan_pixels"),
                      "min": receipt["validator"].get("min"),
                      "max": receipt["validator"].get("max"),
                      "mass_outside_footprint": receipt["validator"].get("mass_outside_footprint")},
        "submission_name": sub_name, "submission_note": note,
        "verdict_detail": ("promote to the separate selector step (this run spends no slot)"
                           if verdict.startswith("PROMOTE") else
                           f"NEGATIVE - do not submit; failed gates: {', '.join(failed)}"),
        "evidence_class": "HOLDOUT-DTI",
    }
    G60.write_json(EVID / "h62_runcard.json", runcard)
    G60.write_json(ROOT / "docs" / "h62_runcard.json", runcard)
    print(json.dumps({"verdict": verdict, "failed_gates": failed, "chosen_budget": chosen_budget,
                      "dots": n_dots, "holdout_dti": hold["dti"], "holdout_ci95": hold["ci95"],
                      "best_other": (g3["best_other_arm"], g3["best_other_dti"]),
                      "sha256": receipt["sha256"], "file": receipt["file"],
                      "note": note}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
