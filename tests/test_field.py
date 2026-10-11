"""Sanity limits of the field statistics."""
import numpy as np
from gems60.field import ksn_profile, chi_residual_profile, local_channel_direction


def test_ksn_recovers_a_known_slope():
    chi = np.linspace(0, 1000, 200)
    for slope in (0.1, 0.5, 2.0):
        z = slope * chi
        k = ksn_profile(chi, z, w=7)
        good = np.isfinite(k)
        assert np.allclose(k[good], slope, rtol=1e-6)


def test_residual_is_zero_on_a_straight_profile():
    chi = np.linspace(0, 1000, 200)
    z = 0.3 * chi + 5.0
    r = chi_residual_profile(chi, z, w=61)
    good = np.isfinite(r)
    assert np.abs(r[good]).max() < 1e-8


def test_channel_direction_is_orthogonal_to_a_straight_line():
    shape = (60, 60)
    path = np.array([y * 60 + 30 for y in range(10, 50)])  # a N-S line
    dy, dx = local_channel_direction(path, shape, halfspan=4)
    good = np.isfinite(dy)
    assert good.any()
    assert np.allclose(np.abs(dy[good]), 8.0)
    assert np.allclose(dx[good], 0.0)
