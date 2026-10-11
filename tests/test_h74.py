"""Lock the H74-1 evidence contract.

These assertions pin the run card the parallel-run protocol requires (rule 5) and the numbers this
session measured, so a later session cannot silently rewrite them.  Every number asserted here is
recomputed from the evidence files, never copied, and the preregistration is checked to predate the
evidence it governs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _j(rel: str):
    return json.loads((ROOT / rel).read_text())


CARD = _j("evidence/h74_runcard.json")
E1 = _j("evidence/h74_e1_first_test.json")
E1B = _j("evidence/h74_e1b_offcatalogue.json")
TIFF = _j("evidence/h74_tiff.json")
UNI = _j("evidence/h74_uniqueness_satisfiable.json")
HOLD = _j("evidence/h74_holdout.json")
PRE = _j("registry/preregistration-h74.json")


def test_preregistration_predates_the_evidence_it_governs():
    pre_mtime = (ROOT / "registry" / "preregistration-h74.json").stat().st_mtime
    for rel in ("evidence/h74_e1_first_test.json", "evidence/h74_e1b_offcatalogue.json",
                "evidence/h74_holdout.json", "evidence/h74_runcard.json"):
        assert pre_mtime <= (ROOT / rel).stat().st_mtime, f"preregistration is newer than {rel}"
    # the endpoint and the gate must be fixed in the preregistration, not chosen afterwards
    assert PRE["e1_gating_first_test"]["gate"].startswith("PROCEED iff")
    assert "amendments" in PRE, "the primary/secondary split must be recorded, not silent"


def test_run_card_carries_the_full_protocol_contract():
    for field in ("hypothesis", "mechanism", "named_non_fault_process_that_could_mimic_it",
                  "first_test", "holdout_dti", "leakage_canary", "uniqueness", "raster",
                  "validator_output", "submission", "verdict"):
        assert field in CARD, f"run card missing {field!r}"
    assert CARD["verdict"] == "negative"
    assert len(CARD["submission"]["name"]) <= 140
    assert len(CARD["submission"]["note"]) <= 140
    assert CARD["submission_slots_spent"] == 0


def test_gating_first_test_is_the_lane_question_and_did_not_proceed():
    p = E1["arms"]["step"]["summary"]
    s = E1["arms"]["step_abs"]["summary"]
    assert E1["arms"]["step"]["role"] == "primary"
    assert E1["arms"]["step_abs"]["role"] == "secondary"
    assert E1["gate_G1_verdict"] != "PROCEED"
    # the power fix is real: 15x the components of every prior run
    assert p["n_components"] > 3000, "the re-run lost the power it was designed for"
    # the primary is a bounded null: the interval brackets zero and is narrow
    assert p["ci95"][0] < 0 < p["ci95"][1]
    assert (p["ci95"][1] - p["ci95"][0]) < 0.05
    # the central tendency is negative, so the positive mean is a tail effect
    assert p["median"] < 0
    assert p["fraction_positive"] < 0.5
    # the secondary passed, and the diagnostic says why: level, not step
    assert s["verdict"] == "PROCEED"
    d = E1["arms"] and _j("evidence/h74_secondary_diagnostic_logksn.json")["summary"]
    assert d["verdict"] == "PROCEED", "the steepness-level control must reproduce the secondary signal"
    assert d["mean"] > 0.5 * s["mean"], "the level control must explain a large share of the secondary"


def test_off_catalogue_arm_is_significantly_negative():
    o = E1B["summary"]
    assert o["verdict"] == "STOP"
    assert o["mean"] < 0 and o["ci95"][1] < 0, "the off-catalogue reversal must exclude zero"


def test_holdout_is_classed_and_below_the_random_control():
    assert HOLD["evaluator"] == "gems57-pooled-hide-v2"
    assert CARD["holdout_dti"]["evidence_class"] == "HOLDOUT-DTI"
    for row in HOLD["ladder"].values():
        assert 0.0 <= row["pooled_dti"] <= 1.0
        assert "random_mass_control_dti" in row
    top = HOLD["ladder"]["0.0"]
    assert top["pooled_dti"] < top["random_mass_control_dti"], \
        "the lane field must not beat random dots of the same mass"


def test_leakage_canary_is_clean():
    can = _j("evidence/h74_leakage_canary.json")
    assert can, "the canary must have run"
    for name, row in can.items():
        assert row["max_abs_auc"] <= 0.90, f"{name} trips the 0.90 leakage gate"
    assert CARD["leakage_verdict"].startswith("CLEAN")


def test_uniqueness_reports_both_readings_and_the_unsatisfiable_comparators():
    raw = _j("evidence/h74_uniqueness.json")
    assert UNI["max_abs_spearman_all_comparators"] <= 0.90
    assert raw["max_abs_spearman"] <= 0.90
    assert UNI["unsatisfiable_comparators"] > 0, \
        "the dense calibration comparators must still be reported as unsatisfiable"
    # our own NaN-container variant is not a comparator: identical dot pattern by construction
    assert UNI["self_container_variants_excluded"], \
        "the second container of this emission must be excluded, not scored as a duplicate"
    assert UNI["comparators_total"] >= 100
    assert UNI["literal_verdict_all_comparators"] == "FAIL", \
        "the literal 70% clause does fire; that must not be hidden"
    assert UNI["worst_among_satisfiable"]["our_dots_within_3px"] <= 0.70
    assert UNI["literal_verdict_satisfiable_subset"] == "PASS"


def test_raster_matches_its_card_and_the_official_grid():
    tif = ROOT / CARD["raster"]["path"]
    assert tif.is_file()
    assert hashlib.sha256(tif.read_bytes()).hexdigest() == CARD["raster"]["sha256"]
    v = CARD["validator_output"]
    assert (v["bands"], v["dtype"]) == (1, "float32")
    assert v["shape"] == [3730, 3292]
    assert v["crs"] == "EPSG:32611"
    assert v["transform"] == [100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0]
    assert v["nan_inside_footprint"] == 0
    assert 0.0 <= v["min"] and v["max"] <= 1.0
    assert v["problems"] == []
    # the zip must contain exactly one GeoTIFF
    import zipfile
    with zipfile.ZipFile(ROOT / CARD["raster"]["zip"]) as zf:
        names = [n for n in zf.namelist() if not n.startswith("__")]
        assert len(names) == 1 and names[0].endswith(".tif")


def test_the_site_states_both_verdicts_plainly():
    for rel in ("docs/executive-summary.html", "docs/h74-report.html", "docs/index.html",
                "index.html", "README.md"):
        txt = (ROOT / rel).read_text()
        assert "DO NOT SUBMIT" in txt, f"{rel} does not state the submit verdict"
    readme = (ROOT / "README.md").read_text()
    assert "OK TO DOWNLOAD" in readme and "OK TO SUBMIT" in readme
    assert "OK to submit to the competition?" in readme
    assert "Predicted values must be in range [0, 1]" in readme
    assert "DO NOT SUBMIT" in readme.split("## Sources and project values")[0], \
        "the submit verdict must appear before the historical appendix"
