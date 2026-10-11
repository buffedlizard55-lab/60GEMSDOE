#!/usr/bin/env python3
"""H61-A / XCRD decision screen.

Purpose
-------
Decide, without spending a submission slot, whether the XCRD emission (H61-A) is a real
improvement over the live promoted ladder.  This is the E1 instrument applied to a candidate
plus three guards:

  1. E1 screen            mass-normalised off-catalogue excess vs the 7 owner-reported live
                          points; linear + Spearman projection for the candidate
                          (a *projection*, never a score).
  2. Scarp control        the candidate AND the live artifacts scored on the h52 LiDAR scarp
                          weight, so the candidate's scarp behaviour has a baseline
                          (a candidate that is much worse than the champion on scarp evidence
                          is not trustworthy even if the E1 screen likes it).
  3. Uniqueness           |Spearman| against every registry raster and the within-3-px
                          overlap excess vs random; both hard gates from the brief.

Output: evidence/e2b_xcrd_screen.json   (artifact only; never a submitted TIF)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
EVID = ROOT / "evidence"
RASTERS = ROOT / "registry" / "rasters"
PIXEL_M = 100.0
R_M = 300.0
K_PX = R_M / PIXEL_M          # 3 px
CAT_FLANK = 3                 # px
LIVE = [  # owner-reported ladder; every path verified to be a distinct raster in this repo
    ("H33-2-B2 champion", 0.2778, "registry/rasters/dotted_b2_prune_02778.tif"),   # 37,654 px
    ("H27-4-R1-SOLO", 0.2708, "registry/rasters/dotted_d2_8_02708.tif"),            # 40,199 px
    ("TIP-STEPOVER-R30", 0.2632, "registry/rasters/tip_stepover_r30_02632.tif"),    # 41,865 px
    ("D2.8", 0.2600, "registry/rasters/dotted_d2_8_02600.tif"),                     # 44,090 px
    ("Hedge-v2", 0.1563, "registry/rasters/hedge_v2_01563.tif"),                    # 227,507 px
    ("LATTICE-S5", 0.0904, "registry/rasters/r13_lattice_s5_00904.tif"),            # 206,895 px
]
# dropped: H19-5 (live 0.1922, 121,131 dots) -- no raster for it exists in registry/rasters/


def read(band: Path, idx: int = 1) -> np.ndarray:
    with rasterio.open(band) as ds:
        a = ds.read(idx)
    return a


def main() -> int:
    foot = np.isfinite(read(ROOT / "data/bridge/example_submission.tif"))
    cat = read(WORK / "labels.tif") > 0
    sgmc = read(WORK / "sgmc100.tif") > 0
    d_cat = ndimage.distance_transform_edt(~cat)
    d_sgmc = ndimage.distance_transform_edt(~sgmc)

    scarp_path = Path("/tmp/gemsdoe48/GEMSDOE48-main/data/external/h52_scarp3m_100m.tif")
    if scarp_path.exists():
        with rasterio.open(scarp_path) as ds:
            g12 = ds.read(2).astype(np.float32)
            valid = ds.read(1) != -32768
        scarp_w = np.clip((g12 - 100.0) / 230.0, 0.0, 1.0)
        scarp_w[~valid] = 0.0
    else:                                     # keep the screen runnable without the LiDAR mirror
        scarp_w = np.zeros_like(foot, np.float32)
    w_off = np.where(foot & (d_cat > CAT_FLANK) & (d_sgmc > CAT_FLANK), scarp_w, 0.0)
    w_known = np.where(foot & (d_cat <= CAT_FLANK), scarp_w, 0.0)

    off = sgmc & foot & ~ndimage.binary_dilation(cat, iterations=CAT_FLANK)
    n_off = int(off.sum())
    ed_off = ndimage.distance_transform_edt(~off, sampling=PIXEL_M)
    k_off = np.maximum(1.0 - ed_off / R_M, 0.0)
    k_off_mean = float(k_off[foot].mean())

    foot_mean_k = float(k_off[foot].mean())          # random baseline kernel weight

    def screen(pred: np.ndarray) -> dict:
        n = int(pred.sum())
        tp = float(k_off[pred].sum())
        cov = tp / n_off
        # MASS-NORMALISED quality: mean kernel weight at the dots / the footprint mean.  Unlike the
        # raw excess this does not reward small mass, so it is the screen to compare at equal mass.
        quality_ratio = (cov * n_off / n) / foot_mean_k if n else 0.0
        wgot = float(w_off[pred].sum())
        wexp = float(w_off[foot & (d_cat > CAT_FLANK)].mean()) * n
        kgot = float(w_known[pred].sum())
        kexp = float(w_known[foot & (d_cat <= CAT_FLANK)].mean()) * n
        return dict(mass=n, tp_w=round(tp, 3), coverage=round(cov, 6),
                    sgmc_offcat_quality_ratio=round(quality_ratio, 4),
                    expected_coverage_if_random=round(k_off_mean * n / n_off, 6),
                    offcat_excess_vs_random=round(cov - k_off_mean * n / n_off, 6),
                    scarp_offcat_enrichment=round(wgot / wexp, 4) if wexp > 0 else None,
                    scarp_known_fault_enrichment=round(kgot / kexp, 4) if kexp > 0 else None,
                    med_dist_to_catalogue_px=float(np.median(d_cat[pred])))

    live_screen = {}
    for name, dti, rel in LIVE:
        p = ROOT / rel
        if not p.exists():
            continue
        m = read(p) > 0
        row = screen(m)
        row["reported_live_dti"] = dti
        live_screen[name] = row

    cand_path = WORK / "xcrd_dots.npy"
    cand = np.load(cand_path) > 0
    cand_row = screen(cand)

    ratio = {n: r["sgmc_offcat_quality_ratio"] for n, r in live_screen.items()}
    # local slope fitted only on the four disciplined low-mass points (the two 200k+ mass arms are
    # a different regime: their ratios sit at ~1.0, i.e. indistinguishable from random)
    low = {n: r for n, r in live_screen.items() if r["mass"] <= 60_000}
    xs_low = np.array([r["sgmc_offcat_quality_ratio"] for r in low.values()], float)
    ys_low = np.array([r["reported_live_dti"] for r in low.values()], float)
    slope_low = float(np.polyfit(xs_low, ys_low, 1)[0][0] if False else np.polyfit(xs_low, ys_low, 1)[0])
    proj_low = float(np.polyval(np.polyfit(xs_low, ys_low, 1), cand_row["sgmc_offcat_quality_ratio"]))

    xs = np.array([r["offcat_excess_vs_random"] for r in live_screen.values()], float)
    ys = np.array([r["reported_live_dti"] for r in live_screen.values()], float)
    fit = np.polyfit(xs, ys, 1)
    rho, pval = spearmanr(xs, ys)
    proj = float(np.polyval(fit, cand_row["offcat_excess_vs_random"]))

    # ---- uniqueness gates (brief): |Spearman| <= 0.90 and <= 70 % of dots within 3 px of one raster
    sub = slice(None, None, 7)
    cpix = np.argwhere(cand)
    uniq = {"n_registry_rasters": 0, "max_abs_spearman": 0.0, "worst_peer": None,
            "max_within_3px_excess": -9.9, "worst_peer_3px": None}
    for rp in sorted(RASTERS.glob("*.tif")):
        try:
            other = read(rp) > 0
        except Exception:
            continue
        if other.shape != cand.shape or other.sum() == 0:
            continue
        uniq["n_registry_rasters"] += 1
        rho_o = spearmanr(cand[sub, sub].ravel(), other[sub, sub].ravel()).statistic
        if abs(rho_o) > abs(uniq["max_abs_spearman"]):
            uniq["max_abs_spearman"] = float(rho_o)
            uniq["worst_peer"] = rp.name
        ed = ndimage.distance_transform_edt(~other)
        frac = float(np.mean(ed[cpix[:, 0], cpix[:, 1]] <= K_PX))
        rng = np.random.default_rng(7)
        fy, fx = np.nonzero(foot)
        pick = rng.integers(0, fy.size, size=cpix.shape[0])
        exp = float(np.mean(ed[fy[pick], fx[pick]] <= K_PX))
        if frac - exp > uniq["max_within_3px_excess"]:
            uniq["max_within_3px_excess"] = frac - exp
            uniq["worst_peer_3px"] = rp.name
            uniq["worst_peer_3px_frac"] = round(frac, 5)
            uniq["worst_peer_3px_random"] = round(exp, 5)
    uniq["pass_spearman_gate"] = abs(uniq["max_abs_spearman"]) <= 0.90
    uniq["pass_within_3px_gate"] = uniq["max_within_3px_excess"] <= 0.0

    verdict = dict(
        e1_screen_live=live_screen,
        e1_fit_live_vs_excess=dict(slope=float(fit[0]), intercept=float(fit[1]),
                                   spearman=float(rho), spearman_p=float(pval), n=len(xs)),
        quality_ratio_ladder=ratio,
        quality_ratio_spearman=float(spearmanr(list(ratio.values()),
                                               [r["reported_live_dti"] for r in live_screen.values()]).statistic),
        quality_ratio_slope_low_mass_arms=round(slope_low, 4),
        candidate_projection_from_quality_ratio=round(proj_low, 4),
        candidate=cand_row,
        candidate_projected_live_dti_from_screen=round(proj, 4),
        projection_warning=("projection from the E1 screen, NOT an organizer score; "
                            "only ORGANIZER-CONFIRMED numbers are scores"),
        scarp_control_note=("enrichment <1 means the emission hits that scarp family less often "
                            "than random allowed pixels; compare against the live artifacts' rows"),
        uniqueness=uniq,
    )
    EVID.mkdir(exist_ok=True)
    (EVID / "e2b_xcrd_screen.json").write_text(json.dumps(verdict, indent=2, default=str))
    print(json.dumps(verdict, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
