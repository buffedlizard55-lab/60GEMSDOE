"""Channel-hydrology core for the tectonic-geomorphology lane.

Implements, on the official 100 m competition grid (EPSG:32611):
  1. Priority-Flood + epsilon depression filling (Barnes, Lehman & Mulla 2014)
     with downstream parent pointers, so flats and playas route correctly.
  2. D8 drainage: every cell drains to the neighbour it was discovered from
     during the fill (its first lower/open neighbour).
  3. Flow accumulation in cells (A_m2 = acc * 10_000).
  4. The chi transform of Perron & Royden (2013): chi = int (A0/A)^theta dx'
     integrated downstream with theta = 0.45 (Kirby & Whipple 2012 review).
  5. Channel slope S = dz/dx on the filled surface and the stream-power
     proxy ksn = S * A^theta, from which the lane's steepness-step anomaly
     is derived downstream of this module.

Everything is deterministic. No labels are used anywhere in this module.

References (verified 2026-10-11):
  - Perron & Royden, Earth Surf. Process. Landforms 38(1):94-102 (2013).
  - Kirby & Whipple, J. Geophys. Res. 117:F01024 (2012) - ksn / theta review.
  - Barnes, Lehman & Mulla, Comput. Geosci. 62:117-127 (2014) - Priority-Flood.
"""
from __future__ import annotations

import numpy as np
from numba import njit

_DY = np.array([-1, -1, -1, 0, 0, 1, 1, 1], dtype=np.int64)
_DX = np.array([-1, 0, 1, -1, 1, -1, 0, 1], dtype=np.int64)


@njit(cache=True)
def _priority_flood_full(z: np.ndarray, valid: np.ndarray):
    """Priority-Flood + epsilon fill; single correct implementation."""
    H, W = z.shape
    N = H * W
    filled = z.ravel().copy()
    parent = np.full(N, -1, dtype=np.int64)
    visited = np.zeros(N, dtype=np.bool_)
    order = np.empty(N, dtype=np.int64)
    n_order = 0

    cap = N + 16
    heap_k = np.empty(cap, dtype=np.float64)
    heap_i = np.empty(cap, dtype=np.int64)
    hn = 0
    eps = 1e-4

    for y in range(H):
        for x in range(W):
            i = y * W + x
            if not valid[y, x]:
                continue
            for nb in range(8):
                yy = y + _DY[nb]
                xx = x + _DX[nb]
                if yy < 0 or xx < 0 or yy >= H or xx >= W or not valid[yy, xx]:
                    visited[i] = True
                    hn += 1
                    j = hn
                    kv = filled[i]
                    while j > 1 and heap_k[j >> 1] > kv:
                        heap_k[j] = heap_k[j >> 1]
                        heap_i[j] = heap_i[j >> 1]
                        j >>= 1
                    heap_k[j] = kv
                    heap_i[j] = i
                    break

    while hn > 0:
        k = heap_k[1]
        i = heap_i[1]
        hn -= 1
        if hn > 0:
            lk = heap_k[hn + 1]
            li = heap_i[hn + 1]
            j = 1
            while True:
                l = j << 1
                r = l + 1
                s = j
                sk = lk
                si = li
                if l <= hn and heap_k[l] < sk:
                    s = l
                    sk = heap_k[l]
                    si = heap_i[l]
                if r <= hn and heap_k[r] < sk:
                    s = r
                    sk = heap_k[r]
                    si = heap_i[r]
                if s == j:
                    break
                heap_k[j] = sk
                heap_i[j] = si
                j = s
            heap_k[j] = lk
            heap_i[j] = li

        order[n_order] = i
        n_order += 1
        y = i // W
        x = i - y * W
        for nb in range(8):
            yy = y + _DY[nb]
            xx = x + _DX[nb]
            if yy < 0 or xx < 0 or yy >= H or xx >= W:
                continue
            jj = yy * W + xx
            if visited[jj] or not valid[yy, xx]:
                continue
            visited[jj] = True
            parent[jj] = i
            zj = filled[jj]
            if zj <= k:
                zj = k + eps
                filled[jj] = zj
            hn += 1
            j2 = hn
            while j2 > 1 and heap_k[j2 >> 1] > zj:
                heap_k[j2] = heap_k[j2 >> 1]
                heap_i[j2] = heap_i[j2 >> 1]
                j2 >>= 1
            heap_k[j2] = zj
            heap_i[j2] = jj

    return filled, parent, order[:n_order]


@njit(cache=True)
def _accumulate(parent: np.ndarray, order: np.ndarray):
    """Flow accumulation in cells: reverse pop order = upstream first."""
    N = parent.shape[0]
    acc = np.ones(N, dtype=np.float64)
    for t in range(order.shape[0] - 1, -1, -1):
        i = order[t]
        p = parent[i]
        if p >= 0:
            acc[p] += acc[i]
    return acc


@njit(cache=True)
def _chi(parent: np.ndarray, order: np.ndarray, acc: np.ndarray,
         theta: float, a0_m2: float, cell_m: float, width: int = 0):
    """chi = integral of (A0/A)^theta dx' downstream (fused single pass).

    order is ascending filled z: the parent (strictly lower) is always
    final before any of its upstream neighbours is reached.

    Shared-tool fix (2026-10-11, session arena/96ecd67e, H65): ``dx'`` is the
    true length of the D8 step into the parent -- ``cell_m * sqrt(2)`` for a
    diagonal step -- when the grid ``width`` is supplied.  The previous form
    used ``cell_m`` for every step, under-stating chi by up to 29 % on
    diagonal reaches.  ``width = 0`` keeps the legacy behaviour for callers
    that do not pass it.
    """
    N = parent.shape[0]
    chi = np.zeros(N, dtype=np.float64)
    cell2 = cell_m * cell_m
    diag = cell_m * np.sqrt(2.0)
    for t in range(order.shape[0]):
        i = order[t]
        p = parent[i]
        if p >= 0:
            a_m2 = acc[i] * cell2
            ds = cell_m
            if width > 0:
                if (i // width) != (p // width) and (i % width) != (p % width):
                    ds = diag
            chi[i] = chi[p] + ds * ((a0_m2 / a_m2) ** theta)
    return chi


def hydro_stack(z: np.ndarray, valid: np.ndarray, cell_m: float = 100.0,
                theta: float = 0.45, a0_m2: float = 1e6):
    """Full lane stack from a valid-masked elevation grid (deterministic)."""
    z64 = np.ascontiguousarray(z.astype(np.float64))
    vbool = np.ascontiguousarray(valid.astype(np.bool_))
    filled, parent, order = _priority_flood_full(z64, vbool)
    acc = _accumulate(parent, order)
    chi = _chi(parent, order, acc, float(theta), float(a0_m2), float(cell_m), int(z.shape[1]))

    H, W = z.shape
    N = H * W
    idx = np.arange(N)
    cy = idx // W
    cx = idx % W
    py = parent // W
    px = parent % W
    has_p = parent >= 0
    step = np.hypot(py - cy, px - cx)
    step[~has_p] = 1.0
    step[step == 0] = 1.0
    slope = np.zeros(N, dtype=np.float64)
    slope[has_p] = (filled[has_p] - filled[parent[has_p]]) / (step[has_p] * cell_m)
    return {
        "filled": filled.reshape(H, W),
        "parent": parent,
        "order": order,
        "n_valid": int(vbool.sum()),
        "acc": acc,
        "chi": chi,
        "slope": slope,
    }


def gaussian_blur(a: np.ndarray, sigma: float, valid: np.ndarray) -> np.ndarray:
    """Validity-normalised gaussian blur (no leakage from nodata)."""
    from scipy.ndimage import gaussian_filter
    x = np.where(valid, a, 0.0).astype(np.float64)
    w = valid.astype(np.float64)
    num = gaussian_filter(x, sigma, mode="constant")
    den = gaussian_filter(w, sigma, mode="constant")
    out = np.where(den > 1e-9, num / np.maximum(den, 1e-9), 0.0)
    return np.where(valid, out, 0.0)
