#!/usr/bin/env python3
"""H62-A / SGMC-LOCALITY screen (three-pass build, pass 1).

Hypothesis H62-A
----------------
The hidden expert-labelled set is "faults mapped by geologists that the *public USGS
Quaternary* database does not contain".  The USGS State Geologic Map Compilation (SGMC,
DOI 10.5066/P1A3DQZK) is exactly such a body of mapping: it carries faults the QFaults layer
does not, and it carries the *same* faults at different (sometimes better) geometry.  So the
question the metric asks -- "is there hidden truth within 300 m of this dot?" -- should be
answered by locality on the SGMC trace, not by a topo-ridge belief field.

Falsifier measured here, independently of the SGMC itself
--------------------------------------------------------
The h52 LiDAR scarp product (counts of 3 m cells passing a 12-sample gate) is an independent
surface-rupture channel that shares no bytes with the SGMC.  If SGMC off-catalogue traces are
real surface faults, dots placed on them must be scarp-ENRICHED (enrichment > 1).  If the
off-catalogue SGMC set were mostly non-Quaternary lineaments (bedding, intrusions, contacts),
enrichment would be near or below 1 and H62-A fails this independent check.

Arms (all emitted on the competition lattice: min_sep 3.0 px, >= 2.5 px from the catalogue,
inside the footprint; budget 37,654 = the live champion's mass)
    sgmc_pure      on SGMC off-catalogue traces only
    sgmc_scarp     SGMC off-catalogue traces, ranked by independent scarp weight (tiebreak)
    sgmc_hybrid    SGMC off-catalogue traces x (XCRD field + scarp weight) -- geomorphic support
    xcrd_control   the XCRD field alone, same emitter (control for the emitter itself)
    random         uniform random allowed pixels, same NMS rules (null control)

Outputs: evidence/e3_sgmc_locality.json, work/sgmc_dots.npy (bit-packed, best arm by the
E1 screen; unpack with np.unpackbits(...).reshape(3730, 3292))
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
EVID = ROOT / "evidence"
REG = ROOT / "registry" / "rasters"
SCARP = Path("/tmp/gemsdoe48/GEMSDOE48-main/data/external/h52_scarp3m_100m.tif")

PIXEL_M = 100.0
R_M = 300.0
K_PX = R_M / PIXEL_M                 # 3 px kernel radius
CAT_FLANK_PX = 3                     # SGMC truth taken strictly beyond the kernel radius
MIN_SEP = 3.0
MIN_DIST_CAT = 2.5
BUDGET = 37654                       # live champion mass
SEED = 6261


def read(rel: str, band: int = 1) -> np.ndarray:
    with rasterio.open(ROOT / rel) as ds:
        return ds.read(band)


def nms(field: np.ndarray, allowed: np.ndarray, budget: int, min_sep: float) -> np.ndarray:
    """Deterministic greedy thinning at min_sep, ranked by `field` (the shared emitter rule)."""
    flat = np.where(allowed, field, -np.inf).ravel()
    cand = np.flatnonzero(np.isfinite(flat))
    order = cand[np.argsort(-flat[cand], kind="stable")][: min(cand.size, budget * 12)]
    H, W = field.shape
    taken = np.zeros((H, W), bool)
    sep2 = min_sep ** 2
    cell = max(1, int(np.ceil(min_sep)))
    keep: list[tuple[int, int]] = []
    r = int(np.ceil(min_sep))
    pad = np.zeros((H + 2 * r, W + 2 * r), bool)
    for flat_i in order:
        y, x = divmod(int(flat_i), W)
        y0, x0 = y, x                        # padded coordinates of taken neighbours
        win = pad[y0:y0 + 2 * r + 1, x0:x0 + 2 * r + 1]
        if win.any():
            wy, wx = np.nonzero(win)
            dy = wy + y0 - (y + r)
            dx = wx + x0 - (x + r)
            if (dy * dy + dx * dx < sep2).any():
                continue
        pad[y + r, x + r] = True
        keep.append((y, x))
        if len(keep) >= budget:
            break
    out = np.zeros((H, W), np.float32)
    for y, x in keep:
        out[y, x] = 1.0
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=BUDGET)
    ap.add_argument("--budget-sweep", action="store_true",
                    help="also screen every arm at 8k/16k/25k mass")
    args = ap.parse_args()
    t0 = time.time()

    foot = np.isfinite(read("data/bridge/example_submission.tif"))
    cat = read("work/labels.tif") > 0
    sgmc = read("work/sgmc100.tif") > 0
    if SCARP.exists():
        with rasterio.open(SCARP) as ds:
            g12 = ds.read(2).astype(np.float32)
            valid = ds.read(1) != -32768
        scarp_w = np.clip((g12 - 100.0) / 230.0, 0.0, 1.0)
        scarp_w[~valid] = 0.0
    else:
        scarp_w = np.zeros_like(foot, np.float32)

    d_cat = ndimage.distance_transform_edt(~cat)
    d_sgmc = ndimage.distance_transform_edt(~sgmc)
    allowed = foot & (d_cat > MIN_DIST_CAT)

    off = sgmc & foot & ~ndimage.binary_dilation(cat, iterations=CAT_FLANK_PX)
    n_off = int(off.sum())
    ed_off = ndimage.distance_transform_edt(~off, sampling=PIXEL_M)
    k_off = np.maximum(1.0 - ed_off / R_M, 0.0)
    k_off_mean = float(k_off[foot].mean())

    w_off = np.where(foot & (d_cat > CAT_FLANK_PX) & (d_sgmc > CAT_FLANK_PX), scarp_w, 0.0)
    w_known = np.where(foot & (d_cat <= CAT_FLANK_PX), scarp_w, 0.0)
    a_off = foot & (d_cat > CAT_FLANK_PX) & (d_sgmc > CAT_FLANK_PX)
    a_known = foot & (d_cat <= CAT_FLANK_PX)

    # --- fields the arms rank on -------------------------------------------------
    sgmc_ind = sgmc.astype(np.float32)
    xcrd = np.load(WORK / "xcrd_field.npy") if (WORK / "xcrd_field.npy").exists() \
        else np.zeros_like(foot, np.float32)
    xn = xcrd / max(float(xcrd.max()), 1e-9)
    rng = np.random.default_rng(SEED)
    noise = rng.random(foot.shape).astype(np.float32)

    on_trace = allowed & sgmc_ind.astype(bool)
    arms = {
        "sgmc_pure": (sgmc_ind + 1e-6 * noise, on_trace),
        "sgmc_scarp": (sgmc_ind + 0.001 * scarp_w + 1e-6 * noise, on_trace),
        "sgmc_hybrid": (sgmc_ind + 0.1 * xn + 0.1 * scarp_w + 1e-6 * noise, on_trace),
        "xcrd_control": (xcrd, allowed),
        "random": (noise, allowed),
    }

    def metrics(dots: np.ndarray) -> dict:
        p = dots > 0
        n = int(p.sum())
        tp = float(k_off[p].sum())
        cov = tp / n_off if n_off else 0.0
        exp = k_off_mean * n / n_off if n_off else 0.0
        wgot = float(w_off[p].sum())
        wexp = float(w_off[a_off].mean()) * n if a_off.any() else 0.0
        kgot = float(w_known[p].sum())
        kexp = float(w_known[a_known].mean()) * n if a_known.any() else 0.0
        return dict(mass=n,
                    sgmc_offcat_coverage=round(cov, 6),
                    expected_if_random=round(exp, 6),
                    e1_offcat_excess=round(cov - exp, 6),
                    scarp_offcat_enrichment=round(wgot / wexp, 4) if wexp > 0 else None,
                    scarp_known_fault_enrichment=round(kgot / kexp, 4) if kexp > 0 else None,
                    median_dist_to_catalogue_px=round(float(np.median(d_cat[p])), 2))

    report: dict = {"schema": "e3-sgmc-locality/1", "budget": args.budget,
                    "population": dict(sgmc_px=int(sgmc.sum()), offcat_sgmc_px=n_off,
                                       footprint_px=int(foot.sum()),
                                       allowed_px=int(allowed.sum()),
                                       on_trace_available=int(on_trace.sum())),
                    "arms": {}, "mass_sweep": {}}
    best = None
    for name, (field, allow) in arms.items():
        dots = nms(field, allow, args.budget, MIN_SEP)
        report["arms"][name] = metrics(dots)
        print(f"[e3] {name:<12} {json.dumps(report['arms'][name])}  ({time.time()-t0:.0f}s)")
        if name != "random" and (best is None or
                                 report["arms"][name]["e1_offcat_excess"] > best[1]):
            best = (name, report["arms"][name]["e1_offcat_excess"], dots)
        np.save(WORK / f"e3_dots_{name}.npy", np.packbits((dots > 0).ravel()))

    if best is not None:
        np.save(WORK / "sgmc_dots.npy", np.packbits((best[2] > 0).ravel()))
        report["best_arm"] = {"name": best[0], "e1_offcat_excess": best[1]}
        print(f"[e3] best arm by E1 screen: {best[0]} (excess {best[1]:+.6f}) -> work/sgmc_dots.npy")

    # --- uniqueness gates (brief hard rule) --------------------------------------
    cand = best[2] > 0 if best else None
    if cand is not None:
        cpix = np.argwhere(cand)
        sub = slice(None, None, 7)
        uniq = {"max_abs_spearman": 0.0, "worst_peer": None,
                "max_within_3px_excess": -9.9, "worst_peer_3px": None}
        for rp in sorted(REG.glob("*.tif")):
            other = read(str(rp.relative_to(ROOT))) > 0
            if other.shape != cand.shape or other.sum() == 0:
                continue
            rho = spearmanr(cand[sub, sub].ravel(), other[sub, sub].ravel()).statistic
            if abs(rho) > abs(uniq["max_abs_spearman"]):
                uniq["max_abs_spearman"], uniq["worst_peer"] = float(rho), rp.name
            ed = ndimage.distance_transform_edt(~other)
            frac = float(np.mean(ed[cpix[:, 0], cpix[:, 1]] <= K_PX))
            fy, fx = np.nonzero(foot)
            pick = np.random.default_rng(7).integers(0, fy.size, size=cpix.shape[0])
            exp3 = float(np.mean(ed[fy[pick], fx[pick]] <= K_PX))
            if frac - exp3 > uniq["max_within_3px_excess"]:
                uniq.update(max_within_3px_excess=frac - exp3, worst_peer_3px=rp.name,
                            worst_peer_3px_frac=round(frac, 5),
                            worst_peer_3px_random=round(exp3, 5))
        uniq["pass_spearman_gate"] = abs(uniq["max_abs_spearman"]) <= 0.90
        uniq["pass_within_3px_gate"] = uniq["max_within_3px_excess"] <= 0.0
        report["uniqueness"] = uniq
        print("[e3] uniqueness:", json.dumps(uniq))

    EVID.mkdir(exist_ok=True)
    (EVID / "e3_sgmc_locality.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"[e3] wrote evidence/e3_sgmc_locality.json ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
