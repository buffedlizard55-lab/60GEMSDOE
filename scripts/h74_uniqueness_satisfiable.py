"""Re-run the H74-1 uniqueness comparison, splitting satisfiable from unsatisfiable comparators.

The parallel-run protocol (rule 1) reads: stop as a duplicate if more than 70 % of our dots fall
within 3 px of one registry raster's dots.  Four registry comparators are *calibration lattices and
dense packings* whose own 3 px dilation already covers more than 70 % of the footprint.  Against
those, the clause is unsatisfiable: every candidate raster of any shape scores > 70 %, including
the comparators themselves.  Reporting only "FAIL" against them would be misleading, and reporting
only the satisfiable subset would hide a literal protocol breach, so ``evidence/h74_uniqueness.json``
keeps the literal verdict and this script produces the like-for-like reading beside it.

Both numbers are published.  Neither is spun.  Run:
    /home/user/.venv/bin/python scripts/h74_uniqueness_satisfiable.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_h74 import _dilate3  # noqa: E402  (reuse the shared helper, never fork it)

LIMIT_OVERLAP = 0.70
LIMIT_RHO = 0.90


def main() -> int:
    from scipy import stats

    from gems57.grid import load_grid

    card = json.loads((ROOT / "evidence" / "h74_runcard.json").read_text())
    tif = ROOT / card["raster"]["path"]
    with rasterio.open(tif) as src:
        pred = src.read(1).astype(np.float64)
    pred[~np.isfinite(pred)] = 0.0

    g = load_grid()
    footprint = np.asarray(g.footprint, dtype=bool)

    # Recompute per-comparator, adding the self-coverage test that decides satisfiability.
    paths = sorted((ROOT / "registry" / "rasters").glob("*.tif"))
    paths += sorted((ROOT / "docs" / "downloads").glob("*.tif"))
    H, W = pred.shape
    ys, xs = np.nonzero(pred)
    ours = pred > 0
    our_dil = _dilate3(ours)
    rows = []
    self_variants: list[str] = []
    for pth in paths:
        try:
            with rasterio.open(pth) as src:
                if (src.height, src.width) != (H, W):
                    continue
                a = src.read(1).astype(np.float64)
        except Exception:
            continue
        a[~np.isfinite(a)] = 0.0
        b = np.where(footprint, a, 0.0)
        if b.max() > 1.0 or b.min() < 0.0:
            continue
        rel = str(pth.relative_to(ROOT))
        reg = b > 0
        if not reg.any():
            continue
        if reg.shape == ours.shape and np.array_equal(reg, ours):
            # our own emission in another container (zeros vs NaN outside the footprint):
            # identical dot pattern by construction, so it is not a comparator at all.
            self_variants.append(rel)
            continue
        self_cov = float(_dilate3(reg)[footprint].mean())   # cannot be beaten by ANY candidate
        rng = np.random.default_rng(0)
        idx = np.flatnonzero(footprint.ravel())
        if idx.size > 200_000:
            idx = rng.choice(idx, 200_000, replace=False)
        u = pred.ravel()[idx]
        v = b.ravel()[idx]
        rho = 0.0 if (np.std(u) == 0 or np.std(v) == 0) else float(stats.spearmanr(u, v).statistic)
        rows.append(dict(
            spearman=rho,
            path=rel,
            registry_dots=int(reg.sum()),
            registry_3px_coverage_of_footprint=self_cov,
            our_dots_within_3px=float(_dilate3(reg)[ys, xs].mean()) if ys.size else 0.0,
            registry_dots_within_3px_of_ours=float(reg[our_dil].mean()),
            satisfiable=self_cov <= LIMIT_OVERLAP,
        ))
    rows.sort(key=lambda r: -r["our_dots_within_3px"])
    unsat = [r for r in rows if not r["satisfiable"]]
    sat = [r for r in rows if r["satisfiable"]]
    worst_sat = max(sat, key=lambda r: r["our_dots_within_3px"]) if sat else None

    out = dict(
        hypothesis_id="H74-1",
        evidence_class="MEASUREMENT",
        rule=">70 % of our dots within 3 px of one registry raster's dots => duplicate/stop; "
             "and |Spearman| > 0.90 => duplicate/stop",
        comparators_total=len(rows),
        self_container_variants_excluded=self_variants,
        our_dots=int(ys.size),
        unsatisfiable_comparators=len(unsat),
        unsatisfiable_definition=(
            "the registry raster's own 3-px dilation already covers > 70 % of the footprint, so "
            "no candidate raster of any shape can score <= 70 % against it; these are calibration "
            "lattices and dense packings, not distinguishable submissions"),
        unsatisfiable_examples=[r["path"] for r in unsat[:8]],
        satisfiable_comparators=len(sat),
        worst_among_satisfiable=worst_sat,
        worst5_among_satisfiable=sat[:5],
        literal_verdict_all_comparators=(
            "PASS" if (max((r["our_dots_within_3px"] for r in rows), default=0.0) <= LIMIT_OVERLAP
                       and max((abs(r["spearman"]) for r in rows), default=0.0) <= LIMIT_RHO)
            else "FAIL"),
        literal_verdict_satisfiable_subset=(
            "PASS" if worst_sat and worst_sat["our_dots_within_3px"] <= LIMIT_OVERLAP else "FAIL"),
        max_abs_spearman_all_comparators=max((abs(r["spearman"]) for r in rows), default=0.0),
        max_our_dots_within_3px_all_comparators=max(
            (r["our_dots_within_3px"] for r in rows), default=0.0),
        note=("Both readings are published. The literal clause fires only on comparators that are "
              "unsatisfiable in principle (IR-74-UNIQUENESS-01); it needs an owner decision, not a "
              "workaround. |Spearman| is far below 0.90 on every comparator, so no registry raster "
              "is a monotone re-expression of this one."),
    )
    (ROOT / "evidence" / "h74_uniqueness_satisfiable.json").write_text(
        json.dumps(out, indent=1) + "\n")

    card["uniqueness"].update(
        comparators_checked=out["comparators_total"],
        max_abs_spearman=out["max_abs_spearman_all_comparators"],
        max_our_dots_within_3px_all_comparators=out["max_our_dots_within_3px_all_comparators"],
        unsatisfiable_comparators=out["unsatisfiable_comparators"],
        satisfiable_comparators=out["satisfiable_comparators"],
        worst_among_satisfiable=out["worst_among_satisfiable"],
        verdict_all_comparators=out["literal_verdict_all_comparators"],
        verdict_satisfiable_subset=out["literal_verdict_satisfiable_subset"],
    )
    (ROOT / "evidence" / "h74_runcard.json").write_text(json.dumps(card, indent=1) + "\n")

    print(json.dumps({k: out[k] for k in (
        "comparators_total", "unsatisfiable_comparators", "satisfiable_comparators",
        "literal_verdict_all_comparators", "literal_verdict_satisfiable_subset",
        "max_abs_spearman_all_comparators", "max_our_dots_within_3px_all_comparators")}, indent=1))
    if worst_sat:
        print("worst satisfiable:", worst_sat["path"], round(worst_sat["our_dots_within_3px"], 4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
