"""Tectonic-geomorphology lane: channel steepness, the chi transform, knickpoints, and the
strike-coherence test across independent drainages.

Method references (peer-reviewed; each is cited where it is implemented):

  * Kirby, E. & Whipple, K. X. (2012), "Expression of active tectonics in erosional landscapes",
    Journal of Structural Geology 44, 54-75.  -- normalized channel steepness k_sn = S * A**theta,
    and its use to read spatial gradients in rock uplift, including across active normal faults.
  * Perron, J. T. & Royden, L. (2013), "An integral approach to bedrock river profile analysis",
    Earth Surface Processes and Landforms 38, 570-576.  -- the chi transform
    chi(x) = integral_{x_b}^{x} (A0 / A(x'))**theta dx', putting channels that drain to different
    base levels on a common footing.
  * Gailleton, B., Mudd, S. M., Clubb, F. J., Peifer, D. & Hurst, M. D. (2019), "A segmentation
    approach for the reproducible extraction and quantification of knickpoints from river long
    profiles", Earth Surface Dynamics 7, 211-230. https://doi.org/10.5194/esurf-7-211-2019 --
    piecewise segmentation of the channel profile rather than one global S-A fit.
  * Wobus, C. et al. (2006), GSA Special Paper 398, "Tectonics from topography: procedures,
    promise, and pitfalls".  -- the confound list this module masks.
  * Barnes, R., Lehman, C. & Mulla, D. (2014), Computers & Geosciences 62, 117-127.  --
    Priority-Flood depression filling (epsilon variant, so flats drain).

The lane's mandated first test is :func:`orientation_matched_control`: do lines that crossed the
withheld catalogue segments carry larger steepness steps than random lines of the SAME orientation
distribution?  If not, the lane stops -- the prompt says so, and nothing here hides that outcome.
"""

from __future__ import annotations

import numpy as np

try:
    from numba import njit

    HAVE_NUMBA = True
except Exception:  # pragma: no cover
    HAVE_NUMBA = False

    def njit(*a, **k):  # type: ignore
        if a and callable(a[0]):
            return a[0]

        def deco(f):
            return f

        return deco


IDX_BITS = 25                      # 2**25 = 33,554,432 > 12,279,160 grid cells
IDX_MASK = (1 << IDX_BITS) - 1

D8_DY = (-1, -1, -1, 0, 0, 1, 1, 1)
D8_DX = (-1, 0, 1, -1, 1, -1, 0, 1)
_D8_LEN = tuple(np.hypot(dy, dx) for dy, dx in zip(D8_DY, D8_DX))
D8_LEN = np.asarray(_D8_LEN, dtype=np.float64)


# ------------------------------------------------------------------------------------------------
# 1. Priority-Flood + epsilon (Barnes et al. 2014)
# ------------------------------------------------------------------------------------------------
@njit(cache=True, inline="always")
def _heap_push(heap, size, key):
    i = size
    heap[i] = key
    while i > 0:
        parent = (i - 1) >> 1
        if heap[parent] <= heap[i]:
            break
        tmp = heap[parent]
        heap[parent] = heap[i]
        heap[i] = tmp
        i = parent
    return size + 1


@njit(cache=True, inline="always")
def _heap_pop(heap, size):
    top = heap[0]
    size -= 1
    heap[0] = heap[size]
    i = 0
    while True:
        l = 2 * i + 1
        r = l + 1
        smallest = i
        if l < size and heap[l] < heap[smallest]:
            smallest = l
        if r < size and heap[r] < heap[smallest]:
            smallest = r
        if smallest == i:
            break
        tmp = heap[smallest]
        heap[smallest] = heap[i]
        heap[i] = tmp
        i = smallest
    return top, size


@njit(cache=True)
def priority_flood_epsilon(dem, finite, rank, eps):
    """Priority-Flood + epsilon on a cell grid.  Heap keys are (rank << 25) | index: the rank is a
    dense ascending order of the ORIGINAL elevations, so ordering by rank is ordering by elevation
    while tying deterministically (row-major) inside flats."""
    h, w = dem.shape
    n = h * w
    filled = np.full(n, np.nan, dtype=np.float64)
    seen = np.zeros(n, dtype=np.bool_)
    heap = np.empty(n, dtype=np.int64)
    size = 0

    # seed: every finite cell touching the grid border or an invalid cell
    for y in range(h):
        for x in range(w):
            if not finite[y, x]:
                continue
            i = y * w + x
            edge = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    ny = y + dy
                    nx = x + dx
                    if ny < 0 or nx < 0 or ny >= h or nx >= w or not finite[ny, nx]:
                        edge = True
                        break
                if edge:
                    break
            if edge:
                filled[i] = dem[y, x]
                seen[i] = True
                size = _heap_push(heap, size, (rank[i] << IDX_BITS) | i)

    while size > 0:
        key, size = _heap_pop(heap, size)
        i = key & IDX_MASK
        y = i // w
        x = i - y * w
        c = filled[i]
        for k in range(8):
            ny = y + D8_DY[k]
            nx = x + D8_DX[k]
            if ny < 0 or nx < 0 or ny >= h or nx >= w:
                continue
            if not finite[ny, nx]:
                continue
            j = ny * w + nx
            if seen[j]:
                continue
            seen[j] = True
            e = dem[ny, nx]
            if e <= c:
                e = c + eps
            filled[j] = e
            size = _heap_push(heap, size, (rank[j] << IDX_BITS) | j)

    out = np.empty((h, w), dtype=np.float64)
    for y in range(h):
        for x in range(w):
            out[y, x] = filled[y * w + x]
    return out


def fill_depressions(dem: np.ndarray, finite: np.ndarray, eps: float = 1e-3) -> np.ndarray:
    """Depression filling with a documented epsilon.

    ``eps`` is in DEM units (metres for a metre DEM).  1e-3 m keeps the fill numerically resolvable
    in float64 (the DEM has ~1e3 m of relief, so eps is ~6 orders below the signal) while still
    guaranteeing a strictly descending D8 neighbour for every non-edge cell.
    """
    d = np.where(finite, np.asarray(dem, dtype=np.float64), np.nan)
    rank = np.empty(d.size, dtype=np.int64)
    order = np.lexsort((np.arange(d.size, dtype=np.int64), d.ravel()))
    rank[order] = np.arange(d.size, dtype=np.int64)
    filled = priority_flood_epsilon(d, finite, rank, float(eps))
    out = np.where(finite, np.maximum(filled, d), np.nan)
    return out


# ------------------------------------------------------------------------------------------------
# 2. D8 routing, flow accumulation, chi
# ------------------------------------------------------------------------------------------------
@njit(cache=True)
def d8_receivers(filled):
    """Steepest-descent D8 receiver (row-major index) per cell; -1 for edges / sinks / invalid.

    Steepness = drop / distance (so that diagonals are not under-used), which is the standard D8
    slope rule and avoids the well-known bias of using the largest drop in cell counts.
    """
    h, w = filled.shape
    rec = np.full((h, w), -1, dtype=np.int64)
    for y in range(h):
        for x in range(w):
            c = filled[y, x]
            if not (c == c):  # NaN test that numba compiles
                continue
            best = 0.0
            bi = -1
            for k in range(8):
                ny = y + D8_DY[k]
                nx = x + D8_DX[k]
                if ny < 0 or nx < 0 or ny >= h or nx >= w:
                    continue
                n = filled[ny, nx]
                if not (n == n):
                    continue
                drop = (c - n) / D8_LEN[k]
                if drop > best:
                    best = drop
                    bi = ny * w + nx
            rec[y, x] = bi
    return rec


@njit(cache=True)
def accumulate_area(rec_flat, order_desc, cell_area_m2):
    """Exact D8 flow accumulation (m^2) in one descending-elevation sweep.

    Every receiver is strictly lower after epsilon filling, so a cell's total is final before it is
    passed downstream: one pass is exact, no iteration to convergence.
    """
    n = rec_flat.size
    acc = np.full(n, cell_area_m2, dtype=np.float64)
    for k in range(order_desc.size):
        i = order_desc[k]
        r = rec_flat[i]
        if r >= 0:
            acc[r] += acc[i]
    return acc


@njit(cache=True)
def chi_field(rec_flat, acc_flat, order_asc, theta, area0, cell_len_m):
    """Perron & Royden (2013) chi.

        chi(i) = chi(receiver(i)) + (A0 / A(i))**theta * L

    ``order_asc`` walks cells from lowest filled elevation to highest, so a cell's receiver is
    always evaluated first.  Cells with no receiver keep chi = 0: they are their own base level.
    """
    n = rec_flat.size
    chi = np.zeros(n, dtype=np.float64)
    for k in range(order_asc.size):
        i = order_asc[k]
        r = rec_flat[i]
        if r >= 0:
            a = acc_flat[i]
            if a <= 0.0:
                a = area0
            chi[i] = chi[r] + (area0 / a) ** theta * cell_len_m
    return chi


@njit(cache=True)
def count_upstream_channels(rec_flat, chan_flat, order_asc):
    """Number of channel cells that drain directly into each cell (0, 1 or 2; >2 only in
    pathological convergent patterns)."""
    n = rec_flat.size
    n_up = np.zeros(n, dtype=np.int32)
    for k in range(order_asc.size):
        i = order_asc[k]
        if not chan_flat[i]:
            continue
        r = rec_flat[i]
        if r >= 0 and chan_flat[r]:
            n_up[r] += 1
    return n_up


@njit(cache=True)
def first_order_basins(rec_flat, chan_flat, n_up, w):
    """Label first-order channel links (headwater -> first junction) and return them in order.

    A "first-order basin" is the drainage above the first junction: it is the natural unit for the
    lane's requirement that knickpoints "align across several independent drainages", because two
    knickpoints in the same first-order basin are NOT independent evidence.

    Returns (basin_id, cells, offsets) where cells[offsets[b]:offsets[b+1]] lists the cells of
    link b in downstream-to-upstream order.
    """
    n = rec_flat.size
    basin = np.full(n, -1, dtype=np.int32)
    cells = np.empty(n, dtype=np.int64)
    offs = np.empty(n + 1, dtype=np.int64)
    local = np.empty(n, dtype=np.int64)       # hoisted scratch: one allocation, not one per link
    nb = 0
    offs[0] = 0
    k = 0
    for i in range(n):
        if not chan_flat[i]:
            continue
        if n_up[i] != 0:
            continue
        # walk downstream until the first junction (n_up >= 2) or the channel end
        j = i
        m = 0
        while j >= 0:
            local[m] = j
            m += 1
            r = rec_flat[j]
            if r < 0 or not chan_flat[r]:
                j = r if r >= 0 else -1
                break
            if n_up[r] >= 2:
                j = -1
                break
            j = r
        if m < 2:
            continue
        for t in range(m - 1, -1, -1):        # store upstream-first
            cells[k] = local[t]
            basin[local[t]] = nb
            k += 1
        nb += 1
        offs[nb] = k
    return basin, cells[:k], offs[: nb + 1]


def channel_mask(acc: np.ndarray, ac_m2: float) -> np.ndarray:
    return acc >= ac_m2


def slope_horn(z: np.ndarray, cell_m: float) -> np.ndarray:
    """Horn (1981) 3x3 slope magnitude; NaN where the DEM is NaN."""
    p = np.pad(z, 1, mode="edge")
    dzdx = ((p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:])
            - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])) / (8.0 * cell_m)
    dzdy = ((p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:])
            - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])) / (8.0 * cell_m)
    s = np.hypot(dzdx, dzdy)
    s[~np.isfinite(z)] = np.nan
    return s


# ------------------------------------------------------------------------------------------------
# 3. Segmentation of a (chi, z) profile -> knickpoints, and per-segment steepness
# ------------------------------------------------------------------------------------------------
def segment_profile(chi: np.ndarray, z: np.ndarray, window: int = 5, ratio: float = 1.6,
                    min_drop_m: float = 10.0) -> dict:
    """Gailleton et al. (2019)-style segmentation of one channel profile.

    The profile is (chi, z) ordered downstream -> upstream.  For every interior position the local
    gradient dz/dchi is estimated by least squares on ``window`` samples behind and ahead; a
    breakpoint is recorded where the ratio of the two gradients exceeds ``ratio`` AND the elevation
    change across the lead/lag span exceeds ``min_drop_m`` (a materiality floor that removes
    sub-metre breaks produced by DEM noise rather than by base-level steps).

    Returns the breakpoint positions, the per-segment gradients, k_sn per segment (gradient of
    z vs chi IS k_sn when theta = m/n; Perron & Royden 2013), and the mean |d z/d chi| of the profile.
    """
    chi = np.asarray(chi, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    ok = np.isfinite(chi) & np.isfinite(z)
    chi, z = chi[ok], z[ok]
    n = chi.size
    empt = {"positions": np.zeros(0, dtype=np.int64), "slopes": np.zeros(0, dtype=np.float64),
            "breaks": np.zeros(0, dtype=np.float64), "mean_slope": np.nan, "n": n}
    if n < 2 * window + 2:
        return empt
    k = window
    slopes = np.full(n, np.nan)
    for i in range(n):
        lo = max(0, i - k)
        hi = min(n, i + k + 1)
        dc = chi[lo:hi] - chi[lo:hi].mean()
        denom = float((dc * dc).sum())
        if hi - lo >= 3 and denom > 1e-12:
            slopes[i] = float(((dc * (z[lo:hi] - z[lo:hi].mean())).sum()) / denom)
    breaks = []
    for i in range(k, n - k):
        s1 = slopes[i - k]
        s2 = slopes[i + k] if i + k < n else np.nan
        if not (np.isfinite(s1) and np.isfinite(s2)):
            continue
        a1, a2 = abs(s1), abs(s2)
        lo, hi = (a1, a2) if a1 <= a2 else (a2, a1)
        if lo <= 1e-12:
            continue
        if hi / lo >= ratio and abs(z[i + k] - z[i - k]) >= min_drop_m:
            breaks.append(i)
    pos = []
    last = -10 * k
    for i in breaks:
        if i - last > k:
            pos.append(i)
            last = i
    pos = np.asarray(pos, dtype=np.int64)
    seg = []
    edges = np.concatenate([np.asarray([0]), pos, np.asarray([n - 1])])
    for a, b in zip(edges[:-1], edges[1:]):
        if b - a < 2:
            continue
        dc = chi[a:b + 1] - chi[a:b + 1].mean()
        den = float((dc * dc).sum())
        if den > 1e-12:
            seg.append(float(((dc * (z[a:b + 1] - z[a:b + 1].mean())).sum()) / den))
    brk = np.asarray([abs(slopes[i + k] - slopes[i - k]) for i in pos], dtype=np.float64)
    return {"positions": pos, "slopes": np.asarray(seg, dtype=np.float64), "breaks": brk,
            "slope_profile": slopes, "n": n}


# ------------------------------------------------------------------------------------------------
# 4. The lane's mandated first test: withheld segments vs orientation-matched random lines
# ------------------------------------------------------------------------------------------------
def strike_of_segments(truth: np.ndarray, min_px: int = 25) -> np.ndarray:
    """Strike (deg from east, in [0,180)) of every connected truth segment >= min_px pixels.

    Second-moment (principal-axis) orientation of each segment's pixel set: the standard label-free
    line azimuth, no skeletonisation required.
    """
    from scipy import ndimage as ndi

    lab, n = ndi.label(truth, structure=np.ones((3, 3), dtype=int))
    out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if ys.size < min_px:
            continue
        y = ys - ys.mean()
        x = xs - xs.mean()
        cov = np.array([[float((y * y).mean()), float((y * x).mean())],
                        [float((y * x).mean()), float((x * x).mean())]])
        evals, evecs = np.linalg.eigh(cov)
        v = evecs[:, int(np.argmax(evals))]
        out.append(float(np.degrees(np.arctan2(v[0], v[1])) % 180.0))
    return np.asarray(out, dtype=np.float64)


def orientation_matched_lines(strikes_deg: np.ndarray, n_lines: int, length_px: int,
                              shape: tuple[int, int], anchor_yx: np.ndarray,
                              rng: np.random.Generator) -> np.ndarray:
    """Random lines with the SAME orientation distribution as ``strikes_deg``.

    The control required by the lane: if the withheld segments' lines show bigger steepness steps
    than these, the difference cannot be an artefact of orientation.  Anchors are drawn from the
    caller-supplied valid anchor list (truth-pixel centres, say), so the control is also matched on
    starting position.
    """
    h, w = shape
    idx = rng.integers(0, strikes_deg.size, size=n_lines)
    az = np.deg2rad(strikes_deg[idx])
    t = np.arange(length_px, dtype=np.float64) - length_px // 2
    start = rng.integers(0, anchor_yx.shape[0], size=n_lines)
    cy = anchor_yx[start, 0].astype(np.float64)
    cx = anchor_yx[start, 1].astype(np.float64)
    lines = np.empty((n_lines, length_px, 2), dtype=np.int64)
    for j in range(n_lines):
        lines[j, :, 0] = np.clip(np.rint(cy[j] + t * np.sin(az[j])).astype(np.int64), 0, h - 1)
        lines[j, :, 1] = np.clip(np.rint(cx[j] + t * np.cos(az[j])).astype(np.int64), 0, w - 1)
    return lines


def sample_line_steps(field: np.ndarray, lines: np.ndarray) -> np.ndarray:
    """Per-line summary of a steepness-step field: the 90th percentile over the line's pixels.

    A percentile, not a mean, because a 15-pixel line that crosses a fault has a few very large
    values and many small ones; the mean would dilute the very effect the lane is testing for.
    """
    vals = np.empty(lines.shape[0], dtype=np.float64)
    for j in range(lines.shape[0]):
        v = field[lines[j, :, 0], lines[j, :, 1]]
        v = v[np.isfinite(v)]
        vals[j] = float(np.percentile(v, 90)) if v.size else np.nan
    return vals


def paired_bootstrap(diff: np.ndarray, n: int = 4000, seed: int = 0) -> dict:
    """Two-sided paired bootstrap CI and a sign test on the mean of ``diff``."""
    d = np.asarray(diff, dtype=np.float64)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return {"mean": float("nan"), "ci95": [float("nan")] * 2, "n": 0, "frac_positive": float("nan")}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(n, d.size))
    m = d[idx].mean(axis=1)
    return {"mean": float(d.mean()),
            "ci95": [float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))],
            "n": int(d.size), "frac_positive": float((d > 0).mean())}


@njit(cache=True)
def flow_distance(rec_flat, order_asc, cell_len_m):
    """Channel length from each cell to its downstream terminus, in metres.

    ``order_asc`` runs lowest-elevation (downstream) first, so a cell's receiver is always already
    final.  Used for the Hack-law diagnostic that tells whether a DEM supports a real drainage
    network or only noise (a routing sanity check, not a fit).
    """
    n = rec_flat.size
    d = np.zeros(n, dtype=np.float64)
    for k in range(order_asc.size):
        i = order_asc[k]
        r = rec_flat[i]
        if r >= 0:
            d[i] = d[r] + cell_len_m
    return d


def truth_segment_lines(truth: np.ndarray, length_px: int, rng, max_lines: int = 3000,
                        min_px: int = 25) -> tuple[np.ndarray, np.ndarray, int]:
    """The lane's first test, done correctly: truth-strike lines vs orientation-matched control.

    BOTH arms are anchored on the SAME randomly chosen pixels of the withheld truth segments, so the
    only difference between them is azimuth:

      * truth arm   -- each line runs along the OWN principal azimuth of the segment the anchor
                       pixel belongs to (``strike_of_segments``);
      * control arm -- each line draws its azimuth from the whole segment population's strike
                       distribution ("random same-orientation lines" in the lane specification).

    An earlier revision drew BOTH arms from that distribution, which made the two samples
    statistically identical; it "passed" on noise.  Caught in review before any number was used.

    Returns (truth_lines, control_lines, n_lines), each line an (n, 2) array of (y, x) pixels.
    """
    from scipy import ndimage as ndi

    lab, n = ndi.label(truth, structure=np.ones((3, 3), dtype=int))
    segs = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if ys.size >= min_px:
            segs.append((ys, xs))
    empty = np.zeros((0, length_px, 2), dtype=np.int64)
    if not segs:
        return empty, empty, 0
    strikes = strike_of_segments(truth, min_px=min_px)
    if strikes.size == 0:
        return empty, empty, 0
    h, w = truth.shape
    which = rng.integers(0, len(segs), size=max_lines)
    anchors = np.empty((max_lines, 2), dtype=np.int64)
    own_az = np.empty(max_lines, dtype=np.float64)
    for j in range(max_lines):
        ys, xs = segs[int(which[j])]
        k = int(rng.integers(0, ys.size))
        anchors[j, 0], anchors[j, 1] = ys[k], xs[k]
        own_az[j] = strikes[int(which[j])]
    ctrl_az = strikes[rng.integers(0, strikes.size, size=max_lines)]

    def _mk(az_deg: np.ndarray) -> np.ndarray:
        tt = np.arange(length_px, dtype=np.float64) - length_px // 2
        a = np.deg2rad(az_deg)
        lines = np.empty((az_deg.size, length_px, 2), dtype=np.int64)
        lines[:, :, 0] = np.clip(np.rint(anchors[:, 0][:, None] + tt[None, :] * np.sin(a)[:, None]),
                                 0, h - 1).astype(np.int64)
        lines[:, :, 1] = np.clip(np.rint(anchors[:, 1][:, None] + tt[None, :] * np.cos(a)[:, None]),
                                 0, w - 1).astype(np.int64)
        return lines

    return _mk(own_az), _mk(ctrl_az), max_lines
