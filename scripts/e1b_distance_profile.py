"""E1b - distance-profile diagnostic for the E1 negative (confound mapping).

E1 found AUC(N1) = 0.224: the trace-line corridor carries LOWER channel
steepness anomaly than lines offset by up to +/- 2 km.  Before the lane is
stopped, this diagnostic maps the anomaly against distance from the withheld
trace (0 .. 3 km, 200 m bands, channel cells only) for real traces and for the
same two null families as E1.  Kirby & Whipple (2012) place the knickpoint
response on the DRAINAGES CROSSING the trace - typically in the upstream,
incising block - so enrichment, if it exists, need not sit on the trace line.

This is measurement construction, not a second gate: E2/E3 may use a band only
if that band shows enrichment against BOTH nulls, and the choice is recorded
here, in evidence, with the full profile.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import lane_channels as LC  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from e1_lane_test import load_inputs, get_channel_stack  # noqa: E402

EVID = ROOT / "evidence"
SEED = 20261011
N_NULL = 30
LAT_OFFSET_PX = 20.0
BANDS = [(d, d + 2) for d in range(0, 31, 2)]      # 0-2, 2-4, ... 30-32 px


def band_stats(an, ch, dist, band):
    """Top-decile channel anomaly inside one distance band; all arrays pre-cropped."""
    m = (dist >= band[0]) & (dist < band[1])
    v = an[m & ch]
    if v.size == 0:
        return 0.0
    v = np.sort(v)[::-1]
    top = max(1, int(round(0.1 * v.size)))
    return float(v[:top].mean())


def main():
    det, slope_band, cat, valid = load_inputs()
    cs = get_channel_stack(det, valid)
    anomaly, channels = cs["anomaly"], cs["channels"]
    segs_info = LC.segment_catalogue(cat, valid, min_px=40)
    segs, comp = segs_info["segments"], segs_info["comp"]

    rng = np.random.default_rng(SEED)
    by_oct = {}
    for i, s in enumerate(segs):
        by_oct.setdefault(int(s["strike_deg"] // 22.5), []).append(i)
    held_idx = set()
    for octant, idxs in sorted(by_oct.items()):
        idxs = sorted(idxs)
        rng2 = np.random.default_rng(SEED + 977 * octant)
        k = max(1, int(round(0.25 * len(idxs))))
        held_idx.update(rng2.choice(idxs, size=k, replace=False).tolist())

    struct = np.ones((3, 3), dtype=bool)

    def bbox_of(mask, pad):
        ys, xs = np.nonzero(mask)
        return (max(ys.min() - pad, 0), min(ys.max() + pad + 1, mask.shape[0]),
                max(xs.min() - pad, 0), min(xs.max() + pad + 1, mask.shape[1]))

    real_prof = np.zeros(len(BANDS))
    n1_prof = np.zeros(len(BANDS))
    n2_prof = np.zeros(len(BANDS))
    n_segs = 0
    per_seg = []
    for i in sorted(held_idx):
        s = segs[i]
        seg_mask = comp == s["id"]
        r0, r1, c0, c1 = bbox_of(seg_mask, 40)
        dist_full = ndimage.distance_transform_edt(~ndimage.binary_dilation(seg_mask, iterations=1))
        an_b, ch_b = anomaly[r0:r1, c0:c1], channels[r0:r1, c0:c1]
        d_b = dist_full[r0:r1, c0:c1]
        rp = np.array([band_stats(an_b, ch_b, d_b, b) for b in BANDS])
        n1s = np.zeros(len(BANDS))
        n2s = np.zeros(len(BANDS))
        for k in range(N_NULL):
            m1 = LC.orient_line_masks(det.shape, s["cy"], s["cx"], s["strike_deg"],
                                      s["length_px"], valid, n=1, rng=rng,
                                      lateral_offset_px=float(rng.uniform(-LAT_OFFSET_PX, LAT_OFFSET_PX)))[0]
            m2 = LC.orient_line_masks(det.shape, s["cy"], s["cx"], s["strike_deg"],
                                      s["length_px"], valid, n=1, rng=rng,
                                      rot_deg=float(rng.uniform(30, 150)))[0]
            for tag, m, acc in (("n1", m1, n1s), ("n2", m2, n2s)):
                q0, q1, q2, q3 = bbox_of(m, 40)
                d2 = ndimage.distance_transform_edt(~m[q0:q1, q2:q3])
                an2, ch2 = anomaly[q0:q1, q2:q3], channels[q0:q1, q2:q3]
                vals = [band_stats(an2, ch2, d2, b) for b in BANDS]
                acc += np.array(vals)
        n1s /= N_NULL
        n2s /= N_NULL
        real_prof += rp
        n1_prof += n1s
        n2_prof += n2s
        n_segs += 1
        per_seg.append(dict(idx=i, size=s["size"], strike=round(s["strike_deg"], 1),
                            real=rp.tolist(), n1=n1s.tolist(), n2=n2s.tolist()))

    real_prof /= n_segs
    n1_prof /= n_segs
    n2_prof /= n_segs
    band_mids = [d + 1 for d, _ in BANDS]
    out = dict(
        experiment="E1b-distance-profile",
        note="post-E1 diagnostic; anomaly profile vs distance from withheld trace, "
             "channel cells, top-decile mean; 200 m bands; nulls identical to E1",
        seed=SEED, n_segments=n_segs,
        band_mid_px=band_mids,
        band_mid_km=[round(b * 0.1, 1) for b in band_mids],
        real_profile=real_prof.round(4).tolist(),
        null_placement_profile=n1_prof.round(4).tolist(),
        null_orientation_profile=n2_prof.round(4).tolist(),
        per_segment=per_seg,
    )
    (EVID / "e1b_distance_profile.json").write_text(json.dumps(out, indent=2) + "\n")
    print("band_km real null_N1 null_N2")
    for k, b in enumerate(band_mids):
        print(f"{b*0.1:5.1f} {real_prof[k]:7.3f} {n1_prof[k]:7.3f} {n2_prof[k]:7.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
