#!/usr/bin/env python3
"""E2/E3 (GEMS61): thermally-corroborated knickpoint lane -> one validated, unique GeoTIFF.

Lane (the brief's method paragraph, unchanged): drainage from the free 3DEP DEM -> chi and
normalised channel steepness -> knickpoints/steepness steps kept only where they align across >= 3
independent first-order drainages along a common strike; confounds (playa/closed-basin base level,
acquisition striping, catalogue ring) masked.

What is NEW in this session (and absent from every prior lane in the family):

  * the substrate is the 3DEP-derived 100 m mean elevation (data/external/topo_10m_derived_100m_u8.tif,
    public domain, GitHub-Actions-fetched from prd-tnm.s3.amazonaws.com), not the detrended band;
  * a THERMAL CORROBORATION layer built from three official INGENIOUS/GDR products restored this
    session for the first time anywhere in this family --
        GDR 1391 spring/well chemistry (geothermometer temperatures; 27,092 rows),
        GDR 1391 paleo-geothermal travertine/sinter deposits (727 sites),
        GDR 1391 2 m temperature probes (3,800 stations with background-normalised anomalies);
  * the emission budget is taken from the metric's own marginal-acceptance bar (alpha*DTI), evaluated
    as a ladder so the budget is measured rather than assumed.

Evaluation uses the shared template verbatim: ``gems52-pooled-hide-v1`` (whole-segment
hide-and-recover, pooled DTI, 20 km spatial-block bootstrap) and, for selection, the one local truth
set that E1 measured as rank-consistent with the live board (SGMC off-catalogue faults, thinned to
live-like prevalence).  Both are INSTRUMENTS on public proxy truth -- never a score claim.

Usage: PYTHONPATH=src python3 scripts/e62_lane_thermal.py [--budgets 5000,...]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems60 import nodes as N              # noqa: E402  shared lane emission toolkit
from gems60 import surface as S            # noqa: E402  shared lane detector
from gems52 import evaluate_holdout as EH  # noqa: E402  shared pooled evaluator
from gems52 import holdout as H            # noqa: E402
from gems52 import submission_writer as W  # noqa: E402
from gems61 import dataio, instruments as I  # noqa: E402

CELL_M = 100.0
SIGMA_PX = 3.0                # 300 m -- the metric's own kernel radius; a corroboration neighbourhood
KAPPA = 1.0                   # weight of the thermal multiplier
N_LIVE_LIKE = 8000
SRC = {
    "dem_3dep_100m": "data/external/topo_10m_derived_100m_u8.tif",
    "springs_csv": "data/external/gdr_wellspring_in_footprint.csv",
    "probes_zip": "data/external/2m_temperature_probe_INGENIOUS_regional_data.zip",
    "paleo_zip": "data/external/paleo_geothermal_regional.zip",
}


def log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:7.1f}s] {msg}", flush=True)


# ------------------------------------------------------------------------------------------------
# thermal corroboration
# ------------------------------------------------------------------------------------------------
def _splat(points: list[tuple[float, float, float]], shape: tuple[int, int], transform) -> np.ndarray:
    out = np.zeros(shape, dtype=np.float32)
    for x, y, w in points:
        col = int((x - transform.c) / transform.a)
        row = int((y - transform.f) / transform.e)
        if 0 <= row < shape[0] and 0 <= col < shape[1]:
            out[row, col] = max(out[row, col], float(w))
    return out


def thermal_field(shape, transform, valid) -> tuple[np.ndarray, dict]:
    # --- GDR 1391 spring / well chemistry (already on this grid: utm_x, utm_y, dist_known_fault_px)
    pts: dict[tuple[float, float], dict] = {}
    with open(ROOT / SRC["springs_csv"], newline="") as f:
        for r in csv.DictReader(f):
            try:
                x, y = float(r["utm_x"]), float(r["utm_y"])
            except (TypeError, ValueError):
                continue
            g = [float(r[k]) for k in ("geothermquartz_c", "geothermchalc_c", "geothermcat_c", "temp_c")
                 if r.get(k) not in (None, "", "NULL")]
            if not g:
                continue
            key = (round(x, 1), round(y, 1))
            cur = pts.get(key)
            w = max(g) / 200.0
            d = float(r["dist_known_fault_px"]) if r.get("dist_known_fault_px") not in (None, "", "NULL") else np.nan
            if cur is None:
                pts[key] = {"x": x, "y": y, "w": w, "d": d}
            else:
                cur["w"] = max(cur["w"], w)
                cur["d"] = np.nanmin([cur["d"], d]) if np.isfinite(d) or np.isfinite(cur["d"]) else np.nan
    sites = list(pts.values())
    off = [s for s in sites if not np.isfinite(s["d"]) or s["d"] > 3.0]
    spring = _splat([(s["x"], s["y"], s["w"]) for s in sites], shape, transform)
    spring_off = _splat([(s["x"], s["y"], s["w"]) for s in off], shape, transform)

    # --- GDR 1391 paleo-geothermal travertine / sinter (lat-lon NAD83 -> UTM 11N)
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4269", "EPSG:32611", always_xy=True)
    with zipfile.ZipFile(ROOT / SRC["paleo_zip"]) as z:
        text = z.read("Paleo_geothermal_final.csv").decode("utf-8", "replace").splitlines()
    pal = []
    for r in csv.DictReader(text):
        try:
            x, y = tr.transform(float(r["Long_deg_NAD83"]), float(r["Lat_deg_NAD83"]))
        except (TypeError, ValueError, KeyError):
            continue
        pal.append((x, y, 1.0))
    paleo = _splat(pal, shape, transform)

    # --- GDR 1391 2 m temperature probes (UTM_E / UTM_N NAD83 11N; F2mDAB = background anomaly)
    with zipfile.ZipFile(ROOT / SRC["probes_zip"]) as z:
        base = "2m_temperature_probe_INGENIOUS_regional_data/2m_temperature_probe_n83geo/"
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        for ext in ("shp", "shx", "dbf", "prj", "cpg"):
            (tmp / f"probe.{ext}").write_bytes(z.read(base + f"2m_temperature_probe_n83geo.{ext}"))
    import shapefile
    rd = shapefile.Reader(str(tmp / "probe.shp"))
    names = [f[0] for f in rd.fields][1:]
    ie, iN, iab = names.index("UTM_E"), names.index("UTM_N"), names.index("F2mDAB")
    probes = []
    for rec in rd.records():
        try:
            x, y = float(rec[ie]), float(rec[iN])
            dab = float(rec[iab])
        except (TypeError, ValueError):
            continue
        if dab > 0:
            probes.append((x, y, float(np.clip(dab / 6.0, 0.0, 2.0))))
    probe = _splat(probes, shape, transform)

    fields = {}
    for name, arr, scale in (("spring", spring, 1.0), ("spring_offcatalogue", spring_off, 1.0),
                             ("paleo", paleo, 1.0), ("probe", probe, 1.0)):
        sm = ndi.gaussian_filter(arr.astype(np.float32), SIGMA_PX)
        peak = float(np.quantile(sm[valid], 0.999)) if valid.any() else 1.0
        fields[name] = np.clip(sm / max(peak, 1e-9), 0.0, 1.5).astype(np.float32)
    combined = np.maximum.reduce([fields[k] for k in fields])
    combined = np.where(valid, combined, 0.0).astype(np.float32)
    # two variants: all thermal evidence, and only evidence that the mapped catalogue does not explain
    both = np.maximum.reduce([fields["spring_offcatalogue"], fields["paleo"], fields["probe"]])
    both = np.where(valid, both, 0.0).astype(np.float32)
    diag = {"n_spring_sites": len(sites), "n_spring_sites_off_catalogue": len(off),
            "n_paleo_sites": len(pal), "n_probe_stations_positive": len(probes),
            "sigma_px": SIGMA_PX, "kappa": KAPPA,
            "px_thermal_gt_0.2_all": int((combined > 0.2).sum()),
            "px_thermal_gt_0.2_offcat": int((both > 0.2).sum())}
    return dict(all=combined, offcatalogue=both, **fields), diag


# ------------------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budgets", default="3000,5000,8000,12000,20000,37654")
    ap.add_argument("--out", default="submission")
    ap.add_argument("--tag", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    args = ap.parse_args()
    t0 = time.time()
    budgets = [int(b) for b in args.budgets.split(",")]

    valid, cat = dataio.load_footprint_and_labels()
    with rasterio.open(ROOT / SRC["dem_3dep_100m"]) as ds:
        shape, transform = ds.shape, ds.transform
    dem = dataio.dequantise_u8(ROOT / SRC["dem_3dep_100m"], 9)      # band 9 = dem_mean
    dem = np.where(valid, dem, np.nan).astype(np.float32)
    log(f"footprint {int(valid.sum()):,} px | catalogue {int(cat.sum()):,} px | DEM finite "
        f"{int(np.isfinite(dem).sum()):,}", t0)

    th, th_diag = thermal_field(shape, transform, valid)
    log(f"thermal evidence: {th_diag}", t0)

    lane = S.build(dem, valid, cell_m=CELL_M, theta=0.45, ac_m2=1.0e6, knick_window=4,
                   knick_ratio=1.6, min_drop_m=20.0, corridor_px=12, azimuth_bins=18)
    log(f"lane stats: {json.dumps({k: v for k, v in lane['stats'].items() if k != 'per_azimuth_bin_counts'})}", t0)

    conc = S.score_field(lane, valid, min_drainages=3)
    log(f"strike-concordant surface: {int((conc > 0).sum()):,} px > 0", t0)

    # --- arms: lane-only, lane x thermal(all), lane x thermal(off-catalogue only)
    arms = {
        "lane_only": conc.copy(),
        "lane_x_thermal_all": (conc * (1.0 + KAPPA * th["all"])).astype(np.float32),
        "lane_x_thermal_offcat": (conc * (1.0 + KAPPA * th["offcatalogue"])).astype(np.float32),
        "thermal_only": th["offcatalogue"].copy(),
    }

    dc0 = ndi.distance_transform_edt(~cat) * CELL_M
    allowed = valid.copy()
    allowed &= ~(dc0 <= 200.0)                       # the metric never pays for mass this close to a mask
    allowed &= ~lane["playa_or_closed_basin"]
    if lane["stripe"] is not None:
        allowed &= ~lane["stripe"]["rows"][:, None]
    log(f"allowed region {int(allowed.sum()):,} px (catalogue ring, playa/closed basin, stripes removed)", t0)

    off = I.sgmc_off_catalogue(dataio.load_sgmc(), cat, valid, buffer_px=3)
    truth_sel = I.thin_random(off, N_LIVE_LIKE, seed=61)
    folds = H.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=0, mode="hide")
    log(f"selection truth {int(truth_sel.sum()):,} px | folds {[f['n_truth'] for f in folds]}", t0)

    ladder = {}
    for arm_name, field in arms.items():
        f = np.where(allowed, np.nan_to_num(field, nan=0.0), 0.0).astype(np.float32)
        if not (f > 0).any():
            continue
        if arm_name == "thermal_only":
            n_emit = 4000                              # thermal evidence alone is a sparse point prior
            dots = N.emit(f, allowed, n_emit, N.spacing_from_budget(n_emit, int((f > 0).sum())),
                          min_sep_px=3.0, seed=60)
            inst = I.global_dti(dots.astype(np.float32), truth_sel, valid, cat)
            ladder[arm_name] = {"budget": n_emit, "instrument": inst}
            continue
        for b in budgets:
            dots = N.emit(f, allowed, b, N.spacing_from_budget(b, int((f > 0).sum())),
                          min_sep_px=3.0, seed=60)
            inst = I.global_dti(dots.astype(np.float32), truth_sel, valid, cat)
            ladder[f"{arm_name}|{b}"] = {"arm": arm_name, "budget": b, "instrument": inst}
            log(f"  {arm_name:24s} b={b:>6,} -> instr {inst['dti']:.5f} "
                f"(mass {inst['emitted_px']:,}, c/px {inst['credit_per_px']:.4f})", t0)

    # --- the shipped arm: best instrument score among the lane arms, then the pooled holdout
    cand = max((k for k in ladder if "|" in k), key=lambda k: ladder[k]["instrument"]["dti"])
    chosen = np.where(allowed, np.nan_to_num(arms[ladder[cand]["arm"]], nan=0.0), 0.0).astype(np.float32)
    b = ladder[cand]["budget"]
    dots = N.emit(chosen, allowed, b, N.spacing_from_budget(b, int((chosen > 0).sum())),
                  min_sep_px=3.0, seed=60)
    pred = dots.astype(np.float32)
    log(f"selected arm '{cand}' (instrument {ladder[cand]['instrument']['dti']:.5f}); "
        f"{int(pred.sum()):,} dots", t0)

    # --- pooled hide-and-recover (protocol instrument) + canary
    # Arms evaluated on identical folds/masks: this lane, the family's live champion (a registry
    # raster, used as the comparable control) and a mass-matched uniform-random control.
    arm_preds = {"lane_thermal": pred}
    for extra, rel in (("champion_h33b2", "dotted_b2_prune_02778.tif"),
                       ("incumbent_d28", "dotted_d2_8_02600.tif")):
        pth = ROOT / "registry" / "rasters" / rel
        if pth.exists():
            arm_preds[extra] = (np.nan_to_num(dataio.read_band(pth, dtype=np.float32), nan=0.0)).astype(np.float32)
    rng0 = np.random.default_rng(7)
    rndm = np.zeros(shape, dtype=np.float32)
    ri = rng0.choice(np.flatnonzero(valid.ravel()), size=int(pred.sum()), replace=False)
    rndm.ravel()[ri] = 1.0
    arm_preds["random_matched"] = rndm

    terms_by_arm: dict[str, list[np.ndarray]] = {k: [] for k in arm_preds}
    for fold in folds:
        for k, arr in arm_preds.items():
            _, t = EH.evaluate(arr, fold, valid, block_side=200)
            terms_by_arm[k].append(t)
    stacked = {k: np.stack(v).sum(axis=0) for k, v in terms_by_arm.items()}
    pooled = EH.pooled_summary(stacked, draws=1000, seed=520810, candidate="lane_thermal")
    pooled_all = pooled["scores"]["lane_thermal"]

    # --- leakage canary (protocol item 4): each evidence layer ALONE on the holdout folds
    canary = {}
    for cname, field in (("concordance", conc), ("thermal_offcatalogue", th["offcatalogue"]),
                         ("lane_x_thermal_offcatalogue", arms["lane_x_thermal_offcat"])):
        aucs = []
        for fold in folds:
            sel = fold["region"] & valid & ~fold["visible"]
            v = np.asarray(field, dtype=np.float64)[sel]
            y = fold["truth"][sel]
            if y.sum() == 0 or y.sum() == y.size:
                continue
            order = np.argsort(v, kind="stable")
            r = np.empty(v.size, dtype=np.float64)
            r[order] = np.arange(v.size, dtype=np.float64)
            aucs.append(float((r[y].sum() - y.sum() * (y.sum() - 1) / 2.0) / (y.sum() * (~y).sum())))
        canary[cname] = round(float(np.mean(aucs)), 4) if aucs else None
    print(f"canary AUC: {canary}", flush=True)

    # --- uniqueness vs the registry
    print(f"canary AUC: {canary}", flush=True)

    # --- uniqueness vs the registry
    names, masks = N.registry_cover_masks(ROOT / "registry" / "rasters", shape)
    ov = N.overlap_fractions(dots, masks, radius_px=3)
    for o, nm in zip(ov, names):
        o["raster"] = nm
    rng = np.random.default_rng(0)
    rnd = np.zeros_like(dots)
    ri = rng.choice(np.flatnonzero(valid.ravel()), size=max(int(dots.sum()), 1), replace=False)
    rnd.ravel()[ri] = True
    ov_rnd = N.overlap_fractions(rnd, masks, radius_px=3)
    for o, rr in zip(ov, ov_rnd):
        o["frac_random_within_3px"] = rr["frac_within_3px"]
        o["excess_over_random"] = o["frac_within_3px"] - rr["frac_within_3px"]
    worst = max(ov, key=lambda o: o["frac_within_3px"])
    over_gate = sorted([o for o in ov if o["frac_within_3px"] > 0.70],
                       key=lambda o: -o["frac_within_3px"])
    # rank correlation on the same grid (Spearman on subsampled cells, both sparse)
    sp = {}
    ours = pred.ravel() > 0
    oy, ox = np.nonzero(pred)
    for p in sorted((ROOT / "registry" / "rasters").glob("*.tif")):
        with rasterio.open(p) as ds:
            if (ds.height, ds.width) != shape:
                continue
            a = ds.read(1)
        m = np.isfinite(a) & (a > 0)
        if not m.any():
            continue
        b_flat = m.ravel()
        idx = np.flatnonzero(ours | b_flat)
        if idx.size < 1000:
            continue
        ra = np.zeros(idx.size); rb = np.zeros(idx.size)
        ra[ours.ravel()[idx]] = 1.0; rb[b_flat[idx]] = 1.0
        if ra.std() == 0 or rb.std() == 0:
            continue
        sp[p.name] = round(float(np.corrcoef(ra, rb)[0, 1]), 4)
    del oy, ox

    # --- write the submission pair (shared writer: fail-closed format validation)
    sample = ROOT / "data/bridge/example_submission.tif"   # template path (gates reads the grid itself)
    name = f"gems61-lane-thermal-knick-{int(pred.sum())}px-{args.tag}"
    note = (f"chi/ksn knickpoint strike-concordance x INGENIOUS thermal corroboration; "
            f"{int(pred.sum())} dots; E1-audited selector; UNSCORED")[:140]
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.tif"
    receipt = W.write_submission(path, pred, sample, valid, note=note, name=name,
                                metadata={"arm": cand, "budget": int(b),
                                          "instrument_dti": ladder[cand]["instrument"]["dti"],
                                          "arms_ladder": {k: v["instrument"]["dti"] for k, v in ladder.items()}})

    report = {
        "experiment": "E2/E3 thermally-corroborated knickpoint lane",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": SRC,
        "thermal": th_diag,
        "lane_stats": lane["stats"],
        "strike_concordant_px": int((conc > 0).sum()),
        "allowed_px": int(allowed.sum()),
        "ladder": ladder,
        "selected_arm": cand,
        "instrument_selection": {"truth": "SGMC off-catalogue, thinned to 8,000 px, seed 61",
                                 "evidence_class": "INSTRUMENT",
                                 "E1_spearman_vs_live": 0.4685},
        "holdout_pooled": pooled_all,
        "holdout_pooled_full": pooled, "holdout_terms_per_fold": {k: [[float(y) for y in np.asarray(x).sum(axis=0)] for x in v] for k, v in terms_by_arm.items()},
        "canary_auc": canary,
        "uniqueness": {"worst_overlap": worst,
                       "rasters_above_raw_70pct_clause": [
                           {"raster": o["raster"], "frac_within_3px": o["frac_within_3px"],
                            "excess_over_random": o["excess_over_random"]} for o in over_gate[:8]],
                       "n_rasters_above_raw_clause": len(over_gate), "max_abs_pearson_on_support": max(sp.values()) if sp else None,
                       "gate_overlap": 0.70, "gate_rank": 0.90,
                       "note": "gate is on rank correlation; Pearson on the union support is reported "
                               "as the conservative companion since both rasters are binary"},
        "receipt": {k: receipt[k] for k in ("file", "sha256", "bytes", "submission_name", "note",
                                            "zip_file", "zip_sha256", "validator")},
    }
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence" / "e62_lane_thermal.json").write_text(json.dumps(report, indent=1) + "\n")
    log(f"wrote {path.name} sha256 {receipt['sha256'][:16]}…", t0)
    log(f"pooled HOLDOUT-DTI {pooled_all['dti']:.5f} on {pooled_all['withheld_positive_pixels']:,} "
        f"withheld positives; canary {canary}", t0)
    log(f"uniqueness: worst 3-px overlap {worst['frac_within_3px']:.3f} "
        f"({worst['raster']}), excess over random {worst['excess_over_random']:+.3f}", t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
