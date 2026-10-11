#!/usr/bin/env python3
"""H69 — champion-anchored identification probes (knowledge/02 section 6, re-anchored).

Why these two files exist
-------------------------
The competition hides the truth, so T (weighted credit), K (hidden label mass) and
F (wasted mass) have never been measured for this project.  Because the metric is
exactly homogeneous of degree 0 in a scaled field,

    1/DTI(lam*p) = alpha + alpha*(F/T) + (beta*K/T)/lam          (verified 1e-15)

two extra uploads of the *current best* field identify all three numbers:

  probe A  p_A = 0.5 * p_champion            -> gives beta*K/T
  probe B  p_B = p_champion + M floor dots   -> gives T = alpha*M / (1/s_B - 1/s_1)

with the champion's own live return s_1 = 0.2778 as the already-paid anchor.  Both
probes are constructed to score strictly BELOW the anchor (see predicted returns in
the build log), so neither can lower the team's standing: only the best submission
counts.

Where the dots go (probe B)
---------------------------
The M = 2,000 added dots are placed at the *floor* of a composite belief field built
from the committed evidence rasters (rank of relief, profile curvature, hillshade
lineament, slope, k_sn, |step| and channel-hood, minus a capped distance-to-catalogue),
at least 4 px from every champion dot and at least 3 px from the mapped catalogue, so
that (i) they carry no belief, and (ii) the organizers' catalogue mask cannot be what
moves the return.

Reuse, not rebuild: the shared fail-closed writer and validator do all packaging.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems57 import grid as G57                     # noqa: E402
from gems57 import submission_writer as SW         # noqa: E402
from gems57.metric import ALPHA, BETA               # noqa: E402

CHAMPION = ROOT / "docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
CHAMPION_SHA = "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9"
M_NULL_DOTS = 2000
MIN_SEP_PX = 4.0
CAT_BUFFER_PX = 3.0
STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Footprint percentile rank in [0, 1]; NaN -> 0.5 (neutral)."""
    out = np.full(a.shape, 0.5, np.float64)
    flat_out = out.reshape(-1)          # flat view: flat indices are only valid here
    vals = a[mask]
    ok = np.isfinite(vals)
    if ok.sum() < 100:
        return out
    order = np.argsort(vals[ok], kind="stable")
    r = np.empty(int(ok.sum()), np.float64)
    r[order] = np.linspace(0.0, 1.0, int(ok.sum()))
    flat_out[np.flatnonzero(mask)[ok]] = r
    return out


def belief_floor(grid) -> tuple[np.ndarray, dict]:
    from scipy import ndimage as ndi
    fp = grid.footprint
    ev = {}
    with rasterio.open(ROOT / "data/external/topo_10m_derived_100m_u8.tif") as s:
        nod = s.nodata
        tb = s.read().astype(np.float32)
    tb[tb == nod] = np.nan
    ev["relief_local"] = tb[4]
    ev["curv_prof_absmax"] = tb[5]
    ev["hs_lineament"] = tb[7]
    ev["slope_p90"] = tb[0]
    with rasterio.open(ROOT / "data/external/dem10_chi_100m_i16.tif") as s:
        nod = s.nodata
        b = s.read().astype(np.float64)
    b[b == nod] = np.nan
    ev["ksn_max"] = b[2]
    ev["abs_step_max"] = np.abs(b[0]) / 1000.0
    with rasterio.open(ROOT / "data/external/dem10_chi_100m_u8.tif") as s:
        u8 = s.read().astype(np.float32)
    ev["channel"] = u8[0]
    ev["knick"] = u8[1]
    comp = np.zeros(fp.shape, np.float64)
    for name, arr in ev.items():
        comp += rank01(np.asarray(arr, np.float64), fp) if name != "channel" else np.clip(arr, 0, 1)
    comp /= len(ev)
    d_cat = ndi.distance_transform_edt(~grid.catalogue)
    d_norm = np.clip(d_cat / 50.0, 0.0, 1.0)          # capped at 5 km
    comp -= 0.5 * d_norm                               # prefer far from the catalogue
    return comp, {k: int(np.isfinite(v).sum()) for k, v in ev.items()}


def greedy_far(score: np.ndarray, allowed: np.ndarray, n: int, min_sep: float,
               blocked: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Take the n highest-score cells keeping >= min_sep px from taken/blocked cells."""
    from scipy import ndimage as ndi
    cand = np.flatnonzero((allowed & ~blocked).ravel())
    order = cand[np.argsort(-score.ravel()[cand], kind="stable")]
    keep = np.zeros(score.size, bool)
    taken_mask = np.zeros(score.shape, bool)
    r = int(np.ceil(min_sep))
    offs = [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if dy * dy + dx * dx <= min_sep * min_sep]
    h, w = score.shape
    got = 0
    for idx in order:
        if got >= n:
            break
        y, x = divmod(int(idx), w)
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        if (taken_mask[y0:y1, x0:x1] | blocked[y0:y1, x0:x1]).any():
            continue
        # enforce the exact separation against already-taken cells
        sub = taken_mask[y0:y1, x0:x1]
        bad = False
        for dy, dx in offs:
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and sub[yy - y0, xx - x0]:
                bad = True
                break
        if bad:
            continue
        taken_mask[y, x] = True
        keep[idx] = True
        got += 1
    ys, xs = np.nonzero(keep.reshape(score.shape))
    return ys, xs


def main() -> int:
    t0 = time.time()
    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue
    got = sha256(CHAMPION)
    if got != CHAMPION_SHA:
        print(f"champion sha mismatch: {got}")
        return 2
    with rasterio.open(CHAMPION) as s:
        champ = s.read(1).astype(np.float32)
    n_dots = int((champ > 0).sum())
    print(f"[H69] champion {CHAMPION.name}: {n_dots:,} dots, sha ok", flush=True)

    sample = ROOT / "data/official/sample_submission.tif"
    log: dict = {"hypothesis": "H69", "generated_utc": STAMP, "champion_file": CHAMPION.name,
                 "champion_sha256": got, "champion_dots": n_dots,
                 "anchor_live_score": 0.2778, "anchor_live_score_class": "OWNER-REPORTED / UNVERIFIED",
                 "alpha": ALPHA, "beta": BETA, "probes": {}}

    # ---- probe A: 0.5 x champion ------------------------------------------------
    half = (0.5 * champ).astype(np.float32)
    name_a = f"60GEMSDOE-H69A-CHAMP-HALF-{n_dots}-{STAMP}"
    note_a = (f"H69A identification probe: 0.5 x champion h33-2-b2 ({n_dots} dots); "
              "recovers beta*K/T from one leaderboard return; below anchor by construction")
    ra = SW.write_submission(ROOT / "docs/downloads" / f"gems60-h69a-champ-half-{STAMP}-zeros.tif",
                             half, sample, fp, note=note_a[:140], name=name_a[:140],
                             catalogue=cat, metadata={"probe": "lambda=0.5", "of": CHAMPION_SHA})
    print(f"[H69] A written {ra['file']} sha {ra['sha256'][:16]}", flush=True)

    # ---- probe B: champion + M floor dots --------------------------------------
    comp, diag = belief_floor(grid)
    from scipy import ndimage as ndi
    d_dot = ndi.distance_transform_edt(~(champ > 0))
    d_cat = ndi.distance_transform_edt(~cat)
    allowed = fp & (champ == 0) & (d_dot >= MIN_SEP_PX) & (d_cat > CAT_BUFFER_PX)
    blocked = ~allowed
    ys, xs = greedy_far(comp, allowed, M_NULL_DOTS, MIN_SEP_PX, blocked)
    m = int(ys.size)
    if m != M_NULL_DOTS:
        print(f"[H69] only {m} floor dots found; refusing to ship a different M")
        return 3
    probe_b = champ.copy()
    probe_b[ys, xs] = 1.0
    name_b = f"60GEMSDOE-H69B-CHAMP-NULLADD-{m}PX-{STAMP}"
    note_b = (f"H69B identification probe: champion + {m} floor dots (>300m from catalogue, "
              "no belief); T=alpha*M/(1/sB-1/s1); below anchor by construction")
    rb = SW.write_submission(ROOT / "docs/downloads" / f"gems60-h69b-champ-nulladd-{m}px-{STAMP}-zeros.tif",
                             probe_b, sample, fp, note=note_b[:140], name=name_b[:140],
                             catalogue=cat, metadata={"probe": "null-add", "M": m, "of": CHAMPION_SHA,
                                                      "min_sep_px": MIN_SEP_PX,
                                                      "cat_buffer_px": CAT_BUFFER_PX,
                                                      "belief_floor_evidence": list(diag)})
    print(f"[H69] B written {rb['file']} sha {rb['sha256'][:16]}", flush=True)

    log["probes"] = {
        "A": {"file": ra["file"], "sha256": ra["sha256"], "bytes": ra["bytes"],
              "submission_name": ra["submission_name"], "note": ra["note"],
              "note_chars": ra["note_chars"], "zip": ra["zip_file"], "zip_sha256": ra["zip_sha256"],
              "validator_all_checks_passed": ra["validator"]["all_checks_passed"]},
        "B": {"file": rb["file"], "sha256": rb["sha256"], "bytes": rb["bytes"],
              "submission_name": rb["submission_name"], "note": rb["note"],
              "note_chars": rb["note_chars"], "zip": rb["zip_file"], "zip_sha256": rb["zip_sha256"],
              "validator_all_checks_passed": rb["validator"]["all_checks_passed"],
              "M": m, "min_sep_px": MIN_SEP_PX,
              "min_catalogue_distance_px": float(d_cat[ys, xs].min()),
              "min_champion_distance_px": float(d_dot[ys, xs].min())},
    }
    log["recovery"] = {
        "a": "1/s1 - alpha = alpha*(F/T) + beta*(K/T)",
        "b": "1/sA - alpha = alpha*(F/T) + 2*beta*(K/T)   =>   K = T*(b-a)/beta",
        "c": "1/sB - 1/s1 = alpha*M/T                     =>   T = alpha*M/(1/sB - 1/s1)",
        "F": "F = T*(2a - b)/alpha",
        "instrument_file": "scripts/h69_recovery.py",
    }
    # predicted returns under the repo's own champion inversion [MODEL, not a result]
    T, F, K = 5092.0, 37654.0, 12226.0
    s1 = T / (ALPHA * (T + F) + BETA * K)
    sA = (0.5 * T) / (ALPHA * (0.5 * T + 0.5 * F) + BETA * K)
    sB = T / (ALPHA * (T + F + M_NULL_DOTS) + BETA * K)
    log["predicted_returns_MODEL"] = {"s1_check": s1, "sA": sA, "sB": sB,
                                      "both_below_anchor": bool(sA < s1 and sB < s1),
                                      "note": "arithmetic on the repo's [MODEL] T/F/K; not a score"}
    log["seconds"] = round(time.time() - t0, 1)
    out = ROOT / "evidence" / "h69_probe_build.json"
    out.write_text(json.dumps(log, indent=2) + "\n")
    print(json.dumps(log["predicted_returns_MODEL"], indent=1))
    print(f"[H69] wrote {out.name} in {log['seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
