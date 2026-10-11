"""Load-bearing tests for the vendored metric and the lane hydrology.

Metric pins (identical to the shared template's tests, which pin the
organiser's own worked example on the official page):
  * page worked triple TPw 3.00, FPw 1.89, FNw 2.00 -> 0.60 printed,
    0.6026516673... exact;
  * analytic single-pixel degeneration to the kernel weight;
  * identity FNw == |G| - TPw;
  * brute-force loop agreement.

Hydrology pins (synthetic cone with a pit and noise, 200x200):
  * the pit is filled (filled - original >= 0 everywhere, ~ depth at pit);
  * chi is non-decreasing downstream along parent chains;
  * flow accumulation at the grid edge equals the number of cells draining
    through it (mass conservation: sum of acc over roots == n_valid).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import metric as M  # noqa: E402
from gems52 import lane_hydro as HY  # noqa: E402


# ---------------------------------------------------------------- metric pins
def test_published_worked_example():
    num, den = 3.00, 3.00 + 0.2 * 1.89 + 0.8 * 2.00
    assert M.R_M == 300.0 and M.ALPHA == 0.2 and M.BETA == 0.8
    assert num / den == pytest.approx(0.6026516673, abs=1e-9)
    assert round(num / den, 2) == 0.60


def test_single_pixel_kernel_weight():
    g = np.zeros((21, 21), dtype=bool)
    g[10, 10] = True
    for d_px, expect in [(0, 1.0), (1, 2 / 3), (2, 1 / 3), (3, 0.0)]:
        p = np.zeros_like(g, dtype=np.float64)
        p[10, 10 + d_px] = 1.0
        assert M.dti(p, g)["dti"] == pytest.approx(expect, abs=1e-12)
    p = np.zeros_like(g, dtype=np.float64)
    p[11, 11] = 1.0
    assert M.dti(p, g)["dti"] == pytest.approx(1 - np.sqrt(2) / 3, abs=1e-12)


def test_identity_fn_and_bruteforce():
    rng = np.random.default_rng(0)
    for _ in range(4):
        g = rng.random((40, 40)) < 0.05
        p = np.where(rng.random((40, 40)) < 0.08, rng.choice([0.3, 1.0]), 0.0)
        if not g.any() or not (p > 0).any():
            continue
        r = M.dti(p, g)
        assert r["fnw"] == pytest.approx(r["n_truth"] - r["tpw"], abs=1e-9)
        assert r["dti"] == pytest.approx(M.dti_bruteforce(p, g), abs=1e-9)


# ------------------------------------------------------------- hydrology pins
@pytest.fixture(scope="module")
def cone_stack():
    H = W = 200
    yy, xx = np.mgrid[0:H, 0:W]
    z = np.sqrt((yy - 100) ** 2 + (xx - 100) ** 2).astype(float) * 2.0
    z[150:170, 150:200] -= 60.0
    z += 5.0 * np.sin(xx / 7.0)
    valid = np.ones((H, W), bool)
    valid[:5, :] = False
    valid[:, 190:] = False
    return HY.hydro_stack(z, valid), valid


def test_pit_is_filled(cone_stack):
    st, valid = cone_stack
    H, W = valid.shape
    zf = st["filled"]
    yy, xx = np.mgrid[0:H, 0:W]
    z = np.sqrt((yy - 100) ** 2 + (xx - 100) ** 2).astype(float) * 2.0
    z[150:170, 150:200] -= 60.0
    z += 5.0 * np.sin(xx / 7.0)
    # (1) fill never carves: filled >= original on every valid cell
    assert (zf[valid] >= z[valid] - 1e-9).all()
    # (2) the synthetic 60 m pit floor rose by >= 40 m after filling
    rise = zf - z
    assert float(rise[150:170, 150:195].max()) >= 40.0


def test_chi_monotone_downstream(cone_stack):
    st, valid = cone_stack
    par, chi = st["parent"], st["chi"]
    rng = np.random.default_rng(0)
    bad = n = 0
    for _ in range(500):
        i = int(rng.integers(par.shape[0]))
        if par[i] >= 0 and valid.ravel()[i]:
            n += 1
            if chi[i] <= chi[par[i]] - 1e-9:
                bad += 1
    assert bad == 0


def test_accumulation_mass_conservation(cone_stack):
    st, valid = cone_stack
    par, acc = st["parent"], st["acc"]
    roots = np.flatnonzero((par < 0) & valid.ravel())
    assert acc[roots].sum() == pytest.approx(float(valid.sum()), abs=1e-6)
