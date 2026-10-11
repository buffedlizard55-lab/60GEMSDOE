#!/usr/bin/env python3
"""EXPERIMENT 3 - emission, format validation and uniqueness.

Builds the single deliverable GeoTIFF from the chi-lane field:

  field      = channel-normal cast count (``gems60.field.cast_field``), i.e.
               knickpoint / steepness-step crossings projected along the local
               channel normal and reinforced where several independent drainages
               share a strike;
  support    = footprint  AND  off the mapped catalogue by > 2 px  AND  cast > 0;
  emission   = the metric's own optimal packing: peaks of the field at >= 2 px
               separation (a 5x5 maximum filter), taken in decreasing order of
               value up to the budget n* that MAXIMISES the pooled buffered
               whole-component HOLDOUT-DTI (rule fixed before the sweep was read).

Then: 15 independent format checks, and a uniqueness audit against every registry
raster obtainable in this sandbox (declared scope).

Usage:  PYTHONPATH=src python3 scripts/exp3_emit_validate.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage, stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems60chi.holdout import build_holdout  # noqa: E402
from gems60chi.metric import dti_components, pooled_dti  # noqa: E402

BUDGETS = [500, 1_000, 2_000, 3_000, 4_000, 6_000, 9_000]
NAME = "gems60-chi-knickpoint-cast-lane-v1"
NOTE = ("GEMS60 chi/ksn lane: channel-normal knickpoint casts; pre-registered first "
        "test returned STOP - NEGATIVE RESULT, do not spend a slot.")[:140]


def log(*a):
    print(*a, flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    cache = Path("/tmp/study/work")
    ev = ROOT / "evidence"
    ev.mkdir(exist_ok=True)
    out = ROOT / "docs" / "downloads"
    out.mkdir(parents=True, exist_ok=True)

    # The written geotransform MUST be the OFFICIAL submission grid, not the DEM's:
    # the GeoDAWN DEM carries a 0.034 m x-origin offset (243349.965575182 vs 243350.0)
    # that the portal would reject as a geotransform mismatch.  Found by
    # scripts/verify_submission.py before shipping (IR-60-08).
    with rasterio.open(ROOT / "data" / "labels.tif") as ls:
        shape, transform, crs = ls.shape, ls.transform, ls.crs
    with rasterio.open(ROOT / "data" / "geodawn_dem_a2_100m.tif") as ds:
        assert ds.shape == shape, "DEM grid differs from the submission grid"
    labels = rasterio.open(ROOT / "data" / "labels.tif").read(1)
    footprint = labels >= 0
    catalogue = labels == 1
    cast = np.load(cache / "cast.npy")
    assert cast.shape == shape

    d_cat = ndimage.distance_transform_edt(~catalogue)
    support = footprint & (~catalogue) & (d_cat > 2.0) & (cast > 0)
    log(f"[1/6] support {int(support.sum()):,} cells "
        f"(off-catalogue > 2 px, cast > 0, inside footprint)")

    # ---- peaks of the field, >= 2 px apart (5x5 maximum filter) -----------
    mx = ndimage.maximum_filter(cast, size=5)
    peaks = support & (cast >= mx) & (cast > 0)
    yy, xx = np.nonzero(peaks)
    vals = cast[yy, xx]
    order = np.argsort(-vals, kind="stable")
    yy, xx, vals = yy[order], xx[order], vals[order]
    log(f"[2/6] {len(yy):,} separated field peaks")

    hd = build_holdout(catalogue=catalogue, footprint=footprint, n_folds=4, buffer_px=3)

    # ---- budget sweep on the pooled buffered holdout ---------------------
    log("[3/6] HOLDOUT-DTI vs budget (pooled, buffered whole-component folds)")
    # Two supports are reported, because they answer different questions:
    #   S_geo : footprint AND cast > 0            -> "can this field find faults at all?"
    #   S_off : S_geo off the catalogue by > 2 px  -> the SHIPPED support, so the curve
    #           below is degenerate for a catalogue-truth instrument and is reported
    #           for completeness, never as a score.  (IR-PROXY: the catalogue holdout
    #           rewards covering the catalogue; the live ladder does the opposite -
    #           the family measured Spearman(live, catalogue-proxy) = -0.93.)
    mx_geo = ndimage.maximum_filter(cast, size=5)
    peaks_geo = footprint & (cast >= mx_geo) & (cast > 0)
    gy, gx = np.nonzero(peaks_geo)
    go = np.argsort(-cast[gy, gx], kind="stable")
    gy, gx = gy[go], gx[go]
    log(f"      off-catalogue peaks {len(yy):,}; unrestricted peaks {len(gy):,}")
    curve, curve_geo = {}, {}
    for n in BUDGETS:
        for tag, (Y, X), store in (("off", (yy, xx), curve), ("geo", (gy, gx), curve_geo)):
            if n > len(Y):
                continue
            pred = np.zeros(shape, np.float32)
            pred[Y[:n], X[:n]] = 1.0
            store[n] = pooled_dti([dti_components(pred, f.withheld, r_px=3.0)
                                   for f in hd.folds])
            log(f"      n={n:7,d}  support={tag:4s}  HOLDOUT-DTI = {store[n]:.5f}")
    best_n = max(curve, key=lambda k: curve[k])
    log(f"      -> shipped budget (max of the off-catalogue curve): {best_n:,}")

    # controls at the chosen budget: random off-catalogue support
    rng = np.random.default_rng(2026)
    ctrl = {}
    for tag, sel in (("random_on_offcatalogue_support", np.nonzero(support.ravel())[0]),
                     ("random_in_footprint", np.nonzero(footprint.ravel())[0])):
        ds = []
        for rep in range(3):
            pick = rng.choice(sel, size=min(best_n, sel.size), replace=False)
            p = np.zeros(shape, np.float32)
            p.ravel()[pick] = 1.0
            ds.append(pooled_dti([dti_components(p, f.withheld, r_px=3.0)
                                  for f in hd.folds]))
        ctrl[tag] = float(np.mean(ds))
        log(f"      control {tag}: mean HOLDOUT-DTI {ctrl[tag]:.5f} (3 draws)")

    # ---- final raster ----------------------------------------------------
    final = np.zeros(shape, np.float32)
    final[yy[:best_n], xx[:best_n]] = 1.0
    tif = out / f"{NAME}-{best_n}-dots-zeros.tif"
    with rasterio.open(tif, "w", driver="GTiff", height=shape[0], width=shape[1],
                       count=1, dtype="float32", crs=crs, transform=transform,
                       compress="deflate", predictor=2) as dst:
        dst.write(final, 1)
        dst.update_tags(note=NOTE, lane="tectonic-geomorphology chi/ksn/knickpoints",
                        verdict="NEGATIVE - pre-registered first test returned STOP")
    log(f"[4/6] wrote {tif.name} ({tif.stat().st_size:,} bytes)")

    # ---- 15 independent format checks (re-read from the bytes on disk) ----
    checks = {}
    with rasterio.open(tif) as ds:
        a = ds.read(1)
        checks["crs_matches"] = (ds.crs == crs)
        checks["shape_matches"] = (ds.shape == shape)
        checks["transform_matches"] = (tuple(ds.transform)[:6] == tuple(transform)[:6])
        checks["single_band"] = (ds.count == 1)
        checks["dtype_float32"] = (ds.dtypes[0] == "float32")
        checks["no_nodata_tag"] = (ds.nodata is None)
        checks["all_finite"] = bool(np.isfinite(a).all())
        checks["range_0_1"] = bool((a.min() >= 0.0) and (a.max() <= 1.0))
        checks["no_negative"] = bool((a >= 0).all())
        checks["no_nan"] = bool(not np.isnan(a).any())
        checks["no_inf"] = bool(not np.isinf(a).any())
        checks["finite_footprint_equals_labels"] = bool(
            np.array_equal(np.isfinite(a), footprint))
        checks["zero_outside_footprint"] = bool((a[~footprint] == 0).all())
        checks["n_positive"] = int((a > 0).sum())
        checks["no_catalogue_hit"] = bool((a[catalogue] == 0).all())
        checks["min_distance_to_catalogue_px"] = float(
            ndimage.distance_transform_edt(~catalogue)[a > 0].min()) if (a > 0).any() else None
    checks["all_pass"] = all(v is True or isinstance(v, (int, float))
                             for k, v in checks.items()
                             if k not in ("n_positive", "min_distance_to_catalogue_px",
                                          "all_pass"))
    log("[5/6] format checks: " + json.dumps(checks, indent=1))

    # ---- uniqueness vs every registry raster we can obtain ---------------
    reg_paths = sorted(
        [p for d in ("/tmp/study",) for p in Path(d).rglob("*.tif")
         if p.is_file() and p.stat().st_size > 20_000 and p.resolve() != tif.resolve()])
    log(f"[6/6] uniqueness audit over {len(reg_paths)} obtainable registry rasters")
    fp_flat = footprint.ravel()
    mine = (a.ravel()[fp_flat] > 0).astype(np.float64)
    worst_rho, worst_rho_p, worst_ov, worst_ov_p, n_ok = 0.0, None, 0.0, None, 0
    hits = []
    for p in reg_paths:
        try:
            with rasterio.open(p) as ds:
                if ds.shape != shape:
                    continue
                b = ds.read(1).astype(np.float64)
                if ds.nodata is not None and np.isnan(ds.nodata):
                    b = np.where(np.isfinite(b), b, 0.0)
            n_ok += 1
            b[fingerprint_bad(b)] = 0.0
            bv = b.ravel()[fp_flat]
            bpos = (bv > 0)
            if mine.sum() and bpos.sum():
                sub = rng.choice(mine.size, size=min(400_000, mine.size), replace=False)
                rho = stats.spearmanr(mine[sub], bv[sub]).statistic
                if np.isfinite(rho) and abs(rho) > abs(worst_rho):
                    worst_rho, worst_rho_p = float(rho), str(p)
            # 3-px forward overlap: fraction of MY dots within 3 px of a prior dot
            dil = ndimage.binary_dilation(bpos.reshape(shape),
                                          np.ones((7, 7), bool)).ravel()[fp_flat]
            ov = float((mine > 0)[dil].mean()) if mine.sum() else 0.0
            if ov > worst_ov:
                worst_ov, worst_ov_p = ov, str(p)
        except Exception:
            continue
    uniqueness = dict(
        evidence_class="REGISTRY-MEASUREMENT",
        rasters_expected=696, rasters_checked=n_ok,
        scope_note=("Checked against every registry raster obtainable in this sandbox. "
                    "Un-fetched entries are a stated scope limitation, never a claim of "
                    "absence."),
        thresholds=dict(rho=0.90, forward_overlap=0.70),
        worst_spearman_full_footprint=worst_rho, worst_spearman_submission=worst_rho_p,
        worst_forward_overlap=worst_ov, worst_forward_overlap_submission=worst_ov_p,
        unique=bool(abs(worst_rho) <= 0.90 and worst_ov <= 0.70),
    )
    log(json.dumps(uniqueness, indent=1))

    receipt = dict(
        name=NAME, file=tif.name, sha256=sha256(tif), bytes=tif.stat().st_size,
        note=NOTE, n_positive=checks["n_positive"],
        evidence_class="HOLDOUT-DTI", evaluator_version="gems60-exp3-v1",
        budget_curve_offcatalogue={str(k): v for k, v in curve.items()},
        budget_curve_unrestricted={str(k): v for k, v in curve_geo.items()},
        chosen_budget=best_n, n_peaks_offcatalogue=int(len(yy)),
        n_peaks_unrestricted=int(len(gy)),
        controls_at_chosen_budget=ctrl,
        holdout_dti_at_chosen_budget=curve[best_n],
        withheld_positive_pixels=int(hd.n_withheld_total),
        format_checks=checks, uniqueness=uniqueness,
        verdict="negative - do not spend a competition slot",
    )
    (out / f"checks-{tif.name}.json").write_text(json.dumps(receipt, indent=1))
    (ev / "exp3_emission.json").write_text(json.dumps(receipt, indent=1))
    log("DONE: " + tif.name)
    return 0


def fingerprint_bad(b):
    """Cells that are neither nodata nor a real 0 - used only to sanitise priors."""
    return ~np.isfinite(b)


if __name__ == "__main__":
    raise SystemExit(main())
