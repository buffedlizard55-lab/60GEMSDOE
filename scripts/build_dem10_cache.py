#!/usr/bin/env python3
"""H65-1 Stage A': turn the committed native-10 m reduction into the lane's feature cache.

Reads the three rasters the ``dem10-chi`` workflow committed (sha256-checked
against ``data/external/dem10_chi_100m.manifest.json``) and writes
``.cache/features65/*.npy`` with exactly the names ``scripts/run_lane60.py``
and ``scripts/build_submission60.py`` consume, following the reduction rule
pre-registered in ``evidence/preregistration_h65.json``:

    step       = step_max / 1000            (steeper-upstream extreme, log ratio)
    channel    = footprint & step defined
    ksn        = ksn_max                    (m^0.9)
    acc        = 10**log10_area / 1e4       (100 m cells; canary only)
    playa      = raised_n >= 50             (closed-basin floor / filled flat)
    branch_sig = global 100 m index 500 m downstream of the max-|step| 10 m cell
    footprint, catalogue from the pinned labels

Writes ``evidence/h65_feature_cache.json``.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"
CACHE = ROOT / ".cache" / "features65"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "H65 DEM10 feature-cache builder"):
        return 0
    man = json.loads((EXT / "dem10_chi_100m.manifest.json").read_text())
    for name, meta in man["files"].items():
        got = sha256(EXT / name)
        if got != meta["sha256"]:
            raise SystemExit(f"sha256 mismatch for {name}: {got} != {meta['sha256']}")
    with rasterio.open(ROOT / "data/official/labels.tif") as src:
        labels = src.read(1)
    fp = labels >= 0
    cat = labels == 1
    with rasterio.open(EXT / "dem10_chi_100m_i16.tif") as src:
        b = src.read().astype(np.float64)
        nod = src.nodata
    b[b == nod] = np.nan
    step_max, step_min, ksn_max, loga, zmean = b / np.array([1000, 1000, 1, 1000, 1])[:, None, None]
    with rasterio.open(EXT / "dem10_chi_100m_sig_i32.tif") as src:
        sig = src.read(1).astype(np.int64)
    with rasterio.open(EXT / "dem10_chi_100m_u8.tif") as src:
        chan_n, knick_n, raised_n, valid_n = src.read().astype(np.int32)
    step = np.where(fp, step_max, np.nan)
    channel = fp & np.isfinite(step)
    ksn = np.where(channel, ksn_max, np.nan)
    acc = np.where(np.isfinite(loga), 10.0 ** loga / 1.0e4, 0.0)
    playa = fp & (raised_n >= 50)
    # independence: pixels without a step get their own index (never shared)
    own = np.arange(fp.size, dtype=np.int64).reshape(fp.shape)
    branch = np.where(channel & (sig >= 0), sig, own + fp.size)
    CACHE.mkdir(parents=True, exist_ok=True)
    arrays = dict(step=step.astype(np.float32), channel=channel, ksn=ksn.astype(np.float32),
                  acc=acc.astype(np.float32), playa=playa, branch_sig=branch,
                  footprint=fp, catalogue=cat, step_min=step_min.astype(np.float32),
                  knick_n=knick_n.astype(np.int16), zmean=zmean.astype(np.float32))
    files = []
    for k, v in arrays.items():
        p = CACHE / f"{k}.npy"
        np.save(p, v)
        files.append(dict(name=k, dtype=str(v.dtype), sha256=sha256(p)))
    diag = dict(footprint_px=int(fp.sum()), channel_px=int(channel.sum()),
                channel_frac_of_footprint=float(channel.sum() / fp.sum()),
                playa_px=int(playa.sum()),
                step_p50=float(np.nanpercentile(step[channel], 50)),
                step_p95=float(np.nanpercentile(step[channel], 95)),
                frac_step_positive=float(np.mean(step[channel] > 0)),
                ksn_p50=float(np.nanpercentile(ksn[channel], 50)),
                ksn_p95=float(np.nanpercentile(ksn[channel], 95)),
                knick_px=int((fp & (knick_n > 0)).sum()),
                distinct_branches=int(np.unique(branch[channel]).size),
                footprint_px_with_valid_dem=int((fp & (valid_n > 0)).sum()))
    rec = dict(evidence_class="DATA-MEASUREMENT", hypothesis="H65-1",
               generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               source_manifest=dict(run_id=man.get("run_id"), files=man["files"],
                                    tiles=len(man["source"]["tiles"]),
                                    blocks_ok=man["blocks_ok"], blocks_total=man["blocks_total"]),
               rule="evidence/preregistration_h65.json -> declared_parameters.reduction_to_100m",
               diagnostics=diag, files=files)
    (ROOT / "evidence" / "h65_feature_cache.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps(diag, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
