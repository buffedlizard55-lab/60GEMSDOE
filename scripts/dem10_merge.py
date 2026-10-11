#!/usr/bin/env python3
"""H65 runner merge job: assemble the per-block 10 m reductions into three
compact GeoTIFFs on the exact competition grid + a provenance manifest.

Outputs (committed back to the branch by the workflow):
  data/external/dem10_chi_100m_i16.tif   int16, nodata -32768
       1 step_max x1000   (log steepness step, steeper-upstream extreme)
       2 step_min x1000   (steeper-downstream extreme)
       3 ksn_max          (m^0.9, rounded, clipped to 32767)
       4 loga_at x1000    (log10 drainage area, m^2, at the max-|step| cell)
       5 zmean            (m, mean 10 m elevation of the 100 m pixel)
  data/external/dem10_chi_100m_sig_i32.tif  int32, nodata -1
       1 sig_at           (global 100 m flat index of the cell 500 m downstream
                           of the max-|step| 10 m cell; branch independence)
  data/external/dem10_chi_100m_u8.tif    uint8
       1 chan_n  2 knick_n  3 raised_n  4 valid_n   (counts of 10 m cells / 100)
  data/external/dem10_chi_100m.manifest.json
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

ROOT = Path(__file__).resolve().parents[1]
H, W = 3730, 3292
TRANSFORM = Affine(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def write(path, bands, dtype, nodata, names):
    prof = dict(driver="GTiff", height=H, width=W, count=len(bands), dtype=dtype,
                crs="EPSG:32611", transform=TRANSFORM, nodata=nodata, compress="deflate",
                predictor=2, zlevel=9, tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(path, "w", **prof) as dst:
        for i, (b, n) in enumerate(zip(bands, names), start=1):
            dst.write(b.astype(dtype), i)
            dst.set_band_description(i, n)


def main() -> int:
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "H65 10 m DEM feature merge"):
        return 0
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--blocks", default="blocks")
    ap.add_argument("--out", default="data/external")
    a = ap.parse_args()
    with rasterio.open(ROOT / "data/official/labels.tif") as src:
        fp = src.read(1) >= 0
    names = ("step_max", "step_min", "ksn_max", "loga_at", "zmean")
    f32 = {n: np.full((H, W), np.nan, np.float32) for n in names}
    sig = np.full((H, W), -1, np.int32)
    u8n = ("chan_n", "knick_n", "raised_n", "valid_n")
    u8 = {n: np.zeros((H, W), np.int32) for n in u8n}
    covered = np.zeros((H, W), bool)
    receipts = []
    for js in sorted(glob.glob(os.path.join(a.blocks, "**", "block_*.json"), recursive=True)):
        rec = json.loads(Path(js).read_text())
        receipts.append(rec)
        if rec.get("status") != "ok":
            continue
        npz = np.load(js[:-5] + ".npz")
        r0, c0 = int(npz["r0"]), int(npz["c0"])
        nr, nc = npz["step_max"].shape
        sl = (slice(r0, r0 + nr), slice(c0, c0 + nc))
        for n in names:
            f32[n][sl] = npz[n]
        sig[sl] = npz["sig_at"]
        for n in u8n:
            u8[n][sl] = npz[n]
        covered[sl] = True
    for n in names:
        f32[n][~fp] = np.nan
    sig[~fp] = -1
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)

    def q(v, scale, lo=-32767, hi=32767):
        r = np.where(np.isfinite(v), np.clip(np.round(v * scale), lo, hi), -32768)
        return r.astype(np.int16)

    p16 = out / "dem10_chi_100m_i16.tif"
    write(p16, [q(f32["step_max"], 1000), q(f32["step_min"], 1000), q(f32["ksn_max"], 1, 0),
                q(f32["loga_at"], 1000), q(f32["zmean"], 1)], "int16", -32768,
          ["step_max_x1000", "step_min_x1000", "ksn_max_m0.9", "log10_area_m2_x1000", "zmean_m"])
    p32 = out / "dem10_chi_100m_sig_i32.tif"
    write(p32, [sig], "int32", -1, ["branch_signature_global_index_100m"])
    p8 = out / "dem10_chi_100m_u8.tif"
    write(p8, [np.where(fp, np.clip(u8[n], 0, 255), 0) for n in u8n], "uint8", None, list(u8n))
    tiles = {}
    for r in receipts:
        for t in r.get("tiles", []):
            if t.get("ok"):
                tiles[t["tile"]] = dict(url=t["url"], bytes=t["bytes"], sha256=t["sha256"])
    man = dict(
        evidence_class="DATA-MEASUREMENT",
        hypothesis="H65-1 (executes H62-5): tectonic-geomorphology lane at native 3DEP 10 m",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        workflow=os.environ.get("GITHUB_WORKFLOW"), run_id=os.environ.get("GITHUB_RUN_ID"),
        run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT"), ref=os.environ.get("GITHUB_REF"),
        commit=os.environ.get("GITHUB_SHA"),
        source=dict(product="USGS 3DEP 1/3 arc-second DEM (current 1x1 degree tiles)",
                    license="public domain (USGS)",
                    landing="https://www.usgs.gov/3d-elevation-program",
                    bucket="https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/",
                    tiles=dict(sorted(tiles.items()))),
        grid=dict(height=H, width=W, crs="EPSG:32611", transform=list(TRANSFORM)[:6]),
        blocks_ok=sum(1 for r in receipts if r.get("status") == "ok"),
        blocks_total=len(receipts),
        footprint_px=int(fp.sum()), footprint_px_covered=int((fp & covered).sum()),
        footprint_px_with_step=int((fp & np.isfinite(f32["step_max"])).sum()),
        files={p.name: dict(bytes=p.stat().st_size, sha256=sha256(p)) for p in (p16, p32, p8)},
        block_receipts=receipts,
    )
    (out / "dem10_chi_100m.manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    print(json.dumps({k: v for k, v in man.items() if k != "block_receipts"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
