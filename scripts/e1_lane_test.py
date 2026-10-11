"""E1 - the lane's preregistered first test (brief, verbatim):

    "First test: do channels crossing withheld segments show larger steepness
     steps than random lines of the same orientation?  If not, stop."

Design
------
* Features are LABEL-FREE (det_elev -> fill -> D8 -> acc -> ksn -> DoG anomaly).
* Whole catalogue segments (>= 40 px = 4 km) are partitioned by strike octant;
  a seeded 25% of the segments in every octant are WITHHELD (the surrogate
  hidden set; the same population the organisers withheld from the catalogue).
* For each withheld segment the lane statistic is the mean top-decile
  steepness anomaly on channel cells inside the segment's own 3 px corridor.
* Nulls, 30 per segment: identical straight line - same midpoint, same strike,
  same length - displaced laterally by a uniform random offset in +/- 2 km
  (N1, placement null); and, separately, the same line with the strike rotated
  by a uniform random angle in [30, 150) degrees (N2, orientation null).
  N2 keeps the line near the fault corridor but destroys the alignment, so
  AUC(N2) tests the orientation specificity the brief asks about.
* AUC = P(real > null) with ties at 0.5, pooled over segments; the signed-rank
  test is paired per segment against the null median.

Gate (preregistered before the run): proceed to E2/E3 iff
  AUC(N1) >= 0.60 and Wilcoxon p(N1) <= 0.05 and AUC(N2) >= AUC(N1) - 0.05.
Stop condition is equally preregistered: if AUC(N1) < 0.55 the lane is a
negative result and no submission raster is promoted from it.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import lane_channels as LC  # noqa: E402

DATA = ROOT / "data"
WORK = ROOT / "data" / "work"
EVID = ROOT / "evidence"
WORK.mkdir(parents=True, exist_ok=True)
EVID.mkdir(parents=True, exist_ok=True)

SEED = 20261011
WITHHOLD_FRAC = 0.25
N_NULL = 30
LAT_OFFSET_PX = 20.0          # +/- 2 km lateral displacement for N1
CORRIDOR_PX = 3               # 300 m corridor around a segment


def load_inputs():
    import rasterio
    feats = DATA / "training_features.tif"
    if not feats.exists():
        raise SystemExit(
            "data/training_features.tif missing - run `python scripts/fetch_bridge.py` "
            "to reassemble the hash-pinned bridge (see README).")
    with rasterio.open(feats) as ds:
        det = ds.read(12).astype(np.float64)
        slope_band = ds.read(19).astype(np.float64)
    lab_path = DATA / "labels.tif"
    if not lab_path.exists():
        lab_path = DATA / "bridge" / "existing_faults.tif"   # same bytes (sha 7ba308cc...)
    with rasterio.open(lab_path) as ds:
        lab = ds.read(1)
    valid = lab != -1
    det = np.where(valid, det, 0.0)
    return det, slope_band, (lab > 0) & valid, valid


def get_channel_stack(det, valid, cache=True):
    f = WORK / "channel_stack.npz"
    if cache and f.exists():
        z = np.load(f)
        if z["valid_hash"] == hash(valid.tobytes()) % (1 << 62):
            return {k: z[k] for k in z.files if k != "valid_hash"}
    t0 = time.time()
    cs = LC.channel_stack(det, valid)
    dt = time.time() - t0
    if cache:
        arr = {k: v for k, v in cs.items() if k != "hydro"}
        np.savez_compressed(f, valid_hash=hash(valid.tobytes()) % (1 << 62), dt=dt, **arr)
    print(f"channel stack built in {dt:.1f}s")
    return cs


def corridor_of(seg_mask: np.ndarray, px: int) -> np.ndarray:
    return ndimage.binary_dilation(seg_mask, iterations=px)


def corridor_stat_bbox(anomaly: np.ndarray, channels: np.ndarray,
                       line_mask: np.ndarray, px: int = 3) -> float:
    """Top-decile channel anomaly inside the corridor, cropped to a bbox (fast)."""
    ys, xs = np.nonzero(line_mask)
    if ys.size == 0:
        return 0.0
    r0, r1 = max(ys.min() - px - 1, 0), min(ys.max() + px + 2, line_mask.shape[0])
    c0, c1 = max(xs.min() - px - 1, 0), min(xs.max() + px + 2, line_mask.shape[1])
    sub = line_mask[r0:r1, c0:c1]
    cor = ndimage.binary_dilation(sub, iterations=px)
    ch = channels[r0:r1, c0:c1]
    an = anomaly[r0:r1, c0:c1]
    v = an[cor & ch]
    if v.size == 0:
        return 0.0
    v = np.sort(v)[::-1]
    top = max(1, int(round(0.1 * v.size)))
    return float(v[:top].mean())


def main():
    t0 = time.time()
    det, slope_band, cat, valid = load_inputs()
    print(f"footprint cells: {int(valid.sum())}, catalogue px: {int(cat.sum())}")

    cs = get_channel_stack(det, valid)
    channels = cs["channels"]
    anomaly = cs["anomaly"]
    print(f"channel cells (>= {LC.ACC_MIN_CELLS} cells = {LC.ACC_MIN_CELLS/100:.0f} km^2): {int(channels.sum())}")

    segs_info = LC.segment_catalogue(cat, valid, min_px=40)
    segs = segs_info["segments"]
    print(f"catalogue segments >= 40 px: {len(segs)}")

    # stratified withhold by strike octant, seeded
    rng = np.random.default_rng(SEED)
    by_oct = {}
    for i, s in enumerate(segs):
        by_oct.setdefault(int(s["strike_deg"] // 22.5), []).append(i)
    held_idx = set()
    for octant, idxs in sorted(by_oct.items()):
        idxs = sorted(idxs)
        rng2 = np.random.default_rng(SEED + 977 * octant)
        k = max(1, int(round(WITHHOLD_FRAC * len(idxs))))
        held_idx.update(rng2.choice(idxs, size=k, replace=False).tolist())
    print(f"withheld segments: {len(held_idx)} of {len(segs)} "
          f"({sum(segs[i]['size'] for i in held_idx)} px)")

    comp = segs_info["comp"]
    rows = []
    for i in held_idx:
        s = segs[i]
        seg_mask = comp == s["id"]
        real = LC.corridor_stat(anomaly, channels, corridor_of(seg_mask, CORRIDOR_PX))
        n1 = LC.orient_line_masks(det.shape, s["cy"], s["cx"], s["strike_deg"],
                                  s["length_px"], valid, n=N_NULL, rng=rng,
                                  lateral_offset_px=LAT_OFFSET_PX)
        n2 = LC.orient_line_masks(det.shape, s["cy"], s["cx"], s["strike_deg"],
                                  s["length_px"], valid, n=N_NULL, rng=rng,
                                  rot_deg=float(rng.uniform(30, 150)))
        s1 = [LC.corridor_stat(anomaly, channels, corridor_of(m, CORRIDOR_PX)) for m in n1]
        s2 = [LC.corridor_stat(anomaly, channels, corridor_of(m, CORRIDOR_PX)) for m in n2]
        rows.append(dict(idx=i, size=s["size"], strike=s["strike_deg"], real=real,
                         n1=s1, n2=s2))

    def auc(real_vals, null_matrix):
        wins = ties = tot = 0
        for r, nulls in zip(real_vals, null_matrix):
            for nv in nulls:
                tot += 1
                if r > nv:
                    wins += 1
                elif r == nv:
                    ties += 1
        return (wins + 0.5 * ties) / max(tot, 1)

    real_v = [r["real"] for r in rows]
    n1_med = [float(np.median(r["n1"])) for r in rows]
    n2_med = [float(np.median(r["n2"])) for r in rows]
    auc1 = auc(real_v, [r["n1"] for r in rows])
    auc2 = auc(real_v, [r["n2"] for r in rows])
    try:
        p1 = float(wilcoxon(real_v, n1_med, zero_method="zsplit").pvalue)
        p2 = float(wilcoxon(real_v, n2_med, zero_method="zsplit").pvalue)
    except ValueError:
        p1 = p2 = 1.0

    gate = dict(auc_n1=auc1, auc_n2=auc2, p_n1=p1, p_n2=p2)
    verdict = "PROCEED" if (auc1 >= 0.60 and p1 <= 0.05 and auc2 >= auc1 - 0.05) else \
              ("NEGATIVE-STOP" if auc1 < 0.55 else "WEAK-CAUTION")
    out = dict(
        experiment="E1-knickpoint-enrichment",
        preregistration=__doc__,
        seed=SEED, withhold_frac=WITHHOLD_FRAC, n_null=N_NULL,
        n_segments_tested=len(rows),
        withheld_px=int(sum(segs[i]["size"] for i in held_idx)),
        channel_cells=int(channels.sum()),
        knick_floor_percentile=95,
        auc_placement_null=auc1, auc_orientation_null=auc2,
        wilcoxon_p_n1=p1, wilcoxon_p_n2=p2,
        median_real=float(np.median(real_v)),
        median_null_n1=float(np.median(n1_med)),
        median_null_n2=float(np.median(n2_med)),
        gate=gate, verdict=verdict,
        rows=[{k: v for k, v in r.items() if k not in ("n1", "n2")} |
              {"n1_median": float(np.median(r["n1"])), "n2_median": float(np.median(r["n2"]))}
              for r in rows],
        runtime_s=round(time.time() - t0, 1),
    )
    (EVID / "e1_lane_test.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("auc_placement_null", "auc_orientation_null", "wilcoxon_p_n1",
                       "wilcoxon_p_n2", "verdict")}, indent=1))
    return 0 if verdict != "NEGATIVE-STOP" else 1


if __name__ == "__main__":
    sys.exit(main())
