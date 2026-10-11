#!/usr/bin/env python3
"""Measure every candidate artifact this session touched on the *same* instruments, honestly.

Arms: the live-scored champion, the three lane artifacts on main (H65-1, H66-1, H68-1), the two
complementary-cover probes (H71-A 6,000 / H71-B 12,000) and the union (H72 = champion + H71-A), plus
the derived H68-1 + H71-A.

Instruments (both are proxies, neither is an organizer score):
  * SGMC-off-catalogue: 62,226 state-geological-map fault pixels >300 m from the given catalogue.
  * registered catalogue holdout: gems57-pooled-hide-v2, 8 cells, shared evaluator.
Governance: every arm's literal 3-px overlap against the local corpus is measured and reported, so
the "can this be submitted at all" question is answered with numbers rather than judgement.

Writes ``evidence/h71_artifact_comparison.json``.  Read-only: builds no submission.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems57 import evaluate_holdout as EH   # noqa: E402
from gems57 import grid as G57              # noqa: E402
from gems57 import holdout as HO            # noqa: E402
from gems57 import metric as M              # noqa: E402
from gems61 import instruments as I         # noqa: E402

DL = ROOT / "docs" / "downloads"
REG = ROOT / "registry" / "rasters"
EXT = ROOT / "data" / "external"
BLOCK_PX, DRAWS, SEED = 200, 1000, 7001
_RHO = np.random.default_rng(70).choice(12_279_160, size=400_000, replace=False)
PROTOCOL_NOTE = ("holdout numbers use the 8 cells with mode == 'all' of gems57-pooled-hide-v2 "
                 "(block_side 200 px); comparable across the arms in this file only, not the "
                 "pooled values printed in the run cards")

ARMS = {
    "champion_h33_2_b2": "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif",
    "H65_1_lane": "gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif",
    "H66_1_lane": "gems60-h66-dem10-bedrock-dksn-40000-20261011T162456Z-dbafa4373009-zeros.tif",
    "H68_1_lane": "gems60-h68-dem10-lidar-piedmont-dksn-40000-20261011T185033Z-6e9b1e286c45-zeros.tif",
    "H71A_probe": "gems60-h71a-convcomp-6000-20261011T185116Z-zeros.tif",
    "H71B_field": "gems60-h71b-convcomp-12000-20261011T184819Z-zeros.tif",
    "H72_union": "gems60-h72-union-champ-convcomp-43654-20261011T191739Z-zeros.tif",
}


def read_mask(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
    a[~np.isfinite(a)] = 0.0
    return a > 0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    t0 = time.time()
    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue

    arms = {}
    for name, fname in ARMS.items():
        p = DL / fname
        if not p.is_file():
            print(f"MISSING {fname}")
            return 2
        arms[name] = read_mask(p)
    arms["H68_1_plus_H71A"] = arms["H68_1_lane"] | arms["H71A_probe"]
    print(f"arms built ({time.time() - t0:.1f}s): "
          + ", ".join(f"{k}={int(v.sum()):,}" for k, v in arms.items()), flush=True)

    # ---------------- instrument 1: SGMC-off-catalogue ---------------- #
    with rasterio.open(EXT / "sgmc_faults_100m.tif") as src:
        sgmc = src.read(1)
    sgmc[sgmc == 255] = 0
    offcat = I.sgmc_off_catalogue(sgmc > 0, cat, fp, buffer_px=3)
    print(f"sgmc-off truth px: {int(offcat.sum()):,}", flush=True)
    inst = {k: I.global_dti(v.astype(np.float64), offcat, fp, cat) for k, v in arms.items()}

    # ---------------- instrument 2: registered holdout ---------------- #
    ctx = HO.build_holdout(grid)
    cells = [c for c in ctx.cells if c.mode == "all"]
    terms = {k: [] for k in arms}
    for cell in cells:
        bb = cell.bbox
        truth_crop = ctx.hidden_by_cell[cell.key][bb] & cell.active
        fold = dict(region=cell.active, visible=np.zeros_like(cell.active), truth=truth_crop)
        for k, arr in arms.items():
            _, tt = EH.evaluate(arr[bb].astype(np.float32), fold, grid.footprint[bb],
                                block_side=BLOCK_PX, origin=(bb[0].start, bb[1].start),
                                global_shape=(grid.height, grid.width))
            terms[k].append(tt)
    pooled = EH.pooled_summary({k: np.sum(v, axis=0) for k, v in terms.items()},
                               draws=DRAWS, seed=SEED, candidate="H68_1_plus_H71A")
    print(f"holdout done ({time.time() - t0:.1f}s)", flush=True)

    # ---------------- governance: literal overlap vs the corpus ---------------- #
    corpus = sorted(set(REG.glob("*.tif")) | set(DL.glob("*.tif")))
    names = {v for v in ARMS.values()}
    rows = {k: dict(max_overlap=0.0, worst=None, max_abs_rho=0.0) for k in arms}
    for f in corpus:
        if f.name in names:
            continue
        try:
            with rasterio.open(f) as src:
                if (src.height, src.width) != fp.shape:
                    continue
                a = src.read(1).astype(np.float32)
        except Exception:                                          # pragma: no cover
            continue
        a[~np.isfinite(a)] = 0.0
        m = a > 0
        if not m.any():
            continue
        d = ndi.distance_transform_edt(~m)
        for k, arr in arms.items():
            ov = float((d[arr] <= 3.0).mean())
            if ov > rows[k]["max_overlap"]:
                rows[k]["max_overlap"] = round(ov, 6)
                rows[k]["worst"] = f.name
        x = a.ravel().astype(np.float64)
        if not np.isfinite(x).all():
            continue
        for k, arr in arms.items():
            y = arr.ravel().astype(np.float64)
            rho = abs(float(np.corrcoef(rankdata(x[_RHO]), rankdata(y[_RHO]))[0, 1]))
            rows[k]["max_abs_rho"] = round(max(rows[k]["max_abs_rho"], rho), 6)
    print(f"corpus scan done ({time.time() - t0:.1f}s), {len(corpus)} files", flush=True)

    # cross-arm overlap of the two complements
    d_h68 = ndi.distance_transform_edt(~arms["H68_1_lane"])
    d_h71a = ndi.distance_transform_edt(~arms["H71A_probe"])
    cross = dict(
        h71a_dots_within_3px_of_h68_1=round(float((d_h68[arms["H71A_probe"]] <= 3.0).mean()), 6),
        h68_1_dots_within_3px_of_h71a=round(float((d_h71a[arms["H68_1_lane"]] <= 3.0).mean()), 6),
        note=("if the probes are mutually distant, the H68-1 field and the H71-A complement are additive "
              "in max-cover terms; if not, the complement is already covered by H68-1"))

    out = dict(
        run="H71-artifact-comparison", generated_utc=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        evidence_class="proxies only (HOLDOUT-DTI + INSTRUMENT-DTI); NOT organizer-confirmed",
        governance=("registry/current_site_status.json STOP + the literal 70-raster uniqueness rule with no "
                    "dense/lattice exception: any arm whose max_overlap > 0.70 is NOT CLEARED to submit, and "
                    "the two lattice comparators put every arm above 0.70"),
        arms={k: dict(file=ARMS.get(k, "derived"), dots=int(v.sum()), sha256=(sha256(DL / ARMS[k])
                   if k in ARMS else None)) for k, v in arms.items()},
        instrument_sgmc_off=inst,
        holdout_pooled=pooled,
        literal_uniqueness=rows,
        protocol_note=PROTOCOL_NOTE,
        cross_overlap=cross,
        seconds=round(time.time() - t0, 1))
    (ROOT / "evidence" / "h71_artifact_comparison.json").write_text(
        json.dumps(out, indent=2, default=float) + "\n")
    for k in arms:
        print(f"{k:22s} dots={int(arms[k].sum()):6,} sgmc_off dti={inst[k]['dti']:.5f} "
              f"c/px={inst[k]['credit_per_px']:.4f} holdout={pooled['scores'][k]['dti']:.6f} "
              f"lit_overlap={rows[k]['max_overlap']:.4f}")
    print("wrote evidence/h71_artifact_comparison.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
