#!/usr/bin/env python3
"""Register the H66 session's hypotheses and irregularities (idempotent).

Same pattern as ``scripts/patch_registries_h33.py``: the registry JSONs are the
source of truth for ``scripts/build_site.py``, so a session adds its rows here
rather than hand-editing the rendered pages.  Re-running is a no-op.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLATE = "H66 (2026-10-11, session arena/970443fc) - ranked after the off-catalogue re-test"

HYPOTHESES = [
    dict(id="H66-1", rank=41, slate=SLATE, slate_rank=1,
         title="Chi/ksn steepness-step corridors mark faults the given catalogue omits; test them "
               "against off-catalogue truth, not against the catalogue",
         layers=["native 3DEP 10 m chi/ksn reduction (data/external/dem10_chi_100m_*.tif)",
                 "USGS SGMC faults rasterised to the grid, minus a 3 px catalogue buffer",
                 "GeoDAWN airborne radiometrics K/Th for the lithology confound"],
         signature="log(ksn_up/ksn_down) two-segment step, blockwise z-scored, corroborated by "
                   ">= 3 independent drainages inside a strike corridor",
         why_off_catalogue="the hidden set is off-catalogue by construction, so the lane must be "
                           "scored against faults the given catalogue omits",
         differs_from_repo="changes the TARGET set, not the detector; every previous lane run gated "
                           "on the catalogue hide-and-recover",
         expected_dti="MEASURED: INSTRUMENT-DTI 0.00630 vs mass-matched random 0.07253 on 62,703 "
                      "off-catalogue px; first test -0.1128 [-0.1738, -0.0437] -> STOP",
         cost="low (all rasters committed)", data_status="in repository, hash-pinned",
         status="EXECUTED 2026-10-11: NEGATIVE. evidence/h66_runcard.json"),
    dict(id="H66-2", rank=42, slate=SLATE, slate_rank=2,
         title="The downstream-steepening limb of the same statistic (max(step_max, -step_min)) is "
               "the signature that survives in alluvial hanging-wall ground",
         layers=["the same 10 m chi/ksn reduction, band step_min as well as step_max"],
         signature="|log ksn ratio| extremum rather than the upstream-only extremum; 53,116 "
                   "candidates in place of 43,131",
         why_off_catalogue="H65's diagnostics put the off-catalogue targets lower in the local "
                           "relief than the catalogue, where the upstream limb is weak "
                           "(Crosby & Whipple 2006, JGR 111 F03014)",
         differs_from_repo="H60-A and H65-1 both used step_max only",
         expected_dti="MEASURED: first test -0.0860 [-0.1372, -0.0220] -> STOP; INSTRUMENT-DTI "
                      "0.00913 vs random 0.07253",
         cost="low", data_status="in repository",
         status="EXECUTED 2026-10-11: NEGATIVE (this is the shipped artefact)"),
    dict(id="H66-3", rank=43, slate=SLATE, slate_rank=3,
         title="Instrument before field: no further detector work until a local statistic "
               "reproduces the live ladder",
         layers=["registry/rasters calibration anchors (12 live-scored artefacts, hash-pinned)",
                 "SGMC off-catalogue truth, terrain-balanced variants",
                 "registry/observations.jsonl"],
         signature="Spearman of each candidate statistic against owner-reported live score; "
                   "leave-one-anchor-out so one artefact cannot carry the correlation. Measured "
                   "this session: SGMC off-catalogue credit-per-pixel orders the top five live "
                   "scores exactly (0.1488 > 0.1409 > 0.1368 > 0.1288 > 0.1056 for live 0.2778 > "
                   "0.2708 > 0.2632 > 0.2600 > 0.2477) and its one large violation is the dense "
                   "r13 lattice (0.1155 at live 0.0904)",
         why_off_catalogue="the selector, not the field, is the binding constraint: the instrument "
                           "the family gates on ranks the 0.2778 champion last of twelve",
         differs_from_repo="e61 measured the correlation once with n = 12 and no resampling; this "
                           "adds leave-one-out CIs and a preregistered acceptance threshold",
         expected_dti="UNVALIDATED; it does not emit, it decides what may be emitted",
         cost="low (rasters already committed)", data_status="in repository",
         status="PROPOSED - first experiment of the next session"),
    dict(id="H66-4", rank=44, slate=SLATE, slate_rank=4,
         title="Coverage-first screening: measure what fraction of off-catalogue trace a detector's "
               "support can reach BEFORE fitting it",
         layers=["any candidate support mask (channels, scarps, lineaments, basin edges)",
                 "SGMC off-catalogue truth"],
         signature="share of off-catalogue fault pixels with detector support within 300 m, "
                   "against the footprint background",
         why_off_catalogue="measured this session: of 1,200 sampled off-catalogue segments only 124 "
                           "are >= 600 m long and 38 of those have no bedrock channel within 3 px - "
                           "a channel-based detector cannot see them at any resolution",
         differs_from_repo="no session has screened support coverage before running a detector; "
                           "four lane runs were spent finding it after the fact",
         expected_dti="UNVALIDATED; a gate, not an emitter",
         cost="very low", data_status="in repository",
         status="PROPOSED"),
    dict(id="H66-5", rank=45, slate=SLATE, slate_rank=5,
         title="Mass-thrift sweep on the champion's own field at the metric's break-even point",
         layers=["registry/rasters/dotted_b2_prune_02778.tif (owner-reported 0.2778)",
                 "gems52.metric credit bar 0.2 * DTI"],
         signature="DTI as a function of emitted mass for one fixed field; the stationary point is "
                   "where the marginal dot's realised credit equals 0.2 * DTI",
         why_off_catalogue="irrelevant to detection: this is the emission lever, and minus-mass is "
                           "the strongest single correlate of live score measured here "
                           "(Spearman +0.9371, n = 12)",
         differs_from_repo="the family thinned by eye (d1.5 -> d2.8 -> b2); nobody has swept mass "
                           "on the champion field and located the metric's own break-even",
         expected_dti="UNVALIDATED; bounded upside, bounded downside, cheapest experiment available",
         cost="very low", data_status="in repository",
         status="PROPOSED"),
]

IRREGULARITIES = [
    dict(id="IR-66-INST-01", severity="high",
         statement="The catalogue hide-and-recover DTI - the gate every knickpoint-lane run in this "
                   "repository has cited - is rank-ANTI-correlated with the live board: Spearman "
                   "-0.9021 against owner-reported live scores over 12 live-scored family artefacts "
                   "(evidence/e61_instrument_audit.json). It gives the 0.2778 champion the lowest "
                   "catalogue credit-per-pixel of the twelve (0.0100) while the artefact with the "
                   "highest (0.2296, h28-ridge, live 0.1839). Any verdict that read a low "
                   "catalogue-holdout DTI as evidence "
                   "of 'no skill' was measured with an instrument that ranks the group's own best "
                   "file last.",
         mitigation="H66 re-ran the lane's mandated first test and its DTI against the only local "
                    "truth set containing off-catalogue faults (SGMC > 300 m from the catalogue) and "
                    "labels every such number INSTRUMENT-DTI, never HOLDOUT-DTI. Next session: "
                    "H66-3 (instrument before field)."),
    dict(id="IR-66-DUP-01", severity="high",
         statement="The first H66 emission, built at the lane's declared parameters on the native "
                   "10 m cache, put 75.72% of its 37,654 dots within 3 px of the previous session's "
                   "gems60-h65-dem10-knick file (Spearman 0.7141), tripping the parallel-run "
                   "protocol's 70% co-location gate. Changing only the confound mask and the dot "
                   "budget moved about a quarter of the dots: a lane run that reuses the declared "
                   "parameters cannot produce a unique artefact.",
         mitigation="that emission was never published to docs/downloads/; it is kept in "
                    "evidence/superseded/ with evidence/superseded/README-h66.md. The shipped H66 "
                    "file uses the other limb of the same statistic and clears both literal gates "
                    "against all 57 sparse, submission-like rasters (worst |rho| 0.5411, worst 3-px "
                    "share 0.6105)."),
    dict(id="IR-66-DATA-01", severity="medium",
         statement="The 419 MB training_features.tif is not in git (GitHub 100 MB blob limit) and is "
                   "absent from this sandbox, so H60-A's declared lithology / basin-fill confound "
                   "masks (band 15 depth_to_base p90, band 17 cond_surf p95) could not be computed. "
                   "The pinned GeoDAWN airborne-radiometric pack (K p95, Th p95) was substituted; "
                   "893,496 px (17.3% of the footprint) are excluded instead of the H60-A set.",
         mitigation="scripts/run_lane60.confound_masks now fails closed to the substitute only when "
                    "training_features.tif is missing, uses it unchanged when present (so H60-A and "
                    "H65-1 still reproduce), and writes lithology_source into every receipt."),
    dict(id="IR-66-LB-01", severity="low",
         statement="The live leaderboard could not be re-read this session: drivendata.org is not "
                   "reachable from the sandbox (HTTPS returned 000 for the leaderboard URL, while "
                   "api.github.com and pypi.org returned 200). The 0.4133 figure quoted on this site "
                   "is the repository's last recorded reading (2026-10-11, H65 session), not a "
                   "measurement made now. The brief's 0.3774 and 0.3195 are older still.",
         mitigation="labelled as a recorded reading everywhere it appears; "
                    ".github/workflows/probe-egress.yml runs the fetch on a runner."),
    dict(id="IR-66-BUDGET-01", severity="low",
         statement="The parallel-run protocol declares a budget of 3 experiments. This session ran "
                   "4 measurement rounds: E1a, E1b, E2, and then a second E1b+E2+emission pair "
                   "because the first emission failed the uniqueness gate and had to be re-emitted "
                   "on a different limb of the same statistic.",
         mitigation="declared in evidence/h66_runcard.json under budget_note rather than absorbed "
                    "silently; wall-clock was inside the 2-hour limit."),
    dict(id="IR-66-STOP-01", severity="high",
         statement="PR #15 (session arena/6429039c-60gemsdoe) installed an authoritative lane STOP "
                   "for channel-steepness (registry/current_site_status.json, active_run H65-1, "
                   "'No follow-up experiment or submission is authorized') plus a fail-closed "
                   "scripts/stop_guard.py that blocks run_lane60.py and check_uniqueness60.py. It "
                   "landed on main WHILE this session was measuring, on a branch cut before it, so "
                   "H66's four measurement rounds ran the stopped lane with no guard in the tree. "
                   "Two parallel sessions reached opposite process conclusions in the same lane on "
                   "the same day.",
         mitigation="the H66 result is NEGATIVE at both targets (catalogue and off-catalogue), so it "
                    "corroborates the stop instead of contradicting it and the stop stays in force. "
                    "scripts/run_h66.py and scripts/check_uniqueness66.py now call the same "
                    "lane_is_stopped guard; both were executed after the merge and printed 'STOP "
                    "GUARD ... not run' while writing no evidence (verified). The archived "
                    "evidence/h66b_*.json files are the record; the reproduction command in README "
                    "now no-ops by design and must not be forced without separate authorization."),
    dict(id="IR-66-SITE-01", severity="medium",
         statement="scripts/build_site.py re-renders docs/index.html, docs/executive-summary.html "
                   "and the nine root redirect stubs from the registry, and until this session it "
                   "DELETED every parallel session's marker-delimited status board while doing so. "
                   "Three sessions publishing in sequence on 2026-10-11 therefore silently removed "
                   "each other's 'is this file OK to submit?' read-outs. Unmarked hand-inserted "
                   "banners are still replaced: the GEMS61 banner on the root redirect stubs was "
                   "lost when this session regenerated the site.",
         mitigation="build_site.py now carries preserve_status_blocks(), and "
                    "build_current_review_site.py (the 'active stop review' renderer added by PR #15, "
                    "which deletes the boards just the same) imports that one implementation for all "
                    "11 of its page writes, so regeneration is safe for every publisher that uses the "
                    "marker convention. Verified: after the merge, build_site.py in stop-review mode "
                    "leaves the H65 and H66 boards in place. Both artifacts named in the lost banner remain in "
                    "docs/downloads/ and are linked from docs/index.html. Any future insertion "
                    "into a generated page must use the marker convention."),
    dict(id="IR-66-GATE-01", severity="medium",
         statement="The literal 3-px co-location uniqueness gate fires against large dense priors "
                   "for ANY sparse dot set: calib_r13lattice_00904.tif (206,895 dots) co-locates "
                   "with 99.94% of the H66 dots, but a mass-matched random dot set co-locates with "
                   "67.63% of the same raster, and the rank correlation is +0.0018. The gate "
                   "therefore cannot distinguish copying from co-location on its own.",
         mitigation="scripts/check_uniqueness66.py reports a 5-draw mass-matched random control and "
                    "the excess over it for every row, splits the corpus into sparse "
                    "(<= 100,000 dots) and large priors, and applies the literal gates to the sparse "
                    "population, which is what the protocol's 'drifted into another lane' rule is "
                    "about."),
]


def patch(path: Path, key: str, rows: list[dict]) -> tuple[int, int]:
    d = json.loads(path.read_text())
    have = {r["id"] for r in d[key]}
    added = 0
    for r in rows:
        if r["id"] in have:
            continue
        d[key].append(r)
        added += 1
    if key == "hypotheses":
        d["updated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
    return added, len(d[key])


def main() -> int:
    a, na = patch(ROOT / "registry/hypotheses.json", "hypotheses", HYPOTHESES)
    b, nb = patch(ROOT / "registry/irregularities.json", "items", IRREGULARITIES)
    print(f"hypotheses: +{a} (now {na}); irregularities: +{b} (now {nb})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
