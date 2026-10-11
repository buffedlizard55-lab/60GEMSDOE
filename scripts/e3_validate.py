"""E3 - pooled hide-and-recover evaluation, uniqueness gates, writer, run card.

Protocol (shared template, vendored verbatim): whole-segment hide folds,
prevalence-matched to the organiser-bracketed |G| band, visible catalogue
masked pixel-exactly (staff forum 11516), official DTI (alpha .2, beta .8,
300 m triangular kernel), paired physical 20 km-block bootstrap CI.

Arms
  lane7653     this session's knickpoint raster (7,653 dots, capacity-limited)
  canary_anom  raw steepness-anomaly field, same budget, no concordance/masks
               (one composite-field canary only; it is not a feature-by-feature audit)
  champion  h33-2-b2 -zeros (legacy owner-reported 0.2778; no receipt ties score to these bytes)
  d28        dotted h19-5 d=2.8 -zeros (legacy score claim; not a current live-score source)
  h274r1       h27-4-r1-solo d2.8 -nan (legacy owner score claim 0.2708; not receipt-linked)
  h16topo      h16-1 topo-geophys ridges -nan (legacy owner score claim 0.1855; not receipt-linked)

Partial uniqueness diagnostic: compare the continuous score surface to locally available registry
rasters before placement (absolute Spearman <= 0.90), then compare final emitted dots after placement
(<= 70% of our dots within 3 px). This directory's contents must not be presented as the full global
registry unless coverage is audited.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems52 import metric as M  # noqa: E402
from gems52 import holdout as HO  # noqa: E402
from gems52 import evaluate_holdout as EH  # noqa: E402
from e1_lane_test import load_inputs  # noqa: E402

WORK = ROOT / "data" / "work"
EVID = ROOT / "evidence"
# BUGFIX 2026-10-11: this pointed at a private sandbox path (/home/user/registry_rasters) that no
# fresh clone has, so the shared evaluator vendor could not be re-run outside the session that
# created it.  It now reads the in-repo registry (the same bytes; champion/d28 aliases verified
# sha256-identical to docs/downloads) plus the restored scored/ anchor.  Reported once, per the
# protocol's "fix shared tools in the template, never fork privately".
REG = ROOT / "registry" / "rasters"
SEED = 20261011
BLOCK_SIDE = 200          # px -> 20 km spatial bootstrap clusters
BUDGET = 7653

ANCHORS = {
    "champion": REG / "dotted_b2_prune_02778.tif",
    "d28": REG / "dotted_d2_8_02600.tif",
    "h274r1": REG / "dotted_d2_8_02708.tif",
    "h16topo": ROOT / "data" / "scored" / "gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif",
}


def read_anchor(path):
    import rasterio
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
    return np.nan_to_num(a, nan=0.0)


def spearman(a, b, valid):
    from scipy.stats import spearmanr
    x, y = a[valid].astype(np.float64), b[valid].astype(np.float64)
    return float(spearmanr(x, y).statistic)


def dot_overlap(ours, theirs, valid, r=3):
    o = (ours > 0) & valid
    t = (theirs > 0) & valid
    if not o.any() or not t.any():
        return dict(ours_within=float("nan"), theirs_within=float("nan"),
                    n_ours=int(o.sum()), n_theirs=int(t.sum()))
    t_dil = ndimage.binary_dilation(t, iterations=r)
    o_dil = ndimage.binary_dilation(o, iterations=r)
    return dict(
        ours_within=float((o & t_dil).sum() / o.sum()),
        theirs_within=float((t & o_dil).sum() / t.sum()),
        n_ours=int(o.sum()), n_theirs=int(t.sum()))


def main():
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "E3 pooled evaluator / submission writer"):
        return 0
    import rasterio

    det, slope_band, cat, valid = load_inputs()
    lane = np.load(WORK / "lane_emission.npy")
    field = np.load(WORK / "lane_field.npy")
    anom = np.load(WORK / "channel_stack_cache.npz", allow_pickle=False)["anomaly"] \
        if (WORK / "channel_stack_cache.npz").exists() else None
    if anom is None:
        from e1_lane_test import get_channel_stack
        anom = get_channel_stack(det, valid)["anomaly"]
        np.savez_compressed(WORK / "channel_stack_cache.npz", anomaly=anom)

    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                          seed=SEED, mode="hide")
    print("folds:", [(f["fold"], f["n_truth"]) for f in folds])

    terms_by_arm = {}
    per_fold = {}
    for arm, grid in [("lane7653", lane.astype(np.float32)),
                      ("canary_anom", None)]:
        for f in folds:
            if grid is None:   # canary: raw anomaly, re-emitted per fold's visible mask
                allowed = valid & ~f["visible"] & f["region"]
                em = HO.emit_topk(np.where(allowed, anom, 0.0).astype(np.float32),
                                  allowed, BUDGET)
            else:
                em = grid
            res, terms = EH.evaluate(em, f, valid, block_side=BLOCK_SIDE)
            terms_by_arm.setdefault(arm, []).append(terms)
            per_fold.setdefault(arm, []).append(
                dict(fold=f["fold"], dti=res["dti"], tpw=res["tpw"], fpw=res["fpw"],
                     n_truth=res["n_truth"], emitted=res.get("emitted")))
    for name, path in ANCHORS.items():
        g = read_anchor(path)
        for f in folds:
            res, terms = EH.evaluate(g, f, valid, block_side=BLOCK_SIDE)
            terms_by_arm.setdefault(name, []).append(terms)
            per_fold.setdefault(name, []).append(
                dict(fold=f["fold"], dti=res["dti"], tpw=res["tpw"], fpw=res["fpw"],
                     n_truth=res["n_truth"], emitted=res.get("emitted")))

    terms_by_arm = {k: np.concatenate(v, axis=0) for k, v in terms_by_arm.items()}
    pooled = EH.pooled_summary(terms_by_arm, draws=2000, seed=SEED, candidate="lane7653")

    # Composite-field ROC-AUC on held truth vs non-truth footprint cells. This one diagnostic
    # does not replace the required feature-by-feature leakage audit.
    truth_px = np.zeros_like(valid)
    for f in folds:
        truth_px |= f["truth"] & f["region"]
    tv = field[truth_px & valid]
    nv = field[valid & ~truth_px]
    from sklearn.metrics import roc_auc_score
    lab = np.r_[np.ones(tv.size, dtype=np.uint8), np.zeros(nv.size, dtype=np.uint8)]
    val = np.r_[tv, nv]
    auc = float(roc_auc_score(lab, val))

    # Pre-placement continuous score-surface correlation and post-placement dot overlap.
    # The in-repo rasters are only the locally available comparison set, not proof of global coverage.
    registry = {}
    for p in sorted(REG.glob("*.tif")):
        try:
            registry[p.name] = read_anchor(p)
        except Exception as e:
            print("skip", p.name, e)
    uniq = {}
    for name, g in registry.items():
        uniq[name] = dict(
            surface_spearman=spearman(field, g, valid),
            overlap=dot_overlap(lane, g, valid, r=3))

    # write the artifact through the fail-closed shared writer
    from gems52 import submission_writer as SW
    sample_path = ROOT / "data" / "bridge" / "example_submission.tif"
    stamp = "20261011T000000Z"
    name_tif = f"gems60-knickpoint-lane-c{BUDGET}-{stamp}"
    out_dir = ROOT / "docs" / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    sub_name = f"gems60-lane-knickpoint-c{BUDGET}-{stamp}"
    note = ("tectono-geomorphic chi/ksn knickpoint lane; 7653 concordant channel dots; "
            "E1 negative AUC 0.224; RESEARCH-ONLY, not promoted")
    receipt = SW.write_submission(
        out_dir / f"{name_tif}.tif", lane.astype(np.float32), sample_path, valid,
        note=note[:140], name=sub_name[:140],
        metadata=dict(lane="tectono-geomorphology", dots=int((lane > 0).sum()),
                      e1_auc_placement_null=0.224, e1_verdict="NEGATIVE-STOP"))

    # verdict
    lane_dti = pooled["scores"]["lane7653"]["dti"]
    best_ctrl = pooled["best_comparable_control"]
    best_dti = pooled["scores"][best_ctrl]["dti"] if best_ctrl else float("nan")
    promoted = bool(lane_dti > best_dti)
    verdict = "PROMOTE" if promoted else "NEGATIVE (do not spend a slot; research-only)"

    local_uniqueness_pass = bool(uniq) and all(
        abs(u["surface_spearman"]) <= 0.90
        and u["overlap"]["ours_within"] <= 0.70
        for u in uniq.values())
    # registry/rasters is a partial local cache; no audited inventory proves global coverage.
    registry_coverage_audited = False
    uniq_ok = local_uniqueness_pass and registry_coverage_audited

    card = dict(
        hypothesis="Withheld normal-fault segments carry localized channel-steepness "
                   "(knickpoint/ksn) signals on drainages crossing the trace "
                   "(Kirby & Whipple 2012; Perron & Royden 2013).",
        mechanism="Priority-Flood fill -> D8 accumulation -> chi/ksn on official 100 m "
                  "det_elev; DoG log-ksn steepness-step anomaly; multi-drainage "
                  "concordance; playa/flat/lithology masks; 2px catalogue ring; "
                  "3px NMS dots.",
        named_confound="Range-front alluvial cover: traces crossing piedmonts have no "
                       "bedrock channels; straight orientation-matched nulls cut more "
                       "steep headwater terrain and out-score real traces (E1b).",
        holdout=pooled["scores"]["lane7653"],
        holdout_all_arms=pooled["scores"],
        paired_differences=pooled["paired_differences"],
        canary=dict(field_auc_vs_held_truth=auc,
                    feature_by_feature_results_present=False,
                    full_leakage_clearance=False,
                    note="Composite-field canary only; this does not replace the required feature-by-feature leakage audit."),
        uniqueness=uniq,
        uniqueness_gate_pass=uniq_ok,
        uniqueness_scope=dict(
            compared_registry_rasters=len(uniq),
            pre_placement_surface_check_documented=True,
            final_dot_check_documented=True,
            local_gate_pass=local_uniqueness_pass,
            registry_coverage_audited=registry_coverage_audited,
            full_registry_clearance=uniq_ok,
            local_gate_status="PASS among listed rasters only" if local_uniqueness_pass else "FAIL among listed rasters",
        ),
        validator=receipt["validator"],
        sha256=receipt["sha256"],
        submission_name=receipt["submission_name"],
        note=receipt["note"],
        verdict=verdict,
        evidence_class="HOLDOUT-DTI",
        evaluator_version=EH.VERSION,
        seed=SEED,
    )
    (EVID / "runcard.json").write_text(json.dumps(card, indent=2) + "\n")
    (EVID / "e3_pooled_eval.json").write_text(json.dumps(
        dict(pooled=pooled, per_fold=per_fold), indent=2) + "\n")
    print(json.dumps(dict(lane_dti=lane_dti, best_control=best_ctrl,
                          best_dti=best_dti, canary_auc=auc,
                          uniqueness_pass=uniq_ok, verdict=verdict,
                          sha256=receipt["sha256"]), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
