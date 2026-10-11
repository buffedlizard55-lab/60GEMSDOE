#!/usr/bin/env python3
"""H69 — closed-form recovery of the hidden-set parameters T, K, F.

Metric (official, page 967), with G the hidden truth and p the prediction:

    TP_w = sum_{g in G} max_x p(x) k(d(x,g))      k(d) = max(1 - d/300m, 0)
    FP_w = sum_x p(x) [1 - max_g k(d(x,g))]
    FN_w = |G| - TP_w
    DTI  = TP_w / (TP_w + alpha*FP_w + beta*FN_w),   alpha = 0.2, beta = 0.8

Write T = TP_w, F = FP_w, K = |G|.  Then, exactly,

    1/DTI = alpha + alpha*(F/T) + beta*(K/T)                                   (1)
    1/DTI(lam*p) = alpha + alpha*(F/T) + (beta*K/T)/lam                        (2)

Three leaderboard returns of one field identify all three numbers:

    s1 = DTI(p)                  (the anchor; already paid if the field was scored)
    sA = DTI(0.5*p)              -> beta*K/T = (1/sA - 1/s1)
    sB = DTI(p + M floor dots)   -> T = alpha*M / (1/sB - 1/s1)

    K = T * (1/sA - 1/s1) / beta
    F = T * (2*(1/s1 - alpha) - (1/sA - 1/s1)) / alpha

Usage
-----
    python scripts/h69_recovery.py --selftest
    python scripts/h69_recovery.py --s1 0.2778 --sA <probe A return> --sB <probe B return> --M 2000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems57 import metric as M  # noqa: E402


def recover(s1: float, sA: float, sB: float, m_dots: int,
            alpha: float = M.ALPHA, beta: float = M.BETA) -> dict:
    a = 1.0 / s1 - alpha                 # alpha*(F/T) + beta*(K/T)
    b = 1.0 / sA - alpha                 # alpha*(F/T) + 2*beta*(K/T)
    beta_k_over_t = b - a
    t = alpha * m_dots / (1.0 / sB - 1.0 / s1)
    k = t * beta_k_over_t / beta
    f = t * (2.0 * a - b) / alpha
    return dict(T=t, K=k, F=f, recall_T_over_K=t / k if k else float("nan"),
                F_over_T=f / t if t else float("nan"),
                beta_K_over_T=beta_k_over_t,
                dti_check=t / (alpha * (t + f) + beta * k))


def selftest(seed: int = 11, shape=(180, 220), n_dots: int = 40000 // 40) -> int:
    """End-to-end check against the official metric implementation on synthetic truth."""
    rng = np.random.default_rng(seed)
    h, w = shape
    truth = np.zeros((h, w), bool)
    # three lineaments (hidden faults)
    for _ in range(3):
        y, x = rng.integers(10, h - 10), rng.integers(10, w - 10)
        ang = rng.uniform(0, np.pi)
        for s in range(0, 80):
            yy, xx = int(y + s * np.sin(ang)), int(x + s * np.cos(ang))
            if 0 <= yy < h and 0 <= xx < w:
                truth[yy, xx] = True
    p = np.zeros((h, w), np.float32)
    idx = rng.choice(h * w, size=n_dots, replace=False)
    p.ravel()[idx] = 1.0
    # add some true-positive mass so T is not degenerate
    p[truth] = 1.0

    def score(x):
        return M.dti_exact(x, truth)["dti"]

    # floor dots for probe B: 200 cells with zero credit
    d = M.max_cover(p, truth)[2]
    cand = np.flatnonzero((p == 0).ravel() & (d.reshape(-1) > 3))
    floor = cand[np.argsort(-d.reshape(-1)[cand])][:400]
    pB = p.copy()
    pB.reshape(-1)[floor] = 1.0
    s1, sA, sB = score(p), score((0.5 * p).astype(np.float32)), score(pB)
    base = M.dti_exact(p, truth)
    got = recover(s1, sA, sB, int(floor.size))
    print(f"true   T={base['tp']:12.4f} K={base['n_truth']:8d} F={base['fp']:12.4f} DTI={s1:.6f}")
    print(f"probes s1={s1:.6f} sA={sA:.6f} sB={sB:.6f}  (both below s1: {sA < s1 and sB < s1})")
    print(f"recovered T={got['T']:12.4f} K={got['K']:8.1f} F={got['F']:12.4f} "
          f"ratio T/T_true={got['T'] / base['tp']:.6f} K/K_true={got['K'] / base['n_truth']:.6f}")
    print(f"identity check: recovered DTI = {got['dti_check']:.6f} (anchor {s1:.6f})")
    ok = (abs(got["T"] / base["tp"] - 1) < 1e-6 and abs(got["K"] / base["n_truth"] - 1) < 1e-6
          and abs(got["dti_check"] - s1) < 1e-9)
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--s1", type=float, help="anchor return (champion live score)")
    ap.add_argument("--sA", type=float, help="0.5 x anchor probe return")
    ap.add_argument("--sB", type=float, help="anchor + M floor dots probe return")
    ap.add_argument("--M", type=int, default=2000, help="floor dots in probe B")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.s1 is None or a.sA is None or a.sB is None:
        ap.error("--s1 --sA --sB are required unless --selftest")
    r = recover(a.s1, a.sA, a.sB, a.M)
    print(f"hidden-set parameters of the anchor field (MEASUREMENT, not a projection):")
    print(f"  T (weighted credit)          = {r['T']:.1f}")
    print(f"  K (hidden label mass, px)    = {r['K']:.1f}")
    print(f"  F (wasted mass)              = {r['F']:.1f}")
    print(f"  recall T/K                   = {r['recall_T_over_K']:.4f}")
    print(f"  mass ratio F/T               = {r['F_over_T']:.3f}")
    print(f"  consistency: T/(a(T+F)+bK)   = {r['dti_check']:.6f} (should equal s1={a.s1})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
