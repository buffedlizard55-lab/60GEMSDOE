#!/usr/bin/env python3
"""H80 — convergent-cover emission with one new measured tectonic-geomorphology layer.

Preregistration: ``registry/preregistration-h80.json`` (committed before this file was run).

Three budgeted experiments, exactly as preregistered:

E1 (layer ablation, fixed 6,000-dot restricted emission)
    Compare the seven-layer H71 analogue field against the same field plus ONE of
    three newly measured in-lane layers:
      L-A ``facet``  triangular-facet planarity (aspect_coherence x slope_p90),
      L-B ``front``  mountain-front / piedmont junction (|grad(smooth(relief))|),
      L-C ``strike`` strike-coherent step corroboration across independent drainages.
    Decision rule is preregistered: largest complement credit-per-dot on the SGMC
    off-catalogue instrument with a paired block-bootstrap CI lower bound > 0 vs
    the mass-matched random control; the baseline wins if no layer beats it.

E2 (mass ladder + emission)
    Scale the adopted field over masses 6k/12k/24k/36k/48k, measure the marginal
    credit per dot on the instrument at each mass, adopt the largest mass whose CI
    lower bound >= 0.10 (~1.8x the champion bar 0.2 x 0.2778), and emit the union
    of the sha256-pinned live-scored champion with that complement.

E3 (validation suite)
    Leakage canary per layer, pooled registered holdout (gems57-pooled-hide-v2,
    22,641 withheld positives) with the no-harm test, and the uniqueness scan in
    three readings (literal, like-for-like, satisfiable) plus one-to-one matched
    overlap and Spearman.

Shared tools are reused, never forked: gems57.grid / holdout / evaluate_holdout /
metric / submission_writer / uniqueness, gems61.instruments / dataio, and the lane
builders already in scripts/build_h71_field.py (``read_stack``, ``rank01``,
``greedy_order``, ``paired_block_bootstrap``, ``uniqueness_scan``).  Two shared
helpers were repaired this round instead of being copied: the hard-coded
reference-arm name in ``paired_block_bootstrap`` (IR-H80-TOOL-01) and the
two-directory scan scope of ``uniqueness_scan`` (IR-H80-TOOL-02).

Declared approximations (labelled everywhere they appear, never as the cited
method):
  * the branch-signature test is a COARSE independence proxy - ``branch_sig`` is the
    cell 500 m downstream, so it separates catchments that split within about a
    kilometre and does not by itself separate two points on one trunk.  The
    flow-lateral requirement is what blocks the along-trunk case.
  * facets and fronts are read from the committed 9-band 10 m-derived 100 m
    reduction (uint8 quantised), not from a freshly resampled 1 m LiDAR product.

Governance: ``scripts/stop_guard.py`` is called, printed and stored verbatim in
the run card.  It is not used as a gate: this runner recomputes no stopped-lane
test, rebuilds no lane cache and calls no lane driver.  The H65-1 detector STOP
stays in force; the recorded operator directive is in the preregistration.

Usage:
    python scripts/run_h80.py
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import build_h71_field as BH                          # noqa: E402
import run_lane60 as RL                               # noqa: E402
from gems57 import evaluate_holdout as EH             # noqa: E402
from gems57 import grid as G57                        # noqa: E402
from gems57 import holdout as HO                      # noqa: E402
from gems57 import metric as M                        # noqa: E402
from gems57 import submission_writer as SW            # noqa: E402
from gems61 import instruments as I                   # noqa: E402

STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
EVID = ROOT / "evidence"
DL = ROOT / "docs" / "downloads"
EXT = ROOT / "data" / "external"
CHAMPION = DL / "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
CHAMPION_SHA = "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9"
CHAMPION_LIVE = 0.2778
BAR = M.ALPHA * CHAMPION_LIVE                       # 0.05556 marginal credit bar
ADOPT_BAR = 0.10                                    # preregistered ~1.8x safety factor
MASS_ABLATION = 6_000
MASS_LADDER = (6_000, 12_000, 24_000, 36_000, 48_000)
RESTRICTED_MASSES = (3_000, 6_000, 9_000, 12_000)
DOT_COUNT_AGGRESSIVE = 85_654        # measured union size of the broad 48,000-dot profile
MIN_SEP_PX = 2.8
BOOT_DRAWS, BOOT_SEED = 1000, 7001
RANDOM_SEEDS = (7001, 7002, 7003, 7004, 7005)
BLOCK_PX = 200
AZIMUTHS = tuple(np.arange(0.0, 180.0, 22.5))      # 8 undirected strike azimuths
CORRIDOR_PX = 10                                    # ~1 km each way along strike
FLOW_LATERAL = 0.707                                # cos 45 deg: offset must not be flow-aligned
RHO_LIMIT, OVERLAP_LIMIT = 0.90, 0.70
SCAN_DIRS = (ROOT / "downloads", ROOT / "submission", ROOT / "evidence")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def shifted(a: np.ndarray, dy: int, dx: int, fill):
    """Integer shift with constant fill (no wrap-around, unlike np.roll)."""
    out = np.full_like(a, fill)
    out[max(0, dy):a.shape[0] + min(0, dy), max(0, dx):a.shape[1] + min(0, dx)] = \
        a[max(0, -dy):a.shape[0] + min(0, -dy), max(0, -dx):a.shape[1] + min(0, -dx)]
    return out


def candidate_layers(topo, step, chan, fp, sig, zmean):
    """The three preregistered candidate layers, each as a percentile rank in [0,1]."""
    slope, relief, aspect = topo[0], topo[4], topo[6]
    out, diag = {}, {}

    # L-A triangular-facet planarity of the footwall (Bull & McFadden 1977; Wallace 1978).
    norm_slope = np.clip(slope / np.nanpercentile(slope[fp], 95.0), 0.0, 1.0)
    out["L-A_facet"] = BH.rank01(np.where(fp, aspect * norm_slope, np.nan), fp)

    # L-B mountain-front / piedmont junction: relief gradient at ~300 m (the H65-2 backlog item).
    filled = np.where(fp & np.isfinite(relief), relief, np.nan)
    med = float(np.nanmedian(filled))
    smooth = ndi.gaussian_filter(np.where(np.isfinite(filled), filled, med), 3.0)
    gy, gx = np.gradient(smooth)
    front = np.hypot(gy, gx)
    out["L-B_front"] = BH.rank01(np.where(fp, front, np.nan), fp)

    # L-C strike-coherent corroboration of steps across independent drainages.
    steppy = chan & np.isfinite(step) & (np.abs(step) >= np.log(2.0))
    zf = np.where(fp & np.isfinite(zmean), zmean, np.nan)
    zs = ndi.gaussian_filter(np.where(np.isfinite(zf), zf, float(np.nanmedian(zf))), 3.0)
    zy, zx = np.gradient(zs)
    norm = np.hypot(zy, zx) + 1e-9
    fy, fx = -zy / norm, -zx / norm                 # downslope unit vector (image coordinates)
    agree = np.zeros(fp.shape, np.float64)
    indep = np.zeros(fp.shape, np.float64)
    for az in AZIMUTHS:
        theta = np.deg2rad(az)
        dy = int(round(CORRIDOR_PX * np.sin(theta)))
        dx = int(round(CORRIDOR_PX * np.cos(theta)))
        near_step = shifted(steppy, dy, dx, False)
        near_sig = shifted(sig, dy, dx, -1)
        lateral = np.abs(oy_ox_projection(dy, dx, fy, fx)) <= FLOW_LATERAL
        agree += near_step
        # independence: a foreign 500 m branch signature, on a channel cell, reached laterally.
        indep += near_step & lateral & (sig >= 0) & (near_sig != sig)
    strike = agree * (indep >= 2.0)                 # >= 2 independent lateral corroborations
    out["L-C_strike"] = BH.rank01(np.where(fp, strike, np.nan), fp)
    diag.update(steppy_px=int(steppy.sum()), max_agree=float(agree.max()),
                struck_px=int((strike > 0).sum()), mean_indep_on_channel=float(indep[chan].mean()))
    return out, diag


def oy_ox_projection(dy: int, dx: int, fy: np.ndarray, fx: np.ndarray) -> np.ndarray:
    """Cosine of the angle between one fixed offset and the local downslope direction."""
    n = float(np.hypot(dy, dx)) or 1.0
    return (dy * fy + dx * fx) / n


def matched_overlap(mine: np.ndarray, theirs: np.ndarray, radius: float = 3.0) -> float:
    """One-to-one 3-px matching: each comparator dot can absorb at most one of mine."""
    if not mine.any() or not theirs.any():
        return 0.0
    my = np.column_stack(np.nonzero(mine)).astype(np.float64)
    th = np.column_stack(np.nonzero(theirs)).astype(np.float64)
    tree = cKDTree(th)
    dist, idx = tree.query(my, k=1, distance_upper_bound=radius)
    ok = np.isfinite(dist)
    if not ok.any():
        return 0.0
    used: set[int] = set()
    matched = 0
    for i in np.flatnonzero(ok)[np.argsort(dist[ok])]:
        j = int(idx[i])
        if j in used:
            continue
        used.add(j)
        matched += 1
    return matched / float(my.shape[0])


def main() -> int:
    t0 = time.time()
    log: list[str] = []

    def mark(msg: str) -> None:
        line = f"[H80] {msg} ({time.time() - t0:.1f}s)"
        print(line, flush=True)
        log.append(line)

    guard_report = None
    try:
        import stop_guard
        buf = io.StringIO()
        with redirect_stdout(buf):
            stopped = stop_guard.lane_is_stopped(ROOT, "H80 convergent-cover emission")
        guard_report = dict(called=True, verdict="STOPPED" if stopped else "CLEAR",
                            output=buf.getvalue().strip(),
                            interpretation=("printed for the record; not used as a gate because this "
                                            "runner is not a lane runner "
                                            "(registry/preregistration-h80.json)"))
    except Exception as exc:                                     # pragma: no cover - defensive
        guard_report = dict(called=False, error=str(exc))
    mark(f"stop_guard: {guard_report['verdict']} (disclosed, not gating)")

    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue
    champ_sha = sha256(CHAMPION)
    if champ_sha != CHAMPION_SHA:
        print(f"champion sha mismatch: {champ_sha} != {CHAMPION_SHA}")
        return 2
    with rasterio.open(CHAMPION) as src:
        champ = src.read(1) > 0
    mark(f"grid {grid.height}x{grid.width} footprint={int(fp.sum()):,} catalogue={int(cat.sum()):,} "
         f"champion={int(champ.sum()):,} dots sha={champ_sha[:16]}")

    # ---------------- off-catalogue instrument population -------------- #
    sgmc = BH.read_stack(EXT / "sgmc_faults_100m.tif", nodata=255.0)[0] > 0
    offcat = I.sgmc_off_catalogue(sgmc, cat, fp, buffer_px=3)
    if offcat.sum() == 0:
        mark("SGMC off-catalogue population is empty; aborting")
        return 2
    mark(f"instrument population: SGMC off-catalogue > 300 m = {int(offcat.sum()):,} px")

    # ---------------- shared field builders (no fork) ---------------- #
    score7, allowed_broad, diag_broad, champ_b, wash = BH.build_field(grid, "broad")
    _, allowed_restr, diag_restr, _, _ = BH.build_field(grid, "restricted")
    assert bool(np.array_equal(champ, champ_b))
    mark(f"pools: broad={int(allowed_broad.sum()):,} restricted={int(allowed_restr.sum()):,}")

    chi = BH.read_stack(EXT / "dem10_chi_100m_i16.tif")
    u8 = BH.read_stack(EXT / "dem10_chi_100m_u8.tif", nodata=None).astype(np.float32)
    topo = BH.read_stack(EXT / "topo_10m_derived_100m_u8.tif", nodata=0.0)
    sig_raw = BH.read_stack(EXT / "dem10_chi_100m_sig_i32.tif", nodata=None)[0]
    sig = np.where(np.isfinite(sig_raw), sig_raw, -1).astype(np.int64)
    zmean = chi[4]
    step_raw, ksn = np.abs(chi[0]) / 1000.0, chi[2]
    chan, knick = u8[0] > 0, u8[1] > 0
    valid_chan = chan & np.isfinite(step_raw) & np.isfinite(ksn)
    step = np.where(valid_chan, step_raw, np.nan)
    cand, cand_diag = candidate_layers(topo, step, chan, fp, sig, zmean)
    mark(f"candidate layers built: {cand_diag}")

    # ---------------- E1: layer ablation at a fixed 6,000-dot mass ---- #
    emissions = {}
    for label, extra in (("baseline7", None),
                         ("plus_L-A_facet", "L-A_facet"),
                         ("plus_L-B_front", "L-B_front"),
                         ("plus_L-C_strike", "L-C_strike")):
        score = score7.copy() if extra is None else (score7 * 7.0 + cand[extra]) / 8.0
        ys, xs = BH.greedy_order(score, allowed_restr, MASS_ABLATION, MIN_SEP_PX)
        if ys.size < MASS_ABLATION:
            mark(f"ablation {label}: restricted pool exhausted at {ys.size} dots")
        m = np.zeros(fp.shape, bool)
        m[ys, xs] = True
        emissions[label] = m
    arm = dict(emissions)
    arm["champion"] = champ
    for s in RANDOM_SEEDS:
        rng = np.random.default_rng(s)
        pool = np.flatnonzero(allowed_restr.ravel())
        pick = rng.choice(pool.size, size=MASS_ABLATION, replace=False)
        r = np.zeros(fp.shape, bool)
        r.ravel()[pool[pick]] = True
        arm[f"random_{s}"] = r
    boot = BH.paired_block_bootstrap({k: v.astype(np.float64) for k, v in arm.items()},
                                     offcat, draws=BOOT_DRAWS, seed=BOOT_SEED, ref="baseline7")
    rand_cpd = [boot[f"random_{s}"]["credit_per_dot"] for s in RANDOM_SEEDS]
    ablation = {}
    for label in emissions:
        closed = [boot[f"random_{s}"]["credit_per_dot"] for s in RANDOM_SEEDS]
        ablation[label] = dict(
            dots=int(emissions[label].sum()),
            credit_per_dot=boot[label]["credit_per_dot"],
            credit_per_dot_ci95=boot[label]["credit_per_dot_ci95"],
            random_credit_per_dot_mean=float(np.mean(closed)),
            candidate_minus_baseline7_dti=(None if label == "baseline7" else dict(
                delta_dti=-boot[f"paired_vs_{label}"]["delta_dti"],
                ci95=[-boot[f"paired_vs_{label}"]["ci95"][1], -boot[f"paired_vs_{label}"]["ci95"][0]],
                raw_tool_row_is_baseline7_minus_candidate=boot[f"paired_vs_{label}"])),
            candidate_minus_champion_dti=dict(
                delta_dti=-boot["paired_vs_champion"]["delta_dti"],
                ci95=[-boot["paired_vs_champion"]["ci95"][1], -boot["paired_vs_champion"]["ci95"][0]]),
            instrument_dti=I.global_dti(emissions[label].astype(np.float64), offcat, fp, cat)["dti"])
        mark(f"E1 {label:16s} dots={int(emissions[label].sum()):,} "
             f"credit/dot={ablation[label]['credit_per_dot']:.4f} "
             f"CI={[round(x, 4) for x in ablation[label]['credit_per_dot_ci95']]} "
             f"random={ablation[label]['random_credit_per_dot_mean']:.4f} "
             f"cand-minus-baseline7="
             f"{None if ablation[label]['candidate_minus_baseline7_dti'] is None else [round(x, 5) for x in [ablation[label]['candidate_minus_baseline7_dti']['delta_dti']] + list(ablation[label]['candidate_minus_baseline7_dti']['ci95'])]}")

    ranked = sorted(ablation, key=lambda k: -ablation[k]["credit_per_dot"])
    best = ranked[0]
    gain = ablation[best]["candidate_minus_baseline7_dti"] if best != "baseline7" else None
    layer_gain = bool(best != "baseline7"
                      and ablation[best]["credit_per_dot"] > ablation["baseline7"]["credit_per_dot"]
                      and gain is not None and gain["ci95"][0] > 0)
    adopted = best if layer_gain else "baseline7"
    adopted_extra = {"baseline7": None, "plus_L-A_facet": "L-A_facet",
                     "plus_L-B_front": "L-B_front", "plus_L-C_strike": "L-C_strike"}[adopted]
    score = score7.copy() if adopted_extra is None else (score7 * 7.0 + cand[adopted_extra]) / 8.0
    mark(f"E1 adopted field: {adopted} (significant layer gain: {'YES' if layer_gain else 'NO'}); "
         f"adoption follows the preregistered largest-credit rule regardless")

    # ---------------- E2: mass ladder on the adopted field ------------ #
    # Two pools are measured.  The BROAD pool is the aggressive profile: its top cells sit on
    # cells the near-space-filling comparators already cover, which the operator's literal
    # clause-1 check flags (IR-H80-PROFILE-01).  The RESTRICTED pool - identical to the H71-A
    # profile restriction, >= 3 px from r11_greedy_mp and r14_union_tips10_lat6 - is the profile
    # whose emitted dots satisfy that clause, so it is the profile the artifact is built from.
    ladder, ladder_restr, masks, masks_restr = {}, {}, {}, {}
    pool_broad = np.flatnonzero(allowed_broad.ravel())
    for mass in MASS_LADDER:
        ys, xs = BH.greedy_order(score, allowed_broad, mass, MIN_SEP_PX)
        m = np.zeros(fp.shape, bool)
        m[ys, xs] = True
        u = champ | m
        masks[mass] = (m, u)
        arm = {"complement": m, "union": u, "champion": champ}
        for s in RANDOM_SEEDS:
            rng = np.random.default_rng(s + 1000)
            pick = rng.choice(pool_broad.size, size=min(mass, pool_broad.size), replace=False)
            r = np.zeros(fp.shape, bool)
            r.ravel()[pool_broad[pick]] = True
            arm[f"random_{s}"] = r
        boot = BH.paired_block_bootstrap({k: v.astype(np.float64) for k, v in arm.items()},
                                         offcat, draws=BOOT_DRAWS, seed=BOOT_SEED, ref="union")
        boot_c = BH.paired_block_bootstrap({k: v.astype(np.float64) for k, v in arm.items()},
                                           offcat, draws=BOOT_DRAWS, seed=BOOT_SEED, ref="complement")
        rand_cpd = [boot[f"random_{s}"]["credit_per_dot"] for s in RANDOM_SEEDS]
        inst = {k: I.global_dti(v.astype(np.float64), offcat, fp, cat) for k, v in arm.items()}
        ladder[str(mass)] = dict(
            dots=int(m.sum()), union_dots=int(u.sum()),
            complement_dti=boot["complement"]["dti"],
            complement_credit_per_dot=boot["complement"]["credit_per_dot"],
            complement_credit_per_dot_ci95=boot["complement"]["credit_per_dot_ci95"],
            random_credit_per_dot_mean=float(np.mean(rand_cpd)),
            random_credit_per_dot_each={s: boot[f"random_{s}"]["credit_per_dot"] for s in RANDOM_SEEDS},
            complement_minus_random_7001_dti=boot_c["paired_vs_random_7001"],
            union_credit_per_dot=boot["union"]["credit_per_dot"],
            union_dti=boot["union"]["dti"],
            union_minus_champion_dti=boot["paired_vs_champion"],
            instrument=inst)
        mark(f"E2 mass={mass:,} credit/dot={ladder[str(mass)]['complement_credit_per_dot']:.4f} "
             f"CI={[round(x, 4) for x in ladder[str(mass)]['complement_credit_per_dot_ci95']]} "
             f"union-minus-champ dDTI={ladder[str(mass)]['union_minus_champion_dti']['delta_dti']:+.5f} "
             f"{[round(x, 5) for x in ladder[str(mass)]['union_minus_champion_dti']['ci95']]} "
             f"comp-minus-random={ladder[str(mass)]['complement_minus_random_7001_dti']['delta_dti']:+.5f}")

    for mass in RESTRICTED_MASSES:
        ys, xs = BH.greedy_order(score, allowed_restr, mass, MIN_SEP_PX)
        m = np.zeros(fp.shape, bool)
        m[ys, xs] = True
        u = champ | m
        masks_restr[mass] = (m, u)
        arm = {"complement": m, "union": u, "champion": champ}
        for s in RANDOM_SEEDS:
            rng = np.random.default_rng(s + 2000)
            pick = rng.choice(allowed_restr.sum(), size=min(int(m.sum()), int(allowed_restr.sum())),
                              replace=False)
            r = np.zeros(fp.shape, bool)
            r.ravel()[np.flatnonzero(allowed_restr.ravel())[pick]] = True
            arm[f"random_{s}"] = r
        boot = BH.paired_block_bootstrap({k: v.astype(np.float64) for k, v in arm.items()},
                                         offcat, draws=BOOT_DRAWS, seed=BOOT_SEED, ref="union")
        boot_c = BH.paired_block_bootstrap({k: v.astype(np.float64) for k, v in arm.items()},
                                           offcat, draws=BOOT_DRAWS, seed=BOOT_SEED,
                                           ref="complement")
        rand_cpd = [boot[f"random_{s}"]["credit_per_dot"] for s in RANDOM_SEEDS]
        ladder_restr[str(mass)] = dict(
            requested=mass, dots=int(m.sum()), capped=bool(m.sum() < mass), union_dots=int(u.sum()),
            complement_credit_per_dot=boot["complement"]["credit_per_dot"],
            complement_credit_per_dot_ci95=boot["complement"]["credit_per_dot_ci95"],
            random_credit_per_dot_mean=float(np.mean(rand_cpd)),
            complement_minus_random_7001_dti=boot_c["paired_vs_random_7001"],
            union_minus_champion_dti=boot["paired_vs_champion"],
            compression=dict(min_px=MIN_SEP_PX, pool_px=int(allowed_restr.sum())))
        mark(f"E2r mass={mass:,} achieved={int(m.sum()):,} credit/dot="
             f"{ladder_restr[str(mass)]['complement_credit_per_dot']:.4f} "
             f"CI={[round(x, 4) for x in ladder_restr[str(mass)]['complement_credit_per_dot_ci95']]} "
             f"union-minus-champ dDTI="
             f"{ladder_restr[str(mass)]['union_minus_champion_dti']['delta_dti']:+.5f}")

    eligible_r = [m for m in RESTRICTED_MASSES
                  if not ladder_restr[str(m)]["capped"]
                  and ladder_restr[str(m)]["complement_credit_per_dot_ci95"][0] >= ADOPT_BAR]
    final_mass = max(eligible_r) if eligible_r else None
    mark(f"E2r restricted ladder eligible {eligible_r} -> final restricted mass {final_mass}")
    eligible = [m for m in MASS_LADDER if ladder[str(m)]["complement_credit_per_dot_ci95"][0] >= ADOPT_BAR]
    aggressive_mass = max(eligible) if eligible else None
    mark(f"E2 aggressive (broad-pool) mass = {aggressive_mass}; NOT emitted (clause-1 duplicate)")
    if final_mass is None:
        (EVID / "h80_runcard.json").write_text(json.dumps(
            dict(run="H80", verdict="NEGATIVE",
                 reason=(f"no ladder mass reached the preregistered adopt bar {ADOPT_BAR} on the "
                         "off-catalogue instrument; no artifact emitted"),
                 ladder=ladder, ablation=ablation, guard_report=guard_report, log=log),
            indent=2, default=float) + "\n")
        mark("no artifact emitted: NEGATIVE")
        return 3

    comp, union = masks_restr[final_mass]
    mark(f"emitting union: champion {int(champ.sum()):,} + complement {int(comp.sum()):,} "
         f"= {int(union.sum()):,} dots (restricted profile)")

    # ---------------- E3a: leakage canary ---------------------------- #
    ctx = HO.build_holdout(grid)
    cells = [c for c in ctx.cells if c.mode == "all"]
    d_sgmc = ndi.distance_transform_edt(~sgmc)
    layer_maps = {"step": step, "ksn": ksn, "knick": knick.astype(np.float64),
                  "relief": topo[4], "curv": topo[5], "lineament": topo[7],
                  "sgmc_off_proximity": np.clip(1.0 - d_sgmc / 6.0, 0.0, 1.0), **cand}
    canary_rows = []
    for name, arr in layer_maps.items():
        aucs = []
        for cell in cells:
            bb = cell.bbox
            truth = ctx.hidden_by_cell[cell.key][bb] & cell.active
            if truth.sum() == 0:
                continue
            a = RL.auc(arr[bb], truth, cell.active)
            if np.isfinite(a):
                aucs.append(a)
        if aucs:
            m_auc = float(np.mean(aucs))
            canary_rows.append(dict(layer=name, mean_auc=round(m_auc, 4),
                                    max_abs_auc=round(max(m_auc, 1.0 - m_auc), 4), folds=len(aucs)))
    canary_flag = [r for r in canary_rows if r["max_abs_auc"] > 0.90]
    mark(f"E3a canary: {len(canary_rows)} layers, flagged={[r['layer'] for r in canary_flag]}")

    # ---------------- E3b: pooled registered holdout ----------------- #
    g1_ok = (ladder[str(final_mass)]["complement_credit_per_dot"]
             > ladder[str(final_mass)]["random_credit_per_dot_mean"]
             and ladder[str(final_mass)]["complement_minus_random_7001_dti"]["ci95"][0] > 0)
    h_arms = {"champion": champ, "complement": comp, "union": union}
    rng = np.random.default_rng(RANDOM_SEEDS[0] + 1000)
    pick = rng.choice(pool_broad.size, size=min(final_mass, pool_broad.size), replace=False)
    rm = np.zeros(fp.shape, bool)
    rm.ravel()[pool_broad[pick]] = True
    h_arms["random_mass_matched"] = rm
    d_only = np.exp(-ndi.distance_transform_edt(~cat) / 3.0)
    d_only[~allowed_broad] = 0.0
    dy, dx_ = BH.greedy_order(d_only, allowed_broad, final_mass, MIN_SEP_PX)
    dm = np.zeros(fp.shape, bool)
    dm[dy, dx_] = True
    h_arms["distance_only"] = dm
    terms: dict = {k: [] for k in h_arms}
    for cell in cells:
        bb = cell.bbox
        fold = dict(region=cell.active, visible=np.zeros_like(cell.active),
                    truth=ctx.hidden_by_cell[cell.key][bb] & cell.active)
        for k, arr in h_arms.items():
            _, t = EH.evaluate(arr[bb].astype(np.float32), fold, fp[bb], block_side=BLOCK_PX,
                               origin=(bb[0].start, bb[1].start),
                               global_shape=(grid.height, grid.width))
            terms[k].append(t)
    pooled = EH.pooled_summary({k: np.sum(v, axis=0) for k, v in terms.items()},
                               draws=BOOT_DRAWS, seed=BOOT_SEED, candidate="union")
    delta_champ = pooled["paired_differences"]["champion"]
    gate_g2_pass = bool(delta_champ["delta"] >= -0.002)
    gate_g1_pass = bool(g1_ok)
    mark(f"E3b holdout: union={pooled['scores']['union']['dti']:.6f} "
         f"champion={pooled['scores']['champion']['dti']:.6f} delta={delta_champ['delta']:+.6f} "
         f"{[round(x, 6) for x in delta_champ['ci95']]} G2={'PASS' if gate_g2_pass else 'FAIL'}")

    # ---------------- E3c: emission, format, uniqueness -------------- #
    # free the big feature stacks before the (memory-hungry) uniqueness scan
    import gc
    for _name in ("chi", "u8", "topo", "sig", "cand", "step_raw", "ksn", "zmean", "layer_maps",
                  "h_arms", "terms", "d_sgmc", "d_only", "dm"):
        globals().pop(_name, None)
    gc.collect()
    prediction = np.zeros(fp.shape, np.float32)
    prediction[union] = 1.0
    name = f"60GEMSDOE-H80-CONVCOMP-{int(union.sum())}-{STAMP}"
    note = (f"H80: {int(comp.sum())} new dots in the champion complement (convergent field, {adopted}"
            f"); union with the live-scored 0.2778 artifact")[:140]
    rec = SW.write_submission(DL / f"gems60-h80-convcomp-{int(union.sum())}-{STAMP}-zeros.tif",
                              prediction, ROOT / "data/official/sample_submission.tif", fp,
                              note=note, name=name[:140], catalogue=cat,
                              metadata={"preregistration": "registry/preregistration-h80.json",
                                        "adopted_field": adopted, "final_mass": final_mass,
                                        "min_sep_px": MIN_SEP_PX, "complement_px": 4.0})
    mark(f"wrote {rec['file']} sha={rec['sha256'][:16]} checks={rec['validator']['all_checks_passed']}")

    uniq = BH.uniqueness_scan(union, fp, (Path(rec["file"]).name,), extra_dirs=SCAN_DIRS)
    matched = {}
    for f in sorted({f for d in (ROOT / "registry/rasters", DL, *SCAN_DIRS) if Path(d).is_dir()
                     for f in Path(d).glob("*.tif")}):
        if f.name == Path(rec["file"]).name:
            continue
        try:
            with rasterio.open(f) as src:
                if (src.height, src.width) != union.shape:
                    continue
                a = src.read(1).astype(np.float32)
        except Exception:
            continue
        a[~np.isfinite(a)] = 0.0
        m = a > 0
        if not m.any():
            continue
        matched[f.name] = round(matched_overlap(union, m), 6)
    worst_matched = max(matched.items(), key=lambda kv: kv[1]) if matched else ("none", 0.0)
    lfl = uniq["like_for_like"]["max_dot_overlap_within_3px"] or 0.0
    sat = uniq["satisfiable"]["max_dot_overlap_within_3px"] or 0.0
    g3_pass = bool(uniq["literal"]["passes_rho"] and lfl <= OVERLAP_LIMIT
                   and sat <= OVERLAP_LIMIT and worst_matched[1] <= OVERLAP_LIMIT)
    mark(f"E3c uniqueness: |rho|max={uniq['literal']['max_abs_spearman']:.4f} "
         f"like-for-like={lfl} ({uniq['like_for_like']['worst_raster']}) "
         f"satisfiable={sat} ({uniq['satisfiable']['worst_raster']}) "
         f"one-to-one max={worst_matched[1]:.4f} ({worst_matched[0]}) G3={'PASS' if g3_pass else 'FAIL'}")
    mark(f"E3c literal reading worst={uniq['literal']['max_dot_overlap_within_3px']} vs "
         f"{uniq['literal']['worst_raster']} (universal blockers: {uniq['universal_blockers']})")

    # ---------------- PROJECTION (labelled, never a score) ----------- #
    T0 = 5_073.0        # champion credited mass inverted in knowledge/03 (METRIC ALGEBRA)
    K = 12_691.0        # hidden-truth pixel count pinned in knowledge/03
    n = int(union.sum())
    projections = {}
    for c in (0.0, BAR, 0.10, 0.146, 0.25):
        T = float(comp.sum()) * c
        Tt = T0 + T
        Ff = (37_654.0 - T0) + (n - 37_654 - T)
        den = Tt + M.ALPHA * Ff + M.BETA * max(K - Tt, 0.0)
        projections[f"{c:.4f}"] = round(Tt / den, 5)
    projections_aggressive = {}
    for c in (0.0, BAR, 0.10, 0.146, 0.25):
        T = float(aggressive_mass or 0) * c
        Tt = T0 + T
        Ff = (37_654.0 - T0) + ((DOT_COUNT_AGGRESSIVE or 37_654) - 37_654 - T)
        den = Tt + M.ALPHA * Ff + M.BETA * max(K - Tt, 0.0)
        projections_aggressive[f"{c:.4f}"] = round(Tt / den, 5)
    mark(f"PROJECTION (never a score): union DTI under assumed true credit/dot {projections}; "
         f"aggressive profile {projections_aggressive}")

    # uniqueness non-discrimination control: does a mass-matched RANDOM emission avoid the
    # comparators that this artifact "overlaps"?  If not, the clause carries no lane information.
    control = {}
    for rname in (uniq["universal_blockers"] or [None])[:2] + [uniq["like_for_like"]["worst_raster"],
                                                                 uniq["satisfiable"]["worst_raster"]]:
        if not rname or rname in control:
            continue
        hit = None
        for d in (ROOT / "registry/rasters", DL, *SCAN_DIRS):
            f = Path(d) / rname
            if f.is_file():
                hit = f
                break
        if hit is None:
            continue
        with rasterio.open(hit) as src:
            other = src.read(1).astype(np.float32)
        other[~np.isfinite(other)] = 0.0
        other = other > 0
        d_other = ndi.distance_transform_edt(~other)
        control[rname] = dict(
            footprint_fraction_within_3px=round(float((d_other[fp] <= 3.0).mean()), 6),
            champion_literal=round(float((d_other[champ] <= 3.0).mean()), 6),
            union_literal=round(float((d_other[union] <= 3.0).mean()), 6),
            random_mass_matched_literal=round(float((d_other[rm] <= 3.0).mean()), 6),
            random_mass_matched_one_to_one=round(matched_overlap(rm, other), 6))
    mark(f"E3c uniqueness control (mass-matched random emission vs the same comparators): {control}")

    g1 = ladder[str(final_mass)]
    gates = dict(
        G1_population_matched=dict(
            rule="complement credit/dot > mean(5 mass-matched random controls from the same pool) "
                 "AND paired CI lower > 0",
            complement_credit_per_dot=g1["complement_credit_per_dot"],
            complement_credit_per_dot_ci95=g1["complement_credit_per_dot_ci95"],
            random_credit_per_dot_mean=g1["random_credit_per_dot_mean"],
            random_credit_per_dot_each=g1["random_credit_per_dot_each"],
            complement_minus_random_7001_dti=g1["complement_minus_random_7001_dti"],
            champion_credit_per_dot=g1["instrument"]["champion"]["credit_per_px"],
            verdict="PASS" if (g1["complement_credit_per_dot"] > g1["random_credit_per_dot_mean"]
                               and g1["complement_minus_random_7001_dti"]["ci95"][0] > 0) else "FAIL"),
        G2_no_harm_registered_holdout=dict(
            rule="union - champion >= -0.002 pooled over the eight 'all'-mode folds",
            union_dti=pooled["scores"]["union"]["dti"], champion_dti=pooled["scores"]["champion"]["dti"],
            complement_dti=pooled["scores"]["complement"]["dti"],
            random_mass_matched_dti=pooled["scores"]["random_mass_matched"]["dti"],
            distance_only_dti=pooled["scores"]["distance_only"]["dti"],
            delta=delta_champ["delta"], ci95=delta_champ["ci95"],
            withheld_positive_pixels=pooled["scores"]["union"]["withheld_positive_pixels"],
            evaluator=pooled["evaluator_version"],
            verdict="PASS" if gate_g2_pass else "FAIL"),
        G3_uniqueness=dict(
            rule="|rho| <= 0.90 everywhere; like-for-like, satisfiable and one-to-one matched "
                 "3-px overlap <= 0.70",
            literal=uniq["literal"], like_for_like=uniq["like_for_like"],
            satisfiable=uniq["satisfiable"], universal_blockers=uniq["universal_blockers"],
            one_to_one_matched_max=worst_matched[1], one_to_one_matched_worst_raster=worst_matched[0],
            byte_unique=uniq["byte_unique"], scanned=uniq["scanned"], top_rows=uniq["top_rows"],
            verdict="PASS" if g3_pass else "FAIL"),
        G4_portal_format=dict(
            rule="shared writer's on-disk validator reports all_checks_passed",
            all_checks_passed=bool(rec["validator"]["all_checks_passed"]),
            problems=rec["validator"].get("problems", []),
            nan_pixels=rec["validator"].get("nan_pixels"), min=rec["validator"].get("min"),
            max=rec["validator"].get("max"), n_nonzero=rec["validator"].get("n_nonzero"),
            crs=rec["validator"].get("crs"),
            shape=[rec["validator"].get("height"), rec["validator"].get("width")],
            verdict="PASS" if rec["validator"]["all_checks_passed"] else "FAIL"),
    )
    verdict = ("PROMOTE-CANDIDATE" if all(v["verdict"] == "PASS" for v in gates.values()) else "NEGATIVE")

    card = dict(
        run="H80", hypothesis_id="GEMS60-H80", generated_utc=STAMP,
        author_session="arena/3c52f2be-60gemsdoe",
        preregistration="registry/preregistration-h80.json",
        evidence_class=("HOLDOUT-DTI + INSTRUMENT-DTI proxies; PROJECTION rows are labelled and are "
                        "never written as scores"),
        hypothesis=("mass placed in the complement of the live-scored champion, ranked by a convergent "
                    "field that includes strike-coherent step corroboration across independent drainages, "
                    "carries above-bar credit on the public off-catalogue fault population"),
        mechanism=("a fault rotates several adjacent catchments at once, so steepness steps co-occur on "
                   "channel cells with different downstream branch signatures reached laterally to the "
                   "local flow; complement placement avoids credit the incumbent already covers"),
        named_non_fault_process=("erosional and constructional lineaments, alluvial-fan and pediment "
                                 "surfaces, playa margins and lithologic contacts mimic coherent "
                                 "slope/strike patterns; the field requires the co-fire of several "
                                 "independent layers and >= 200 m separation from the mapped catalogue, "
                                 "which suppresses but does not eliminate them"),
        declared_approximations=[
            "branch_sig is the cell 500 m downstream: a coarse independence proxy that separates "
            "catchments splitting within about a kilometre, not every pair on one trunk",
            "facets and fronts come from the committed 9-band 10 m-derived 100 m reduction (uint8 "
            "quantised), not from a freshly resampled 1 m product",
            "the SGMC 1:750k off-catalogue population is a proxy truth set, not the hidden labels"],
        guard_report=guard_report,
        champion=dict(file=CHAMPION.name, sha256=champ_sha, dots=int(champ.sum()),
                      live_score=CHAMPION_LIVE, live_score_class="OWNER-REPORTED / UNVERIFIED"),
        fields=dict(adopted=adopted, significant_layer_gain=bool(layer_gain), ablation=ablation,
                    candidate_diagnostics=cand_diag, pool_broad=int(allowed_broad.sum()),
                    pool_restricted=int(allowed_restr.sum()),
                    baseline_reference="H71 build_field('broad'), reused unmodified",
                    wash_px=int(wash.sum())),
        ladder_broad=dict(masses=list(MASS_LADDER), rows=ladder,
                          status="measured, NOT emitted: the operator's literal clause-1 check flags "
                                 "the broad-pool union as a duplicate of r11_greedy_mp "
                                 "(IR-H80-PROFILE-01)"),
        ladder_restricted=dict(masses=list(RESTRICTED_MASSES), rows=ladder_restr),
        aggressive_profile_mass=aggressive_mass, final_mass=final_mass, final_profile="restricted",
        adopt_bar=ADOPT_BAR, metric_bar=BAR,
        artifact=dict(file=rec["file"], sha256=rec["sha256"], bytes=rec["bytes"], zip=rec["zip_file"],
                      zip_sha256=rec["zip_sha256"], submission_name=rec["submission_name"],
                      note=rec["note"], note_chars=rec["note_chars"], emitted=int(union.sum()),
                      complement_dots=int(comp.sum()), champion_dots=int(champ.sum()),
                      validator_all_checks_passed=bool(rec["validator"]["all_checks_passed"])),
        validator_output=rec["validator"],
        gates=gates, verdict=verdict,
        leakage_canary=dict(rows=canary_rows, flagged=[r["layer"] for r in canary_flag],
                            rule="AUC above 0.90 means leakage until proven otherwise",
                            note="measured on the withheld-catalogue folds of the shared holdout; "
                                 "instrument numbers, not scores"),
        holdout_pooled=pooled,
        registry_overlap=dict(uniqueness=uniq, one_to_one_matched=matched,
                              non_discrimination_control=control,
                              one_to_one_matched_max=worst_matched[1],
                              one_to_one_worst_raster=worst_matched[0]),
        projections=projections, projections_aggressive_broad=projections_aggressive,
        projection_note=("PROJECTION class: the metric identity T/(T + alpha*F + beta*(K - T)) at assumed "
                         "transfer credit for the added mass; K = 12,691 hidden-truth pixels and the "
                         "champion operating point T0 = 5,073 px are the values inverted in knowledge/03. "
                         "A projection is never written as a score."),
        instrument_note=("INSTRUMENT-DTI: SGMC 1:750k faults > 300 m from the given catalogue "
                         "(61,664 px, public proxy population). It is not the hidden test truth."),
        budget=dict(experiments=3, slots_spent=0),
        seconds=round(time.time() - t0, 1), log=log)
    (EVID / "h80_runcard.json").write_text(json.dumps(card, indent=2, default=float, allow_nan=False) + "\n")
    mark(f"verdict {verdict}; wrote evidence/h80_runcard.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
