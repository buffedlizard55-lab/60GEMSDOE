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

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"


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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", default=os.environ.get("GEMS60_FEATURE_CACHE", "features65"))
    ap.add_argument("--tag", default=os.environ.get("GEMS60_TAG", None))
    ap.add_argument("--mode", choices=("h65", "h66"), default=None)
    args = ap.parse_args()
    cache_name = args.cache_dir
    mode = args.mode or ("h66" if "66" in str(cache_name) else "h65")
    tag = args.tag or ("h67" if mode == "h66" else "h65")
    cache_dir = ROOT / ".cache" / cache_name

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
    del b
    with rasterio.open(EXT / "dem10_chi_100m_sig_i32.tif") as src:
        sig = src.read(1).astype(np.int64)
    with rasterio.open(EXT / "dem10_chi_100m_u8.tif") as src:
        chan_n, knick_n, raised_n, valid_n = src.read().astype(np.int32)

    raw_step = np.where(fp, step_max, np.nan)
    channel = fp & np.isfinite(raw_step) & np.isfinite(ksn_max)
    ksn = np.where(channel, ksn_max, np.nan)
    acc = np.where(np.isfinite(loga), 10.0 ** loga / 1.0e4, 0.0)
    playa = fp & (raised_n >= 50)
    own = np.arange(fp.size, dtype=np.int64).reshape(fp.shape)
    branch = np.where(channel & (sig >= 0), sig, own + fp.size)

    extra_arrays = {}
    meta_cfg = dict(mode=mode, z_min=(1.0 if mode == "h66" else 1.5),
                    min_sep_px=(2.8 if mode == "h66" else 0.0),
                    include_positive_channels=bool(mode == "h66"))
    if mode == "h66":
        # H66-1: recover true 10 m upstream/downstream k_sn difference from step_max & ksn_max
        # (Perron & Royden 2013; Gailleton et al. 2019), replacing the un-floored 0.5 log-ratio
        # that blew up on flat desert washes (ksn_max < 10 m^0.9).
        ku = np.maximum(ksn_max, 0.0)
        kd = np.maximum(0.0, (ku + 0.5) * np.exp(-np.clip(step_max, -2.3, 2.3)) - 0.5)
        dksn_signed = np.where(
            channel,
            np.log1p(np.maximum(ku - kd, 0.0)) - np.log1p(np.maximum(kd - ku, 0.0)),
            np.nan,
        )
        with rasterio.open(EXT / "topo_10m_derived_100m_u8.tif") as src:
            tnod = src.nodata
            curv_prof = src.read(4).astype(np.float32)
        curv_prof[curv_prof == tnod] = np.nan
        with rasterio.open(ROOT / "data/official/training_features.tif") as src:
            depth = src.read(15).astype(np.float32)
        depth[~np.isfinite(depth) | (np.abs(depth) > 1e30)] = np.nan
        dfill = np.where(np.isfinite(depth), depth, float(np.nanmedian(depth[fp]))).astype(np.float32)
        gy, gx = np.gradient(ndi.gaussian_filter(dfill, sigma=2.0))
        dbase_grad = np.hypot(gy, gx).astype(np.float32)
        c_med, c_std = float(np.nanmedian(curv_prof[fp])), float(np.nanstd(curv_prof[fp])) + 1e-6
        g_med, g_std = float(np.nanmedian(dbase_grad[fp])), float(np.nanstd(dbase_grad[fp])) + 1e-6
        pied_z = (
            0.5 * np.clip((curv_prof - c_med) / c_std, -2.0, 4.0)
            + 0.5 * np.clip((dbase_grad - g_med) / g_std, -2.0, 4.0)
        ).astype(np.float32)
        pied_z = np.where(np.isfinite(pied_z), pied_z, 0.0).astype(np.float32)
        step = np.where(channel, dksn_signed + 0.25 * pied_z, np.nan)

        # Confound masks 3 & 4: ephemeral alluvial washes (ksn_max < 10 m^0.9)
        # and intra-range high-relief shallow-basement lithologic cores
        ephemeral_wash = channel & (ksn_max < 10.0)
        z = np.where(fp & np.isfinite(zmean), zmean, np.nan)
        zf = np.where(np.isfinite(z), z, float(np.nanmedian(z))).astype(np.float32)
        med20 = ndi.median_filter(zf[::10, ::10], size=20)
        med20 = np.kron(med20, np.ones((10, 10), dtype=np.float32))[:z.shape[0], :z.shape[1]]
        rel_elev = (z - med20).astype(np.float32)
        d_p25 = float(np.nanpercentile(depth[fp], 25))
        litho_core = fp & (rel_elev > 180.0) & np.isfinite(depth) & (depth < d_p25)
        extra_arrays["ephemeral_wash"] = ephemeral_wash
        extra_arrays["litho_core"] = litho_core
        extra_arrays["dksn_signed"] = dksn_signed.astype(np.float32)
        extra_arrays["pied_z"] = pied_z.astype(np.float32)
    else:
        step = raw_step

    cache_dir.mkdir(parents=True, exist_ok=True)
    arrays = dict(step=step.astype(np.float32), channel=channel, ksn=ksn.astype(np.float32),
                  acc=acc.astype(np.float32), playa=playa, branch_sig=branch,
                  footprint=fp, catalogue=cat, step_min=step_min.astype(np.float32),
                  knick_n=knick_n.astype(np.int16), zmean=zmean.astype(np.float32),
                  **extra_arrays)
    files = []
    for k, v in arrays.items():
        p = cache_dir / f"{k}.npy"
        np.save(p, v)
        files.append(dict(name=k, dtype=str(v.dtype), sha256=sha256(p)))
    (cache_dir / "meta.json").write_text(json.dumps(meta_cfg, indent=2) + "\n")
    diag = dict(mode=mode, footprint_px=int(fp.sum()), channel_px=int(channel.sum()),
                channel_frac_of_footprint=float(channel.sum() / fp.sum()),
                playa_px=int(playa.sum()),
                ephemeral_wash_px=int(extra_arrays["ephemeral_wash"].sum()) if "ephemeral_wash" in extra_arrays else 0,
                litho_core_px=int(extra_arrays["litho_core"].sum()) if "litho_core" in extra_arrays else 0,
                step_p50=float(np.nanpercentile(step[channel], 50)),
                step_p95=float(np.nanpercentile(step[channel], 95)),
                frac_step_positive=float(np.mean(step[channel] > 0)),
                ksn_p50=float(np.nanpercentile(ksn[channel], 50)),
                ksn_p95=float(np.nanpercentile(ksn[channel], 95)),
                knick_px=int((fp & (knick_n > 0)).sum()),
                distinct_branches=int(np.unique(branch[channel]).size),
                footprint_px_with_valid_dem=int((fp & (valid_n > 0)).sum()))
    rec = dict(evidence_class="DATA-MEASUREMENT",
               hypothesis=("H66-1" if mode == "h66" else "H65-1"),
               generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               source_manifest=dict(run_id=man.get("run_id"), files=man["files"],
                                    tiles=len(man["source"]["tiles"]),
                                    blocks_ok=man["blocks_ok"], blocks_total=man["blocks_total"]),
               rule=("H66-1 bedrock delta-ksn + piedmont/basement-step + 4-confound masks"
                     if mode == "h66"
                     else "evidence/preregistration_h65.json -> declared_parameters.reduction_to_100m"),
               meta=meta_cfg, diagnostics=diag, files=files)
    (ROOT / "evidence" / f"{tag}_feature_cache.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps(diag, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
