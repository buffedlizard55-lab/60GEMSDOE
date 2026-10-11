#!/usr/bin/env python3
"""Stage A of the tectonic-geomorphology lane: build and cache the DEM-derived
drainage / chi / ksn / knickpoint feature stack.

Everything here is *catalogue-independent*: it is a function of the pinned
``det_elev`` band only, so it is legal to compute once for the whole footprint
and reuse inside every hide-and-recover fold.  Only the strike corridor (which
uses the *visible* catalogue) is fold-dependent and is computed in Stage B.

Outputs (git-ignored cache + a committed receipt):
    .cache/features60/<name>.npy        float32/int32 rasters on the 3730x3292 grid
    evidence/geomorph_feature_cache.json  provenance, parameters, diagnostics
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems60 import geomorph as gm                      # noqa: E402

CACHE = ROOT / ".cache" / "features60"
EVIDENCE = ROOT / "evidence" / "geomorph_feature_cache.json"

A_MIN_CELLS = 20          # 0.20 km^2 contributing area defines a channel pixel
KNICK_WINDOW = 5          # cells (500 m) upstream/downstream for the step ratio
FILL_RAISE_PLAYA_M = 20.0 # filled-flat raise above which a cell is a closed-basin floor
STEP_FLOOR_KSN = 0.5      # ksn floor added to both window means before the ratio
STEP_WINSOR = float(np.log(10.0))   # cap the log ratio at 10x (declared, not tuned)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save(name: str, arr: np.ndarray) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{name}.npy"
    tmp = CACHE / f"{name}.tmp.npy"          # np.save appends .npy if it is missing
    np.save(tmp, arr)
    tmp.replace(p)
    return dict(name=name, dtype=str(arr.dtype), shape=list(arr.shape),
                file=str(p.relative_to(ROOT)), sha256=sha256(p))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--band", type=int, default=12)
    ap.add_argument("--a-min", type=int, default=A_MIN_CELLS)
    ap.add_argument("--window", type=int, default=KNICK_WINDOW)
    ap.add_argument("--theta", type=float, default=gm.THETA_REF)
    a = ap.parse_args()
    t0 = time.time()
    steps: list[dict] = []

    def mark(step: str, **kw):
        steps.append(dict(step=step, t_s=round(time.time() - t0, 2), **kw))
        print(f"[A] {step} ({time.time() - t0:.1f}s) {kw if kw else ''}", flush=True)

    import rasterio
    with rasterio.open(ROOT / "data/official/labels.tif") as src:
        labels = src.read(1)
    footprint = labels >= 0
    catalogue = labels == 1
    mark("labels", footprint_pixels=int(footprint.sum()), catalogue_pixels=int(catalogue.sum()))

    feature_path = ROOT / "data/official/training_features.tif"
    z = gm.load_dem(feature_path, band=a.band, footprint=footprint)
    mark("dem_loaded", band=a.band, finite=int(np.isfinite(z).sum()),
         nan_inside_footprint=int((footprint & ~np.isfinite(z)).sum()),
         min=float(np.nanmin(z)), max=float(np.nanmax(z)),
         sha256=sha256(feature_path))
    z, n_repaired = gm.fill_nans_local(z, footprint)
    mark("nan_repaired", repaired=int(n_repaired),
         still_nan=int((footprint & ~np.isfinite(z)).sum()))

    zf, stats = gm.priority_flood(z, footprint)
    mark("priority_flood", **stats)
    code = gm.d8_dircode(zf, footprint)
    recv = gm.d8_receivers(code)
    mark("d8", outlets=int((code < 0).sum()), routed=int((code >= 0).sum()))
    acc, level = gm.upslope_area(code, footprint)
    mark("upslope_area", max_cells=float(acc.max()), max_level=int(level.max()),
         mean_cells_inside_footprint=float(acc[footprint].mean()))
    term = gm.drainage_identity(code, footprint)
    mark("drainage_identity", distinct_terminals=int(np.unique(term[footprint]).size))
    chi = gm.chi_field(acc, code, footprint, level, theta=a.theta)
    mark("chi", theta=a.theta, max_chi=float(np.nanmax(chi)),
         median_chi_channels=float(np.nanmedian(chi[footprint & (acc >= a.a_min)])))
    ksn = gm.ksn_local(zf, acc, code, footprint, theta=a.theta)
    channel = footprint & (acc >= a.a_min) & np.isfinite(ksn)
    mark("ksn", channel_pixels=int(channel.sum()),
         ksn_p50=float(np.nanpercentile(ksn[channel], 50)),
         ksn_p95=float(np.nanpercentile(ksn[channel], 95)),
         ksn_p999=float(np.nanpercentile(ksn[channel], 99.9)))

    donor, has_donor = gm.main_stem_donor(code, acc, channel)
    up, down = gm.window_means(ksn, donor, has_donor & channel, recv,
                               footprint & (recv >= 0), a.window)
    # Declared regularisation: both window means are floored at STEP_FLOOR_KSN so
    # that a near-zero downstream ksn (an alluvial reach, or a filled flat) cannot
    # manufacture an unbounded ratio, and the log ratio is winsorised at log(10).
    with np.errstate(invalid="ignore", divide="ignore"):
        ok = np.isfinite(up) & np.isfinite(down)
        ratio = np.where(ok, (np.maximum(up, 0.0) + STEP_FLOOR_KSN)
                         / (np.maximum(down, 0.0) + STEP_FLOOR_KSN), np.nan)
    step = np.clip(np.log(np.maximum(ratio, 1e-6)), -STEP_WINSOR, STEP_WINSOR)
    mark("knickpoint_step", window=a.window,
         channel_with_both_windows=int(np.isfinite(step)[channel].sum()),
         step_p50=float(np.nanpercentile(step[channel], 50)),
         step_p95=float(np.nanpercentile(step[channel], 95)),
         step_p999=float(np.nanpercentile(step[channel], 99.9)),
         frac_step_positive=float(np.nanmean(step[channel] > 0)),
         step_floor_ksn=STEP_FLOOR_KSN, step_winsor=STEP_WINSOR)

    raise_m = zf - z
    playa = footprint & (raise_m > FILL_RAISE_PLAYA_M)
    mark("confound_masks", playa_basin_floor_pixels=int(playa.sum()),
         max_raise_m=float(np.nanmax(raise_m[footprint])),
         raise_p99=float(np.nanpercentile(raise_m[footprint], 99)))

    saved = [save("dem_filled", zf.astype(np.float32)),
             save("dircode", code.astype(np.int8)),
             save("acc", acc.astype(np.float32)),
             save("level", level.astype(np.int32)),
             save("terminal", term.astype(np.int32)),
             save("chi", chi.astype(np.float32)),
             save("ksn", ksn.astype(np.float32)),
             save("donor", donor.astype(np.int32)),
             save("step", step.astype(np.float32)),
             save("channel", channel),
             save("playa", playa),
             save("raise_m", raise_m.astype(np.float32)),
             save("footprint", footprint),
             save("catalogue", catalogue)]
    mark("cached", files=len(saved))

    receipt = dict(evidence_class="DATA-MEASUREMENT",
                   lane="tectonic-geomorphology: channel steepness and knickpoints",
                   generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   parameters=dict(band=a.band, a_min_cells=a.a_min, window_cells=a.window,
                                   theta_ref=a.theta, a0_m2=gm.A0_M2, cell_m=gm.CELL_M,
                                   fill_eps_m=gm.FILL_EPS, bucket_q_m=gm.BUCKET_Q,
                                   playa_raise_threshold_m=FILL_RAISE_PLAYA_M),
                   source=dict(file=str(feature_path.relative_to(ROOT)),
                               sha256=sha256(feature_path),
                               band_description=None),
                   provenance=("hash-pinned third-party bridge of the DrivenData competition file; "
                               "official origin not independently authenticated"),
                   steps=steps, files=saved)
    with rasterio.open(feature_path) as src:
        receipt["source"]["band_description"] = src.descriptions[a.band - 1]
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(f"[A] receipt -> {EVIDENCE.relative_to(ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
