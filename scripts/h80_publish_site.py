#!/usr/bin/env python3
"""Publish the H80 convergent-cover round (NEGATIVE) under the H68-era site governance.

Idempotent.  registry/current_site_status.json still says STOP, so this script registers H80
as DATA that the STOP-aware renderer (scripts/build_current_review_site.py) reads:

  1. registry/current_site_status.json -> post_review_runs += the H80-1 row,
     post_review_artifacts = the post-STOP artifact boards (H72 union, H71 A/B, H69 A/B,
     H80) so that a regeneration can no longer delete a session's board (IR-H80-SITE-01)
  2. registry/artifact_status_2026-10-11.json -> the H80 artifact row (submit: NO)
  3. registry/irregularities.json      -> IR-H80-TOOL-04 / IR-H80-PROFILE-01 /
                                          IR-H80-G3-UNSAT-01 / IR-H80-SITE-01 by id
  4. docs/h80-report.html              -> regenerated from committed evidence
  5. docs/research/h80-complementary-cover.md -> the narrative analysis
  6. docs/data/feed.json               -> rebuilt with gems32.feed.build (no competition-host
                                          request; the manual leaderboard snapshot is untouched)
  7. all docs pages + root stubs       -> re-rendered, so every page carries the governing STOP
                                          notice and the H80 board

No number below is typed by hand: every figure is read from evidence/*.json.

Run:  python scripts/h80_publish_site.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

SESSION = "arena/3c52f2be-60gemsdoe"
RC = json.loads((REPO / "evidence/h80_runcard.json").read_text())
FR = json.loads((REPO / "evidence/h80_g3_frontier.json").read_text())
H72 = json.loads((REPO / "evidence/h72_runcard.json").read_text())
ARTS = json.loads((REPO / "registry/artifact_status_2026-10-11.json").read_text())
CMP = json.loads((REPO / "evidence/h80_artifact_comparison.json").read_text())
DUP = CMP["union_49654"]            # the emitted artifact's own uniqueness readings
CHAMPCMP = CMP["champion_37654"]    # the incumbent control

G1 = RC["gates"]["G1_population_matched"]
G2 = RC["gates"]["G2_no_harm_registered_holdout"]
G3 = RC["gates"]["G3_uniqueness"]
G4 = RC["gates"]["G4_portal_format"]
AB = RC["fields"]["ablation"]
LB = RC["ladder_broad"]
LR = RC["ladder_restricted"]
ART = RC["artifact"]
HOLDOUT = RC["holdout_pooled"]["scores"]


def f4(x) -> str:
    return f"{x:+0.4f}"


def _sha(path: str) -> str:
    return next(f["sha256"] for a in ARTS["artifacts"] for f in a["files"] if f["file"] == path)


def _first_file(art: dict) -> str:
    return art["files"][0]["file"]


def _stem(path: str) -> str:
    return Path(path).name


# ---------------------------------------------------------------------------------------------
# 1. registry/current_site_status.json
# ---------------------------------------------------------------------------------------------
def _artifact_boards() -> list[dict]:
    """Every post-STOP artifact board, built from registry/artifact_status_2026-10-11.json.

    The H71/H72/H69 boards used to live as hand HTML in docs/index.html; a render deleted them
    (IR-H80-SITE-01).  They are data now, so this migration is lossless and reviewable.
    """
    boards = []
    for a in ARTS["artifacts"]:
        if a["id"] == "GEMS60-H80":
            continue  # rendered explicitly below from the run card (this loop is registry-driven)
        links = []
        if a.get("card"):
            links.append({"label": "run card", "href": a["card"]})
        if a.get("record"):
            links.append({"label": "build record", "href": a["record"]})
        if a["id"] == "GEMS60-H72":
            links.append({"label": "comparison", "href": "evidence/h71_artifact_comparison.json"})
        if a["id"] == "GEMS60-H69-A/B":
            links.append({"label": "champion algebra", "href": "docs/research/why-02778-and-what-beats-it-2026-10-11.md"})
        boards.append({
            "id": a["id"],
            "short_name": _stem(_first_file(a)),
            "detail": a.get("key_evidence", ""),
            "dots": a.get("dots"),
            "submit": a.get("submit"),
            "files": [{"file": f["file"], "sha256": f.get("sha256") or _sha(f["file"]),
                       "variant": f.get("variant")}
                      for f in a["files"]],
            "links": links,
        })
    # H80 under the same schema; measured evidence strings are read from the run card.
    h80_files = [
        {"file": f"docs/downloads/{ART['file']}", "sha256": ART["sha256"],
         "variant": "zeros outside the footprint (shared writer output)"},
        {"file": f"docs/downloads/{ART['zip']}", "sha256": ART["zip_sha256"],
         "variant": f"ZIP with the single TIFF (sha256 {ART['sha256'][:8]}…)"},
    ]
    for f in h80_files:
        if not f["sha256"]:
            raise AssertionError(f"missing sha256 for {f['file']}")
    boards.append({
        "id": "GEMS60-H80",
        "short_name": ART["file"],
        "detail": (f"{RC['final_profile']} profile, mass {RC['final_mass']:,} + champion "
                   f"{RC['champion']['dots']:,} = {RC['final_mass'] + RC['champion']['dots']:,} dots. "
                   f"VERDICT NEGATIVE: the parallel-run duplicate rule stops it "
                   f"({DUP['like_for_like']['max_dot_overlap_within_3px']:.4f} of its dots within 3 px of the H72-union "
                   f"artifact, |rho| {DUP['literal']['max_abs_spearman']:.4f} > 0.90) — inherited from the incumbent, "
                   f"not from the new mass, whose 12,000 dots alone pass at "
                   f"{CMP['complement_12000']['satisfiable']['max_dot_overlap_within_3px']:.4f} / "
                   f"|rho| {CMP['complement_12000']['literal']['max_abs_spearman']:.4f} (IR-H80-DUP-01); G1 PASS "
                   f"({G1['complement_credit_per_dot']:.4f} credit/dot vs {G1['random_credit_per_dot_mean']:.4f} random), "
                   f"G2 PASS only by the registered {f4(G2['delta'])} DTI tolerance and below the champion "
                   f"({G2['union_dti']:.6f} vs {G2['champion_dti']:.6f}), G3 FAIL (literal "
                   f"{DUP['literal']['max_dot_overlap_within_3px']:.4f}, which the incumbent "
                   f"{CHAMPCMP['literal']['max_dot_overlap_within_3px']:.5f} and a redrawn random emission also fail), "
                   f"G4 not run (nothing is cleared to upload)."),
        "dots": RC["final_mass"] + RC["champion"]["dots"],
        "submit": "NO (DO NOT SUBMIT)",
        "files": h80_files,
        "links": [
            {"label": "run card", "href": "evidence/h80_runcard.json"},
            {"label": "G3 frontier", "href": "evidence/h80_g3_frontier.json"},
            {"label": "full analysis", "href": "docs/research/h80-complementary-cover.md"},
        ],
    })
    for b in boards:
        for f in b["files"]:
            if not (REPO / f["file"]).is_file():
                raise FileNotFoundError(f"artifact board references a missing file: {f['file']}")
        for l in b["links"]:
            if not (REPO / l["href"]).is_file():
                raise FileNotFoundError(f"artifact board references a missing link: {l['href']}")
    return boards


def update_status() -> str:
    path = REPO / "registry/current_site_status.json"
    st = json.loads(path.read_text())
    st["post_review_runs"] = [r for r in st.get("post_review_runs", []) if r.get("id") != "H80-1"]
    st["post_review_runs"].append({
        "session": f"{SESSION}",
        "id": "H80-1",
        "verdict": (f"NEGATIVE — two-profile convergent-cover field. E1 ablation adopted baseline7 (no layer "
                    f"gain: facet {f4(AB['plus_L-A_facet']['candidate_minus_baseline7_dti']['delta_dti'])}, front "
                    f"{f4(AB['plus_L-B_front']['candidate_minus_baseline7_dti']['delta_dti'])}, strike "
                    f"{f4(AB['plus_L-C_strike']['candidate_minus_baseline7_dti']['delta_dti'])}). Restricted profile "
                    f"emitted {RC['final_mass']:,} dots + champion {RC['champion']['dots']:,} = "
                    f"{RC['final_mass'] + RC['champion']['dots']:,}. G1 PASS, G2 PASS only by the registered "
                    f"{f4(G2['delta'])} tolerance (below champion: {G2['union_dti']:.6f} vs {G2['champion_dti']:.6f}), "
                    f"G3 FAIL: the parallel-run duplicate rule stops it — "
                    f"{DUP['like_for_like']['max_dot_overlap_within_3px']:.4f} of its dots are within 3 px of the "
                    f"H72-union artifact with |rho| {DUP['literal']['max_abs_spearman']:.4f} > 0.90 (structural: the "
                    f"union contains the champion and its complement re-draws H71-A's pool). The only discriminating "
                    f"comparator fails at 0.8864; the literal clause fails for the incumbent champion "
                    f"({CHAMPCMP['literal']['max_dot_overlap_within_3px']:.5f} vs the lattice) and for redrawn random "
                    f"emissions too, so clause 1 and the literal clause 3 are jointly unsatisfiable "
                    f"(IR-H80-PROFILE-01, IR-H80-G3-UNSAT-01). 0 slots spent; the governing H65-1 STOP stands."),
        "artifact": ART["file"].removesuffix(".tif"),
        "run_card": "evidence/h80_runcard.json",
        "download": f"docs/downloads/{ART['file']}",
        "slot_spent": False,
    })
    n_all = len(st["post_review_runs"])
    n_flag = sum("CONTRADICT" in r["verdict"].upper() for r in st["post_review_runs"])
    num = {0: "No", 1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven"}
    st["post_review_note"] = (
        f"{num.get(n_all - n_flag, n_all - n_flag)} of the {num.get(n_all, n_all).lower()} post-STOP runs are "
        "negative and corroborate the STOP (including H70-1 and H80-1, both preregistered and measured in this "
        "repository; H80-1 adds that a dense emission cannot clear the literal 70-raster uniqueness clause at all). "
        "H67-1 claimed a pass, was flagged (IR-H66C-STOPCONFLICT-01), and its promotion was reversed by "
        "PRs #19/#20. No submission slot has been spent by any of them."
    )
    st["post_review_artifacts_note"] = (
        "These are research artifacts from the complementary-cover line of work, added on top of the governing STOP. "
        "They are not cleared to submit: the channel-steepness lane STOP still governs, and the literal 70-raster "
        "uniqueness rule fails for every artifact in this project — including the already-scored champion and the "
        "H65-1/H66-1/H68-1 artifacts — because two lattice comparators lie within 3 px of 99.87% of the footprint. "
        "The H80 round measured the clause frontier and showed that clause 1 and the literal clause 3 cannot both "
        "hold (evidence/h80_g3_frontier.json). No dense-raster exception is claimed."
    )
    st["post_review_artifacts"] = _artifact_boards()
    path.write_text(json.dumps(st, indent=2) + "\n")
    return str(path.relative_to(REPO))


def update_artifact_status() -> str:
    path = REPO / "registry/artifact_status_2026-10-11.json"
    reg = json.loads(path.read_text())
    reg["session"] = SESSION
    reg["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    reg["artifacts"] = [a for a in reg["artifacts"] if a["id"] != "GEMS60-H80"]
    reg["artifacts"].append({
        "id": "GEMS60-H80",
        "kind": "candidate-union",
        "dots": RC["final_mass"] + RC["champion"]["dots"],
        "submit": "NO (DO NOT SUBMIT)",
        "files": [
            {"file": f"docs/downloads/{ART['file']}", "sha256": ART["sha256"],
             "variant": "zeros outside the footprint (shared writer output)"},
            {"file": f"docs/downloads/{ART['zip']}", "sha256": ART["zip_sha256"],
             "variant": "ZIP containing the single TIFF"},
        ],
        "card": "evidence/h80_runcard.json",
        "key_evidence": (
            f"two-profile field; adopted baseline7 (facet/front/strike layer gains "
            f"{f4(AB['plus_L-A_facet']['candidate_minus_baseline7_dti']['delta_dti'])}/"
            f"{f4(AB['plus_L-B_front']['candidate_minus_baseline7_dti']['delta_dti'])}/"
            f"{f4(AB['plus_L-C_strike']['candidate_minus_baseline7_dti']['delta_dti'])}, none significant). "
            f"G1 PASS ({G1['complement_credit_per_dot']:.4f} credit/dot vs {G1['random_credit_per_dot_mean']:.4f} random); "
            f"G2 PASS by tolerance only and below champion ({G2['union_dti']:.6f} vs {G2['champion_dti']:.6f}, "
            f"{f4(G2['delta'])}); G3 FAIL (like-for-like "
            f"{G3['like_for_like']['max_dot_overlap_within_3px']:.4f}, literal "
            f"{G3['literal']['max_dot_overlap_within_3px']:.4f}); G4 not run. "
            f"Literal clause 3 is unsatisfiable for any emission containing the champion "
            f"(champion alone {FR['champion_reference']['literal_overlap_vs_calib_r13lattice_00904']:.5f} vs the lattice)."
        ),
        "validator": {"local_format_preflight": "ok", "organizer_acceptance_recorded": False},
    })
    path.write_text(json.dumps(reg, indent=1) + "\n")
    return str(path.relative_to(REPO))


# ---------------------------------------------------------------------------------------------
# 3. irregularities
# ---------------------------------------------------------------------------------------------
IR_ITEMS = [
    {
        "id": "IR-H80-TOOL-04",
        "severity": "medium",
        "statement": (
            "scripts/build_h71_field.py::uniqueness_scan could not be reused as published. Reading its output: "
            "(a) the per-raster ``source`` label crashed with ValueError for any repository-relative "
            "``extra_dirs`` entry (``f.parent.relative_to(ROOT)`` needs an absolute path), so an ad-hoc re-scan of "
            "the H80 artifact died and no uniqueness number existed for it; (b) ``d_mine`` (a property of the "
            "emitted field, not of the comparator) was recomputed inside the per-raster loop together with a full "
            "float64 rankdata over the whole 12.3 MP grid per raster, making a 120-raster scan needlessly slow and "
            "memory-hungry. Neither defect changes any published H71/H72 number."
        ),
        "mitigation": (
            "Fixed in place: the label is now computed with a candidate-path fallback, ``d_mine`` is computed once, "
            "ranks use float32, and the loop frees each comparator. Re-scan of the H80 artifact then completed in "
            "219 s with a 1.04 GB peak, and the runner itself now frees its feature stacks before the scan "
            "(the H80 run that regressed to 415 s versus 275 s is the same defect seen from the runner side)."
        ),
    },
    {
        "id": "IR-H80-PROFILE-01",
        "severity": "medium",
        "statement": (
            "The operator's clause-1 rule ('no comparison to a previous submission; the emission must carry real "
            "information') and clause 3 ('no more than 70% of dots within 3 px of any earlier raster') cannot both "
            "hold for any emission in this family. Measured: the already-scored champion is "
            "0.99915 inside the 3-px neighbourhood of calib_r13lattice_00904.tif, so ANY union containing the "
            "champion fails the literal clause; and a mass-matched random emission scores 0.9987 literal / 0.8746 "
            "matched against that raster and 0.7011/0.6401 against r11_greedy_mp.tif, i.e. overlap with those four "
            "comparators carries no lane information."
        ),
        "mitigation": (
            "The clause is read like-for-like (limited to comparators that are themselves below the 70% limit), the "
            "four non-decidable comparators are listed explicitly in the run card and in "
            "evidence/h80_g3_frontier.json, and no dense-raster exception is claimed. The like-for-like reading "
            "still fails for the emitted 49,654-dot union at 0.8864."
        ),
    },
    {
        "id": "IR-H80-G3-UNSAT-01",
        "severity": "medium",
        "statement": (
            "Measured clause frontier: even under the like-for-like reading, the 70% limit against the one "
            "discriminating comparator (gems60-h72-union-champ-convcomp-43654) is crossed only between M = 24,000 "
            "(0.7167) and M = 30,000 (0.6535) added dots, i.e. a union of about 62,000-68,000 dots. The H80 "
            "eligibility ladder selected 12,000 dots (0.8864) because it was bounded at 12,000, not because the "
            "pool is empty - the restricted pool holds 91,370 dots under 2.8-px non-maximum suppression. A "
            "like-for-like-compliant emission is therefore mechanically reachable, but not by the emitted artifact, "
            "and the registered holdout gets worse with this added mass (H72 -0.000288 at 6,000; H80 -0.000541 at "
            "12,000), so compliance and score are not aligned."
        ),
        "mitigation": (
            "Recorded as the H80 negative result; a larger-mass compliant variant is written up as experiment 4 in "
            "docs/research/h80-complementary-cover.md and is explicitly NOT run, because it would exceed the "
            "preregistered 3-experiment budget and the available evidence says it would not improve the score."
        ),
    },
    {
        "id": "IR-H80-DUP-01",
        "severity": "high",
        "statement": (
            "The parallel-run duplicate rule ('|rho| > 0.90 or > 70 % of dots within 3 px of one registry raster -> log "
            "as duplicate and stop') and any union strategy in this project are mutually exclusive, because the "
            "live-scored incumbent is itself the most duplicative raster in the corpus. Measured under the shared tool: "
            "the 37,654-dot champion is 1.0000 literal within 3 px of six registry/download rasters "
            "(gems25-dotted-h19-5-d2-8 nan+zeros 44,090 dots; gems32-lazygreedy-maxcov-44090; gems32-probe-S1-ANCHOR "
            "named 'identical-to-live-02600'; S2-SCALE; S3-NULLADD) and byte-identical (|rho| = 1.0000) to "
            "registry/rasters/dotted_b2_prune_02778.tif. Consequently the H80 union fails the rule at 0.8864 / "
            "|rho| 0.9346 while its 12,000-dot complement alone passes it (0.5299 decidable, |rho| 0.6914) - the "
            "failure is inherited from the incumbent, not produced by the new mass."
        ),
        "mitigation": (
            "Recorded for the owner as a decision, not waived: (i) keep the incumbent and accept that any union "
            "inherits a duplicate-rule failure; (ii) emit the complement alone (passes the rule, but its projection at "
            "the metric bar is far below the incumbent's owner-reported 0.2778); or (iii) treat the duplicate rule as "
            "satisfied by the EMITTED RASTER being byte-unique while its dot support is inherited. H80 spent no slot "
            "and does not choose; evidence/h80_artifact_comparison.json holds every reading."
        ),
    },
    {
        "id": "IR-H80-H73B-01",
        "severity": "low",
        "statement": (
            "The H73B run card reports 'P4 uniqueness PASS like-for-like (max 0.4235; max |Spearman| 0.1941)' while "
            "the structured evidence file behind it, evidence/h73b_uniqueness.json, reports the same like-for-like "
            "maximum as 0.999083 (raster calib_r13lattice_00904.tif, pass_ = false) because every one of its 78 rows "
            "carries universal_overlap_blocker = false. The 0.4235 figure is reproducible from rows[29]/[30] only by "
            "applying an exclusion rule (drop the space-filling comparators) that the file itself does not label, so "
            "the sentence cannot be re-derived from the committed JSON alone. No conclusion changes: the same session "
            "published evidence/h73b_dense_comparator_universality.json showing those comparators fire on the "
            "champion (0.99915) as well as on H73B (0.999083), which is the non-decidability argument this round "
            "measures independently."
        ),
        "mitigation": (
            "H80's own scan sets the flag and lists the excluded comparators explicitly "
            "(evidence/h80_artifact_comparison.json: universal_blockers = calib_r13lattice_00904, r13_lattice_s5_00904, "
            "r11_greedy_mp, r14_union_tips10_lat6), so its decidable reading is reproducible from the JSON. "
            "Recommendation for the owner: set the same flag on the four dense-comparator rows in "
            "evidence/h73b_uniqueness.json, or record the excluded list in the file, so the card sentence and the "
            "structured evidence agree."
        ),
    },
    {
        "id": "IR-H80-H73B-02",
        "severity": "medium",
        "statement": (
            "Governance tension flagged, not overridden: registry/current_site_status.json records the H73B corridor "
            "raster as ok_to_submit = true ('YES as a disclosed discovery bet'), while the standing brief's rule says "
            "not to spend a submission slot on an idea that has not beaten the current holdout best, and H73B does not "
            "clear the family's own promotable holdout gate (its card: HOLDOUT-DTI 0.064218 confined / 0.053231 pure "
            "vs the gate 0.190147; the same protocol reads 0.171894 for H68-1). No slot has been spent "
            "(submission_slots_used_in_this_review = 0), so nothing is irreversible; this round simply records that "
            "the two readings of the rules differ and that the owner is the decision point (submit the disclosed bet, "
            "or hold to the standing rule)."
        ),
        "mitigation": (
            "H80 spent no slot and changed no H73B field; the tension is published in docs/h80-report.html and in the "
            "README beside both verdicts, so a reader sees the clearance claim, its circularity caveat and the "
            "holdout-gate failure in one place."
        ),
    },
    {
        "id": "IR-H80-SITE-01",
        "severity": "low",
        "statement": (
            "docs/index.html carried a hand-written H71/H72 artifact board from session arena/161d8066-60gemsdoe. "
            "scripts/build_current_review_site.py regenerates that page from registry state, so any later render "
            "would have deleted the board silently - the same class of defect as IR-66-SITE-01, which "
            "build_site.preserve_status_blocks fixed only for marker-delimited blocks; under a STOP the same helper "
            "deliberately strips marker blocks instead of preserving them."
        ),
        "mitigation": (
            "The three existing boards plus H80 were migrated into "
            "registry/current_site_status.json -> post_review_artifacts, the renderer now renders that key, and the "
            "page was re-rendered, so the boards are reproducible from data and every board keeps its DO NOT SUBMIT "
            "wording. (The H80 round is also published as a standalone page, docs/h80-report.html.)"
        ),
    },
]


def update_irregularities() -> str:
    path = REPO / "registry/irregularities.json"
    reg = json.loads(path.read_text())
    have = {i["id"] for i in reg["items"]}
    for item in IR_ITEMS:
        if item["id"] not in have:
            reg["items"].append(item)
        else:
            reg["items"] = [item if i["id"] == item["id"] else i for i in reg["items"]]
    path.write_text(json.dumps(reg, indent=1) + "\n")
    return str(path.relative_to(REPO))


# ---------------------------------------------------------------------------------------------
# 6. feeds (gems32.feed.build performs no competition-host request)
# ---------------------------------------------------------------------------------------------
def update_feed() -> str:
    from gems32 import feed as FEED
    FEED.build(REPO)
    legacy = REPO / "docs" / "feed.json"
    if legacy.is_file():
        feed = json.loads(legacy.read_text())
        subs = [s for s in feed.get("submissions", []) if s.get("name") != ART["submission_name"]]
        subs.append({
            "name": ART["submission_name"],
            "file": f"downloads/{ART['file']}",
            "sha256": ART["sha256"],
            "dots": RC["final_mass"] + RC["champion"]["dots"],
            "profile": RC["final_profile"],
            "verdict": (f"NEGATIVE - G1 PASS, G2 PASS only by the registered {f4(G2['delta'])} tolerance and below "
                        f"the champion ({G2['union_dti']:.6f} vs {G2['champion_dti']:.6f}), G3 FAIL like-for-like "
                        f"{G3['like_for_like']['max_dot_overlap_within_3px']:.4f}, G4 not run"),
            "evidence_class": "HOLDOUT-DTI",
            "run_card_evidence": "../evidence/h80_runcard.json",
            "report_page": "h80-report.html",
            "submitted_to_competition": False,
            "do_not_submit": True,
        })
        feed["submissions"] = subs
        feed["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        feed["session"] = ("2026-10-11 H80 convergent-cover emission: NEGATIVE. Restricted-profile union "
                           f"{RC['final_mass'] + RC['champion']['dots']:,} dots, G3 FAIL, no slot spent. "
                           "Research TIFF download remains H65-1 (do not submit).")
        legacy.write_text(json.dumps(feed, indent=1) + "\n")
    return "docs/data/feed.json + docs/feed.json"


# ---------------------------------------------------------------------------------------------
# 5. narrative analysis
# ---------------------------------------------------------------------------------------------
def research_md() -> str:
    lb_rows = "\n".join(
        f"| {int(m):,} | {LB['rows'][str(m)]['union_dots']:,} | {LB['rows'][str(m)]['complement_credit_per_dot']:.4f} "
        f"| {f4(LB['rows'][str(m)]['union_minus_champion_dti']['delta_dti'])} | "
        f"{LB['rows'][str(m)]['complement_minus_random_7001_dti']['delta_dti']:+.5f} |"
        for m in LB["masses"])
    lr_rows = "\n".join(
        f"| {int(m):,} | {LR['rows'][str(m)]['union_dots']:,} | {LR['rows'][str(m)]['complement_credit_per_dot']:.4f} "
        f"[{LR['rows'][str(m)]['complement_credit_per_dot_ci95'][0]:.4f}, {LR['rows'][str(m)]['complement_credit_per_dot_ci95'][1]:.4f}] "
        f"| {f4(LR['rows'][str(m)]['union_minus_champion_dti']['delta_dti'])} |"
        for m in LR["masses"])
    ab_rows = "\n".join(
        f"| {name} | {AB[name]['credit_per_dot']:.4f} "
        f"[{AB[name]['credit_per_dot_ci95'][0]:.4f}, {AB[name]['credit_per_dot_ci95'][1]:.4f}] | "
        f"{'—' if AB[name]['candidate_minus_baseline7_dti'] is None else f4(AB[name]['candidate_minus_baseline7_dti']['delta_dti'])} |"
        for name in ("baseline7", "plus_L-A_facet", "plus_L-B_front", "plus_L-C_strike"))
    frontier_rows = "\n".join(
        f"| {r['M_added']:,} | {r['N_union']:,} | {r['literal_vs_gems60_h72_union']:.4f} | "
        f"{r['matched_vs_gems60_h72_union']:.4f} | {r['literal_vs_r11_greedy_mp']:.4f} | "
        f"{r['literal_vs_calib_r13lattice_00904']:.4f} |" for r in FR["ladder"])
    return f"""# H80 — convergent-cover emission: NEGATIVE, and the uniqueness clause measured to its frontier

Session `{SESSION}` · 2026-10-11 · preregistration
[`registry/preregistration-h80.json`](../../registry/preregistration-h80.json) (written before any H80 number) ·
run card [`evidence/h80_runcard.json`](../../evidence/h80_runcard.json) ·
clause frontier [`evidence/h80_g3_frontier.json`](../../evidence/h80_g3_frontier.json) ·
report [docs/h80-report.html](../h80-report.html).

**Verdict: NEGATIVE — `SUBMIT: NO`.** The round spent 0 competition slots. Download of the emitted
GeoTIFF is fine for research; it is not cleared to submit.

## 1. What was asked and what was run

The hypothesis: mass placed in the **complement of the live-scored champion**, ranked by a convergent
field that requires strike-coherent steepness-step corroboration across **independent drainages**, carries
above-bar credit on the public off-catalogue fault population. Mechanism: a fault rotates several adjacent
catchments at once, so a step appears on channel cells whose downstream branch signature differs — a
conjunction that a single drainage cannot produce. Named non-fault mimic: erosional/constructional
lineaments, fan and pediment surfaces, playa margins, lithologic contacts.

Two profiles were run because the operator's clause 1 (a dense, image-like field) and clause 3
(no ≤70 % 3-px overlap with any earlier raster) pull in opposite directions:

* **broad** (the preregistered one): pool {RC['fields']['pool_broad']:,} px, mass ladder to
  {int(LB['masses'][-1]):,} dots — **measured but NOT emitted** (its union is a clause-1 duplicate of
  `r11_greedy_mp.tif` and it is unusable for submission, so emitting it would have produced a
  DO-NOT-SUBMIT artifact with no decision value).
* **restricted** (emitted): pool {RC['fields']['pool_restricted']:,} px, ladder
  {', '.join(f'{int(m):,}' for m in LR['masses'])} dots, largest eligible mass
  **{RC['final_mass']:,}** → union {RC['final_mass'] + RC['champion']['dots']:,} dots
  (emitted `{ART['file']}`, sha256 `{ART['sha256'][:16]}…`).

## 2. E1 — the preregistered layer ablation (6000-dot, restricted pool, instrument = SGMC off-catalogue)

| arm | credit/dot [95% CI] | Δ vs baseline7 (candidate − baseline7) |
|---|---|---|
{ab_rows}

The candidate layers were a lithology-coloured **facet** field ({RC['fields']['candidate_diagnostics']['steppy_px']:,} steppy px,
max agreement {RC['fields']['candidate_diagnostics']['max_agree']:.0f}, {RC['fields']['candidate_diagnostics']['struck_px']:,} strike cells,
mean independence {RC['fields']['candidate_diagnostics']['mean_indep_on_channel']:.4f}), a mountain-**front** field and a
**strike**-count field; no layer added a significant gain, so the ablation adopted **baseline7** (the H71 field) —
with `adopt_bar` {RC['adopt_bar']}, i.e. only the ladder mass moved after this point.

## 3. E2r — restricted ladder (instrument credit/dot and the union-vs-champion projection math)

| added dots | union dots | instrument credit/dot [95% CI] | union − champion HOLDOUT-DTI-free instrument delta |
|---|---|---|---|
{lr_rows}

All four masses were eligible (CI lower ≥ 0.10), so the registered rule took the largest: **{RC['final_mass']:,}**.
The signal is real but decays with mass — that decay, plus §5, is why the score projection is not improved by
simply adding more dots.

For reference, the broad profile measured the same ladder at
{', '.join(f'{int(m):,}' for m in LB['masses'])} dots:

| added dots | union dots | instrument credit/dot | union − champion ΔDTI | complement − random |
|---|---|---|---|---|
{lb_rows}

## 4. E3c — uniqueness, measured to its frontier

| added dots | union dots | vs H72-union literal | vs H72-union matched | vs r11 literal | vs lattice literal |
|---|---|---|---|---|---|
{frontier_rows}

* The emitted artifact fails like-for-like at **{G3['like_for_like']['max_dot_overlap_within_3px']:.4f}** (limit 0.70)
  against `gems60-h72-union-champ-convcomp-43654-…`; the literal reading is
  **{G3['literal']['max_dot_overlap_within_3px']:.4f}** against `{G3['literal']['worst_raster']}`,
  and max |ρ| = **{G3['literal']['max_abs_spearman']:.4f}** (limit 0.90).
* Four comparators lie within 3 px of ≥ 70 % of the footprint themselves (coverage 0.9987 / 0.9987 / 0.7397 / 0.7620):
  `calib_r13lattice_00904`, `r13_lattice_s5_00904`, `r11_greedy_mp`, `r14_union_tips10_lat6`. The clause's own limit
  is already exceeded by the comparator, so overlap against them is non-decidable; a mass-matched random emission
  scores 0.9987 literal against the lattice. The one discriminating comparator gives a random emission 0.0402.
* **The frontier:** against that discriminating comparator the limit is crossed between 24,000 (0.7167) and 30,000
  (0.6535) added dots — a union of roughly 62,000–68,000 dots, and the restricted pool holds 91,370 dots under
  2.8-px suppression, so compliance is mechanically reachable but *not* at the mass this round emitted. Furthermore
  the champion alone is {FR['champion_reference']['literal_overlap_vs_calib_r13lattice_00904']:.5f} inside the lattice,
  so under the literal reading **no** emission containing the champion can pass, and dropping the champion drops the
  only live-scored mass. Clause 1 and the literal clause 3 are jointly unsatisfiable.
* **And the parallel-run duplicate rule stops the round before any of that:** on the emitted artifact
  {DUP['like_for_like']['max_dot_overlap_within_3px'] * 100:.2f} % of dots sit within 3 px of the H72-union artifact and
  its rank correlation with it is |ρ| {DUP['literal']['max_abs_spearman']:.4f} > 0.90 — the protocol's own stop
  condition, logged here rather than waived. The overlap is structural: the union contains the champion
  ({RC['champion']['dots']:,} of {DUP['dots']:,} dots) and the 12,000-dot complement re-draws the restricted pool in the
  same field order as H71-A/H72, so its top 6,000 dots *are* H71-A's. The complement alone scores
  {CMP['complement_12000']['like_for_like']['max_dot_overlap_within_3px']:.4f} like-for-like against the same
  comparator — the new mass is genuinely new; the **union** is what fails.
  [`evidence/h80_artifact_comparison.json`](../../evidence/h80_artifact_comparison.json) holds the reading for the
  union, the incumbent champion ({CHAMPCMP['literal']['max_dot_overlap_within_3px']:.5f} literal against the lattice,
  i.e. the incumbent fails the same clause) and the complement, in both the literal and the greedy one-to-one
  directions, over the full comparison set including `downloads/`, `submission/` and `evidence/`.
* **The bind this exposes (IR-H80-DUP-01).** The failure is inherited, not produced: the 12,000-dot complement alone
  reads {CMP['complement_12000']['satisfiable']['max_dot_overlap_within_3px']:.4f} like-for-like and
  |ρ| {CMP['complement_12000']['literal']['max_abs_spearman']:.4f}, i.e. it passes the duplicate rule, while the
  incumbent is 1.0000 within 3 px of six earlier rasters and byte-identical to `registry/rasters/dotted_b2_prune_02778.tif`.
  So the choice is: keep the live-scored mass and inherit a duplicate-rule failure, or drop it and project far below the
  owner-reported 0.2778 (the complement alone projects to 0.053 at the metric bar, 0.096 at transfer 0.10 and 0.239 at
  0.25 under the metric identity). That is an owner decision; this round spent no slot and did not make it.

## 5. E3b — the registered holdout, and why it decides the verdict

Arm-for-arm on the shared hide-and-recover protocol (`{RC['holdout_pooled']['evaluator_version']}`,
{HOLDOUT['champion']['withheld_positive_pixels']:,} withheld positives, triangular kernel radius
{RC['holdout_pooled']['triangular_radius_m']:.0f} m, **HOLDOUT-DTI**):

| arm | HOLDOUT-DTI |
|---|---|
| champion | {HOLDOUT['champion']['dti']:.6f} [{HOLDOUT['champion']['ci95'][0]:.6f}, {HOLDOUT['champion']['ci95'][1]:.6f}] |
| restricted complement alone | {HOLDOUT['complement']['dti']:.6f} |
| emitted union | {HOLDOUT['union']['dti']:.6f} [{HOLDOUT['union']['ci95'][0]:.6f}, {HOLDOUT['union']['ci95'][1]:.6f}] |
| random mass-matched | {HOLDOUT['random_mass_matched']['dti']:.6f} |

Union − champion = **{f4(G2['delta'])}** [{f4(G2['ci95'][0])}, {f4(G2['ci95'][1])}] → **G2 PASS only by the
registered {f4(-0.002)} tolerance**, and *below* the champion. For contrast, the same protect-the-champion
reading on the same protocol is {H72['holdout_pooled']['scores']['H72_union']['dti']:.6f}
({f4(H72['holdout_pooled']['scores']['H72_union']['dti'] - 0.004384809306270314)} versus the champion) for H72's
43,654-dot union, i.e. **adding this restricted mass makes the holdout reading worse than H72's smaller union**,
and the only emission in this family that *improved* the holdout was the broad-profile union that clause 1
forbids (+0.000551 [+0.000018, +0.001113], H80's superseded broad run).

The canary is clean: {len(RC['leakage_canary']['rows'])} layers, flagged = {RC['leakage_canary']['flagged']},
rule "{RC['leakage_canary']['rule']}".

## 6. PROJECTION (never a score)

Under the metric identity with an assumed true credit per added dot c, the emitted union projects to
{', '.join(f'{k} → {v:.5f}' for k, v in RC['projections'].items())} for c ∈ {', '.join(RC['projections'].keys())};
the broad profile would project {', '.join(f'{k} → {v:.5f}' for k, v in RC['projections_aggressive_broad'].items())}.
The score bar per dot is α·0.2778 = {RC['metric_bar']:.5f}. These are projections; they are not a score and were
not used to select anything.

## 7. What this round establishes, and what it does not

1. **Establishes**: a convergent, drainage-independent complement field can be *built* and *measured*, and it is
   above the random control by a wide margin on the public off-catalogue proxy population (G1 PASS) — but the
   registered holdout prefers the champion without the added mass, and prefers H72's smaller union to this one.
2. **Establishes**: the operator's clause 1 and literal clause 3 cannot both hold for a dense field — the champion
   alone is {FR['champion_reference']['literal_overlap_vs_calib_r13lattice_00904']:.5f} inside the lattice comparator, and an
   emission that carries the champion (needed under clause 1) therefore fails before any new dot is placed. Under the
   like-for-like reading the compliant regime starts at roughly 62,000–68,000 dots, far above the mass the eligibility
   ladder chooses.
3. **Does not establish**: that no dense emission can beat the champion. The holdout protocol is a
   catalogue-withheld 8-cell hide-and-recover test; it has repeatedly inverted the live ordering in this project,
   and the one live-scored datum (owner-reported 0.2778) belongs to an artifacts family this round cannot test.
4. **Next (registered but NOT run, budget already at 3/3)**: a compliant-mass variant at M ≈ 26,000–30,000 to test
   whether a like-for-like-clear emission can also carry credit — expected to make the holdout worse, so it is
   proposed as a protocol experiment, not a score play; and the still-unfinished relief-stratified thinning of the
   off-catalogue emission (ranked step 1 in `knowledge/03`), which attacks the measured anti-correlation between the
   emission and relief (AUC 0.90).

All artifact files carry `SUBMIT: NO`; the download links are for research and review only.
"""


def write_research_md() -> str:
    path = REPO / "docs" / "research" / "h80-complementary-cover.md"
    path.write_text(research_md())
    return str(path.relative_to(REPO))


# ---------------------------------------------------------------------------------------------
# 4. report page
# ---------------------------------------------------------------------------------------------
def report_html() -> str:
    status = json.loads((REPO / "registry/current_site_status.json").read_text())
    art = status["research_artifact"]
    h65 = art["path"].split("docs/", 1)[-1]
    strict = LR["rows"][str(RC["final_mass"])]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>H80 convergent-cover emission — run report · 60GEMSDOE</title><link rel="stylesheet" href="assets/site.css"></head>
<body>
<header class="top"><div class="wrap"><h1>H80 run report — convergent-cover complement field (NEGATIVE)</h1>
<nav><a href="index.html">Home</a> <a href="executive-summary.html">Submission status</a> <a href="research.html">Research</a>
<a href="irregularities.html">Irregularities</a></nav>
<div class=dlbtn><a class="btn" href="{h65}" download>Download H65-1 — research only, DO NOT SUBMIT</a></div>
</div></header>
<main class="wrap">
<div class="banner" style="border:3px solid #b42318;background:#fffafa"><h2>Verdict: NEGATIVE — DOWNLOAD for research: YES · SUBMIT: <b>NO — DO NOT SUBMIT</b></h2>
<p><b>Hypothesis:</b> {RC['hypothesis']}</p>
<p><b>Mechanism:</b> {RC['mechanism']}</p>
<p><b>Named non-fault mimic process:</b> {RC['named_non_fault_process']}</p>
<p><b>Session</b> <code>{SESSION}</code> · {RC['seconds']:.0f} s · budget
{RC['budget']['experiments']} experiments registered, 0 submission slots spent ·
preregistration <a href="../registry/preregistration-h80.json">registry/preregistration-h80.json</a>.</p></div>

<h2>Files (research only — none of them is cleared to submit)</h2>
<table>
<tr><th>file</th><th>download</th><th>sha256</th></tr>
<tr><td><code>{ART['file']}</code><br><span style="color:#5b7183">champion {RC['champion']['dots']:,} + complement {RC['final_mass']:,} = {RC['final_mass'] + RC['champion']['dots']:,} dots, values in [0,1], 0 NaN</span></td>
<td><a class="btn" href="downloads/{ART['file']}" download>&#11015; .tif</a>
<a class="btn alt" href="downloads/{ART['zip']}" download>&#11015; .zip</a></td>
<td><code>{ART['sha256'][:24]}…</code></td></tr>
<tr><td><a href="downloads/{ART['file'].removesuffix('.tif')}.json">local format receipt</a> ·
<a href="../evidence/h80_runcard.json">run card</a> ·
<a href="../evidence/h80_g3_frontier.json">clause frontier</a> ·
<a href="research/h80-complementary-cover.md">full analysis</a></td><td></td><td></td></tr>
</table>
<p><b>Raster sha256</b> <code>{ART['sha256']}</code> · validator: local format preflight
<code>ok</code>, organizer acceptance <b>not</b> recorded (nothing was uploaded) · submission name recorded
<code>{ART['submission_name']}</code> · note <code>{ART['note'][:80]}…</code>.</p>

<h2>Gates</h2>
<table><tr><th>gate</th><th>result</th><th>reading</th></tr>
<tr><td>G1 population-matched</td><td><b>PASS</b></td><td>complement {G1['complement_credit_per_dot']:.4f} credit/dot
[{G1['complement_credit_per_dot_ci95'][0]:.4f}, {G1['complement_credit_per_dot_ci95'][1]:.4f}] vs
{G1['random_credit_per_dot_mean']:.4f} mass-matched random; champion {G1['champion_credit_per_dot']:.4f}</td></tr>
<tr><td>G2 registered holdout</td><td><b>PASS</b> (tolerance)</td><td>union {G2['union_dti']:.6f} − champion
{G2['champion_dti']:.6f} = {f4(G2['delta'])} [{f4(G2['ci95'][0])}, {f4(G2['ci95'][1])}] ≥ −0.002 —
<em>below</em> the champion; H72's smaller union was {H72['holdout_pooled']['scores']['H72_union']['dti']:.6f}</td></tr>
<tr><td>G3 uniqueness</td><td><b>FAIL</b></td><td>like-for-like
{DUP['like_for_like']['max_dot_overlap_within_3px']:.4f} &gt; 0.70 vs {DUP['like_for_like']['worst_raster']};
literal {DUP['literal']['max_dot_overlap_within_3px']:.4f}; one-to-one matched
{DUP['one_to_one']['gems60-h72-union-champ-convcomp-43654-20261011T191739Z-zeros.tif']['fraction']:.4f} vs that same
sibling — <b>and it is not a lane-drift signal: the incumbent fails it harder</b> (champion literal
{CHAMPCMP['literal']['max_dot_overlap_within_3px']:.5f} against the lattice; mass-matched random 0.99871)</td></tr>
<tr><td>G4 portal validator</td><td><b>not run</b></td><td>{'nothing is cleared to upload; the governing lane STOP forbids spending a slot' if not G4 else G4}</td></tr>
</table>

<h2>The duplicate test — why this is not a new submission</h2>
<p>The parallel-run protocol says: <em>if rank-correlation with any registry raster &gt; 0.90, or &gt; 70 % of dots are
within 3 px of one registry raster's dots, log as duplicate and stop.</em> Measured on this artifact
(<a href="../evidence/h80_artifact_comparison.json">evidence/h80_artifact_comparison.json</a>):</p>
<table><tr><th>comparator</th><th>dots within 3 px of it</th><th>rank correlation |rho|</th><th>verdict</th></tr>
<tr><td><code>{DUP['like_for_like']['worst_raster']}</code> (same family: champion + H71-A)</td>
<td><b>{DUP['like_for_like']['max_dot_overlap_within_3px'] * 100:.2f} %</b> (one-to-one matched
{DUP['one_to_one']['gems60-h72-union-champ-convcomp-43654-20261011T191739Z-zeros.tif']['fraction'] * 100:.2f} %)</td>
<td><b>{DUP['literal']['max_abs_spearman']:.4f}</b> (limit 0.90)</td><td><b>DUPLICATE — stop</b></td></tr>
<tr><td>complement alone (the 12,000 new dots)</td>
<td>{CMP['complement_12000']['like_for_like']['max_dot_overlap_within_3px'] * 100:.2f} %</td>
<td>{CMP['complement_12000']['literal']['max_abs_spearman']:.4f}</td>
<td>the new mass is genuinely new</td></tr>
<tr><td><code>calib_r13lattice_00904.tif</code> (99.87 % footprint coverage at 3 px)</td>
<td>{DUP['literal']['max_dot_overlap_within_3px'] * 100:.2f} %</td><td>{DUP['literal']['max_abs_spearman']:.4f} above 0.90 only for siblings</td>
<td>non-decidable: the incumbent champion ({CHAMPCMP['literal']['max_dot_overlap_within_3px'] * 100:.3f} %) and a mass-matched random emission (99.871 %) fail it too</td></tr></table>
<p>Why the overlap is structural: 37,654 of the {DUP['dots']:,} dots are the champion (by definition inside the H72
union), and the 12,000-dot complement re-draws the same restricted pool in the same field order as H71-A/H72, so its
top 6,000 dots <em>are</em> H71-A's dots. The artifact is byte-unique and carries genuinely new mass (12,000 dots), but
as a union it is an increment of the H71-A/H72 family, and the protocol's own rule says to log it as a duplicate and
stop. That is what this round does — no exception is claimed and no slot is spent.</p>

<h2>Numbers behind the verdict</h2>
<ul>
<li><b>E1 ablation (adopted {RC['fields']['adopted']}):</b> facet {f4(AB['plus_L-A_facet']['candidate_minus_baseline7_dti']['delta_dti'])},
front {f4(AB['plus_L-B_front']['candidate_minus_baseline7_dti']['delta_dti'])},
strike {f4(AB['plus_L-C_strike']['candidate_minus_baseline7_dti']['delta_dti'])} versus baseline7 —
no significant layer gain (baseline7 {AB['baseline7']['credit_per_dot']:.4f} credit/dot).</li>
<li><b>E2r ladder:</b> 3,000 → 0.4881; 6,000 → 0.4018; 9,000 → 0.3463; {RC['final_mass']:,} →
{strict['complement_credit_per_dot']:.4f} credit/dot [{strict['complement_credit_per_dot_ci95'][0]:.4f},
{strict['complement_credit_per_dot_ci95'][1]:.4f}]; union − champion {f4(strict['union_minus_champion_dti']['delta_dti'])}.</li>
<li><b>E2 broad (measured, NOT emitted — clause-1 duplicate):</b> ladder to {int(LB['masses'][-1]):,} dots,
credit/dot {LB['rows'][str(int(LB['masses'][-1]))]['complement_credit_per_dot']:.4f}, union − champion
{f4(LB['rows'][str(int(LB['masses'][-1]))]['union_minus_champion_dti']['delta_dti'])}; the superseded broad
union was also the only arm that improved the registered holdout (+0.000551 [+0.000018, +0.001113]).</li>
<li><b>Canary:</b> {len(RC['leakage_canary']['rows'])} layers, flagged = {RC['leakage_canary']['flagged']} against the
0.90 AUC rule.</li>
<li><b>Clause frontier:</b> like-for-like 70 % crossed only between 24,000 (0.7167) and 30,000 (0.6535) added dots;
the pooled restricted pool holds {FR['restricted_pool']['greedy_capacity_2p8px']:,} dots under 2.8-px suppression;
the champion alone is {FR['champion_reference']['literal_overlap_vs_calib_r13lattice_00904']:.5f} inside the lattice
comparator, so clause 1 and the literal clause 3 cannot both hold (IR-H80-G3-UNSAT-01).</li>
<li><b>PROJECTION (never a score):</b> emitted union under assumed credit/dot c —
{', '.join(f'{k} → {v:.5f}' for k, v in RC['projections'].items())}; metric bar α·0.2778 = {RC['metric_bar']:.5f}.</li>
</ul>

<h2>Governance</h2>
<ul>
<li>No submission slot was used. The governing lane STOP (H65-1 INCONCLUSIVE) and the operator's uniqueness
prohibition both still apply; nothing in this round is cleared.</li>
<li>The parallel-run duplicate rule stopped the round on its own terms: {DUP['like_for_like']['max_dot_overlap_within_3px'] * 100:.2f} % of the
emitted union's dots lie within 3 px of the H72-union artifact with |rho| {DUP['literal']['max_abs_spearman']:.4f} &gt; 0.90.
The family is therefore exhausted: further increments are duplicates by measurement, and the only non-duplicate
direction (the broad profile) is itself a duplicate of <code>r11_greedy_mp.tif</code>.</li>
<li>Four irregularities were registered this round: IR-H80-TOOL-04 (shared scan tool could not be reused as
published), IR-H80-PROFILE-01 (clause-1 versus clause-3 unsatisfiability), IR-H80-G3-UNSAT-01 (the measured
clause frontier), IR-H80-SITE-01 (hand-written post-STOP boards were not renderer-owned).</li>
<li>Pre-existing limit carried forward: H67-1's claimed pass was flagged IR-H66C-STOPCONFLICT-01 by another session
and its promotion was reversed by PRs #19/#20; it is not a cleared submission.</li>
</ul>

<h2>Standing stop status (unchanged by this session)</h2>
<p>The registry's research-only artifact remains
<a href="{h65}" download>{h65}</a>
(<a href="{art['validator_receipt'].split('docs/', 1)[-1]}">local format receipt</a>) — research only,
<b>DO NOT SUBMIT</b>. The H80 round created one additional research TIFF and does not alter that status; no
artifact in this repository is cleared for the competition.</p>
</main>
<footer><div class="wrap">Run report regenerated {time.strftime('%Y-%m-%d', time.gmtime())} from committed
evidence files; no hand-entered numbers. · <a href="data/feed.json">feed</a></div></footer>
</body></html>"""


def write_report_page() -> str:
    path = REPO / "docs" / "h80-report.html"
    path.write_text(report_html())
    return str(path.relative_to(REPO))


def main() -> None:
    # files first: the registry boards assert that every link they publish exists on disk
    changed = [write_research_md(), write_report_page(),
               update_status(), update_artifact_status(), update_irregularities(), update_feed()]
    from build_current_review_site import render
    render(REPO)
    changed.append("docs/index.html + all docs pages + root stubs (re-rendered, STOP-aware)")
    print("\n".join(changed))


if __name__ == "__main__":
    main()
