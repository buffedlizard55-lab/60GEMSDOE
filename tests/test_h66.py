"""Tests for the H66 off-catalogue lane driver.

Two things are pinned here, both of them code paths the H66 numbers come from:

1. ``run_e1_offcat`` -- the mandated first-test statistic against an off-catalogue
   target.  On a synthetic field where the segment genuinely carries a steepness
   step and the rest of the grid does not, the paired difference must be positive.
2. ``paired_block_bootstrap`` -- the per-block decomposition of the official DTI
   must sum back to the global TPw / FPw that ``gems52.metric.dti`` reports, so the
   bootstrap resamples the metric's own terms and not an approximation of them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems52 import metric as M          # noqa: E402
import run_h66 as H                     # noqa: E402


def _synthetic():
    """A 60x60 field: one horizontal off-catalogue segment carrying a real step."""
    n = 60
    fp = np.ones((n, n), bool)
    cat = np.zeros((n, n), bool)
    cat[5, 5:20] = True                                  # a mapped fault, must be avoided
    offcat = np.zeros((n, n), bool)
    offcat[30, 10:41] = True                             # off-catalogue segment, 31 px
    channel = np.ones((n, n), bool)
    step = np.full((n, n), 0.1)
    step[29:32, 10:41] = 2.0                             # the step the lane should see
    return step, channel, fp, offcat, cat


def test_e1_offcat_detects_a_real_step():
    step, channel, fp, offcat, cat = _synthetic()
    rows = H.run_e1_offcat(step, channel, fp, offcat, cat, max_components=8, n_transects=10)
    scored = [r for r in rows if "paired_difference" in r]
    assert scored, "the synthetic segment must be scored, not skipped"
    diffs = np.array([r["paired_difference"] for r in scored])
    # the 3 px window straddles the synthetic step (3 rows at 2.0 inside a 7-row window),
    # so the expected contrast is ~0.8, not the full 1.9; the assertion is that the
    # statistic is positive and dominated by the observed value, not a magic number
    assert diffs.mean() > 0.5, diffs
    assert scored[0]["observed_mean_step"] > 5 * scored[0]["control_mean_step"]
    assert scored[0]["control_mean_step"] < 0.5


def test_e1_offcat_controls_never_touch_a_known_trace():
    """The transect pool excludes a 10 px dilation of catalogue + off-catalogue."""
    from scipy import ndimage as ndi
    step, channel, fp, offcat, cat = _synthetic()
    pool = fp & ~ndi.binary_dilation(cat | offcat, iterations=10)
    assert not (pool & cat).any()
    assert not (pool & offcat).any()
    # a 3 px window around any pooled point cannot reach the segment
    assert not (ndi.binary_dilation(pool, iterations=3) & offcat).any()


def test_block_decomposition_reproduces_the_official_metric_terms():
    rng = np.random.default_rng(7)
    shape = (450, 450)          # > 2 x BLOCK_PX, so the decomposition spans several blocks
    truth = np.zeros(shape, bool)
    truth[20, 20:30] = True
    truth[240, 35:45] = True
    truth[410, 300:310] = True
    pred = np.zeros(shape, np.float32)
    ys = rng.integers(0, shape[0], 400)
    xs = rng.integers(0, shape[1], 400)
    pred[ys, xs] = 1.0
    valid = np.ones(shape, bool)
    cat = np.zeros(shape, bool)

    ref = M.dti(pred, truth)
    gy, gx = np.nonzero(truth)
    nb = (shape[0] // H.BLOCK_PX + 1) * (shape[1] // H.BLOCK_PX + 1)
    _, q, _ = M.max_cover(pred, truth)
    tp, fpw = H.block_terms(pred, truth, gy, gx, nb, q)
    assert tp.sum() == ref["tpw"] or abs(tp.sum() - ref["tpw"]) < 1e-9
    assert abs(fpw.sum() - ref["fpw"]) < 1e-9


def test_paired_bootstrap_orders_a_better_arm_first():
    """An arm placed on the truth must beat a mass-matched random arm in the bootstrap."""
    rng = np.random.default_rng(11)
    shape = (450, 450)
    truth = np.zeros(shape, bool)
    truth[20, 20:30] = True
    truth[240, 35:45] = True
    truth[410, 300:310] = True
    good = np.zeros(shape, np.float32)
    good[truth] = 1.0
    good[19, 20:30] = 1.0
    bad = np.zeros(shape, np.float32)
    ys = rng.integers(0, shape[0], int(good.sum()))
    xs = rng.integers(0, shape[1], int(good.sum()))
    bad[ys, xs] = 1.0
    valid = np.ones(shape, bool)
    cat = np.zeros(shape, bool)
    out = H.paired_block_bootstrap({"lane": good, "random_mass_control": bad}, truth, valid, cat,
                                   draws=200, seed=3, reference="lane")
    assert out["per_arm"]["lane"]["mean"] > out["per_arm"]["random_mass_control"]["mean"]
    pair = out["paired"]["lane_minus_random_mass_control"]
    assert pair["mean"] > 0
    assert pair["ci95"][0] > 0
