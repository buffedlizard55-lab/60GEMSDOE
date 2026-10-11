"""The published site renders the current review status, not a stale registry recommendation."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs"
STATUS = json.loads((ROOT / "registry" / "current_site_status.json").read_text())
ACTIVE_TIFF = ROOT / STATUS["research_artifact"]["path"]
ACTIVE_NAME = ACTIVE_TIFF.name
# The artifact this session's home page offers.  Legacy pages still link to the historical
# H65-1 research artifact, so both names are accepted as "a research-only TIFF".
CURRENT_TIFF = ROOT / STATUS["home_page_artifact"]["path"]
CURRENT_NAME = CURRENT_TIFF.name
RESEARCH_ONLY_TIFFS = {ACTIVE_NAME, CURRENT_NAME}


def _hrefs(html: str):
    return re.findall(r'(?:href|src)="([^"#]+?)"', html)


def _assert_local_links(page: Path, html: str):
    for rel in _hrefs(html):
        if rel.startswith(("http://", "https://", "mailto:", "data:")):
            continue
        target = (page.parent / rel).resolve()
        assert target.is_file(), f"{page} links at missing file: {rel}"


def test_current_site_status_is_stopped_and_research_only():
    assert STATUS["status"] == "STOP"
    assert STATUS["active_run"] == "H73-1"
    assert STATUS["recommended_competition_submission"] is None
    assert STATUS["submission_slots_used_in_this_review"] == 0
    # The newest run is H73-1, which DID emit one clearly-labelled research GeoTIFF. Emitting a
    # labelled research artifact is allowed under the STOP; promoting one is not.
    assert STATUS["new_tiff_created_in_this_review"] is True
    for key in ("research_artifact", "home_page_artifact"):
        art = STATUS[key]
        assert art["download_ok_for_research"] is True
        assert art["submit_to_competition"] is False, f"{key} must not be submittable while STOPped"
        tif = ROOT / art["path"]
        assert tif.is_file(), f"missing artifact {art['path']}"
        assert hashlib.sha256(tif.read_bytes()).hexdigest() == art["sha256"]
    first = STATUS["latest_first_test"]
    assert first["run"] == "H73-1"
    assert first["result"] in {"INCONCLUSIVE", "STOP"}
    assert first["ci95"][0] < 0 < first["ci95"][1] or first["result"] == "STOP"
    assert "STOP" in first["decision"]
    assert STATUS["latest_holdout"]["not_a_leaderboard_score"] is True


def test_root_pages_link_to_current_research_artifact():
    root_pages = sorted(ROOT.glob("*.html"))
    assert root_pages, "no root .html pages found"
    for page in root_pages:
        html = page.read_text()
        _assert_local_links(page, html)
        hrefs = re.findall(r'(?:href|src)="([^"]*downloads/[^"]+)"', html)
        assert any(Path(h).name in RESEARCH_ONLY_TIFFS for h in hrefs), \
            f"{page.name} links to no research-only TIFF ({sorted(RESEARCH_ONLY_TIFFS)})"
        assert "DO NOT SUBMIT" in html


def test_docs_pages_link_to_current_research_artifact_and_not_a_recommendation():
    pages = sorted(SITE.glob("*.html"))
    assert pages, "docs site is not built"
    for page in pages:
        html = page.read_text()
        _assert_local_links(page, html)
        hrefs = re.findall(r'(?:href|src)="([^"]*downloads/[^"]+)"', html)
        assert any(Path(h).name in RESEARCH_ONLY_TIFFS for h in hrefs), \
            f"{page.name} links to no research-only TIFF ({sorted(RESEARCH_ONLY_TIFFS)})"
        assert "DO NOT SUBMIT" in html, f"{page.name} omits the stop status"


def test_leaderboard_page_matches_manual_snapshot():
    snapshot = json.loads((ROOT / STATUS["leaderboard_snapshot"]).read_text())
    html = (SITE / "leaderboard.html").read_text()
    assert len(snapshot["rows"]) == 50
    assert "xiaofanhu" in html and "0.4133" in html
    assert "DARD" in html and "0.3195" in html
    assert "extradr19" in html and "0.2778" in html
    assert "not this repository's score" in html
    assert "Manual snapshot" in html or "manual snapshot" in html


def test_ranked_hypothesis_backlog_is_explicitly_deferred():
    backlog = (ROOT / "docs/research/next-chi-hypotheses-2026-10-11.md").read_text()
    page = (SITE / "hypotheses.html").read_text()
    for term in ("Paired-basin ksn contrast", "Bedrock-channel confinement", "Hydroclimate- and permanence", "Outlet/base-level-conditioned"):
        assert term in backlog and term in page
    assert "UNTESTED / DEFERRED" in backlog
    assert "NEGATIVE-STOP" in backlog


def test_h65_report_and_readme_preserve_latest_stop_and_h33_attribution_caveat():
    report = (SITE / "h65-report.html").read_text()
    readme = (ROOT / "README.md").read_text()
    assert "INCONCLUSIVE" in report and "Do not rerun the knickpoint lane at" in report
    assert "no organizer receipt ties that score to these exact bytes" in report.lower()
    assert "first experiment for the next session" not in report
    assert "H65-1" in readme and "NOT OK to submit" in readme
    assert "standing brief" in readme.lower()
    assert "remains owner-reported/unverified" in readme


def test_run_card_is_final_negative_and_matches_the_protocol_contract():
    """The run card must carry every field the parallel-run protocol names, and nothing promoted."""
    card = json.loads((ROOT / STATUS["final_run_card"]).read_text())
    for field in ("hypothesis", "mechanism", "named_non_fault_process_that_could_mimic_it",
                  "first_test", "holdout_dti", "uniqueness", "raster", "validator_output",
                  "submission", "verdict"):
        assert field in card, f"run card is missing the protocol field {field!r}"
    assert card["verdict"] == "negative"
    assert card["submission"]["name"] and len(card["submission"]["name"]) <= 140
    assert len(card["submission"]["note"]) <= 140
    assert card["submission"]["download_ok_for_research"] is True
    assert card["submission"]["submit_to_competition"] is False
    assert card["submission_slots_spent"] == 0

    # validator output: no NaN inside the footprint, values in [0,1], grid matches the organiser
    v = card["validator_output"]
    assert v["bands"] == 1 and v["dtype"] == "float32"
    assert v["shape"] == [3730, 3292]
    assert v["crs"] == "EPSG:32611"
    assert v["transform"] == [100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0]
    assert v["nan_inside_footprint"] == 0
    assert v["min"] >= 0.0 and v["max"] <= 1.0
    assert v["problems"] == []

    # the raster on disk is the raster the card names
    tif = ROOT / card["raster"]["path"]
    assert tif.is_file()
    assert hashlib.sha256(tif.read_bytes()).hexdigest() == card["raster"]["sha256"]

    # gates: leakage clean, the preregistered gate not met, uniqueness reported in both readings
    assert card["leakage_verdict"].startswith("CLEAN")
    assert all(v["max_abs_auc"] <= 0.90 for v in card["leakage_canary"].values())
    assert card["first_test"]["gate_G1_verdict"] != "PROCEED"
    assert card["uniqueness"]["verdict_all_comparators"] == "FAIL"
    assert card["uniqueness"]["unsatisfiable_comparators"] > 0
    assert card["uniqueness"]["max_abs_spearman"] <= 0.90

    # every number is classed
    assert card["holdout_dti"]["evidence_class"] == "HOLDOUT-DTI"
    assert "not a leaderboard score" in card["key_numbers_are"]


def test_historic_registry_submission_note_remains_within_portal_budget():
    sub = json.loads((ROOT / "registry" / "submission_build.json").read_text())
    assert len(sub["note"]) <= 200
    assert sub["name"] and sub["file"]["sha256"]


def test_feed_does_not_promote_historic_build_or_scrape_competition_host():
    feed = json.loads((SITE / "data" / "feed.json").read_text())
    assert feed["active_site_status"]["status"] == "STOP"
    assert feed.get("submission") is None
    assert "historical_registry_submission_build" in feed
    assert len(feed["leaderboard"]) == 50
    assert "manual" in feed["leaderboard_retrieval_policy"]
    refresh = (ROOT / "scripts" / "refresh_feed.py").read_text()
    assert "urlopen" not in refresh
    assert "drivendata.org/competitions" not in refresh


def _load_stop_guard():
    import importlib.util
    spec = importlib.util.spec_from_file_location("stop_guard", ROOT / "scripts" / "stop_guard.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_preregistered_stop_blocks_lane_experiment_runners(capsys):
    module = _load_stop_guard()
    assert module.lane_is_stopped(ROOT, "test E2 runner") is True
    assert "STOP GUARD" in capsys.readouterr().out


def test_current_and_archived_channel_runners_are_stop_guarded():
    guarded = (
        "e1_lane_test.py", "e1b_distance_profile.py", "e2_build.py", "e3_validate.py",
        "e61_instrument_audit.py", "e62_lane_thermal.py", "e62b_substrate.py",
        "run_h62.py", "run_lane.py", "run_lane60.py", "build_submission60.py",
        "check_uniqueness60.py", "dem10_block.py", "dem10_merge.py", "build_dem10_cache.py",
    )
    for name in guarded:
        source = (ROOT / "scripts" / name).read_text()
        assert "lane_is_stopped" in source, f"{name} can bypass the registered E1 stop"


def test_dem10_workflow_is_manual_only_and_stops_before_data_preparation():
    workflow = (ROOT / ".github" / "workflows" / "dem10-chi.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "  push:" not in workflow
    assert workflow.count("fail closed on the recorded lane STOP") == 2
    assert "evidence/h65_e1_first_test.json" in workflow
    assert workflow.index("fail closed on the recorded lane STOP") < workflow.index("- name: install")


def test_recorded_h65_inconclusive_e1_cannot_be_overridden_by_active_status(tmp_path, capsys):
    (tmp_path / "registry").mkdir()
    (tmp_path / "evidence").mkdir()
    active = dict(STATUS, status="ACTIVE", recommended_competition_submission={"name": "test-only"})
    active["latest_first_test"] = dict(
        STATUS["latest_first_test"], result="PROCEED", decision="PROCEED",
        evidence="evidence/h65_e1_first_test.json",
    )
    (tmp_path / "registry" / "current_site_status.json").write_text(json.dumps(active))
    (tmp_path / "evidence" / "e1_lane_test.json").write_text(json.dumps({"verdict": "PROCEED"}))
    (tmp_path / "evidence" / "h65_e1_first_test.json").write_text(
        json.dumps({"summary": {"verdict": "INCONCLUSIVE"}})
    )
    assert _load_stop_guard().lane_is_stopped(tmp_path, "test H65 runner") is True
    output = capsys.readouterr().out
    assert "INCONCLUSIVE" in output and "STOP" in output


def test_stop_guard_fails_closed_when_status_is_missing(tmp_path, capsys):
    (tmp_path / "registry").mkdir()
    assert _load_stop_guard().lane_is_stopped(tmp_path, "test E1 runner") is True
    assert "cannot read authoritative lane status" in capsys.readouterr().out
