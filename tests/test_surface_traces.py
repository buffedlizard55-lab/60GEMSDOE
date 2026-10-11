"""Analytic controls for the lane's core detector: collinear knickpoints from INDEPENDENT drainages.

The detector is the only place where the lane makes a claim that is not standard machinery, so it is
tested the way a detector should be: a positive control that must be found, and three negative
controls that must return nothing.  These are the tests whose earlier absence let a vacuous first test
and a fixed-bin Hough transform reach a full run.
"""

from __future__ import annotations

import numpy as np

from gems60 import surface as S

SHAPE = (140, 140)


def _points(coords, strength=6.0):
    knick = np.zeros(SHAPE, dtype=np.float32)
    basin = -np.ones(SHAPE, dtype=np.int32)
    for j, (y, x) in enumerate(coords):
        knick[y, x] = strength + 0.1 * j
        basin[y, x] = j
    return knick, basin


FOOT = np.ones(SHAPE, dtype=bool)


def test_collinear_knickpoints_from_three_drainages_are_found_at_the_right_azimuth():
    pts = [(20, 20), (48, 25), (75, 29)]          # 28 px apart along ~81 deg
    knick, basin = _points(pts)
    tr = S.strike_trace_support(knick, FOOT, min_support=3, gap_px=35, max_len_px=140, basin=basin)
    assert tr["n_traces"] == 1
    rec = tr["traces"][0]
    assert rec["support"] == 3 and rec["n_drainages"] == 3
    assert abs(rec["azimuth_fit_deg"] - 81.2) < 5.0, rec["azimuth_fit_deg"]
    assert rec["length_px"] > 40
    assert (tr["support"] > 0).sum() > 30            # the trace is painted, not just the knots
    assert float(tr["weight"].max()) >= 6.0


def test_same_points_in_one_drainage_are_not_independent_evidence():
    pts = [(20, 20), (48, 25), (75, 29)]
    knick, basin = _points(pts)
    basin[basin >= 0] = 7                            # all one first-order basin
    tr = S.strike_trace_support(knick, FOOT, min_support=3, gap_px=35, max_len_px=140, basin=basin)
    assert tr["n_traces"] == 0


def test_non_collinear_knickpoints_are_rejected():
    pts = [(12, 10), (26, 60), (44, 50)]             # deliberately not a line
    knick, basin = _points(pts)
    tr = S.strike_trace_support(knick, FOOT, min_support=3, gap_px=40, max_len_px=140, basin=basin)
    assert tr["n_traces"] == 0


def test_two_points_are_not_a_trace():
    knick, basin = _points([(20, 20), (48, 25)])
    tr = S.strike_trace_support(knick, FOOT, min_support=3, gap_px=35, max_len_px=140, basin=basin)
    assert tr["n_traces"] == 0


def test_two_independent_strikes_yield_two_traces():
    knick, basin = _points([(20, 20), (48, 25), (75, 29)])
    knick2, basin2 = _points([(60, 100), (88, 95), (115, 90)])
    knick = np.maximum(knick, knick2)
    basin = np.where(basin2 >= 0, basin2 + 100, basin)
    tr = S.strike_trace_support(knick, FOOT, min_support=3, gap_px=35, max_len_px=140, basin=basin)
    assert tr["n_traces"] == 2
    az = sorted(round(t["azimuth_fit_deg"]) for t in tr["traces"])
    assert abs(az[0] - 81) < 8 and abs(az[1] - 100) < 8, az


def test_score_is_gated_on_the_support_count():
    knick, basin = _points([(20, 20), (48, 25), (75, 29)])
    tr = S.strike_trace_support(knick, FOOT, min_support=3, gap_px=35, max_len_px=140, basin=basin)
    assert (S.score_from_traces(tr, FOOT, min_drainages=3) > 0).any()
    assert not (S.score_from_traces(tr, FOOT, min_drainages=4) > 0).any()
