#!/usr/bin/env python3
"""Matched-random control for the literal 3-px dot-overlap gate (IR-60-GATE-01).

For every registry raster on which the H65-1 candidate trips the >70% overlap
clause, compute the same statistic for 5 uniform-random dot sets of equal size
(40,000) drawn from the candidate's own allowed area (footprint minus mapped
catalogue). If random dots trip the gate equally, the firing measures the
prior's support density, not copying.  DIAGNOSTIC ONLY: it does not overturn
the preregistered literal gate (the tool verdict stays unique=false).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems57 import uniqueness as U  # noqa: E402

import argparse

CAND = ROOT / "docs/downloads/gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif"
CACHE = ROOT / ".cache/features65"
REG = ROOT / ".cache/registry"


def main() -> int:
    # H66 (2026-10-11): CLI so the same control can be run for any session's
    # candidate without forking the script.
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", type=Path, default=CAND)
    ap.add_argument("--rows", type=Path,
                    default=ROOT / "evidence/h65_uniqueness_rows.jsonl")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "evidence/h65_overlap_control.json")
    a = ap.parse_args()
    rows = [json.loads(l) for l in a.rows.open()]
    fired = [r for r in rows if r["duplicate_by_overlap"]]
    with rasterio.open(a.candidate) as ds:
        mine = ds.read(1)
    mine_d = U._dots(mine)
    n = int(mine_d.sum())
    allowed = np.load(CACHE / "footprint.npy").astype(bool) & ~np.load(CACHE / "catalogue.npy").astype(bool)
    idx = np.flatnonzero(allowed.ravel())
    rng = np.random.default_rng(65001)
    rand_sets = []
    for _ in range(5):
        m = np.zeros(allowed.size, bool)
        m[rng.choice(idx, n, replace=False)] = True
        rand_sets.append(m.reshape(allowed.shape))
    out = []
    for r in fired:
        p = REG / f"{r['sha256'][:16]}.tif"
        with rasterio.open(p) as ds:
            theirs = ds.read(1)
        near = U._near(U._dots(theirs), U.RADIUS_PX)
        cand = float(near[mine_d].mean())
        rnd = [float(near[s].mean()) for s in rand_sets]
        out.append(dict(submission=r["submission"], their_dots=r["their_dots"],
                        candidate_overlap=round(cand, 4), random_overlap_mean=round(float(np.mean(rnd)), 4),
                        random_overlap_min=round(min(rnd), 4), excess=round(cand - float(np.mean(rnd)), 4),
                        random_also_fires=bool(min(rnd) > 0.70)))
    ex = [o["excess"] for o in out]
    res = dict(evidence_class="DIAGNOSTIC (post-hoc; does not change the literal gate)",
               candidate=a.candidate.name, n_dots=n, allowed_px=int(allowed.sum()), random_sets=5, seed=65001,
               radius_px=U.RADIUS_PX, n_fired=len(out),
               min_their_dots_among_fired=min(o["their_dots"] for o in out),
               n_where_random_also_fires=sum(o["random_also_fires"] for o in out),
               max_excess=max(ex), median_excess=float(np.median(ex)), rows=out)
    a.out.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
