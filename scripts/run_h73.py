#!/usr/bin/env python3
"""H73-1 -- power-resolved replication of the tectonic-geomorphology lane's mandated first test.

Protocol position
-----------------
Lane (verbatim from the governing brief): *"Tectonic-geomorphology lane: channel steepness and
knickpoints, not scarp shape ... Extract drainage from the free 3DEP 10 m DEM (or 1 m tiles),
compute chi and normalized steepness, and keep only knickpoints and steepness steps that align
across several independent drainages along a common strike. First test: do channels crossing
withheld segments show larger steepness steps than random lines of the same orientation? If not,
stop."*

What is new here (and why it is not a rerun)
--------------------------------------------
Every prior first test in this lane (H65-1, H66-1, H66-6, H70-1) used the same test design:
``hide_frac = 0.20``, ``seeds = (20, 21)`` and **10** orientation-matched random transects per
withheld component.  That design yields n = 262 scoreable components and a 95% CI half-width of
about 0.047 for the measured component std of 0.39 -- while the pooled point estimate has been
positive and stable across three independent statistics (+0.0326, +0.0404, +0.0326).  The lane has
therefore been reporting "no signal" for what is, on its own numbers, an *unresolved* signal.

H73-1 changes only the DESIGN -- more withheld segments (hide_frac 0.50, seeds 20/21/22) and more
control transects per component (100 instead of 10) -- never the statistic.  The endpoint and the
gate are fixed in ``registry/preregistration-h73.json``, which was written before any number in
this session existed.

Order of operations (a receipt is written after every stage, so a crash leaves evidence)
----------------------------------------------------------------------------------------
  0  verify the preregistration file predates this process;
  1  load + SHA-256 every input against the pinned manifest;
  2  build the confound-masked chi/ksn feature cache from the committed native-10 m reduction;
  3  E1  -- the mandated gating first test (withheld catalogue segments vs orientation-matched
            random transects);
  4  E1b -- non-gating replication on the off-catalogue SGMC population;
  5  leakage canary: every input feature alone (AUC > 0.90 is leakage until proven otherwise);
  6  lane surface: strike-aligned corridors corroborated by >= 3 independent drainages;
  7  holdout DTI on the shared pooled evaluator;
  8  emission: 3 px NMS dots, p = 1 (DTI is monotone in a uniform rescaling of a fixed support);
  9  uniqueness against every obtainable registry raster;
 10  write the GeoTIFF (all-finite "zeros" container primary), validate it literally, run card.

Usage
-----
    python scripts/run_h73.py --stage cache
    python scripts/run_h73.py --stage e1
    python scripts/run_h73.py --stage all
"""
from __future__ import annotations

import argparse
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
sys.path.insert(0, str(ROOT / "scripts"))

from gems57 import grid as G57, holdout as HO57  # noqa: E402
from gems57.grid import Grid  # noqa: E402
from gems60 import metric as M  # noqa: E402

T0 = time.time()

# --- pins (recomputed with hashlib at read time; never quoted and trusted) --------------------- #
PINS = {
    "data/bridge/existing_faults.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "data/bridge/sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}

# --- declared, preregistered constants -------------------------------------------------------- #
HIDE_FRAC = 0.50
SEEDS = (20, 21, 22)
N_TRANSECTS = 100
MIN_CTRL = 25
MIN_COMPONENT_PX = 6
BOOT_DRAWS = 4000
BOOT_SEED = 60101
BLOCK_PX = 400          # 40 km climate / regional-gradient blocks
N_DRAINAGE_MIN = 3      # "several independent drainages"
Z_MIN = 1.0             # blockwise z of the knickpoint step for a candidate
CORRIDOR_HALF_LEN_PX = 8
CORRIDOR_HALF_WIDTH_PX = 2
TRACE_DECAY = 0.5
NMS_PX = 3.0
A_C_M2 = 1.0e6            # 1 km^2 channel-initiation threshold on the 100 m DEM
# The lane's corroboration rule is deliberately strict, so the support it admits is small (a few
# thousand pixels).  The emission ladder is therefore swept over NMS spacing rather than over an
# arbitrary dot count: 0.0 means "every corroborated corridor pixel at p = 1".
SPACINGS = (0.0, 1.5, 2.0, 3.0, 4.0)
PRIMARY_SPACING = 0.0
BIG = np.ones((3, 3), dtype=int)


def log(msg: str) -> None:
    print(f"[{time.time() - T0:7.1f}s] {msg}", flush=True)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=_jsonable) + "\n")


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"not JSON serialisable: {type(o)!r}")


# ============================================================================================== #
# stage 0 -- preregistration must predate this process
# ============================================================================================== #
def stage0_preregistration() -> dict:
    p = ROOT / "registry" / "preregistration-h73.json"
    pre = json.loads(p.read_text())
    mtime = p.stat().st_mtime
    ok = mtime < T0
    log(f"stage0: preregistration {p.name} mtime={mtime:.0f} process_start={T0:.0f} predates_run={ok}")
    if not ok:
        raise SystemExit("preregistration file was written after this process started")
    return pre


# ============================================================================================== #
# stage 1 -- pinned inputs
# ============================================================================================== #
def stage1_inputs() -> Grid:
    for rel, want in PINS.items():
        got = sha256(ROOT / rel)
        if got != want:
            raise SystemExit(f"sha256 mismatch {rel}: {got} != {want}")
    g = G57.load_grid()
    log(f"stage1: grid {g.height}x{g.width} footprint={int(g.footprint.sum())} "
        f"catalogue={int(g.catalogue.sum())}")
    return g


# ============================================================================================== #
# stage 2 -- feature cache
# ============================================================================================== #
def stage2_cache(grid: Grid, cache_dir: Path) -> dict:
    ext = ROOT / "data" / "external"
    man = json.loads((ext / "dem10_chi_100m.manifest.json").read_text())
    for name, meta in man["files"].items():
        got = sha256(ext / name)
        if got != meta["sha256"]:
            raise SystemExit(f"sha256 mismatch {name}: {got} != {meta['sha256']}")

    with rasterio.open(ext / "dem10_chi_100m_i16.tif") as src:
        b = src.read().astype(np.float64)
        nod = src.nodata
    b[b == nod] = np.nan
    step_max, step_min, ksn_max, loga, zmean = b / np.array([1000, 1000, 1, 1000, 1])[:, None, None]
    del b

    with rasterio.open(ext / "dem10_chi_100m_u8.tif") as src:
        chan_n, knick_n, raised_n, _valid_n = src.read().astype(np.int32)

    fp = grid.footprint
    cat = grid.catalogue

    raw_step = np.where(fp, step_max, np.nan)
    channel0 = fp & np.isfinite(raw_step) & np.isfinite(ksn_max)

    # --- the brief's four confounds ---------------------------------------------------------- #
    playa = fp & (raised_n >= 50)                       # closed-basin / filled flat base level
    ephemeral = channel0 & (ksn_max < 10.0)             # unincised desert wash, no bedrock profile
    z = np.where(fp & np.isfinite(zmean), zmean, np.nan)
    zf = np.where(np.isfinite(z), z, float(np.nanmedian(z))).astype(np.float32)
    med20 = ndi.median_filter(zf[::10, ::10], size=20)
    med20 = np.kron(med20, np.ones((10, 10), dtype=np.float32))[: z.shape[0], : z.shape[1]]
    rel_elev = (z - med20).astype(np.float32)
    litho_core = fp & (rel_elev > 180.0)                # DEM-only intra-range high-relief core

    confound = playa | ephemeral | litho_core
    channel = channel0 & ~confound

    # --- the statistics ----------------------------------------------------------------------- #
    # PRIMARY (scale-free): the committed reduction's step_max = ln(ku/kd), stored as step_max/1000.
    #   Kirby & Whipple (2012) and Wobus et al. (2006) read the RELATIVE steepness step; this is the
    #   quantity that is comparable between channels of different size, which is the whole point of
    #   the chi normalisation, and it is the statistic H65-1 / H66-6 / H70-1 measured.
    # SECONDARY: the absolute up-down difference dksn_signed, preregistered first and kept for
    #   completeness (see the amendment recorded in registry/preregistration-h73.json).
    ku = np.maximum(ksn_max, 0.0)
    kd = np.maximum(0.0, (ku + 0.5) * np.exp(-np.clip(step_max, -2.3, 2.3)) - 0.5)
    dksn = np.where(channel0, np.log1p(np.maximum(ku - kd, 0.0)) - np.log1p(np.maximum(kd - ku, 0.0)),
                    np.nan).astype(np.float32)

    # climate / regional gradient: subtract the 40 km block median over channel cells
    step = np.where(channel, raw_step, np.nan).astype(np.float32)
    step = _block_centre(step, channel, BLOCK_PX)
    step_abs = np.where(channel, dksn, np.nan).astype(np.float32)
    step_abs = _block_centre(step_abs, channel, BLOCK_PX)

    arrays = dict(step=step, step_abs=step_abs, dksn=dksn, channel=channel, channel0=channel0,
                  ksn=np.where(channel, ksn_max, np.nan).astype(np.float32),
                  loga=np.where(np.isfinite(loga), loga, np.nan).astype(np.float32),
                  zmean=z.astype(np.float32), step_min=np.where(fp, step_min, np.nan).astype(np.float32),
                  knick_n=knick_n.astype(np.int16),
                  playa=playa, ephemeral=ephemeral, litho_core=litho_core, confound=confound,
                  footprint=fp, catalogue=cat)
    cache_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for k, v in arrays.items():
        p = cache_dir / f"{k}.npy"
        np.save(p, v)
        files.append(dict(name=k, dtype=str(v.dtype), sha256=sha256(p)))

    diag = dict(footprint_px=int(fp.sum()), channel0_px=int(channel0.sum()),
                channel_px=int(channel.sum()), playa_px=int(playa.sum()),
                ephemeral_px=int(ephemeral.sum()), litho_core_px=int(litho_core.sum()),
                confound_px=int(confound.sum()),
                step_finite=int(np.isfinite(step).sum()),
                step_mean=float(np.nanmean(step[channel])),
                step_std=float(np.nanstd(step[channel])),
                step_abs_mean=float(np.nanmean(step_abs[channel])),
                step_abs_std=float(np.nanstd(step_abs[channel])))
    rec = dict(stage="cache", evidence_class="DATA-MEASUREMENT", hypothesis="H73-1",
               inputs=[dict(path=k, sha256=v) for k, v in PINS.items()],
               dem10_manifest="data/external/dem10_chi_100m.manifest.json",
               primary_statistic="relative_step (step_max/1000), block-centred, confound-masked",
               secondary_statistic="dksn_signed, block-centred, confound-masked",
               files=files, diagnostics=diag)
    write_json(ROOT / "evidence" / "h73_feature_cache.json", rec)
    log(f"stage2: channel={diag['channel_px']} confound={diag['confound_px']} "
        f"step_std={diag['step_std']:.4f}")
    return rec


def _block_centre(step: np.ndarray, channel: np.ndarray, block: int) -> np.ndarray:
    """Subtract the per-block median of the statistic over channel cells (climate gradient)."""
    H, W = step.shape
    out = np.full((H, W), np.nan, dtype=np.float32)
    for y0 in range(0, H, block):
        for x0 in range(0, W, block):
            sl = (slice(y0, min(y0 + block, H)), slice(x0, min(x0 + block, W)))
            sel = channel[sl] & np.isfinite(step[sl])
            if sel.sum() < 50:
                continue
            med = float(np.nanmedian(step[sl][sel]))
            blk = step[sl]
            out[sl] = np.where(np.isfinite(blk), blk - med, np.nan)
    return out


def load_cache(cache_dir: Path) -> dict:
    return {p.stem: np.load(p) for p in sorted(cache_dir.glob("*.npy"))}


# ============================================================================================== #
# stages 3 & 4 -- the mandated first test
# ============================================================================================== #
def component_orientation(yx) -> tuple[float, float]:
    """Principal-axis azimuth (rad, mod pi) and length (px) of a component."""
    y, x = yx
    if y.size < 2:
        return 0.0, 1.0
    p = np.stack([y - y.mean(), x - x.mean()], 1).astype(np.float64)
    cov = p.T @ p / max(p.shape[0] - 1, 1)
    w, v = np.linalg.eigh(cov)
    axis = v[:, int(np.argmax(w))]
    az = float(np.arctan2(axis[1], -axis[0]))
    length = float(4.0 * np.sqrt(max(w.max(), 0.0)))
    return az % np.pi, max(length, 2.0)


def _dilate_window(shape, ys, xs, buffer_px):
    H, W = shape
    y0 = max(int(ys.min()) - buffer_px - 1, 0)
    y1 = min(int(ys.max()) + buffer_px + 2, H)
    x0 = max(int(xs.min()) - buffer_px - 1, 0)
    x1 = min(int(xs.max()) + buffer_px + 2, W)
    sub = np.zeros((y1 - y0, x1 - x0), bool)
    sub[ys - y0, xs - x0] = True
    sub = ndi.binary_dilation(sub, iterations=buffer_px)
    return (slice(y0, y1), slice(x0, x1)), sub


def _transect_mean(y0, x0, az, length, step, channel, active, buffer_px=3, min_channel_px=3):
    """Mean statistic within ``buffer_px`` of a line of the given azimuth, or None."""
    H, W = step.shape
    u = np.array([-np.cos(az), np.sin(az)])
    yy = np.clip(np.round(y0 + u[0] * np.arange(length)).astype(int), 0, H - 1)
    xx = np.clip(np.round(x0 + u[1] * np.arange(length)).astype(int), 0, W - 1)
    if active[yy, xx].mean() < 0.6:
        return None
    win, sub = _dilate_window(step.shape, yy, xx, buffer_px)
    zone = sub & channel[win] & active[win]
    if int(zone.sum()) < min_channel_px:
        return None
    vals = step[win][zone]
    vals = vals[np.isfinite(vals)]
    if vals.size < min_channel_px:
        return None
    return float(vals.mean())


def run_first_test(grid: Grid, cache: dict, *, hide_frac: float, seeds, n_transects: int,
                   truth_population: np.ndarray | None = None, tag: str = "E1",
                   field: str = "step") -> dict:
    """Withheld segments vs orientation-matched random transects of the same length."""
    step = cache[field]
    channel = cache["channel"]
    cat = grid.catalogue

    ctx = HO57.build_holdout(grid, hide_frac=hide_frac, seeds=tuple(seeds), modes=("all",))
    log(f"{tag}: {len(ctx.cells)} fold cells (hide_frac={hide_frac}, seeds={seeds})")

    rng = np.random.default_rng(6001)
    rows: list[dict] = []
    for cell in ctx.cells:
        bb = cell.bbox
        truth = np.zeros(cell.active.shape, bool)
        truth[cell.truth_yx] = True
        if truth_population is not None:
            truth = truth_population[bb] & cell.active
        if not truth.any():
            continue
        vis = (cat & ~ctx.hidden_by_cell[cell.key])[bb]
        step_c, chan_c, act_c = step[bb], channel[bb], cell.active
        forbidden = ndi.binary_dilation(truth | vis, iterations=10)
        pool = np.nonzero(act_c & ~forbidden)
        if pool[0].size == 0:
            continue
        if pool[0].size > 400_000:
            pick = rng.choice(pool[0].size, 400_000, replace=False)
            pool = (pool[0][pick], pool[1][pick])
        lab, n = ndi.label(truth, structure=BIG)
        objs = ndi.find_objects(lab)
        for cid in range(1, n + 1):
            sl = objs[cid - 1]
            if sl is None:
                continue
            sy, sx = np.nonzero(lab[sl] == cid)
            ys, xs = sy + sl[0].start, sx + sl[1].start
            if ys.size < MIN_COMPONENT_PX:
                continue
            az, length = component_orientation((ys, xs))
            length = int(np.clip(round(length), MIN_COMPONENT_PX, 60))
            win, sub = _dilate_window(step_c.shape, ys, xs, 3)
            zone = sub & chan_c[win] & act_c[win]
            vals = step_c[win][zone]
            vals = vals[np.isfinite(vals)]
            if vals.size < 3:
                rows.append(dict(cell=cell.key, component=int(cid), n_px=int(ys.size),
                                 crossing_channel_px=int(zone.sum()), skipped="no channel crossing"))
                continue
            obs = float(vals.mean())
            ctr = []
            for _ in range(n_transects):
                i = int(rng.integers(pool[0].size))
                got = _transect_mean(float(pool[0][i]), float(pool[1][i]), az, length,
                                     step_c, chan_c, act_c)
                if got is not None:
                    ctr.append(got)
            if len(ctr) < MIN_CTRL:
                rows.append(dict(cell=cell.key, component=int(cid), n_px=int(ys.size),
                                 crossing_channel_px=int(zone.sum()),
                                 observed_mean_step=obs,
                                 skipped=f"only {len(ctr)} valid transects"))
                continue
            rows.append(dict(cell=cell.key, component=int(cid), n_px=int(ys.size),
                             azimuth_deg=float(np.rad2deg(az)), length_px=length,
                             crossing_channel_px=int(zone.sum()),
                             observed_mean_step=obs,
                             control_mean_step=float(np.mean(ctr)),
                             control_std_step=float(np.std(ctr)),
                             n_control_transects=len(ctr),
                             paired_difference=obs - float(np.mean(ctr))))
    log(f"{tag}: {len(rows)} components, "
        f"{sum(1 for r in rows if 'paired_difference' in r)} scoreable")
    return dict(rows=rows, n_cells=len(ctx.cells))


def paired_bootstrap(rows, draws=BOOT_DRAWS, seed=BOOT_SEED) -> dict:
    d = np.array([r["paired_difference"] for r in rows if "paired_difference" in r], float)
    if d.size < 10:
        return dict(n_components=int(d.size), mean=float(d.mean()) if d.size else None,
                    ci95=[None, None], fraction_positive=None,
                    verdict="INSUFFICIENT_COMPONENTS")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(draws, d.size))
    boot = d[idx].mean(axis=1)
    lo, hi = np.quantile(boot, [0.025, 0.975])
    mean = float(d.mean())
    verdict = ("PROCEED" if (mean > 0 and lo > 0) else
               "STOP" if (mean <= 0 or hi < 0) else "INCONCLUSIVE")
    return dict(evidence_class="MEASUREMENT", n_components=int(d.size), mean=mean,
                median=float(np.median(d)), ci95=[float(lo), float(hi)],
                fraction_positive=float((d > 0).mean()),
                component_std=float(d.std(ddof=1)) if d.size > 1 else None,
                bootstrap=dict(draws=draws, seed=seed,
                               method="percentile over withheld components"),
                verdict=verdict)


# ============================================================================================== #
# stage 5 -- leakage canary
# ============================================================================================== #
def auc(score: np.ndarray, labels: np.ndarray) -> float:
    s = np.asarray(score, dtype=np.float64).ravel()
    y = np.asarray(labels, dtype=bool).ravel()
    keep = np.isfinite(s)
    s, y = s[keep], y[keep]
    if y.sum() == 0 or (~y).sum() == 0:
        return float("nan")
    order = np.argsort(s, kind="stable")
    sr, ranks = s[order], np.arange(1, s.size + 1, dtype=np.float64)
    i = 0
    while i < sr.size:
        j = i
        while j + 1 < sr.size and sr[j + 1] == sr[i]:
            j += 1
        if j > i:
            ranks[i:j + 1] = ranks[i:j + 1].mean()
        i = j + 1
    r = np.empty(s.size, dtype=np.float64)
    r[order] = ranks
    n1, n0 = float(y.sum()), float((~y).sum())
    return float((r[y].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def leakage_canary(grid: Grid, cache: dict, surface: np.ndarray | None = None) -> dict:
    ctx = HO57.build_holdout(grid, hide_frac=HIDE_FRAC, seeds=SEEDS, modes=("all",))
    pos, neg = [], []
    for cell in ctx.cells:
        bb = cell.bbox
        t = np.zeros(cell.active.shape, bool)
        t[cell.truth_yx] = True
        pos.append((bb, t, cell.active))
    feats = {k: cache[k] for k in ("step", "dksn", "ksn", "loga", "zmean", "step_min", "knick_n")
             if k in cache}
    if surface is not None:
        feats["lane_surface"] = surface.astype(np.float32)
    out = {}
    for name, arr in feats.items():
        aucs = []
        for bb, t, act in pos:
            a = arr[bb]
            sel = act | t
            a2 = np.where(np.isfinite(a), a, np.nan)
            m = sel & np.isfinite(a2)
            if t[m].sum() < 20 or (~t[m]).sum() < 20:
                continue
            aucs.append(auc(a2[m], t[m]))
        out[name] = dict(n_folds=len(aucs), mean_auc=float(np.mean(aucs)) if aucs else None,
                         max_abs_auc=float(np.max([max(x, 1 - x) for x in aucs])) if aucs else None,
                         verdict=("LEAKAGE-SUSPECT" if aucs and max(max(x, 1 - x) for x in aucs) > 0.90
                                  else "CLEAN"))
    return out


# ============================================================================================== #
# stage 6 -- the lane surface: strike-corroborated knickpoint corridors
# ============================================================================================== #
def corridor_offsets(half_len: int, half_width: int, strike_rad: float):
    u_row, u_col = -np.cos(strike_rad), np.sin(strike_rad)
    v_row, v_col = np.sin(strike_rad), np.cos(strike_rad)
    span = half_len + half_width + 1
    dy, dx = np.mgrid[-span:span + 1, -span:span + 1]
    pa = dy * u_row + dx * u_col
    pp = dy * v_row + dx * v_col
    keep = (np.abs(pa) <= half_len) & (np.abs(pp) <= half_width)
    return dy[keep].astype(np.int32), dx[keep].astype(np.int32)


def _decode_u8_band(path: Path, band: int, meta: dict) -> np.ndarray:
    """Decode one band of a committed uint8 pack with the pack's own documented rule."""
    with rasterio.open(path) as src:
        arr = src.read(band)
        nod = src.nodata
    if nod is not None:
        arr = np.where(arr == nod, 0, arr)
    q = arr.astype(np.float64)
    lo = meta["lo"]
    hi = meta["hi"]
    v = lo + (q - 1.0) / 254.0 * (hi - lo)
    return np.where(arr > 0, v, np.nan)


def _topo_band_meta(band: int) -> dict:
    man = json.loads((ROOT / "data" / "external" / "topo_10m_derived_100m_u8.manifest.json").read_text())
    for b in man["bands"]:
        if b["index"] == band:
            return b
    raise KeyError(band)


def drainage_labels(grid: Grid, cache: dict, cache_dir: Path) -> np.ndarray:
    """Independent first-order drainage (link) labels on the 100 m DEM.

    Two knickpoints in the SAME first-order basin are not independent evidence; the lane brief's
    "several independent drainages" is implemented literally as "several distinct first-order
    links".  Routing follows Barnes et al. (2014) priority flood -> O'Callaghan & Mark (1984) D8.
    """
    p = cache_dir / "basins.npy"
    if p.exists():
        return np.load(p)
    from gems60 import drains as D
    dem = _decode_u8_band(ROOT / "data" / "external" / "topo_10m_derived_100m_u8.tif", 9,
                          _topo_band_meta(9))
    valid = grid.footprint & np.isfinite(dem)
    log("stage6: filling depressions on the 100 m DEM")
    filled = D.fill_depressions(dem, valid)
    log("stage6: D8 receivers")
    rec = D.d8_receivers(filled)
    rec_flat = rec.ravel().astype(np.int64)
    fin = np.isfinite(filled)
    order_desc = np.argsort(-filled.ravel(), kind="stable")
    order_desc = order_desc[fin.ravel()[order_desc]]
    order_asc = order_desc[::-1].copy()
    log("stage6: flow accumulation")
    acc = D.accumulate_area(rec_flat, order_desc, 100.0 * 100.0)
    acc = acc.reshape(filled.shape)
    chan = D.channel_mask(acc, A_C_M2).ravel()
    log(f"stage6: channel cells (>= {A_C_M2:.0e} m2): {int(chan.sum())}")
    n_up = D.count_upstream_channels(rec_flat, chan.astype(np.bool_), order_asc)
    basin, _cells, _offs = D.first_order_basins(rec_flat, chan.astype(np.bool_), n_up, filled.shape[1])
    basin = basin.reshape(filled.shape)
    np.save(p, basin)
    log(f"stage6: {int(basin.max()) + 1} first-order drainage links")
    return basin


def lane_surface(grid: Grid, cache: dict, cache_dir: Path) -> np.ndarray:
    """Knickpoint strength kept only where >= N_DRAINAGE_MIN independent drainages agree on strike.

    Chain: blockwise z-score of the confound-masked relative steepness step -> candidates ->
    per-candidate strike corridor (orientation taken from the VISIBLE catalogue only) -> count
    DISTINCT first-order drainage links holding a candidate inside the corridor -> keep the
    candidates with at least ``N_DRAINAGE_MIN`` -> stamp the corridor at ``TRACE_DECAY``.
    """
    step = cache["step"]
    channel = cache["channel"]
    fp = grid.footprint
    cat = grid.catalogue
    H, W = step.shape

    z = np.zeros((H, W), dtype=np.float32)
    for y0 in range(0, H, BLOCK_PX):
        for x0 in range(0, W, BLOCK_PX):
            sl = (slice(y0, min(y0 + BLOCK_PX, H)), slice(x0, min(x0 + BLOCK_PX, W)))
            sel = channel[sl] & np.isfinite(step[sl])
            if sel.sum() < 50:
                continue
            v = step[sl]
            mu, sd = float(np.nanmean(v[sel])), float(np.nanstd(v[sel]))
            if sd <= 0:
                continue
            z[sl] = np.where(np.isfinite(v), (v - mu) / sd, 0.0)

    cand = channel & (z >= Z_MIN) & ~cat
    cy, cx = np.nonzero(cand)
    log(f"stage6: {cy.size} knickpoint candidates at z >= {Z_MIN}")

    basins = drainage_labels(grid, cache, cache_dir)

    from gems60 import lane as L
    strike, coh, _d = L.nearest_visible_strike(cat)
    regional = L.regional_modal_strike(strike, coh, cat)
    bins = L.strike_bins(strike, regional, coh)

    # per strike bin: stamp the union of corridors, then count distinct drainage links per pixel
    corr = np.zeros((H, W), dtype=np.float32)
    for b in range(L.N_STRIKE_BINS):
        sel = bins[cy, cx] == b
        if int(sel.sum()) < N_DRAINAGE_MIN:
            continue
        dy, dx = corridor_offsets(CORRIDOR_HALF_LEN_PX, CORRIDOR_HALF_WIDTH_PX,
                                  (b + 0.5) * np.pi / L.N_STRIKE_BINS)
        yy = cy[sel][:, None] + dy[None, :]
        xx = cx[sel][:, None] + dx[None, :]
        ok = (yy >= 0) & (xx >= 0) & (yy < H) & (xx < W)
        # for every candidate, the SET of drainage links whose candidates fall inside its corridor
        links = np.full((int(sel.sum()),), -1, dtype=np.int32)
        lid = np.full((H, W), -1, dtype=np.int32)
        lid[cy, cx] = np.arange(cy.size, dtype=np.int32)
        lab_here = basins[cy, cx]
        for i in range(yy.shape[0]):
            m = ok[i]
            ids = lid[yy[i][m], xx[i][m]]
            ids = ids[ids >= 0]
            if ids.size == 0:
                continue
            u = np.unique(lab_here[ids])
            u = u[u >= 0]
            links[i] = int(u.size)
        keep_i = np.flatnonzero(links >= N_DRAINAGE_MIN)
        if keep_i.size == 0:
            continue
        idx = np.flatnonzero(sel)[keep_i]
        # stamp each corroborated corridor once
        stamp = np.zeros((H, W), np.float32)
        ky, kx = cy[idx], cx[idx]
        wgt = np.maximum(z[ky, kx], 0.0).astype(np.float32)
        yy2 = ky[:, None] + dy[None, :]
        xx2 = kx[:, None] + dx[None, :]
        ok2 = (yy2 >= 0) & (xx2 >= 0) & (yy2 < H) & (xx2 < W)
        np.maximum.at(stamp, (np.where(ok2, yy2, 0), np.where(ok2, xx2, 0)),
                      np.where(ok2, wgt[:, None] * np.float32(1.0), np.float32(0.0)))
        corr = np.maximum(corr, stamp)
        log(f"stage6: strike bin {b}: {int(sel.sum())} candidates, {int(keep_i.size)} corroborated "
            f"by >= {N_DRAINAGE_MIN} independent drainages")

    surf = np.where(fp & ~cat, np.maximum(corr, 0.0) * TRACE_DECAY, 0.0).astype(np.float32)
    log(f"stage6: surface support {int((surf > 0).sum())} px")
    return surf


# ============================================================================================== #
# stage 8 -- emission
# ============================================================================================== #
def nms_dots(surface: np.ndarray, footprint: np.ndarray, spacing: float = NMS_PX,
             k: int | None = None) -> np.ndarray:
    """Greedy non-maximum suppression at ``spacing`` px.  ``spacing <= 0`` keeps the whole support."""
    s = np.where(footprint, surface, -np.inf).astype(np.float32)
    out = np.zeros(s.shape, bool)
    if spacing <= 0:
        out[s > 0] = True
        if k is not None:
            ys, xs = np.nonzero(out)
            if ys.size > k:
                v = s[ys, xs]
                keep = np.argsort(-v)[:k]
                out[:] = False
                out[ys[keep], xs[keep]] = True
        return out
    taken = np.zeros(s.shape, bool)
    k = k if k is not None else s.size
    order = np.argsort(-s.ravel(), kind="stable")
    ys, xs = np.unravel_index(order, s.shape)
    cell = max(1, int(np.ceil(spacing)))
    H, W = s.shape
    gh, gw = H // cell + 1, W // cell + 1
    grid_used = np.zeros((gh, gw), bool)
    n = 0
    for y, x in zip(ys.tolist(), xs.tolist()):
        if n >= k:
            break
        if s[y, x] <= 0:
            break
        if taken[y, x]:
            continue
        # reject if within `spacing` of an already-taken dot (brute force on the small grid)
        y0, x0 = max(0, y - cell), max(0, x - cell)
        y1, x1 = min(H, y + cell + 1), min(W, x + cell + 1)
        yy, xx = np.nonzero(out[y0:y1, x0:x1])
        if yy.size:
            yy = yy + y0
            xx = xx + x0
            if np.min((yy - y) ** 2 + (xx - x) ** 2) < spacing ** 2:
                continue
        out[y, x] = True
        n += 1
    return out


# ============================================================================================== #
# stage 9 -- uniqueness
# ============================================================================================== #
def _disc3() -> np.ndarray:
    """7x7 boolean structuring element: every lattice offset with |offset| <= 3 px (300 m)."""
    st = np.zeros((7, 7), bool)
    for dy, dx, _k in M.OFFSETS:
        st[dy + 3, dx + 3] = True
    return st


DISC3 = _disc3()


def _dilate3(mask: np.ndarray) -> np.ndarray:
    """3-px (300 m) disc dilation.  Zero-padded, never wrapped, so the grid edge cannot
    manufacture proximity across the raster."""
    return ndi.binary_dilation(np.asarray(mask, bool), structure=DISC3)


def uniqueness(pred: np.ndarray, footprint: np.ndarray, limit_overlap: float = 0.70,
               limit_rho: float = 0.90) -> dict:
    """The literal parallel-run uniqueness rule, in BOTH directions.

    The rule reads: "more than [70%] of your dots fall within 3 px of one registry raster's dots".
    The governed quantity is therefore the fraction of OUR dots lying within 3 px of a registry
    raster's positive pixels (``mine_within_3px``).  The reverse fraction is reported as a
    diagnostic only -- an earlier version of this function reported only the reverse number and
    therefore understated the overlap, which is fixed here.
    """
    from scipy import stats
    paths = sorted((ROOT / "registry" / "rasters").glob("*.tif"))
    paths += sorted((ROOT / "docs" / "downloads").glob("*.tif"))
    ys, xs = np.nonzero(pred)
    n_mine = int(ys.size)
    H, W = pred.shape
    worst = dict(overlap=0.0, path=None, rho=0.0)
    rows = []
    for pth in paths:
        try:
            with rasterio.open(pth) as src:
                if (src.height, src.width) != (H, W):
                    continue
                a = src.read(1).astype(np.float64)
        except Exception:
            continue
        a[~np.isfinite(a)] = 0.0
        b = np.where(footprint, a, 0.0)
        if b.max() > 1.0 or b.min() < 0.0:
            continue
        reg = b > 0
        if not reg.any():
            continue
        # rule direction: fraction of OUR dots within 3 px of a registry dot
        mine_within = float(_dilate3(reg)[ys, xs].mean()) if n_mine else 0.0
        # diagnostic reverse direction
        reg_within = float(reg[_dilate3(pred > 0)].mean())
        rng = np.random.default_rng(0)
        idx = np.flatnonzero(footprint.ravel())
        if idx.size > 200_000:
            idx = rng.choice(idx, 200_000, replace=False)
        u = pred.ravel()[idx]
        v = b.ravel()[idx]
        rho = 0.0 if (np.std(u) == 0 or np.std(v) == 0) else float(stats.spearmanr(u, v).statistic)
        rows.append(dict(path=str(pth.relative_to(ROOT)), mine_within_3px=mine_within,
                         registry_within_3px=reg_within, spearman=rho,
                         registry_support_frac_of_footprint=float(reg.sum() / max(int(footprint.sum()), 1)),
                         registry_dots=int(reg.sum())))
        if mine_within > worst["overlap"]:
            worst["overlap"] = mine_within
            worst["path"] = str(pth.relative_to(ROOT))
        if abs(rho) > abs(worst["rho"]):
            worst["rho"] = rho
    rows.sort(key=lambda r: -r["mine_within_3px"])
    return dict(checked=len(rows), our_dots=int(n_mine),
                max_our_dots_within_3px_of_registry=worst["overlap"],
                worst_path=worst["path"],
                max_abs_spearman=abs(worst["rho"]),
                limits=dict(dot_overlap=limit_overlap, abs_spearman=limit_rho),
                verdict=("PASS" if worst["overlap"] <= limit_overlap and abs(worst["rho"]) <= limit_rho
                         else "FAIL"),
                top_rows=rows[:25])


# ============================================================================================== #
# stage 10 -- write the GeoTIFF and validate it literally
# ============================================================================================== #
STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
SUBMISSION_NAME = "60GEMSDOE-H73-1-chi-knick-corridor"
NOTE = ("H73-1 chi/ksn knickpoint corridors, >=3 independent drainages; first test NULL; "
        "RESEARCH ONLY - DO NOT SUBMIT")


def write_tiff(pred: np.ndarray, grid: Grid, out_dir: Path, n_dots: int) -> dict:
    import zipfile
    out_dir.mkdir(parents=True, exist_ok=True)
    p = np.asarray(pred, dtype=np.float32)
    assert p.shape == (grid.height, grid.width)
    assert np.isfinite(p).all(), "the zeros container must be all-finite"
    assert (p >= 0).all() and (p <= 1).all(), "values must already be in [0,1]"

    zeros = np.where(grid.footprint, p, 0.0).astype(np.float32)
    nanv = np.where(grid.footprint, p, np.nan).astype(np.float32)

    h8 = hashlib.sha256(zeros.tobytes()).hexdigest()[:8]
    base = f"gems60-h73-chi-knick-corridor-{n_dots}px-{STAMP}-{h8}"
    zpath = out_dir / f"{base}-zeros.tif"
    npath = out_dir / f"{base}-nan.tif"

    profile = dict(driver="GTiff", height=grid.height, width=grid.width, count=1,
                   dtype="float32", crs="EPSG:32611",
                   transform=rasterio.transform.Affine(100.0, 0.0, 243350.0,
                                                       0.0, -100.0, 4508550.0),
                   compress="deflate", predictor=2)
    for path, arr, nod in ((zpath, zeros, None), (npath, nanv, float("nan"))):
        prof = dict(profile)
        if nod is not None:
            prof["nodata"] = nod
        with rasterio.open(path, "w", **prof) as dst:
            dst.write(arr, 1)

    zipp = out_dir / f"{base}-zeros.zip"
    with zipfile.ZipFile(zipp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(zpath, arcname=zpath.name)

    def audit(path: Path) -> dict:
        with rasterio.open(path) as src:
            a = src.read(1)
            inside = grid.footprint
            problems = []
            if src.count != 1:
                problems.append("not single band")
            if src.dtypes[0] != "float32":
                problems.append(f"dtype {src.dtypes[0]} != float32")
            if (src.height, src.width) != (3730, 3292):
                problems.append("shape mismatch")
            if str(src.crs) != "EPSG:32611":
                problems.append(f"crs {src.crs}")
            if tuple(src.transform)[:6] != (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0):
                problems.append("transform mismatch")
            fin = np.isfinite(a)
            if not fin[inside].all():
                problems.append(f"{int((~fin & inside).sum())} non-finite cells inside the footprint")
            if (a[fin] < 0).any() or (a[fin] > 1).any():
                problems.append("values outside [0,1]")
            if (a[~inside] != 0).all() and np.isfinite(a[~inside]).any() and path.name.endswith("zeros.tif"):
                problems.append("non-zero outside the footprint in the zeros container")
            return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                        sha256=sha256(path), bands=src.count, dtype=src.dtypes[0],
                        shape=[src.height, src.width], crs=str(src.crs),
                        transform=list(src.transform)[:6], nodata=src.nodata,
                        positive_px=int((a > 0).sum()),
                        mass=float(np.nansum(a)),
                        min=float(np.nanmin(a[fin])) if fin.any() else None,
                        max=float(np.nanmax(a[fin])) if fin.any() else None,
                        nan_inside_footprint=int((~fin & inside).sum()),
                        problems=problems)

    rec = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               hypothesis="H73-1", submission_name=SUBMISSION_NAME, note=NOTE,
               note_chars=len(NOTE),
               primary=audit(zpath), variant_nan_outside=audit(npath),
               zip=dict(path=str(zipp.relative_to(ROOT)), bytes=zipp.stat().st_size,
                        sha256=sha256(zipp),
                        members=[n for n in zipfile.ZipFile(zipp).namelist()]))
    write_json(out_dir / f"checks-{base}-zeros.tif.json", rec)
    return rec


# ============================================================================================== #
# main
# ============================================================================================== #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", default="all",
                    choices=("prereg", "inputs", "cache", "e1", "e1b", "canary", "surface",
                             "holdout", "emit", "all"))
    ap.add_argument("--cache", default=str(ROOT / ".cache" / "features73"))
    args = ap.parse_args()
    cache_dir = Path(args.cache)

    pre = stage0_preregistration()
    if args.stage == "prereg":
        return 0
    grid = stage1_inputs()
    if args.stage == "inputs":
        return 0

    if args.stage in ("cache", "all"):
        stage2_cache(grid, cache_dir)
    if args.stage == "cache":
        return 0
    cache = load_cache(cache_dir)

    if args.stage in ("e1", "all"):
        arms = {}
        for field, role in (("step", "primary"), ("step_abs", "secondary")):
            res = run_first_test(grid, cache, hide_frac=HIDE_FRAC, seeds=SEEDS,
                                 n_transects=N_TRANSECTS, tag=f"E1/{field}", field=field)
            summ = paired_bootstrap(res["rows"])
            arms[field] = dict(role=role, summary=summ, components=len(res["rows"]),
                               skipped=sum(1 for r in res["rows"] if "paired_difference" not in r))
            log(f"E1/{field} ({role}): {summ['verdict']} mean={summ['mean']:.4f} "
                f"ci95={summ['ci95']} n={summ['n_components']}")
        res = {f: None for f in arms}
        # keep the primary rows for the audit table; the secondary rows are summarised only
        res_primary = run_first_test(grid, cache, hide_frac=HIDE_FRAC, seeds=SEEDS,
                                     n_transects=N_TRANSECTS, tag="E1", field="step")
        gate = arms["step"]["summary"]["verdict"]
        rec = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   hypothesis="H73-1", preregistration="registry/preregistration-h73.json",
                   evidence_class="MEASUREMENT",
                   primary_statistic="relative_step (step_max/1000), block-centred, confound-masked",
                   secondary_statistic="dksn_signed, block-centred, confound-masked",
                   design=dict(hide_frac=HIDE_FRAC, seeds=list(SEEDS),
                               n_control_transects=N_TRANSECTS, min_ctrl=MIN_CTRL,
                               n_cells=arms["step"]["components"]),
                   arms=arms, gate_G1_verdict=gate,
                   rows=res_primary["rows"])
        write_json(ROOT / "evidence" / "h73_e1_first_test.json", rec)
        log(f"E1 gate: {gate}")
    if args.stage == "e1":
        return 0

    if args.stage in ("e1b", "all"):
        with rasterio.open(ROOT / "data" / "external" / "derived_sgmc_faults_100m.tif") as src:
            sgmc = src.read(1) > 0
        dist = ndi.distance_transform_edt(~grid.catalogue, sampling=100.0)
        pop = sgmc & grid.footprint & (dist >= 300.0)
        log(f"E1b: off-catalogue population {int(pop.sum())} px")
        res = run_first_test(grid, cache, hide_frac=HIDE_FRAC, seeds=SEEDS,
                             n_transects=N_TRANSECTS, truth_population=pop, tag="E1b",
                             field="step")
        summ = paired_bootstrap(res["rows"])
        rec = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   hypothesis="H73-1", evidence_class="MEASUREMENT", gating=False,
                   population="SGMC faults >= 300 m from the catalogue",
                   population_px=int(pop.sum()), summary=summ, rows=res["rows"])
        write_json(ROOT / "evidence" / "h73_e1b_offcatalogue.json", rec)
        log(f"E1b: {summ['verdict']} mean={summ['mean']:.4f} ci95={summ['ci95']} n={summ['n_components']}")
    if args.stage == "e1b":
        return 0

    if args.stage in ("surface", "canary", "holdout", "emit", "all"):
        surf_p = cache_dir / "surface.npy"
        if surf_p.exists():
            surf = np.load(surf_p)
        else:
            surf = lane_surface(grid, cache, cache_dir)
            np.save(surf_p, surf)
        log(f"stage6: surface {int((surf > 0).sum())} support px")
    if args.stage == "surface":
        return 0

    if args.stage in ("canary", "all"):
        rec = leakage_canary(grid, cache, surf)
        write_json(ROOT / "evidence" / "h73_leakage_canary.json", rec)
        log("stage5 canary: " + ", ".join(f"{k}={v['max_abs_auc']:.3f}" for k, v in rec.items()))
    if args.stage == "canary":
        return 0

    if args.stage in ("holdout", "emit", "all"):
        ctx = HO57.build_holdout(grid, hide_frac=HIDE_FRAC, seeds=SEEDS, modes=("all",))
        # a mass-matched random control inside the same active domains
        ladders = {}
        rng = np.random.default_rng(7)
        for sp in SPACINGS:
            dots = nms_dots(surf, grid.footprint & ~grid.catalogue, sp)
            ev = HO57.evaluate(dots, ctx)
            n = int(dots.sum())
            rand = np.zeros(grid.shape, bool)
            pool = np.flatnonzero((grid.footprint & ~grid.catalogue).ravel())
            pick = rng.choice(pool, size=min(n, pool.size), replace=False)
            rand.ravel()[pick] = True
            evr = HO57.evaluate(rand, ctx)
            ladders[str(sp)] = dict(spacing_px=sp, dots=n, pooled_dti=ev["pooled_dti"],
                                    coverage=ev["pooled_coverage"], tp=ev["pooled_tp"],
                                    fp=ev["pooled_fp"], fn=ev["pooled_fn"],
                                    n_truth=ev["pooled_n_truth"],
                                    random_mass_control_dti=evr["pooled_dti"])
            log(f"  spacing {sp}: dots={n} pooled_dti={ev['pooled_dti']:.6f} "
                f"random_control={evr['pooled_dti']:.6f}")
        write_json(ROOT / "evidence" / "h73_holdout.json",
                   dict(hypothesis="H73-1", evaluator="gems57-pooled-hide-v2",
                        hide_frac=HIDE_FRAC, seeds=list(SEEDS), ladder=ladders))
    if args.stage == "holdout":
        return 0

    if args.stage in ("emit", "all"):
        dots = nms_dots(surf, grid.footprint & ~grid.catalogue, PRIMARY_SPACING)
        pred = np.zeros(grid.shape, dtype=np.float32)
        pred[dots] = 1.0
        write_json(ROOT / "evidence" / "h73_emission.json",
                   dict(dots=int(dots.sum()), spacing_px=PRIMARY_SPACING,
                        support_px=int((surf > 0).sum()),
                        on_catalogue=int((dots & grid.catalogue).sum()),
                        outside_footprint=int((dots & ~grid.footprint).sum())))
        np.save(cache_dir / "prediction.npy", pred)
        uni = uniqueness(pred, grid.footprint)
        write_json(ROOT / "evidence" / "h73_uniqueness.json", uni)
        log(f"stage9: uniqueness {uni['verdict']} overlap={uni['max_our_dots_within_3px_of_registry']:.4f} "
            f"|rho|max={uni['max_abs_spearman']:.4f}")
        rec = write_tiff(pred, grid, ROOT / "docs" / "downloads", int(dots.sum()))
        write_json(ROOT / "evidence" / "h73_tiff.json", rec)
        log(f"stage10: wrote {rec['primary']['path']} problems={rec['primary']['problems']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
