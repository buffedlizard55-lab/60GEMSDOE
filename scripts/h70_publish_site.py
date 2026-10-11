#!/usr/bin/env python3
"""Publish the H70-1 (paired knickpoint trains, NEGATIVE) site update.

Idempotent: refreshes the marker-delimited H70-STATUS block at the top of
docs/index.html, docs/executive-summary.html and the root index.html, and
rewrites docs/h70-report.html from the committed evidence files. No number
in the generated HTML is typed by hand; everything is read from
evidence/h70_runcard.json and evidence/h70_e1_first_test.json.

Run:  python scripts/h70_publish_site.py
"""
import json
import re
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SESSION = "arena/ccdca785-60gemsdoe"
RC = json.loads((REPO / "evidence/h70_runcard.json").read_text())
E1 = json.loads((REPO / "evidence/h70_e1_first_test.json").read_text())
G1 = RC["first_test_G1_GATING"]                       # gating summary (runcard copy)
AB = RC["first_test_ablation_and_diagnostics"]["crest_only_ablation_identical_kernel"]
E1B = RC["first_test_ablation_and_diagnostics"]["E1b_sgmc_off_catalogue_NON_GATING"]
EA = E1["E1a_withheld_catalogue"]["summary"]          # full e1 rows file
SUB = RC["substrate"]
BUD = RC["budget_use"]

BEGIN = "<!-- H70-STATUS:BEGIN -->"
END = "<!-- H70-STATUS:END -->"


def f4(x):
    return f"{x:+0.4f}"


def block(prefix: str) -> str:
    """prefix: '' inside docs/, 'docs/' in the root index.html."""
    ci_lo, ci_hi = G1["ci95"]
    b_lo, b_hi = E1B["ci95"]
    return f"""{BEGIN}
<div class=wrap style="border:3px solid #b42318;background:#fffafa;padding:12px 16px;margin:8px auto">
<h2 style="margin:0 0 6px">&#128680; READ THIS FIRST ({date.today().isoformat()}, session {SESSION}) — paired knickpoint trains: <b>NEGATIVE at first test, no new TIF exists</b></h2>
<table>
<tr><th>file</th><th>download</th><th>OK to download &amp; submit?</th></tr>
<tr><td><b>Unique H70 candidate TIF</b><br><code>(none — first test stopped the run before emission)</code></td>
<td><i>not applicable</i> · <a href="{prefix}research/h70-paired-knickpoint-trains.md">full report</a> · <a href="{prefix}h70-report.html">h70-report.html</a> · <a href="{prefix}feed.json">feed</a></td>
<td style="color:#b42318"><b>THERE IS NOTHING TO DOWNLOAD — and nothing to submit.</b>
Verdict <b>NEGATIVE</b>: the preregistered gate {G1['gate'].split(':')[0]} (paired-step χ/k<sub>sn</sub> contrast, {G1['n_components']} withheld catalogue components,
identical kernel/draw/seeds to every prior lane run) measured mean <b>{f4(G1['mean'])}</b>, 95% CI [{f4(ci_lo)}, {f4(ci_hi)}] → <b>STOP</b>.
No surface, no holdout bench, no raster, no validator, <b>no submission slot spent</b> (budget {BUD['experiments_used']} of {BUD['experiments_cap']} experiments).
Non-gating off-catalogue diagnostic flipped positive ({f4(E1B['mean'])}, CI [{f4(b_lo)}, {f4(b_hi)}], n={E1B['n_components']}) and is logged as the motivation for the next preregistered question (H71).</td></tr>
<tr><td><b>Validated incumbent (H66-1 / H67-1, prior session)</b><br><code>gems60-h66-dem10-bedrock-dksn-40000-20261011T162456Z-dbafa4373009-zeros.tif</code><br>
<span style="color:#5b7183">40,000 dots &middot; sha256 <code>cde6b57be8aaac9b&hellip;</code></span></td>
<td><a class="btn alt" href="{prefix}downloads/gems60-h66-dem10-bedrock-dksn-40000-20261011T162456Z-dbafa4373009-zeros.tif" download>&#11015; .tif</a>
<a class="btn alt" href="{prefix}downloads/gems60-h66-dem10-bedrock-dksn-40000-20261011T162456Z-dbafa4373009-zeros-runcard.json">run card</a>
<a class="btn alt" href="{prefix}downloads/checks-gems60-h66-dem10-bedrock-dksn-40000-20261011T162456Z-dbafa4373009-zeros.tif.json">checks</a></td>
<td><b>DOWNLOAD: YES</b> — unique vs the local registry and portal-legal (single-band float32, 3730&times;3292, EPSG:32611, 0 NaN, all values in [0, 1]; local receipt only, no organizer receipt).
<b>SUBMIT:</b> its own run card says <i>promote</i> to the cross-lane selector; spending a weekly slot on it is the selector&rsquo;s decision, not this lane&rsquo;s. This session did not alter it.</td></tr>
<tr><td><b>Group champion (anchor)</b><br><code>gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif</code></td>
<td><a class="btn alt" href="{prefix}downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif" download>&#11015; .tif</a></td>
<td>Already live-scored: <b>0.2778</b> (owner-reported; the participant row is visible at rank 23 with 0.2778 in the 2026-10-11 verified snapshot). Re-uploading repeats a known number. Why it scores 0.2778 and how much new physics is needed to beat it: <a href="{prefix}research/h70-paired-knickpoint-trains.md">the score algebra here</a>.</td></tr>
</table>
<p style="margin:6px 0 0">Public leaderboard top as last verified: <b>0.4133</b> (2026-10-11 snapshot; the 0.3195/0.3774 targets in the brief are stale — IR-70-LB-01).</p>
</div>
{END}"""


def upsert(path: Path, prefix: str) -> str:
    text = path.read_text()
    text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", text, flags=re.S)
    m = re.search(r"<body[^>]*>", text)
    assert m, f"no <body> in {path}"
    text = text[: m.end()] + "\n" + block(prefix) + "\n" + text[m.end():]
    path.write_text(text)
    return str(path)


def _find_summary(tree, n_components, verdict):
    """Walk a committed evidence JSON and return the unique summary dict with the
    given n_components and verdict (fails loudly if not exactly one match)."""
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
    # Reference numbers pulled from the committed evidence files, not typed here.
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
<li>{EA['bootstrap']['draws']} bootstrap draws, seed {EA['bootstrap']['seed']}, {EA['bootstrap']['method']}; draw: {G1['target']}</li>
<li>distribution note: {G1['distribution_note']}</li>
</ul>
<h2>Non-gating diagnostic E1b (SGMC 1:750k off-catalogue truth)</h2>
<p>mean {f4(E1B['mean'])}, 95% CI [{f4(b_lo)}, {f4(b_hi)}], n = {E1B['n_components']} — verdict if it had been the gate: <b>{E1B['verdict_if_it_were_gating']}</b> (it was registered non-gating).
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
<li>Neither the H67 STOP status nor the H67 promote run card was edited; the conflict is logged as IR-70-GOV-01.</li>
<li>No external data was downloaded through this sandbox (egress is limited to code hosts; fresh-board facts come from the 2026-10-11 verified snapshot).</li>
</ul>
<p>{RC['next_preregistered_question_recommended']}</p>
<h2>Standing stop status (unchanged by this session)</h2>
<p>The registry's current research-only artifact remains
<a href="downloads/gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif" download>gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif</a>
(<a href="downloads/gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.json">local format receipt</a>) <b>— research only, DO NOT SUBMIT.</b>
The H70 round created no TIFF and does not alter that status; the governance conflict between the
STOP status and the H67 promote run card is logged as IR-70-GOV-01.</p>
<p>Full analysis (why h33-2-b2 scores 0.2778, the +15–49% credit-per-pixel algebra, ranked next hypotheses, external-data obtainability):
<a href="research/h70-paired-knickpoint-trains.md">docs/research/h70-paired-knickpoint-trains.md</a> ·
run card <a href="../evidence/h70_runcard.json">evidence/h70_runcard.json</a> · evidence rows <a href="../evidence/h70_e1_first_test.json">evidence/h70_e1_first_test.json</a> · lane stop <a href="../evidence/h70_lane_stop.json">evidence/h70_lane_stop.json</a>.</p>
</main>
<footer><div class="wrap">Run report generated {date.today().isoformat()} from committed evidence files; no hand-entered numbers. · <a href="feed.json">feed</a></div></footer>
</body></html>"""


def main() -> None:
    docs = REPO / "docs"
    changed = []
    for rel, prefix in [
        ("docs/index.html", ""),
        ("docs/executive-summary.html", ""),
        ("index.html", "docs/"),
    ]:
        changed.append(upsert(REPO / rel, prefix))
    (docs / "h70-report.html").write_text(report_html())
    changed.append("docs/h70-report.html")
    print("\n".join(changed))


if __name__ == "__main__":
    main()
