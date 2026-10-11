"""Tectonic-geomorphology primitives on a 100 m DEM.

Literature implemented here
---------------------------
* Depression filling by **priority flood** - Barnes, Lehman & Mulla (2014),
  *Priority-flood: An optimal depression-filling and watershed-labeling algorithm for digital
  elevation models*, Computers & Geosciences 62, 117-127.
  https://doi.org/10.1016/j.cageo.2013.04.024
* **D8** flow routing - O'Callaghan & Mark (1984), *The extraction of drainage
  networks from digital elevation data*, Computer Vision, Graphics and Image
  Processing 28, 323-344.  https://doi.org/10.1016/S0734-189X(84)80011-0
* The **chi transform** - Perron & Royden (2013), *An integral approach to bedrock
  river profile analysis*, Earth Surface Dynamics 1, 45-61.
  https://doi.org/10.5194/esurf-1-45-2013
      chi(x) = integral_{x_b}^{x} ( A0 / A(x') )^(m/n) dx'
* **Normalised channel steepness** - Wobus et al. (2006), *Tectonics from
  topography: procedures, promise, and pitfalls*, GSA Special Paper 398.
  https://doi.org/10.1130/2006.2398(03) ; Kirby & Whipple (2012), *Expression of
  active tectonics in erosional landscapes*, J. Structural Geology 44, 54-75.
  https://doi.org/10.1016/j.jsg.2012.07.009
  In chi-space the slope dz/dchi *is* the normalised steepness ksn = (U/K)^(1/n).

Every function is deterministic.  ``tests/test_hydro.py`` checks the routing, the
accumulation and the chi transform against independent brute-force
implementations on small random DEMs.
"""

from __future__ import annotations

import heapq

import numpy as np

# 8-neighbourhood: (dy, dx)
_OFFSETS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
SQRT2 = 1.4142135623730951


def neighbour_step(delta: np.ndarray, width: int) -> np.ndarray:
    """Distance in pixels for a flat-index difference ``delta = down - i``.

    |delta| is 1 (E/W), ``width`` (N/S), or ``width +/- 1`` (diagonals); 0 for an
    outlet (self-loop).  Anything else is a bug in the caller.
    """
    a = np.abs(delta)
    out = np.zeros(delta.shape, dtype=np.float64)
    out[(a == 1) | (a == width)] = 1.0
    out[(a == width - 1) | (a == width + 1)] = SQRT2
    return out


def fill_depressions(dem: np.ndarray, valid: np.ndarray):
    """Priority-flood depression filling (Barnes et al. 2014).

    Returns ``(filled, is_filled)``.  ``is_filled`` marks cells raised by the
    fill; a large connected filled flat is the floor of an internal-drainage
    basin (playa) - see :func:`closed_basin_flats`.
    """
    h, w = dem.shape
    dem = np.asarray(dem, dtype=np.float64)
    filled = dem.copy()
    is_filled = np.zeros((h, w), dtype=bool)

    valid = np.asarray(valid, dtype=bool)
    border = valid & (
        ~np.roll(valid, 1, 0) | ~np.roll(valid, -1, 0)
        | ~np.roll(valid, 1, 1) | ~np.roll(valid, -1, 1)
    )
    border[0, :] = valid[0, :]
    border[-1, :] = valid[-1, :]
    border[:, 0] = valid[:, 0]
    border[:, -1] = valid[:, -1]

    visited = np.zeros((h, w), dtype=bool)
    heap: list[tuple[float, int]] = []
    ys, xs = np.nonzero(border)
    for y, x in zip(ys.tolist(), xs.tolist()):
        heap.append((float(dem[y, x]), y * w + x))
        visited[y, x] = True
    heapq.heapify(heap)

    zvals = dem[valid]
    zmin = float(zvals.min())
    zmax = float(zvals.max())
    eps = max(1e-4, 1e-8 * (zmax - zmin))

    push, pop = heapq.heappush, heapq.heappop
    filled_flat = filled.ravel()
    isf_flat = is_filled.ravel()
    visited_flat = visited.ravel()
    valid_flat = valid.ravel()

    while heap:
        z, idx = pop(heap)
        y = idx // w
        x = idx - y * w
        for dy, dx in _OFFSETS:
            ny, nx = y + dy, x + dx
            if ny < 0 or ny >= h or nx < 0 or nx >= w:
                continue
            nidx = ny * w + nx
            if visited_flat[nidx] or not valid_flat[nidx]:
                continue
            visited_flat[nidx] = True
            nz = filled_flat[nidx]
            if nz <= z:
                nz = z + eps
                filled_flat[nidx] = nz
                isf_flat[nidx] = True
            push(heap, (nz, nidx))
    return filled, is_filled


def d8_flow_directions(filled: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Steepest-descent receiver as a flat index; self-loop where there is none."""
    h, w = filled.shape
    n = h * w
    best = np.zeros((h, w), dtype=np.float64)
    down = np.arange(n, dtype=np.int64).reshape(h, w)
    for dy, dx in _OFFSETS:
        dpx = SQRT2 if (dy != 0 and dx != 0) else 1.0
        yn = np.arange(h)[:, None] + dy
        xn = np.arange(w)[None, :] + dx
        # in-bounds AND a valid neighbour: flow may never enter a nodata cell
        ok = (yn >= 0) & (yn < h) & (xn >= 0) & (xn < w)
        yc = np.clip(yn, 0, h - 1)
        xc = np.clip(xn, 0, w - 1)
        ok = ok & valid[yc, xc]
        zn = filled[yc, xc]
        drop = np.where(ok, (filled - zn) / dpx, -np.inf)
        upd = drop > best
        best = np.where(upd, drop, best)
        nidx = yc * w + xc
        down = np.where(upd & ok, nidx, down)
    vflat = valid.ravel()
    down = down.ravel()
    down[~vflat] = np.arange(n)[~vflat]
    down[best.ravel() <= 0] = np.arange(n)[best.ravel() <= 0]
    return down


def bfs_levels(down: np.ndarray, valid: np.ndarray):
    """Level-order sweep outward from the outlets along the reversed network.

    Returns ``(dist, levels)`` where ``dist`` is the integer number of steps to
    the outlet and ``levels[d]`` is the flat index array of the cells at that
    distance.  Every valid cell is visited exactly once.
    """
    n = down.size
    i = np.arange(n)
    v = valid.ravel()
    outlets = v & ((down == i) | ~v[down])

    order = np.argsort(down[v], kind="stable")
    src = i[v][order]
    tgt = down[v][order]
    counts = np.bincount(tgt, minlength=n)
    starts = np.zeros(n + 1, dtype=np.int64)
    np.cumsum(counts, out=starts[1:])

    dist = np.full(n, -1, dtype=np.int64)
    frontier = np.nonzero(outlets)[0]
    dist[frontier] = 0
    levels = []
    while frontier.size:
        levels.append(frontier)
        rep = counts[frontier]
        tot = int(rep.sum())
        if tot == 0:
            break
        # CSR gather: block t of the output starts at output position
        # out_start[t] and at CSR position starts[frontier[t]].
        block_start = np.repeat(starts[frontier], rep)
        out_start = np.concatenate([[0], np.cumsum(rep)[:-1]])
        offs = np.arange(tot, dtype=np.int64) - np.repeat(out_start, rep)
        idx = block_start + offs
        nxt = src[idx]
        nxt = nxt[dist[nxt] < 0]
        if nxt.size == 0:
            break
        dist[nxt] = len(levels)
        frontier = np.unique(nxt)
    return dist, levels


def flow_accumulation(down: np.ndarray, valid: np.ndarray, levels=None) -> np.ndarray:
    """Number of cells (including itself) that drain through each cell.

    Exact: cells are pushed to their receiver level by level, deepest first, so
    a receiver always has its full upstream total before it is pushed onward.
    Verified against a topological brute force in ``tests/test_hydro.py``.
    """
    n = down.size
    v = valid.ravel()
    if levels is None:
        _, levels = bfs_levels(down, v)
    acc = np.ones(n, dtype=np.float64)
    acc[~v] = 0.0
    for d in range(len(levels) - 1, -1, -1):
        cells = levels[d]
        if d == 0:
            break
        np.add.at(acc, down[cells], acc[cells])
    acc[~v] = 0.0
    return acc


def chi_transform(down, acc, valid, shape, theta=0.45, a0=1.0, step_m=100.0, levels=None):
    """chi from each cell's outlet.  See module docstring for the definition."""
    n = down.size
    v = valid.ravel()
    if levels is None:
        _, levels = bfs_levels(down, v)
    i = np.arange(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        inc = (a0 / np.maximum(acc, 1.0)) ** theta * neighbour_step(down - i, shape[1]) * step_m
    inc = np.where(v, inc, 0.0)
    chi = np.zeros(n, dtype=np.float64)
    for d in range(1, len(levels)):
        cells = levels[d]
        chi[cells] = chi[down[cells]] + inc[cells]
    return chi.reshape(shape)


def closed_basin_flats(dem, valid, down, acc, min_flat_px=200, max_drainage_px=200_000):
    """Identify internal-drainage flats (playa floors) - a *named confound*.

    A playa is the terminus of an internally drained basin: its base level is set
    by evaporation, not by regional incision, so it manufactures base-level steps
    (knickpoints) with no tectonic cause.  Operationally we call a cell part of a
    playa-ish flat when it is (a) inside a priority-flood-depression-flat, and
    (b) its drainage accumulation exceeds ``min_flat_px`` - i.e. a real basin
    drains to it - while (c) it is not part of a through-flowing trunk system
    (accumulation below ``max_drainage_px``).
    """
    from scipy import ndimage

    filled, is_filled = fill_depressions(dem, valid)
    flat = is_filled & (filled == np.maximum(filled, filled))  # raised cells
    # depression floors: raised cells + the original minimum of each depression
    lab, n = ndimage.label(is_filled, structure=np.ones((3, 3), bool))
    out = np.zeros(dem.shape, bool)
    if n == 0:
        return out
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    acc2 = acc
    for k in range(1, n + 1):
        if sizes[k] < min_flat_px:
            continue
        m = lab == k
        if acc2[m].max() > max_drainage_px:
            continue
        out |= m
    return out
