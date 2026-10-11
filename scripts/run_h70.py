#!/usr/bin/env python3
"""H70-1: paired-polarity knickpoint trains — the three budgeted experiments.

Preregistration: ``registry/preregistration-h70.json`` (committed before any
number below existed).

E1  mandated first test: do channels crossing withheld segments show larger
    steps of the preregistered statistic (``pair_strength``) than random lines
    of the same orientation?  G1 gate: PROCEED else STOP (no emission).
    E1b (non-gating diagnostic): the identical statistic on USGS SGMC faults
    > 300 m from the given catalogue (the H66 target).
E2  leakage canary (each feature alone) + the shared pooled holdout DTI with
    the crest-only unpaired ablation and the three standard controls + the
    owner-reported 0.2778 champion raster as a benchmark arm; and the
    production-domain instrument bench on public proxy truths.
E3  lives in scripts/build_submission70.py: emission, format validation,
    registry-uniqueness (only run when G1 passes).

Shared tools reused unmodified (no private forks): gems57.grid /
gems57.holdout / gems57.evaluate_holdout / gems57.metric, gems60.lane /
gems60.geomorph, gems61.dataio / gems61.instruments, and the lane kernel
functions of scripts/run_lane60.py (run_e1, paired_bootstrap, confound_masks,
auc) / scripts/run_h66.py (run_e1_offcat, paired_block_bootstrap).

Governance note (IR-70-GOV-01): the committed ``current_site_status.json``
retains a H65-1-era STOP for the channel-steepness lane, enforced fail-closed
by scripts/stop_guard.py against the old runners.  This NEW script neither
imports that guard (it would stop old-statistic reruns, which this is not) nor
edits the status file; the authorization and the deviation are recorded
verbatim in the preregistration, and the empirical G1 gate is enforced here as
written.

Usage:
    python scripts/run_h70.py
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("GEMS60_FEATURE_CACHE", "features70")
os.environ.setdefault("GEMS60_TAG", "h70")
os.environ.setdefault("GEMS60_STEP_STATISTIC", "upstream")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_lane60 as RL                              # noqa: E402
from run_h66 import run_e1_offcat, paired_block_bootstrap  # noqa: E402
from gems57 import grid as G57                       # noqa: E402
from gems57 import holdout as HO                     # noqa: E402
from gems57 import evaluate_holdout as EH            # noqa: E402
from gems60 import lane as L                         # noqa: E402
from gems61 import dataio, instruments as I          # noqa: E402

EVID = ROOT / "evidence"
TAG = "h70"
BUDGET = 40_000
MAX_CANDIDATES = 120_000
Z_MIN = 1.0
MIN_SEP_PX = 2.8
INC_POS_CH = True
PAIR_FLOOR = float(np.log(1.25))
BOOT_DRAWS = 1_000
BOOT_SEED = 60101
CHAMPION = ROOT / "registry" / "rasters" / "dotted_b2_prune_02778.tif"


def _clean(o):
    """Recursively replace non-finite floats with None so allow_nan=False holds."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    return o


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-candidates", type=int, default=MAX_CANDIDATES)
    ap.add_argument("--budget", type=int, default=BUDGET)
    a = ap.parse_args()
    t0 = time.time()
    log: list[str] = []

    def mark(msg: str):
        line = f"[H70] {msg} ({time.time() - t0:.1f}s)"
        print(line, flush=True)
        log.append(line)

    print("H70-1: paired-polarity knickpoint trains. Preregistration registry/preregistration-h70.json.", flush=True)
    print("H70-1: IR-70-GOV-01 governance deviation as registered (no fork of stopped runners; G1 enforced).", flush=True)

    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue
    mark(f"grid {grid.height}x{grid.width} footprint={int(fp.sum()):,} catalogue={int(cat.sum()):,}")

    pair = RL.load("pair_strength").astype(np.float32)
    crest = RL.load("crest").astype(np.float32)
    base_drop = RL.load("base_drop").astype(np.float32)
    channel = RL.load("channel")
    ksn = RL.load("ksn").astype(np.float32)
    acc = RL.load("acc").astype(np.float32)
    branch = RL.load("branch_sig").astype(np.int64)
    exclude, conf = RL.confound_masks(pair, channel)
    extra = RL.load("exclude_extra70").astype(bool)
    exclude = exclude | extra
    conf.update(radcg70_px=int(RL.load("radcg70").sum()),
                litho_core70_px=int(RL.load("litho_core70").sum()),
                exclude_extra70_px=int(extra.sum()),
                excluded_px=int(exclude.sum()),
                channel_excluded_px=int((channel & exclude).sum()))
    mark(f"confounds {conf}")

    # ---------------- candidates (shared machinery + registered floor) ------ #
    z_pair, cand_pair, cand_diag = L.prepare_candidates(pair, channel, exclude,
                                                        block_px=L.BLOCK_PX, z_min=Z_MIN)
    cand_pair = cand_pair & np.isfinite(pair) & (pair >= PAIR_FLOOR)
    cand_diag.update(pair_floor=PAIR_FLOOR,
                     candidate_pixels_after_pair_floor=int(cand_pair.sum()),
                     z_min=Z_MIN, min_sep_px=MIN_SEP_PX,
                     include_positive_channels=INC_POS_CH)
    z_crest, cand_crest, crest_diag = L.prepare_candidates(crest, channel, exclude,
                                                           block_px=L.BLOCK_PX, z_min=Z_MIN)
    mark(f"candidates {cand_diag}")
    mark(f"crest ablation candidates {crest_diag}")

    # ---------------- E1a: the mandated first test (G1, GATING) ------------- #
    ctx = HO.build_holdout(grid)
    mark(f"holdout cells={len(ctx.cells)}")
    truth_by_cell = {k: v for k, v in ctx.hidden_by_cell.items()}
    visible_by_cell = {c.key: ctx.visible(c.key) for c in ctx.cells}
    active_by_cell = {c.key: c.active for c in ctx.cells}
    e1a_rows = RL.run_e1(ctx, pair, channel, active_by_cell, truth_by_cell, visible_by_cell,
                         modes=("all",))
    e1a = RL.paired_bootstrap(e1a_rows, draws=BOOT_DRAWS, seed=BOOT_SEED)
    mark(f"E1a pair_strength (GATING) {e1a}")

    # crest-only ablation runs the identical first test as the mechanism contrast
    e1a_crest_rows = RL.run_e1(ctx, crest, channel, active_by_cell, truth_by_cell,
                               visible_by_cell, modes=("all",))
    e1a_crest = RL.paired_bootstrap(e1a_crest_rows, draws=BOOT_DRAWS, seed=BOOT_SEED)
    mark(f"E1a crest-only ablation (mechanism contrast) {e1a_crest}")

    # ---------------- E1b: off-catalogue diagnostic (NON-GATING) ------------ #
    sgmc = dataio.load_sgmc()
    offcat = I.sgmc_off_catalogue(sgmc, cat, fp, buffer_px=3)
    mark(f"SGMC {int(sgmc.sum()):,} px | off-catalogue (>300 m) {int(offcat.sum()):,} px")
    e1b_rows = run_e1_offcat(pair, channel, fp, offcat, cat)
    e1b = RL.paired_bootstrap(e1b_rows, draws=BOOT_DRAWS, seed=BOOT_SEED)
    mark(f"E1b off-catalogue diagnostic (NON-GATING) {e1b}")

    proceed = e1a.get("verdict") == "PROCEED"
    (EVID / f"{TAG}_e1_first_test.json").write_text(json.dumps(_clean(dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        preregistration="registry/preregistration-h70.json",
        evidence_class="MEASUREMENT",
        statistic="pair_strength = min(crest, base_drop) at 500 m paired separation",
        E1a_withheld_catalogue=dict(gating=True, gate="G1: verdict == PROCEED",
                                    summary=e1a, components=len(e1a_rows),
                                    skipped=sum(1 for r in e1a_rows if "skipped" in r)),
        E1a_crest_only_ablation=dict(gating=False, summary=e1a_crest),
        E1b_sgmc_off_catalogue=dict(gating=False, note=("population mixes ancient/relict "
                                                        "structures; preregistered non-gating"),
                                    summary=e1b, components=len(e1b_rows),
                                    skipped=sum(1 for r in e1b_rows if "skipped" in r)),
        gate_G1_verdict="PROCEED" if proceed else "STOP",
        e1a_rows=e1a_rows, e1b_rows=e1b_rows, log=log)),
        indent=2, allow_nan=False) + "\n")
    mark(f"G1 {'PROCEED' if proceed else 'STOP'}")

    if not proceed:
        (EVID / f"{TAG}_lane_stop.json").write_text(json.dumps(_clean(dict(
            reason=("G1 failed: paired-polarity steps at withheld catalogue crossings do "
                    "not exceed random same-orientation transects; H70-1 stops here, no "
                    "surface, no emission, negative run card"),
            e1a_summary=e1a, e1a_crest_ablation=e1a_crest, e1b_diagnostic=e1b,
            protocol="registry/preregistration-h70.json gates.G1_first_test")),
            indent=2, allow_nan=False) + "\n")
        mark("wrote evidence/h70_lane_stop.json -- STOP")
        return 2

    # ---------------- E2: per-cell holdout bench ---------------------------- #
    cells = [c for c in ctx.cells if c.mode == "all"]
    arms = ("lane_h70", "crest_only_no_pairing", "ksn_only_no_alignment",
            "distance_only", "random_mass_control", "champion_02778")
    terms = {k: [] for k in arms}
    canary_rows: list[dict] = []
    budgets: dict[str, dict] = {}
    champ = None
    if CHAMPION.is_file():
        champ = np.nan_to_num(dataio.read_band(CHAMPION), nan=0.0).astype(np.float32)
    from scipy.stats import rankdata
    for cell in cells:
        bb = cell.bbox
        vis = visible_by_cell[cell.key]
        vis_crop = vis[bb]
        buf = ndi.binary_dilation(vis_crop, iterations=L.CATALOGUE_BUFFER_PX)
        allowed = cell.active & ~buf
        n_allowed = int(allowed.sum())
        budget = max(200, int(round(RL.DENSITY * n_allowed)))
        budgets[cell.key] = dict(allowed=n_allowed, budget=budget)

        res_p = L.surface_from_candidates(z_pair, cand_pair, branch, vis, dict(cand_diag),
                                          max_candidates=a.max_candidates,
                                          include_positive_channels=INC_POS_CH)
        p_pair = res_p.p
        dots_lane = L.top_k_dots(p_pair[bb], allowed, budget, min_sep_px=MIN_SEP_PX)
        res_c = L.surface_from_candidates(z_crest, cand_crest, branch, vis, dict(crest_diag),
                                          max_candidates=a.max_candidates,
                                          include_positive_channels=INC_POS_CH)
        dots_crest = L.top_k_dots(res_c.p[bb], allowed, budget, min_sep_px=MIN_SEP_PX)

        d = ndi.distance_transform_edt(~vis_crop)
        p_dist = np.exp(-d / 3.0)
        p_dist[~allowed] = 0.0
        dots_dist = L.top_k_dots(p_dist, allowed, budget)
        zz = np.where(channel[bb] & ~exclude[bb] & np.isfinite(ksn[bb]), ksn[bb], np.nan)
        rr = rankdata(np.where(np.isfinite(zz), zz, 0.0).ravel()).reshape(zz.shape) / zz.size
        p_ksn = np.where(np.isfinite(zz), rr, 0.0).astype(np.float64)
        dots_ksn = L.top_k_dots(p_ksn, allowed, budget)
        rng = np.random.default_rng(60000 + cell.fold)
        pr = np.zeros(allowed.shape)
        pr[allowed] = rng.random(n_allowed)
        dots_rnd = L.top_k_dots(pr, allowed, budget)
        pred_by_arm = dict(lane_h70=dots_lane.astype(np.float32),
                           crest_only_no_pairing=dots_crest.astype(np.float32),
                           ksn_only_no_alignment=dots_ksn.astype(np.float32),
                           distance_only=dots_dist.astype(np.float32),
                           random_mass_control=dots_rnd.astype(np.float32))
        if champ is not None:
            pred_by_arm["champion_02778"] = champ[bb]
        fold = dict(region=cell.active, visible=np.zeros_like(cell.active),
                    truth=truth_by_cell[cell.key][bb])
        for arm, arr in pred_by_arm.items():
            scored, t = EH.evaluate(np.clip(arr, 0, 1).astype(np.float32), fold,
                                    grid.footprint[bb], block_side=200,
                                    origin=(bb[0].start, bb[1].start),
                                    global_shape=(grid.height, grid.width))
            terms[arm].append(t)
        feats = [("pair_strength", pair[bb]), ("crest_only", crest[bb]),
                 ("base_drop", base_drop[bb]), ("ksn", ksn[bb]),
                 ("drainage_area", acc[bb]), ("lane_p", p_pair[bb].astype(np.float64)),
                 ("dist_to_visible", -d)]
        for name, feat in feats:
            canary_rows.append(dict(cell=cell.key, feature=name, auc=RL.auc(
                feat, truth_by_cell[cell.key][bb] & cell.active, allowed)))
        mark(f"cell {cell.key} budget={budget} aligned={res_p.diagnostics.get('aligned_candidates')}")
        del res_p, res_c, p_pair, d, pr
        gc.collect()

    pooled = EH.pooled_summary({k: np.sum(v, axis=0) for k, v in terms.items()},
                               draws=BOOT_DRAWS, seed=BOOT_SEED, candidate="lane_h70")
    can: dict[str, dict] = {}
    for row in canary_rows:
        av = row["auc"]
        if not np.isfinite(av):
            continue
        m = max(av, 1 - av)
        cur = can.get(row["feature"])
        if cur is None or m > cur["max_abs_auc"]:
            can[row["feature"]] = dict(feature=row["feature"], max_abs_auc=float(m),
                                       auc=float(av), worst_cell=row["cell"],
                                       leakage_flag=bool(m > 0.90))
    mark(f"pooled lane={pooled['scores']['lane_h70']['dti']:.6f} "
         f"crest={pooled['scores']['crest_only_no_pairing']['dti']:.6f} "
         f"random={pooled['scores']['random_mass_control']['dti']:.6f}")
    mark(f"paired deltas {json.dumps({k: round(v['delta'], 6) for k, v in pooled['paired_differences'].items()})}")

    # ---------------- E2: production-domain instrument bench ---------------- #
    allowed_prod = L.allowed_production(fp, cat, L.CATALOGUE_BUFFER_PX)
    res_prod = L.surface_from_candidates(z_pair, cand_pair, branch, cat, dict(cand_diag),
                                         max_candidates=a.max_candidates,
                                         include_positive_channels=INC_POS_CH)
    res_prod_crest = L.surface_from_candidates(z_crest, cand_crest, branch, cat, dict(crest_diag),
                                               max_candidates=a.max_candidates,
                                               include_positive_channels=INC_POS_CH)
    d_cat = ndi.distance_transform_edt(~cat)
    p_dist_g = np.where(allowed_prod, np.exp(-d_cat / 3.0), 0.0)
    rng = np.random.default_rng(70070)
    pr_g = np.zeros(fp.shape)
    pr_g[allowed_prod] = rng.random(int(allowed_prod.sum()))
    prank = np.where(channel & ~exclude & np.isfinite(ksn), ksn, np.nan)
    rrr = rankdata(np.where(np.isfinite(prank), prank, 0.0).ravel()).reshape(prank.shape) / prank.size
    preds = dict(
        lane=L.top_k_dots(res_prod.p, allowed_prod, a.budget, min_sep_px=MIN_SEP_PX).astype(np.float32),
        crest_only_no_pairing=L.top_k_dots(res_prod_crest.p, allowed_prod, a.budget,
                                           min_sep_px=MIN_SEP_PX).astype(np.float32),
        ksn_only_no_alignment=L.top_k_dots(np.where(np.isfinite(prank), rrr, 0.0),
                                           allowed_prod, a.budget),
        distance_only=L.top_k_dots(p_dist_g, allowed_prod, a.budget),
        random_mass_control=L.top_k_dots(pr_g, allowed_prod, a.budget),
    )
    if champ is not None:
        preds["champion_02778_owner_report"] = champ
    for k, v in preds.items():
        mark(f"instrument arm {k:32s} dots={int((v > 0).sum()):,} on_catalogue={int(((v > 0) & cat).sum())}")
    truths = {"sgmc_off_full": offcat,
              "sgmc_off_thin8000": I.thin_random(offcat, 8000, seed=61),
              "catalogue_full": I.catalogue_truth(cat, fp)}
    instr = {}
    for tname, tmask in truths.items():
        per_arm = {k: I.global_dti(v, tmask, fp, cat) for k, v in preds.items()}
        boot = paired_block_bootstrap(preds, tmask, fp, cat, reference="lane")
        instr[tname] = dict(n_truth=int(tmask.sum()), per_arm=per_arm, bootstrap=boot)
        mark(f"truth {tname:20s} n={int(tmask.sum()):>7,} " +
             " ".join(f"{k}={per_arm[k]['dti']:.5f}" for k in per_arm))

    production_dots = preds["lane"]
    out = dict(evidence_class="HOLDOUT-DTI (bench) + INSTRUMENT-DTI (public proxy truths; "
                              "NOT ORGANIZER-CONFIRMED)",
               evaluator_version=EH.VERSION,
               implementation_sha256=EH.implementation_hashes(),
               generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               preregistration="registry/preregistration-h70.json",
               statistic="pair_strength", density=RL.DENSITY, budgets=budgets,
               cells=len(cells),
               e1a_first_test=e1a, e1a_crest_ablation=e1a_crest, e1b_off_catalogue=e1b,
               confounds=conf, candidates=cand_diag, crest_candidates=crest_diag,
               pooled_binary=pooled,
               production_surface_diagnostics=res_prod.diagnostics,
               canary=list(can.values()),
               canary_rule="max(AUC,1-AUC) > 0.90 is leakage until proven otherwise",
               instrument_evidence_class="INSTRUMENT-DTI (public proxy truth; not a leaderboard score)",
               instrument=instr,
               production_dots=int((production_dots > 0).sum()),
               log=log)
    (EVID / f"{TAG}_holdout.json").write_text(json.dumps(_clean(out), indent=2,
                                                          allow_nan=False) + "\n")
    np.save(ROOT / ".cache" / "features70" / "production_dots.npy", production_dots > 0)
    mark(f"wrote evidence/{TAG}_holdout.json and cached production dots (budget {a.budget})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
