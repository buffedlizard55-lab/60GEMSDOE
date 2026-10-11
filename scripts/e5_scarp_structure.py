#!/usr/bin/env python3
"""H63-A / SCARP x STRUCTURE — the two mass-normalised screens that order the live ladder, combined.

Why this exists
---------------
Two *independent* screens each reproduce the owner-reported live ladder at rho ~ +0.94 with the
same single inversion (Hedge-v2 / LATTICE-S5, the two 200k+ dot arms, sit at ~1.0 i.e. random):

  screen A  SGMC off-catalogue kernel ratio   champion 1.62, H27 1.56, TIP 1.51, D2.8 1.43 | 0.96, 1.00
  screen B  LiDAR scarp kernel enrichment     champion 1.84, H27 1.72, TIP 1.66, D2.8 1.57 | 0.72, 0.87

They are *not* the same axis: off-catalogue SGMC traces are themselves scarp-DEPLETED (0.68x of
random, measured), so a dot set can win one screen by losing the other.  The XCRD/H61-A emission
does exactly that (A 2.45, B 0.46) and is therefore not promotable on this evidence.

H63-A asks the complementary question: is there a dot set that is enriched on BOTH?  If the hidden
labels are expert-mapped faults of the GeoDAWN survey -- structures that are both mapped by the
state survey and expressed as surface rupture, just absent from the USGS Quaternary database --
then the ground that maximises both kernels at once is the right place to bet, and it is a
construction no registry artifact occupies (uniqueness is measured, not asserted).

Arms (min_sep 3.0 px, >= 3.5 px from the visible catalogue, inside the footprint, budget 37,654)
    combined   rank by 0.5*k_sgmc_offcat + 0.5*k_scarp   (both 300 m triangular, max-normalised)
    scarp_only rank by k_scarp
    sgmc_only  rank by k_sgmc_offcat

Outputs: evidence/e5_scarp_structure.json, work/h63_dots.npy (bit-packed winner)
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
WORK, EVID, REG = ROOT / "work", ROOT / "evidence", ROOT / "registry" / "rasters"
SCARP = Path("/tmp/gemsdoe48/GEMSDOE48-main/data/external/h52_scarp3m_100m.tif")

R_M, PIXEL_M = 300.0, 100.0
CAT_FLANK_PX = 3
MIN_SEP, MIN_DIST_CAT, SEED = 3.0, 3.5, 6361
LIVE = [("H33-2-B2 champion", 0.2778, "dotted_b2_prune_02778.tif"),
        ("H27-4-R1-SOLO", 0.2708, "dotted_d2_8_02708.tif"),
        ("TIP-STEPOVER-R30", 0.2632, "tip_stepover_r30_02632.tif"),
        ("D2.8", 0.2600, "dotted_d2_8_02600.tif"),
        ("Hedge-v2", 0.1563, "hedge_v2_01563.tif"),
        ("LATTICE-S5", 0.0904, "r13_lattice_s5_00904.tif")]


def rd(p: Path, band: int = 1) -> np.ndarray:
    with rasterio.open(p) as ds:
        return ds.read(band)


def nms(field: np.ndarray, allowed: np.ndarray, budget: int, min_sep: float) -> np.ndarray:
    flat = np.where(allowed, field, -np.inf).ravel()
    cand = np.flatnonzero(np.isfinite(flat))
    order = cand[np.argsort(-flat[cand], kind="stable")][: min(cand.size, budget * 40)]
    H, W = field.shape
    r = int(np.ceil(min_sep))
    pad = np.zeros((H + 2 * r, W + 2 * r), bool)
    sep2 = min_sep ** 2
    keep = []
    for flat_i in order:
        y, x = divmod(int(flat_i), W)
        win = pad[y:y + 2 * r + 1, x:x + 2 * r + 1]
        if win.any():
            wy, wx = np.nonzero(win)
            dy, dx = wy - r, wx - r
            if (dy * dy + dx * dx < sep2).any():
                continue
        pad[y + r, x + r] = True
        keep.append(flat_i)
        if len(keep) >= budget:
            break
    out = np.zeros(H * W, bool)
    out[np.asarray(keep, int)] = True
    return out.reshape(H, W)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=37654)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    foot = np.isfinite(rd(ROOT / "data/bridge/example_submission.tif").astype(np.float32))
    with rasterio.open(ROOT / "data/bridge/example_submission.tif") as ds:
        foot = np.isfinite(ds.read(1))
    cat = rd(WORK / "labels.tif") > 0
    sgmc = rd(WORK / "sgmc100.tif") > 0
    d_cat = ndimage.distance_transform_edt(~cat)

    if SCARP.exists():
        with rasterio.open(SCARP) as ds:
            g12, valid = ds.read(2).astype(np.float32), ds.read(1) != -32768
        scarp_w = np.clip((g12 - 100.0) / 230.0, 0.0, 1.0)
        scarp_w[~valid] = 0.0
    else:
        raise SystemExit("LiDAR scarp product missing (/tmp mirror is ephemeral) -- restore first")

    off = sgmc & foot & ~ndimage.binary_dilation(cat, iterations=CAT_FLANK_PX)
    k_sgmc = np.maximum(1.0 - ndimage.distance_transform_edt(~off, sampling=PIXEL_M) / R_M, 0.0)
    strong = (g12 >= 200) & valid                        # top 6.7 % of the scarp-count product
    k_scarp = np.maximum(1.0 - ndimage.distance_transform_edt(~strong, sampling=PIXEL_M) / R_M, 0.0)

    allowed = foot & (d_cat > MIN_DIST_CAT)
    kn, sc = k_sgmc / max(k_sgmc[foot].max(), 1e-9), k_scarp / max(k_scarp[foot].max(), 1e-9)
    rng = np.random.default_rng(SEED)
    arms = {"combined": (0.5 * kn + 0.5 * sc + 1e-6 * rng.random(foot.shape),
                         allowed & (kn > 0) & (sc > 0)),
            "scarp_only": (sc + 1e-6 * rng.random(foot.shape), allowed),
            "sgmc_only": (kn + 1e-6 * rng.random(foot.shape), allowed)}

    ref_rows = {}
    for name, live, f in LIVE:
        m = np.nan_to_num(rd(REG / f), nan=0.0) > 0
        ref_rows[name] = dict(live=live, mass=int(m.sum()),
                              ratio_a=round(float(k_sgmc[m].mean() / k_sgmc[foot].mean()), 4),
                              ratio_b=round(float(k_scarp[m].mean() / k_scarp[foot].mean()), 4))
    report = dict(schema="e5-scarp-structure/1", budget=args.budget,
                  screen_a="SGMC off-catalogue 300 m triangular kernel, mean at dots / footprint mean",
                  screen_b="LiDAR scarp (h_gate12>=200) 300 m kernel, mean at dots / footprint mean",
                  live_ladder=ref_rows, arms={}, best=None)
    print("[e5] ladder:", json.dumps(ref_rows))
    best = None
    for name, (field, allow) in arms.items():
        t1 = time.time()
        m = nms(field, allow, args.budget, MIN_SEP)
        n = int(m.sum())
        ra = float(k_sgmc[m].sum() / k_sgmc[m].size / 0.0) if False else float(k_sgmc[m].mean() / k_sgmc[foot].mean())
        rb = float(k_scarp[m].mean() / k_scarp[foot].mean())
        row = dict(mass=n, ratio_a=round(ra, 4), ratio_b=round(rb, 4),
                   frac_within_300m_of_catalogue=round(float((d_cat[m] <= 3).mean()), 4))
        report["arms"][name] = row
        print(f"[e5] {name:<11} {json.dumps(row)}  ({time.time()-t1:.0f}s)")
        score = ra + rb
        if best is None or score > best[1]:
            best = (name, score, m)
        if name == "combined":
            np.save(WORK / "h63_dots.npy", np.packbits(m.ravel()))
    report["best"] = dict(arm=best[0], combined_screen=round(best[1], 4))

    # uniqueness of the winner against every registry raster
    cand, cpix = best[2], np.argwhere(best[2])
    fy, fx = np.nonzero(foot)
    sub = slice(None, None, 7)
    uniq = {"max_abs_spearman": 0.0, "worst_peer": None, "max_within_3px_frac": 0.0,
            "worst_peer_3px": None, "n_registry_rasters": 0}
    for rp in sorted(REG.glob("*.tif")):
        other = np.nan_to_num(rd(rp), nan=0.0) > 0
        if other.shape != cand.shape or other.sum() == 0:
            continue
        uniq["n_registry_rasters"] += 1
        rho = float(spearmanr(cand[sub, sub].ravel(), other[sub, sub].ravel()).statistic)
        ed = ndimage.distance_transform_edt(~other)
        frac = float(np.mean(ed[cpix[:, 0], cpix[:, 1]] <= 3.0))
        if abs(rho) > abs(uniq["max_abs_spearman"]):
            uniq["max_abs_spearman"], uniq["worst_peer"] = rho, rp.name
        if frac > uniq["max_within_3px_frac"]:
            uniq["max_within_3px_frac"], uniq["worst_peer_3px"] = frac, rp.name
        _ = np.random.default_rng(7).integers(0, fy.size, size=min(cpix.shape[0], 5000))
    uniq["pass_spearman_gate"] = abs(uniq["max_abs_spearman"]) <= 0.90
    uniq["pass_within_3px_rule"] = uniq["max_within_3px_frac"] <= 0.70
    report["uniqueness"] = uniq
    print("[e5] uniqueness:", json.dumps({k: uniq[k] for k in
                                          ("max_abs_spearman", "worst_peer", "max_within_3px_frac",
                                           "worst_peer_3px", "pass_spearman_gate",
                                           "pass_within_3px_rule")}))
    EVID.mkdir(exist_ok=True)
    (EVID / "e5_scarp_structure.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"[e5] wrote evidence/e5_scarp_structure.json ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
