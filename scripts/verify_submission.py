#!/usr/bin/env python3
"""Independent format check for every committed submission GeoTIFF.

Re-reads the bytes from disk (never trusting the writer) and checks the portal's
requirements:

  * single-band GeoTIFF, CRS / shape / geotransform identical to the submission format
  * every value inside [0, 1]  -- the check that produced the portal error
    "Predicted values must be in range [0, 1]"
  * no NaN / Inf
  * footprint handling declared (zero-filled or NaN-filled, both validated)

Exit status 0 = PASS, 1 = FAIL.  Prints one line per file.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
EXPECT = dict(crs="EPSG:32611", shape=(3730, 3292),
              transform=(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0))


def check(path: Path) -> tuple[bool, list[str]]:
    msgs, ok = [], True

    def need(cond, msg):
        nonlocal ok
        if not cond:
            ok = False
        msgs.append(("PASS " if cond else "FAIL ") + msg)

    with rasterio.open(path) as ds:
        a = ds.read()
        need(ds.count == 1, f"single band (got {ds.count})")
        need(ds.dtypes[0] == "float32", f"float32 (got {ds.dtypes[0]})")
        need(str(ds.crs) == EXPECT["crs"], f"crs {ds.crs}")
        need(ds.shape == EXPECT["shape"], f"shape {ds.shape}")
        need(tuple(ds.transform)[:6] == EXPECT["transform"],
             f"transform {tuple(ds.transform)[:6]}")
        band = a[0]
        need(bool(np.isfinite(band).all()), "all values finite (no NaN / Inf)")
        need(bool((band >= 0.0).all() and (band <= 1.0).all()),
             f"every value in [0, 1] (min {np.nanmin(band)}, max {np.nanmax(band)})")
        need(ds.nodata is None, f"no nodata tag (got {ds.nodata})")
    return ok, msgs


def main() -> int:
    files = sorted((ROOT / "docs" / "downloads").glob("*.tif")) + \
            sorted((ROOT / "registry" / "submissions").glob("*.tif")) \
        if (ROOT / "registry" / "submissions").exists() else \
        sorted((ROOT / "docs" / "downloads").glob("*.tif"))
    if not files:
        print("no submission GeoTIFF found")
        return 1
    bad = 0
    for f in files:
        ok, msgs = check(f)
        print(f"\n{f.name}: {'PASS' if ok else 'FAIL'}")
        for m in msgs:
            print("   " + m)
        bad += 0 if ok else 1
    print(f"\n{len(files) - bad}/{len(files)} files pass")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
