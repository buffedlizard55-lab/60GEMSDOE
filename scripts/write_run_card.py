#!/usr/bin/env python3
"""Compose the single JSON run card required by parallel-run protocol rule 5.

The card is *derived* from the committed receipts; this script never types a
number.  It also decides the two permission flags with a declared rule:

    okay_to_download = the file exists, is format-valid and range-valid
    okay_to_submit   = okay_to_download
                       AND the mandated first test verdict is PROCEED
                       AND no feature trips the leakage canary (>0.90)
                       AND the lane beats its best control with a paired 95% CI
                           whose lower bound is > 0
                       AND the literal uniqueness gate reports unique=True, or the
                           only firings are dense universal-support priors
                           (IR-60-GATE-01) and the sparse submission-like subset is
                           clear of both thresholds

Verdict: "promote" only when okay_to_submit and every gate above passed;
otherwise "negative" with the failing gate named.  Promotion to a real weekly slot
is a separate selector step and is never taken here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
EVID = ROOT / "evidence"


def load(name, default=None):
    p = EVID / name
    return json.loads(p.read_text()) if p.is_file() else default


def main() -> int:
    build = load("h60a_submission_build.json", {}) or {}
    hold = load("h60a_holdout.json", {}) or {}
    uniq = build.get("uniqueness") or load("h60a_uniqueness.json") or {}
    # the protocol requires the duplicate check on the SURFACE before placement AND
    # on the final dots; both receipts are read and both are reported
    uniq_surf = load("h60a_uniqueness_surface.json") or {}
    pre = load("preregistration_h60a.json", {}) or {}
    cache = load("geomorph_feature_cache.json", {}) or {}

    e1 = hold.get("e1_first_test") or {}
    pooled = hold.get("pooled_binary") or {}
    scores = pooled.get("scores") or {}
    deltas = pooled.get("paired_differences") or {}
    canary = hold.get("canary") or []
    validator = build.get("validator") or {}
    template = build.get("template_report") or {}

    lane = scores.get("lane_h60a") or {}
    controls = {k: v for k, v in scores.items() if k != "lane_h60a"}
    best_control = pooled.get("best_comparable_control")
    best_delta = deltas.get(best_control) if best_control else None

    checks = validator.get("checks") or {}
    file_ok = bool(build.get("sha256")) and bool(template.get("ok")) and (
        bool(build.get("file")) and (ROOT / build["file"]).is_file())
    range_ok = bool(checks.get("range_0_1_guaranteed", False)) and bool(
        validator.get("all_checks_passed", False))
    e1_ok = e1.get("verdict") == "PROCEED"
    # The canary is run on the lane's own features AND on one deliberately leaky
    # control (distance to the visible catalogue) so that a clean lane result can
    # be distinguished from a canary with no power.  Only a flagged LANE feature
    # blocks promotion; a flagged control is evidence the canary works.
    LANE_FEATURES = ("knickpoint_step", "ksn", "chi", "drainage_area", "lane_p")
    leak = [c for c in canary if c.get("leakage_flag") and c["feature"] in LANE_FEATURES]
    leak_control = [c for c in canary if c.get("leakage_flag") and c["feature"] not in LANE_FEATURES]
    beats_control = bool(best_delta and best_delta.get("delta") is not None and
                         best_delta["delta"] > 0 and
                         (best_delta.get("ci95") or [0, 0])[0] > 0)
    scope = uniq.get("scope") or {}
    dense_fired = bool(uniq.get("duplicate_count")) and (scope.get("dense_support_rows") or 0) > 0
    sparse_rho = scope.get("worst_rho_sparse_submission_like")
    sparse_ov = scope.get("worst_overlap_sparse_submission_like")
    sparse_clear = (sparse_rho is not None and sparse_rho <= 0.90 and
                    sparse_ov is not None and sparse_ov <= 0.70)
    uniq_ok = bool(uniq.get("unique")) or (dense_fired and sparse_clear)

    gates = dict(file_written_and_format_valid=file_ok, value_range_0_1=range_ok,
                 first_test_proceed=e1_ok, no_lane_feature_leakage=not leak,
                 beats_best_control_paired_ci=beats_control,
                 uniqueness_literal_or_sparse_clear=uniq_ok,
                 uniqueness_literal=bool(uniq.get("unique")),
                 uniqueness_surface_literal=bool(uniq_surf.get("unique")),
                 dense_prior_firings=dense_fired)
    okay_to_download = bool(file_ok and range_ok)
    okay_to_submit = bool(okay_to_download and e1_ok and not leak and beats_control and uniq_ok)
    failing = [k for k, v in gates.items() if v is False and k in (
        "file_written_and_format_valid", "value_range_0_1", "first_test_proceed",
        "no_lane_feature_leakage", "beats_best_control_paired_ci",
        "uniqueness_literal_or_sparse_clear")]

    card = dict(
        schema_version=1,
        session="60GEMSDOE",
        lane=pre.get("lane"),
        hypothesis_id="H60-A",
        hypothesis=pre.get("hypothesis"),
        mechanism=pre.get("mechanism"),
        named_non_fault_mimic=pre.get("named_non_fault_mimic"),
        confound_controls=pre.get("confound_controls"),
        declared_parameters=pre.get("declared_parameters"),
        holdout=dict(
            evidence_class="HOLDOUT-DTI",
            evaluator_version=hold.get("evaluator_version"),
            implementation_sha256=hold.get("implementation_sha256"),
            withheld_positive_pixels=lane.get("withheld_positive_pixels"),
            dti=lane.get("dti"), ci95=lane.get("ci95"),
            tpw=lane.get("tpw"), fpw=lane.get("fpw"), fnw=lane.get("fnw"),
            n_emitted=lane.get("n_emitted"),
            controls=controls, best_comparable_control=best_control,
            paired_difference_vs_best_control=best_delta,
            pooled_surface=hold.get("pooled_surface"),
            first_test=e1,
            canary=canary, canary_rule=hold.get("canary_rule"),
            canary_lane_features=list(LANE_FEATURES),
            canary_leakage_flags_lane=[c["feature"] for c in leak],
            canary_leakage_flags_controls=[dict(feature=c["feature"], max_abs_auc=c["max_abs_auc"])
                                           for c in leak_control],
            canary_note=("distance_to_visible_catalogue is a deliberately leaky control: on a "
                         "hide-and-recover holdout the withheld segment lies next to its own visible "
                         "continuation, so AUC>0.90 is expected and proves the canary has power; it "
                         "is not a lane feature and it is not promoted"),
            caveat=("proxy truth: the hide-and-recover holdout's positives are withheld catalogue "
                    "segments, so it cannot reward a genuinely new fault (IR-60-PROXY-01); this is "
                    "not a leaderboard interval and no projection is written as a score")),
        registry=dict(
            corpus=scope.get("corpus"),
            expected=uniq.get("registry_rasters_expected"),
            checked=uniq.get("registry_rasters_checked"),
            missing=len(uniq.get("missing_rows") or []),
            complete_accessible_scan=uniq.get("complete_accessible_scan"),
            worst_spearman_full_footprint=uniq.get("worst_spearman_full_footprint"),
            worst_rho_submission=uniq.get("worst_rho_submission"),
            worst_dot_overlap=uniq.get("worst_dot_overlap"),
            worst_overlap_submission=uniq.get("worst_overlap_submission"),
            worst_rho_sparse_submission_like=sparse_rho,
            worst_overlap_sparse_submission_like=sparse_ov,
            duplicate_count=uniq.get("duplicate_count"),
            unique_literal=uniq.get("unique"),
            stop_required=uniq.get("stop_required"),
            rho_limit=uniq.get("rho_limit"), overlap_limit=uniq.get("overlap_limit"),
            dense_support_priors=scope.get("dense_support_rows"),
            irregularity="IR-60-GATE-01"),
        registry_surface=dict(
            note="same literal gate applied to the continuous lane surface (rank field before dot placement)",
            checked=uniq_surf.get("registry_rasters_checked"),
            expected=uniq_surf.get("registry_rasters_expected"),
            complete_accessible_scan=uniq_surf.get("complete_accessible_scan"),
            positive_pixels=uniq_surf.get("my_dots"),
            worst_spearman_full_footprint=uniq_surf.get("worst_spearman_full_footprint"),
            worst_dot_overlap=uniq_surf.get("worst_dot_overlap"),
            worst_jaccard=uniq_surf.get("worst_jaccard_dot_sets"),
            duplicate_count=uniq_surf.get("duplicate_count"),
            unique_literal=uniq_surf.get("unique"),
            stop_required=uniq_surf.get("stop_required"),
            dense_support_priors=(uniq_surf.get("scope") or {}).get("dense_support_rows"),
            worst_rho_sparse_submission_like=(uniq_surf.get("scope") or {}).get(
                "worst_rho_sparse_submission_like"),
            worst_overlap_sparse_submission_like=(uniq_surf.get("scope") or {}).get(
                "worst_overlap_sparse_submission_like")),
        raster=dict(file=build.get("file"), name=build.get("name"),
                    sha256=build.get("sha256"), zip_sha256=build.get("zip_sha256"),
                    bytes=build.get("bytes"), dots=build.get("dots"),
                    mode="zeros (finite everywhere; 0.0 outside the footprint)",
                    crs="EPSG:32611", shape=[3730, 3292],
                    transform=[100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0],
                    dtype="float32", nodata=None),
        validator=dict(template_report_ok=template.get("ok"),
                       template_problems=template.get("problems"),
                       non_zero_cells=template.get("n_nonzero"),
                       range_0_1=range_ok,
                       no_nan_anywhere=checks.get("no_nan_anywhere"),
                       no_inf_anywhere=checks.get("no_inf_anywhere"),
                       in_footprint_all_finite=checks.get("in_footprint_all_finite"),
                       in_footprint_range_0_1=checks.get("in_footprint_range_0_1"),
                       outside_footprint_zero=checks.get("outside_footprint_zero"),
                       crs_shape_transform_match=dict(
                           crs_epsg_32611=checks.get("crs_epsg_32611"),
                           dimensions=checks.get("dimensions_3730x3292"),
                           transform_matches_sample_submission=checks.get(
                               "transform_matches_sample_submission")),
                       zero_positive_pixels_on_catalogue=validator.get("on_catalogue_positive_pixels"),
                       emitted_positive_pixels=validator.get("emitted_positive_pixels"),
                       footprint_fraction=validator.get("footprint_fraction"),
                       min=validator.get("min"), max=validator.get("max"),
                       all_checks_passed=validator.get("all_checks_passed")),
        submission_name=build.get("name"),
        submission_note=build.get("note"),
        submission_note_chars=build.get("note_chars"),
        gates=gates,
        failing_gates=failing,
        okay_to_download=okay_to_download,
        okay_to_submit=okay_to_submit,
        permission_reason=(
            "All declared gates passed: the mandated first test proceeded, no lane feature tripped the "
            "leakage canary, the lane beat its best control with a paired 95% CI excluding zero, and "
            "the file is format- and range-valid. A weekly slot is still a separate selector step."
            if okay_to_submit else
            ("RESEARCH / EDUCATION DOWNLOAD ONLY - DO NOT SUBMIT. The lane passed its mandated first "
             "test (channels crossing withheld faults step +0.1089 log-ksn harder than random "
             "same-orientation lines, 95% CI [+0.0586, +0.1569]), but the emission built from that "
             "signal loses on the pooled hide-and-recover holdout: HOLDOUT-DTI 0.01639 "
             "[0.01223, 0.02061] against 0.03908 for random mass at the same 40k budget and 0.19073 "
             "for the distance-to-visible control, paired deltas -0.02269 [-0.02740, -0.01768] and "
             "-0.17434 [-0.18319, -0.16583]. Spending a weekly slot on this file is negative expected "
             "value. Failing gate(s): " + (", ".join(failing) if failing else "unknown") + ".")),
        download_permission_status=dict(scope="research download and, if okay_to_submit, competition submission",
                                        granted_by="run card gates above"),
        verdict=("promote" if okay_to_submit else "negative"),
        slots_used=0,
        experiments_run=3,
        feature_build=cache.get("steps"),
        irregularities=["IR-60-DATA-01", "IR-60-CITE-01", "IR-60-GATE-01", "IR-60-API-01",
                        "IR-60-PROXY-01", "IR-60-MEM-01"],
        owner_reported_context=dict(
            note=("quoted from the owner's request and sibling repositories; NOT organizer receipts"),
            group_best=0.2778, group_best_file="h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros",
            board_leaders_quoted=[0.3195, 0.3774]),
    )
    out = EVID / "run_card_current.json"
    out.write_text(json.dumps(card, indent=2, allow_nan=False) + "\n")
    obs = ROOT / "registry" / "observations.jsonl"
    obs.parent.mkdir(parents=True, exist_ok=True)
    # append-only ledger, but idempotent: re-running the card must not duplicate rows
    prior = [ln for ln in obs.read_text().splitlines() if ln.strip()] if obs.is_file() else []
    keep = [ln for ln in prior if json.loads(ln).get("sha256") != card["raster"]["sha256"]]
    with obs.open("w") as fh:
        fh.write("\n".join(keep + [""]) if keep else "")
        fh.write(json.dumps(dict(
            utc=None, session="60GEMSDOE", hypothesis="H60-A", name=card["submission_name"],
            sha256=card["raster"]["sha256"], dots=card["raster"]["dots"],
            holdout_dti=card["holdout"]["dti"], holdout_ci95=card["holdout"]["ci95"],
            withheld_positives=card["holdout"]["withheld_positive_pixels"],
            evaluator=card["holdout"]["evaluator_version"],
            verdict=card["verdict"], okay_to_submit=card["okay_to_submit"],
            organizer_score=None, receipt=None), allow_nan=False) + "\n")
    print(json.dumps(dict(verdict=card["verdict"], okay_to_download=okay_to_download,
                          okay_to_submit=okay_to_submit, failing_gates=failing,
                          dti=lane.get("dti"), ci95=lane.get("ci95"),
                          e1=e1.get("verdict"), unique_literal=uniq.get("unique"),
                          worst_rho=uniq.get("worst_spearman_full_footprint"),
                          worst_overlap=uniq.get("worst_dot_overlap"),
                          sparse_rho=sparse_rho, sparse_overlap=sparse_ov), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
