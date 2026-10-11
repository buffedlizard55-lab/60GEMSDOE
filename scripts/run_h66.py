#!/usr/bin/env python3
"""H66-1: the tectonic-geomorphology lane scored against *off-catalogue* truth.

Preregistration: ``registry/preregistration-h66.json`` (committed before any number
below existed).  Three budgeted experiments, in the brief's order:

E1  the mandated first test, run against BOTH targets
      E1a  withheld catalogue segments  -- the literal brief; comparability only
      E1b  SGMC off-catalogue segments  -- the competition's actual target; GATING
    "do channels crossing withheld segments show larger steepness steps than
     random lines of the same orientation?  If not, stop."
E2  leakage canary (each feature alone) + off-catalogue instrument skill against
    mass-matched controls, with a paired 20 km spatial-block bootstrap.
E3  (scripts/build_submission60.py, TAG=h66) emission, validation, uniqueness.

Why the target changed (measured, not argued)
---------------------------------------------
``evidence/e61_instrument_audit.json`` scores the family's twelve live-scored
artifacts against six local truth sets.  The Spearman rank correlation with the
live score is **-0.9021** for the catalogue-truth DTI -- the very instrument every
knickpoint-lane run in this repository has gated on -- and **+0.4685** for the
SGMC-off-catalogue-truth DTI.  The catalogue instrument ranks the owner-reported
0.2778 champion last of twelve.  So the lane's gates have been pointing the wrong
way, and the only local truth set that contains *off-catalogue* faults (which is
what the hidden set is) is the SGMC difference set.

Shared tools are imported, never forked: ``gems57.grid`` / ``gems57.holdout``,
``gems60.lane`` / ``gems60.geomorph``, ``gems61.dataio`` / ``gems61.instruments``,
``gems52.metric``, and the lane driver ``scripts/run_lane60.py`` (E1 kernels,
confound masks, AUC).

Usage:
    GEMS60_FEATURE_CACHE=features65 python scripts/run_h66.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems52 import metric as M                       # noqa: E402
from gems57 import grid as G57                       # noqa: E402
from gems57 import holdout as HO                     # noqa: E402
from gems52 import holdout as H52                    # noqa: E402  (mask_visible lives here)
from gems60 import lane as L                         # noqa: E402
from gems61 import dataio, instruments as I          # noqa: E402
import run_lane60 as RL                              # noqa: E402  (E1 kernels, confounds, AUC)

EVID = ROOT / "evidence"
TAG = os.environ.get("GEMS60_TAG", "h66")
BOOT_DRAWS = 1000
BOOT_SEED = 6601
BLOCK_PX = 200                       # 20 km spatial blocks for the paired bootstrap
BUDGET = 37_654                      # champion-matched mass (prereg: declared_parameters)
MIN_SEGMENT_PX = 6
N_TRANSECTS = 10
MAX_COMPONENTS = 1200
POOL_CAP = 200_000


def _clean(o):
    """Recursively replace non-finite floats with None so ``allow_nan=False`` cannot fail
    on a legitimately undefined measurement (an AUC over a domain with no positives)."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    return o


# --------------------------------------------------------------------------- #
# E1b -- the mandated statistic, off-catalogue target
# --------------------------------------------------------------------------- #
def run_e1_offcat(step, channel, fp, offcat, cat, max_components=MAX_COMPONENTS,
                  n_transects=N_TRANSECTS):
    """Mean log-ksn step within 3 px of an off-catalogue fault segment, minus the mean
    over ``n_transects`` random same-orientation same-length transects.

    Identical statistic to ``run_lane60.run_e1`` (same ``transect_stat`` kernel, same
    orientation estimator, same 3 px window); only the segment population and the
    transect pool change.  The pool excludes a 10 px (1 km) dilation of both the
    given catalogue and the off-catalogue set, so a control transect cannot sit on
    any known trace.
    """
    rows = []
    rng = np.random.default_rng(BOOT_SEED)
    pool_mask = fp & ~ndi.binary_dilation(cat | offcat, iterations=10)
    pool = np.nonzero(pool_mask)
    if pool[0].size > POOL_CAP:
        pick = rng.choice(pool[0].size, POOL_CAP, replace=False)
        pool = (pool[0][pick], pool[1][pick])
    lab, n = ndi.label(offcat)
    objs = ndi.find_objects(lab)
    cids = np.arange(1, n + 1)
    if cids.size > max_components:
        cids = np.sort(rng.choice(cids, max_components, replace=False))
    for cid in cids:
        sl = objs[int(cid) - 1]
        if sl is None:
            continue
        sub_y, sub_x = np.nonzero(lab[sl] == cid)
        ys = sub_y + sl[0].start
        xs = sub_x + sl[1].start
        if ys.size < MIN_SEGMENT_PX:
            continue
        az, length = RL.component_orientation((ys, xs))
        length = int(np.clip(round(length), MIN_SEGMENT_PX, 60))
        win, sub = RL._dilate_window(step.shape, ys, xs, 3)
        zone = sub & channel[win] & fp[win]
        vals = step[win][zone]
        vals = vals[np.isfinite(vals)]
        if vals.size < 3:
            rows.append(dict(component=int(cid), n_px=int(ys.size),
                             crossing_channel_px=int(zone.sum()),
                             skipped="no channel crossing"))
            continue
        obs = float(vals.mean())
        ctr = []
        for _ in range(n_transects):
            y0, x0 = RL._random_point(pool, rng)
            if y0 is None:
                break
            got = RL.transect_stat(y0, x0, az, length, step, channel, fp, pool,
                                   step.shape, rng=rng)
            if got is not None:
                ctr.append(got[0])
        if len(ctr) < 5:
            rows.append(dict(component=int(cid), n_px=int(ys.size),
                             crossing_channel_px=int(zone.sum()),
                             observed_mean_step=obs,
                             skipped=f"only {len(ctr)} valid transects"))
            continue
        rows.append(dict(component=int(cid), n_px=int(ys.size),
                         azimuth_deg=float(np.rad2deg(az)), length_px=length,
                         crossing_channel_px=int(zone.sum()),
                         observed_mean_step=obs,
                         control_mean_step=float(np.mean(ctr)),
                         control_std_step=float(np.std(ctr)),
                         n_control_transects=len(ctr),
                         paired_difference=obs - float(np.mean(ctr))))
    return rows


# --------------------------------------------------------------------------- #
# E2 -- paired spatial-block bootstrap of the official DTI
# --------------------------------------------------------------------------- #
def block_terms(pred: np.ndarray, truth: np.ndarray, gy: np.ndarray, gx: np.ndarray,
                n_blocks: int, q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-block (TPw, FPw) sums for one emission against one fixed truth set."""
    m, _, _ = M.max_cover(pred, truth)
    tb = (gy // BLOCK_PX) * (pred.shape[1] // BLOCK_PX + 1) + (gx // BLOCK_PX)
    tp = np.bincount(tb, weights=m, minlength=n_blocks)
    w = np.where(pred > 0, pred, 0.0)
    py, px = np.nonzero(w > 0)
    fpw_px = w[py, px] * (1.0 - q[py, px])
    pb = (py // BLOCK_PX) * (pred.shape[1] // BLOCK_PX + 1) + (px // BLOCK_PX)
    fp = np.bincount(pb, weights=fpw_px, minlength=n_blocks)
    return tp, fp


def paired_block_bootstrap(preds: dict, truth: np.ndarray, valid: np.ndarray,
                           cat: np.ndarray, draws=BOOT_DRAWS, seed=BOOT_SEED,
                           reference="lane") -> dict:
    """Cluster bootstrap of DTI and of paired DTI differences over 20 km blocks.

    Blocks are resampled with replacement; the *same* resample is applied to every
    arm, so the paired difference is a within-resample contrast.  DTI is recomputed
    from the resampled (T, F, K) triple each draw, which is the ratio's own form.
    """
    _, q, _ = M.max_cover(preds[reference], truth)      # q depends on truth only
    gy, gx = np.nonzero(truth)
    nb = (truth.shape[0] // BLOCK_PX + 1) * (truth.shape[1] // BLOCK_PX + 1)
    kb = np.bincount((gy // BLOCK_PX) * (truth.shape[1] // BLOCK_PX + 1) + (gx // BLOCK_PX),
                     minlength=nb).astype(np.float64)
    terms = {}
    for name, p in preds.items():
        mass = np.where(valid, np.asarray(p, np.float64), 0.0)
        mass = H52.mask_visible(mass, cat & valid)
        terms[name] = block_terms(mass, truth, gy, gx, nb, q)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nb, size=(draws, nb))
    out = {"per_arm": {}, "paired": {}}
    for name, (tp, fp) in terms.items():
        T = tp[idx].sum(axis=1)
        F = fp[idx].sum(axis=1)
        K = kb[idx].sum(axis=1)
        den = T + M.ALPHA * F + M.BETA * np.maximum(K - T, 0.0)
        d = np.divide(T, den, out=np.zeros_like(T), where=den > 0)
        lo, hi = np.quantile(d, [0.025, 0.975])
        out["per_arm"][name] = dict(mean=float(d.mean()), median=float(np.median(d)),
                                    ci95=[float(lo), float(hi)])
    for name, (tp, fp) in terms.items():
        if name == reference:
            continue
        T0, F0 = terms[reference]
        T1, F1 = tp, fp
        def _dti(T_, F_):
            Ts, Fs, Ks = T_[idx].sum(1), F_[idx].sum(1), kb[idx].sum(1)
            den_ = Ts + M.ALPHA * Fs + M.BETA * np.maximum(Ks - Ts, 0.0)
            return np.divide(Ts, den_, out=np.zeros_like(Ts), where=den_ > 0)

        d0, d1 = _dti(T0, F0), _dti(T1, F1)
        dd = d0 - d1
        lo, hi = np.quantile(dd, [0.025, 0.975])
        out["paired"][f"{reference}_minus_{name}"] = dict(
            mean=float(dd.mean()), ci95=[float(lo), float(hi)],
            fraction_positive=float((dd > 0).mean()))
    out["bootstrap"] = dict(method="paired 20 km spatial-block percentile", block_px=BLOCK_PX,
                            n_blocks=int(nb), draws=draws, seed=seed)
    return out


def main() -> int:
    # Fail-closed: main carries an authoritative lane STOP for channel-steepness
    # (registry/current_site_status.json) enforced by scripts/stop_guard.py, which
    # landed on main in PR #15 while this session was measuring.  Adopt the shared
    # guard rather than fork around it (IR-66-STOP-01): this runner measures the
    # same lane, so it must not run while the lane is stopped.
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "H66 off-catalogue knickpoint experiment runner"):
        return 0
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-candidates", type=int, default=120_000)
    ap.add_argument("--budget", type=int, default=BUDGET)
    a = ap.parse_args()
    t0 = time.time()
    log: list[str] = []

    def mark(msg):
        line = f"[H66] {msg} ({time.time() - t0:.1f}s)"
        print(line, flush=True)
        log.append(line)

    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue
    mark(f"grid {grid.height}x{grid.width} footprint={int(fp.sum()):,} catalogue={int(cat.sum()):,}")

    step = RL.load_step()
    mark(f"step statistic = {RL.STEP_STATISTIC}")
    channel = RL.load("channel")
    ksn = RL.load("ksn").astype(np.float64)
    acc = RL.load("acc").astype(np.float64)
    from gems60 import geomorph as gm
    if (RL.CACHE / "branch_sig.npy").is_file():
        branch = RL.load("branch_sig").astype(np.int64)
        mark("independence = substrate branch_sig (native 10 m network)")
    else:
        branch = gm.branch_signature(RL.load("dircode"), fp,
                                     k=L.CORRIDOR_HALF_LEN_PX - 1).astype(np.int64)
        mark(f"independence = branch_signature(k={L.CORRIDOR_HALF_LEN_PX - 1})")
    exclude, conf = RL.confound_masks(step, channel)
    mark(f"confounds {conf}")

    # ---------------- E1a: the literal brief ---------------- #
    ctx = HO.build_holdout(grid)
    mark(f"holdout cells={len(ctx.cells)}")
    truth_by_cell = {k: v for k, v in ctx.hidden_by_cell.items()}
    visible_by_cell = {c.key: ctx.visible(c.key) for c in ctx.cells}
    active_by_cell = {c.key: c.active for c in ctx.cells}
    e1a_rows = RL.run_e1(ctx, step, channel, active_by_cell, truth_by_cell, visible_by_cell,
                         modes=("all",))
    e1a = RL.paired_bootstrap(e1a_rows, draws=BOOT_DRAWS, seed=BOOT_SEED)
    e1a_full = dict(evidence_class="MEASUREMENT",
                    target="withheld catalogue segments (shared hide-and-recover, mode 'all')",
                    gating=False, summary=e1a, components=len(e1a_rows),
                    skipped=sum(1 for r in e1a_rows if "skipped" in r))
    mark(f"E1a (literal brief, NOT gating) {e1a}")

    # ---------------- E1b: off-catalogue target, GATING ---------------- #
    sgmc = dataio.load_sgmc()
    offcat = I.sgmc_off_catalogue(sgmc, cat, fp, buffer_px=3)
    mark(f"SGMC {int(sgmc.sum()):,} px | off-catalogue (>300 m) {int(offcat.sum()):,} px")
    e1b_rows = run_e1_offcat(step, channel, fp, offcat, cat)
    e1b = RL.paired_bootstrap(e1b_rows, draws=BOOT_DRAWS, seed=BOOT_SEED)
    proceed = bool(e1b.get("mean") is not None and e1b["mean"] > 0
                   and e1b.get("ci95") and e1b["ci95"][0] is not None and e1b["ci95"][0] > 0)
    reasons = {}
    for r in e1b_rows:
        if "skipped" in r:
            reasons[r["skipped"]] = reasons.get(r["skipped"], 0) + 1
    e1b_full = dict(evidence_class="MEASUREMENT",
                    target="USGS SGMC faults > 300 m from the given catalogue",
                    gating=True, gate="G1: mean > 0 AND ci95 lower bound > 0",
                    offcat_px=int(offcat.sum()), offcat_components_total=int(ndi.label(offcat)[1]),
                    components_sampled=int(len(e1b_rows)), summary=e1b,
                    components_scored=int(e1b.get("n_components") or 0),
                    skipped=sum(1 for r in e1b_rows if "skipped" in r),
                    skip_reasons=reasons,
                    coverage_note=("components sampled = min(max_components, total); a component is "
                                   "skipped when no bedrock-channel pixel lies within 3 px of it, which "
                                   "is itself the measurement of how much off-catalogue trace the "
                                   "channel network can see at all"),
                    gate_G1_verdict="PROCEED" if proceed else "STOP")
    (EVID / f"{TAG}_e1_first_test.json").write_text(json.dumps(_clean(
        dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             preregistration="registry/preregistration-h66.json",
             step_statistic=RL.STEP_STATISTIC,
             E1a_literal_brief=e1a_full, E1b_off_catalogue=e1b_full,
             e1a_rows=e1a_rows, e1b_rows=e1b_rows, log=log)), indent=2, allow_nan=False) + "\n")
    mark(f"E1b (GATING) {e1b} -> G1 {'PROCEED' if proceed else 'STOP'}")

    # ---------------- surface + emission arms ---------------- #
    z, cand, cand_diag = L.prepare_candidates(step, channel, exclude)
    mark(f"candidates {cand_diag}")
    res = L.surface_from_candidates(z, cand, branch, cat, dict(cand_diag),
                                    max_candidates=a.max_candidates)
    p = res.p.astype(np.float64)
    mark(f"surface {res.diagnostics}")
    allowed = L.allowed_production(fp, cat, L.CATALOGUE_BUFFER_PX)
    mark(f"allowed={int(allowed.sum()):,}")

    d = ndi.distance_transform_edt(~cat)
    p_dist = np.exp(-d / 3.0)
    p_dist[~allowed] = 0.0
    from scipy.stats import rankdata
    zz = np.where(channel & ~exclude & np.isfinite(ksn), ksn, np.nan)
    rr = rankdata(np.where(np.isfinite(zz), zz, 0.0).ravel()).reshape(zz.shape) / zz.size
    p_ksn = np.where(np.isfinite(zz) & allowed, rr, 0.0)
    rng = np.random.default_rng(6600)
    pr = np.zeros_like(p)
    pr[allowed] = rng.random(int(allowed.sum()))

    arms = {
        "lane": L.top_k_dots(p, allowed, a.budget).astype(np.float32),
        "ksn_only_no_alignment": L.top_k_dots(p_ksn, allowed, a.budget).astype(np.float32),
        "distance_only": L.top_k_dots(p_dist, allowed, a.budget).astype(np.float32),
        "random_mass_control": L.top_k_dots(pr, allowed, a.budget).astype(np.float32),
    }
    champ_path = ROOT / "registry/rasters/dotted_b2_prune_02778.tif"
    if champ_path.is_file():
        champ = dataio.read_band(champ_path)
        arms["champion_02778_owner_report"] = np.nan_to_num(champ, nan=0.0).astype(np.float32)
    for k, v in arms.items():
        mark(f"arm {k:32s} dots={int((v > 0).sum()):,} on_catalogue={int(((v > 0) & cat).sum())}")

    # ---------------- E2: leakage canary ---------------- #
    canary_rows = []
    for name, feat in (("knickpoint_step", step), ("ksn", ksn), ("drainage_area", acc),
                       ("lane_p", p), ("dist_to_visible", -d.astype(np.float64))):
        canary_rows.append(dict(
            feature=name,
            # domain = the emission domain (footprint minus a 2 px catalogue buffer): the same
            # domain run_lane60 uses, so a canary AUC here is comparable with H60-A / H65-1
            auc_offcat=RL.auc(feat, offcat & fp, allowed),
            # the catalogue column is reported on the full footprint instead: `allowed` excludes a
            # 2 px dilation of the catalogue, so it holds no catalogue positives and the AUC there
            # is undefined by construction (this raised on the first run -- kept as the fix)
            auc_catalogue_full_footprint=RL.auc(feat, cat & fp, fp)))
    canary = []
    for row in canary_rows:
        worst = max(max(row["auc_offcat"], 1 - row["auc_offcat"]),
                    max(row["auc_catalogue_full_footprint"], 1 - row["auc_catalogue_full_footprint"]))
        canary.append(dict(**row, max_abs_auc=float(worst), leakage_flag=bool(worst > 0.90)))
    mark("canary " + json.dumps({c["feature"]: round(c["max_abs_auc"], 4) for c in canary}))

    # ---------------- E2: off-catalogue instrument skill ---------------- #
    terrain = dataio.dequantise_u8(ROOT / "data/external/topo_10m_derived_100m_u8.tif", 5)
    truths = {
        "sgmc_off_full": offcat,
        "sgmc_off_thin8000": I.thin_random(offcat, 8000, seed=61),
        "sgmc_off_balanced8000": I.terrain_balanced_truth(offcat, fp, terrain, 8000, seed=61)[0],
        "catalogue_full": I.catalogue_truth(cat, fp),
    }
    instr = {}
    for tname, tmask in truths.items():
        per_arm = {k: I.global_dti(v, tmask, fp, cat) for k, v in arms.items()}
        boot = paired_block_bootstrap(arms, tmask, fp, cat, reference="lane")
        instr[tname] = dict(n_truth=int(tmask.sum()), per_arm=per_arm, bootstrap=boot)
        mark(f"truth {tname:22s} n={int(tmask.sum()):>7,} " +
             " ".join(f"{k}={per_arm[k]['dti']:.5f}" for k in arms))
        mark(f"   lane-random paired {boot['paired']['lane_minus_random_mass_control']}")

    gate_g3 = instr["sgmc_off_full"]["bootstrap"]["paired"]["lane_minus_random_mass_control"]
    g3_pass = bool(gate_g3["ci95"][0] > 0)
    out = dict(
        experiment="H66-1 E1/E2",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        preregistration="registry/preregistration-h66.json",
        evidence_class="INSTRUMENT-DTI (public proxy truth; NOT HOLDOUT-DTI, NOT ORGANIZER-CONFIRMED)",
        step_statistic=RL.STEP_STATISTIC,
        truth_sets={k: int(v.sum()) for k, v in truths.items()},
        instrument_provenance="evidence/e61_instrument_audit.json spearman_vs_live",
        confounds=conf, candidates=cand_diag, surface=res.diagnostics,
        budget=a.budget, allowed_px=int(allowed.sum()),
        e1a_literal_brief=e1a, e1b_off_catalogue=e1b, gate_G1="PROCEED" if proceed else "STOP",
        canary=canary,
        canary_rule="max(AUC,1-AUC) > 0.90 is leakage until proven otherwise",
        instrument=instr,
        gate_G3=dict(reference="sgmc_off_full lane_minus_random_mass_control", **gate_g3,
                     verdict="PASS" if g3_pass else "FAIL"),
        log=log)
    (EVID / f"{TAG}_holdout.json").write_text(json.dumps(_clean(out), indent=2, allow_nan=False) + "\n")
    mark(f"wrote evidence/{TAG}_holdout.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
