"""From chi-profiles to a fault-trace evidence field.

Two statistics are computed on the channel network:

1. **Sharpened steepness step** (localised to a few hundred metres, unlike the
   long-window segmentation of :mod:`gems60.knick`):

       Sigma(cell) = log10( ksn(upstream of cell +/- gap) / ksn(downstream) )

   with ``ksn = dz/dchi`` fitted on a short window of ``w`` samples.  A fault
   crossing a channel puts a base-level step there, so ``Sigma > 0`` at the
   crossing (convex knickpoint, Kirby & Whipple 2012).

2. **chi-residual step**: the residual of z about a local straight line in
   chi-space, i.e. the classic chi-plot step (Perron & Royden 2013).

3. **Channel-normal casting** (the fault-line integrator).  A fault trace crosses
   a channel roughly *perpendicular* to the channel there.  So each candidate
   crossing casts a line along the local channel **normal**; where several
   independent drainages cast across one common strike the casts reinforce and a
   continuous fault trace emerges.  This is the operational form of the lane's
   requirement to "keep only knickpoints and steepness steps that align across
   several independent drainages along a common strike".
"""

from __future__ import annotations

import numpy as np

from .knick import segment_contrast_profile


def _cum(a):
    return np.concatenate([[0.0], np.cumsum(a)])


def ksn_profile(chis: np.ndarray, zs: np.ndarray, w: int = 7) -> np.ndarray:
    """ksn = dz/dchi on a centred window of ``w`` samples; NaN where undefined."""
    n = len(chis)
    out = np.full(n, np.nan)
    if n < w:
        return out
    Sx, Sy, Sxx, Sxy = _cum(chis), _cum(zs), _cum(chis * chis), _cum(chis * zs)
    half = w // 2
    idx = np.arange(half, n - half, dtype=np.int64)
    if idx.size == 0:
        return out
    i0, i1 = idx - half, idx + half + 1
    m = (i1 - i0).astype(float)
    sx = Sx[i1] - Sx[i0]
    sy = Sy[i1] - Sy[i0]
    sxx = Sxx[i1] - Sxx[i0]
    sxy = Sxy[i1] - Sxy[i0]
    den = m * sxx - sx * sx
    good = np.abs(den) > 1e-12
    a = np.full(idx.size, np.nan)
    a[good] = (m * sxy - sx * sy)[good] / den[good]
    out[idx] = a
    return out


def chi_residual_profile(chis: np.ndarray, zs: np.ndarray, w: int = 61) -> np.ndarray:
    """z minus the local chi-line: the chi-plot step, centred window of w."""
    n = len(chis)
    out = np.full(n, np.nan)
    if n < w:
        return out
    Sx, Sy, Sxx, Sxy = _cum(chis), _cum(zs), _cum(chis * chis), _cum(chis * zs)
    half = w // 2
    idx = np.arange(half, n - half, dtype=np.int64)
    if idx.size == 0:
        return out
    i0, i1 = idx - half, idx + half + 1
    m = (i1 - i0).astype(float)
    sx = Sx[i1] - Sx[i0]
    sy = Sy[i1] - Sy[i0]
    sxx = Sxx[i1] - Sxx[i0]
    sxy = Sxy[i1] - Sxy[i0]
    den = m * sxx - sx * sx
    good = np.abs(den) > 1e-12
    a = np.zeros(idx.size)
    b = np.zeros(idx.size)
    a[good] = (m * sxy - sx * sy)[good] / den[good]
    b = (sy - a * sx) / m
    out[idx] = zs[idx] - (a * chis[idx] + b)
    return out


def surface_statistics(profiles, chi, z, shape, w_ksn=7, gap=2, w_resid=61,
                       min_profile_len=16):
    """Build flat-indexed surfaces of the three statistics.

    Returns a dict of (flat_idx, value) pairs *and* a (N,) surface array per
    statistic filled only on the channel pixel each profile claims (longest
    profile wins, so every channel pixel has exactly one value).
    """
    chis_all = chi.ravel()
    zs_all = np.asarray(z).ravel()
    n = chis_all.size
    out = {k: np.full(n, np.nan) for k in ("ksn", "sigma", "resid", "basin")}
    order = np.argsort([-len(p) for p in profiles], kind="stable")
    for pi in order.tolist():
        path0 = profiles[pi]
        if len(path0) < min_profile_len:
            continue
        if np.isfinite(out["sigma"][path0]).all():
            continue
        c = chis_all[path0]
        o = np.argsort(c, kind="stable")
        path = path0[o]
        c = c[o]
        keep = np.concatenate([[True], np.diff(c) > 1e-9])
        path, c = path[keep], c[keep]
        if len(path) < min_profile_len:
            continue
        zz = zs_all[path]
        ksn = ksn_profile(c, zz, w=w_ksn)
        resid = chi_residual_profile(c, zz, w=w_resid)
        sig = np.full(len(path), np.nan)
        if gap + 1 < len(path):
            up = np.arange(0, len(path) - 2 * gap)
            k_up = ksn[up + 2 * gap]
            k_dn = ksn[up]
            good = (k_up > 0) & (k_dn > 0)
            pos = up[good]
            sig[pos] = np.log10(k_up[good] / k_dn[good])
        for key, arr in (("ksn", ksn), ("sigma", sig), ("resid", resid)):
            fresh = np.isnan(out[key][path]) & np.isfinite(arr)
            if fresh.any():
                out[key][path[fresh]] = arr[fresh]
        fresh = np.isnan(out["basin"][path])
        if fresh.any():
            basin_id = int(path[0]) if len(path) else -1
            out["basin"][path[fresh]] = basin_id
    return out


def local_channel_direction(path_flat, shape, halfspan: int = 5):
    """Unit direction of the channel at each interior sample of one profile."""
    ys, xs = np.unravel_index(path_flat, shape)
    n = len(path_flat)
    dy = np.full(n, np.nan)
    dx = np.full(n, np.nan)
    if n < 2 * halfspan + 1:
        return dy, dx
    i0 = np.arange(halfspan, n - halfspan)
    dy[i0] = (ys[i0 + halfspan] - ys[i0 - halfspan]).astype(float)
    dx[i0] = (xs[i0 + halfspan] - xs[i0 - halfspan]).astype(float)
    return dy, dx


def cast_field(profiles, chi, z, shape, sigma_surface, threshold, gap=2,
               cast_half_length_px=12, weight_mode="step", min_contrast=None,
               contrast_surface=None):
    """Accumulate channel-normal casts from candidate knickpoint crossings.

    For every channel pixel whose Sigma exceeds ``threshold`` a segment of
    half-length ``cast_half_length_px`` is drawn through the pixel along the
    local channel **normal** (the direction a fault trace would cross it),
    weighted by the step magnitude.  The result is a per-cell evidence count.
    """
    chis_all = chi.ravel()
    field = np.zeros(shape, dtype=np.float64)
    n_cast = 0
    h, w = shape
    for path0 in profiles:
        if len(path0) < 20:
            continue
        c = chis_all[path0]
        o = np.argsort(c, kind="stable")
        path = path0[o]
        c = c[o]
        keep = np.concatenate([[True], np.diff(c) > 1e-9])
        path, c = path[keep], c[keep]
        if len(path) < 20:
            continue
        sig = sigma_surface[path]
        cand = np.nonzero(np.isfinite(sig) & (sig >= threshold))[0]
        if cand.size == 0:
            continue
        if min_contrast is not None and contrast_surface is not None:
            ctr = contrast_surface[path]
            cand = cand[np.isfinite(ctr[cand]) & (ctr[cand] >= min_contrast)]
            if cand.size == 0:
                continue
        # one cast per local maximum along the profile, separated by >= 3 px
        picked = []
        for i in cand[np.argsort(-sig[cand])]:
            if all(abs(i - j) >= 3 for j in picked):
                picked.append(int(i))
        dy, dx = local_channel_direction(path, shape, halfspan=4)
        ys, xs = np.unravel_index(path, shape)
        for i in picked:
            if not np.isfinite(dy[i]) or not np.isfinite(dx[i]):
                continue
            ny, nx = dx[i], -dy[i]      # rotate the tangent by 90 degrees
            norm = float(np.hypot(ny, nx))
            if norm < 1e-9:
                continue
            ny /= norm
            nx /= norm
            t = np.arange(-cast_half_length_px, cast_half_length_px + 1)
            py = np.rint(ys[i] + ny * t).astype(np.int64)
            px = np.rint(xs[i] + nx * t).astype(np.int64)
            ok = (py >= 0) & (py < h) & (px >= 0) & (px < w)
            if not ok.any():
                continue
            wgt = float(sig[i]) if weight_mode == "step" else 1.0
            front = 1.0 - np.abs(t) / (cast_half_length_px + 1.0)
            np.add.at(field, (py[ok], px[ok]), wgt * front[ok])
            n_cast += 1
    return field, n_cast
