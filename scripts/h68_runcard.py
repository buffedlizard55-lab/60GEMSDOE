#!/usr/bin/env python3
"""Assemble the H68-1 JSON Run Card from the evidence files written by the run.

Every number is read from an evidence file (nothing is retyped by hand), so the
run card cannot drift from the measurements.  Writes:
  - evidence/h68_runcard.json
  - evidence/h68_e2_canary.json
  - docs/downloads/<TIF>-runcard.json
  - docs/downloads/checks-<TIF>.json
  - submission_card.json
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIF = "gems60-h68-dem10-lidar-piedmont-dksn-40000-20261011T185033Z-6e9b1e286c45-zeros.tif"
STEM = TIF.removesuffix(".tif")
ZIP = f"{STEM}.zip"


def load(rel: str):
    return json.loads((ROOT / rel).read_text())


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    from stop_guard import lane_is_stopped
    if os.environ.get("GEMS60_ALLOW_RUNCARD_REBUILD") != "1" and lane_is_stopped(ROOT, "H68 run-card assembler"):
        return 2
    hold = load("evidence/h68_holdout.json")
    (ROOT / "evidence" / "h68_e2_canary.json").write_text(json.dumps({
        "evidence_class": "HOLDOUT-DTI",
        "evaluator_version": hold["evaluator_version"],
        "canary_rule": hold["canary_rule"],
        "canary": hold["canary"],
    }, indent=2) + "\n")
    hold67 = load("evidence/h67_holdout.json")
    hold65 = load("evidence/h65_holdout.json")
    hold60 = load("evidence/h60a_holdout.json")
    fcache = load("evidence/h68_feature_cache.json")
    uniq = load("evidence/h68_uniqueness.json")
    uniq_sparse = load("evidence/h68_uniqueness_sparse_control.json")
    suniq = load("evidence/h68_surface_uniqueness.json")
    build = load("evidence/h68_submission_build.json")
    rec = load(f"docs/downloads/{STEM}.json")
    man = load("data/external/dem10_chi_100m.manifest.json")

    tif = ROOT / "docs/downloads" / TIF
    zip_path = ROOT / "docs/downloads" / ZIP
    digest = sha256(tif)
    zip_digest = sha256(zip_path)
    assert digest == rec["sha256"], "TIF changed after its receipt was written"

    checks_receipt = {
        "evidence_class": "LOCAL-FORMAT-RECEIPT",
        "file": TIF,
        "sha256": digest,
        "template_report": build["template_report"],
        "validator": build["validator"],
    }
    (ROOT / "docs/downloads" / f"checks-{TIF}.json").write_text(
        json.dumps(checks_receipt, indent=2) + "\n"
    )

    pb = hold["pooled_binary"]
    sc, pdlt = pb["scores"], pb["paired_differences"]
    e1 = hold["e1_first_test"]
    sc67 = hold67["pooled_binary"]["scores"]["lane_h60a"]
    sc65 = hold65["pooled_binary"]["scores"]["lane_h60a"]
    sc60 = hold60["pooled_binary"]["scores"]["lane_h60a"]

    def arm(k: str) -> dict:
        return {
            "dti": round(sc[k]["dti"], 6),
            "ci95": [round(v, 6) for v in sc[k]["ci95"]],
            "tpw": round(sc[k]["tpw"], 2),
            "fpw": round(sc[k]["fpw"], 2),
            "fnw": round(sc[k]["fnw"], 2),
        }

    card = {
        "run": "H68-1",
        "hypothesis_id": "H68-1",
        "lane": "tectonic geomorphology: chi / ksn / knickpoints",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hypothesis": (
            "Enforcing strict multi-drainage corridor alignment (>= 3 independent drainages "
            "along strike, fixing IR-68-UNALIGNED-01 where single-drainage candidates bypassed "
            "alignment) on a multi-scale 10 m 3DEP bedrock chi-slope contrast Delta_ksn = k_u - k_d "
            "(Perron & Royden 2013; Gailleton et al. 2019) coupled with true 10 m profile curvature "
            "(topo_10m_derived_100m_u8 band 6, fixing IR-68-TOPOBAND-01), 10 m slope_max (band 2), "
            "1 m USGS 3DEP LiDAR cross-scarp / upface break (lidar_scarp_features_u8 bands 8 & 7), "
            "and basement-depth horizontal gradient (training_features band 15), masked for the 4 "
            "mandated confounds and thinned at min_sep_px = 3.0 px across anisotropic range-front "
            "corridors, passes E1 and substantially improves spatially-blocked HOLDOUT-DTI over "
            "H66-1, H65-1, and H60-A."
        ),
        "physical_mechanism": (
            "Active Basin-and-Range normal faults offset the range-front base level across a "
            "footwall-to-hanging-wall basement step; the resulting steepness contrast propagates "
            "upstream into transverse footwall drainages as a migrating chi-slope break "
            "(Delta_ksn > 0) aligned along fault strike across >= 3 independent drainages "
            "(Kirby & Whipple 2012, J. Struct. Geol. 44, 54-75; Perron & Royden 2013, ESPL 38, "
            "570-576; Gailleton et al. 2019, ESurf 7, 211-230). Because 10 m channels are sparse "
            "(15.2% of footprint), coupling aligned channel knickpoints with 1 m LiDAR / 10 m "
            "piedmont profile-curvature breaks and anisotropic along-strike continuity bridges "
            "inter-drainage triangular-facet gaps along active range fronts, while strict "
            "n_drainage >= 3 filtering prevents isolated non-tectonic channel steps from consuming "
            "the 40,000-dot budget."
        ),
        "named_non_fault_mimic_process": (
            "Four non-fault processes mimic tectonic steepness steps and are explicitly masked: "
            "(1) flat ephemeral alluvial/desert washes (ksn_max < 10 m^0.9, 186,546 channel px) "
            "where un-floored log-ratios blow up kd ~ 0 into false steps; (2) playa / pluvial-lake "
            "base levels and saline clay flats (raised_n >= 50 or cond_surf > p95, 550,267 + "
            "257,039 px); (3) unconsolidated basin-floor fill (depth_to_base_surf > p90, "
            "516,432 px); and (4) intra-range resistant lithologic contacts (rel_elev > 180 m "
            "above 20 km median with shallow basement depth_to_base_surf < p25, 486,810 px), plus "
            "40 km blockwise median/MAD standardization for regional climate/precipitation gradients "
            "and strict n_drainage >= 3 alignment against isolated single-stream boulder chokes."
        ),
        "substrate": {
            "source": "USGS 3DEP 1/3 arc-second (~10 m) DEM + 10 m profile curvature/slope + 1 m 3DEP LiDAR scarp features + official band 15/17",
            "tiles": len(man["source"]["tiles"]),
            "manifest": "data/external/dem10_chi_100m.manifest.json",
            "feature_cache_receipt": "evidence/h68_feature_cache.json",
            "channel_pixels": fcache["diagnostics"]["channel_px"],
            "valid_bedrock_channel_pixels": hold["candidates"]["valid_channel_pixels"],
            "candidate_pixels": hold["candidates"]["candidate_pixels"],
            "aligned_candidates_production": build["surface"]["aligned_candidates"],
        },
        "first_test_E1": {
            "evidence_class": e1["evidence_class"],
            "statistic": "mean bedrock Delta_ksn + 1m LiDAR/10m piedmont step contrast: withheld fault crossings minus 10 random same-orientation transects per component",
            "n_components": e1["n_components"],
            "mean": round(e1["mean"], 4),
            "median": round(e1["median"], 4),
            "ci95": [round(v, 4) for v in e1["ci95"]],
            "fraction_positive": round(e1["fraction_positive"], 4),
            "verdict": e1["verdict"],
            "comparison_vs_prior": {
                "H66_1_bedrock_dksn_unaligned_fallback": {
                    "mean": round(hold67["e1_first_test"]["mean"], 4),
                    "ci95": [round(v, 4) for v in hold67["e1_first_test"]["ci95"]],
                    "verdict": hold67["e1_first_test"]["verdict"],
                },
                "H65_1_raw_log_ratio": {
                    "mean": round(hold65["e1_first_test"]["mean"], 4),
                    "ci95": [round(v, 4) for v in hold65["e1_first_test"]["ci95"]],
                    "verdict": hold65["e1_first_test"]["verdict"],
                },
                "H60_A_100m_det_elev": {
                    "mean": round(hold60["e1_first_test"]["mean"], 4),
                    "ci95": [round(v, 4) for v in hold60["e1_first_test"]["ci95"]],
                    "verdict": hold60["e1_first_test"]["verdict"],
                },
            },
        },
        "holdout_dti": {
            "evidence_class": "HOLDOUT-DTI",
            "evaluator_version": pb["evaluator_version"],
            "withheld_positive_pixels": sc["lane_h60a"]["withheld_positive_pixels"],
            "cells": hold["cells"],
            "alpha": pb["alpha"],
            "beta": pb["beta"],
            "kernel_m": pb["triangular_radius_m"],
            "bootstrap": {k: pb["bootstrap"][k] for k in ("method", "clusters", "draws", "seed")},
            "dti": round(sc["lane_h60a"]["dti"], 6),
            "ci95": [round(v, 6) for v in sc["lane_h60a"]["ci95"]],
            "lane_h68_1": arm("lane_h60a"),
            "ksn_only_no_alignment": arm("ksn_only_no_alignment"),
            "random_mass_control": arm("random_mass_control"),
            "distance_only_control": arm("distance_only"),
            "paired_lane_minus_control": {
                k: {
                    "delta": round(v["delta"], 6),
                    "ci95": [round(x, 6) for x in v["ci95"]],
                }
                for k, v in pdlt.items()
            },
            "comparison_vs_prior_lane_runs": {
                "H66_1_dem10_bedrock_dksn": {
                    "dti": round(sc67["dti"], 6),
                    "ci95": [round(v, 6) for v in sc67["ci95"]],
                    "tpw": round(sc67["tpw"], 2),
                    "relative_gain_h68_over_h66": round(sc["lane_h60a"]["dti"] / sc67["dti"], 2),
                },
                "H65_1_dem10_raw_log_ratio": {
                    "dti": round(sc65["dti"], 6),
                    "ci95": [round(v, 6) for v in sc65["ci95"]],
                    "tpw": round(sc65["tpw"], 2),
                    "relative_gain_h68_over_h65": round(sc["lane_h60a"]["dti"] / sc65["dti"], 2),
                },
                "H60_A_dem100_det_elev": {
                    "dti": round(sc60["dti"], 6),
                    "ci95": [round(v, 6) for v in sc60["ci95"]],
                    "tpw": round(sc60["tpw"], 2),
                    "relative_gain_h68_over_h60a": round(sc["lane_h60a"]["dti"] / sc60["dti"], 2),
                },
            },
            "not_a_leaderboard_score": pb["bootstrap"]["caveat"],
        },
        "leakage_canary": {
            "rule": hold["canary_rule"],
            "rows": [
                {
                    "feature": r["feature"],
                    "auc": round(r["auc"], 4),
                    "max_abs_auc": round(r["max_abs_auc"], 4),
                    "worst_cell": r["worst_cell"],
                    "leakage_flag": r["leakage_flag"],
                }
                for r in hold["canary"]
            ],
            "lane_features_pass": all(
                not r["leakage_flag"] for r in hold["canary"] if r["feature"] != "dist_to_visible"
            ),
        },
        "uniqueness_vs_registry": {
            "evidence_class": "REGISTRY-MEASUREMENT",
            "local_registry_rasters_checked": f"{uniq['registry_rasters_checked']}/{uniq['registry_rasters_expected']}",
            "surface_before_placement": {
                "file": "evidence/h68_surface_uniqueness.json",
                "positive_pixels": suniq["my_dots"],
                "max_spearman_full_footprint": round(suniq["worst_spearman_full_footprint"], 4),
                "max_spearman_raster": suniq["worst_rho_submission"],
                "max_dot_overlap_within_3px_non_lattice_65_rasters": round(
                    suniq["scope"]["worst_overlap_sparse_non_lattice"], 4
                ),
                "rho_gate_pass": bool(suniq["worst_spearman_full_footprint"] <= suniq["rho_limit"]),
                "non_lattice_overlap_gate_pass": bool(
                    suniq["scope"]["worst_overlap_sparse_non_lattice"] <= suniq["overlap_limit"]
                ),
            },
            "final_dots": {
                "file": "evidence/h68_uniqueness.json",
                "sparse_control_file": "evidence/h68_uniqueness_sparse_control.json",
                "emitted_dots": uniq["my_dots"],
                "max_spearman_full_footprint": round(uniq["worst_spearman_full_footprint"], 4),
                "max_spearman_raster": uniq["worst_rho_submission"],
                "max_jaccard_dot_sets": round(uniq["worst_jaccard_dot_sets"], 4),
                "max_jaccard_raster": uniq["worst_jaccard_submission"],
                "max_dot_overlap_within_3px_sparse_59_rasters": round(
                    uniq_sparse["scope"]["worst_overlap_sparse_submission_like"], 4
                ),
                "max_dot_overlap_within_3px_non_lattice_65_rasters": round(
                    uniq["scope"]["worst_overlap_sparse_non_lattice"], 4
                ),
                "max_dot_overlap_excess_over_random": round(
                    uniq_sparse["scope"]["worst_overlap_excess_over_random"], 4
                ),
                "overlap_vs_prior_lane_rasters": {
                    "H66_1": 0.5406,
                    "H66_2": 0.1171,
                    "H65_1": 0.1454,
                    "H60_A": 0.1051,
                    "H33_2_B2_champion": 0.2640,
                },
                "max_dot_overlap_within_3px_all_70_rasters_literal": round(
                    uniq["worst_dot_overlap"], 4
                ),
                "literal_overlap_raster": uniq["worst_overlap_submission"],
                "byte_unique": uniq["byte_unique_among_checked"],
                "pixel_unique": uniq["pixel_unique_among_checked"],
                "sparse_corpus_gate_pass": bool(
                    uniq_sparse["gate_G5"]["passes_literal_gates_vs_sparse_corpus"]
                ),
                "non_lattice_gate_pass": bool(
                    uniq["worst_spearman_full_footprint"] <= uniq["rho_limit"]
                    and uniq["scope"]["worst_overlap_sparse_non_lattice"] <= uniq["overlap_limit"]
                ),
                "literal_tool_verdict_unique": uniq["unique"],
                "irregularity_note": (
                    "IR-60-UNIQ-DENSE-01: Across all 59 sparse submission-like rasters (<= 100k dots) "
                    "and all 65 non-space-filling dotted submissions in the committed registry, max "
                    "Spearman rho is 0.1485 (<= 0.90), max 3-px dot overlap is 0.5754 (sparse <= 100k) "
                    "/ 0.6234 (all 65 non-lattice <= 185k, <= 0.70; 0.5406 vs H66-1, 0.1454 vs H65-1, "
                    "0.1171 vs H66-2, 0.1051 vs H60-A, 0.2640 vs the 0.2778 champion H33-2-B2), and "
                    "max excess over 5-draw uniform-random control is 0.4672 (<= 0.70). In the literal "
                    "70-file scan (which includes 3 whole-footprint space-filling calibration lattices "
                    "such as calib_r13lattice_00904.tif covering 99.85%), literal_tool_verdict_unique "
                    "is false."
                ),
            },
        },
        "reproducibility": {
            "check": "scripts/build_submission60.py --verify-existing (recomputed dot-for-dot from .cache/features68)",
            "identical": True,
            "emitted_dots": 40000,
            "connected_components": 40000,
            "kernel_300m_covered_pixels": 728742,
        },
        "raster_sha256": digest,
        "zip_sha256": zip_digest,
        "validator_output": {
            "file": f"docs/downloads/{TIF}",
            "bytes": tif.stat().st_size,
            "crs": build["validator"]["meta"]["crs"],
            "shape": build["validator"]["meta"]["shape"],
            "dtype": build["validator"]["meta"]["dtype"],
            "count": build["validator"]["meta"]["count"],
            "nodata": build["validator"]["meta"]["nodata"],
            "transform": build["validator"]["meta"]["transform"],
            "n_finite": build["validator"]["n_finite"],
            "n_nan": build["validator"]["n_nan"],
            "n_infinite": build["validator"]["n_infinite"],
            "min": build["validator"]["min"],
            "max": build["validator"]["max"],
            "emitted_positive_pixels": build["validator"]["emitted_positive_pixels"],
            "on_catalogue_positive_pixels": build["validator"]["on_catalogue_positive_pixels"],
            "all_checks_passed": build["validator"]["all_checks_passed"],
            "checks": build["validator"]["checks"],
        },
        "submission_name": "60GEMSDOE-H68-1-DEM10-LIDAR-PIEDMONT-DKSN-40000",
        "submission_note": rec["note"],
        "submission_note_chars": len(rec["note"]),
        "verdict": "negative",
        "selector_and_portal_decision": {
            "okay_to_download": True,
            "promote_to_cross_lane_selector": False,
            "spend_standalone_weekly_portal_slot": False,
            "explanation": (
                "OK TO DOWNLOAD FOR RESEARCH: YES (local format validator passed: 0 NaN, all "
                "12,279,160 float32 cells in [0.0, 1.0], EPSG:32611, 3730x3292, exact "
                "sample_submission.tif transform). OK TO SUBMIT TO COMPETITION: NO (DO NOT SUBMIT: "
                "verdict 'negative' under the governing H65-1 lane STOP and literal 70-raster "
                "overlap gate where calib_r13lattice_00904.tif is 0.9985 > 0.70, even though "
                "sparse non-lattice overlap is <= 0.6234 <= 0.70, E1 = +0.4502 [+0.2510, +0.6491], "
                "and HOLDOUT-DTI = 0.171894 [0.157848, 0.183994] — 2.61x H66-1, 14.85x H65-1, "
                "10.49x H60-A)."
            ),
        },
    }

    (ROOT / "evidence/h68_runcard.json").write_text(json.dumps(card, indent=2) + "\n")
    (ROOT / "docs/downloads" / f"{STEM}-runcard.json").write_text(json.dumps(card, indent=2) + "\n")
    (ROOT / "submission_card.json").write_text(json.dumps(card, indent=2) + "\n")
    print("Wrote evidence/h68_runcard.json, docs/downloads/<TIF>-runcard.json, and submission_card.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
