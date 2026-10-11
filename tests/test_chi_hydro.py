"""Hydrology primitives vs independent brute-force implementations."""
import numpy as np
import pytest
from gems60chi.hydro import (bfs_levels, chi_transform, d8_flow_directions,
                          fill_depressions, flow_accumulation)


def make(seed, h=34, w=41):
    rng = np.random.default_rng(seed)
    dem = 1000 - 3.0 * np.arange(h)[:, None] - 0.5 * np.arange(w)[None, :]
    dem = dem + rng.normal(0, 1.0, (h, w))
    valid = np.ones((h, w), bool)
    valid[:, :2] = False
    valid[8:12, 15:20] = False
    return dem, valid


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_routing_accumulation_chi(seed):
    dem, valid = make(seed)
    filled, _ = fill_depressions(dem, valid)
    assert (filled[valid] >= dem[valid] - 1e-9).all()
    down = d8_flow_directions(filled, valid)
    n = down.size
    v = valid.ravel()
    i = np.arange(n)
    # flow never enters an invalid cell, and is always downhill
    assert (v[down[v]] | (down[v] == i[v])).all()
    lower = (filled.ravel()[down[v]] <= filled.ravel()[v] + 1e-9)
    assert lower.all()
    dist, levels = bfs_levels(down, valid)
    assert (dist[v] >= 0).all()
    acc = flow_accumulation(down, valid, levels)
    bf = np.zeros(n)
    for k in np.nonzero(v)[0]:
        j = k
        while True:
            bf[j] += 1
            nx = down[j]
            if nx == j:
                break
            j = nx
    assert np.allclose(acc, bf)
    chi = chi_transform(down, acc, valid, dem.shape).ravel()
    for k in np.nonzero(v)[0]:
        j = down[k]
        if j != k and v[j]:
            assert chi[k] >= chi[j] - 1e-9


def test_no_cycles():
    dem, valid = make(7)
    filled, _ = fill_depressions(dem, valid)
    down = d8_flow_directions(filled, valid)
    n = down.size
    for k in np.nonzero(valid.ravel())[0]:
        seen, j = set(), k
        while j not in seen:
            seen.add(j)
            j = down[j]
        assert j == down[j], "flow path entered a cycle"
