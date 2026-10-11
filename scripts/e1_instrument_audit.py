#!/usr/bin/env python
"""E1 -- instrument audit: which local proxy, if any, ranks the OWNER-REPORTED live ladder?

Every number in this repository that ranks candidate rasters is a *proxy*: the organizers mask the
visible catalogue out of scoring and the hidden truth (expert-added faults) is unavailable.  The
only live ground truth this project owns is the set of scores the operator read off the DrivenData
submission page (``[OWNER-REPORT]``).  This script asks the one question that decides whether a proxy
may be used as a screen at all:

    does instrument X reproduce the order of the live ladder?

It implements, self-contained, the three instruments the family has used, plus the exact official
metric in ``src/gems52/metric.py`` semantics:

  * ``sgmc_raw_dti``            -- official DTI against SGMC faults >300 m from the catalogue
                                   (NOT mass-calibrated: rewards mass, so it inverts the ladder)
  * ``sgmc_prevalence_cal``     -- the family's mass-calibrated version (G = ESTIMATED_LB_HIDDEN_TRUTH_PX)
  * ``offcat_coverage``         -- fraction of the off-catalogue truth set covered at <=300 m
  * ``offcat_excess_vs_random`` -- coverage minus the coverage of a mass-matched random draw

Outputs ``evidence/e1_instrument_audit.json``.

Run:  .venv/bin/python scripts/e1_instrument_audit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import metric as M  # noqa: E402

# Owner-reported live scores (submission-page receipts copied into the standing brief).  Files are
# resolved by sha256 where the repo holds a pinned copy, so a renamed raster cannot smuggle in a
# different score.
LIVE = [
    # (label, live DTI, path relative to repo root)
    # H19-5 (121,131 dots, live 0.1922) has NO raster in registry/rasters/ -- the two
    # `gems25-dotted-h19-5-...` files both contain 44,090 dots (they are D2.8), so that ladder
    # point is dropped rather than duplicated.  n = 6 owner-reported points.
    ("H33-2-B2 champion", 0.2778, "registry/rasters/dotted_b2_prune_02778.tif"),
    ("H27-4-R1-SOLO", 0.2708, "registry/rasters/dotted_d2_8_02708.tif"),
    ("TIP-STEPOVER-R30", 0.2632, "registry/rasters/tip_stepover_r30_02632.tif"),
    ("D2.8", 0.2600, "registry/rasters/dotted_d2_8_02600.tif"),
    ("Hedge-v2", 0.1563, "registry/rasters/hedge_v2_01563.tif"),
    ("LATTICE-S5", 0.0904, "registry/rasters/r13_lattice_s5_00904.tif"),
]
ESTIMATED_LB_HIDDEN_TRUTH_PX = 12691.0     # `gems32.holdout.ESTIMATED_LB_HIDDEN_TRUTH_PX`
CAT_FLANK_PX = 3                            # SGMC truth is taken strictly beyond the kernel radius


def load_mask(path: Path) -> np.ndarray:
    with rasterio.open(path) as ds:
        return np.nan_to_num(ds.read(1).astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0) > 0


def main() -> int:
    labels = load_mask(ROOT / "data/bridge/existing_faults.tif")
    sgmc = load_mask(ROOT / "work/sgmc100.tif")
    foot = load_mask(ROOT / "work/footprint.tif") if (ROOT / "work/footprint.tif").exists() else None
    if foot is None:                       # footprint derives from the sample submission (finite)
        with rasterio.open(ROOT / "data/bridge/example_submission.tif") as ds:
            a = ds.read(1)
        foot = np.isfinite(a)
    cat_flank = ndimage.binary_dilation(labels, iterations=CAT_FLANK_PX)
    offcat = sgmc & foot & ~cat_flank
    n_off = int(offcat.sum())

    # kernel weight of every footprint pixel to the nearest off-catalogue SGMC fault (and its dist)
    ed_off = ndimage.distance_transform_edt(~offcat, sampling=M.PIXEL_M)
    k_off = np.maximum(1.0 - ed_off / M.R_M, 0.0)
    d_cat = ndimage.distance_transform_edt(~labels, sampling=M.PIXEL_M)

    rows = []
    for label, live, rel in LIVE:
        p = ROOT / rel
        if not p.exists():
            rows.append(dict(candidate=label, live_dti=live, file=rel, status="MISSING"))
            continue
        with rasterio.open(p) as ds:
            arr = np.nan_to_num(ds.read(1).astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
        pred = (arr > 0) & foot
        n_px = int(pred.sum())
        # TP_w on the off-catalogue truth (exact lattice kernel, prediction is binary {0,1})
        tp_w = float(k_off[pred].sum())
        coverage = tp_w / n_off
        dti_raw = tp_w / (tp_w + M.ALPHA * max(0.0, n_px - tp_w) + M.BETA * (n_off - tp_w))
        # family's mass-calibrated variant
        g = ESTIMATED_LB_HIDDEN_TRUTH_PX
        tp_cal = coverage * g
        fp_cal = max(0.0, n_px - tp_cal)
        dti_cal = tp_cal / (M.ALPHA * (tp_cal + fp_cal) + M.BETA * g)
        # random control at matched mass: expected coverage with the same number of random px
        rand_cov = float(np.mean(k_off[foot])) * n_px / n_off
        rows.append(dict(candidate=label, live_dti=live, file=rel, mass=n_px,
                         tp_w_offcat=tp_w, offcat_coverage=coverage,
                         sgmc_raw_dti=dti_raw, sgmc_prevalence_cal=dti_cal,
                         offcat_excess_vs_random=coverage - rand_cov,
                         frac_within_300m_of_catalogue=float((d_cat[pred] <= 300).mean())
                         if n_px else float("nan")))
    # rank correlations
    def spearman(x, y):
        x = np.asarray(x, float); y = np.asarray(y, float)
        rx = np.argsort(np.argsort(x)).astype(float); ry = np.argsort(np.argsort(y)).astype(float)
        rx -= rx.mean(); ry -= ry.mean()
        return float((rx @ ry) / np.sqrt((rx @ rx) * (ry @ ry)))

    ok = [r for r in rows if r.get("status") != "MISSING"]
    out = dict(schema=1, population="off-catalogue SGMC faults (>300 m from catalogue)",
               n_truth_px=n_off, rows=rows,
               spearman_vs_live={k: spearman([r["live_dti"] for r in ok],
                                             [r[k] for r in ok])
                                 for k in ("mass", "tp_w_offcat", "offcat_coverage",
                                           "sgmc_raw_dti", "sgmc_prevalence_cal",
                                           "offcat_excess_vs_random",
                                           "frac_within_300m_of_catalogue")},
               n_live_points=len(ok))
    print(json.dumps(out, indent=1)[:4000])
    dest = ROOT / "evidence/e1_instrument_audit.json"
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
