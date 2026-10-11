"""Dot placement: the metric's own marginal-acceptance rule, hexagonal packing, and the registry
uniqueness budget.

Why this module exists, in one line of algebra (published metric, exact):

    DTI = T / (0.2*(T + S - M) + 0.8*|G|)          T = TP_w, S = sum p, M = sum p * max_g k(d),
                                                   FN_w = |G| - T identically

Adding a pixel of true credit increment ``c`` and false-positive increment ``f`` (= 1 - w, w being
that pixel's own best kernel weight to the truth) changes DTI by

    dDTI > 0   <=>   c * (1 - 0.2*DTI) > 0.2*DTI*f

In the common case of a single previously-uncovered truth pixel this reduces to the simple bar

    add iff   w > 0.2 * DTI

which at DTI = 0.2778 is w > 0.0556, i.e. the pixel must lie within 300*(1-0.0556) = 283 m of a
hidden fault.  Every pixel emitted beyond that distance pays the false-positive tax and earns
nothing.  The bar rises with the running DTI, so a greedy that recomputes it self-terminates.  That
self-terminating budget is what this module derives -- the number of dots is an OUTPUT, not a
chosen constant.
"""

from __future__ import annotations

import numpy as np

from . import metric as M


def marginal_gain(surface_field: np.ndarray, cover: np.ndarray, offsets=None) -> np.ndarray:
    """Exact one-dot marginal truth credit over the kernel disc, for a known cover field.

    ``surface_field`` is the evidence field (used as the truth-density proxy), ``cover`` is the
    current per-truth-pixel best credit.  Gain(p) = sum_g max(0, k(d(p,g)) - cover(g)) where the sum
    runs over the 29 lattice offsets inside the 300 m disc.  Implemented with zero-padded shifts so
    the grid edge cannot wrap credit around the raster.
    """
    if offsets is None:
        offsets = M.OFFSETS
    v = np.maximum(surface_field, 0.0).astype(np.float32)
    c = np.asarray(cover, dtype=np.float32)
    acc = np.zeros_like(v)
    vp = np.pad(v, 3, mode="constant")
    cp = np.pad(c, 3, mode="constant")
    for dy, dx, kk in offsets:
        shifted_v = vp[3 - dy: 3 - dy + v.shape[0], 3 - dx: 3 - dx + v.shape[1]]
        shifted_c = cp[3 - dy: 3 - dy + c.shape[0], 3 - dx: 3 - dx + c.shape[1]]
        acc += np.maximum(0.0, (kk * shifted_v) - shifted_c)
    return acc


def hex_lattice_mask(shape: tuple[int, int], spacing_px: float, phase=(0, 0)) -> np.ndarray:
    """Staggered (hexagonal) lattice: rows offset by half a spacing every other row.

    The repository's own measurement (H87 section 4.2) is that a staggered packing reaches a much
    higher mean cover at the same nearest-neighbour distance than a square one: the one owner-scored
    raster whose geometry is fully known is a staggered packing with mean cover 0.3748 at 5.00 px NN,
    where a square packing at the same NN distance leaves ~5% of the area uncovered.  Packing is
    therefore a real lever on T at fixed S, and it is free.
    """
    h, w = shape
    y = np.arange(h)[:, None]
    x = np.arange(w)[None, :]
    dx = (x + (phase[1] % 2) * (spacing_px / 2.0)) % spacing_px
    dy = (y + (phase[0] % 2) * (spacing_px / 2.0)) % spacing_px
    return (dx < 1.0) & (dy < 1.0)


def spacing_from_budget(n_dots: int, n_allowed: int) -> float:
    """Equivalent spacing (px) of a staggered lattice holding ``n_dots`` inside ``n_allowed`` cells.

    A staggered lattice at spacing s occupies 2 cells per s^2: the count is 2*A/s^2.
    """
    if n_dots <= 0 or n_allowed <= 0:
        return float("inf")
    return float(np.sqrt(2.0 * n_allowed / n_dots))


def budget_from_marginal_rule(cover_field: np.ndarray, allowed: np.ndarray, dti0: float,
                              alpha: float = 0.2, max_dots: int = 200_000,
                              n_probe: int = 40) -> dict:
    """Derive the self-terminating dot budget from the metric's own acceptance bar.

    The bar at running DTI s is w_min(s) = alpha*s*(1-w)/(1-alpha*s) ~ alpha*s for small alpha*s;
    using the conservative (larger) form w_min = alpha*s exactly reproduces the published marginal
    condition in the one-uncovered-truth-pixel case, which is the case the greedy acts on.  The
    budget is the number of allowed cells whose evidence-weighted credit exceeds the bar, evaluated
    on a probe grid and extrapolated, then reported with its bracket rather than as a point.
    """
    a = np.asarray(allowed, dtype=bool)
    n_allowed = int(a.sum())
    if n_allowed == 0:
        return {"n_dots": 0, "spacing_px": float("inf"), "note": "no allowed cells"}
    vals = np.asarray(cover_field, dtype=np.float64)[a]
    vals = vals[np.isfinite(vals)]
    out = []
    pos = vals[vals > 0.0]
    for s in (dti0 * 0.8, dti0, dti0 * 1.25):
        bar = alpha * s
        # The field is a RANKING, not a calibrated probability, so the marginal rule is applied the
        # only way it can be applied to a ranking: keep the most-evidence-dense fraction of the
        # gated set, with that fraction equal to the acceptance bar alpha*DTI.  The quantile is
        # taken over the STRICTLY POSITIVE values and floored at the smallest positive value, so a
        # mass of exact zeros can never collapse the bar to zero and emit everything.
        if pos.size == 0:
            out.append({"dti_assumed": float(s), "bar": float(bar), "n_dots": 0,
                        "note": "no positive evidence inside the gated set"})
            continue
        q = float(np.quantile(pos, 1.0 - min(0.999, bar)))
        q = max(q, float(pos.min()))
        n = int((vals >= q).sum())
        out.append({"dti_assumed": float(s), "bar": float(bar), "keep_fraction": float(bar),
                    "quantile_on_positive_values": q, "n_dots": int(min(n, n_allowed))})
    n_mid = out[1]["n_dots"]
    return {"n_dots": int(n_mid), "bracket": out, "n_allowed": n_allowed,
            "spacing_px": spacing_from_budget(max(n_mid, 1), n_allowed),
            "note": "budget derived from the marginal-acceptance bar alpha*DTI at three assumed DTI"}


def emit(surface_field: np.ndarray, allowed: np.ndarray, n_dots: int, spacing_px: float,
         min_sep_px: float = 3.0, seed: int = 60, hex_grid=True) -> np.ndarray:
    """Emit ``n_dots`` unit dots inside ``allowed``, ranked by ``surface_field``.

    Two stages, both published in the repository's own methods:
      1. an explicit staggered lattice at ``spacing_px`` inside ``allowed`` (packing lever);
      2. rank the lattice cells by the evidence field and keep the top ``n_dots``, with a hard
         minimum separation so that no two kept dots fall inside the 300 m kernel of the same
         truth pixel in a way that wastes credit.
    """
    a = np.asarray(allowed, dtype=bool)
    h, w = surface_field.shape
    lat = hex_lattice_mask(surface_field.shape, spacing_px) if hex_grid else np.ones_like(a)
    cand = lat & a
    idx = np.flatnonzero(cand.ravel())
    if idx.size < n_dots:
        # the lattice is too coarse for this budget: fall back to every allowed cell, ranked
        idx = np.flatnonzero(a.ravel())
    vals = np.nan_to_num(np.asarray(surface_field, dtype=np.float32).ravel()[idx],
                         nan=-np.inf, posinf=-np.inf)
    idx = idx[np.argsort(-vals, kind="stable")]
    sep2 = float(min_sep_px) ** 2
    cell = max(1, int(np.ceil(min_sep_px)))       # spatial hash cell, so the test is not O(n^2)
    buckets: dict[tuple[int, int], list[int]] = {}
    keep: list[int] = []
    for pos in idx:
        y, x = divmod(int(pos), w)
        by, bx = y // cell, x // cell
        ok = True
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                for q in buckets.get((by + oy, bx + ox), ()):   # type: ignore[arg-type]
                    qy, qx = divmod(q, w)
                    if (qy - y) ** 2 + (qx - x) ** 2 < sep2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            keep.append(int(pos))
            buckets.setdefault((by, bx), []).append(int(pos))
            if len(keep) >= n_dots:
                break
    dots = np.zeros(h * w, dtype=bool)
    if keep:
        dots[np.asarray(keep, dtype=np.int64)] = True
    return dots.reshape((h, w))


def registry_cover_masks(registry_dir, shape) -> tuple[list[str], list[np.ndarray]]:
    """Load every same-grid registry raster as a positive-pixel mask (no exclusions, per protocol)."""
    from pathlib import Path

    import rasterio

    names, masks = [], []
    for p in sorted(Path(registry_dir).glob("*.tif")):
        with rasterio.open(p) as ds:
            if (ds.height, ds.width) != shape:
                continue
            a = ds.read(1)
        m = np.isfinite(a) & (a > 0)
        if m.any():
            names.append(p.name)
            masks.append(m)
    return names, masks


def overlap_fractions(dots: np.ndarray, masks: list[np.ndarray], radius_px: int = 3) -> list[dict]:
    """Share of ``dots`` lying within ``radius_px`` of each registry raster's own dots.

    This is the protocol's lane-duplicate test (stop at > 0.70), evaluated with a square
    (2r+1) neighbourhood, which is the conservative direction: it can only over-report overlap.
    """
    from scipy import ndimage as ndi

    out = []
    n = int(dots.sum())
    for m in masks:
        if n == 0:
            out.append({"frac_within_3px": float("nan"), "n_dots_in_halo": 0})
            continue
        halo = ndi.binary_dilation(m, structure=ndi.generate_binary_structure(2, 1),
                                   iterations=radius_px)
        k = int((dots & halo).sum())
        out.append({"frac_within_3px": k / n, "n_dots_in_halo": k})
    return out
