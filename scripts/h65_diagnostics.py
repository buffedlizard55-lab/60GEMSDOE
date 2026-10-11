#!/usr/bin/env python3
"""H65-1 descriptive diagnostics (DESCRIPTIVE, never a score).

1. Support: where can a 10 m channel-steepness lane see anything at all?
   Share of catalogue pixels vs share of all footprint pixels lying within
   300 m (3 px) of a defined 10 m steepness step, of a z >= 1.5 candidate, and of
   a 10 m knickpoint (|step| >= log 2).  An enrichment ratio <= 1 means the
   lane's support is not concentrated where mapped faults are.
2. Relief stratification: mapped faults vs 10 m mean elevation relative to a
   20 km local median (range front vs basin floor), the named confound.
3. Bytes of the group champion h33-2-b2 (owner-reported 0.2778): dot count,
   value set, minimum distance to the catalogue -- re-measured, not copied.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
C = ROOT / ".cache" / "features65"


def main() -> int:
    fp = np.load(C / "footprint.npy")
    cat = np.load(C / "catalogue.npy")
    step = np.load(C / "step.npy")
    knick = np.load(C / "knick_n.npy") > 0
    zmean = np.load(C / "zmean.npy").astype(np.float64)
    defined = fp & np.isfinite(step)
    # same candidate rule as the lane (blockwise z of step >= 1.5) is in the lane receipt;
    # here only the raw supports are measured
    out = dict(evidence_class="DESCRIPTIVE (not a holdout score)", hypothesis="H65-1")
    sup = {}
    for name, m in (("step_defined", defined), ("knickpoint_10m", fp & knick),
                    ("step_ge_log2", defined & (np.nan_to_num(step) >= np.log(2)))):
        near = ndi.distance_transform_edt(~m) <= 3.0
        a = float(near[cat].mean())
        b = float(near[fp].mean())
        sup[name] = dict(share_of_catalogue_within_300m=a, share_of_footprint_within_300m=b,
                         enrichment=a / b if b else None, pixels=int(m.sum()))
    out["support"] = sup
    # relief position: elevation minus 20 km median (range = positive, basin = negative)
    z = np.where(fp & np.isfinite(zmean), zmean, np.nan)
    zf = np.where(np.isfinite(z), z, np.nanmedian(z))
    med = ndi.median_filter(zf[::10, ::10], size=20)          # 1 km samples, 20 km window
    med = np.kron(med, np.ones((10, 10)))[: z.shape[0], : z.shape[1]]
    rel = z - med
    out["relative_elevation_m"] = dict(
        catalogue_p25_p50_p75=[float(x) for x in np.nanpercentile(rel[cat], [25, 50, 75])],
        footprint_p25_p50_p75=[float(x) for x in np.nanpercentile(rel[fp], [25, 50, 75])],
        step_defined_p25_p50_p75=[float(x) for x in np.nanpercentile(rel[defined], [25, 50, 75])],
        note="relative to a 20 km running median (1 km samples) of the 10 m mean elevation; "
             "read the percentiles, no direction is asserted in advance")
    champ = ROOT / "docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
    with rasterio.open(champ) as src:
        a = src.read(1)
    d = ndi.distance_transform_edt(~cat)
    nz = a > 0
    out["champion_h33_2_b2"] = dict(
        file=str(champ.relative_to(ROOT)), nonzero=int(nz.sum()),
        values=sorted({float(v) for v in np.unique(a[np.isfinite(a)])})[:5],
        nan=int((~np.isfinite(a)).sum()),
        min_dist_to_catalogue_m=float(d[nz].min() * 100.0),
        p50_dist_to_catalogue_m=float(np.median(d[nz]) * 100.0),
        share_within_300m_of_catalogue=float((d[nz] <= 3).mean()))
    p = ROOT / "evidence" / "h65_diagnostics.json"
    p.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
