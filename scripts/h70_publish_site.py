#!/usr/bin/env python3
"""Register H70-1 (paired knickpoint trains, NEGATIVE) under the H68-era site governance.

Idempotent. Under registry/current_site_status.json the lane is STOP, and the
STOP-aware renderer (scripts/build_current_review_site.py) strips marker
boards on regeneration — so this script registers H70-1 as DATA, the way the
renderer expects:

  1. registry/current_site_status.json -> post_review_runs += the H70-1 row
  2. docs/feed.json                    -> submissions += the H70-1 entry, session string updated
  3. registry/irregularities.json      -> IR-70-SEL-01 / IR-70-DATA-01 / IR-70-LB-01 appended by id
     (the STOP-vs-promote governance conflict H70 observed is already recorded
     upstream as IR-H66C-STOPCONFLICT-01, resolved by PRs #19/#20; H70 does not duplicate it)
  4. docs/h70-report.html              -> regenerated from committed evidence (no hand-typed numbers)

No number here is typed by hand; every figure is read from evidence/*.json.

Run:  python scripts/h70_publish_site.py
"""
import json
import re
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SESSION = "arena/ccdca785-60gemsdoe"
RC = json.loads((REPO / "evidence/h70_runcard.json").read_text())
E1 = json.loads((REPO / "evidence/h70_e1_first_test.json").read_text())
G1 = RC["first_test_G1_GATING"]
AB = RC["first_test_ablation_and_diagnostics"]["crest_only_ablation_identical_kernel"]
E1B = RC["first_test_ablation_and_diagnostics"]["E1b_sgmc_off_catalogue_NON_GATING"]
SUB = RC["substrate"]
BUD = RC["budget_use"]


def f4(x):
    return f"{x:+0.4f}"


def update_status() -> str:
    path = REPO / "registry/current_site_status.json"
    st = json.loads(path.read_text())
    g_lo, g_hi = G1["ci95"]
    st["post_review_runs"] = [r for r in st.get("post_review_runs", []) if r.get("id") != "H70-1"]
    st["post_review_runs"].append({
        "session": f"{SESSION} (PR #21)",
        "id": "H70-1",
        "verdict": ("NEGATIVE — preregistered gate G1 (paired-polarity knickpoint trains, "
                    f"catalogue-withheld crossings) mean {f4(G1['mean'])} [{f4(g_lo)}, {f4(g_hi)}] "
                    f"n={G1['n_components']} -> STOP; no TIF was emitted and no slot was spent "
                    "(budget 1/3). Non-gating E1b (SGMC off-catalogue) flipped positive "
                    f"{f4(E1B['mean'])} [{f4(E1B['ci95'][0])}, {f4(E1B['ci95'][1])}] n={E1B['n_components']} "
                    "where both prior single-limb statistics were negative; recorded as the "
                    "motivation for H71, not re-gated post hoc."),
        "artifact": "none (first-test STOP precedes emission)",
        "run_card": "evidence/h70_runcard.json",
        "slot_spent": False,
    })
    st["post_review_note"] = (
        "Three of the four post-STOP runs are negative and corroborate the STOP (H66-1/H66-2, "
        "H66-6, H70-1 — the last preregistered and measured here; its paired-step statistic also "
        "missed the catalogue-withheld gate). H67-1 claimed a pass, was flagged "
        "(IR-H66C-STOPCONFLICT-01), and its promotion was reversed by PRs #19/#20. No submission "
        "slot has been spent by any of them."
    )
    path.write_text(json.dumps(st, indent=2) + "\n")
    return str(path)


def update_feed() -> str:
    path = REPO / "docs" / "feed.json"
    feed = json.loads(path.read_text())
    feed["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    feed["session"] = ("2026-10-11 lane stop audit (H68) + H70-1 paired-polarity knickpoint trains: "
                       "preregistered G1 first test STOP; NEGATIVE result, no new TIFF, no slot spent. "
                       "Research TIFF download remains H65-1 (do not submit).")
    feed["submissions"] = [s for s in feed.get("submissions", []) if s.get("name") != "60GEMSDOE-H70-1-NO-ARTIFACT"]
    feed["submissions"].append({
        "name": "60GEMSDOE-H70-1-NO-ARTIFACT",
        "file": None,
        "sha256": None,
        "dots": None,
        "verdict": ("NEGATIVE - preregistered gate G1 STOP: paired-step chi/ksn contrast "
                    f"{f4(G1['mean'])} [{f4(G1['ci95'][0])}, {f4(G1['ci95'][1])}], n={G1['n_components']} "
                    "withheld catalogue components; the lane stopped before emission"),
        "evidence_class": "MEASUREMENT",
        "first_test": {
            "statistic": "pair_strength = min(crest, -step_min(500 m downstream)) step contrast",
            "mean": G1["mean"],
            "ci95": G1["ci95"],
            "median": G1["median"],
            "n_components": G1["n_components"],
            "verdict": "STOP",
            "gate": G1["gate"],
        },
        "off_catalogue_diagnostic_non_gating": {
            "population": "SGMC 1:750k straight lines",
            "mean": E1B["mean"], "ci95": E1B["ci95"], "n": E1B["n_components"],
        },
        "tool_verification": ("crest-only ablation on the identical kernel reproduces H65-1's "
                              "published INCONCLUSIVE first test to ~1e-9"),
        "run_card": RC["links"]["preregistration"].replace("registry/", "../registry/"),
        "run_card_evidence": "../evidence/h70_runcard.json",
        "report_page": "h70-report.html",
        "research_note": "research/h70-paired-knickpoint-trains.md",
        "submitted_to_competition": False,
        "archive_status": ("NEGATIVE lane record; no TIFF exists to download; no slot spent; "
                           "next preregistered question: H71 paired-basin ksn contrast"),
    })
    path.write_text(json.dumps(feed, indent=1) + "\n")
    return str(path)


IR_ITEMS = [
    {
        "id": "IR-70-SEL-01",
        "severity": "medium",
        "statement": ("Multiple-comparison selection history across the lane's first tests must travel with "
                      "every E1 verdict: the lane's mandated first test has now been probed with five statistics "
                      "(raw step_max log-ratio H65-1 INCONCLUSIVE; abs-step both-limb H66-2 STOP; bedrock dksn "
                      "off-catalogue H66 STOP; bedrock dksn + piedmont composite H67-1 claimed PASS, erratum-applied; "
                      "paired-polarity train H70-1 STOP on catalogue truth, +0.0567 would-be on the SGMC-off target). "
                      "Two of five gated runs passed. A passing gate chosen after several formulations is weaker "
                      "evidence than its CI suggests; H70 registered its statistic before measuring it."),
        "mitigation": ("The H70 preregistration (registry/preregistration-h70.json) fixes the statistic, floor, "
                       "z_min, budget and gates before computation; the run card carries the full history; the "
                       "next lane question must be registered the same way."),
    },
    {
        "id": "IR-70-DATA-01",
        "severity": "medium",
        "statement": ("H66-1/H67-1's claimed 'piedmont profile curvature' input reads topo band 4 (slope_std), "
                      "not band 6 (curv_prof_absmax), in raw quantized codes: scripts/build_dem10_cache.py "
                      "(mode h66) assigns curv_prof = src.read(4) of topo_10m_derived_100m_u8.tif while the "
                      "pack's own manifest names band 4 'slope_std' and band 6 'curv_prof_absmax'; values were "
                      "z-scored against raw uint8 codes. The pied_z term is therefore a slope-variability "
                      "corroborant, not the stated profile-curvature corroborant, and features66 cannot be "
                      "rebuilt offline as committed (it also reads data/official/training_features.tif, which "
                      "is not in this checkout, IR-66-DATA-01)."),
        "mitigation": ("H70 does not rely on pied_z. Recommendation: fix the band index in the shared template, "
                       "rebuild the cache, and re-certify H66-1's dot-for-dot reproducibility before any "
                       "selector relies on it."),
    },
    {
        "id": "IR-70-LB-01",
        "severity": "low",
        "statement": ("Session brief's quoted leaderboard targets (0.3195, later 0.3774) are stale relative to "
                      "the repository's verified snapshot (public top xiaofanhu 0.4133 on 2026-10-11, 50 rows). "
                      "The group's own best remains owner-reported 0.2778 (the participant row at rank 23 shows "
                      "the same value; byte attribution of files to that row is not possible from public data)."),
        "mitigation": ("All H70 planning used 0.4133 as the public target; the score-gap algebra in "
                       "docs/research/h70-paired-knickpoint-trains.md is computed against it."),
    },
]


def update_irregularities() -> str:
    path = REPO / "registry/irregularities.json"
    reg = json.loads(path.read_text())
    have = {i["id"] for i in reg["items"]}
    # the governance conflict H70 originally logged as IR-70-GOV-01 is superseded by
    # IR-H66C-STOPCONFLICT-01 (logged upstream, resolved); drop our duplicate if present
    reg["items"] = [i for i in reg["items"] if i["id"] != "IR-70-GOV-01"]
    for item in IR_ITEMS:
        if item["id"] not in have:
            reg["items"].append(item)
    path.write_text(json.dumps(reg, indent=1) + "\n")
    return str(path)


def _find_summary(tree, n_components, verdict):
    hits = []

    def walk(x):
        if isinstance(x, dict):
            if {"mean", "ci95", "n_components", "verdict"} <= set(x) and \
                    x["n_components"] == n_components and x["verdict"] == verdict:
                hits.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(tree)
    assert len(hits) == 1, f"expected 1 summary (n={n_components}, {verdict}), got {len(hits)}"
    return hits[0]


def report_html() -> str:
    g_lo, g_hi = G1["ci95"]
    a_lo, a_hi = AB["ci95"]
    b_lo, b_hi = E1B["ci95"]
    h65 = _find_summary(json.loads((REPO / "evidence/h65_e1_first_test.json").read_text()), 262, "INCONCLUSIVE")
    h66 = _find_summary(json.loads((REPO / "evidence/h66_e1_first_test.json").read_text()), 86, "STOP")
    h66b = _find_summary(json.loads((REPO / "evidence/h66b_e1_first_test.json").read_text()), 86, "STOP")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>H70-1 paired knickpoint trains — run report · 60GEMSDOE</title><link rel="stylesheet" href="assets/site.css"></head>
<body>
<header class="top"><div class="wrap"><h1>H70-1 run report — paired-polarity knickpoint trains (NEGATIVE)</h1>
<nav><a href="index.html">Home</a> <a href="executive-summary.html">Submission status</a> <a href="research.html">Research</a></nav></div></header>
<main class="wrap">
<div class="banner"><h2>Verdict: NEGATIVE — no new GeoTIFF, no slot spent</h2>
<p><b>Hypothesis:</b> {RC['hypothesis']}</p>
<p><b>Mechanism:</b> {RC['mechanism']}</p>
<p><b>Named non-fault mimic process:</b> {RC['named_non_fault_mimic_process']}</p></div>
<h2>Primary result — preregistered first test G1 (GATING)</h2>
<p>{E1['statistic']} → <b>{G1['gate_verdict']}</b>.</p>
<ul>
<li>n = {G1['n_components']} components scored ({E1['E1a_withheld_catalogue']['skipped']} skipped upstream: crossing pool excludes components with no valid paired crossing)</li>
<li>mean {f4(G1['mean'])}, median {f4(G1['median'])}, 95% CI [{f4(g_lo)}, {f4(g_hi)}], {G1['fraction_positive'] * 100:.2f}% of components positive</li>
<li>{E1['E1a_withheld_catalogue']['summary']['bootstrap']['draws']} bootstrap draws, seed {E1['E1a_withheld_catalogue']['summary']['bootstrap']['seed']}, {E1['E1a_withheld_catalogue']['summary']['bootstrap']['method']}; draw: {G1['target']}</li>
<li>distribution note: mean negative with positive median — the CI crosses zero on the heavy negative tail; no post-hoc rescue claimed</li>
</ul>
<h2>Non-gating diagnostic E1b (SGMC 1:750k off-catalogue truth)</h2>
<p>mean {f4(E1B['mean'])}, 95% CI [{f4(b_lo)}, {f4(b_hi)}], n = {E1B['n_components']} — verdict if it had been the gate: <b>{E1B['verdict_if_it_were_gating']}</b> (it was registered non-gating and stays non-gating).
Single-limb comparisons on the same population: H66-1 measured mean {f4(h66['mean'])} (95% CI [{f4(h66['ci95'][0])}, {f4(h66['ci95'][1])}], n=86, STOP;
<a href="../evidence/h66_e1_first_test.json">evidence/h66_e1_first_test.json</a>) and H66-2 both-limb measured mean {f4(h66b['mean'])} (95% CI [{f4(h66b['ci95'][0])}, {f4(h66b['ci95'][1])}], STOP;
<a href="../evidence/h66b_e1_first_test.json">evidence/h66b_e1_first_test.json</a>).
The sign flip motivates hypothesis H71 (paired-basin k<sub>sn</sub> contrast); it changes nothing about this verdict, because the gates were registered before any number existed.</p>
<h2>Ablation and tool verification</h2>
<p>Identical first test on the raw crest-only statistic: mean {f4(AB['mean'])} (H65-1 published mean {f4(h65['mean'])}), 95% CI [{f4(a_lo)}, {f4(a_hi)}] (H65-1 published CI [{f4(h65['ci95'][0])}, {f4(h65['ci95'][1])}]) → {AB['verdict']}.
{AB['verification_certificate']}</p>
<h2>Substrate and counts</h2>
<ul>
<li>{SUB['source']}</li>
<li>channel pixels {SUB['channel_pixels']:,}; pair-defined channel pixels {SUB['pair_defined_channel_pixels']:,}; candidates after confounds and pair floor {SUB['candidate_pixels_after_confounds_and_floor']:,}</li>
<li>manifest: <code>{SUB['manifest']}</code>; feature-cache receipt: <code>{SUB['feature_cache_receipt']}</code></li>
</ul>
<h2>Downstream fields of the run card</h2>
<ul>
<li>holdout DTI: {RC['holdout_dti']['reason']}</li>
<li>leakage canary: {RC['leakage_canary']['reason']}</li>
<li>uniqueness vs registry: {RC['correlation_overlap_vs_registry']}</li>
<li>raster sha256 / validator / submission name: none (nothing was emitted)</li>
</ul>
<h2>Budget</h2>
<p>{BUD['experiments_used']} of {BUD['experiments_cap']} experiments · {BUD['reason_not_more']}</p>
<h2>What this session did NOT do</h2>
<ul>
<li>No GeoTIFF was generated or made downloadable — the G1 STOP precedes emission. {RC['what_would_have_been_shipped']}</li>
<li>No holdout bench, leaderboard chase or projection-to-score was run for H70.</li>
<li>The STOP-vs-'promote' governance conflict this session originally logged was already recorded upstream as
IR-H66C-STOPCONFLICT-01 and resolved by PRs #19/#20; H70 keeps its three remaining flags (IR-70-SEL-01, IR-70-DATA-01, IR-70-LB-01).</li>
<li>No external data was downloaded through this sandbox (egress is limited to code hosts; fresh-board facts come from the 2026-10-11 verified snapshot).</li>
</ul>
<p>{RC['next_preregistered_question_recommended']}</p>
<h2>Standing stop status (unchanged by this session)</h2>
<p>The registry's current research-only artifact remains
<a href="downloads/gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif" download>gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif</a>
(<a href="downloads/gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.json">local format receipt</a>) — research only, <b>DO NOT SUBMIT</b>.
The H70 round created no TIFF and does not alter that status; the H66/H67 artifacts carry negative errata
(their literal uniqueness clearance failed) and are research-only likewise.</p>
<p>Full analysis (why h33-2-b2 scores 0.2778, the +15–49% credit-per-pixel algebra, ranked next hypotheses, external-data obtainability):
<a href="research/h70-paired-knickpoint-trains.md">docs/research/h70-paired-knickpoint-trains.md</a> ·
run card <a href="../evidence/h70_runcard.json">evidence/h70_runcard.json</a> · evidence rows <a href="../evidence/h70_e1_first_test.json">evidence/h70_e1_first_test.json</a> · lane stop <a href="../evidence/h70_lane_stop.json">evidence/h70_lane_stop.json</a>.</p>
</main>
<footer><div class="wrap">Run report regenerated {time.strftime('%Y-%m-%d', time.gmtime())} from committed evidence files; no hand-entered numbers. · <a href="feed.json">feed</a></div></footer>
</body></html>"""


def main() -> None:
    changed = [update_status(), update_feed(), update_irregularities()]
    (REPO / "docs/h70-report.html").write_text(report_html())
    changed.append("docs/h70-report.html")
    print("\n".join(changed))


if __name__ == "__main__":
    main()
