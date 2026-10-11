"""The published site renders the current review status, not a stale registry recommendation."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs"
STATUS = json.loads((ROOT / "registry" / "current_site_status.json").read_text())
ACTIVE_RECORD = STATUS.get("latest_generated_artifact", STATUS["research_artifact"])
ACTIVE_TIFF = ROOT / ACTIVE_RECORD["path"]
ACTIVE_NAME = ACTIVE_TIFF.name


def _hrefs(html: str):
    return re.findall(r'(?:href|src)="([^"#]+?)"', html)


def _assert_local_links(page: Path, html: str):
    for rel in _hrefs(html):
        if rel.startswith(("http://", "https://", "mailto:", "data:")):
            continue
        target = (page.parent / rel).resolve()
        assert target.is_file(), f"{page} links at missing file: {rel}"


def test_current_site_status_is_stopped_and_research_only():
    assert STATUS["active_run"] == "H65-1"
    assert STATUS["latest_first_test"]["result"] == "INCONCLUSIVE"
    assert STATUS["status"] == "STOP"
    assert STATUS["recommended_competition_submission"] is None
    assert STATUS["new_tiff_created_in_this_review"] is True
    assert STATUS["submission_slots_used_in_this_review"] == 0
    assert ACTIVE_RECORD.get("download_ok", ACTIVE_RECORD.get("download_ok_for_research")) is True
    assert ACTIVE_RECORD["submit_to_competition"] is False
    assert ACTIVE_TIFF.is_file()
    assert hashlib.sha256(ACTIVE_TIFF.read_bytes()).hexdigest() == ACTIVE_RECORD["sha256"]


def test_root_pages_link_to_current_research_artifact():
    root_pages = sorted(ROOT.glob("*.html"))
    assert root_pages, "no root .html pages found"
    for page in root_pages:
        html = page.read_text()
        _assert_local_links(page, html)
        hrefs = re.findall(r'(?:href|src)="([^"]*downloads/[^"]+)"', html)
        assert any(Path(h).name == ACTIVE_NAME for h in hrefs), \
            f"{page.name} does not link to the research-only TIFF {ACTIVE_NAME}"
        assert "DO NOT SUBMIT" in html


def test_docs_pages_link_to_current_research_artifact_and_not_a_recommendation():
    pages = sorted(SITE.glob("*.html"))
    assert pages, "docs site is not built"
    for page in pages:
        html = page.read_text()
        _assert_local_links(page, html)
        hrefs = re.findall(r'(?:href|src)="([^"]*downloads/[^"]+)"', html)
        assert any(Path(h).name == ACTIVE_NAME for h in hrefs), \
            f"{page.name} does not link to the research-only TIFF {ACTIVE_NAME}"
        assert "DO NOT SUBMIT" in html, f"{page.name} omits the stop status"


def test_leaderboard_page_matches_manual_snapshot():
    snapshot = json.loads((ROOT / STATUS["leaderboard_snapshot"]).read_text())
    html = (SITE / "leaderboard.html").read_text()
    assert len(snapshot["rows"]) == 50
    assert "xiaofanhu" in html and "0.4133" in html
    assert re.search(r"<td>2</td><td>cfld__</td><td>0\.3585</td>", html)
    assert re.search(r"<td>9</td><td>DARD</td><td>0\.3195</td>", html)
    assert "extradr19" in html and "0.2778" in html
    assert "same-day top-10 re-read" in html
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
    assert "0.2778 remains owner-reported/unverified" in readme


def test_run_card_is_final_negative_and_discloses_incomplete_gates():
    card = json.loads((ROOT / STATUS["final_run_card"]).read_text())
    assert card["decision"] == "negative"
    assert card["verdict"] == "NEGATIVE"
    assert card["raster_sha256"] == STATUS["research_artifact"]["sha256"]
    assert card["submission_name"] == STATUS["research_artifact"]["submission_name"]
    assert len(card["note"]) <= 140
    assert card["approved_for_weekly_slot"] is False
    assert card["validator_output"]["local_format_preflight_ok"] is True
    assert card["validator_output"]["organizer_acceptance_recorded"] is False
    assert card["uniqueness_gate_pass"] is False
    uniqueness = card["registry_uniqueness_review"]
    assert uniqueness["full_registry_clearance"] is False
    assert uniqueness["checked_registry_rasters"] == 651
    assert uniqueness["expected_registry_rasters"] == 655
    assert uniqueness["max_dot_overlap_within_3px"] == 1.0
    assert uniqueness["pre_placement_surface_spearman_check_documented"] is False
    assert uniqueness["post_placement_final_dot_overlap_check_documented"] is True
    assert card["canary_review"]["full_leakage_clearance"] is True
    assert card["canary_review"]["feature_by_feature_audit"] is True
    assert all(row["max_abs_auc"] <= 0.90 for row in card["canary_review"]["lane_input_rows"])
    assert card["canary_review"]["positive_control"]["leakage_flag"] is True
    assert card["first_test_E1"]["verdict"] == "INCONCLUSIVE"
    assert "PROCEED gate" in card["decision_reason"]


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
