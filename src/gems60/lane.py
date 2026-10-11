"""H60-A lane surface: corroborated knickpoints -> strike-aligned trace probability.

Physical argument
-----------------
Kirby & Whipple (2012) : a step in rock-uplift rate across an active normal
fault produces a knickpoint at the fault crossing and elevated normalized
steepness (``ksn``) upstream of it.  Perron & Royden (2013) : ``chi`` puts
channels of different size on one axis, so a ``ksn`` step is comparable between
drainages.  One knickpoint in one drainage is ambiguous (lithology, a landslide,
a debris-flow reach, a climate-driven discharge change all make them).  A
knickpoint *corroborated by several independent drainages along a common strike*
is not: no single-channel process is strike-aligned across drainage divides,
while a fault is exactly that.

The surface therefore keeps only knickpoints that satisfy the lane brief's
corroboration rule and then re-expresses them as **strike-aligned corridors** --
because the object being predicted is a fault *trace*, and the corridor is the
segment of that trace bracketed by the corroborated crossings.

Everything catalogue-derived here comes from the *visible* faults of the fold
(``structure_strike`` of the visible mask), so a withheld segment cannot leak
through the orientation.  Declared constants are module-level and are never
fitted per fold.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

from . import geomorph as gm

# --- declared, pre-registered constants (not tuned per fold) ------------------ #
Z_MIN = 1.5                    # blockwise z-score of log(ksn_up/ksn_down) for a candidate
N_DRAINAGE_MIN = 3             # "several independent drainages" in the lane brief
CORRIDOR_HALF_LEN_PX = 6       # 600 m along strike
CORRIDOR_HALF_WIDTH_PX = 2     # 200 m across strike
N_STRIKE_BINS = 18             # 10 deg strike resolution
TRACE_DECAY = 0.5              # corridor (non-crossing) cells get this fraction of the knickpoint z
STRIKE_SIGMA_PX = 6.0          # 600 m smoothing of the visible-catalogue structure tensor
BLOCK_PX = 400                 # 40 km blocks for the climate/lithology gradient control
CATALOGUE_BUFFER_PX = 2        # production rule: no dot within 2 px (200 m) of a mapped fault


def nearest_visible_strike(visible: np.ndarray, sigma_px: float = STRIKE_SIGMA_PX):
    """Strike azimuth (rad, mod pi) of the *nearest visible* catalogue pixel.

    Returns ``(strike, coherence, distance_px)``.  Where the nearest visible
    pixel is far or the fabric incoherent, the caller falls back to the regional
    modal strike, which is also computed from visible faults only.
    """
    vis = np.asarray(visible, bool)
    strike, coh = gm.structure_strike(vis.astype(np.float32), sigma_px=sigma_px)
    if not vis.any():
        return strike, coh, np.full(vis.shape, np.inf)
    d, (iy, ix) = ndi.distance_transform_edt(~vis, return_indices=True)
    return strike[iy, ix], coh[iy, ix], d


def regional_modal_strike(strike: np.ndarray, coh: np.ndarray, visible: np.ndarray,
                          n_bins: int = N_STRIKE_BINS) -> float:
    """Modal visible-fault strike in ``n_bins`` bins, weighted by coherence."""
    vis = np.asarray(visible, bool)
    if not vis.any():
        return 0.0
    near = ndi.binary_dilation(vis, iterations=8)
    sel = near & (coh > 0.5) & np.isfinite(strike)
    if sel.sum() < 50:
        sel = vis
    b = np.floor(np.asarray(strike)[sel] / np.pi * n_bins).astype(int) % n_bins
    counts = np.bincount(b, minlength=n_bins)
    return float((np.argmax(counts) + 0.5) * np.pi / n_bins)


def strike_bins(strike: np.ndarray, regional: float, coh: np.ndarray,
                max_dist_px: float = 25.0, min_coh: float = 0.25,
                n_bins: int = N_STRIKE_BINS) -> np.ndarray:
    """Bin index of the strike to use per cell: local fabric, else regional mode."""
    use_local = (coh > min_coh) & np.isfinite(strike)
    s = np.where(use_local, strike, regional)
    return (np.floor(s / np.pi * n_bins).astype(np.int32) % n_bins)


def corridor_offsets(half_len: int, half_width: int, strike_rad: float) -> tuple[np.ndarray, np.ndarray]:
    """(dy, dx) offsets of the corridor rectangle for one strike (radians)."""
    u_row, u_col = -np.cos(strike_rad), np.sin(strike_rad)
    v_row, v_col = np.sin(strike_rad), np.cos(strike_rad)
    span = half_len + half_width + 1
    dy, dx = np.mgrid[-span:span + 1, -span:span + 1]
    pa = dy * u_row + dx * u_col
    pp = dy * v_row + dx * v_col
    keep = (np.abs(pa) <= half_len) & (np.abs(pp) <= half_width)
    return dy[keep].astype(np.int32), dx[keep].astype(np.int32)


def stamp_corridors(ys: np.ndarray, xs: np.ndarray, bins: np.ndarray, values: np.ndarray,
                    shape: tuple[int, int], half_len: int, half_width: int,
                    n_bins: int = N_STRIKE_BINS, decay: float = TRACE_DECAY):
    """Stamp every candidate's corridor into ``(mask, score)`` arrays.

    Sparse stamping (one small patch per candidate) instead of 18 full-array
    oriented filters: identical output, two orders of magnitude cheaper.
    """
    offs = {}
    for b in range(n_bins):
        ang = (b + 0.5) * np.pi / n_bins
        offs[b] = corridor_offsets(half_len, half_width, ang)
    mask = np.zeros(shape, bool)
    score = np.zeros(shape, np.float32)
    H, W = shape
    for i in range(ys.size):
        dy, dx = offs[int(bins[i])]
        yy = ys[i] + dy
        xx = xs[i] + dx
        ok = (yy >= 0) & (xx >= 0) & (yy < H) & (xx < W)
        if not ok.any():
            continue
        yy, xx = yy[ok], xx[ok]
        mask[yy, xx] = True
        v = np.float32(decay * values[i])
        np.maximum.at(score, (yy, xx), v)
    return mask, score


@dataclass
class SurfaceResult:
    p: np.ndarray                 # float32 in [0, 1], 0 where the lane says nothing
    diagnostics: dict
    n_drainages: np.ndarray       # int32, distinct drainages in the corridor (0 off-candidate)


def prepare_candidates(step: np.ndarray, channel: np.ndarray, exclude: np.ndarray,
                       block_px: int = BLOCK_PX, z_min: float = Z_MIN):
    """Catalogue-independent half of the surface: blockwise z-score and candidates.

    Split out so the 16 holdout cells share one computation; ``exclude`` here
    holds only the *declared confound masks*, never anything derived from the
    catalogue, so the result is legal to compute once for the whole grid.
    """
    step = np.asarray(step, np.float64)
    valid = np.asarray(channel, bool) & ~np.asarray(exclude, bool) & np.isfinite(step)
    z = gm.blockwise_zscore(step, valid, block_px=block_px)
    z = np.where(np.isfinite(z), z, 0.0).astype(np.float32)
    cand = valid & (z >= z_min)
    diag = dict(channel_pixels=int(np.asarray(channel, bool).sum()),
                valid_channel_pixels=int(valid.sum()),
                candidate_pixels=int(cand.sum()),
                z_min=z_min, block_px=block_px)
    return z, cand, diag


def surface_from_candidates(z: np.ndarray, cand: np.ndarray, terminal: np.ndarray,
                            visible: np.ndarray, diag: dict | None = None, *,
                            n_drainage_min: int = N_DRAINAGE_MIN,
                            half_len: int = CORRIDOR_HALF_LEN_PX,
                            half_width: int = CORRIDOR_HALF_WIDTH_PX,
                            regional_strike: float | None = None,
                            max_candidates: int = 120_000,
                            include_positive_channels: bool = False) -> SurfaceResult:
    """Fold-dependent half: visible-catalogue strike, corridor corroboration, p."""
    diag = dict(diag or {})
    diag.update(n_drainage_min=n_drainage_min, corridor_half_len_px=half_len,
                corridor_half_width_px=half_width, trace_decay=TRACE_DECAY)
    p = np.zeros(z.shape, np.float32)
    ndr = np.zeros(z.shape, np.int32)
    ys, xs = np.nonzero(cand)
    if ys.size == 0:
        diag.update(aligned_candidates=0, trace_pixels=0, positive_pixels=0)
        return SurfaceResult(p, diag, ndr)
    if ys.size > max_candidates:
        keep = np.argsort(-z[ys, xs], kind="stable")[:max_candidates]
        ys, xs = ys[keep], xs[keep]
        diag["candidates_capped_to"] = max_candidates

    strike_near, coh, dvis = nearest_visible_strike(visible)
    regional = (regional_modal_strike(strike_near, coh, visible)
                if regional_strike is None else float(regional_strike))
    diag.update(regional_modal_strike_deg=float(np.rad2deg(regional)))
    bins_all = strike_bins(strike_near, regional, coh)
    b = bins_all[ys, xs]
    ndr_vals = gm.distinct_drainages_in_corridor((ys, xs), terminal, strike_near,
                                                 half_len, half_width)
    ndr[ys, xs] = ndr_vals
    aligned = ndr_vals >= n_drainage_min
    diag.update(candidate_pixels_scanned=int(ys.size), aligned_candidates=int(aligned.sum()),
                n_drainage_p50=float(np.median(ndr_vals)),
                n_drainage_p90=float(np.percentile(ndr_vals, 90)),
                n_drainage_max=int(ndr_vals.max()))

    if include_positive_channels:
        s = np.where(np.isfinite(z) & (z > 0), z * np.float32(0.05), np.float32(0.0)).astype(np.float32)
    else:
        s = np.zeros(z.shape, np.float32)
    s[ys, xs] = np.maximum(s[ys, xs], z[ys, xs])
    if aligned.any():
        ay, ax = ys[aligned], xs[aligned]
        s[ay, ax] += np.float32(1.0 + np.log2(np.maximum(ndr_vals[aligned], 1)))
        tmask, tscore = stamp_corridors(ay, ax, bins_all[ay, ax], s[ay, ax], z.shape,
                                        half_len, half_width, decay=TRACE_DECAY)
        trace_only = tmask & (s < tscore)
        s[trace_only] = tscore[trace_only]
        diag.update(trace_pixels=int(tmask.sum()), trace_only_pixels=int(trace_only.sum()))
    else:
        diag.update(trace_pixels=0, trace_only_pixels=0)

    pos = s > 0
    n_pos = int(pos.sum())
    if n_pos:
        vals = s[pos]
        ranks = np.zeros(s.size, np.float32)
        order = np.argsort(vals, kind="stable")
        ranks[np.flatnonzero(pos.ravel())[order]] = np.arange(1, n_pos + 1, dtype=np.float32)
        p = (ranks / np.float32(n_pos)).reshape(s.shape)
        p[~pos] = 0.0
    diag.update(positive_pixels=n_pos, p_max=float(p.max()) if n_pos else 0.0)
    return SurfaceResult(p, diag, ndr)


def build_surface(step: np.ndarray, channel: np.ndarray, terminal: np.ndarray,
                  visible: np.ndarray, exclude: np.ndarray, *,
                  z_min: float = Z_MIN, n_drainage_min: int = N_DRAINAGE_MIN,
                  half_len: int = CORRIDOR_HALF_LEN_PX,
                  half_width: int = CORRIDOR_HALF_WIDTH_PX,
                  block_px: int = BLOCK_PX, regional_strike: float | None = None,
                  max_candidates: int = 120_000) -> SurfaceResult:
    """Build the lane probability surface from visible-catalogue context only.

    ``exclude`` is the union of the declared confound masks (closed-basin/playa
    floors, thick basin fill, conductive clay-rich alluvium) plus the cells where
    a dot may never be placed (mapped faults and their buffer).
    """
    z, cand, diag = prepare_candidates(step, channel, exclude, block_px=block_px, z_min=z_min)
    return surface_from_candidates(z, cand, terminal, visible, diag,
                                   n_drainage_min=n_drainage_min, half_len=half_len,
                                   half_width=half_width, regional_strike=regional_strike,
                                   max_candidates=max_candidates)


def allowed_production(footprint: np.ndarray, catalogue: np.ndarray,
                       buffer_px: int = CATALOGUE_BUFFER_PX) -> np.ndarray:
    """Cells where a production dot may sit: footprint, off mapped faults."""
    fp = np.asarray(footprint, bool)
    cat = np.asarray(catalogue, bool)
    if buffer_px > 0:
        yy, xx = np.mgrid[-buffer_px:buffer_px + 1, -buffer_px:buffer_px + 1]
        cat = ndi.binary_dilation(cat, structure=(yy * yy + xx * xx) <= buffer_px ** 2)
    return fp & ~cat


def top_k_dots(p: np.ndarray, allowed: np.ndarray, budget: int, seed: int = 60,
               min_sep_px: float = 0.0) -> np.ndarray:
    """Top-``budget`` allowed cells by ``p``, ties broken by a fixed RNG.

    Tie-breaking is randomised but seeded, so a rank plateau cannot smuggle a
    raster-order artefact into the emission (the failure mode documented for the
    sibling family's earliest dotted files).  When ``min_sep_px > 0``, greedy
    spatial-hash non-maximum suppression enforces a minimum Euclidean spacing of
    ``min_sep_px`` pixels so multiple dots do not pack into the same 300 m
    Tversky kernel.
    """
    p = np.asarray(p, np.float64)
    al = np.asarray(allowed, bool) & (p > 0)
    ys, xs = np.nonzero(al)
    if ys.size == 0:
        return np.zeros(p.shape, bool)
    rng = np.random.default_rng(seed)
    key = p[ys, xs] + rng.random(ys.size) * 1e-9
    order = np.argsort(-key, kind="stable")
    if min_sep_px <= 0.0:
        order = order[:min(int(budget), ys.size)]
        out = np.zeros(p.shape, bool)
        out[ys[order], xs[order]] = True
        return out
    sep2 = float(min_sep_px) ** 2
    cell_sz = max(1, int(np.ceil(min_sep_px)))
    buckets: dict[tuple[int, int], list[tuple[int, int]]] = {}
    keep_y: list[int] = []
    keep_x: list[int] = []
    target = int(budget)
    for idx in order:
        y, x = int(ys[idx]), int(xs[idx])
        by, bx = y // cell_sz, x // cell_sz
        ok = True
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                for qy, qx in buckets.get((by + oy, bx + ox), ()):
                    if (qy - y) ** 2 + (qx - x) ** 2 < sep2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            keep_y.append(y)
            keep_x.append(x)
            buckets.setdefault((by, bx), []).append((y, x))
            if len(keep_y) >= target:
                break
    out = np.zeros(p.shape, bool)
    if keep_y:
        out[keep_y, keep_x] = True
    return out

