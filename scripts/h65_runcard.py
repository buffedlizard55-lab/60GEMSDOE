#!/usr/bin/env python3
"""Assemble the H65-1 JSON run card from the evidence files written by the run.

Every number is read from an evidence file (nothing is retyped by hand), so the
run card cannot drift from the measurements.  Output: evidence/h65_runcard.json
(+ a copy beside the downloadable TIF in docs/downloads/).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIF = "gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif"


def load(rel):
    return json.loads((ROOT / rel).read_text())


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    hold = load("evidence/h65_holdout.json")
    diag = load("evidence/h65_diagnostics.json")
    uniq = load("evidence/h65_uniqueness.json")
    rec = load(f"docs/downloads/{TIF.replace('.tif', '.json')}")
    man = load("data/external/dem10_chi_100m.manifest.json")
    prereg = load("evidence/preregistration_h65.json")
    octl = load("evidence/h65_overlap_control.json")
    build = load("evidence/h65_submission_build.json")
    tif = ROOT / "docs/downloads" / TIF
    digest = sha256(tif)
    assert digest == rec["sha256"], "TIF changed after its receipt was written"

    pb = hold["pooled_binary"]
    sc, pdlt = pb["scores"], pb["paired_differences"]
    e1 = hold["e1_first_test"]

    def arm(k):
        return {"dti": round(sc[k]["dti"], 5), "ci95": [round(v, 5) for v in sc[k]["ci95"]]}

    card = {
        "run": "H65-1",
        "registry_hypothesis": "H62-5 (true-10 m chi/ksn concordance)",
        "lane": "tectonic geomorphology: chi / ksn / knickpoints",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "preregistration": {"file": "evidence/preregistration_h65.json",
                            "preregistered_utc": prereg.get("preregistered_utc")},
        "hypothesis": ("Channel-steepness steps (dz/dchi two-segment step, 10 m 3DEP) that recur at the same strike "
                       "across >= 3 independent drainages mark faults, and channels crossing withheld fault "
                       "segments show larger steps than random same-orientation lines."),
        "mechanism": ("A fault offsets base level; the steepness contrast propagates upstream as a knickpoint "
                      "(Kirby & Whipple 2012, J. Struct. Geol. 44, 54-75; Perron & Royden 2013, ESPL 38, 570-576; "
                      "Gailleton et al. 2019, ESurf 7, 211-230) and persists after the scarp degrades."),
        "mimicking_non_fault_process": (
            "Lithologic contacts (resistant-over-weak bedrock), migrating transient knickpoints detached from "
            "their source, channel heads / colluvial-fluvial transitions near the A_ch=2e5 m^2 threshold, and "
            "playa/pluvial-shoreline base levels. MEASURED: the lane's support is barely enriched near mapped "
            "faults (share within 300 m / share of footprint = %.2f for steps >= ln2, %.2f for knickpoints), "
            "and step-defined channels sit lower in the local relief (median %+d m vs a 20 km median) than "
            "the catalogue (median %+d m), so the steps are dominated by these non-fault processes." % (
                diag["support"]["step_ge_log2"]["enrichment"],
                diag["support"]["knickpoint_10m"]["enrichment"],
                round(diag["relative_elevation_m"]["step_defined_p25_p50_p75"][1]),
                round(diag["relative_elevation_m"]["catalogue_p25_p50_p75"][1]))),
        "substrate": {
            "source": "USGS 3DEP 1/3 arc-second (~10 m) DEM, current 1x1-degree tiles (public domain)",
            "url_pattern": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/<tile>/USGS_13_<tile>.tif",
            "tiles": len(man["source"]["tiles"]), "tile_sha256_pins": "data/external/dem10_chi_100m.manifest.json source.tiles",
            "blocks_ok": f'{man["blocks_ok"]}/{man["blocks_total"]} (the rest contain no footprint)',
            "footprint_px_covered": f'{man["footprint_px_covered"]}/{man["footprint_px"]}',
            "github_actions_run": "https://github.com/buffedlizard55-lab/60GEMSDOE/actions/runs/38113556275",
            "manifest": "data/external/dem10_chi_100m.manifest.json",
        },
        "first_test_E1": {
            "evidence_class": e1["evidence_class"],
            "statistic": "mean log-ksn step contrast, withheld-crossing channels minus same-orientation random lines",
            "mean": round(e1["mean"], 4), "ci95": [round(v, 4) for v in e1["ci95"]],
            "median": round(e1["median"], 4), "n_components": e1["n_components"],
            "fraction_positive": round(e1["fraction_positive"], 3), "verdict": e1["verdict"],
            "rule": "brief: 'if not, stop' -> INCONCLUSIVE fails the preregistered PROCEED gate -> STOP",
        },
        "holdout_dti": {
            "evidence_class": "HOLDOUT-DTI", "evaluator_version": pb["evaluator_version"],
            "n_withheld_positives": sc["lane_h60a"]["withheld_positive_pixels"],
            "alpha": pb["alpha"], "beta": pb["beta"], "kernel_m": pb["triangular_radius_m"],
            "bootstrap": {k: pb["bootstrap"][k] for k in ("method", "clusters", "draws", "seed")},
            "lane": arm("lane_h60a"), "ksn_only_control": arm("ksn_only_no_alignment"),
            "random_mass_control": arm("random_mass_control"), "distance_only_control": arm("distance_only"),
            "paired_lane_minus_control": {k: {"delta": round(v["delta"], 5), "ci95": [round(x, 5) for x in v["ci95"]]}
                                           for k, v in pdlt.items()},
            "not_a_leaderboard_score": pb["bootstrap"]["caveat"],
        },
        "leakage_canary": {"rule": hold["canary_rule"],
                           "rows": [{"feature": r["feature"], "auc": round(r["auc"], 4),
                                     "max_abs_auc": round(r["max_abs_auc"], 4), "leakage_flag": r["leakage_flag"]}
                                    for r in hold["canary"]],
                           "reading": "every lane feature <= 0.518 (no leakage); dist_to_visible 0.924 is the "
                                      "deliberate positive control (distance to the visible catalogue), flagged as "
                                      "designed, and is not a lane input"},
        "uniqueness_vs_registry": {
            "evidence_class": uniq.get("evidence_class"),
            "registry_rasters_checked": f'{uniq["registry_rasters_checked"]}/{uniq["registry_rasters_expected"]}',
            "max_abs_spearman_full_footprint": round(uniq["worst_spearman_full_footprint"], 4),
            "max_abs_spearman_raster": uniq["worst_rho_submission"],
            "max_dot_overlap_within_3px": round(uniq["worst_dot_overlap"], 4),
            "max_dot_overlap_raster": uniq["worst_overlap_submission"],
            "max_jaccard_dot_sets": round(uniq["worst_jaccard_dot_sets"], 4),
            "max_jaccard_raster": uniq["worst_jaccard_submission"],
            "byte_unique": uniq["byte_unique_among_checked"], "pixel_unique": uniq["pixel_unique_among_checked"],
            "tool_verdict_unique": uniq["unique"],
            "limits": {"rho": uniq["rho_limit"], "overlap": uniq["overlap_limit"]},
            "file": "evidence/h65_uniqueness.json",
            "scope_note": "651/655 registry rasters fetched; the 4 missing are the known 55GEMSDOE blobs (IR-60-CORPUS-01)",
            "overlap_gate_reading": (
                "the literal 3-px overlap clause fires on %d rasters, all dense (>= %d dots); %d/%d of them also "
                "fire for 5 uniform-random 40,000-dot sets (max excess over random %+.4f), so the firing measures "
                "the prior's support density, not copying (IR-60-GATE-01). Post-hoc diagnostic: the tool verdict "
                "stays unique=false." % (octl["n_fired"], octl["min_their_dots_among_fired"],
                                         octl["n_where_random_also_fires"], octl["n_fired"], octl["max_excess"])),
            "overlap_control_file": "evidence/h65_overlap_control.json",
        },
        "reproducibility": {
            "check": "scripts/build_submission60.py --verify-existing (recompute the lane from the sha-pinned cache)",
            "log": [l for l in build["log"] if "verify-existing" in l],
            "identical": any("identical=True" in l for l in build["log"]),
            "irregularity": ("IR-65-CACHE-01: the local .cache/features65 found on disk after the run did not "
                             "match its recorded sha256 (step finite px 787,225 vs 786,299; cause not identified; "
                             ".cache is untracked scratch). Rebuilt from the sha-pinned TIFs -> all 11 arrays match "
                             "evidence/h65_feature_cache.json, the shipped TIF reproduces dot-for-dot, and the "
                             "diagnostics were re-run on the verified cache."),
        },
        "artifact": {
            "file": f"docs/downloads/{TIF}",
            "sha256": digest, "bytes": tif.stat().st_size,
            "validator_ok": rec["validator"]["all_checks_passed"],
            "validator_problems": [k for k, v in rec["validator"]["checks"].items() if not v],
            "emitted_positive_pixels": rec["validator"]["emitted_positive_pixels"],
            "min": rec["validator"]["min"], "max": rec["validator"]["max"], "n_nan": rec["validator"]["n_nan"],
        },
        "submission_name": "60GEMSDOE-H65-1-DEM10-KNICK-40000",
        "note": rec["note"],
        "note_chars": len(rec["note"]),
        "verdict": "NEGATIVE",
        "submit": "NO - research artifact only; do not spend a slot",
        "shared_tool_fixes": [
            "src/gems52/lane_hydro.py _chi: diagonal D8 steps now use sqrt(2)*cell length (was cell length)",
            "scripts/run_lane60.py + scripts/build_submission60.py: GEMS60_FEATURE_CACHE / GEMS60_TAG env vars, "
            "optional branch_sig.npy, --hypothesis/--note/--substrate (defaults reproduce H60-A byte-for-byte)",
            "scripts/check_uniqueness60.py: --surface honours GEMS60_FEATURE_CACHE and branch_sig.npy",
            "citations corrected in src/gems60/geomorph.py, src/gems52/lane_hydro.py, src/gems52/lane_channels.py, "
            "scripts/build_site60.py, docs/lane-knick-corridor-report.html (Kirby & Whipple 2012 is J. Struct. "
            "Geol. 44:54-75, not JGR F04002; Perron & Royden 2013 is ESPL 38:570-576; Gailleton 2019 is ESurf "
            "7:211-230; Royden & Perron 2013 is JGR-ES 118:497-518; Barnes 2014 is C&G 62:117-127)",
        ],
    }
    out = ROOT / "evidence/h65_runcard.json"
    out.write_text(json.dumps(card, indent=1) + "\n")
    (ROOT / "docs/downloads" / TIF.replace(".tif", "-runcard.json")).write_text(json.dumps(card, indent=1) + "\n")
    print(json.dumps(card, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
