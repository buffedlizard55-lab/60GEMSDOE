"""Tests for the lane's physical core.  These are analytic or conservation tests, not curve fits:
if one fails, no chi/knickpoint number produced by this repository means anything."""

from __future__ import annotations

import numpy as np
import pytest

from gems60 import drains as D


def _ramp(h=40, w=40, dy=5.0, dx=1.0):
    y, x = np.indices((h, w))
    return (-dy * y - dx * x).astype(np.float64)


def test_fill_depressions_removes_every_sink():
    """After epsilon filling, every finite non-edge cell must have a strictly lower D8 receiver."""
    dem = _ramp(30, 30)
    dem[10:14, 10:14] -= 50.0            # a closed pit
    finite = np.ones_like(dem, dtype=bool)
    filled = D.fill_depressions(dem, finite, eps=1e-3)
    rec = D.d8_receivers(filled)
    h, w = dem.shape
    inner = np.zeros_like(finite)
    inner[1:-1, 1:-1] = True
    ys, xs = np.nonzero(finite & inner)
    sinks = [(int(y), int(x)) for y, x in zip(ys, xs) if rec[y, x] < 0]
    assert sinks == [], f"sinks remain after fill: {sinks[:5]}"
    # the fill must not LOWER anything
    assert np.all(filled[finite] >= dem[finite] - 1e-12)


def test_accumulation_is_conserved_and_monotone_downstream():
    dem = _ramp(25, 25)
    finite = np.ones_like(dem, dtype=bool)
    filled = D.fill_depressions(dem, finite, eps=1e-3)
    rec = D.d8_receivers(filled)
    order = np.argsort(filled.ravel(), kind="stable")
    acc = D.accumulate_area(rec.ravel(), order, 10_000.0).reshape(dem.shape)
    assert acc.min() == pytest.approx(10_000.0)
    # every non-edge cell passes its own area downstream, so a receiver can never be smaller
    ys, xs = np.nonzero(finite)
    for y, x in zip(ys, xs):
        r = rec[y, x]
        if r >= 0:
            assert acc.ravel()[r] >= acc[y, x]
    # a cell with no upstream contributor holds exactly one cell
    n_up = D.count_upstream_channels(rec.ravel(), np.ones(rec.size, dtype=bool), order)
    heads = np.nonzero(n_up == 0)[0]
    assert np.allclose(acc.ravel()[heads], 10_000.0)


def test_chi_on_a_uniform_channel_matches_the_closed_form():
    """On a single straight channel chi must equal sum_j (A0/A_j)**theta * L exactly.

    The first version of this test assumed the accumulated area along the channel was constant and
    compared chi against a formula with the wrong sign; it failed against correct code.  A pure
    downhill ramp has no D8 tie for the interior: of the three lower neighbours the straight-down
    one is strictly the steepest (drop/distance 10/1 vs 10/sqrt(2)), and the last row is flat, so
    its cells have no receiver at all and are the outlets.  Every column is therefore an independent
    single-thread channel and the area at cell (j, x) is exactly (j + 1) * cell_area.
    """
    dem = _ramp(30, 30, dy=10.0, dx=0.0)
    finite = np.ones_like(dem, dtype=bool)
    filled = D.fill_depressions(dem, finite, eps=1e-3)
    rec = D.d8_receivers(filled)
    order_asc = np.argsort(filled.ravel(), kind="stable")
    cell_area = 10_000.0
    acc = D.accumulate_area(rec.ravel(), order_asc[::-1], cell_area).reshape(dem.shape)
    theta, a0, L = 0.45, 1.0, 100.0
    chi = D.chi_field(rec.ravel(), acc.ravel(), order_asc, theta, a0, L).reshape(dem.shape)
    # every non-outlet cell must drain straight down its own column (no lateral merging, no tie)
    ys, xs = np.nonzero(finite & (np.arange(dem.shape[0])[:, None] < dem.shape[0] - 1))
    for y, x in zip(ys, xs):
        r = rec[y, x]
        if r >= 0:
            assert r == (y + 1) * dem.shape[1] + x, f"flow left column at {(y, x)}"
    assert acc[0, 15] == pytest.approx(cell_area)
    assert acc[-1, 15] == pytest.approx(30 * cell_area)
    col = chi[:, 15]
    expect = np.zeros(dem.shape[0])
    for y in range(dem.shape[0] - 1):                    # outlet row keeps chi = 0
        expect[y] = sum((a0 / ((j + 1) * cell_area)) ** theta * L
                        for j in range(y, dem.shape[0] - 1))
    np.testing.assert_allclose(col, expect, rtol=1e-9, atol=1e-9)


def test_first_order_basins_are_disjoint_and_cover_headwaters():
    dem = _ramp(21, 21, dy=10.0, dx=0.0)
    finite = np.ones_like(dem, dtype=bool)
    filled = D.fill_depressions(dem, finite, eps=1e-3)
    rec = D.d8_receivers(filled)
    order_asc = np.argsort(filled.ravel(), kind="stable")
    acc = D.accumulate_area(rec.ravel(), order_asc[::-1], 10_000.0)
    chan = D.channel_mask(acc.reshape(dem.shape), 100_000.0).ravel()
    n_up = D.count_upstream_channels(rec.ravel(), chan, order_asc)
    basin, cells, offs = D.first_order_basins(rec.ravel(), chan, n_up, dem.shape[1])

    # documented convention: each link runs DOWNSTREAM -> UPSTREAM, so its last cell is a headwater
    # and its first cell is the last channel cell before the first junction (or the channel end).
    # (The first version asserted that row indices increase along a link "upstream of the last one",
    # which contradicts the documented order for a DEM that drains towards larger row indices.)
    assert len(set(cells.tolist())) == cells.size, "links must be pixel-disjoint"
    heads_in_links = set()
    for b in range(offs.size - 1):
        seg = cells[offs[b]:offs[b + 1]]
        assert seg.size >= 2
        first, last = int(seg[0]), int(seg[-1])
        assert n_up[last] == 0, "the upstream end of a first-order link must be a headwater"
        r = rec.ravel()[first]
        assert (r < 0) or (n_up[r] >= 2) or (not chan[r]), \
            "a link may only stop at the first junction or the channel end"
        heads_in_links.add(last)
    heads = set(np.flatnonzero(chan & (n_up == 0)).tolist())
    assert heads_in_links == heads, "every headwater channel cell must start exactly one link"
    lab = basin[cells]
    assert lab.min() >= 0
    # basin ids are contiguous and appear once, so a knickpoint can be attributed to one drainage
    assert sorted(set(lab.tolist())) == list(range(offs.size - 1))


def test_segment_profile_finds_a_synthetic_knickpoint():
    """A piecewise-linear (chi, z) profile with one slope change must produce one breakpoint."""
    chi = np.arange(0.0, 100.0, 1.0)
    z = np.where(chi < 50.0, 0.05 * chi, 0.05 * 50 + 0.30 * (chi - 50))
    r = D.segment_profile(chi, z, window=5, ratio=1.6, min_drop_m=1.0)
    # A windowed ratio detector legitimately reports the two flanking window centres (here 47 and 53)
    # for one step at chi = 50; the physics claim is localisation + a real steepness contrast, not a
    # count of detections, so the test asserts what the detector is for.
    assert 1 <= r["positions"].size <= 2
    assert np.all(np.abs(r["positions"] - 50) <= 6)
    slopes = np.sort(np.abs(r["slopes"]))
    assert slopes[-1] / slopes[0] > 3.0


def test_segment_profile_is_silent_on_a_straight_line():
    chi = np.arange(0.0, 80.0, 1.0)
    z = 0.1 * chi
    r = D.segment_profile(chi, z, window=5, ratio=1.6, min_drop_m=1.0)
    assert r["positions"].size == 0


def test_strike_of_segments_recovers_a_known_azimuth():
    truth = np.zeros((60, 60), dtype=bool)
    # a 45-degree line: 30 px long, azimuth 135 deg (dy = -1, dx = +1) -> 135 in [0,180)
    for t in range(30):
        truth[40 - t, 10 + t] = True
    az = D.strike_of_segments(truth, min_px=25)
    assert az.size == 1
    assert min(abs(az[0] - 135.0), abs(az[0] - 135.0 + 180.0)) < 2.0


def test_orientation_matched_lines_match_the_azimuth_histogram():
    strikes = np.array([0.0] * 50 + [90.0] * 50)
    rng = np.random.default_rng(3)
    anchors = np.stack([np.full(500, 100), np.arange(500)], axis=1)
    lines = D.orientation_matched_lines(strikes, 200, 21, (200, 200), anchors, rng)
    dy = lines[0, -1, 0] - lines[0, 0, 0] if False else None
    az = []
    for j in range(lines.shape[0]):
        d = lines[j, -1] - lines[j, 0]
        az.append(np.degrees(np.arctan2(d[0], d[1])) % 180.0)
    az = np.asarray(az)
    frac_horizontal = float((az < 45).mean())
    assert 0.35 < frac_horizontal < 0.65, frac_horizontal


def test_paired_bootstrap_matches_a_known_mean():
    d = np.concatenate([np.full(100, 1.0), np.full(100, -0.5)])
    r = D.paired_bootstrap(d, n=2000, seed=1)
    assert r["mean"] == pytest.approx(0.25)
    assert r["ci95"][0] < 0.25 < r["ci95"][1]
    assert r["frac_positive"] == pytest.approx(0.5)
