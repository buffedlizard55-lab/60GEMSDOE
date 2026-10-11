#!/usr/bin/env python3
"""Uniqueness comparison for the H80 round, on the shared tool (scripts/build_h71_field.py).

Three questions, all on grid-matched 100 m rasters at the protocol's 3-px radius:

  1. the emitted union (49,654 dots) -> the clause's readings (literal / decidable / one-to-one),
     over the full comparison set including downloads/ and submission/ (IR-H80-TOOL-02);
  2. the live-scored champion (37,654 dots) -> the incumbent control: does the clause fail the
     artifact the project already submitted and scored?
  3. the complement alone (12,000 dots) -> the only NEW information in the union.

Writes evidence/h80_artifact_comparison.json. No number is typed by hand.

Run:  python scripts/h80_compare.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import build_h71_field as BH  # noqa: E402

DL = ROOT / "docs" / "downloads"
UNION = DL / "gems60-h80-convcomp-49654-20261011T202055Z-zeros.tif"
CHAMPION = DL / "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
EXTRA = (ROOT / "downloads", ROOT / "submission", ROOT / "evidence")


def load(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
    a[~np.isfinite(a)] = 0.0
    return a > 0


def one_to_one(mine: np.ndarray, theirs: np.ndarray, radius: float = 3.0) -> dict:
    """Greedy one-to-one matching: each comparator dot absorbs at most one of mine."""
    my = np.column_stack(np.nonzero(mine)).astype(np.float64)
    th = np.column_stack(np.nonzero(theirs)).astype(np.float64)
    if my.size == 0 or th.size == 0:
        return {"matched": 0, "of_mine": int(my.shape[0]), "fraction": 0.0, "theirs": int(th.shape[0])}
    tree = cKDTree(th)
    dist, idx = tree.query(my, k=1, distance_upper_bound=radius)
    ok = np.isfinite(dist)
    used: set[int] = set()
    for i in np.flatnonzero(ok)[np.argsort(dist[ok])]:
        used.add(int(idx[i]))
    return {"matched": len(used), "of_mine": int(my.shape[0]),
            "fraction": round(len(used) / my.shape[0], 6), "theirs": int(th.shape[0])}


def main() -> None:
    with rasterio.open(ROOT / "data/official/sample_submission.tif") as src:
        fp = np.isfinite(src.read(1))
    out: dict = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "evidence_class": "MEASUREMENT",
                 "tool": "scripts/build_h71_field.py::uniqueness_scan + greedy cKDTree one-to-one",
                 "radius_px": 3.0, "grain_px": 100.0,
                 "scope": "registry/rasters + docs/downloads + downloads + submission + evidence (grid-matched)"}

    champion = load(CHAMPION)
    union = load(UNION)
    complement = union & ~champion
    masks = {"union_49654": union, "champion_37654": champion, "complement_12000": complement}

    for name, mask in masks.items():
        t0 = time.time()
        scan = BH.uniqueness_scan(mask, fp, (UNION.name, CHAMPION.name), extra_dirs=EXTRA)
        o2o = {}
        for rel in ("registry/rasters/calib_r13lattice_00904.tif", "registry/rasters/r11_greedy_mp.tif",
                    "registry/rasters/r14_union_tips10_lat6.tif",
                    "docs/downloads/gems60-h72-union-champ-convcomp-43654-20261011T191739Z-zeros.tif"):
            p = ROOT / rel
            if p.is_file():
                o2o[Path(rel).name] = one_to_one(mask, load(p))
        out[name] = {
            "dots": int(mask.sum()),
            "literal": scan["literal"],
            "like_for_like": scan["like_for_like"],
            "satisfiable": scan["satisfiable"],
            "universal_blockers": scan["universal_blockers"],
            "scanned": scan["scanned"],
            "seconds": round(time.time() - t0, 1),
            "top_rows": scan["top_rows"][:6],
            "one_to_one": o2o,
        }
        print(f"[cmp] {name}: dots={int(mask.sum()):,} literal={scan['literal']['max_dot_overlap_within_3px']:.4f} "
              f"decidable={scan['satisfiable']['max_dot_overlap_within_3px']:.4f} "
              f"({scan['satisfiable']['worst_raster']}) rho_max={scan['literal']['max_abs_spearman']:.4f} "
              f"({time.time() - t0:.0f}s)", flush=True)

    (ROOT / "evidence/h80_artifact_comparison.json").write_text(
        json.dumps(out, indent=1, default=float) + "\n")
    print("wrote evidence/h80_artifact_comparison.json")


if __name__ == "__main__":
    main()
