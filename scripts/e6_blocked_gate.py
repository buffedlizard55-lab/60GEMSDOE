#!/usr/bin/env python3
"""Promotion gate: score every candidate of this session on the repository's own pooled,
spatially-blocked hide-and-recover holdout, alongside the live-lineage incumbents.

The brief's rule is "never spend a submission slot on anything that has not beaten the best
promotable holdout".  This script produces that number with the shared template
(`gems52.evaluate_holdout`, 4 quadrant blocks, 30 px buffer, official alpha/beta/kernel), so any
promotion claim in this session is checkable rather than asserted.

Outputs: evidence/e6_blocked_gate.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems52 import evaluate_holdout, holdout  # noqa: E402

WORK, EVID, REG = ROOT / "work", ROOT / "evidence", ROOT / "registry" / "rasters"


def rd(p: Path) -> np.ndarray:
    with rasterio.open(p) as ds:
        return np.nan_to_num(ds.read(1).astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def packed(path: Path) -> np.ndarray:
    return np.unpackbits(np.load(path)).reshape(3730, 3292).astype(np.float32)


ARMS = {
    "champion_C(0.2778)": ("tif", REG / "dotted_b2_prune_02778.tif"),
    "D2.8_A(0.2600)": ("tif", REG / "dotted_d2_8_02600.tif"),
    "ring_peel_D3": ("tif", None),                      # built inline from C
    "xcrd_H61A": ("npy", WORK / "xcrd_dots.npy"),
    "sgmc_trace_H62A": ("packed", WORK / "e3_dots_sgmc_pure.npy"),
    "scarp_structure_H63A": ("packed", WORK / "h63_dots.npy"),
}


def main() -> int:
    t0 = time.time()
    with rasterio.open(ROOT / "data/bridge/example_submission.tif") as ds:
        foot = np.isfinite(ds.read(1))
    cat = rd(WORK / "labels.tif") > 0
    from scipy import ndimage
    d_cat = ndimage.distance_transform_edt(~cat)

    preds: dict[str, np.ndarray] = {}
    for name, (kind, path) in ARMS.items():
        if name == "ring_peel_D3":
            preds[name] = ((rd(REG / "dotted_b2_prune_02778.tif") > 0) & (d_cat > 3)).astype(np.float32)
        elif kind == "tif":
            preds[name] = (rd(path) > 0).astype(np.float32)
        elif kind == "npy":
            preds[name] = (np.load(path) > 0).astype(np.float32)
        else:
            preds[name] = packed(path)
        print(f"[e6] {name:<22} mass {int(preds[name].sum()):>7}")

    folds = holdout.make_folds(cat, foot, n_folds=4, buffer_px=30, mode="block")
    terms: dict[str, np.ndarray] = {}
    for name, p in preds.items():
        acc = None
        for fold in folds:
            _, tf = evaluate_holdout.evaluate(p, fold, foot, block_side=200)
            acc = tf.copy() if acc is None else acc + tf
        terms[name] = acc
        print(f"[e6] {name:<22} terms ready ({time.time()-t0:.0f}s)")

    summ = evaluate_holdout.pooled_summary(terms, draws=1000, candidate="champion_C(0.2778)")
    out = dict(schema="e6-blocked-gate/1",
               protocol="gems52-pooled-hide-v1, 4 quadrant blocks, 30 px buffer, block train mask",
               note=("Withheld truth is the VISIBLE catalogue (a proxy): a candidate can win here by "
                     "better recovering mapped faults while being worse on the hidden new-fault set. "
                     "This gate can promote nothing on its own; it can only veto."),
               scores={n: dict(dti=round(s["dti"], 6), ci95=[round(x, 6) for x in s["ci95"]],
                               withheld_positive_pixels=s["withheld_positive_pixels"])
                       for n, s in summ["scores"].items()},
               paired_delta_vs_champion={n: dict(delta=round(d["delta"], 6),
                                                 ci95=[round(x, 6) for x in d["ci95"]])
                                         for n, d in summ["paired_differences"].items()},
               implementation_sha256=summ["implementation_sha256"])
    rank = sorted(out["scores"].items(), key=lambda kv: -kv[1]["dti"])
    out["ranking"] = [n for n, _ in rank]
    out["beats_champion"] = {n: bool(out["paired_delta_vs_champion"][n]["ci95"][0] > 0)
                             for n in out["paired_delta_vs_champion"]}
    EVID.mkdir(exist_ok=True)
    (EVID / "e6_blocked_gate.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
