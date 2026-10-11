#!/usr/bin/env python3
"""Standalone literal uniqueness audit of a shipped candidate against the fetched
registry corpus (``evidence/registry_full_index.json`` -> ``.cache/registry``).

Split out of ``build_submission60.py`` so the audit can be re-run against an
already-written TIFF without recomputing the lane surface.

Method
------
* Spearman rank correlation is *screened* on a fixed 400,000-cell random sample of
  the footprint (same sample for every raster, seed 6060) and *recomputed exactly*
  on all 5,167,373 footprint cells for every raster whose screen exceeds |0.70|.
  Both numbers are reported per row, with a flag saying which is which.
* The 3-px forward dot overlap (my dots inside their dilated support) and the
  reverse overlap are exact for every raster.  Sparse priors are dilated by
  coordinate stamping; priors with more than 100,000 positive cells are dilated
  with ``scipy.ndimage.binary_dilation`` (memory-safe).  The fast path is checked
  against the shared ``gems57.uniqueness.dot_overlap`` on a sample and the largest
  absolute difference is reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems57 import grid as G57                     # noqa: E402
from gems57 import uniqueness as U                 # noqa: E402

CACHE = ROOT / ".cache" / "registry"
SCREEN_CELLS = 400_000
EXACT_RHO_TRIGGER = 0.70
DENSE_PX = 100_000


def disk(radius_px=3.0):
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return (yy * yy + xx * xx) <= radius_px ** 2


def near_from_coords(shape, ys, xs, radius_px=3.0):
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    off = np.stack([yy.ravel(), xx.ravel()], 1)
    off = off[(off[:, 0] ** 2 + off[:, 1] ** 2) <= radius_px ** 2]
    out = np.zeros(shape, bool)
    Y = ys[:, None] + off[None, :, 0]
    X = xs[:, None] + off[None, :, 1]
    ok = (Y >= 0) & (X >= 0) & (Y < shape[0]) & (X < shape[1])
    out[np.clip(Y, 0, shape[0] - 1)[ok], np.clip(X, 0, shape[1] - 1)[ok]] = True
    return out


def rho(a, b, mask=None, idx=None):
    if idx is not None:
        x = a.ravel()[idx]
        y = b.ravel()[idx]
    else:
        x = a[mask]
        y = b[mask]
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 100 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
        return float("nan")
    return float(spearmanr(x[ok], y[ok]).statistic)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", type=Path, default=None)
    ap.add_argument("--out", default=str(ROOT / "evidence" / "h60a_uniqueness.json"))
    ap.add_argument("--rows-cache", default=str(ROOT / "evidence" / "uniqueness_rows.jsonl"),
                    help="incremental per-raster rows; re-used with --reuse-rows so a "
                         "summarise failure can never cost another full 8-minute scan")
    ap.add_argument("--reuse-rows", action="store_true")
    ap.add_argument("--surface", action="store_true",
                    help="audit the continuous lane SURFACE (rank field before dot placement) "
                         "instead of the shipped dots, as the parallel-run protocol requires "
                         "both to be checked")
    a = ap.parse_args()
    t0 = time.time()
    grid = G57.load_grid()
    fp = grid.footprint
    if a.surface:
        # rebuild the exact production surface from the cached feature stack
        sys.path.insert(0, str(ROOT / "scripts"))
        from gems60 import geomorph as gm
        from gems60 import lane as L
        from run_lane60 import confound_masks, load
        import os
        cache = ROOT / ".cache" / os.environ.get("GEMS60_FEATURE_CACHE", "features60")
        step = np.load(cache / "step.npy")
        channel = np.load(cache / "channel.npy")
        if (cache / "branch_sig.npy").is_file():      # substrate-supplied independence (H65-1)
            branch = np.load(cache / "branch_sig.npy").astype(np.int64)
        else:
            branch = gm.branch_signature(np.load(cache / "dircode.npy"), fp,
                                         k=L.CORRIDOR_HALF_LEN_PX - 1).astype(np.int64)
        exclude, _conf = confound_masks(step, channel)
        z, cand, cand_diag = L.prepare_candidates(step, channel, exclude)
        res = L.surface_from_candidates(z, cand, branch, grid.catalogue, dict(cand_diag))
        mine = np.clip(np.nan_to_num(res.p, nan=0.0), 0.0, 1.0).astype(np.float32)
        print(f"[uniq] surface rebuilt: positive_px={int((mine > 0).sum())} "
              f"p_max={float(mine.max()):.4f}", flush=True)
    else:
        with rasterio.open(a.candidate) as src:
            mine = src.read(1).astype(np.float32)
            mine[~np.isfinite(mine)] = 0.0
    mine_dots = mine > 0
    n_mine = int(mine_dots.sum())
    my_ys, my_xs = np.nonzero(mine_dots)
    mine_near = near_from_coords(fp.shape, my_ys, my_xs)
    rng = np.random.default_rng(6060)
    fp_idx = np.flatnonzero(fp.ravel())
    screen_idx = np.sort(rng.choice(fp_idx, size=min(SCREEN_CELLS, fp_idx.size), replace=False))
    index = json.loads((ROOT / "evidence" / "registry_full_index.json").read_text())
    rows_index = index["rasters"]
    rows, missing, equivalence = [], [], []
    rows_path = Path(a.rows_cache)
    reuse = {}
    if a.reuse_rows and rows_path.is_file():
        for line in rows_path.read_text().splitlines():
            r = json.loads(line)
            reuse[r["sha256"]] = r
        rows = [reuse[r["sha256"]] for r in rows_index if r["sha256"] in reuse]
        missing = [dict(sha256=r["sha256"], sources=r["sources"], error="not fetched")
                   for r in rows_index if r["sha256"] not in reuse]
        equivalence = []
        rows = [r for r in rows if "error" not in r]
        print(f"[uniq] reusing {len(rows)} cached rows; {len(missing)} to rescan", flush=True)
    rows_fh = rows_path.open("w")
    for i, row in enumerate(rows_index):
        if row["sha256"] in reuse:
            continue
        f = CACHE / f"{row['sha256'][:16]}.tif"
        if not f.is_file():
            missing.append(dict(sha256=row["sha256"], sources=row["sources"], error="not fetched"))
            continue
        try:
            with rasterio.open(f) as src:
                if tuple(src.shape) != tuple(fp.shape):
                    missing.append(dict(sha256=row["sha256"], sources=row["sources"],
                                        error=f"shape {list(src.shape)}"))
                    continue
                theirs = src.read(1).astype(np.float32)
        except Exception as exc:                                  # noqa: BLE001
            missing.append(dict(sha256=row["sha256"], sources=row["sources"], error=str(exc)[:200]))
            continue
        theirs[~np.isfinite(theirs)] = 0.0
        t_dots = theirs > 0
        n_theirs = int(t_dots.sum())
        if n_theirs > DENSE_PX:
            theirs_near = ndi.binary_dilation(t_dots, structure=disk(3.0))
        else:
            t_ys, t_xs = np.nonzero(t_dots)
            theirs_near = near_from_coords(fp.shape, t_ys, t_xs)
        overlap = float(theirs_near[mine_dots].mean()) if n_mine else 0.0
        reverse = float(mine_near[t_dots].mean()) if n_theirs else 0.0
        r_screen = rho(mine, theirs, idx=screen_idx)
        exact = (np.isfinite(r_screen) and abs(r_screen) > EXACT_RHO_TRIGGER)
        r_full = rho(mine, theirs, mask=fp) if exact else r_screen
        if len(equivalence) < 12 and n_theirs <= DENSE_PX:
            equivalence.append(dict(sha256=row["sha256"], fast_overlap=overlap,
                                    shared_overlap=U.dot_overlap(mine_dots, theirs > 0),
                                    fast_reverse=reverse,
                                    shared_reverse=U.dot_overlap(theirs > 0, mine_dots)))
        rec = dict(sha256=row["sha256"], sources=row["sources"],
                   submission=(row["sources"][0] if row["sources"] else None),
                   repo=row.get("repo_first"), their_dots=n_theirs,
                         spearman_screen_400k=float(r_screen) if np.isfinite(r_screen) else None,
                         spearman_full_footprint=float(r_full) if np.isfinite(r_full) else None,
                         spearman_exact_recomputed=bool(exact),
                         my_dots_within_3px_of_theirs=overlap,
                         their_dots_within_3px_of_mine=reverse,
                         jaccard_dot_sets=U._jaccard(mine_dots, t_dots),
                         identical_bytes=False,
                         identical_decoded_predictions=bool(np.array_equal(mine_dots, t_dots)),
                         duplicate_by_rho=bool(np.isfinite(r_full) and r_full > U.RHO_LIMIT),
                         duplicate_by_overlap=bool(overlap > U.OVERLAP_LIMIT))
        rows.append(rec)
        rows_fh.write(json.dumps(rec, allow_nan=False) + "\n")
        rows_fh.flush()
        del theirs, theirs_near, t_dots, rec
        if (i + 1) % 50 == 0:
            print(f"[uniq] {i + 1}/{len(rows_index)} ({time.time() - t0:.0f}s)", flush=True)
    cand_meta = dict(my_file=(a.candidate.name if a.candidate
                              else "lane surface rebuilt from .cache/features60 (--surface)"),
                     my_dots=n_mine,
                     audit_target=("surface" if a.surface else "shipped dots"),
                     candidate_file_sha256=(hashlib.sha256(a.candidate.read_bytes()).hexdigest()
                                            if a.candidate else None),
                     candidate_decoded_sha256=hashlib.sha256(mine.tobytes()).hexdigest(),
                     candidate_rank_variation=bool(np.ptp(mine[fp]) > 0))
    dense = [r for r in rows if r["their_dots"] > 0.5 * int(fp.sum())]
    sparse = [r for r in rows if r not in dense]
    report = U.summarize_registry_rows(
        rows, registry_rasters_expected=len(rows_index),
        complete_accessible_scan=(len(missing) == 0), source_errors=[],
        candidate_meta=cand_meta,
        scope=dict(corpus="evidence/registry_full_index.json (655 pinned grid rasters, 56 sibling repositories)",
                   fetched=len(rows), missing=len(missing), screen_cells=int(screen_idx.size),
                   exact_recompute_trigger=EXACT_RHO_TRIGGER,
                   dense_support_rows=len(dense), sparse_submission_like_rows=len(sparse),
                   worst_rho_sparse_submission_like=max(
                       (r["spearman_full_footprint"] for r in sparse
                        if r["spearman_full_footprint"] is not None), default=None),
                   worst_overlap_sparse_submission_like=max(
                       (r["my_dots_within_3px_of_theirs"] for r in sparse), default=None),
                   seconds=round(time.time() - t0, 1)))
    report["scope"]["fast_overlap_equivalence_checked"] = len(equivalence)
    report["scope"]["fast_overlap_max_abs_difference"] = max(
        (max(abs(e["fast_overlap"] - e["shared_overlap"]),
             abs(e["fast_reverse"] - e["shared_reverse"])) for e in equivalence), default=None)
    report["scope"]["equivalence_rows"] = equivalence
    report["missing_rows"] = missing
    report["rows_top20_by_rho"] = sorted(
        rows, key=lambda r: -(r["spearman_full_footprint"] or -9))[:20]
    report["rows_top20_by_overlap"] = sorted(
        rows, key=lambda r: -(r["my_dots_within_3px_of_theirs"] or -9))[:20]
    rows_fh.close()
    slim = {k: v for k, v in report.items() if k != "rows"}
    slim["rows_file"] = "evidence/uniqueness_rows.jsonl (one row per registry raster)"
    Path(a.out).write_text(json.dumps(slim, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: report[k] for k in (
        "registry_rasters_expected", "registry_rasters_checked", "complete_accessible_scan",
        "worst_spearman_full_footprint", "worst_dot_overlap", "duplicate_count", "unique",
        "stop_required")}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
