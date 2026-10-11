#!/usr/bin/env python3
"""H65 runner job: one block of the competition grid at native 3DEP 10 m.

Runs on a GitHub-hosted runner (the development sandbox cannot reach the USGS
bucket; see evidence/probe-egress-receipt.json).  For block (by, bx) of an
NBY x NBX tiling of the 3730 x 3292 competition grid it

1. downloads the official USGS 3DEP 1/3 arc-second 1x1 degree tiles that cover
   the block plus an 8 km halo (public domain;
   https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/nYYwXXX/USGS_13_nYYwXXX.tif,
   tile nYYwXXX spans latitude [YY-1, YY] and longitude [-XXX, -XXX+1] -- the
   bounds were verified in evidence/probe-egress-receipt.json for n39w119),
   pinning the sha256 of each tile,
2. reprojects them (bilinear) onto a 10 m EPSG:32611 grid that nests exactly in
   the 100 m competition pixels (origin 243350, 4508550 is a multiple of 10 m),
3. runs ``gems65.dem10.run_block`` (fill, D8, area, chi, chi-space steepness
   step, edge contamination, 10x10 reduction), and
4. writes ``<out>/block_<by>_<bx>.npz`` with the 100 m core arrays + a JSON receipt.

No labels or catalogue are read except the footprint (labels >= 0) used to skip
blocks that lie entirely outside the scored area.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GRID_H, GRID_W = 3730, 3292
X0, Y0, CELL = 243350.0, 4508550.0, 100.0
FINE = 10.0
F = int(CELL / FINE)
BASE = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def block_rows_cols(by, bx, nby, nbx):
    rb = math.ceil(GRID_H / nby)
    cb = math.ceil(GRID_W / nbx)
    r0, r1 = by * rb, min((by + 1) * rb, GRID_H)
    c0, c1 = bx * cb, min((bx + 1) * cb, GRID_W)
    return r0, r1, c0, c1


def tiles_for_bounds(xmin, ymin, xmax, ymax):
    from pyproj import Transformer
    t = Transformer.from_crs(32611, 4269, always_xy=True)
    xs = np.linspace(xmin, xmax, 25)
    ys = np.linspace(ymin, ymax, 25)
    gx, gy = np.meshgrid(xs, ys)
    lon, lat = t.transform(gx.ravel(), gy.ravel())
    names = set()
    for la in range(int(math.floor(lat.min())), int(math.floor(lat.max())) + 1):
        for lo in range(int(math.floor(lon.min())), int(math.floor(lon.max())) + 1):
            # tile nYYwXXX covers lat [YY-1, YY], lon [-XXX, -XXX+1]
            names.add(f"n{la + 1:02d}w{-lo:03d}")
    return sorted(names)


def fetch_tile(name: str, dest: Path) -> dict:
    url = f"{BASE}/{name}/USGS_13_{name}.tif"
    path = dest / f"USGS_13_{name}.tif"
    t0 = time.time()
    r = subprocess.run(["curl", "-sS", "-f", "-L", "--retry", "5", "--retry-delay", "5",
                        "-m", "1800", "-o", str(path), url], capture_output=True, text=True)
    if r.returncode != 0 or not path.exists():
        return dict(tile=name, url=url, ok=False, error=r.stderr.strip()[-300:])
    return dict(tile=name, url=url, ok=True, bytes=path.stat().st_size,
                sha256=sha256(path), seconds=round(time.time() - t0, 1), path=str(path))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--by", type=int, required=True)
    ap.add_argument("--bx", type=int, required=True)
    ap.add_argument("--nby", type=int, default=6)
    ap.add_argument("--nbx", type=int, default=6)
    ap.add_argument("--halo", type=int, default=80, help="halo in 100 m pixels (80 = 8 km)")
    ap.add_argument("--tiles-dir", default="/tmp/tiles")
    ap.add_argument("--out", default="out/dem10")
    a = ap.parse_args()
    t0 = time.time()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rec = dict(block=[a.by, a.bx], tiling=[a.nby, a.nbx], halo_px100=a.halo,
               started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    import rasterio
    from rasterio.transform import Affine
    from rasterio.warp import Resampling, reproject

    with rasterio.open(ROOT / "data/official/labels.tif") as src:
        labels = src.read(1)
    r0, r1, c0, c1 = block_rows_cols(a.by, a.bx, a.nby, a.nbx)
    nr, nc = r1 - r0, c1 - c0
    fp = labels[r0:r1, c0:c1] >= 0
    rec.update(core_rows=[r0, r1], core_cols=[c0, c1], footprint_px=int(fp.sum()))
    if fp.sum() == 0:
        rec["status"] = "skipped: no footprint pixel in the core"
        (out / f"block_{a.by}_{a.bx}.json").write_text(json.dumps(rec, indent=2) + "\n")
        print(json.dumps(rec))
        return 0

    h = a.halo
    fx0 = X0 + (c0 - h) * CELL
    fy0 = Y0 - (r0 - h) * CELL
    FH, FW = (nr + 2 * h) * F, (nc + 2 * h) * F
    dst_t = Affine(FINE, 0.0, fx0, 0.0, -FINE, fy0)
    xmin, xmax = fx0, fx0 + FW * FINE
    ymax, ymin = fy0, fy0 - FH * FINE
    names = tiles_for_bounds(xmin, ymin, xmax, ymax)
    rec["tiles_needed"] = names
    tdir = Path(a.tiles_dir)
    tdir.mkdir(parents=True, exist_ok=True)
    got = [fetch_tile(n, tdir) for n in names]
    rec["tiles"] = [{k: v for k, v in g.items() if k != "path"} for g in got]
    print(f"[{time.time()-t0:.0f}s] tiles {[(g['tile'], g['ok']) for g in got]}", flush=True)

    z = np.full((FH, FW), np.nan, np.float32)
    for g in got:
        if not g["ok"]:
            continue
        with rasterio.open(g["path"]) as src:
            tmp = np.full((FH, FW), np.nan, np.float32)
            reproject(source=rasterio.band(src, 1), destination=tmp,
                      src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                      dst_transform=dst_t, dst_crs="EPSG:32611", dst_nodata=np.nan,
                      resampling=Resampling.bilinear, num_threads=4)
        good = np.isfinite(tmp) & (tmp > -1000)
        z = np.where(good & ~np.isfinite(z), tmp, z)
        del tmp
        Path(g["path"]).unlink()
    rec["dem_finite_frac"] = float(np.isfinite(z).mean())
    rec["dem_min_max"] = [float(np.nanmin(z)), float(np.nanmax(z))] if np.isfinite(z).any() else None
    print(f"[{time.time()-t0:.0f}s] dem {FH}x{FW} finite={rec['dem_finite_frac']:.4f}", flush=True)

    from gems65 import dem10 as D
    res, diag = D.run_block(z, FINE, h * F, h * F, nr, nc, F, r0, c0, GRID_W)
    rec["diagnostics"] = diag
    rec["parameters"] = dict(theta=D.THETA_REF, a0_m2=D.A0_M2, a_channel_m2=D.A_CHANNEL_M2,
                             window_m=D.WINDOW_M, step_floor_ksn=D.STEP_FLOOR_KSN,
                             step_winsor=D.STEP_WINSOR, knick_min=D.KNICK_MIN,
                             fill_raise_m=D.FILL_RAISE_M, sig_steps_m=D.SIG_STEPS_M,
                             fine_cell_m=FINE, resampling="bilinear")
    np.savez_compressed(out / f"block_{a.by}_{a.bx}.npz", r0=r0, c0=c0, **res)
    rec["status"] = "ok"
    rec["seconds"] = round(time.time() - t0, 1)
    (out / f"block_{a.by}_{a.bx}.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if k != "tiles"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
