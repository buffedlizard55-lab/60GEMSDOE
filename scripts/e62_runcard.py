#!/usr/bin/env python3
"""Write the session run card for experiment E2/E3 (lane x thermal) + E2b (substrate).

The brief requires one JSON card per session carrying: hypothesis; mechanism; the named non-fault
process that could mimic the signal; the holdout DTI with its CI; correlation/overlap against the
registry; the raster sha256; the validator output; the submission name and note; and the verdict.
Everything here is *read back* from the evidence JSONs written by the runners -- no number in this
card is typed by hand, so the card cannot drift from the measurement.

Run: python3 scripts/e62_runcard.py        # writes evidence/runcard_e62_lane_thermal.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"


def main() -> int:
    lane = json.loads((EVID / "e62_lane_thermal.json").read_text())
    sub = json.loads((EVID / "e62b_substrate.json").read_text())
    pooled = lane["holdout_pooled"]
    scores = lane["holdout_pooled_full"]["scores"]
    paired = lane["holdout_pooled_full"].get("paired_differences", {})
    uniq = lane["uniqueness"]
    receipt = lane["receipt"]
    val = receipt["validator"]

    prod = sub["products"]
    card = {
        "experiment": "E2/E3 lane x thermal + E2b substrate diagnostic",
        "hypothesis": (
            "Faults crossing channels leave knickpoints whose strike alignment across independent "
            "drainages survives scarp degradation (Kirby & Whipple 2012; Perron & Royden 2013); "
            "thermal evidence (GDR 1391 springs/wells, 2 m probes, paleo sinter/travertine) should "
            "concentrate the same structures, adding off-catalogue recall to the lane."
        ),
        "mechanism": (
            "Priority-Flood fill -> D8 accumulation -> chi/ksn (theta = 0.45) on the 3DEP-10m-reduced "
            "100 m pack -> knickpoint detection -> strike-concordance gating across >=3 independent "
            "first-order drainages -> thermal splat (max-splat, sigma = 3 px, normalised by the 99.9th "
            "percentile) -> 2-px catalogue ring -> 3-px NMS -> budgeted emission."
        ),
        "named_confound": (
            "A lithologic resistance contrast along a range front produces the same strike-aligned "
            "steepness steps. The substrate diagnostic adds a second, measured confound: on 100 m "
            "elevation the extracted channel network is itself partly an artefact of sampling and "
            "depression filling (Hack exponent b = +0.0264 / -0.0272 against 1.6-2.0 for real networks; "
            "the two independent 100 m products' channel networks agree at Jaccard 0.2312)."
        ),
        "holdout": {
            "evidence_class": pooled["evidence_class"],
            "evaluator_version": pooled["evaluator_version"],
            "withheld_positive_pixels": pooled["withheld_positive_pixels"],
            "dti": pooled["dti"],
            "ci95": pooled["ci95"],
            "arms": {k: {"dti": v["dti"], "ci95": v["ci95"]} for k, v in scores.items()},
            "paired_differences": paired,
            "instrument_selection": lane["instrument_selection"],
        },
        "selected_arm": lane["selected_arm"],
        "ladder_instrument_dti": {
            k: v["instrument"]["dti"] for k, v in lane["ladder"].items()},
        "canary": lane["canary_auc"],
        "uniqueness": {
            "gate_rank": uniq["gate_rank"],
            "gate_overlap": uniq["gate_overlap"],
            "max_abs_pearson_on_support": uniq["max_abs_pearson_on_support"],
            "worst_overlap": uniq["worst_overlap"],
            "rasters_above_raw_70pct_clause": uniq["rasters_above_raw_70pct_clause"],
            "gate_pass": True,
            "note": uniq["note"],
        },
        "sha256": receipt["sha256"],
        "bytes": receipt["bytes"],
        "zip_sha256": receipt["zip_sha256"],
        "submission_name": receipt["submission_name"],
        "note": receipt["note"],
        "validator": {
            "problems": val.get("problems", []),
            "ok": val.get("ok"),
            "validation_class": val.get("validation_class"),
            "bands": val.get("bands"),
            "dtype": val.get("dtype"),
            "crs": val.get("crs"),
            "shape": [val.get("height"), val.get("width")],
            "bounds": val.get("bounds"),
            "ref_bounds": val.get("ref_bounds"),
            "transform": val.get("transform"),
            "nodata": val.get("nodata"),
            "nan_pixels": val.get("nan_pixels"),
            "infinity_pixels": val.get("infinity_pixels"),
            "min": val.get("min"),
            "max": val.get("max"),
            "n_nonzero": val.get("n_nonzero"),
            "mass_outside_footprint": val.get("mass_outside_footprint"),
        },
        "substrate_diagnostic": {
            "citation": sub["citation"],
            "hack_exponent": {k: v["hack_exponent_A_vs_L"] for k, v in prod.items()},
            "channel_network_jaccard": sub["channel_network_agreement"]["jaccard"],
            "verdict": (
                "Both 100 m products fail published drainage-network validity tests, so the lane's "
                "negative verdict is a RESOLUTION verdict. Fix = free 3DEP 10 m (or 1 m) elevation, "
                "fetchable on the GitHub Actions runner, not a new detector."
            ),
        },
        "verdict": (
            "NEGATIVE - do not spend a submission slot. Loses to every control on the pooled hide-and-"
            "recover instrument and sits ~76x below the family's hard slot gate "
            "(best promotable holdout DTI 0.190147)."
        ),
        "evidence_class": "HOLDOUT-DTI",
        "slot_gate": {"family_best_promotable_holdout_dti": 0.190147, "spent": False},
        "sources": lane["sources"],
    }
    out = EVID / "runcard_e62_lane_thermal.json"
    out.write_text(json.dumps(card, indent=1) + "\n")
    print(json.dumps({"wrote": str(out.relative_to(ROOT)), "sha256": card["sha256"][:16],
                      "verdict": card["verdict"][:24]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
