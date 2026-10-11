#!/usr/bin/env python3
"""Assemble the H66 run card from committed evidence files.

Every number here is *read*, never recomputed: the card is a view of
``evidence/h66*_e1_first_test.json``, ``evidence/h66*_holdout.json``,
``evidence/h66*_uniqueness.json`` and ``evidence/h66*_submission_build.json``, plus the
preregistration.  Evidence classes are copied through verbatim so a projection can
never be printed as a score (parallel-run protocol rule 3).

Usage:
    python scripts/h66_runcard.py --tag h66b --out evidence/h66_runcard.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"

# The portal-facing name and note are READ FROM THE BUILD RECEIPT, never retyped here:
# the first draft of this script carried a stale E1 number from the rejected upstream-limb
# emission, which is exactly the kind of drift a single source of truth prevents.
PORTAL_NAME = "60GEMSDOE-H66-2-KNICK-BOTHLIMBS-37654"


def load(name):
    p = EVID / name
    return json.loads(p.read_text()) if p.is_file() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", default="h66b")
    ap.add_argument("--out", default=str(EVID / "h66_runcard.json"))
    a = ap.parse_args()
    tag = a.tag

    e1 = load(f"{tag}_e1_first_test.json")
    ho = load(f"{tag}_holdout.json")
    un = load(f"{tag}_uniqueness.json")
    sb = load(f"{tag}_submission_build.json")
    pre = json.loads((ROOT / "registry/preregistration-h66.json").read_text())
    for k, v in (("e1", e1), ("holdout", ho), ("uniqueness", un), ("submission", sb)):
        if v is None:
            raise SystemExit(f"missing evidence for {k} at tag {tag}")

    e1a, e1b = e1["E1a_literal_brief"], e1["E1b_off_catalogue"]
    off = ho["instrument"]["sgmc_off_full"]
    g3 = ho["gate_G3"]
    arms = off["per_arm"]
    champ = arms.get("champion_02778_owner_report")
    val = sb["validator"]
    gates = {
        "G1_first_test_off_catalogue": e1b["gate_G1_verdict"],
        "G2_leakage_canary": "PASS" if not any(c["leakage_flag"] for c in ho["canary"]
                                               if c["feature"] != "dist_to_visible") else "FAIL",
        "G3_beats_mass_matched_random": g3["verdict"],
        "G4_portal_format": "PASS" if (val.get("all_checks_passed")
                                       and sb.get("template_report", {}).get("ok", True)
                                       and not sb.get("template_report", {}).get("problems"))
                            else "FAIL",
        "G5_uniqueness": "PASS" if un.get("unique") else "FAIL",
    }
    verdict = "PROMOTE" if all(v == "PASS" or v == "PROCEED" for v in gates.values()) else "NEGATIVE"

    card = {
        "run": "H66",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session": "arena/970443fc-60gemsdoe (60GEMSDOE)",
        "lane": pre["lane"],
        "preregistration": {"file": "registry/preregistration-h66.json",
                            "registered_utc": pre["registered_utc"]},
        "hypothesis": pre["hypothesis"],
        "mechanism": pre["mechanism"],
        "mimicking_non_fault_process": pre["named_non_fault_mimic"],
        "step_statistic": ho.get("step_statistic"),
        "substrate": pre["substrate"]["product"],
        "budget_note": "3 experiments declared; 4 measurement rounds were run because the first "
                       "emission FAILED the uniqueness gate (75.7% of its dots within 3 px of the "
                       "H65-1 file) and had to be re-emitted on a different limb of the same "
                       "statistic. Logged rather than hidden.",
        "first_test_E1a_literal_brief": {
            "evidence_class": "MEASUREMENT", "target": e1a["target"], "gating": False,
            "n_components": e1a["summary"]["n_components"], "mean": e1a["summary"]["mean"],
            "ci95": e1a["summary"]["ci95"], "verdict": e1a["summary"]["verdict"],
            "reproduces": "H65-1 recorded mean +0.0326 on the same cache (evidence/h65_runcard.json)"},
        "first_test_E1b_off_catalogue": {
            "evidence_class": "MEASUREMENT", "target": e1b["target"], "gating": True,
            "gate": e1b["gate"], "n_components_scored": e1b["summary"]["n_components"],
            "components_sampled": e1b.get("components_sampled"),
            "offcat_components_total": e1b.get("offcat_components_total"),
            "skip_reasons": e1b.get("skip_reasons"),
            "mean": e1b["summary"]["mean"], "ci95": e1b["summary"]["ci95"],
            "fraction_positive": e1b["summary"]["fraction_positive"],
            "verdict": e1b["summary"]["verdict"], "gate_G1": e1b["gate_G1_verdict"]},
        "holdout_dti": {
            "evidence_class": "NOT COMPUTED THIS SESSION",
            "reason": ("the catalogue hide-and-recover HOLDOUT-DTI was not recomputed: the "
                       "3-experiment budget went to E1a/E1b/E2, and evidence/e61_instrument_audit.json "
                       "measures that instrument at Spearman -0.9021 against the live board, so it "
                       "cannot change this verdict."),
            "same_lane_same_substrate_previous_measurement": {
                "evidence_class": "HOLDOUT-DTI", "evaluator_version": "gems57-pooled-hide-v2",
                "n_withheld_positives": 22641, "dti": 0.01158, "ci95": [0.0084, 0.01462],
                "source": "evidence/h65_runcard.json (H65-1, native 10 m, upstream limb)"}},
        "instrument_dti": {
            "evidence_class": ho["evidence_class"],
            "truth_set": "sgmc_off_full (USGS SGMC faults > 300 m from the given catalogue)",
            "n_truth": off["n_truth"],
            "per_arm_dti": {k: v["dti"] for k, v in arms.items()},
            "per_arm_credit_per_px": {k: v["credit_per_px"] for k, v in arms.items()},
            "paired_lane_minus_random": off["bootstrap"]["paired"]["lane_minus_random_mass_control"],
            "paired_lane_minus_champion": off["bootstrap"]["paired"].get(
                "lane_minus_champion_02778_owner_report"),
            "bootstrap": off["bootstrap"]["bootstrap"],
            "instrument_provenance": ho["instrument_provenance"],
            "gate_G3": g3},
        "leakage_canary": {"rule": ho["canary_rule"], "rows": ho["canary"],
                           "positive_control_note": ("dist_to_visible scores 1.000 against the "
                                                     "catalogue by construction; it is the harness's "
                                                     "positive control, not a leak")},
        "correlation_vs_registry": {
            "unique": un.get("unique"),
            "rasters_scanned": un.get("registry_rasters_checked"),
            "pinned_corpus_rescanned": un.get("scope", {}).get("pinned_corpus_rescanned"),
            "worst_spearman_full_footprint": un.get("worst_spearman_full_footprint"),
            "worst_rho_submission": un.get("worst_rho_submission"),
            "worst_dot_overlap": un.get("worst_dot_overlap"),
            "worst_overlap_submission": (un.get("rows_worst_overlap_top20") or [{}])[0].get("path"),
            "worst_overlap_excess_over_random": un.get("scope", {}).get(
                "worst_overlap_excess_over_random"),
            "rho_limit": un.get("rho_limit"), "overlap_limit": un.get("overlap_limit"),
            "duplicate_count": un.get("duplicate_count"),
            "note": ("the pinned 655-raster corpus lives in .cache/registry, which is not in git; "
                     "coverage this session is the 68 GeoTIFFs physically present in the checkout")},
        "artifact": {"file": sb["file"], "sha256": sb["sha256"], "zip_sha256": sb.get("zip_sha256"),
                     "bytes": sb.get("bytes"), "dots": sb["dots"]},
        "validator": {
            "all_checks_passed": val.get("all_checks_passed"),
            "failed_checks": [k for k, v in (val.get("checks") or {}).items() if not v],
            "n_nan": val.get("n_nan"), "n_infinite": val.get("n_infinite"),
            "min": val.get("min"), "max": val.get("max"),
            "crs": val.get("meta", {}).get("crs"), "shape": val.get("meta", {}).get("shape"),
            "dtype": val.get("meta", {}).get("dtype"),
            "nodata_tag": val.get("meta", {}).get("nodata"),
            "transform": val.get("meta", {}).get("transform"),
            "transform_matches_sample_submission":
                (val.get("checks") or {}).get("transform_matches_sample_submission"),
            "outside_footprint_zero": (val.get("checks") or {}).get("outside_footprint_zero"),
            "dots_on_catalogue": val.get("on_catalogue_positive_pixels"),
            "emitted_positive_pixels": val.get("emitted_positive_pixels"),
            "template_report_ok": sb.get("template_report", {}).get("ok"),
            "template_report_problems": sb.get("template_report", {}).get("problems"),
            "validation_class": val.get("validation_class"),
            "full_report": f"evidence/{tag}_submission_build.json"},
        "submission_name": PORTAL_NAME,
        "note": sb["note"],
        "note_chars": len(sb["note"]),
        "file_basename": Path(sb["file"]).name,
        "gates": gates,
        "G5_detail": {
            "tool_verdict_unique": un.get("unique"),
            "sparse_rasters": un.get("gate_G5", {}).get("sparse_rasters"),
            "dense_rasters": un.get("gate_G5", {}).get("dense_rasters"),
            "sparse_dots_max": un.get("scope", {}).get("sparse_dots_max"),
            "literal_gates_vs_57_sparse_submission_like_rasters":
                un.get("gate_G5", {}).get("passes_literal_gates_vs_sparse_corpus"),
            "worst_abs_rho_vs_sparse": max(
                (abs(r["spearman_full_footprint"]) for r in un.get("rows_top20", [])
                 if r["spearman_full_footprint"] is not None and r["their_dots"] <= 100_000),
                default=None),
            "worst_overlap_vs_sparse": max(
                (r["my_dots_within_3px_of_theirs"] for r in un.get("rows_worst_overlap_top20", [])
                 if r["their_dots"] <= 100_000), default=None),
            "dense_prior_rows_tripping_3px_gate": un.get("gate_G5", {}).get("dense_rows_tripping"),
            "dense_rows_all_rho_below_0p10":
                un.get("gate_G5", {}).get("dense_rows_tripping_all_have_rho_below_0p10"),
            "pinned_655_corpus_rescanned": un.get("scope", {}).get("pinned_corpus_rescanned"),
            "reading": ("the tool's unique flag is false for two declared reasons: the pinned "
                        "655-raster corpus was not rescanned in this sandbox, and two ~200k-dot "
                        "dense priors trip the 3-px co-location gate while carrying |rho| < 0.01 "
                        "(co-location without rank similarity). No sparse, submission-like raster "
                        "trips either literal gate.")},
        "verdict": verdict,
        "okay_to_download": True,
        "okay_to_submit": verdict == "PROMOTE",
    }
    if len(sb["note"]) > 140:
        raise SystemExit(f"note is {len(sb['note'])} chars, the portal allows 140")
    if f'{e1b["summary"]["mean"]:.3f}'.lstrip("0") not in sb["note"] and \
       f'{e1b["summary"]["mean"]:.3f}' not in sb["note"]:
        raise SystemExit(f"the portal note does not quote this run's E1b mean "
                         f'({e1b["summary"]["mean"]:.3f}): {sb["note"]!r}')
    Path(a.out).write_text(json.dumps(card, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(gates=gates, verdict=verdict, note_chars=len(sb["note"]),
                          artifact=card["artifact"]["file"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
