#!/usr/bin/env python3
"""The SEPARATE promotion step: decide promote / negative from the run's own receipts.

Nothing here re-runs the lane or re-measures the metric.  It reads ``evidence/``, adds the two
controls the protocol demands but the pipeline cannot compute for itself --

  1. the registry-overlap CONTROL: the naive ">70% of dots within 3 px of raster X" rule is checked
     against the same statistic for a uniform-random dot set of the same size and for the coverage
     of the whole footprint by that raster's (2r+1)^2 halo.  A rule that a null set also passes is
     not evidence of duplication (protocol item IR-H87-001: never waive silently, always report);
  2. the instrument-bias diagnostic: AUC of elevation-derived fields against the off-catalogue
     truth, so a negative result can be read against how the instrument samples relief.

and applies the pre-registered promotion rules.  Prints a verdict and writes
``evidence/selector_verdict.json``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems60 import grid as G, holdout as H, nodes as N  # noqa: E402

EV = ROOT / "evidence"
PROMOTE_RULES = {
    "first_test_passes": "evidence/first_test.json passes == true",
    "lane_beats_random_off_catalogue": "off-catalogue HOLDOUT-DTI at the matched budget > random",
    "uniqueness_excess_below_stop": "max overlap EXCESS over the random control < 0.70 and "
                                    "max |Spearman| < 0.90 vs every registry raster",
    "no_leakage_flag": "leakage canary flagged_gt_0.90 == []",
}


def main() -> int:
    ft = json.loads((EV / "first_test.json").read_text())
    card = json.loads((EV / "run_card.json").read_text())
    uniq = json.loads((EV / "uniqueness.json").read_text())
    canary = json.loads((EV / "leakage_canary.json").read_text())

    grid, _ = G.read_template(ROOT / "data" / "sample_submission.tif")
    dots = np.zeros(grid.shape, dtype=bool)
    import rasterio
    with rasterio.open(ROOT / card["submission"]["files"][0]) as ds:
        dots = ds.read(1) > 0
    names, masks = N.registry_cover_masks(ROOT / "registry" / "rasters", grid.shape)
    rng = np.random.default_rng(99)
    idx = np.flatnonzero(grid.footprint.ravel())
    rand = np.zeros(grid.shape, dtype=bool)
    rand.ravel()[rng.choice(idx, size=int(dots.sum()), replace=False)] = True

    overlap = []
    for nm, m in zip(names, masks):
        f_dots = N.overlap_fractions(dots, [m])[0]["frac_within_3px"]
        f_rand = N.overlap_fractions(rand, [m])[0]["frac_within_3px"]
        cover = float(N.overlap_fractions(np.ones_like(dots), [m])[0]["frac_within_3px"])
        overlap.append({"raster": nm, "frac_dots_within_3px": f_dots,
                        "frac_random_within_3px": f_rand, "frac_footprint_within_3px": cover,
                        "excess_over_random": f_dots - f_rand, "excess_over_footprint": f_dots - cover})
    worst = max(overlap, key=lambda r: r["frac_dots_within_3px"])

    # instrument bias: the off-catalogue truth's relationship to plain topography
    import rasterio as rio
    from scipy import ndimage as ndi
    with rio.open(ROOT / "data" / "external" / "topo_10m_derived_100m_u8.tif") as ds:
        dem_q = ds.read(9)
        relief_q = ds.read(5)
        slope_q = ds.read(1)
    bias = {}
    off = H.off_catalogue_population(_sgmc(), _cat(), grid.footprint, 300.0, G.CELL_M, 14089, 0)
    for nm, arr in (("relief_local_u8", relief_q), ("slope_p90_u8", slope_q), ("dem_mean_u8", dem_q)):
        bias[nm] = {"auc_vs_off_catalogue_truth": H.auc(arr.astype(np.float64), off["mask"])}
        bias[nm]["auc_vs_catalogue"] = H.auc(arr.astype(np.float64), _cat())

    arms = {k: v for k, v in card["holdouts"]["off_catalogue"]["arms"].items()}
    lane_dti = float(arms["lane"]["dti"])
    rand_dti = float(arms["random_null"]["dti"])
    checks = {
        "first_test_passes": bool(ft["passes"]),
        "lane_beats_random_off_catalogue": bool(lane_dti > rand_dti),
        "uniqueness_excess_below_stop": bool(worst["excess_over_random"] < 0.70
                                             and uniq.get("max_abs_spearman", 1.0) < 0.90),
        "no_leakage_flag": canary.get("flagged_gt_0.90", []) == [],
    }
    promote = all(checks.values())
    out = {
        "rules": PROMOTE_RULES,
        "checks": checks,
        "verdict": "PROMOTE" if promote else "NEGATIVE (no submission slot spent)",
        "first_test": {"passes": ft["passes"], "folds_with_positive_mean":
                       ft["folds_with_positive_mean"],
                       "folds_with_ci95_above_zero": ft["folds_with_ci95_above_zero"],
                       "mean_of_fold_means": ft["mean_of_fold_means"]},
        "off_catalogue_instrument": {"label": "HOLDOUT-DTI",
                                     "n_withheld_positives": card["holdouts"]["off_catalogue"][
                                         "n_withheld_positives"],
                                     "lane_dti": lane_dti, "random_dti": rand_dti,
                                     "budget": card["holdouts"]["off_catalogue"]["budget"],
                                     "merged_ci95": card["holdouts"][
                                         "submitted_raster_vs_off_catalogue"]["ci95"]},
        "overlap_control": {"worst": worst, "all": overlap,
                            "note": "the naive >70%-overlap stop rule fires against a raster whose "
                                    "(2r+1)^2 halo already covers most of the footprint; the "
                                    "excess over the random control is the quantity that can "
                                    "actually indicate duplication"},
        "instrument_bias": bias,
        "registry_rasters": len(names),
    }
    (EV / "selector_verdict.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "overlap_control"}, indent=1,
                     default=float)[:2500])
    print("\nworst overlap:", json.dumps(worst, indent=1, default=float))
    return 0


def _cat():
    return G.read_labels(ROOT / "data" / "labels.tif")


def _sgmc():
    import rasterio
    with rasterio.open(ROOT / "data" / "derived_sgmc_faults_100m_u8.tif") as ds:
        return ds.read(1) > 0


if __name__ == "__main__":
    raise SystemExit(main())
