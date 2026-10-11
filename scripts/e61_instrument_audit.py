#!/usr/bin/env python3
"""E1 (session GEMS61): can any local truth set rank the family's own live scores?

Motivation (previous session's remaining work #1): every lane in this family is judged on a local
proxy, and the one measurement that exists says the family's instruments rank live scores at roughly
chance (pooled hide-and-recover gives the 0.2778 champion 0.0041 while giving the 0.2600 dotted file
0.0862 -- a rank inversion).  A selector that cannot rank is the binding constraint on winning: no
field idea can be trusted, and submission slots can only be spent blindly.

This experiment measures that directly.  Thirteen artifacts whose live scores are known (owner
reports, docs/score-ledger.csv) are scored against five local truth sets, and each instrument's
Spearman rank correlation with the live score is reported.  Nothing here is a score claim about the
hidden label set; the truth sets are public proxies and every number is labelled INSTRUMENT.

Usage:  PYTHONPATH=src python3 scripts/e61_instrument_audit.py [--pooled]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import dataio, instruments as I          # noqa: E402
from gems52 import evaluate_holdout as EH            # noqa: E402
from gems52 import holdout as H                      # noqa: E402

TERRAIN_BAND = 5          # relief_local, from data/external/topo_10m_derived_100m_u8.manifest.json
N_LIVE_LIKE = 8000        # |G| bracket centre implied by the family's own live-anchor inversion


def read_pred(path: Path) -> np.ndarray:
    p = dataio.read_band(path, dtype=np.float32)
    return np.nan_to_num(p, nan=0.0, posinf=0.0, neginf=0.0)


def main() -> int:
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "E61 instrument audit"):
        return 0
    ap = argparse.ArgumentParser()
    ap.add_argument("--pooled", action="store_true", help="also run gems52-pooled-hide-v1 (~2 min)")
    ap.add_argument("--out", default="evidence/e61_instrument_audit.json")
    args = ap.parse_args()
    t0 = time.time()

    valid, cat = dataio.load_footprint_and_labels()
    sgmc = dataio.load_sgmc()
    terrain = dataio.dequantise_u8(ROOT / "data/external/topo_10m_derived_100m_u8.tif", TERRAIN_BAND)
    print(f"footprint {valid.sum():,} px | catalogue {cat.sum():,} px | SGMC {sgmc.sum():,} px",
          flush=True)

    off = I.sgmc_off_catalogue(sgmc, cat, valid, buffer_px=3)
    print(f"SGMC off-catalogue (>300 m) {off.sum():,} px", flush=True)
    off8 = I.thin_random(off, N_LIVE_LIKE, seed=61)
    bal8, diag8 = I.terrain_balanced_truth(off, valid, terrain, N_LIVE_LIKE, seed=61)
    bal30, diag30 = I.terrain_balanced_truth(off, valid, terrain, 30000, seed=61)
    cat8 = I.thin_random(I.catalogue_truth(cat, valid), N_LIVE_LIKE, seed=61)
    print(f"balanced truth counts: {bal8.sum():,} / {bal30.sum():,}", flush=True)

    fin = np.isfinite(terrain) & valid
    qs = np.quantile(terrain[fin], np.linspace(0, 1, 6)[1:-1])
    strata = np.where(fin, np.digitize(terrain, qs), -1)
    fp_share = {s: float(((strata == s) & valid).sum()) / float(valid.sum()) for s in range(5)}
    truth_by_stratum = {s: (bal8 & (strata == s)) for s in range(5)}

    truths = {
        "catalogue_full": I.catalogue_truth(cat, valid),
        "catalogue_thin8000": cat8,
        "sgmc_off_full": off,
        "sgmc_off_thin8000": off8,
        "sgmc_off_balanced8000": bal8,
        "sgmc_off_balanced30000": bal30,
    }
    for k, v in truths.items():
        print(f"  truth {k:24s} {int(v.sum()):>7,} px", flush=True)

    files = dataio.load_calibration()
    seen = {}
    for f in files:                       # one artifact per distinct live score level
        seen.setdefault(round(f["live_score"], 4), f)
    files = sorted(seen.values(), key=lambda f: -f["live_score"])
    print(f"calibration artifacts (one per live level): {len(files)}", flush=True)

    rows = []
    for f in files:
        p = read_pred(f["abspath"])
        rec = {"file": f["abspath"].name, "live_score": f["live_score"], "label": f["label"],
               "sha256": f["sha256"], "emitted_px": int((p > 0).sum()),
               "mass_on_catalogue_px": int(((p > 0) & cat).sum())}
        for name, t in truths.items():
            rec[name] = I.global_dti(p, t, valid, cat)
        rows.append(rec)
        print(f"  {f['live_score']:.4f}  {f['abspath'].name[:44]:44s} "
              f"mass={rec['emitted_px']:>7,}  cat={rec['mass_on_catalogue_px']:>5,}  "
              f"sgmc_off={rec['sgmc_off_full']['dti']:.4f}  bal8={rec['sgmc_off_balanced8000']['dti']:.4f}",
              flush=True)
        del p

    live = [r["live_score"] for r in rows]
    report = {
        "experiment": "E1 instrument selection audit",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": "INSTRUMENT (public proxy truth; not the hidden label set)",
        "question": ("does any local truth set rank the family's live-scored artifacts in the same "
                     "order as the competition's public leaderboard?"),
        "n_artifacts": len(rows),
        "live_score_class": "OWNER-REPORT / OFFICIAL-SNAPSHOT from docs/score-ledger.csv",
        "organizer_mask": ("predicted mass on USGS/INGENIOUS fault pixels is deleted before scoring "
                           "(DrivenData staff, community thread 11516 post #2)"),
        "truth_sets": {k: int(v.sum()) for k, v in truths.items()},
        "terrain_strata": {"band": "relief_local",
                           "quantiles": [float(q) for q in qs],
                           "footprint_share": fp_share,
                           "balanced_diag_8000": diag8, "balanced_diag_30000": diag30},
        "rows": rows,
        "spearman_vs_live": {},
    }
    for name in truths:
        report["spearman_vs_live"][name] = round(
            I.spearman([r[name]["dti"] for r in rows], live), 4)
    report["spearman_vs_live"]["mass_only_negative"] = round(
        I.spearman([-r["emitted_px"] for r in rows], live), 4)
    report["spearman_vs_live"]["credit_per_px"] = round(
        I.spearman([r["sgmc_off_balanced8000"]["credit_per_px"] for r in rows], live), 4)

    # terrain-balanced instrument: footprint-area-weighted mean of per-stratum DTI vs balanced truth
    for r in rows:
        p = read_pred(ROOT / "registry/rasters" / Path(r["file"]).name)
        b = I.balanced_dti(p, truth_by_stratum, strata, valid, cat, fp_share)
        r["balanced_dti_vs_balanced8000"] = b
        del p
    report["spearman_vs_live"]["balanced_dti_vs_balanced8000"] = round(
        I.spearman([r["balanced_dti_vs_balanced8000"]["balanced_dti"] for r in rows], live), 4)

    if args.pooled:
        folds = H.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=0,
                             mode="hide")
        print(f"pooled folds: {[f['n_truth'] for f in folds]}", flush=True)
        pooled = {}
        for r in rows:
            p = read_pred(ROOT / "registry/rasters" / Path(r["file"]).name)
            terms = {}
            for fold in folds:
                res, t = EH.evaluate(p, fold, valid, block_side=200)
                terms[f"fold{fold['fold']}"] = t
                del res
            summary = EH.pooled_summary(terms, draws=1000, seed=520810,
                                        candidate="fold0" if False else
                                        next(iter(terms)))
            # candidate arg must name an existing arm: use the pooled point estimate over all folds
            tot = {k: v for k, v in terms.items()}
            arr = np.stack([tot[k] for k in tot]).sum(axis=0)
            pooled[r["file"]] = {"pooled_from_terms": float(EH.from_terms(arr)),
                                 "n_truth": int(arr[3])}
            r["pooled_hide_and_recover"] = pooled[r["file"]]
            print(f"  pooled {r['live_score']:.4f} {r['file'][:40]:40s} "
                  f"{pooled[r['file']]['pooled_from_terms']:.5f}", flush=True)
            del p, terms
        report["spearman_vs_live"]["pooled_hide_and_recover"] = round(
            I.spearman([r["pooled_hide_and_recover"]["pooled_from_terms"] for r in rows], live), 4)

    out = ROOT / args.out
    out.write_text(json.dumps(report, indent=1, allow_nan=False) + "\n")
    print("\n== Spearman(instrument, live score) ==", flush=True)
    for k, v in report["spearman_vs_live"].items():
        print(f"  {k:34s} {v:+.4f}")
    print(f"\nwrote {out}  ({time.time() - t0:.1f}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
