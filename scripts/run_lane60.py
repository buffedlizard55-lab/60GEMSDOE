#!/usr/bin/env python3
"""Stage B: the three budgeted experiments of the H60-A tectonic-geomorphology lane.

E1 (mandated first test)  do channels crossing withheld segments show larger
                          steepness steps than random lines of the same
                          orientation?  If not: STOP.
E2 (leakage canary)       each feature alone, AUC vs withheld truth.
E3 (holdout DTI)          pooled DTI of the lane emission against three controls,
                          with the shared evaluator and a paired spatial-block
                          bootstrap CI.

Shared tools are reused unmodified: ``gems57.grid``, ``gems57.holdout``,
``gems57.evaluate_holdout``, ``gems57.metric``, ``gems57.emit``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems57 import evaluate_holdout as EH        # noqa: E402
from gems57 import grid as G57                   # noqa: E402
from gems57 import holdout as HO                 # noqa: E402
from gems57 import metric as M                   # noqa: E402
from gems60 import geomorph as gm                # noqa: E402
from gems60 import lane as L                     # noqa: E402

CACHE = ROOT / ".cache" / os.environ.get("GEMS60_FEATURE_CACHE", "features60")
# Substrate-agnostic driver (shared-tool change 2026-10-11, session arena/96ecd67e, H65-1):
# GEMS60_FEATURE_CACHE selects the feature cache (default: the 100 m det_elev cache of H60-A;
# H65-1 points it at the native-3DEP-10 m reduction) and GEMS60_TAG prefixes every evidence
# file, so a new substrate never overwrites the H60-A record.  Defaults reproduce H60-A exactly.
TAG = os.environ.get("GEMS60_TAG", "h60a")
EVID = ROOT / "evidence"
DENSITY = 40_000 / 5_106_385          # declared production budget / allowed cells
BOOT_DRAWS = 1000
BOOT_SEED = 60101
TRANSECTS_PER_COMPONENT = 10
MIN_COMPONENT_PX = 6


def load(name):
    return np.load(CACHE / f"{name}.npy")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def auc(score, truth, domain) -> float:
    sel = np.asarray(domain, bool)
    s = np.asarray(score, np.float64)[sel]
    t = np.asarray(truth, bool)[sel]
    n_pos = int(t.sum())
    n_neg = int(t.size - n_pos)
    if n_pos == 0 or n_neg == 0 or not np.isfinite(s).any():
        return float("nan")
    s = np.where(np.isfinite(s), s, np.nanmin(s[np.isfinite(s)]) if np.isfinite(s).any() else 0.0)
    r = rankdata(s, method="average")
    return float((r[t].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def load_meta() -> dict:
    p = CACHE / "meta.json"
    if p.is_file():
        return json.loads(p.read_text())
    return {}


STEP_STATISTIC = os.environ.get("GEMS60_STEP_STATISTIC", "upstream").lower()


def load_step() -> np.ndarray:
    """The lane's steepness-step statistic, selected once for every consumer."""
    s = load("step").astype(np.float64)
    if STEP_STATISTIC == "upstream":
        return s
    if STEP_STATISTIC == "abs":
        sm = load("step_min").astype(np.float64)
        both = np.isfinite(s) & np.isfinite(sm)
        return np.where(both, np.maximum(s, -sm), np.nan)
    raise SystemExit(f"GEMS60_STEP_STATISTIC must be 'upstream' or 'abs', got {STEP_STATISTIC!r}")


TRAINING_FEATURES = ROOT / "data/official/training_features.tif"
GEODAWN_RAD = ROOT / "data/external/geodawn_rad_u8.tif"


def confound_masks(step, channel, acc=None, a_min_m2=1e6) -> tuple[np.ndarray, dict]:
    """Declared lithology / base-level / ephemeral-wash confound masks.

    Two paths, chosen by what the machine actually has; the choice is recorded in
    the diagnostics so no receipt is ambiguous about which mask was used.

    * **Preferred (H60-A / H65-1 defaults):** ``training_features.tif`` band 15
      (``depth_to_base_surf``) above its 90th footprint percentile = thick cover,
      and band 17 (``cond_surf``) above its 95th = clay-rich / evaporitic.
      Reproduces H60-A and H65-1 byte-for-byte whenever that raster is present.
    * **Substitute (shared-tool fix, 2026-10-11, session arena/970443fc):** the
      419 MB feature stack cannot live in git (GitHub 100 MB blob limit) and is
      absent from an egress-restricted sandbox.  Failing closed here made the
      whole lane unrunnable, so the pinned GeoDAWN airborne-radiometric pack
      supplies the lithology mask instead: K (band 1) or Th (band 2) above the
      95th footprint percentile = clay-rich / alluvial cover.  Radiometric K and
      Th are the standard lithologic discriminators for exactly this survey
      (https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and).
      Recorded as irregularity IR-66-DATA-01; ``lithology_source`` names the path used.

    Ephemeral/litho terms: the H67 cache may carry precomputed
    ``ephemeral_wash.npy`` / ``litho_core.npy`` arrays (applied when present,
    session arena/7085de4f); the H66-6 ``acc`` parameter (session
    arena/b219bfe1) computes the ephemeral-channel mask from the 10 m drainage
    area band (``acc`` < ``a_min_m2`` cells, default 1e6 m2 = 1 km2) when the
    cache lacks the precomputed arrays.  ``acc=None`` plus absent arrays
    reproduces H60-A/H65 exactly.
    """
    playa = load("playa")
    fp = load("footprint")
    if TRAINING_FEATURES.is_file():
        with rasterio.open(TRAINING_FEATURES) as src:
            depth = src.read(15).astype(np.float32).astype(np.float64)
            cond = src.read(17).astype(np.float32).astype(np.float64)
        depth[~np.isfinite(depth) | (np.abs(depth) > 1e30)] = np.nan
        cond[~np.isfinite(cond) | (np.abs(cond) > 1e30)] = np.nan
        d_thr = float(np.nanpercentile(depth[fp], 90))
        c_thr = float(np.nanpercentile(cond[fp], 95))
        basin_fill = fp & np.isfinite(depth) & (depth > d_thr)
        conductive = fp & np.isfinite(cond) & (cond > c_thr)
        source = "training_features.tif band15 p90 + band17 p95"
        extra = dict(depth_to_base_p90_m=d_thr, cond_surf_p95=c_thr)
    elif GEODAWN_RAD.is_file():
        with rasterio.open(GEODAWN_RAD) as src:
            k = src.read(1).astype(np.float64)
            th = src.read(2).astype(np.float64)
        k = np.where(k > 0, k, np.nan)      # 0 is the pack's nodata code
        th = np.where(th > 0, th, np.nan)
        k_thr = float(np.nanpercentile(k[fp], 95))
        th_thr = float(np.nanpercentile(th[fp], 95))
        conductive = fp & np.isfinite(k) & (k > k_thr)
        basin_fill = fp & np.isfinite(th) & (th > th_thr)
        source = ("SUBSTITUTE geodawn_rad_u8.tif K p95 + Th p95 "
                  "(training_features.tif absent; IR-66-DATA-01)")
        extra = dict(rad_K_p95=k_thr, rad_Th_p95=th_thr)
    else:
        raise SystemExit("confound masks unavailable: neither "
                         f"{TRAINING_FEATURES.name} nor {GEODAWN_RAD.name} is present")
    exclude = playa | basin_fill | conductive
    diag = dict(playa_px=int(playa.sum()), basin_fill_px=int(basin_fill.sum()),
                conductive_px=int(conductive.sum()), lithology_source=source)
    if (CACHE / "ephemeral_wash.npy").is_file():
        eph = load("ephemeral_wash").astype(bool)
        exclude = exclude | eph
        diag["ephemeral_wash_px"] = int(eph.sum())
    if (CACHE / "litho_core.npy").is_file():
        lith = load("litho_core").astype(bool)
        exclude = exclude | lith
        diag["litho_core_px"] = int(lith.sum())
    diag.update(excluded_px=int(exclude.sum()),
                channel_excluded_px=int((channel & exclude).sum()),
                channel_px=int(channel.sum()), **extra)
    # H66-6 shared-tool extension (2026-10-11, session arena/b219bfe1): the lane
    # brief's confound list also includes *ephemeral channels*.  When the substrate
    # cache carries a drainage-area band (``acc``, in 100 m cells), channel cells
    # with 10 m drainage area below ``a_min_m2`` (default 1e6 m2 = 1 km2, the
    # standard bedrock-channel threshold) are added to the exclusion.
    # ``acc=None`` (the default) reproduces H60-A/H65 exactly, so this change is
    # strictly additive.
    if acc is not None:
        acc = np.asarray(acc, np.float64)
        a_min_cells = a_min_m2 / 1e4          # the cache stores area in 100 m cells
        ephemeral = channel & (acc < a_min_cells)
        exclude = exclude | ephemeral
        diag.update(ephemeral_px=int(ephemeral.sum()), a_min_m2=float(a_min_m2),
                    excluded_px=int(exclude.sum()),
                    channel_excluded_px=int((channel & exclude).sum()))
    return exclude, diag


def litho_step_mask(footprint, win=15, pct=90) -> tuple[np.ndarray, float]:
    """H66-6: cells sitting on a step in the basement surface (band 15).

    ``|depth_to_base_surf - median_win(depth_to_base_surf)| > p{pct}`` of that
    residual over the footprint's finite cells.  A fault that offsets the basement
    and a lithologic contact both produce this; it is the *named lithologic
    mimic*'s signature and is therefore a test input, never a positive term.
    """
    if not TRAINING_FEATURES.is_file():
        raise SystemExit("litho_step_mask needs training_features.tif band 15 (depth_to_base_surf); "
                         "the GeoDAWN substitute path carries no basement-depth band")
    with rasterio.open(TRAINING_FEATURES) as src:
        depth = src.read(15).astype(np.float32).astype(np.float64)
    depth[~np.isfinite(depth) | (np.abs(depth) > 1e30)] = np.nan
    med = ndi.median_filter(depth, size=win, mode="nearest")
    res = np.abs(depth - med)
    valid = np.asarray(footprint, bool) & np.isfinite(res)
    thr = float(np.nanpercentile(res[valid], pct))
    return np.asarray(footprint, bool) & np.isfinite(depth) & (res > thr), thr


# --------------------------------------------------------------------------- #
# E1
# --------------------------------------------------------------------------- #
def component_orientation(yx) -> tuple[float, float]:
    """Principal-axis azimuth (rad, mod pi) and length (px) of a component."""
    y, x = yx
    if y.size < 2:
        return 0.0, 1.0
    p = np.stack([y - y.mean(), x - x.mean()], 1).astype(np.float64)
    cov = p.T @ p / max(p.shape[0] - 1, 1)
    w, v = np.linalg.eigh(cov)
    axis = v[:, int(np.argmax(w))]           # (row, col) direction
    az = float(np.arctan2(axis[1], -axis[0]))  # geographic azimuth from north
    length = float(4.0 * np.sqrt(max(w.max(), 0.0)))
    return az % np.pi, max(length, 2.0)


def _dilate_window(shape, ys, xs, buffer_px):
    """Dilate a sparse line inside a local window; return the window and the mask.

    Returning a full-crop boolean array per draw (3 M cells) was the third silent
    cost in the mandated first test; callers now slice their own arrays with the
    returned window.
    """
    H, W = shape
    y0 = max(int(ys.min()) - buffer_px - 1, 0)
    y1 = min(int(ys.max()) + buffer_px + 2, H)
    x0 = max(int(xs.min()) - buffer_px - 1, 0)
    x1 = min(int(xs.max()) + buffer_px + 2, W)
    sub = np.zeros((y1 - y0, x1 - x0), bool)
    sub[ys - y0, xs - x0] = True
    sub = ndi.binary_dilation(sub, iterations=buffer_px)
    return (slice(y0, y1), slice(x0, x1)), sub


def transect_stat(y0, x0, az, length, step, channel, active, pool, shape,
                  buffer_px=3, min_channel_px=3, max_tries=25, rng=None):
    """Mean knickpoint step within ``buffer_px`` of a line segment, or None.

    The dilation is done in a local window: a full-crop dilation per draw made
    the mandated first test two orders of magnitude slower than the science
    needs and was the single largest cost in the session (fixed here, once, in
    the shared lane driver rather than in a private fork).
    """
    H, W = shape
    u = np.array([-np.cos(az), np.sin(az)])
    for _ in range(max_tries):
        yy = np.clip(np.round(y0 + u[0] * np.arange(length)).astype(int), 0, H - 1)
        xx = np.clip(np.round(x0 + u[1] * np.arange(length)).astype(int), 0, W - 1)
        inside = active[yy, xx]
        if inside.mean() < 0.6:
            if rng is None:
                return None
            y0, x0 = _random_point(pool, rng)
            if y0 is None:
                return None
            continue
        win, sub = _dilate_window(shape, yy, xx, buffer_px)
        zone = sub & channel[win] & active[win]
        if int(zone.sum()) < min_channel_px:
            if rng is None:
                return None
            y0, x0 = _random_point(pool, rng)
            if y0 is None:
                return None
            continue
        vals = step[win][zone]
        vals = vals[np.isfinite(vals)]
        if vals.size < min_channel_px:
            return None
        return float(vals.mean()), int(zone.sum()), float(y0), float(x0)
    return None


def _random_point(pool, rng):
    """Draw one transect start from a per-cell precomputed pool.

    ``np.nonzero`` over a 3 M-cell crop per draw was the second silent cost in the
    mandated first test (the pool is now built once per cell).
    """
    ys, xs = pool
    if ys.size == 0:
        return None, None
    i = int(rng.integers(ys.size))
    return float(ys[i]), float(xs[i])


MAX_COMPONENTS_PER_CELL = 900


def run_e1(ctx, step, channel, active_by_cell, truth_by_cell, visible_by_cell,
           modes=("all",), n_transects=TRANSECTS_PER_COMPONENT,
           max_components=MAX_COMPONENTS_PER_CELL, exclude=None, channel_eff=None):
    """Mandated first test.

    H66-6 shared-tool extension (2026-10-11, session arena/b219bfe1): ``exclude``
    (the lane brief's confound masks) and ``channel_eff`` (a further channel
    restriction, e.g. the H66-6 litho arms) are optional.  When given, they are
    applied to BOTH the observed crossing zone and the random same-orientation
    control transects (zones and start pool), so the comparison stays matched on
    the same masked domain.  With both ``None`` the function is byte-identical to
    the H60-A/H65 behaviour.
    """
    exl = np.asarray(exclude, bool) if exclude is not None else None
    chan = channel_eff if channel_eff is not None else channel
    rows = []
    rng = np.random.default_rng(6001)
    for cell in ctx.cells:
        if cell.mode not in modes:
            continue
        bb = cell.bbox
        truth = truth_by_cell[cell.key][bb]
        active = cell.active
        step_c = step[bb]
        chan_c = chan[bb]
        forbidden = ndi.binary_dilation(truth | visible_by_cell[cell.key][bb], iterations=10)
        pool_mask = active & ~forbidden
        if exl is not None:
            pool_mask = pool_mask & ~exl[bb]
        pool = np.nonzero(pool_mask)
        if pool[0].size > 200_000:
            pick = rng.choice(pool[0].size, 200_000, replace=False)
            pool = (pool[0][pick], pool[1][pick])
        lab, n = ndi.label(truth)
        objs = ndi.find_objects(lab)
        cids = np.arange(1, n + 1)
        if cids.size > max_components:
            cids = np.sort(rng.choice(cids, max_components, replace=False))
        for cid in cids:
            sl = objs[int(cid) - 1]
            if sl is None:
                continue
            sub_y, sub_x = np.nonzero(lab[sl] == cid)
            ys = sub_y + sl[0].start
            xs = sub_x + sl[1].start
            if ys.size < MIN_COMPONENT_PX:
                continue
            az, length = component_orientation((ys, xs))
            length = int(np.clip(round(length), MIN_COMPONENT_PX, 60))
            win, sub = _dilate_window(step_c.shape, ys, xs, 3)
            zone = sub & chan_c[win] & active[win]
            vals = step_c[win][zone]
            vals = vals[np.isfinite(vals)]
            if vals.size < 3:
                rows.append(dict(cell=cell.key, component=int(cid), n_px=int(ys.size),
                                 crossing_channel_px=int(zone.sum()), skipped="no channel crossing"))
                continue
            obs = float(vals.mean())
            ctr = []
            for _ in range(n_transects):
                y0, x0 = _random_point(pool, rng)
                if y0 is None:
                    break
                got = transect_stat(y0, x0, az, length, step_c, chan_c, active,
                                    pool, step_c.shape, rng=rng)
                if got is not None:
                    ctr.append(got[0])
            if len(ctr) < 5:
                rows.append(dict(cell=cell.key, component=int(cid), n_px=int(ys.size),
                                 crossing_channel_px=int(zone.sum()),
                                 observed_mean_step=obs, skipped=f"only {len(ctr)} valid transects"))
                continue
            rows.append(dict(cell=cell.key, component=int(cid), n_px=int(ys.size),
                             azimuth_deg=float(np.rad2deg(az)), length_px=length,
                             crossing_channel_px=int(zone.sum()),
                             observed_mean_step=obs,
                             control_mean_step=float(np.mean(ctr)),
                             control_std_step=float(np.std(ctr)),
                             n_control_transects=len(ctr),
                             paired_difference=obs - float(np.mean(ctr))))
    return rows


def paired_bootstrap(rows, draws=BOOT_DRAWS, seed=BOOT_SEED):
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
                bootstrap=dict(draws=draws, seed=seed, method="percentile over withheld components"),
                verdict=verdict)


# --------------------------------------------------------------------------- #
# E3
# --------------------------------------------------------------------------- #
def cell_fold(cell, truth_crop):
    zeros = np.zeros_like(cell.active)
    return dict(region=cell.active, visible=zeros, truth=truth_crop)


def run(args) -> int:
    t0 = time.time()
    log: list[str] = []

    def mark(msg):
        line = f"[B] {msg} ({time.time() - t0:.1f}s)"
        print(line, flush=True)
        log.append(line)

    grid = G57.load_grid()
    mark(f"grid {grid.height}x{grid.width} footprint={int(grid.footprint.sum())} "
         f"catalogue={int(grid.catalogue.sum())}")
    ctx = HO.build_holdout(grid, modes=("all",))
    mark(f"holdout cells={len(ctx.cells)}")

    step = load_step()
    channel = load("channel")
    if (CACHE / "branch_sig.npy").is_file():
        # substrate supplies its own branch signature (H65-1: the 10 m network's cell 500 m
        # downstream, expressed as a global 100 m index) -- same independence definition
        terminal = load("branch_sig").astype(np.int64)
    else:
        terminal = gm.branch_signature(load("dircode"), load("footprint"),
                                       k=L.CORRIDOR_HALF_LEN_PX - 1).astype(np.int64)
    mark("independence=substrate branch_sig" if (CACHE / "branch_sig.npy").is_file() else
         f"independence=branch_signature(k={L.CORRIDOR_HALF_LEN_PX - 1})")
    ksn = load("ksn").astype(np.float64)
    # chi is only a canary row; a substrate without a comparable chi datum (H65-1: chi is
    # block-local on the 10 m runner) omits it rather than faking one
    chi = load("chi").astype(np.float64) if (CACHE / "chi.npy").is_file() else None
    acc = load("acc").astype(np.float64)
    exclude, conf_diag = confound_masks(step, channel,
                                        acc=acc if getattr(args, "include_ephemeral", False) else None)
    mark(f"confounds {conf_diag}")
    meta_cfg = load_meta()
    z_min = float(meta_cfg.get("z_min", L.Z_MIN))
    min_sep_px = float(meta_cfg.get("min_sep_px", 0.0))
    inc_pos_ch = bool(meta_cfg.get("include_positive_channels", False))
    surf_kw = L.surface_kwargs_from_meta(meta_cfg, CACHE, exclude=exclude)

    z, cand, cand_diag = L.prepare_candidates(step, channel, exclude,
                                              block_px=L.BLOCK_PX, z_min=z_min)
    cand_diag.update(min_sep_px=min_sep_px, include_positive_channels=inc_pos_ch,
                     strict_aligned_corridors=bool(meta_cfg.get("strict_aligned_corridors", False)),
                     strike_bridge_weight=float(meta_cfg.get("strike_bridge_weight", 0.0)))
    mark(f"candidates {cand_diag}")

    truth_by_cell = {k: v for k, v in ctx.hidden_by_cell.items()}
    visible_by_cell = {c.key: ctx.visible(c.key) for c in ctx.cells}
    active_by_cell = {c.key: c.active for c in ctx.cells}

    # ---------------- E1 ---------------- #
    # H66-6: the lane brief's mandated confound masks applied to the first-test
    # statistic (both arms of the comparison), and the preregistered litho
    # arm split (crossing channels on / off a basement-surface step).
    e1_masked = bool(getattr(args, "e1_mask", False))
    e1_rows = run_e1(ctx, step, channel, active_by_cell, truth_by_cell, visible_by_cell,
                     modes=("all",),
                     exclude=exclude if e1_masked else None)
    e1 = paired_bootstrap(e1_rows)
    e1_arms = {}
    if getattr(args, "e1_arms", False):
        litho, litho_thr = litho_step_mask(load("footprint"))
        channel_eff = channel & ~exclude
        for arm, mask in (("T_no_basement_step", ~litho & channel_eff),
                          ("L_on_basement_step", litho & channel_eff)):
            # exclude is passed again so the control start pool is masked exactly
            # as in the main test (the arm masks already remove those cells from
            # the statistic, the pool restriction keeps the comparison matched)
            rows_arm = run_e1(ctx, step, mask, active_by_cell, truth_by_cell,
                              visible_by_cell, modes=("all",), exclude=exclude)
            e1_arms[arm] = paired_bootstrap(rows_arm)
        mark("E1 arms (litho_step thr %.1f m, channel px T %d / L %d): %s" % (
            litho_thr, int((channel_eff & ~litho).sum()), int((channel_eff & litho).sum()),
            {k: v["verdict"] for k, v in e1_arms.items()}))
    e1_full = dict(evidence_class="MEASUREMENT", test="withheld-segment steepness step vs "
                   "random same-orientation transects",
                   masks_applied_to_statistic=e1_masked,
                   summary=e1,
                   components=len(e1_rows),
                   skipped=sum(1 for r in e1_rows if "skipped" in r),
                   rows=e1_rows)
    if e1_arms:
        e1_full["arms"] = e1_arms
        e1_full["arms_note"] = ("H66-6 prereg: arm T = crossing channel cells on a CONTINUOUS "
                                "basement surface (uplift reading); arm L = cells on a "
                                "depth_to_base_surf step (named lithologic mimic). Same "
                                "statistic, same seeds, control pool restricted to the same "
                                "masked domain as the observation.")
    (EVID / f"{TAG}_e1_first_test.json").write_text(
        json.dumps(e1_full, indent=2, allow_nan=False) + "\n")
    mark(f"E1 {e1}")
    if e1.get("verdict") == "STOP":
        (EVID / f"{TAG}_lane_stop.json").write_text(json.dumps(dict(
            reason="mandated first test failed: withheld crossings do not exceed "
                   "random same-orientation transects", summary=e1), indent=2) + "\n")
        mark("E1 verdict STOP -> lane halts here per the brief")

    # ---------------- per-cell surfaces ---------------- #
    terms = {}
    surf_terms = {}
    canary_rows = []
    diag_cells = []
    budgets = {}
    DOT_ARMS = ("lane_h60a", "ksn_only_no_alignment", "distance_only", "random_mass_control")
    # the continuous-surface arm is only defined for arms that have a [0,1] field:
    # an empty list would sum to a scalar and break pooled_summary's alignment check
    SURF_ARMS = ("lane_h60a", "distance_only")
    for arm in DOT_ARMS:
        terms[arm] = []
    for arm in SURF_ARMS:
        surf_terms[arm] = []
    cells = [c for c in ctx.cells if c.mode == "all"]
    # leave-one-out k_truth estimate: design prevalence from the other cells
    for cell in cells:
        bb = cell.bbox
        truth = truth_by_cell[cell.key][bb] & cell.active
        vis = visible_by_cell[cell.key]
        vis_crop = vis[bb]
        buf = ndi.binary_dilation(vis_crop, iterations=L.CATALOGUE_BUFFER_PX)
        allowed = cell.active & ~buf
        n_allowed = int(allowed.sum())
        budget = max(200, int(round(DENSITY * n_allowed)))
        budgets[cell.key] = dict(allowed=n_allowed, budget=budget)
        res = L.surface_from_candidates(z, cand, terminal, vis, dict(cand_diag),
                                        max_candidates=args.max_candidates,
                                        **surf_kw)
        p = res.p[bb].astype(np.float64)
        diag_cells.append(dict(cell=cell.key, **res.diagnostics))
        dots = L.top_k_dots(p, allowed, budget, min_sep_px=min_sep_px).astype(np.float32)

        d = ndi.distance_transform_edt(~vis_crop)
        p_dist = np.exp(-d / 3.0)
        p_dist[~allowed] = 0.0
        dots_dist = L.top_k_dots(p_dist, allowed, budget).astype(np.float32)

        zz = np.where(channel[bb] & ~exclude[bb] & np.isfinite(ksn[bb]), ksn[bb], np.nan)
        rr = rankdata(np.where(np.isfinite(zz), zz, 0.0).ravel()).reshape(zz.shape) / zz.size
        p_ksn = np.where(np.isfinite(zz), rr, 0.0).astype(np.float64)
        dots_ksn = L.top_k_dots(p_ksn, allowed, budget).astype(np.float32)

        rng = np.random.default_rng(60000 + cell.fold)
        pr = np.zeros_like(p)
        pr[allowed] = rng.random(n_allowed)
        dots_rnd = L.top_k_dots(pr, allowed, budget).astype(np.float32)

        fold = cell_fold(cell, truth_by_cell[cell.key][bb])
        origin = (bb[0].start, bb[1].start)
        gshape = (grid.height, grid.width)
        for arm, arr in (("lane_h60a", dots), ("ksn_only_no_alignment", dots_ksn),
                         ("distance_only", dots_dist), ("random_mass_control", dots_rnd)):  # DOT_ARMS
            scored, t = EH.evaluate(arr, fold, grid.footprint[bb], block_side=200,
                                    origin=origin, global_shape=gshape)
            terms[arm].append(t)
        for arm, arr in (("lane_h60a", np.clip(p, 0, 1).astype(np.float32)),
                         ("distance_only", p_dist.astype(np.float32))):  # SURF_ARMS
            scored, t = EH.evaluate(arr, fold, grid.footprint[bb], block_side=200,
                                    origin=origin, global_shape=gshape)
            surf_terms[arm].append(t)
        # canary: each feature alone
        feats = [("knickpoint_step", step[bb]), ("ksn", ksn[bb])]
        if chi is not None:
            feats.append(("chi", chi[bb]))
        feats += [("drainage_area", acc[bb]), ("lane_p", p), ("dist_to_visible", -d)]
        for name, feat in feats:
            canary_rows.append(dict(cell=cell.key, feature=name,
                                    auc=auc(feat, truth_by_cell[cell.key][bb] & cell.active,
                                            allowed)))
        mark(f"cell {cell.key} budget={budget} allowed={n_allowed} "
             f"aligned={diag_cells[-1].get('aligned_candidates')}")
        del res, p, dots, p_dist, dots_dist, p_ksn, dots_ksn, pr, dots_rnd

    pooled_dots = EH.pooled_summary({k: np.sum(v, axis=0) for k, v in terms.items()},
                                    draws=BOOT_DRAWS, seed=BOOT_SEED, candidate="lane_h60a")
    pooled_surf = EH.pooled_summary({k: np.sum(v, axis=0) for k, v in surf_terms.items()},
                                    draws=BOOT_DRAWS, seed=BOOT_SEED, candidate="lane_h60a")
    can = {}
    for row in canary_rows:
        a = row["auc"]
        if not np.isfinite(a):
            continue
        m = max(a, 1 - a)
        cur = can.get(row["feature"])
        if cur is None or m > cur["max_abs_auc"]:
            can[row["feature"]] = dict(feature=row["feature"], max_abs_auc=float(m),
                                       auc=float(a), worst_cell=row["cell"],
                                       leakage_flag=bool(m > 0.90))
    out = dict(evidence_class="HOLDOUT-DTI", evaluator_version=EH.VERSION,
               implementation_sha256=EH.implementation_hashes(),
               generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               density=DENSITY, budgets=budgets, cells=len(cells),
               e1_first_test=e1, confounds=conf_diag, candidates=cand_diag,
               pooled_binary=pooled_dots, pooled_surface=pooled_surf,
               canary=list(can.values()),
               canary_rule="max(AUC,1-AUC) > 0.90 is leakage until proven otherwise",
               cell_diagnostics=diag_cells, log=log)
    (EVID / f"{TAG}_holdout.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    mark(f"pooled binary: {json.dumps(pooled_dots['scores'], default=float)[:600]}")
    mark(f"paired deltas: {json.dumps(pooled_dots['paired_differences'], default=float)[:600]}")
    mark(f"canary flags: {[c['feature'] for c in can.values() if c['leakage_flag']]}")
    mark(f"wrote {EVID/(TAG + '_holdout.json')}")
    return 0


def main() -> int:
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "channel-knickpoint experiment runner (H60A/H65)"):
        return 0
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-candidates", type=int, default=60_000)
    # H66-6 (2026-10-11, session arena/b219bfe1): the lane brief's mandated
    # confound masks, applied to the first-test statistic. All three default
    # OFF, so a bare invocation reproduces H60-A/H65 byte-for-byte.
    ap.add_argument("--e1-mask", action="store_true",
                    help="apply the confound masks to the E1 statistic (observed "
                         "zone, control zones and random start pool)")
    ap.add_argument("--include-ephemeral", action="store_true",
                    help="add the lane brief's ephemeral-channel mask (10 m "
                         "drainage area < 1 km2) to the confound exclusion")
    ap.add_argument("--e1-arms", action="store_true",
                    help="preregistered H66-6 arm split of the first test: "
                         "crossing channels on vs off a basement-surface step "
                         "(depth_to_base_surf, the named lithologic mimic)")
    return run(ap.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
