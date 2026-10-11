#!/usr/bin/env python3
"""Exact preplacement/final-dot uniqueness audit for H73 against the full registry.

Requires ``scripts/fetch_registry_rasters.py`` first. Four deleted-at-HEAD blobs
listed in the index can be recovered through GitHub's Git-blob API using their
recorded object IDs; the audit fails closed if any of the 655 pinned hashes is
missing. Later local TIFFs are added and de-duplicated by SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems57 import grid as G57  # noqa: E402

CACHE = ROOT / ".cache" / "registry"
INDEX = ROOT / "evidence" / "registry_full_index.json"
OUT = ROOT / "evidence" / "h73_preplacement_uniqueness.json"
TIF = ROOT / "docs" / "downloads" / "gems60-h73-paired-basin-ksn-20000-20261011T200117Z-zeros.tif"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corpus() -> tuple[list[dict], dict]:
    index = json.loads(INDEX.read_text())
    rows, missing = {}, []
    for rec in index["rasters"]:
        path = CACHE / f"{rec['sha256'][:16]}.tif"
        if not path.is_file() or digest(path) != rec["sha256"]:
            missing.append({"sha256": rec["sha256"], "sources": rec["sources"],
                            "blob": rec.get("blob"), "repo": rec.get("repo_first")})
            continue
        rows[rec["sha256"]] = {"path": path, "sha256": rec["sha256"],
                                "sources": rec["sources"], "scope": "full pinned sibling registry"}
    for folder in (ROOT / "registry" / "rasters", ROOT / "docs" / "downloads", ROOT / "downloads"):
        for path in folder.glob("*.tif"):
            if path.resolve() == TIF.resolve():
                continue
            sha = digest(path)
            if sha in rows:
                rows[sha]["sources"].append(str(path.relative_to(ROOT)))
            else:
                rows[sha] = {"path": path, "sha256": sha,
                             "sources": [str(path.relative_to(ROOT))],
                             "scope": "later local registry/artifact"}
    scope = {"pinned_index_rows": len(index["rasters"]),
             "pinned_fetched_and_sha_verified": len(index["rasters"]) - len(missing),
             "pinned_missing": missing, "unique_sha_after_later_local_additions": len(rows)}
    return list(rows.values()), scope


def spearman_exact(xrank: np.ndarray, values: np.ndarray) -> float:
    y = np.nan_to_num(values.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    unique = np.unique(y)
    if unique.size <= 1:
        return 0.0
    yrank = ((y == unique[1]).astype(np.float64) if unique.size == 2
             else rankdata(y, method="average").astype(np.float64, copy=False))
    xc, yc = xrank - xrank.mean(), yrank - yrank.mean()
    den = float(np.sqrt(np.dot(xc, xc) * np.dot(yc, yc)))
    return float(np.dot(xc, yc) / den) if den else 0.0


def main() -> int:
    started = time.time()
    grid = G57.load_grid()
    if TIF.is_file():
        with rasterio.open(TIF) as src:
            pred = src.read(1).astype(np.float32)
        candidate_file_sha = digest(TIF)
    else:
        pred = np.load(ROOT / ".cache" / "features73" / "production_prediction.npy").astype(np.float32)
        candidate_file_sha = None
    rows, scope = corpus()
    if scope["pinned_missing"]:
        raise SystemExit(f"registry incomplete: {scope['pinned_missing']}")
    fp, mine = grid.footprint, pred > 0
    xrank = rankdata(pred[fp].astype(np.float64), method="average")
    yy, xx = np.mgrid[-3:4, -3:4]
    structure = (yy * yy + xx * xx) <= 9
    results = []
    for i, rec in enumerate(rows):
        with rasterio.open(rec["path"]) as src:
            if src.shape != pred.shape:
                continue
            arr = np.nan_to_num(src.read(1).astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        dots = arr > 0
        near = ndi.binary_dilation(dots, structure=structure)
        results.append({"sha256": rec["sha256"], "sources": rec["sources"], "scope": rec["scope"],
                        "their_positive_cells": int(dots.sum()),
                        "my_positive_cells_within_3px": float(near[mine].mean()),
                        "spearman_full_footprint": spearman_exact(xrank, arr[fp]),
                        "decoded_equal": bool(np.array_equal(arr, pred))})
        if (i + 1) % 100 == 0:
            print(f"audited {i+1}/{len(rows)} ({time.time()-started:.0f}s)", flush=True)
    worst_overlap = max(results, key=lambda r: r["my_positive_cells_within_3px"])
    worst_rho = max(results, key=lambda r: abs(r["spearman_full_footprint"]))
    violations = [r for r in results if r["my_positive_cells_within_3px"] > 0.70 or
                  abs(r["spearman_full_footprint"]) > 0.90 or r["decoded_equal"]]
    report = {
        "label": "H73-preplacement-and-final-dots", "scope": scope,
        "method": {"overlap": "exact disk-radius 3 px dilation; positive iff value>0",
                   "spearman": "exact full-footprint midrank Spearman (not sampled)",
                   "thresholds": {"max_abs_spearman": 0.9, "max_overlap": 0.7}},
        "candidate_file_sha256": candidate_file_sha,
        "candidate_decoded_sha256": hashlib.sha256(pred.tobytes()).hexdigest(),
        "candidate_positive_cells": int(mine.sum()), "checked_unique_sha_rasters": len(results),
        "worst_overlap": worst_overlap, "worst_abs_spearman": worst_rho,
        "violation_count": len(violations), "violations": sorted(
            violations, key=lambda r: -max(r["my_positive_cells_within_3px"],
                                           abs(r["spearman_full_footprint"])))[:50],
        "byte_unique": candidate_file_sha not in {r["sha256"] for r in rows} if candidate_file_sha else None,
        "pixel_unique": not any(r["decoded_equal"] for r in results),
        "passes": not violations, "decision": "PASS" if not violations else "DUPLICATE-STOP",
        "rows_top20_overlap": sorted(results, key=lambda r: -r["my_positive_cells_within_3px"])[:20],
        "rows_top20_abs_spearman": sorted(results, key=lambda r: -abs(r["spearman_full_footprint"]))[:20],
        "seconds": round(time.time() - started, 2)}
    OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in ("checked_unique_sha_rasters", "worst_overlap",
                                              "worst_abs_spearman", "byte_unique", "pixel_unique",
                                              "passes", "decision")}, indent=2))
    return 0 if report["passes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
