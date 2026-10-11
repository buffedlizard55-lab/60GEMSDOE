"""E2 - build the lane's submission raster (research artifact; verdict from E3).

Composition (all measured choices recorded in the run card):
  field   = max(anomaly, 0) on channel cells
            x concordance weight (independent-drainage count, >=1 drainages)
            x confound masks (playa fill-depth > 15 m; valley-flat relief < 30 m)
            x lithology down-weight (top-2% |grad iso_grav_anom| off-concordant x0.5)
  dots    = local maxima of the field (min separation 3 px = 300 m, one dot per
            kernel footprint), top-K by field value, K = 37,654 (the champion's
            measured budget) for comparability.
  ring    = no dot within 2 px (200 m) of the catalogue - the measured-winning
            removal rule of the h33 family (catalogue pixels can earn no credit).
  container = all-finite float32 {0,1}, 0 outside the footprint ('-zeros'), the
            container the current champion itself uses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from skimage.feature import peak_local_max

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import lane_channels as LC  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from e1_lane_test import load_inputs, get_channel_stack  # noqa: E402

WORK = ROOT / "data" / "work"
EVID = ROOT / "evidence"
K_DOTS = 37654
CAT_RING_PX = 2
MIN_SEP_PX = 3


def local_relief(z: np.ndarray, valid: np.ndarray, size: int = 5) -> np.ndarray:
    from scipy.ndimage import maximum_filter, minimum_filter
    zz = np.where(valid, z, np.nan)
    mx = maximum_filter(np.nan_to_num(zz, nan=-np.inf), size=size)
    mn = minimum_filter(np.nan_to_num(zz, nan=np.inf), size=size)
    r = mx - mn
    return np.where(valid, r, 0.0)


def build_field(det, slope_band, iso_grav, valid):
    cs = get_channel_stack(det, valid)
    kp = LC.knickpoint_field(cs, valid)
    anomaly = np.maximum(cs["anomaly"], 0.0)

    relief = local_relief(det, valid, size=5)
    playa = (cs["fill_depth"] > 15.0) & valid
    flats = (relief < 30.0) & valid

    g_edge = np.hypot(*np.gradient(np.where(valid, iso_grav, 0.0)))
    thr = np.percentile(g_edge[valid], 98.0)
    litho = (g_edge >= thr) & valid

    conc = kp["distinct_nets"].astype(np.float64)
    w_conc = 1.0 + 0.5 * np.minimum(conc, 4.0)          # >=1: base weight

    field = anomaly * w_conc
    field[playa | flats] = 0.0
    field[litho & (conc < 1)] *= 0.5
    field[~cs["channels"]] = 0.0
    field[~valid] = 0.0
    return field, dict(playa=int(playa.sum()), flats=int(flats.sum()),
                       litho=int(litho.sum()), channels=int(cs["channels"].sum()),
                       knick=int(kp["knick"].sum()),
                       knick_floor=float(kp["knick_floor"]),
                       concordant=int(kp["concordant"].sum()),
                       n_networks=int(kp["n_networks"]))


def rasterize(field, cat, valid, k=K_DOTS, ring_px=CAT_RING_PX, min_sep=MIN_SEP_PX):
    ring = ndimage.binary_dilation(cat > 0, iterations=ring_px)
    allowed = valid & ~ring
    fp = np.where(allowed & (field > 0), field, 0.0)
    coords = peak_local_max(fp, min_distance=min_sep, labels=allowed, exclude_border=False)
    peak_mask = np.zeros(field.shape, dtype=bool)
    if coords.size:
        peak_mask[tuple(coords.T)] = True
    # ONLY field-supported peaks are eligible: pad with -inf so the top-k emitter
    # can never add mass the field does not support (zero-value filler is a bug).
    f2 = np.where(peak_mask, field, -np.inf)
    from gems52.holdout import emit_topk
    em = emit_topk(f2, allowed & peak_mask, k)
    n_peaks = int(peak_mask.sum())
    return em, dict(peaks=n_peaks, emitted=int((em > 0).sum()),
                    budget_requested=k, budget_used=int(min(k, n_peaks)),
                    capacity_limited=bool(n_peaks < k),
                    ring_px=ring_px, min_sep_px=min_sep)


def main():
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "E2 raster-builder"):
        return 0
    import rasterio
    det, slope_band, cat, valid = load_inputs()
    with rasterio.open(ROOT / "data" / "training_features.tif") as ds:
        iso = ds.read(13).astype(np.float64)      # iso_grav_anom
    iso = np.where(valid, iso, 0.0)

    field, comp_stats = build_field(det, slope_band, iso, valid)
    em, emit_stats = rasterize(field, cat, valid)

    np.save(WORK / "lane_field.npy", field.astype(np.float32))
    np.save(WORK / "lane_emission.npy", em)
    out = dict(experiment="E2-lane-build", field=comp_stats, emission=emit_stats,
               field_sum=float(field.sum()),
               dot_mass_outside_footprint=int((em[~valid] > 0).sum()))
    (EVID / "e2_lane_build.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
