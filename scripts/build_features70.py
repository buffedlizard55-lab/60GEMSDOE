#!/usr/bin/env python3
"""H70-1 Stage A: build the paired-polarity knickpoint-train feature cache.

Reads the three committed native-10 m reduction rasters (sha256-checked against
``data/external/dem10_chi_100m.manifest.json``) and the committed GeoDAWN
radiometric pack, plus the bridged competition grid, and writes
``.cache/features70/*.npy`` with the statistic preregistered in
``registry/preregistration-h70.json``:

    crest(i)       = step_max(i)/1000      (log ksn ratio, steeper-upstream extreme)
    down(i)        = sig(i)                (100 m pixel 500 m downstream of the
                                            pixel's max-|step| 10 m cell; -1 undefined)
    base_drop(i)   = -step_min(down(i))/1000
    pair_strength  = min(crest, base_drop), NaN where either flank missing

plus the shared reduction arrays under the same names run_lane60.py consumes
(step = pair_strength, channel, ksn, acc, playa, branch_sig, footprint,
catalogue, step_min, knick_n, zmean, ephemeral_wash) and the H70-declared extra
confounds (radcg70 radiometric-contact-gradient, litho_core70, exclude_extra70)
whose H66 equivalents (depth_to_base, cond_surf bands) are NOT committed in this
checkout (IR-66-DATA-01).

Deliberately does NOT write ``litho_core.npy``: the H70 core mask is a different
(declared) proxy, and overloading the shared name would silently change the
meaning of evidence from other sessions.

Writes ``evidence/h70_feature_cache.json``.  Deterministic; no labels used
anywhere except the bridged footprint/catalogue masks themselves.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
EXT = ROOT / "data" / "external"
CACHE = ROOT / ".cache" / "features70"

from gems60 import geomorph as gm          # noqa: E402
from gems57 import grid as G57             # noqa: E402

PAIR_FLOOR = float(np.log(1.25))           # 0.22314355131420976 (preregistered)
RADCG_Z = 1.645                            # one-sided ~p95 blockwise z threshold
LITHO_REL_ELEV_M = 180.0                   # H66-defined relative-elevation threshold


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    t0 = time.time()
    man = json.loads((EXT / "dem10_chi_100m.manifest.json").read_text())
    pins = man["files"]
    for name, meta in pins.items():
        p = EXT / name
        got = sha256(p)
        if got != meta["sha256"]:
            raise SystemExit(f"sha256 mismatch for {name}: {got} != {meta['sha256']}")
    print(f"[A] pins ok ({time.time()-t0:.1f}s)", flush=True)

    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue
    H, W = fp.shape

    # --- committed 10 m reduction (band-by-band: 3 GB sandbox) ------------- #
    # mask the raw int16 nodata (-32768) BEFORE float conversion, so no exactness
    # question ever arises on the divided values.
    with rasterio.open(EXT / "dem10_chi_100m_i16.tif") as src:
        nod16 = src.nodata
        def _band(i, scale):
            raw = src.read(i)
            out = np.where(raw == nod16, np.nan,
                           raw.astype(np.float32) / np.float32(scale)).astype(np.float32)
            return out
        crest = _band(1, 1000.0)
        step_min = _band(2, 1000.0)
        ksn = _band(3, 1.0)
        loga = _band(4, 1000.0)
        zmean = _band(5, 1.0)
    with rasterio.open(EXT / "dem10_chi_100m_sig_i32.tif") as src:
        sig = src.read(1)                    # int32, -1 undefined
    with rasterio.open(EXT / "dem10_chi_100m_u8.tif") as src:
        chan_n = src.read(1).astype(np.uint8)
        knick_n = src.read(2).astype(np.int16)
        raised_n = src.read(3).astype(np.int16)
        valid_n = src.read(4).astype(np.int16)
    del chan_n
    print(f"[A] substrate loaded ({time.time()-t0:.1f}s)", flush=True)

    channel = fp & np.isfinite(crest) & np.isfinite(ksn)
    acc = np.where(np.isfinite(loga), 10.0 ** loga.astype(np.float64) / 1.0e4, 0.0).astype(np.float32)
    playa = fp & (raised_n >= 50)
    own = np.arange(fp.size, dtype=np.int64).reshape(fp.shape)
    branch = np.where(channel & (sig >= 0), sig.astype(np.int64), own + fp.size)

    # --- the paired statistic --------------------------------------------- #
    sm_flat = step_min.ravel()
    down = sig.astype(np.int64).ravel()
    ok_down = (down >= 0) & (down < sm_flat.size)
    sm_down = np.full(down.shape, np.nan, dtype=np.float64)
    sm_down[ok_down] = sm_flat[down[ok_down]]
    base_drop = (-sm_down).astype(np.float32).reshape(fp.shape)
    pair = np.where(
        channel & np.isfinite(crest) & np.isfinite(base_drop),
        np.minimum(crest, base_drop),
        np.nan,
    ).astype(np.float32)
    del sm_down, down, ok_down, sm_flat

    # --- confounds: shared definitions + the two H70-declared substitutes --- #
    ephemeral_wash = channel & (ksn < 10.0)

    z = np.where(fp & np.isfinite(zmean), zmean, np.nan)
    zf = np.where(np.isfinite(z), z, float(np.nanmedian(z))).astype(np.float32)
    med20 = ndi.median_filter(zf[::10, ::10], size=20)
    med20 = np.kron(med20, np.ones((10, 10), dtype=np.float32))[:H, :W]
    rel_elev = (z - med20).astype(np.float32)
    del zf, med20

    with rasterio.open(EXT / "geodawn_rad_u8.tif") as src:
        krad = src.read(1).astype(np.float32)
        th = src.read(2).astype(np.float32)
    krad = np.where((krad > 0) & fp, krad, np.nan)
    th = np.where((th > 0) & fp, th, np.nan)
    # radiometric-contact-gradient mask (lithologic contacts)
    def _grad_mag(v):
        fill = np.where(np.isfinite(v), v, float(np.nanmedian(v[fp])))
        gy, gx = np.gradient(ndi.gaussian_filter(fill, sigma=1.0))
        return np.hypot(gy, gx).astype(np.float32)
    gk, gth = _grad_mag(krad), _grad_mag(th)
    zk = gm.blockwise_zscore(gk, fp, block_px=400)
    zt = gm.blockwise_zscore(gth, fp, block_px=400)
    radcg = fp & ((np.nan_to_num(zk, nan=-9.0) > RADCG_Z) | (np.nan_to_num(zt, nan=-9.0) > RADCG_Z))
    radcg = fp & ndi.binary_dilation(radcg, iterations=2)
    # low-radioelement high-relief bedrock cores (substitute for the un-committed
    # depth_to_base<p25 member of H66's litho_core, to which this is NOT identical)
    k_p25 = float(np.nanpercentile(krad[fp], 25))
    th_p25 = float(np.nanpercentile(th[fp], 25))
    litho_core70 = fp & (rel_elev > LITHO_REL_ELEV_M) & (krad <= k_p25) & (th <= th_p25)
    exclude_extra70 = radcg | litho_core70
    del gk, gth, zk, zt

    CACHE.mkdir(parents=True, exist_ok=True)
    arrays = dict(
        step=pair, crest=crest, base_drop=base_drop, pair_strength=pair,
        channel=channel, ksn=ksn, acc=acc, playa=playa, branch_sig=branch,
        footprint=fp, catalogue=cat, step_min=step_min, knick_n=knick_n,
        zmean=zmean, ephemeral_wash=ephemeral_wash,
        rel_elev=rel_elev.astype(np.float32),
        radcg70=radcg, litho_core70=litho_core70, exclude_extra70=exclude_extra70,
    )
    files = []
    for k, v in arrays.items():
        p = CACHE / f"{k}.npy"
        np.save(p, v)
        files.append(dict(name=k, dtype=str(v.dtype), sha256=sha256(p)))
    meta = dict(mode="h70", statistic="pair_strength", pair_floor=PAIR_FLOOR,
                z_min=1.0, min_sep_px=2.8, include_positive_channels=True,
                confounds_extra=["radcg70", "litho_core70"],
                confounds_extra_rule="exclude_extra70 = radcg70 | litho_core70")
    (CACHE / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    ch_pair = channel & np.isfinite(pair)
    diag = dict(
        footprint_px=int(fp.sum()), catalogue_px=int(cat.sum()),
        channel_px=int(channel.sum()),
        pair_defined_channel_px=int(ch_pair.sum()),
        frac_channel_pair_defined=float(ch_pair.sum() / max(1, channel.sum())),
        crest_p50=float(np.nanpercentile(crest[channel], 50)),
        crest_p95=float(np.nanpercentile(crest[channel], 95)),
        pair_p50=float(np.nanpercentile(pair[ch_pair], 50)),
        pair_p95=float(np.nanpercentile(pair[ch_pair], 95)),
        pair_p99=float(np.nanpercentile(pair[ch_pair], 99)),
        frac_pair_ge_floor=float(np.mean(pair[ch_pair] >= PAIR_FLOOR)),
        playa_px=int(playa.sum()),
        ephemeral_wash_px=int(ephemeral_wash.sum()),
        radcg70_px=int(radcg.sum()),
        litho_core70_px=int(litho_core70.sum()),
        exclude_extra70_px=int(exclude_extra70.sum()),
        rad_k_p25=float(k_p25), rad_th_p25=float(th_p25),
        knick_px=int((fp & (knick_n > 0)).sum()),
        distinct_branches=int(np.unique(branch[channel]).size),
        footprint_px_with_valid_dem=int((fp & (valid_n > 0)).sum()),
    )
    rec = dict(evidence_class="DATA-MEASUREMENT", hypothesis="H70-1",
               preregistration="registry/preregistration-h70.json",
               generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               source_manifest=dict(run_id=man.get("run_id"),
                                    tiles=len(man["source"]["tiles"]),
                                    blocks_ok=man["blocks_ok"], blocks_total=man["blocks_total"]),
               statistic_definition=meta, diagnostics=diag, files=files)
    (ROOT / "evidence" / "h70_feature_cache.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps(diag, indent=1), flush=True)
    print(f"[A] wrote .cache/features70 + evidence/h70_feature_cache.json ({time.time()-t0:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
