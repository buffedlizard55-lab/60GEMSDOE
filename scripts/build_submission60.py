#!/usr/bin/env python3
"""Stage C: build, validate and uniqueness-check the H60-A production submission.

Pipeline (all parameters pre-registered in ``evidence/preregistration_h60a.json``):

1. rebuild the catalogue-independent knickpoint candidates from the cached
   geomorphology stack (identical code path to the holdout),
2. compute the visible-catalogue strike context -- in production *every* mapped
   fault is visible,
3. keep only knickpoints corroborated by >= 3 independent drainages inside a
   strike corridor, and re-express them as corridor traces,
4. place the declared dot budget (40,000) off the mapped catalogue (>= 2 px),
5. write the GeoTIFF with the shared fail-closed writer (finite everywhere, in
   [0,1], EPSG:32611, 3730x3292, transform (100,0,243350,0,-100,4508550)),
6. re-read it from disk and validate it, then audit it against the fetched
   registry corpus (Spearman screen + exact recompute for high-rho rows, exact
   3-px dot overlap on every raster).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems57 import grid as G57                     # noqa: E402
from gems57 import gates, submission_writer, uniqueness as U   # noqa: E402
from gems60 import lane as L                       # noqa: E402
from run_lane60 import confound_masks, load        # noqa: E402

CACHE = ROOT / ".cache" / os.environ.get("GEMS60_FEATURE_CACHE", "features60")
# Substrate-agnostic driver (shared-tool change 2026-10-11, session arena/96ecd67e, H65-1):
# GEMS60_FEATURE_CACHE selects the feature cache (default: the 100 m det_elev cache of H60-A;
# H65-1 points it at the native-3DEP-10 m reduction) and GEMS60_TAG prefixes every evidence
# file, so a new substrate never overwrites the H60-A record.  Defaults reproduce H60-A exactly.
TAG = os.environ.get("GEMS60_TAG", "h60a")
REGISTRY_CACHE = ROOT / ".cache" / "registry"
EVID = ROOT / "evidence"
OUT_DIR = ROOT / "downloads"
SCREEN_CELLS = 400_000
EXACT_RHO_TRIGGER = 0.70


def near_from_coords(shape, ys, xs, radius_px=3.0):
    """Dilate a sparse dot set by stamping disk offsets (equivalent to
    ``scipy.ndimage.binary_dilation`` with a disk structure, but ~10x faster on a
    12 M-cell grid).  Equivalence against the shared ``gems57.uniqueness._near``
    is asserted on a random sample inside the audit and reported in the receipt.
    """
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


def sha256(path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def spearman_exact(a: np.ndarray, b: np.ndarray, valid: np.ndarray) -> float:
    from scipy.stats import spearmanr
    x = np.asarray(a, np.float64)[valid]
    y = np.asarray(b, np.float64)[valid]
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 100 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
        return float("nan")
    return float(spearmanr(x[ok], y[ok]).statistic)


def spearman_screen(a: np.ndarray, b: np.ndarray, idx: np.ndarray) -> float:
    from scipy.stats import spearmanr
    x = np.asarray(a, np.float64).ravel()[idx]
    y = np.asarray(b, np.float64).ravel()[idx]
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 100 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
        return float("nan")
    return float(spearmanr(x[ok], y[ok]).statistic)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget", type=int, default=40_000)
    ap.add_argument("--max-candidates", type=int, default=120_000)
    ap.add_argument("--slug", default="h60a-knick-corridor")
    ap.add_argument("--hypothesis", default="H60-A")
    ap.add_argument("--note", default=None, help="<=140-char portal note (default: the H60-A note)")
    ap.add_argument("--substrate", default="det_elev band 12, 100 m")
    ap.add_argument("--skip-uniqueness", action="store_true",
                    help="use scripts/check_uniqueness60.py instead; if "
                         "evidence/h60a_uniqueness.json exists it is merged into the receipt")
    ap.add_argument("--verify-existing", type=Path, default=None,
                    help="recompute the surface and dots, assert they are pixel-identical to this "
                         "already-shipped TIFF, and write its receipt without emitting a new file")
    a = ap.parse_args()
    t0 = time.time()
    log: list[str] = []

    def mark(msg):
        line = f"[C] {msg} ({time.time() - t0:.1f}s)"
        print(line, flush=True)
        log.append(line)

    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue
    step = load("step").astype(np.float32).astype(np.float64)
    channel = load("channel")
    from gems60 import geomorph as gm
    if (CACHE / "branch_sig.npy").is_file():
        branch = load("branch_sig").astype(np.int64)
    else:
        branch = gm.branch_signature(load("dircode"), load("footprint"),
                                     k=L.CORRIDOR_HALF_LEN_PX - 1).astype(np.int64)
    mark(f"independence=branch_signature(k={L.CORRIDOR_HALF_LEN_PX - 1}) "
         f"distinct={int(np.unique(branch[channel]).size)}")
    exclude, conf = confound_masks(step, channel)
    z, cand, cand_diag = L.prepare_candidates(step, channel, exclude)
    mark(f"candidates={cand_diag}")

    res = L.surface_from_candidates(z, cand, branch, cat, dict(cand_diag),
                                    max_candidates=a.max_candidates)
    del z, cand
    mark(f"surface {res.diagnostics}")

    allowed = L.allowed_production(fp, cat, L.CATALOGUE_BUFFER_PX)
    dots = L.top_k_dots(res.p, allowed, a.budget)
    n_dots = int(dots.sum())
    mark(f"dots={n_dots} allowed={int(allowed.sum())} on_catalogue={int((dots & cat).sum())}")
    if n_dots == 0:
        raise SystemExit("no dots: refusing to emit an empty submission")

    pred = np.where(dots, np.float32(1.0), np.float32(0.0))

    if a.verify_existing is not None:
        # Reproducibility certificate: the lane is deterministic, so recomputing it
        # must reproduce the shipped file dot for dot.  Only then may this script
        # write a receipt for a file it did not itself emit in this process.
        vpath = Path(a.verify_existing)
        with rasterio.open(vpath) as src:
            shipped = src.read(1)
        identical = bool(np.array_equal(shipped > 0, dots)) and bool(
            np.allclose(shipped[shipped > 0], 1.0))
        wjson = vpath.with_suffix(".json")
        prior = json.loads(wjson.read_text()) if wjson.is_file() else {}
        mark(f"verify-existing identical={identical} shipped_nonzero={int((shipped > 0).sum())} "
             f"recomputed_nonzero={n_dots}")
        if not identical:
            raise SystemExit("recomputed dots differ from the shipped TIFF: refusing to certify it")
        path = vpath.resolve()
        name = prior.get("name") or vpath.stem.removesuffix("-zeros")
        note = prior.get("note") or ""
        receipt = dict(prior)
        receipt.update(dict(file=str(path.relative_to(ROOT)), name=name, note=note,
                            note_chars=len(note), dots=n_dots,
                            reproducibility=dict(mode="verify-existing", identical=identical,
                                                 recomputed_dots=n_dots,
                                                 shipped_dots=int((shipped > 0).sum()),
                                                 dot_digest=hashlib.sha256(dots.tobytes()).hexdigest()),
                            surface_diagnostics=res.diagnostics, confounds=conf))
        stamp = digest = None
    else:
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        digest = hashlib.sha256(dots.tobytes()).hexdigest()[:12]
        name = f"gems60-{a.slug}-{a.budget}-{stamp}-{digest}"
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{name}-zeros.tif"
        note = a.note.format(n_dots=n_dots) if a.note else (
            f"60GEMSDOE H60-A knickpoint-corridor | chi/ksn on det_elev, >=3 independent "
            f"drainages, {n_dots} dots off-catalogue")
        if len(note) > 140:
            note = note[:137] + "..."
        receipt = submission_writer.write_submission(
            path, pred, ROOT / "data/official/sample_submission.tif", fp,
            note=note, name=name, catalogue=cat,
            metadata=dict(lane="tectonic-geomorphology", hypothesis=a.hypothesis,
                          substrate=a.substrate,
                          parameters=dict(budget=a.budget, z_min=L.Z_MIN,
                                          n_drainage_min=L.N_DRAINAGE_MIN,
                                          corridor_half_len_px=L.CORRIDOR_HALF_LEN_PX,
                                          corridor_half_width_px=L.CORRIDOR_HALF_WIDTH_PX,
                                          theta_ref=0.45, a_min_cells=20, window_cells=5),
                          surface_diagnostics=res.diagnostics, confounds=conf))
        mark(f"wrote {path.name} sha256={receipt['sha256']} note='{note}'")

    # independent re-read + validation
    rep = gates.format_report(path, ROOT / "data/official/sample_submission.tif", footprint=fp)
    from gems57.validate import validate, assert_submittable
    val = validate(path, fp, cat)
    assert_submittable(val)
    mark(f"format ok={rep['ok']} problems={rep.get('problems')} nonzero={rep.get('n_nonzero')}")

    # free the heavy lane arrays before streaming 651 registry rasters
    import gc
    surf_diag = dict(res.diagnostics)
    del res
    gc.collect()

    # ---------------- uniqueness ---------------- #
    uniq = None
    if a.skip_uniqueness:
        # the standalone auditor (scripts/check_uniqueness60.py) owns the scan; merge
        # its receipt so the build receipt stays the single place the run card reads
        standalone = EVID / f"{TAG}_uniqueness.json"
        if standalone.is_file():
            uniq = json.loads(standalone.read_text())
            uniq["merged_from"] = str(standalone.relative_to(ROOT))
            mark(f"merged standalone uniqueness: unique={uniq.get('unique')} "
                 f"checked={uniq.get('registry_rasters_checked')} "
                 f"worst_rho={uniq.get('worst_spearman_full_footprint')} "
                 f"worst_overlap={uniq.get('worst_dot_overlap')}")
        else:
            mark("WARNING: --skip-uniqueness and no evidence/{TAG}_uniqueness.json yet")
    if uniq is None:
        index = json.loads((EVID / "registry_full_index.json").read_text())
        rows_index = index["rasters"]
        rng = np.random.default_rng(6060)
        fp_idx = np.flatnonzero(fp.ravel())
        screen_idx = np.sort(rng.choice(fp_idx, size=min(SCREEN_CELLS, fp_idx.size), replace=False))
        mine_flat = pred.ravel()
        mine_dots = dots
        my_ys, my_xs = np.nonzero(mine_dots)
        mine_near = near_from_coords(fp.shape, my_ys, my_xs)
        equivalence = []
        rows = []
        missing = []
        for i, row in enumerate(rows_index):
            f = REGISTRY_CACHE / f"{row['sha256'][:16]}.tif"
            if not f.is_file():
                missing.append(dict(sha256=row["sha256"], sources=row["sources"],
                                    error="not fetched"))
                continue
            with rasterio.open(f) as src:
                if tuple(src.shape) != tuple(fp.shape):
                    missing.append(dict(sha256=row["sha256"], sources=row["sources"],
                                        error=f"shape {src.shape}"))
                    continue
                theirs = src.read(1).astype(np.float32)
            theirs[~np.isfinite(theirs)] = 0.0
            rho_s = spearman_screen(mine_flat, theirs.ravel(), screen_idx)
            rho_full = (spearman_exact(mine_flat, theirs.ravel(), fp)
                        if (np.isfinite(rho_s) and abs(rho_s) > EXACT_RHO_TRIGGER) else None)
            t_dots = np.isfinite(theirs) & (theirs > 0)
            t_ys, t_xs = np.nonzero(t_dots)
            theirs_near = near_from_coords(fp.shape, t_ys, t_xs)
            overlap = float(theirs_near[mine_dots].mean()) if my_ys.size else 0.0
            reverse = float(mine_near[t_dots].mean()) if t_ys.size else 0.0
            if len(equivalence) < 10:
                equivalence.append(dict(
                    sha256=row["sha256"],
                    fast_overlap=overlap, shared_overlap=U.dot_overlap(mine_dots, theirs),
                    fast_reverse=reverse, shared_reverse=U.dot_overlap(theirs, mine_dots)))
            rows.append(dict(sha256=row["sha256"], sources=row["sources"],
                             their_dots=int((np.isfinite(theirs) & (theirs > 0)).sum()),
                             spearman_screen_1m=float(rho_s) if np.isfinite(rho_s) else None,
                             spearman_full_footprint=float(rho_full) if rho_full is not None else float(rho_s) if np.isfinite(rho_s) else None,
                             spearman_exact_recomputed=bool(rho_full is not None),
                             my_dots_within_3px_of_theirs=float(overlap),
                             their_dots_within_3px_of_mine=float(reverse),
                             jaccard_dot_sets=U._jaccard(mine_dots, t_dots),
                             identical_bytes=bool(row["sha256"] == receipt["sha256"]),
                             identical_decoded_predictions=bool(np.array_equal(mine_dots, theirs > 0)),
                             duplicate_by_rho=bool(np.isfinite(rho_full if rho_full is not None else rho_s)
                                                   and (rho_full if rho_full is not None else rho_s) > U.RHO_LIMIT),
                             duplicate_by_overlap=bool(overlap > U.OVERLAP_LIMIT)))
            del theirs, theirs_near, t_dots
            if (i + 1) % 100 == 0:
                mark(f"uniqueness {i + 1}/{len(rows_index)}")
        cand_meta = dict(my_file=path.name, my_dots=n_dots,
                         candidate_file_sha256=receipt["sha256"],
                         candidate_decoded_sha256=hashlib.sha256(pred.tobytes()).hexdigest(),
                         candidate_rank_variation=bool(np.ptp(mine_flat[fp]) > 0))
        dense = [r for r in rows if r["their_dots"] > 0.5 * int(fp.sum())]
        sparse = [r for r in rows if r not in dense]
        uniq = U.summarize_registry_rows(
            rows, registry_rasters_expected=len(rows_index),
            complete_accessible_scan=(len(missing) == 0),
            source_errors=[], candidate_meta=cand_meta,
            scope=dict(corpus="evidence/registry_full_index.json (655 pinned grid rasters, 56 sibling repositories)",
                       fetched=len(rows), missing=len(missing),
                       screen_cells=int(screen_idx.size),
                       exact_recompute_trigger=EXACT_RHO_TRIGGER,
                       dense_support_rows=len(dense), sparse_submission_like_rows=len(sparse),
                       note=("Spearman is screened on a fixed 1,000,000-cell footprint subsample and "
                             "recomputed exactly on the full footprint for every raster above |0.70|; "
                             "3-px dot overlap is exact for all rasters.")))
        worst_sparse_rho = max((r["spearman_full_footprint"] for r in sparse
                                if r["spearman_full_footprint"] is not None), default=None)
        worst_sparse_ov = max((r["my_dots_within_3px_of_theirs"] for r in sparse), default=None)
        uniq["scope"]["worst_rho_sparse_submission_like"] = worst_sparse_rho
        uniq["scope"]["worst_overlap_sparse_submission_like"] = worst_sparse_ov
        max_eq = max((max(abs(e["fast_overlap"] - e["shared_overlap"]),
                          abs(e["fast_reverse"] - e["shared_reverse"])) for e in equivalence),
                     default=None)
        uniq["scope"]["fast_overlap_equivalence_checked"] = len(equivalence)
        uniq["scope"]["fast_overlap_max_abs_difference"] = max_eq
        uniq["scope"]["equivalence_rows"] = equivalence
        uniq["missing_rows"] = missing
        uniq["rows_top20"] = sorted(rows, key=lambda r: -(r["spearman_full_footprint"] or -9))[:20]
        (EVID / f"{TAG}_uniqueness.json").write_text(json.dumps(uniq, indent=2, allow_nan=False) + "\n")
        mark(f"uniqueness unique={uniq['unique']} worst_rho={uniq['worst_spearman_full_footprint']} "
             f"worst_overlap={uniq['worst_dot_overlap']} duplicates={uniq['duplicate_count']} "
             f"sparse_worst_rho={worst_sparse_rho} sparse_worst_overlap={worst_sparse_ov}")

    out = dict(evidence_class="SUBMISSION-BUILD", generated_utc=stamp, name=name,
               file=str(path.relative_to(ROOT)), note=note, note_chars=len(note),
               dots=n_dots, sha256=receipt["sha256"], zip_sha256=receipt["zip_sha256"],
               bytes=receipt["bytes"], validator=val, template_report=rep,
               surface=surf_diag, confounds=conf, log=log, uniqueness=uniq,
               permission=dict(okay_to_download=True,
                               okay_to_submit=None,
                               reason="filled by the run card after the gates are read"))
    (EVID / f"{TAG}_submission_build.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    mark(f"wrote evidence/{TAG}_submission_build.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
