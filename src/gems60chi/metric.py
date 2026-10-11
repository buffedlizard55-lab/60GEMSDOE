"""Official competition metric (Deterministic Tversky Index, DTI).

Transcribed *literally* from the published definition on the problem-description
page:

    TP_w = sum_{g in G} max_{x : d(x,g) <= R} p(x) * k(d(x,g))
    FP_w = sum_{x : p(x) > 0}  p(x) * [ 1 - max_{g in G} k(d(x,g)) ]
    FN_w = sum_{g in G} [ 1 - max_{x : d(x,g) <= R} p(x) * k(d(x,g)) ]
    k(d) = max(1 - d/R, 0)
    DTI  = TP_w / (TP_w + alpha*FP_w + beta*FN_w + eps)

with  alpha = 0.2,  beta = 0.8,  R = 300 m.

Source (public): https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/

Implementation notes
--------------------
* ``R`` is expressed in **pixels** (R_px) because the competition grid is 100 m.
  The default R_px = 3.0 reproduces R = 300 m exactly on that grid.
* ``TP_w`` is computed by exact brute force over the integer offsets inside the
  kernel disc (dx^2+dy^2 <= R_px^2).  For R_px <= 4 this is <= 49 offsets, so it
  is exact and fast.
* ``FP_w`` uses the *exact Euclidean* distance transform from the truth set, so
  ``max_g k(d(x,g))`` is exact everywhere (not only inside the disc).
* ``tests/test_metric.py`` checks this implementation against a literal
  brute-force O(len(G) * N) transcription defined in that file.

Nothing here is fitted or tuned; it is the published formula.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

ALPHA = 0.2
BETA = 0.8
R_M = 300.0
EPS = 1e-7


def kernel_offsets(r_px: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Integer (dy, dx, weight) triples with dx^2+dy^2 <= r_px^2."""
    r = int(np.floor(r_px))
    dys, dxs, ws = [], [], []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d = float(np.hypot(dx, dy))
            if d <= r_px:
                dys.append(dy)
                dxs.append(dx)
                ws.append(max(1.0 - d / r_px, 0.0))
    return np.array(dys), np.array(dxs), np.array(ws, dtype=np.float64)


def _shift(a: np.ndarray, dy: int, dx: int, fill: float = 0.0) -> np.ndarray:
    """Shift ``a`` by (dy, dx) with zero fill (a[y, x] -> out[y+dy, x+dx])."""
    out = np.full_like(a, fill, dtype=np.float64)
    h, w = a.shape
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    if ys0 >= ys1 or xs0 >= xs1:
        return out
    out[ys0:ys1, xs0:xs1] = a[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def dti_components(
    pred: np.ndarray,
    truth: np.ndarray,
    r_px: float = 3.0,
    alpha: float = ALPHA,
    beta: float = BETA,
) -> dict:
    """Return TP_w, FP_w, FN_w, |G| and DTI for a single raster.

    Parameters
    ----------
    pred : float array
        Prediction mass in [0, 1] (the submission).
    truth : bool array
        Ground-truth fault mask for this scoring unit.
    """
    pred = np.asarray(pred, dtype=np.float64)
    truth = np.asarray(truth, dtype=bool)
    if pred.shape != truth.shape:
        raise ValueError(f"shape mismatch: {pred.shape} vs {truth.shape}")

    n_gt = int(truth.sum())
    if n_gt == 0:
        return dict(tpw=0.0, fpw=0.0, fnw=0.0, n_gt=0, dti=float("nan"))

    if r_px == int(r_px) and float(r_px) == float(int(r_px)):
        dys, dxs, ws = kernel_offsets(float(r_px))
    else:
        dys, dxs, ws = kernel_offsets(float(r_px))

    # ---- TP_w -------------------------------------------------------------
    # For every truth pixel g: max over the disc of pred(x) * k(d(x, g)).
    ty, tx = np.nonzero(truth)
    best = np.zeros(n_gt, dtype=np.float64)
    p = pred
    for dy, dx, w in zip(dys, dxs, ws):
        # value contributed by source pixel (ty-dy, tx-dx) to truth pixel (ty, tx)
        sy = ty - dy
        sx = tx - dx
        ok = (sy >= 0) & (sy < p.shape[0]) & (sx >= 0) & (sx < p.shape[1])
        v = np.zeros(n_gt, dtype=np.float64)
        v[ok] = p[sy[ok], sx[ok]] * w
        np.maximum(best, v, out=best)
    tpw = float(best.sum())

    # ---- FP_w -------------------------------------------------------------
    # max_g k(d(x,g)) = max(1 - D(x)/R, 0) with D the Euclidean distance to the
    # nearest truth pixel.  Computed exactly via a distance transform.
    dist = ndimage.distance_transform_edt(~truth)
    kbar = np.clip(1.0 - dist / float(r_px), 0.0, None)
    fpw = float((pred * (1.0 - kbar)).sum())

    # ---- FN_w (identity FN_w = |G| - TP_w, asserted here) -----------------
    fnw = float(n_gt) - tpw
    if fnw < -1e-6:
        raise AssertionError("FN_w = |G| - TP_w violated")

    denom = tpw + alpha * fpw + beta * max(fnw, 0.0) + EPS
    return dict(tpw=tpw, fpw=fpw, fnw=max(fnw, 0.0), n_gt=n_gt, dti=tpw / denom)


def dti(pred: np.ndarray, truth: np.ndarray, r_px: float = 3.0) -> float:
    return dti_components(pred, truth, r_px=r_px)["dti"]


def pooled_dti(components: list[dict], alpha: float = ALPHA, beta: float = BETA) -> float:
    """Pooled DTI: sum the components over scoring units, then form the ratio.

    This is the correct pooling for a global-ratio metric; averaging per-unit
    DTIs is not (it is not decomposable).
    """
    t = sum(c["tpw"] for c in components)
    f = sum(c["fpw"] for c in components)
    k = sum(c["n_gt"] for c in components)
    fn = k - t
    return t / (t + alpha * f + beta * fn + EPS)


def marginal_credit_bar(current_dti: float, alpha: float = ALPHA) -> float:
    """A unit of added mass raises DTI iff its realised kernel credit exceeds
    alpha * current DTI.  (First-order condition of the metric.)"""
    return alpha * current_dti
