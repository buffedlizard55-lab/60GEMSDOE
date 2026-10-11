"""Knickpoint detection by chi-profile segmentation.

Method
------
Channel profiles are extracted as ordered (chi, z) sequences along the D8 flow
path.  In chi-space the *slope* dz/dchi is the normalised channel steepness
ksn = (U/K)^(1/n) (Perron & Royden 2013, eq. 12), so a **knickpoint** is a
location where the chi-profile slope changes.  We detect them by an exhaustive
two-segment linear fit inside a sliding window:

  for every candidate breakpoint k in the middle third of a window of W samples,
  fit   z = a1*chi + b1   on the downstream part and
        z = a2*chi + b2   on the upstream part,
  and compare the total sum of squared residuals SSE2 with the single-segment
  fit SSE1 on the same window.  The **segment contrast**

        C = (SSE1 - SSE2) / SSE1        in [0, 1]

  is maximised over k; the profile location achieving the local maximum of C is
  reported as a knickpoint with its upstream/downstream steepness ratio.

This is the reproducible, parameter-explicit form of the segmentation approach
of Gailleton et al. (2019, *Earth Surface Dynamics* 7, 707-725,
https://doi.org/10.5194/esurf-7-707-2019) and follows the two-segment / slope-break
logic of Wobus et al. (2006) and Kirby & Whipple (2012).  All window sizes are
declared parameters recorded in the run card - nothing is tuned on the label set.
"""

from __future__ import annotations

import numpy as np

from .hydro import bfs_levels, neighbour_step, SQRT2


def channel_mask(acc: np.ndarray, valid: np.ndarray, area_threshold_px: float) -> np.ndarray:
    """Channel cells: drainage accumulation >= a declared threshold (in pixels).

    1 px of the competition grid is 100 m x 100 m = 0.01 km2, so
    ``area_threshold_px = 100`` is a 1 km2 channel-initiation threshold.
    """
    return np.asarray(valid, bool) & (acc.reshape(np.asarray(valid).shape)
                                      >= float(area_threshold_px))


def upstream_channel_counts(down: np.ndarray, chan: np.ndarray) -> np.ndarray:
    n = down.size
    src = np.nonzero(chan.ravel())[0]
    return np.bincount(down[src], minlength=n)


def extract_profiles(down, chan, acc, chi, valid, min_len=25, max_profiles=200000):
    """Walk downstream from every channel source; return a list of flat-index
    arrays, each an ordered channel profile (downstream -> upstream reversed:
    the returned arrays run **upstream first** (high chi) to outlet last)."""
    n = down.size
    flat_chan = chan.ravel()
    up_cnt = upstream_channel_counts(down, chan)
    sources = np.nonzero(flat_chan & (up_cnt == 0))[0]
    v = valid.ravel()
    profiles = []
    for s in sources.tolist():
        path = []
        j = s
        while True:
            path.append(j)
            nxt = down[j]
            if nxt == j or not flat_chan[nxt]:
                break
            j = nxt
            if len(path) > 200000:
                break
        if len(path) >= min_len:
            profiles.append(np.array(path, dtype=np.int64))
        if len(profiles) >= max_profiles:
            break
    return profiles


def _window_sums(x: np.ndarray, w: int):
    """Cumulative sums helper: returns arrays of length n-w+1 giving sum over
    each window [i, i+w)."""
    cs = np.concatenate([[0.0], np.cumsum(x)])
    return cs[w:] - cs[:-w]


def _fit_vec(cum, i0: np.ndarray, i1: np.ndarray):
    """Fully vectorised least-squares slope + SSE for the slices [i0, i1).

    ``cum`` is a tuple of cumulative sums (Sx, Sy, Sxx, Syy, Sxy) of the profile.
    Returns (slope, sse).  Equivalent to fitting each slice separately.
    """
    Sx, Sy, Sxx, Syy, Sxy = cum
    m = (i1 - i0).astype(np.float64)
    sx = Sx[i1] - Sx[i0]
    sy = Sy[i1] - Sy[i0]
    sxx = Sxx[i1] - Sxx[i0]
    syy = Syy[i1] - Syy[i0]
    sxy = Sxy[i1] - Sxy[i0]
    den = m * sxx - sx * sx
    good = (m >= 2) & (np.abs(den) > 1e-12)
    a = np.zeros_like(m)
    b = np.zeros_like(m)
    np.divide(m * sxy - sx * sy, den, out=a, where=good)
    np.divide(sy - a * sx, m, out=b, where=m > 0)
    sse = (syy - 2 * a * sxy - 2 * b * sy + a * a * sxx + 2 * a * b * sx + m * b * b)
    # degenerate slice: SSE of the mean
    deg = ~good
    if deg.any():
        sse = np.where(deg, np.maximum(syy - np.divide(sy * sy, np.maximum(m, 1)), 0.0), sse)
    return a, np.maximum(sse, 0.0)


def segment_contrast_profile(chis: np.ndarray, zs: np.ndarray, w: int = 31):
    """Segment contrast C at every interior sample of one profile (vectorised).

    Returns ``(C, a_dn, a_up)`` each of length n.  C = 0 where a full window does
    not exist.  ``a_dn``/``a_up`` are the fitted slopes (ksn) downstream/upstream
    of the best breakpoint.  See the module docstring for the definition of C.
    """
    n = len(chis)
    C = np.zeros(n)
    A_D = np.zeros(n)
    A_U = np.zeros(n)
    if n < w + 2:
        return C, A_D, A_U
    half = w // 2
    csum = lambda a: np.concatenate([[0.0], np.cumsum(a)])
    cum = (csum(chis), csum(zs), csum(chis * chis), csum(zs * zs), csum(chis * zs))

    idx = np.arange(half, n - half, dtype=np.int64)
    if idx.size == 0:
        return C, A_D, A_U
    lo = idx - half
    hi = idx + half + 1
    _, sse1 = _fit_vec(cum, lo, hi)

    best_sse2 = np.full(idx.size, np.inf)
    best_ad = np.zeros(idx.size)
    best_au = np.zeros(idx.size)
    k0 = idx - half // 2
    for k in range(0, half + 1):
        kk = k0 + k
        ok = (kk > lo + 2) & (kk < hi - 2)
        if not ok.any():
            continue
        sel = np.nonzero(ok)[0]
        a1, s1 = _fit_vec(cum, lo[sel], kk[sel])
        a2, s2 = _fit_vec(cum, kk[sel], hi[sel])
        tot = s1 + s2
        upd = tot < best_sse2[sel]
        if upd.any():
            j = sel[upd]
            best_sse2[j] = tot[upd]
            best_ad[j] = a1[upd]
            best_au[j] = a2[upd]
    with np.errstate(divide="ignore", invalid="ignore"):
        Cw = np.where(sse1 > 1e-12, (sse1 - best_sse2) / np.maximum(sse1, 1e-300), 0.0)
    C[idx] = np.clip(Cw, 0.0, 1.0)
    A_D[idx] = best_ad
    A_U[idx] = best_au
    return C, A_D, A_U


def detect_knickpoints(
    profiles,
    down,
    acc,
    chi,
    z,
    valid,
    w: int = 31,
    contrast_min: float = 0.25,
    min_separation_px: int = 5,
    min_segment_px: int = 8,
):
    """Run the segmentation on every profile and return a structured table.

    Parameters
    ----------
    w : int
        Sliding-window length in *samples* along the profile (declared).
    contrast_min : float
        Minimum segment contrast C to call a knickpoint (declared).
    min_separation_px : int
        Minimum profile distance between reported knickpoints.
    min_segment_px : int
        Minimum number of samples on each side of a reported breakpoint.
    """
    chis_all = chi.ravel()
    zs_all = np.asarray(z).ravel()
    down_flat = down
    acc_flat = acc.ravel()
    v_flat = valid.ravel()

    rows = []
    basin_of = {}
    for p, path in enumerate(profiles):
        # profile order: source (upstream, high chi) -> outlet (low chi).
        # sort by chi ascending so `chi` behaves like distance downstream
        c = chis_all[path]
        order = np.argsort(c, kind="stable")
        path = path[order]
        c = c[order]
        if len(path) < max(w + 2, 2 * min_segment_px + 2):
            continue
        # enforce strictly increasing chi
        keep = np.concatenate([[True], np.diff(c) > 1e-9])
        path = path[keep]
        c = c[keep]
        if len(path) < max(w + 2, 2 * min_segment_px + 2):
            continue
        zz = zs_all[path]
        C, AD, AU = segment_contrast_profile(c, zz, w=w)
        # local maxima above threshold and far enough from the profile ends
        cand = np.nonzero(C >= contrast_min)[0]
        cand = cand[(cand >= min_segment_px) & (cand <= len(path) - min_segment_px - 1)]
        if cand.size == 0:
            continue
        picked = []
        for i in cand[np.argsort(-C[cand])]:
            if all(abs(i - j) >= min_separation_px for j in picked):
                picked.append(i)
        outlet_idx = int(path[0]) if down_flat[path[-1]] == path[-1] else int(down_flat[path[-1]])
        basin = outlet_idx
        for i in picked:
            flat = int(path[i])
            rows.append((
                flat, flat // valid.shape[1], flat % valid.shape[1],
                float(c[i]), float(AD[i]), float(AU[i]), float(C[i]),
                basin, int(acc_flat[flat]), float(zz[i]),
            ))
    cols = ("flat", "row", "col", "chi", "ksn_dn", "ksn_up", "contrast", "basin", "acc", "z")
    if not rows:
        return np.zeros(0, dtype=[(k, "f8") for k in cols])
    arr = np.array(rows, dtype=[(k, "f8") for k in cols])
    return arr


def channel_step_statistic(profiles, down, chi, z, valid, w: int = 31, dedupe: bool = True):
    """Per-channel-pixel steepness-step statistic used by the pre-registered
    first test:

        Sigma(cell) = log10( ksn_up(cell) / ksn_dn(cell) )

    computed on the same segmentation windows, so a fault crossing a channel is
    predicted to produce Sigma > 0 (steepening upstream of the base-level step).

    When ``dedupe`` is set (default) every channel pixel is assigned a value from
    exactly **one** profile - the longest profile that contains it - so the output
    statistic is a well-defined function of position rather than an average over
    the many overlapping source-to-outlet walks below a confluence.

    Returns ``(flat_idx, Sigma, contrast)``.
    """
    chis_all = chi.ravel()
    zs_all = np.asarray(z).ravel()
    n_flat = chis_all.size
    sigma = np.full(n_flat, np.nan)
    contrast = np.full(n_flat, np.nan)
    order = np.argsort([-len(p) for p in profiles], kind="stable")
    half = w // 2
    for pi in order.tolist():
        path = profiles[pi]
        if len(path) < w + 2:
            continue
        if dedupe and np.isfinite(sigma[path]).all():
            continue
        c = chis_all[path]
        o = np.argsort(c, kind="stable")
        path = path[o]
        c = c[o]
        keep = np.concatenate([[True], np.diff(c) > 1e-9])
        path, c = path[keep], c[keep]
        if len(path) < w + 2:
            continue
        C, AD, AU = segment_contrast_profile(c, zs_all[path], w=w)
        sl = slice(half, len(path) - half)
        p_sl = path[sl]
        ad, au = AD[sl], AU[sl]
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = au / np.maximum(ad, 1e-12)
        sig = np.where((ad > 0) & (au > 0), np.log10(np.maximum(ratio, 1e-12)), 0.0)
        if dedupe:
            fresh = ~np.isfinite(sigma[p_sl])
            sigma[p_sl[fresh]] = sig[fresh]
            contrast[p_sl[fresh]] = C[sl][fresh]
        else:
            sigma[p_sl] = sig
            contrast[p_sl] = C[sl]
    good = np.isfinite(sigma)
    return np.nonzero(good)[0], sigma[good], contrast[good]


def slope_steepness_profile(chis: np.ndarray, zs: np.ndarray, w: int = 31):
    """ksn = dz/dchi on a fixed sample window (the non-segmented baseline)."""
    n = len(chis)
    out = np.zeros(n)
    if n < w:
        return out
    cs = lambda a: np.concatenate([[0.0], np.cumsum(a)])
    Sx, Sy = cs(chis), cs(zs)
    Sxx, Sxy = cs(chis * chis), cs(chis * zs)
    half = w // 2
    i0 = np.arange(0, n - w + 1)
    i1 = i0 + w
    m = float(w)
    sx = Sx[i1] - Sx[i0]
    sy = Sy[i1] - Sy[i0]
    sxx = Sxx[i1] - Sxx[i0]
    sxy = Sxy[i1] - Sxy[i0]
    den = m * sxx - sx * sx
    a = np.where(np.abs(den) > 1e-12, (m * sxy - sx * sy) / np.maximum(den, 1e-300), 0.0)
    out[i0 + half] = a
    return out
