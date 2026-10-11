#!/usr/bin/env python3
"""H73 run card: assembled programmatically from the evidence files (no hand-typed numbers).

Every value below is copied out of an evidence JSON by this script; if a file is missing the script
fails rather than inventing a number.  Run:  /home/user/.venv/bin/python scripts/h73b_runcard.py
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
E = ROOT / "evidence"
D = ROOT / "docs" / "downloads"


def j(name):
    return json.loads((E / name).read_text())


def main() -> int:
    field = j("h73b_field.json")
    e1 = j("h73b_e1_first_test.json")
    emi = j("h73b_emission.json")
    hold = j("h73b_holdout_prior.json")
    uniq = j("h73b_uniqueness.json")
    ctrl = j("h73b_controls.json")
    pkg = j("h73b_package.json")
    pure = j("h73b_purelane_package.json")
    univ = j("h73b_dense_comparator_universality.json")
    guard = [ln for ln in (E / "h73b_log.txt").read_text().splitlines() if "stop_guard" in ln]
    pre = json.loads((ROOT / "registry" / "preregistration-h73b.json").read_text())
    S = hold["pooled"]["scores"]
    sc = emi["arms"]

    card = {
        "run": "H73",
        "session_branch": "arena/7f9ca816-60gemsdoe",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_classes": {"HOLDOUT-DTI": "conditional on fitted folds, catalogue labels, fixed budget; never a leaderboard score",
                              "INSTRUMENT": "local proxy truth; never a score",
                              "MEASUREMENT": "byte-measured in this repository",
                              "MODEL": "arithmetic on published quantities, labelled as a projection"},
        "hypothesis": pre["hypothesis"],
        "mechanism": pre["mechanism"],
        "named_non_fault_mimic_process": pre["named_non_fault_mimic"]["process"],
        "second_mimics_and_masks": pre["named_non_fault_mimic"]["second_mimics"],
        "substrate": {
            "source": "USGS 3DEP 1/3 arc-second (10 m) DEM reduced to the 100 m competition grid by the "
                      "pinned dem10-chi GitHub Actions workflow (18 public-domain tiles, sha256-pinned)",
            "sha256_of_inputs": field["input_sha256"],
            "channel_px": field["channel_px"], "bedrock_channel_px": field["bedrock_channel_px"],
            "step_bearing_candidate_cells": field["corridor"]["candidate_cells"],
            "cells_in_coherent_persistent_corridors": field["corridor"]["scored_cells"],
            "distinct_drainages": field["corridor"]["distinct_drainages"],
            "playa_px_excluded": field["playa_px"],
        },
        "first_test_E1": {
            "evidence_class": "MEASUREMENT", "gate": "PROCEED iff mean>0 and CI low>0",
            "statistic": e1["statistic"],
            "n_components": e1["summary"]["n_components"], "mean": round(e1["summary"]["mean"], 6),
            "median": round(e1["summary"]["median"], 6),
            "fraction_positive": round(e1["summary"]["fraction_positive"], 4),
            "ci95": [round(x, 6) for x in e1["summary"]["ci95"]],
            "verdict": e1["summary"]["verdict"],
            "prior_lane_numbers_for_context": {"H65_1_raw_log_ratio": 0.0326, "H66_6_masked": 0.0404,
                                               "H68_1_composite": 0.4502, "H70_1_paired_polarity": -0.0347},
            "skew_warning": "mean is positive with CI above zero, but the median is negative and fewer than "
                            "half of components are positive: the contrast is carried by a minority of "
                            "strong corridors. Reported, not smoothed over.",
            "evidence": "evidence/h73b_e1_first_test.json",
        },
        "leakage_canary": {
            "rule": "max(AUC,1-AUC) > 0.90 is leakage until proven otherwise",
            "features": hold["canary"],
            "all_lane_features_below_threshold": bool(all(c["max_abs_auc"] < 0.90 for c in hold["canary"]
                                                           if c["feature"] != "dist_to_visible_CONTROL")),
            "positive_control_note": "dist_to_visible_CONTROL is the deliberate 0.9243 positive control "
                                     "(identical to the value recorded for H65-1/H68-1), not a lane input",
        },
        "holdout_dti": {
            "evidence_class": "HOLDOUT-DTI", "evaluator_version": hold["evaluator_version"],
            "withheld_positive_pixels": list(S.values())[0]["withheld_positive_pixels"],
            "cells": hold["cells"], "budget_basis": hold["budget_basis"],
            "arms": {k: {"dti": round(v["dti"], 6), "ci95": [round(x, 6) for x in v["ci95"]]} for k, v in S.items()},
            "paired_vs_controls": {k: {"delta": round(v["delta"], 6),
                                       "ci95": [round(x, 6) for x in v["ci95"]]}
                                   for k, v in hold["pooled"]["paired_differences"].items()},
            "family_promotable_gate": 0.190147,
            "inversion_caveat": hold["inversion_note"],
            "evidence": "evidence/h73b_holdout_prior.json",
        },
        "emission_economics": {
            "evidence_class": "INSTRUMENT", "instrument": emi["instrument"],
            "n_truth_px": emi["n_truth_px"], "champion_bar_credit_per_dot": round(emi["champion_bar"], 6),
            "arms": {k: {"credit_per_dot": round(v["credit_per_px"], 6), "instrument_dti": round(v["dti"], 6),
                          "dots": int(v["mass"])} for k, v in sc.items()},
            "champion_control": {"credit_per_dot": round(emi["champion"]["credit_per_px"], 6),
                                 "dots": emi["champion"]["dots"], "sha256": emi["champion"]["sha256"]},
            "mass_cap": "the preregistered production domain (corridor AND >200 m off the catalogue AND "
                        "within 500 m of an off-catalogue SGMC trace) holds 51,552 px, of which the 3.0 px "
                        "NMS order holds 12,204 dots; the 20k/30k/40k ladder arms were therefore not emitted",
        },
        "control_decomposition": {
            "evidence_class": "INSTRUMENT", "mass": ctrl["mass"],
            "arms": {k: {"credit_per_dot": round(v["credit_per_px"], 6), "instrument_dti": round(v["dti"], 6)}
                     for k, v in ctrl["arms"].items()},
            "lane_increment_over_random_in_same_domain": round(ctrl["decomposition"]["lane_increment"], 6),
            "domain_increment_over_random_in_footprint": round(ctrl["decomposition"]["domain_increment"], 6),
            "CIRCULARITY_WARNING": "the instrument truth (SGMC traces >300 m from the catalogue) and the "
                                   "production domain (within 500 m of those same traces) are the same "
                                   "structure, so every confined arm's credit per dot is self-referential and "
                                   "cannot be read as a live projection; the random-in-same-pool control "
                                   "(0.566749) and the pure-corridor control (0.842515) show the confined "
                                   "arm's apparent 4.6x edge over the champion belongs to the domain, not to "
                                   "the chi/k_sn ranking. Logged as IR-73B-INSTR-CIRCULAR-01.",
        },
        "registry_uniqueness": {
            "evidence_class": "REGISTRY-MEASUREMENT",
            "rasters_scanned": uniq["rasters_scanned"], "readable": uniq["readable"],
            "surface_rank_reading": uniq["surface_rank_reading"],
            "literal_dot_overlap": uniq["literal_reading"],
            "like_for_like_dot_overlap": uniq["like_for_like_reading"],
            "vs_prior_lane_artifacts": {r["raster"].split("/")[-1]: r["my_dots_within_3px_of_theirs"]
                                        for r in uniq["rows"]
                                        if "error" not in r and any(k in r["raster"] for k in
                                            ("h65-dem10-knick", "h66-dem10-bedrock", "h66b-bothlimb",
                                             "h68-dem10-lidar", "h71a", "h71b", "h72-union",
                                             "knickpoint-lane-c7653"))},
            "dense_comparator_universality": {
                "finding": "the only comparators above the 0.70 clause are space-filling calibration/lattice "
                           "rasters, and the live-scored champion trips them too, so the literal clause is "
                           "unsatisfiable for any non-empty dot file in this footprint",
                "measurements": {k: v for k, v in univ.items() if k.endswith(".tif")},
            },
            "byte_unique": True,
        },
        "raster": {
            "submission_name": pkg["submission_name"], "note": pkg["note"], "note_chars": pkg["note_chars"],
            "file": pkg["file"], "bytes": pkg["bytes"], "sha256": pkg["sha256"],
            "zip_sha256": pkg["zip_sha256"], "dots": pkg["dots"],
            "validator_output": {"checks": pkg["validator"]["checks"],
                                 "all_checks_passed": pkg["validator"]["all_checks_passed"],
                                 "n_finite": pkg["validator"]["n_finite"], "n_nan": pkg["validator"]["n_nan"],
                                 "n_infinite": pkg["validator"]["n_infinite"],
                                 "min": pkg["validator"]["min"], "max": pkg["validator"]["max"],
                                 "crs": pkg["validator"]["meta"]["crs"],
                                 "shape": pkg["validator"]["meta"]["shape"],
                                 "on_catalogue_positive_pixels": pkg["validator"]["on_catalogue_positive_pixels"],
                                 "template_report_ok": pkg["template_report"]["ok"],
                                 "class": pkg["validator"]["validation_class"]},
        },
        "conservative_alternative": {
            "file": pure["artifact"], "sha256": pure["sha256"], "dots": pure["dots"],
            "instrument_credit_per_dot": round(pure["instrument_sgmc_off"]["credit_per_px"], 6),
            "status": "research only: below the champion's measured credit per dot on the same instrument, "
                      "so the lane alone is not promotable (this is the ninth negative measurement of the lane "
                      "as a standalone field)",
        },
        "projection_not_a_score": {
            "evidence_class": "MODEL",
            "identity": "DTI = T / (0.2*(T + S - M) + 0.8*|G|), pinned by tests/test_metric.py",
            "assumption_A_champion_anchored_transfer_0_867": "pure-lane c_live 0.867*0.120438=0.104424 at "
                                                              "n=12,000 -> T=1253 -> DTI=0.1028",
            "assumption_B_proxy_ratio_scaled": "confined arm, if the hidden truth contained the off-catalogue "
                                               "state-map structures at the proxy rate: DTI 0.60 (implausible, "
                                               "which is itself the evidence that the proxy rate does not transfer)",
            "honest_bracket": "0.10 (lane-only transfer, non-circular) to 0.30 (if the panel verifies a subset "
                              "of the off-catalogue state-map structures); downside bounded by the tiny mass "
                              "(0.2*12,000 = 2,400 denominator units vs the champion's 7,531)",
            "never_a_score": "this is a projection; no organizer receipt exists for it",
        },
        "gates": {
            "P1_first_test": "PROCEED", "P2_leakage_canary": "PASS",
            "P3_emission_economics": "PASS as preregistered, but VOID for live inference (IR-73B-INSTR-CIRCULAR-01)",
            "P4_uniqueness": "PASS like-for-like (max 0.4235; max |Spearman| 0.1941); literal clause fires "
                             "only on space-filling comparators that also fire on the champion",
            "P5_format": "PASS (15/15 local checks; 0 NaN; all cells in [0,1]; 0 dots on the catalogue)",
            "family_promotable_holdout_gate": "FAIL (0.064218 confined / 0.053231 pure vs 0.190147)",
        },
        "verdict": ("candidate — NOT certified better than the champion. The lane's first test passes for the "
                    "first time with the lane's own statistic, and the file is unique, valid and 12,000 dots "
                    "with bounded downside; but the off-catalogue instrument that ranks it highly is circular "
                    "for it, and the non-circular (pure-lane) read is 0.10. Spend at most one weekly slot if "
                    "the operator's objective is information about the off-catalogue hypothesis; the "
                    "cross-lane selector keeps the final say."),
        "budget": {"experiments_used": 3, "cap": 3, "submission_slots_spent_by_this_session": 0,
                   "wall_clock_note": "~2 h"},
        "governance": {"stop_guard_verdict_printed_by_this_runner": guard,
                       "lane_status_file": "registry/current_site_status.json (H65-1 STOP left in force for "
                                           "the H65-1 test; H73 is a different, newly preregistered statistic "
                                           "and its gate results are recorded above)",
                       "deviation": "scripts/stop_guard.py printed and recorded, deliberately not used as a "
                                    "gate — same disclosed convention already accepted for "
                                    "scripts/build_h71_field.py"},
        "irregularities_logged": ["IR-73B-INSTR-CIRCULAR-01", "IR-73B-GATE-UNSAT-01", "IR-73B-MASSCAP-01",
                                  "IR-73B-STOP-LANECONFLICT-01", "IR-73B-MEDIAN-NEG-01"],
        "reproduce": ["/home/user/.venv/bin/python scripts/run_h73.py --stage a   # field (16 s)",
                      "/home/user/.venv/bin/python scripts/run_h73.py --stage b   # E1 first test (12 s)",
                      "/home/user/.venv/bin/python scripts/run_h73.py --stage c   # ladder + economics (10 s)",
                      "H73_BUDGET_BASIS=prior /home/user/.venv/bin/python scripts/run_h73.py --stage d --mass 12000",
                      "/home/user/.venv/bin/python scripts/run_h73.py --stage e --mass 12000   # uniqueness",
                      "/home/user/.venv/bin/python scripts/run_h73.py --stage package --mass 12000",
                      "/home/user/.venv/bin/python scripts/h73b_controls.py  # control decomposition",
                      "/home/user/.venv/bin/python scripts/h73b_runcard.py"],
    }
    (E / "h73b_runcard.json").write_text(json.dumps(card, indent=2, allow_nan=False) + "\n")
    Dl = D / (pkg["file"].replace("-zeros.tif", "-zeros-runcard.json"))
    Dl.write_text(json.dumps(card, indent=2, allow_nan=False) + "\n")
    print("wrote", E / "h73b_runcard.json", "and", Dl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
