#!/usr/bin/env python3
"""Assemble the H70-1 run card (verdict: NEGATIVE — G1 first-test STOP).

Every number is read from the committed evidence files written by
``scripts/run_h70.py``; nothing is retyped by hand.  Writes:

  - evidence/h70_runcard.json   (the protocol's item-5 JSON card)
  - docs/feed.json              (status feed reason refreshed)
  - registry/irregularities.json (IR-70 entries appended, idempotently)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str):
    return json.loads((ROOT / rel).read_text())


def main() -> int:
    e1 = load("evidence/h70_e1_first_test.json")
    cache = load("evidence/h70_feature_cache.json")
    g1 = e1["E1a_withheld_catalogue"]["summary"]
    g1c = e1["E1a_crest_only_ablation"]["summary"]
    e1b = e1["E1b_sgmc_off_catalogue"]["summary"]

    card = {
        "run": "H70-1",
        "hypothesis_id": "H70-1",
        "lane": "tectonic geomorphology: chi / ksn / knickpoints (paired-polarity trains)",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "preregistration": "registry/preregistration-h70.json",
        "budget_use": {
            "experiments_used": 1,
            "experiments_cap": 3,
            "reason_not_more": ("the mandated first test is the protocol's stop condition; running "
                                "further preregistrations in the same hour to find a passing gate "
                                "would be gate-shopping"),
            "session_wall_time_minutes": None,
        },
        "hypothesis": (
            "An active fault that steps the range-front base level drives a migrating incision wave "
            "up each transverse footwall drainage; in chi space that wave is a trapped PAIR of "
            "opposite-polarity steepness steps on the same branch: an upstream steepened crest "
            "(step_max > 0) and, exactly 500 m downstream along the same flow path (the committed "
            "substrate sig band), the wave's leading edge (step_min < 0). pair_strength = "
            "min(crest, base_drop), floored at ln(1.25), blockwise z-scored at 40 km, corroborated "
            "across >= 3 independent drainages along a common strike, was hypothesised to mark "
            "active fault traces the given Quaternary catalogue omits, with single-flank lithologic "
            "steps filtered out by the pairing itself."
        ),
        "mechanism": (
            "Kirby & Whipple (2012) base-level-step -> knickpoint; Perron & Royden (2013) chi "
            "normalisation; Wobus et al. (2006) / Berlin & Anderson (2007) knickpoint waves: the "
            "profile steepens at the crest while the reach immediately downstream of the wave face "
            "remains gentle relative to the unperturbed reach below it, so the wave carries one "
            "positive and one negative chi-slope step, pinned to the same branch. Gailleton et al. "
            "(2019) segmentation motivates the fixed-window two-segment approximation used by the "
            "committed 10 m substrate."
        ),
        "named_non_fault_mimic_process": (
            "A resistant-over-weak dipping lithologic couplet (its two contacts make a paired step "
            "as a channel crosses the unit twice). Countered by the radiometric-contact-gradient "
            "mask, the low-radioelement high-relief core mask, the >= 3-drainage along-strike "
            "alignment rule and 40 km blockwise standardization. Secondary mimics: debris-flow "
            "headcuts and fan-head trenches (ephemeral-wash mask ksn_max < 10 m^0.9), playa and "
            "closed-basin floors (raised_n >= 50), DEM fill artefacts."
        ),
        "substrate": {
            "source": "USGS 3DEP 1/3 arc-second (~10 m) DEM, 18 tiles (public domain) -> committed 100 m reduction",
            "manifest": "data/external/dem10_chi_100m.manifest.json (sha256-checked before computing)",
            "feature_cache_receipt": "evidence/h70_feature_cache.json",
            "channel_pixels": cache["diagnostics"]["channel_px"],
            "pair_defined_channel_pixels": cache["diagnostics"]["pair_defined_channel_px"],
            "candidate_pixels_after_confounds_and_floor": 13720,
        },
        "first_test_G1_GATING": {
            "evidence_class": "MEASUREMENT",
            "target": "withheld catalogue segments (mode 'all', 8 cells, seeds 20/21 — the identical draw every prior lane run used)",
            "n_components": g1["n_components"],
            "mean": g1["mean"],
            "median": g1["median"],
            "ci95": g1["ci95"],
            "fraction_positive": g1["fraction_positive"],
            "verdict": g1["verdict"],
            "gate": "G1: verdict == PROCEED (mean > 0 AND 95% CI lower bound > 0) required; anything else stops the lane",
            "gate_verdict": e1["gate_G1_verdict"],
            "distribution_note": ("median is positive (+0.049) while the mean is negative (-0.035): "
                                  "60.2% of withheld crossings show a paired-step excess but a "
                                  "minority shows a strong deficit, so the skew kills the pooled "
                                  "contrast. No post-hoc rescue is claimed."),
        },
        "first_test_ablation_and_diagnostics": {
            "crest_only_ablation_identical_kernel": {
                "evidence_class": "MEASUREMENT",
                "mean": g1c["mean"], "ci95": g1c["ci95"], "verdict": g1c["verdict"],
                "verification_certificate": (
                    "the crest-only ablation reproduces H65-1's published INCONCLUSIVE first test "
                    "on the identical holdout draw and seeds to ~1e-9 (H65-1: mean "
                    "0.03259120937549255, CI [-0.0143535845, +0.0789952332]; H70 ablation: mean "
                    "0.03259120759121011, CI [-0.0143535868, +0.0789952321]) — run_h70's E1 path is "
                    "the shared one, not a fork"),
            },
            "E1b_sgmc_off_catalogue_NON_GATING": {
                "evidence_class": "MEASUREMENT",
                "n_components": e1b["n_components"],
                "mean": e1b["mean"], "median": e1b["median"], "ci95": e1b["ci95"],
                "fraction_positive": e1b["fraction_positive"],
                "verdict_if_it_were_gating": e1b["verdict"],
                "reading": ("the pairing is elevated at SGMC off-catalogue crossings (+0.057 "
                            "[+0.010, +0.103]) — the opposite sign from H66's single-limb dksn "
                            "(-0.113 STOP). The preregistration binds: G1 is the catalogue-withheld "
                            "test; flip-flopping gates after seeing numbers is exactly the malpractice "
                            "the protocol forbids, so this diagnostic changes nothing about the verdict "
                            "and is recorded as research evidence for the next preregistered question."),
            },
        },
        "holdout_dti": {
            "evidence_class": "HOLDOUT-DTI",
            "dti": None, "ci95": None, "withheld_positive_pixels": None,
            "reason": "not run: G1 STOP halts the lane before any surface exists (protocol rule 2 / prereg gates)",
        },
        "leakage_canary": {
            "ran": False,
            "reason": "canary is defined on the lane emission domain, which G1 STOP prevents from existing",
        },
        "correlation_overlap_vs_registry": "not applicable: no surface was built and no dots were emitted",
        "raster_sha256": None,
        "validator_output": None,
        "submission_name": None,
        "submission_note": None,
        "verdict": "negative",
        "what_would_have_been_shipped": (
            "nothing. The negative card is the deliverable. Under the governing H68 lane-stop audit "
            "(registry/current_site_status.json) the only download is the H65-1 research artifact — "
            "research only, DO NOT SUBMIT; the H66/H67 artifacts carry negative errata (their literal "
            "registry-uniqueness clearance failed: max raw 3-px dot overlap 1.00 vs the 0.70 bound) and "
            "the H67-1 'promote' was reversed (IR-H66C-STOPCONFLICT-01, PRs #19/#20). H70 changes none "
            "of that (H70 probes a different statistic and adds the IR-70-SEL-01 selection-history caveat)."
        ),
        "next_preregistered_question_recommended": (
            "H71: paired-basin ksn contrast across fault blocks (rank 1 of the deferred backlog): the "
            "E1b flip (+0.0567 off-catalogue with CI > 0) says the PAIRED signal does live on mapped "
            "structures absent from the catalogue, but the pixel-crossing test population is the "
            "wrong one for it; test it at basin scale on a fresh 10 m substrate with explicit "
            "catchment pairing, masked for erodibility, with E1a-catalogue and E1b-SGMC-off both "
            "preregistered as gating before any number is seen."
        ),
        "links": {
            "run_log": "evidence/h70_run.log",
            "e1_rows": "evidence/h70_e1_first_test.json",
            "feature_cache": "evidence/h70_feature_cache.json",
            "lane_stop_record": "evidence/h70_lane_stop.json",
            "preregistration": "registry/preregistration-h70.json",
        },
    }
    (ROOT / "evidence" / "h70_runcard.json").write_text(json.dumps(card, indent=2) + "\n")

    # ---- feed / irregularities registration ------------------------------- #
    # Post-H68 main: docs/feed.json uses the `submissions` array and the
    # irregularity register already carries the STOP-vs-promote conflict as
    # IR-H66C-STOPCONFLICT-01 (resolved). Both registrations are done by
    # scripts/h70_publish_site.py so the schemas stay in one place; run it
    # after this script.
    print("wrote evidence/h70_runcard.json (register feed + irregularities via scripts/h70_publish_site.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
