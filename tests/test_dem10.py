"""Analytic tests for the H65 10 m channel-steepness kernels (src/gems65/dem10.py)."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("numba")
from gems52 import lane_hydro as HY  # noqa: E402
from gems65 import dem10 as D  # noqa: E402


def _stack(z):
    valid = np.isfinite(z)
    filled, parent, order = HY._priority_flood_full(np.ascontiguousarray(z, np.float64), valid)
    acc = HY._accumulate(parent, order)
    return filled, parent, order, acc


def test_chi_true_matches_analytic_on_a_single_column():
    # hand-built chain: one column (width 1) of n cells, row n-1 is the outlet,
    # every other cell drains to the row below it (orthogonal steps of 10 m)
    n = 40
    parent = np.array([r + 1 for r in range(n - 1)] + [-1], np.int64)
    order = np.arange(n - 1, -1, -1, dtype=np.int64)       # outlet popped first
    acc = HY._accumulate(parent, order)
    assert acc[0] == 1 and acc[n - 1] == n
    chi = D.chi_true(parent, order, acc, 0.5, 1.0, 10.0, 1)
    exp = np.zeros(n)
    for row in range(n - 2, -1, -1):
        a_cells = row + 1          # cells at and above this row
        exp[row] = exp[row + 1] + 10.0 * (1.0 / (a_cells * 100.0)) ** 0.5
    assert np.allclose(chi, exp)


def test_chi_true_uses_diagonal_length():
    # a 2x2 grid where the top-left cell can only step diagonally is hard to force;
    # check the shared-tool fix directly instead: diagonal parent -> sqrt(2) * cell
    parent = np.array([-1, -1, -1, 0], np.int64)          # cell 3 (1,1) -> cell 0 (0,0)
    order = np.array([0, 1, 2, 3], np.int64)
    acc = np.ones(4)
    chi = D.chi_true(parent, order, acc, 0.0, 1.0, 10.0, 2)
    assert chi[3] == pytest.approx(10.0 * np.sqrt(2.0))
    chi_shared = HY._chi(parent, order, acc, 0.0, 1.0, 10.0, 2)
    assert chi_shared[3] == pytest.approx(10.0 * np.sqrt(2.0))
    legacy = HY._chi(parent, order, acc, 0.0, 1.0, 10.0, 0)
    assert legacy[3] == pytest.approx(10.0)


def test_step_is_positive_where_a_steep_reach_overlies_a_gentle_one():
    # a valley draining south; rows < 100 ("footwall") are 6x steeper than rows >= 100
    H, W = 200, 41
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    along = np.where(yy < 100, 6.0 * (100 - yy) + 100.0, 1.0 * (200 - yy))
    z = along + 0.5 * np.abs(xx - 20)          # V-shaped valley centred on column 20
    filled, parent, order, acc = _stack(z)
    chi = D.chi_true(parent, order, acc, 0.45, 1.0, 10.0, W)
    area = acc * 100.0
    is_chan = area >= 3000.0
    donor = D.main_donor(parent, order, acc, is_chan)
    step, ku, kd = D.chi_steps(filled, chi, parent, donor, is_chan, 10, 0.5, np.log(10.0))
    s = step.reshape(H, W)
    # on the valley axis, the step peaks at the slope break and is positive there
    axis = s[:, 20]
    finite = np.isfinite(axis)
    assert finite.sum() > 20
    near = axis[95:106]
    far = axis[150:180]
    assert np.nanmax(near) > 0.5
    assert np.nanmax(near) > np.nanmax(np.abs(far[np.isfinite(far)])) + 0.3


def test_edge_contamination_spares_catchments_inside_the_block():
    # a cone: cells near the summit have catchments that never reach the boundary
    H = W = 61
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    z = 1000.0 - np.hypot(yy - 30, xx - 30)
    filled, parent, order, acc = _stack(z)
    bad = D.edge_contamination(parent, order, H, W, filled).reshape(H, W)
    assert not bad[30, 30]
    assert not bad[25, 30]
    assert bad[0, :].all() and bad[:, 0].all()


def test_edge_contamination_flags_a_stream_entering_the_block():
    # a valley entering from the north edge and leaving at the south edge:
    # its whole axis has a truncated catchment and must be flagged
    H, W = 80, 41
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    z = 2.0 * (H - yy) + 0.5 * np.abs(xx - 20)
    filled, parent, order, acc = _stack(z)
    bad = D.edge_contamination(parent, order, H, W, filled).reshape(H, W)
    assert bad[1:-1, 20].all()


def test_reduce_to_100m_counts_and_signature_are_global():
    f = 2
    H, W = 4, 4          # core = whole block, 2x2 coarse cells
    n = H * W
    step = np.full(n, np.nan)
    step[0] = 1.0        # coarse (0,0)
    step[15] = -2.0      # coarse (1,1)
    is_chan = np.zeros(n, bool)
    is_chan[[0, 15]] = True
    ok = np.ones(n, bool)
    sig = np.arange(n, dtype=np.int64)
    out = D.reduce_to_100m(step, np.ones(n), np.ones(n), is_chan, ok, sig, np.zeros(n),
                           np.zeros(n), np.zeros(n, bool), W, 0, 0, 2, 2, f, 10, 20, 100)
    step_max, step_min, ksn_max, loga, sig_at, chan_n, knick_n, raised_n, valid_n, zmean = out
    assert step_max[0, 0] == 1.0 and step_min[1, 1] == -2.0
    assert np.isnan(step_max[0, 1])
    assert chan_n.sum() == 2 and knick_n.sum() == 2
    assert sig_at[0, 0] == 10 * 100 + 20
    assert sig_at[1, 1] == 11 * 100 + 21
    assert (valid_n == 4).all()
