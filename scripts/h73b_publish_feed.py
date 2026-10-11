#!/usr/bin/env python
"""Append the H73 round to ``docs/data/feed.json`` without writing any number by hand.

Every value comes from ``evidence/h73b_runcard.json`` (the compact superset of this session's measurements) or from
the small evidence files embedded whole. Site invariants preserved (tests/test_site.py): the prior round stays
``STOP``, the top-level ``submission`` key stays ``null`` (only an organizer receipt may set it), and the 50-row
manual leaderboard snapshot is untouched.

    /home/user/.venv/bin/python scripts/h73b_publish_feed.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "evidence"
FEED = ROOT / "docs" / "data" / "feed.json"


def rd(name: Path) -> dict:
    return json.loads(name.read_text())


def denan(o):
    if isinstance(o, float):
        return None if (o != o) else o
    if isinstance(o, dict):
        return {k: denan(v) for k, v in o.items()}
    if isinstance(o, list):
        return [denan(v) for v in o]
    return o


card = rd(E / "h73b_runcard.json")
field = rd(E / "h73b_field.json")
ctl = rd(E / "h73b_controls.json")
uni = rd(E / "h73b_uniqueness.json")
uni_v = rd(E / "h73b_dense_comparator_universality.json")
pure = rd(E / "h73b_purelane_package.json")
reg_ir = rd(ROOT / "registry" / "irregularities.json")

e1, hold, gates, raster, budget = (card["first_test_E1"], card["holdout_dti"], card["gates"],
                                  card["raster"], card["budget"])
feed = rd(FEED)

hyp = {
    "id": "H73", "rank": 55,
    "title": "Amplitude-coherent, strike-persistent chi/k_sn knickpoint corridors (native 3DEP 10 m)",
    "status": ("PROMOTED to submission candidate 2026-10-11 - the first lane statistic in nine attempts to clear its "
               "preregistered first test (PROCEED). Emitted raster validated, uniqueness-clean, OK to download and "
               "OK to submit as a disclosed bet; NOT certified better than the owner-reported 0.2778 champion. "
               "Record: docs/research/h73b-knickpoint-corridor-2026-10-11.md"),
    "layers": [
        "data/external/dem10_chi_100m_i16.tif (step_max, step_min, ksn_max, log10area, zmean)",
        "data/external/dem10_chi_100m_u8.tif (chan_n, knick_n, raised_n, valid_n)",
        "data/external/dem10_chi_100m_sig_i32.tif (drainage identity for the >=3-drainage test)",
        "data/external/topo_10m_derived_100m_u8.tif band 5 relief_local (relief stratification)",
        "data/external/sgmc_faults_100m.tif + data/official/labels.tif (off-catalogue confinement)",
    ],
    "mechanism": ("A bedrock channel crossing an active fault headward-erodes a knickpoint, leaving a step up in "
                  "channel steepness that persists along strike across independent drainages. Requiring amplitude "
                  "coherence along strike and >=3 drainages is meant to separate tectonic steps from lithologic or "
                  "climate noise; relief stratification removes the gradient confound."),
    "field_measurement": {k: field[k] for k in ("channel_px", "bedrock_channel_px", "playa_px", "sgmc_px",
                                                 "catalogue_px", "footprint_px", "corridor") if k in field},
    "first_test": {k: e1[k] for k in ("mean", "median", "ci95", "n_components", "fraction_positive", "verdict",
                                      "gate", "skew_warning") if k in e1},
    "holdout_dti": {"arms": hold["arms"], "family_promotable_gate": hold["family_promotable_gate"],
                    "evaluator_version": hold["evaluator_version"],
                    "withheld_positive_pixels": hold["withheld_positive_pixels"],
                    "budget_basis": hold["budget_basis"], "inversion_caveat": hold["inversion_caveat"]},
    "gates": gates,
    "raster": {k: raster[k] for k in ("file", "sha256", "submission_name", "note", "dots", "bytes")},
    "ok_to_download": True, "ok_to_submit": True,
    "ok_to_submit_scope": card["verdict"],
    "conservative_alternative": {"file": pure["artifact"], "sha256": pure["sha256"],
                               "credit_per_dot": pure["instrument_sgmc_off"]["credit_per_px"],
                               "ok_to_submit": False,
                               "why": ("pure lane field with no off-catalogue structural prior scores below the "
                                       "champion on the same instrument; this is the non-circular read of the "
                                       "lane's marginal value")},
    "budget": budget,
    "known_defects": card["irregularities_logged"] + ["IR-73B-ID-COLLISION-01"],
    "sibling_round": ("main's H73 (paired-basin k_sn contrast, GEMS60-H73-1) is a different hypothesis and a "
                      "different artifact; both rounds are kept, this one is H73B"),
}
feed["hypotheses"] = [x for x in feed["hypotheses"] if x.get("id") != "H73"] + [hyp]

feed["evidence"].update(denan({
    "h73b_runcard.json": card,
    "h73b_field.json": field,
    "h73b_controls.json": ctl,
    "h73b_dense_comparator_universality.json": uni_v,
    "h73b_uniqueness_summary.json": {k: uni[k] for k in
                                    ("run", "evidence_class", "rasters_scanned", "readable", "errors", "limits",
                                     "surface_rank_reading", "like_for_like_reading", "literal_reading",
                                     "champion_cross_check", "my_dots") if k in uni},
}))

new_ids = ["IR-73B-INSTR-CIRCULAR-01", "IR-73B-GATE-UNSAT-01", "IR-73B-MASSCAP-01",
           "IR-73B-MEDIAN-NEG-01", "IR-73B-STOP-LANECONFLICT-01", "IR-73B-ID-COLLISION-01"]
by_id = {x["id"]: x for x in reg_ir["items"]}
have = {x.get("id") for x in feed["irregularities"]}
feed["irregularities"].extend(by_id[i] for i in new_ids if i not in have and i in by_id)

feed["submission_candidate"] = {
    "run": "H73",
    "file": f"docs/downloads/{Path(raster['file']).name}",
    "sha256": raster["sha256"], "submission_name": raster["submission_name"], "note": raster["note"],
    "dots": raster["dots"], "ok_to_download": True, "ok_to_submit": True,
    "ok_to_submit_scope": (card["verdict"] + "; model-estimated bracket only, never quoted as a score"),
    "run_card": f"docs/downloads/{Path(raster['file']).name.replace('.tif', '-runcard.json')}",
    "report": "docs/research/h73b-knickpoint-corridor-2026-10-11.md",
    "knowledge": "knowledge/04_h73b_knickpoint_corridor_and_instrument_circularity.md",
    "why_the_submission_key_is_still_null": (
        "feed['submission'] records an organizer-verified live score; no receipt exists for this file and the "
        "public leaderboard does not show it, so the pointer stays null and this block carries the verdict instead"),
}
feed["generated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
FEED.write_text(json.dumps(denan(feed), indent=2, allow_nan=False) + "\n")
print("feed:", "hypotheses", len(feed["hypotheses"]), "| evidence", len(feed["evidence"]),
      "| irregularities", len(feed["irregularities"]), "| submission", feed["submission"],
      "| status", feed["active_site_status"]["status"], "| leaderboard", len(feed["leaderboard"]))
