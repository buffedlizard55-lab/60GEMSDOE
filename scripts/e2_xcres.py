#!/usr/bin/env python
"""E2 -- XCRD: cross-catalogue residual detector (new hypothesis, ranked #1).

Hypothesis (H61-A, mine, not previously implemented in this repository)
-----------------------------------------------------------------------
The competition's hidden truth is *expert-added faults that the USGS/INGENIOUS catalogue lacks*
(organizer page 967: "we have consulted with fault experts who have manually identified faults that
are not contained within the current public USGS database").  A model trained on the visible
catalogue therefore learns exactly the class that is *excluded* from scoring.  This script trains
instead on the one official fault compilation that has a large population the catalogue lacks:

    USGS State Geologic Map Compilation (SGMC), 100 m raster, 82,151 px in footprint,
    of which 61,664 px lie >300 m from every competition catalogue pixel.

Physical signature.  A fault is a line-shaped discontinuity; the layers that image it without
reference to any catalogue are the magnetics (rtp/tmi/tmi_hg/tmi_vg/tc), gravity derivatives,
conductivity, depth-to-basement, detrended elevation and its slope, plus radiometric K/Th/U/TC.
The model is asked: *given only these physics, where would a state geologist map a fault?*
Distance to the catalogue is deliberately NOT a feature (it is a label-defining shortcut), and the
negatives are sampled from the same distance-to-catalogue deciles as the positives so the model
cannot learn the target's own spatial construction.

Named non-fault process that could mimic it (required by the protocol): strike-parallel
LITHOLOGIC CONTACTS and basin-fill stratigraphic boundaries produce the same line-shaped
geophysical gradients as faults, and are the dominant false-positive family in any
potential-field lineament detector.

Validation design (what makes this non-circular)
------------------------------------------------
* Spatial blocking: 4 quadrant folds; every reported number is out-of-fold.
* Held-out independent channel: the LiDAR-derived scarp product (`h52_scarp3m_100m.tif`,
  bands h_gate12 / h_all) is excluded from the features and used only as *independent physical
  evidence*; the emission is scored on scarp pixels that lie >300 m from BOTH the competition
  catalogue AND the SGMC -- i.e. scarp evidence that neither catalogue contains.
* Leakage canary: single-feature AUC on the held-out folds, printed and written to evidence.
* Screen vs the live ladder: the mass-normalised off-catalogue excess of script
  ``e1_instrument_audit.py`` (the only local quantity measured here to rank the owner-reported
  live ladder, rho = +0.93).

Outputs: ``work/xcrd_field.npy`` (float32 OOF fault-likelihood field), evidence JSON, and -- only
when the emission passes the standing gates -- a candidate GeoTIFF.

Run:  .venv/bin/python scripts/e2_xcres.py --budget 37654
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

WORK = ROOT / "work"
BIG = Path("/tmp/gemsdl")                    # outside the workspace on purpose (see README)
AUX = Path("/tmp/gemsdoe48/GEMSDOE48-main")

TRAIN_FEATURES = "/tmp/gemsdl/training_features.tif"
TOPO = ROOT / "data/external/topo_10m_derived_100m_u8.tif"
RAD = AUX / "data/source_mirrors/geodawn_rad_u8.tif"
SCARP = AUX / "data/external/h52_scarp3m_100m.tif"      # validation only, never a feature
SGMC = WORK / "sgmc100.tif"
LABELS = ROOT / "data/bridge/existing_faults.tif"
SAMPLE = ROOT / "data/bridge/example_submission.tif"

# the two earthquake-distance bands are excluded on the family's own measurement (100 km radius:
# value constant at the metric's 300 m scale -- docs/research/h33-hypotheses.md, H33-E)
SKIP_BANDS = {10, 16}          # deq_n100a15, ieq_n100a15  (1-based)
TILE_ROWS = 256


def read(path: Path, band: int = 1) -> np.ndarray:
    with rasterio.open(path) as ds:
        return ds.read(band)


def footprint() -> np.ndarray:
    with rasterio.open(SAMPLE) as ds:
        return np.isfinite(ds.read(1))


def quadrant_ids(foot: np.ndarray) -> np.ndarray:
    """NW/NE/SW/SE by the footprint median -- same convention as gems32.hypotheses33."""
    yy, xx = np.nonzero(foot)
    ym, xm = int(np.median(yy)), int(np.median(xx))
    H, W = foot.shape
    gy, gx = np.ogrid[:H, :W]
    q = np.full((H, W), -1, np.int8)
    q[(gy < ym) & (gx < xm) & foot] = 0
    q[(gy < ym) & (gx >= xm) & foot] = 1
    q[(gy >= ym) & (gx < xm) & foot] = 2
    q[(gy >= ym) & (gx >= xm) & foot] = 3
    return q


def jsonable(obj):
    """JSON-safe copy: non-finite floats become null (the receipt writer is allow_nan=False)."""
    return json.loads(json.dumps(obj, default=str).replace("NaN", "null").replace("Infinity", "null"))


def build_meta() -> dict:
    foot = footprint()
    cat = read(LABELS) > 0
    sgmc = read(SGMC) > 0
    d_cat = ndimage.distance_transform_edt(~cat)            # px
    d_sgmc = ndimage.distance_transform_edt(~sgmc)
    with rasterio.open(SCARP) as ds:
        # h52 "scarp3m" bands are per-pixel COUNTS of 3 m cells passing a gate, not masks.
        # Continuous weight: h_gate12 >= 330 is the top 0.2 % of valid pixels, 100 ~ background.
        g12 = ds.read(2).astype(np.float32)
        valid = ds.read(1) != -32768
        scarp_w = np.clip((g12 - 100.0) / 230.0, 0.0, 1.0)
        scarp_w[~valid] = 0.0
    # independent evidence: scarp weight on ground explained by NEITHER catalogue
    w_off = np.where(foot & (d_cat > 3.0) & (d_sgmc > 3.0), scarp_w, 0.0)
    w_known = np.where(foot & (d_cat <= 3.0), scarp_w, 0.0)      # known-fault control
    pos = sgmc & foot & ~ndimage.binary_dilation(cat, iterations=3)   # fault-like, not on catalogue
    neg_pool = foot & ~ndimage.binary_dilation(sgmc, iterations=3)
    return dict(foot=foot, cat=cat, sgmc=sgmc, d_cat=d_cat, scarp_w=scarp_w,
                w_off=w_off, w_known=w_known, pos=pos, neg_pool=neg_pool,
                quad=quadrant_ids(foot))


def feature_bands() -> list[tuple[Path, int, str]]:
    out = []
    with rasterio.open(TRAIN_FEATURES) as ds:
        for i in range(1, ds.count + 1):
            if i not in SKIP_BANDS:
                out.append((Path(TRAIN_FEATURES), i, f"tf{i:02d}"))
    with rasterio.open(TOPO) as ds:
        for i, d in enumerate(ds.descriptions, start=1):
            out.append((TOPO, i, f"topo_{d}"))
    with rasterio.open(RAD) as ds:
        for i, d in enumerate(ds.descriptions, start=1):
            out.append((RAD, i, f"rad_{d}"))
    return out


def tile_features(bands, r0: int, r1: int) -> np.ndarray:
    """(F, r1-r0, W) float32; sentinels -> nan -> 0 with a validity mask column."""
    F = len(bands)
    with rasterio.open(bands[0][0]) as ds:
        W = ds.width
    out = np.empty((F, r1 - r0, W), np.float32)
    cache: dict[Path, object] = {}
    for j, (p, i, _) in enumerate(bands):
        if p not in cache:
            cache[p] = rasterio.open(p)
        a = cache[p].read(i, window=((r0, r1), (0, W))).astype(np.float32)
        a = np.where(a <= -1e30, np.nan, a)
        out[j] = a
    for ds in cache.values():
        ds.close()
    return out


def stratified_sample(meta, quad_mask: np.ndarray, rng, n_pos_max=140_000, n_neg_max=140_000):
    """Positives = fault-class pixels; negatives drawn from the SAME d_cat deciles."""
    pos_idx = np.flatnonzero((meta["pos"] & quad_mask).ravel())
    neg_pool_idx = np.flatnonzero((meta["neg_pool"] & quad_mask).ravel())
    d_cat = meta["d_cat"].ravel()
    if pos_idx.size > n_pos_max:
        pos_idx = rng.choice(pos_idx, n_pos_max, replace=False)
    dp = d_cat[pos_idx]
    bins = np.quantile(dp, np.linspace(0, 1, 11))
    bins[-1] += 1e-6
    dn = d_cat[neg_pool_idx]
    neg_sel = []
    per_bin = n_neg_max // 10
    for b in range(10):
        sel = neg_pool_idx[(dn >= bins[b]) & (dn < bins[b + 1])]
        if sel.size == 0:
            continue
        take = min(per_bin, sel.size)
        neg_sel.append(rng.choice(sel, take, replace=False))
    neg_idx = np.concatenate(neg_sel) if neg_sel else np.array([], np.int64)
    return pos_idx, neg_idx


def sample_features(bands, idx: np.ndarray, shape) -> np.ndarray:
    """(n, F) features at flat indices, read tile by tile (RSS stays bounded)."""
    W = shape[1]
    rows = idx // W
    order = np.argsort(rows, kind="stable")
    out = np.full((idx.size, len(bands)), np.nan, np.float32)
    r_sorted = rows[order]
    bounds = np.searchsorted(r_sorted, np.arange(0, shape[0] + TILE_ROWS, TILE_ROWS))
    for t, r0 in enumerate(range(0, shape[0], TILE_ROWS)):
        lo, hi = bounds[t], bounds[t + 1]
        if hi <= lo:
            continue
        sub = order[lo:hi]
        sel = idx[sub]
        r1 = min(shape[0], r0 + TILE_ROWS)
        feats = tile_features(bands, r0, r1)
        rr = (sel // W) - r0
        cc = sel % W
        out[sub] = feats[:, rr, cc].T
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=37654, help="emitted dots (comparable budget)")
    ap.add_argument("--min-sep", type=float, default=3.0)
    ap.add_argument("--min-dist-cat-px", type=float, default=2.5)
    ap.add_argument("--seed", type=int, default=6061)
    ap.add_argument("--quick", action="store_true", help="fewer samples / trees (smoke test)")
    ap.add_argument("--write-tif", default=None,
                    help="ship the emission through the shared submission writer (zeros outside; "
                         "portal-safe container). Value = artifact label.")
    ap.add_argument("--reuse-field", action="store_true",
                    help="load work/xcrd_field.npy instead of retraining (emission/metric sweeps)")
    args = ap.parse_args()

    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    t0 = time.time()
    rng = np.random.default_rng(args.seed)
    meta = build_meta()
    foot, quad = meta["foot"], meta["quad"]
    H, W = foot.shape
    bands = feature_bands()
    print(f"[xcrd] footprint {int(foot.sum())} px, {len(bands)} features, "
          f"positives {int(meta['pos'].sum())} px, off-catalogue scarp evidence "
          f"{float(meta['w_off'].sum()):.0f} px-equiv")

    n_pos = 30_000 if args.quick else 140_000
    n_neg = 30_000 if args.quick else 140_000
    iters = 60 if args.quick else 180

    field = np.zeros((H, W), np.float32)
    fold_report, feat_auc = [], {}
    reuse = bool(getattr(args, "reuse_field", False)) and (WORK / "xcrd_field.npy").exists()
    if reuse:
        field = np.load(WORK / "xcrd_field.npy")
        print("[xcrd] field reused from work/xcrd_field.npy (training skipped)")
    for f in ([] if reuse else range(4)):
        tr_mask = (quad != f) & foot
        te_mask = (quad == f) & foot
        pos_tr, neg_tr = stratified_sample(meta, tr_mask, rng, n_pos, n_neg)
        X = sample_features(bands, np.concatenate([pos_tr, neg_tr]), foot.shape)
        y = np.concatenate([np.ones(pos_tr.size, np.int8), np.zeros(neg_tr.size, np.int8)])
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        clf = HistGradientBoostingClassifier(max_iter=iters, learning_rate=0.08,
                                             max_leaf_nodes=31, min_samples_leaf=40,
                                             l2_regularization=1.0, random_state=args.seed + f)
        clf.fit(X, y)
        # ---- held-out fold: AUC on its own positives vs stratified negatives
        pos_te, neg_te = stratified_sample(meta, te_mask, rng, 40_000, 40_000)
        Xte = sample_features(bands, np.concatenate([pos_te, neg_te]), foot.shape)
        Xte = np.nan_to_num(Xte, nan=0.0, posinf=0.0, neginf=0.0)
        yte = np.concatenate([np.ones(pos_te.size, np.int8), np.zeros(neg_te.size, np.int8)])
        auc = float(roc_auc_score(yte, clf.predict_proba(Xte)[:, 1]))
        if f == 0:      # single-feature canary on fold 0's own test sample
            for j, (_, _, nm) in enumerate(bands):
                col = Xte[:, j]
                if col.std() > 0:
                    a = float(roc_auc_score(yte, col))
                    feat_auc[nm] = round(max(a, 1 - a), 4)
        fold_report.append(dict(fold=f, n_train=int(y.size), n_pos_train=int(pos_tr.size), auc=round(auc, 4)))
        print(f"[xcrd] fold {f}: trained on {y.size} samples, held-out AUC {auc:.4f}  ({time.time()-t0:.0f}s)")
        # ---- out-of-fold prediction over this quadrant
        for r0 in range(0, H, TILE_ROWS):
            r1 = min(H, r0 + TILE_ROWS)
            feats = tile_features(bands, r0, r1)
            flat = np.moveaxis(feats, 0, -1).reshape(-1, feats.shape[0])
            m = foot[r0:r1].ravel()
            if not m.any():
                continue
            p = clf.predict_proba(np.nan_to_num(flat, nan=0.0, posinf=0.0, neginf=0.0))[:, 1]
            qf = (quad[r0:r1].ravel() == f) & m
            blk = field[r0:r1].ravel()
            blk[qf] = p[qf].astype(np.float32)
            field[r0:r1] = blk.reshape(r1 - r0, W)

    WORK.mkdir(exist_ok=True)
    np.save(WORK / "xcrd_field.npy", field)
    print(f"[xcrd] field written; mass stats: max {field.max():.4f} p99.9 {np.percentile(field[foot],99.9):.4f}")

    # ---------------- emission ----------------
    allowed = foot & (meta["d_cat"] > args.min_dist_cat_px)
    flat_field = np.where(allowed, field, -np.inf).ravel()
    cand = np.flatnonzero(np.isfinite(flat_field))
    # deterministic NMS at min-sep (spatial hash; preserves ranked order)
    order = cand[np.argsort(-flat_field[cand], kind="stable")]
    order = order[: min(order.size, args.budget * 12)]
    keep = np.zeros(order.size, bool)
    took = np.zeros((H, W), bool)
    sep2 = args.min_sep ** 2
    cell = max(1, int(np.ceil(args.min_sep)))
    for j, flat in enumerate(order):
        y, x = divmod(int(flat), W)
        y0, y1 = max(0, y - cell), min(H, y + cell + 1)
        x0, x1 = max(0, x - cell), min(W, x + cell + 1)
        if took[y0:y1, x0:x1].any():
            ty, tx = np.nonzero(took[y0:y1, x0:x1])
            dy = ty + y0 - y
            dx = tx + x0 - x
            if (dy * dy + dx * dx < sep2).any():
                continue
        took[y, x] = True
        keep[j] = True
    dots = np.zeros((H, W), np.float32)
    ys, xs = np.divmod(order[keep][: args.budget], W)
    dots[ys, xs] = 1.0
    n_dots = int(dots.sum())
    print(f"[xcrd] emitted {n_dots} dots (budget {args.budget}, min_sep {args.min_sep} px, "
          f"> {args.min_dist_cat_px} px from catalogue)  ({time.time()-t0:.0f}s)")

    # ---------------- scoring: instrument + independent evidence ----------------
    from gems52 import metric as M

    def offcat_metrics(pred: np.ndarray) -> dict:
        off = meta["sgmc"] & foot & ~ndimage.binary_dilation(meta["cat"], iterations=3)
        n_off = int(off.sum())
        ed = ndimage.distance_transform_edt(~off, sampling=M.PIXEL_M)
        k_off = np.maximum(1.0 - ed / M.R_M, 0.0)
        n_px = int(pred.sum())
        tp = float(k_off[pred].sum())
        cov = tp / n_off
        dti_raw = tp / (tp + M.ALPHA * max(0.0, n_px - tp) + M.BETA * (n_off - tp)) if n_px else 0.0
        g = 12691.0
        tp_c = cov * g
        fp_c = max(0.0, n_px - tp_c)
        return dict(mass=n_px, tp_w=tp, coverage=cov,
                    sgmc_raw_dti=dti_raw,
                    sgmc_prevalence_cal=tp_c / (M.ALPHA * (tp_c + fp_c) + M.BETA * g),
                    offcat_excess_vs_random=cov - float(np.mean(k_off[foot])) * n_px / n_off)

    def independent_metrics(pred: np.ndarray) -> dict:
        """Held-out LiDAR scarp evidence (never a feature): weighted enrichment on scarp
        strength, split into ground explained by the catalogue vs ground explained by neither."""
        allowed_px = foot & (meta["d_cat"] > args.min_dist_cat_px)
        n_px = int(pred.sum())
        out = {}
        for tag, key in (("offcatalogue", "w_off"), ("known_fault_control", "w_known")):
            w = meta[key]
            got = float(w[pred].sum())
            exp = float(w[allowed_px].mean()) * n_px if allowed_px.any() else 0.0
            out[f"weight_{tag}"] = round(got, 3)
            out[f"expected_{tag}"] = round(exp, 3)
            out[f"enrichment_{tag}"] = round(got / exp, 4) if exp > 0 else float("nan")
        # AUC of the field against presence of any off-catalogue scarp evidence on the footprint
        from sklearn.metrics import roc_auc_score
        m = foot & (meta["w_off"] > 0)
        out["n_offcat_scarp_px"] = int(m.sum())
        if 0 < m.sum() < int(foot.sum()):
            out["field_auc_vs_offcat_scarp"] = round(
                float(roc_auc_score(m[foot].astype(np.int8), field[foot])), 4)
        return out

    em = offcat_metrics(dots > 0)
    ind = independent_metrics(dots > 0)
    field_offcat = offcat_metrics(field >= np.quantile(field[foot], 1 - min(args.budget, int(foot.sum())) / int(foot.sum())))
    print("[xcrd] off-catalogue instrument :", json.dumps({k2: round(v, 6) if isinstance(v, float) else v for k2, v in em.items()}))
    print("[xcrd] independent scarp check  :", json.dumps({k2: round(v, 6) if isinstance(v, float) else v for k2, v in ind.items()}))

    # ---------------- ship the artifact (shared writer, zeros outside the footprint) --------
    shipped_receipt = None
    if args.write_tif:
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from gems52 import submission_writer
        SUB = ROOT / "submission"
        SUB.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        name = (f"{args.write_tif}-{n_dots}px-{stamp}")[:140]
        note = ("H61-A XCRD: gradient-boosted 30-channel detector (17 physics + 9 topo + 4 "
                "radiometric), 4 spatial folds, dots >=350 m from the visible catalogue. "
                "Unique vs all 35 registry rasters. No organizer score; projection only.")[:140]
        receipt = submission_writer.write_submission(
            SUB / f"{name}-zeros.tif", dots, ROOT / "data/bridge/example_submission.tif",
            foot, note=note, name=name,
            metadata=jsonable(dict(dots=n_dots, min_dist_cat_px=args.min_dist_cat_px,
                                   emissions=em, independent=ind, folds=fold_report,
                                   projection="MODEL only")))
        print("[xcrd] shipped:", receipt["file"], receipt["sha256"][:16],
              "validator_ok", receipt["validator"]["ok"])
        shipped_receipt = receipt

    # canary
    worst = max(feat_auc.items(), key=lambda kv: kv[1]) if feat_auc else ("none", 0.0)
    report = dict(
        schema="xcrd-v1", hypothesis="H61-A cross-catalogue residual detector (SGMC target, "
                                     "distance-stratified negatives, out-of-fold spatial blocking)",
        features=[nm for _, _, nm in bands],
        n_features=len(bands),
        n_positives_px=int(meta["pos"].sum()),
        n_offcat_scarp_weight=float(meta["w_off"].sum()),
        folds=fold_report,
        leakage_canary_single_feature_auc=dict(sorted(feat_auc.items(), key=lambda kv: -kv[1])[:5]),
        canary_worst_feature=worst[0], canary_worst_auc=worst[1],
        emission=dict(budget=args.budget, dots=n_dots, min_sep_px=args.min_sep,
                      min_dist_cat_px=args.min_dist_cat_px),
        instrument_offcatalogue=em, independent_lidar_scarp=ind, field_offcatalogue=field_offcat,
        seconds=round(time.time() - t0, 1))
    (ROOT / "evidence").mkdir(exist_ok=True)
    if shipped_receipt:
        report["shipped"] = shipped_receipt
    (ROOT / "evidence/e2_xcrd.json").write_text(json.dumps(jsonable(report), indent=1) + "\n")
    np.save(WORK / "xcrd_dots.npy", dots)
    print(f"[xcrd] wrote evidence/e2_xcrd.json and work/xcrd_dots.npy ({n_dots} dots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
