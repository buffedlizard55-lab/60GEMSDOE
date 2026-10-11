"""10 m channel-steepness kernels and their exact reduction to the 100 m grid.

Lane: channel steepness and knickpoints (Kirby & Whipple 2012, JGR 117, F04002;
Perron & Royden 2013, ESPL 38, 570-576; Gailleton et al. 2019, ESurf 7, 211-230).

Pipeline for one block (all deterministic, no labels anywhere):

1. ``gems52.lane_hydro._priority_flood_full`` (shared template kernel) fills the
   10 m DEM and returns the D8 parent of every cell plus the pop order.
2. ``gems52.lane_hydro._accumulate`` gives contributing area in cells.
3. :func:`chi_true` integrates ``chi = sum ds (A0/A)^theta`` with the true D8
   step length (the same fix that was landed in the shared ``_chi``).
4. :func:`main_donor` picks, for every channel cell, the upstream channel
   neighbour with the largest area (the main-stem walk used before segmenting
   ``z(chi)``).
5. :func:`edge_contamination` flags every cell whose catchment touches the
   block boundary: its area -- hence chi -- is truncated, so it is excluded.
6. :func:`chi_steps` measures, at every channel cell, the steepness of the
   ``L``-cell reach upstream and the ``L``-cell reach downstream as the slope of
   ``z`` against ``chi`` (``ksn = dz/dchi`` with ``A0 = 1 m^2``; Perron & Royden
   2013 eq. 8).  The *steepness step* is ``log((ksn_up + f)/(ksn_down + f))``,
   winsorised at ``log 10`` -- the same declared statistic as the 100 m run
   (H60-A: 500 m windows, floor 0.5, winsor log 10), now on a 10 m network.
   A positive step = steeper upstream (footwall reach above a fault crossing);
   a negative step = steeper downstream (a migrating knickpoint's lower limb).
7. :func:`reduce_to_100m` aggregates the core of the block, 10x10 fine cells per
   competition pixel, keeping only uncontaminated, unfilled channel cells.

Declared approximation: a fixed-window two-segment slope in chi-space is a
reproducible stand-in for the full TVD segmentation of Gailleton et al. (2019);
it is labelled as an approximation, never as their method.
"""
from __future__ import annotations

import numpy as np
from numba import njit

THETA_REF = 0.45          # reference concavity (Kirby & Whipple 2012 review range 0.35-0.6)
A0_M2 = 1.0               # chi reference area -> ksn in m^(2 theta)
A_CHANNEL_M2 = 2.0e5      # 0.2 km^2: same channel threshold as the 100 m H60-A run
WINDOW_M = 500.0          # same 500 m reach as H60-A (5 cells at 100 m -> 50 cells at 10 m)
STEP_FLOOR_KSN = 0.5      # H60-A declared floor
STEP_WINSOR = float(np.log(10.0))
KNICK_MIN = float(np.log(2.0))   # |step| >= log 2 (a 2x steepness change) to count a knickpoint
FILL_RAISE_M = 1.0        # a 10 m cell raised > 1 m by filling is a pit/flat/playa floor
SIG_STEPS_M = 500.0       # branch signature: the cell 500 m downstream (H60-A independence)


@njit(cache=True)
def chi_true(parent, order, acc, theta, a0_m2, cell_m, width):
    n = parent.shape[0]
    chi = np.zeros(n, dtype=np.float64)
    cell2 = cell_m * cell_m
    diag = cell_m * np.sqrt(2.0)
    for t in range(order.shape[0]):
        i = order[t]
        p = parent[i]
        if p >= 0:
            ds = cell_m
            if (i // width) != (p // width) and (i % width) != (p % width):
                ds = diag
            chi[i] = chi[p] + ds * (a0_m2 / (acc[i] * cell2)) ** theta
    return chi


@njit(cache=True)
def main_donor(parent, order, acc, is_chan):
    n = parent.shape[0]
    donor = np.full(n, -1, dtype=np.int64)
    best = np.full(n, -1.0, dtype=np.float64)
    for t in range(order.shape[0]):
        i = order[t]
        p = parent[i]
        if p >= 0 and is_chan[i] and is_chan[p]:
            if acc[i] > best[p]:
                best[p] = acc[i]
                donor[p] = i
    return donor


@njit(cache=True)
def edge_contamination(parent, order, height, width, zf):
    """True where the catchment may extend beyond the block.

    The priority flood seeds every boundary cell as an outlet (parent -1), so a
    stream that *enters* the block never appears upstream of anything in the
    parent graph.  Inflow is therefore detected explicitly: an inner-ring cell
    with a higher boundary neighbour may receive water from outside the block
    and is flagged; the flag is then pushed downstream through the parent
    graph, so every cell whose area could be truncated is excluded.
    """
    n = parent.shape[0]
    bad = np.zeros(n, dtype=np.bool_)
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if not (y == 1 or x == 1 or y == height - 2 or x == width - 2):
                continue
            i = y * width + x
            zi = zf[i]
            if not np.isfinite(zi):
                continue
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    yy = y + dy
                    xx = x + dx
                    if yy == 0 or xx == 0 or yy == height - 1 or xx == width - 1:
                        zb = zf[yy * width + xx]
                        if (not np.isfinite(zb)) or zb > zi:
                            bad[i] = True
    for y in range(height):
        for x in range(width):
            if y == 0 or x == 0 or y == height - 1 or x == width - 1:
                bad[y * width + x] = True
    # reverse pop order = upstream first: push the flag downstream
    for t in range(order.shape[0] - 1, -1, -1):
        i = order[t]
        p = parent[i]
        if p >= 0 and bad[i]:
            bad[p] = True
    return bad


@njit(cache=True)
def chi_steps(zf, chi, parent, donor, is_chan, nwin, floor, winsor):
    """Upstream/downstream chi-space slopes and the log steepness step."""
    n = parent.shape[0]
    step = np.full(n, np.nan, dtype=np.float64)
    ksn_up = np.full(n, np.nan, dtype=np.float64)
    ksn_dn = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        if not is_chan[i]:
            continue
        j = i
        k = 0
        while k < nwin:
            q = parent[j]
            if q < 0:
                break
            j = q
            k += 1
        if k < nwin:
            continue
        jd = j
        j = i
        k = 0
        while k < nwin:
            q = donor[j]
            if q < 0:
                break
            j = q
            k += 1
        if k < nwin:
            continue
        ju = j
        dchi_u = chi[ju] - chi[i]
        dchi_d = chi[i] - chi[jd]
        if dchi_u <= 0.0 or dchi_d <= 0.0:
            continue
        ku = (zf[ju] - zf[i]) / dchi_u
        kd = (zf[i] - zf[jd]) / dchi_d
        ksn_up[i] = ku
        ksn_dn[i] = kd
        r = (max(ku, 0.0) + floor) / (max(kd, 0.0) + floor)
        s = np.log(max(r, 1e-6))
        if s > winsor:
            s = winsor
        if s < -winsor:
            s = -winsor
        step[i] = s
    return step, ksn_up, ksn_dn


@njit(cache=True)
def downstream_index(parent, nsteps):
    n = parent.shape[0]
    out = np.empty(n, dtype=np.int64)
    for i in range(n):
        j = i
        for _ in range(nsteps):
            q = parent[j]
            if q < 0:
                break
            j = q
        out[i] = j
    return out


@njit(cache=True)
def reduce_to_100m(step, ksn_up, ksn_dn, is_chan, ok, sig_fine, logA, zf, raised,
                   width, r0, c0, nr, nc, f, gy0, gx0, gw):
    """Aggregate the fine core [r0:r0+nr*f, c0:c0+nc*f] to nr x nc coarse cells.

    ``sig_fine`` holds fine flat indices; they are converted to the *global*
    100 m flat index via the block's global origin (gy0, gx0) and grid width gw.
    """
    step_max = np.full((nr, nc), np.nan, dtype=np.float32)
    step_min = np.full((nr, nc), np.nan, dtype=np.float32)
    ksn_max = np.full((nr, nc), np.nan, dtype=np.float32)
    loga_at = np.full((nr, nc), np.nan, dtype=np.float32)
    sig_at = np.full((nr, nc), -1, dtype=np.int32)
    chan_n = np.zeros((nr, nc), dtype=np.int32)
    knick_n = np.zeros((nr, nc), dtype=np.int32)
    raised_n = np.zeros((nr, nc), dtype=np.int32)
    valid_n = np.zeros((nr, nc), dtype=np.int32)
    zsum = np.zeros((nr, nc), dtype=np.float64)
    best_abs = np.full((nr, nc), -1.0, dtype=np.float64)
    for a in range(nr):
        for b in range(nc):
            for u in range(f):
                for v in range(f):
                    y = r0 + a * f + u
                    x = c0 + b * f + v
                    i = y * width + x
                    if np.isfinite(zf[i]):
                        valid_n[a, b] += 1
                        zsum[a, b] += zf[i]
                    if raised[i]:
                        raised_n[a, b] += 1
                    if not (is_chan[i] and ok[i]):
                        continue
                    chan_n[a, b] += 1
                    s = step[i]
                    if not np.isfinite(s):
                        continue
                    km = max(ksn_up[i], ksn_dn[i])
                    if np.isnan(ksn_max[a, b]) or km > ksn_max[a, b]:
                        ksn_max[a, b] = km
                    if np.isnan(step_max[a, b]) or s > step_max[a, b]:
                        step_max[a, b] = s
                    if np.isnan(step_min[a, b]) or s < step_min[a, b]:
                        step_min[a, b] = s
                    if abs(s) >= 0.6931471805599453:
                        knick_n[a, b] += 1
                    if abs(s) > best_abs[a, b]:
                        best_abs[a, b] = abs(s)
                        loga_at[a, b] = logA[i]
                        j = sig_fine[i]
                        jy = j // width
                        jx = j - jy * width
                        gy = gy0 + (jy - r0) // f
                        gx = gx0 + (jx - c0) // f
                        sig_at[a, b] = gy * gw + gx
    zmean = np.full((nr, nc), np.nan, dtype=np.float32)
    for a in range(nr):
        for b in range(nc):
            if valid_n[a, b] > 0:
                zmean[a, b] = zsum[a, b] / valid_n[a, b]
    return step_max, step_min, ksn_max, loga_at, sig_at, chan_n, knick_n, raised_n, valid_n, zmean


def run_block(z, cell_m, core_r0, core_c0, nr, nc, f, gy0, gx0, gw,
              theta=THETA_REF, a_channel_m2=A_CHANNEL_M2, window_m=WINDOW_M):
    """Full 10 m stack for one block -> dict of 100 m core arrays + diagnostics."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from gems52 import lane_hydro as HY

    H, W = z.shape
    valid = np.isfinite(z) & (z > -500.0)
    z64 = np.ascontiguousarray(np.where(valid, z, np.nan).astype(np.float64))
    filled, parent, order = HY._priority_flood_full(z64, np.ascontiguousarray(valid))
    acc = HY._accumulate(parent, order)
    zf = filled.copy()
    zf[~valid.ravel()] = np.nan
    raised = valid.ravel() & ((filled - z64.ravel()) > FILL_RAISE_M)
    chi = chi_true(parent, order, acc, float(theta), A0_M2, float(cell_m), int(W))
    area = acc * cell_m * cell_m
    is_chan = valid.ravel() & (area >= a_channel_m2) & ~raised
    donor = main_donor(parent, order, acc, is_chan)
    bad = edge_contamination(parent, order, H, W, zf)
    nwin = int(round(window_m / cell_m))
    step, ku, kd = chi_steps(zf, chi, parent, donor, is_chan, nwin,
                             STEP_FLOOR_KSN, STEP_WINSOR)
    sig = downstream_index(parent, int(round(SIG_STEPS_M / cell_m)))
    ok = ~bad
    logA = np.log10(np.maximum(area, 1.0))
    out = reduce_to_100m(step, ku, kd, is_chan, ok, sig, logA, zf, raised,
                         W, core_r0, core_c0, nr, nc, f, gy0, gx0, gw)
    names = ("step_max", "step_min", "ksn_max", "loga_at", "sig_at", "chan_n",
             "knick_n", "raised_n", "valid_n", "zmean")
    res = dict(zip(names, out))
    core = np.zeros((H, W), bool)
    core[core_r0:core_r0 + nr * f, core_c0:core_c0 + nc * f] = True
    cflat = core.ravel()
    diag = dict(cells=int(H * W), valid=int(valid.sum()),
                raised=int(raised.sum()), channel=int(is_chan.sum()),
                channel_core=int((is_chan & cflat).sum()),
                channel_core_ok=int((is_chan & cflat & ok).sum()),
                contaminated_core_channel=int((is_chan & cflat & bad).sum()),
                step_defined_core=int((np.isfinite(step) & cflat & ok).sum()),
                max_acc_cells=float(acc.max()), nwin=nwin)
    return res, diag
