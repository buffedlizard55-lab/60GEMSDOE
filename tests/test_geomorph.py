"""Unit tests for the tectonic-geomorphology lane primitives.

Every test here is an *algorithm/physics* check whose answer is known
independently of the implementation: a tilted plane must route to its lowest
edge, a pit must be filled to its spill elevation, an endorheic basin must be
seeded rather than raised to its rim, ``chi`` must be monotonic upstream and
match the closed form for a plane, ``ksn`` must equal ``S*A^theta``, and the
drainage identity must never merge two separate basins.
"""
from __future__ import annotations

import numpy as np
import pytest

from gems60 import geomorph as gm


def _plane(h=40, w=40, dip=0.01, pit=None, pit_depth=30.0):
    y, x = np.mgrid[0:h, 0:w].astype(float)
    z = dip * gm.CELL_M * y           # dips "south" = increasing row index
    if pit is not None:
        py, px = pit
        r = np.hypot(y - py, x - px)
        z -= pit_depth * np.exp(-(r ** 2) / 8.0)
    return z


def test_priority_flood_fills_pit_to_spill_and_leaves_no_pit_behind():
    z = _plane(pit=(20, 20))
    dom = np.ones(z.shape, bool)
    zf, stats = gm.priority_flood(z, dom)
    assert (zf >= z - 1e-9).all(), "fill must never lower a cell"
    assert stats["closed"] == stats["cells"], "every domain cell must be processed"
    assert zf[20, 20] > z[20, 20] + 1.0, "the pit centre must be raised"
    pad = np.pad(zf, 1, mode="edge")
    nbmin = np.minimum.reduce([pad[0:-2, 0:-2], pad[0:-2, 1:-1], pad[0:-2, 2:],
                               pad[1:-1, 0:-2], pad[1:-1, 2:],
                               pad[2:, 0:-2], pad[2:, 1:-1], pad[2:, 2:]])
    interior = np.zeros(z.shape, bool)
    interior[1:-1, 1:-1] = True
    assert not ((zf < nbmin - 1e-9) & interior).any(), "no pits may survive the fill"


def test_priority_flood_does_not_alter_a_monotone_surface():
    z = _plane(h=25, w=25, dip=0.03)
    zf, stats = gm.priority_flood(z, np.ones(z.shape, bool))
    assert stats["raised"] == 0
    assert np.allclose(zf, z, atol=1e-9)


def test_nan_walled_pocket_is_reached_by_a_restart_wave():
    """A pocket walled off by no-data cells cannot be reached from the footprint
    edge, so the flood must stall and re-seed it instead of silently skipping
    it (3,061 such cells exist inside the real footprint)."""
    h = w = 41
    y, x = np.mgrid[0:h, 0:w].astype(float)
    r = np.hypot(y - 20, x - 20)
    z = 200.0 + 2.0 * y
    z = np.where(r < 10, 100.0 + 0.5 * r, z)      # a pocket 100 m below its rim
    dom = np.ones(z.shape, bool)
    ring = (r >= 10) & (r < 11.5)                # no-data wall around the pocket
    z = np.where(ring, np.nan, z)
    zf, stats = gm.priority_flood(z, dom)
    assert stats["waves"] >= 1, "a walled-off pocket must trigger a restart wave"
    assert stats["closed"] == stats["cells"], "every cell must still be processed"
    assert zf[20, 20] < 199.0, "the pocket floor must be seeded, not raised to the rim"


def test_d8_and_area_on_a_plane_route_to_the_low_edge():
    z = _plane(h=30, w=30, dip=0.02)
    dom = np.ones(z.shape, bool)
    zf, _ = gm.priority_flood(z, dom)
    code = gm.d8_dircode(zf, dom)
    recv = gm.d8_receivers(code)
    acc, level = gm.upslope_area(code, dom)
    ys, xs = np.nonzero(dom & (recv >= 0))
    ry, _ = np.divmod(recv[ys, xs], z.shape[1])
    assert (ry <= ys).all(), "flow must go to lower elevation (smaller row index)"
    assert (recv[0] == -1).all(), "the lowest row (row 0) must be the outlet row"
    assert acc.max() == pytest.approx(30.0), "max area = full plane width"
    assert level.max() >= 25
    # every cell must have exactly one receiver inside the domain
    assert ((recv[dom] == -1) | ((recv[dom] >= 0) & (recv[dom] < z.size))).all()


def test_chi_closed_form_on_a_single_row_chain():
    # 1 x n plane dipping towards column 0: A(x) = x+1 cells, exact partial sum
    n = 25
    z = (0.02 * gm.CELL_M * np.arange(n)).reshape(1, n)
    dom = np.ones(z.shape, bool)
    zf, _ = gm.priority_flood(z, dom)
    code = gm.d8_dircode(zf, dom)
    acc, level = gm.upslope_area(code, dom)
    chi = gm.chi_field(acc, code, dom, level)
    # the outlet is column 0 (lowest elevation): it collects the whole chain
    assert acc[0, 0] == pytest.approx(float(n))
    assert acc[0, n - 1] == pytest.approx(1.0)
    for k in range(1, n):
        # A(cell j) = (n - j) cells, so chi is an exact partial sum from the outlet
        expect = sum(gm.CELL_M * (gm.A0_M2 / ((n - j) * gm.CELL_M ** 2)) ** gm.THETA_REF
                     for j in range(1, k + 1))
        assert chi[0, k] == pytest.approx(expect, rel=1e-9)


def test_chi_is_monotonic_upstream_and_matches_the_closed_form_on_a_plane():
    z = _plane(h=30, w=30, dip=0.02)
    dom = np.ones(z.shape, bool)
    zf, _ = gm.priority_flood(z, dom)
    code = gm.d8_dircode(zf, dom)
    recv = gm.d8_receivers(code)
    acc, level = gm.upslope_area(code, dom)
    chi = gm.chi_field(acc, code, dom, level)
    ch = np.isfinite(chi)
    ys, xs = np.nonzero(dom & (recv >= 0) & ch)
    ry, rx = np.divmod(recv[ys, xs], z.shape[1])
    assert (chi[ys, xs] > chi[ry, rx]).all(), "chi must increase upstream"
    # row k of a plane whose outlet row is 0 has A = (H - k) cells, so the exact
    # discrete chi is the partial sum of ds*(A0/A)^theta over the path
    H, W = z.shape
    for k in (1, 5, 20):
        # row 0 is the outlet (chi = 0 by definition, Perron & Royden 2013);
        # A(row j) = (H - j) cells of the column draining through it
        expect = sum(gm.CELL_M * (gm.A0_M2 / ((H - j) * gm.CELL_M ** 2)) ** gm.THETA_REF
                     for j in range(1, k + 1))
        assert chi[k, 15] == pytest.approx(expect, rel=1e-9)


def test_ksn_equals_slope_times_area_to_theta():
    z = _plane(h=30, w=30, dip=0.02)
    dom = np.ones(z.shape, bool)
    zf, _ = gm.priority_flood(z, dom)
    code = gm.d8_dircode(zf, dom)
    acc, level = gm.upslope_area(code, dom)
    ksn = gm.ksn_local(zf, acc, code, dom)
    expect = 0.02 * (acc[10, 15] * gm.CELL_M ** 2 / gm.A0_M2) ** gm.THETA_REF
    assert ksn[10, 15] == pytest.approx(expect, rel=1e-9)


def test_drainage_identity_separates_two_basins():
    h = w = 40
    y, x = np.mgrid[0:h, 0:w].astype(float)
    # a ridge down the middle column and a gentle slope to the middle row: two
    # independent basins draining to the west and east array edges
    z = 0.02 * gm.CELL_M * np.abs(y - h / 2) - 0.05 * gm.CELL_M * np.abs(x - w / 2)
    dom = np.ones(z.shape, bool)
    zf, _ = gm.priority_flood(z, dom)
    code = gm.d8_dircode(zf, dom)
    term = gm.drainage_identity(code, dom)
    left = set(np.unique(term[:, 2:15]).tolist())
    right = set(np.unique(term[:, 25:38]).tolist())
    assert left and right and not (left & right), "separate basins must not share a terminal id"
    assert len(left) <= 4 and len(right) <= 4, "one basin must collapse to few terminal ids"


def test_main_stem_donor_picks_the_largest_tributary():
    h = w = 21
    y, x = np.mgrid[0:h, 0:w].astype(float)
    # a V-shaped valley: two symmetric arms join at the centre column
    z = 0.05 * gm.CELL_M * (np.abs(x - 10) + y * 0.0)
    z += 0.01 * gm.CELL_M * y
    dom = np.ones(z.shape, bool)
    zf, _ = gm.priority_flood(z, dom)
    code = gm.d8_dircode(zf, dom)
    acc, _ = gm.upslope_area(code, dom)
    channel = acc >= 3
    donor, has = gm.main_stem_donor(code, acc, channel)
    ys, xs = np.nonzero(channel & has)
    # every donor must itself be a channel cell that flows into the target
    recv = gm.d8_receivers(code)
    dy, dx = np.divmod(donor[ys, xs], w)
    assert (recv[dy, dx] == ys * w + xs).all(), "donor must flow into the cell"
    assert channel.ravel()[donor[ys, xs]].all()


def test_window_means_recovers_a_step_function_on_a_synthetic_path():
    # a 1-D chain: cell i receives i-1, so downstream = decreasing index
    n = 40
    code = np.full((1, n), -1, np.int8)
    code[0, 1:] = 3                      # direction 3 = (0,-1) = receiver is the left neighbour
    dom = np.ones((1, n), bool)
    v = np.zeros((1, n))
    v[0, 20:] = 1.0                      # a knickpoint step at index 20
    up_ptr, up_ok = np.full((1, n), -1, np.int64), np.zeros((1, n), bool)
    up_ptr[0, :-1] = np.arange(1, n)     # upstream = increasing index
    up_ok[0, :-1] = True
    recv = gm.d8_receivers(code)
    up, down = gm.window_means(v, up_ptr, up_ok, recv, dom & (recv >= 0), w=4)
    # well upstream of the step: both windows see 1.0 -> ratio 1
    assert up[0, 35] == pytest.approx(1.0) and down[0, 35] == pytest.approx(1.0)
    # well downstream: both windows see 0.0
    assert up[0, 3] == pytest.approx(0.0) and down[0, 3] == pytest.approx(0.0)
    # at the step: upstream window is high, downstream window is low
    assert up[0, 20] > down[0, 20]
    assert up[0, 19] / max(down[0, 19], 1e-9) > 1.5


def test_blockwise_zscore_removes_a_regional_gradient():
    H = W = 900
    rng = np.random.default_rng(7)
    y, x = np.mgrid[0:H, 0:W].astype(float)
    v = 0.01 * x + rng.normal(0, 1, (H, W))     # monotone regional gradient + noise
    valid = np.ones((H, W), bool)
    z = gm.blockwise_zscore(v, valid, block_px=300)
    got = z[valid & np.isfinite(z)]
    assert abs(float(np.mean(got))) < 0.05
    assert abs(float(np.std(got)) - 1.0) < 0.15
    means = [float(np.nanmean(z[:, bx * 300:(bx + 1) * 300])) for bx in range(3)]
    assert max(means) - min(means) < 0.1


def _draw_lineament(az_deg, H=300, W=300, thick=2):
    """A lineament of geographic azimuth ``az_deg`` (clockwise from north)."""
    m = np.zeros((H, W), bool)
    for t in np.arange(-140, 141, 0.25):
        north = t * np.cos(np.deg2rad(az_deg))
        east = t * np.sin(np.deg2rad(az_deg))
        y = int(round(H / 2 - north))
        x = int(round(W / 2 + east))
        if 0 <= y < H and 0 <= x < W:
            m[max(0, y - thick):y + thick + 1, max(0, x - thick):x + thick + 1] = True
    return m


@pytest.mark.parametrize("az", [0.0, 30.0, 60.0, 90.0, 120.0, 150.0])
def test_structure_strike_recovers_a_known_lineament_orientation(az):
    """The reported strike is a geographic azimuth mod 180 deg, 0 = N-S."""
    from scipy import ndimage as ndi
    m = _draw_lineament(az)
    strike, coh = gm.structure_strike(m.astype(float), sigma_px=8.0)
    band = ndi.binary_dilation(m, iterations=6) & ~m
    sel = band & (coh > 0.6)
    assert sel.sum() > 500, "the coherence gate must keep most of the near-line band"
    got = np.rad2deg(strike[sel]) % 180.0
    err = np.abs(((got - az + 90.0) % 180.0) - 90.0)
    assert float(np.median(err)) < 3.0, f"az {az}: median strike error {np.median(err):.2f} deg"


def test_branch_signature_separates_independent_channel_branches():
    """Independence must mean 'different channel branch', not 'different sink'.

    The northwestern Great Basin is internally drained: every channel of a closed
    basin shares one terminal playa, so terminal-sink identity would call all of
    them one drainage (measured: 1,224 sinks for 5.17 M cells, and only 64 of
    36,633 knickpoint candidates had >=3 distinct sinks in their corridor).
    """
    h = w = 24
    y, x = np.mgrid[0:h, 0:w].astype(float)
    # a ridge along x = w/2: water flows to opposite edges on either side
    z = 0.02 * 100.0 * np.abs(y - 12.0) - 0.05 * 100.0 * np.abs(x - 12.0)
    dom = np.ones((h, w), bool)
    zf, _ = gm.priority_flood(z, dom)
    code = gm.d8_dircode(zf, dom)
    sig = gm.branch_signature(code, dom, k=3)

    assert sig.shape == (h, w), "branch signature must come back in 2-D domain shape"
    left = set(np.unique(sig[:, 2:9]).tolist())
    right = set(np.unique(sig[:, 15:22]).tolist())
    assert left and right and not (left & right), "opposite basins must be independent"
    # cells on the same flow path within k steps share the signature
    sig1 = gm.branch_signature(code, dom, k=1)
    assert len(np.unique(sig1)) > len(np.unique(gm.branch_signature(code, dom, k=8)))
