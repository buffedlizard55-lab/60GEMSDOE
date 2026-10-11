#!/usr/bin/env python3
"""Render the dated, authoritative site view for the stopped c7653 lane.

The legacy builder still renders prior experimental runs. This narrow post-render pass replaces
its recommendation surfaces and injects the current stop/research-only notice into archived pages.
It never changes or creates a GeoTIFF and never treats a public leaderboard row as a project score.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path


def _read(path: Path):
    return json.loads(path.read_text())


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _base(title: str, body: str, active: str = "", *, root_prefix: str = "") -> str:
    nav = [
        ("index.html", "Home"),
        ("executive-summary.html", "Submission status"),
        ("research.html", "Research"),
        ("hypotheses.html", "Deferred hypotheses"),
        ("leaderboard.html", "Leaderboard"),
        ("sources.html", "Sources"),
        ("irregularities.html", "Irregularities"),
    ]
    nav_html = " ".join(
        f'<a href="{root_prefix}{href}"{" class=active" if href == active else ""}>{label}</a>'
        for href, label in nav
    )
    tif = f'{root_prefix}downloads/gems60-knickpoint-lane-c7653-20261011T000000Z.tif'
    review = f'{root_prefix}research/active-lane-review-2026-10-11.md'
    btn = (f'<a class="btn" href="{tif}" download>Download c7653 GeoTIFF — research only, DO NOT SUBMIT</a> '
           f'<a class="btn alt" href="{review}">Read current review</a>')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)} · 60GEMSDOE</title><link rel="stylesheet" href="{root_prefix}assets/site.css"></head><body>
<header class="top"><div class="wrap"><h1>{_e(title)}</h1><nav>{nav_html}</nav>
<div class="dlbtn">{btn}</div></div></header>
<div class="values"><div class="wrap"><b>Maximize P(Win).</b> No slot is spent on an unvalidated candidate. <b>Own the Outcome.</b> Negative results and evidence limits are published clearly.</div></div>
<main class="wrap">{body}</main>
<footer><div class="wrap">Current review date: 2026-10-11 · Official board capture is a manual snapshot; the competition host is not polled automatically. ·
<a href="{root_prefix}data/feed.json">Machine-readable feed</a> · <a href="{root_prefix}../README.md">README</a> ·
<a href="https://github.com/buffedlizard55-lab/60GEMSDOE">Repository</a></div></footer></body></html>'''


def _common_status(status: dict, *, prefix: str = "") -> str:
    art = status["research_artifact"]
    tif = prefix + "downloads/" + Path(art["path"]).name
    report = prefix + "research/active-lane-review-2026-10-11.md"
    card = prefix + "../evidence/runcard.json"
    snapshot = prefix + "../registry/leaderboard_snapshot_2026-10-11.json"
    return f'''<div class="banner"><h2>STOP — no competition submission is cleared</h2>
<p><b>Active lane:</b> channel-steepness / χ / knickpoints. The preregistered c7653 E1 test returned
<strong>NEGATIVE-STOP</strong> (placement-null AUC 0.22436; orientation-matched AUC 0.25641).
No follow-up experiment was run, no new TIFF was created, and no weekly slot was used.</p>
<p><a class="btn" href="{tif}" download>Download the existing c7653 GeoTIFF for research only</a>
<strong>DO NOT SUBMIT.</strong> This is not an approved/promoted file; local format validation is not organizer acceptance.</p>
<p><a href="{report}">Full review</a> · <a href="{card}">final JSON run card</a> ·
<a href="{snapshot}">manual 50-row public-board snapshot</a></p></div>'''


def render(root: Path | None = None) -> dict:
    root = root or Path(__file__).resolve().parents[1]
    docs = root / "docs"
    status = _read(root / "registry/current_site_status.json")
    snapshot = _read(root / status["leaderboard_snapshot"])
    art = status["research_artifact"]
    tif_path = root / art["path"]
    if not tif_path.is_file():
        raise FileNotFoundError(f"research-only GeoTIFF missing: {tif_path}")
    if art.get("submit_to_competition") is not False or status.get("recommended_competition_submission") is not None:
        raise ValueError("current site status must not promote a submission")

    # Home: never surface registry/submission_build.json as a recommendation while the stop applies.
    body = _common_status(status) + f'''<h2>Current research state</h2>
<div class="grid"><section class="card"><h3>c7653 negative result</h3>
<p><b>First test:</b> 78 segments, 5,683 withheld pixels; placement AUC 0.22436 and orientation-matched AUC 0.25641.
The preregistered action is stop.</p>
<p><b>Pooled HOLDOUT-DTI:</b> 0.00213750, 95% CI [0.00179003, 0.00251341], 36,414 withheld positives,
evaluator <code>gems52-pooled-hide-v1</code>. This is a catalogue hide-and-recover proxy, not a public or organizer score.</p>
<p>Full-registry uniqueness and feature-by-feature leakage clearance were not established.</p></section>
<section class="card"><h3>H33-2-B2 score claim</h3>
<p>The reported 0.2778 remains <b>owner-reported / unverified</b>. A local LM-calibrated change of +0.0048695 is instrument evidence only.
No organizer receipt links the bytes to a score. An older report calls a same-named file 0.2708; exact-byte identity is unresolved. Public rank 23 (0.2778, extradr19) and rank 36 (0.2708, smrtdoog5) are not file attributions.</p>
<a href="research/active-lane-review-2026-10-11.md">What the evidence does and does not establish →</a></section></div>
<h2>Official public leaderboard — manual read 2026-10-11</h2>
<p class="mut">50 rows captured manually from the official page. Public ranks/scores only; not project scores, private-test performance, or file attribution.</p>
<table><tr><th>rank</th><th>participant</th><th>public score</th></tr>
<tr><td>1</td><td>xiaofanhu</td><td>0.4133</td></tr>
<tr><td>8</td><td>DARD</td><td>0.3195</td></tr>
<tr><td>23</td><td>extradr19</td><td>0.2778</td></tr></table>
<p><a href="leaderboard.html">Open all 50 rows →</a> · <a href="data/feed.json">Current repository feed</a></p>
<h2>Research paths</h2><ul>
<li><a href="research/active-lane-review-2026-10-11.md">Executive review, algebra correction, H33 evidence limits and citations</a></li>
<li><a href="research/next-chi-hypotheses-2026-10-11.md">Four ranked hypotheses — explicitly UNTESTED / DEFERRED</a></li>
<li><a href="../evidence/runcard.json">c7653 JSON run card</a> · <a href="downloads/{Path(art['validator_receipt']).name}">local format receipt</a></li>
</ul>
<p class="mut">The previous portal message “Predicted values must be in range [0, 1]” is a format/range rejection. For any future separately promoted raster, use the shared writer and validate the official grid, CRS, transform, dimensions, finite values and [0,1] range before upload. c7653 passed local format checks but is <b>not submit-cleared</b>. The historical <code>gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan</code> file remains an audit example, not a recommendation.</p>'''
    (docs / "index.html").write_text(_base("60GEMSDOE — current status and evidence", body, "index.html"))

    # Submission/executive page: disclose why the correct file is research-only and repeat the
    # format-vs-acceptance distinction relevant to the previous [0,1] portal rejection.
    body = _common_status(status) + f'''<h2>Download / submission decision</h2>
<p><a class="btn" href="downloads/{Path(art['path']).name}" download>Download c7653 GeoTIFF (research only)</a>
<a class="btn alt" href="downloads/{Path(art['validator_receipt']).name}">Local format receipt</a></p>
<ul><li><b>OK to download for research:</b> yes.</li><li><b>OK to submit to DrivenData:</b> <b>no</b> — the stop rule fired and the artifact was not promoted.</li>
<li><b>Weekly slots used in this review:</b> 0. No new raster was generated.</li>
<li><b>Unique submission name recorded on the artifact:</b> <code>{_e(art['submission_name'])}</code>.</li>
<li><b>Note ({len(art['note'])} characters):</b> <code>{_e(art['note'])}</code>.</li></ul>
<h2>Local format receipt is not an organizer receipt</h2>
<p>The TIFF is single-band float32, EPSG:32611, 3292×3730 on the 100 m grid, with values in [0,1],
no NaN/Inf, and 7,653 positive cells. The recorded local validator returned no listed problems.
That does <b>not</b> prove that DrivenData accepted the upload, passed its private validation, or assigned a score.
No such organizer receipt is recorded for this raster.</p>
<p>The historical portal message “Predicted values must be in range [0, 1]” is a format/range failure.
For any separately promoted future file, use the shared submission writer and verify the complete official grid,
CRS, transform, dimensions, finite values and [0,1] range with the shared validator before upload.
That checklist does not override this run's negative stop or authorize submitting c7653.</p>
<p><a href="research/active-lane-review-2026-10-11.md">Read full review</a> ·
<a href="research/next-chi-hypotheses-2026-10-11.md">Deferred hypothesis backlog</a></p>'''
    (docs / "executive-summary.html").write_text(_base("Submission status — research only", body, "executive-summary.html"))

    # Full 50-row board, based only on the dated manual snapshot.
    rows = "".join(
        f"<tr><td>{int(r['rank'])}</td><td>{_e(r['participant'])}</td><td>{float(r['score']):.4f}</td>"
        f"<td>{_e(r.get('submissions', ''))}</td><td>{_e(r.get('last_activity', ''))}</td></tr>"
        for r in snapshot["rows"]
    )
    body = f'''<h2>Official public leaderboard <span class="pill">manual snapshot</span></h2>
<p>Observed on <b>{_e(snapshot['observed_utc'])}</b> by a manual rendered-page fetch in three chunks.
The repository does not automate requests to <code>drivendata.org</code>. The public board is dynamic and may change.</p>
<p><b>Scope:</b> these are public leaderboard rows only. They are not this repository's score, are not private-test results,
and do not identify the TIFF associated with a row. In particular, the public 0.2778 at rank 23 belongs to extradr19;
it does not attribute H33-2-B2.</p>
<p>Headline values: #1 xiaofanhu <b>0.4133</b>; #8 DARD <b>0.3195</b>; #23 extradr19 <b>0.2778</b>.
At the current leader score, the nonredundant one-dot special case has marginal credit bar αs = 0.08266;
this is an algebraic condition, not a score projection.</p>
<table><tr><th>rank</th><th>participant</th><th>public score</th><th>submissions</th><th>last activity as displayed</th></tr>{rows}</table>
<p>Machine-readable provenance: <a href="../{_e(status['leaderboard_snapshot'])}">dated JSON snapshot</a> ·
<a href="../registry/leaderboard_history.jsonl">snapshot history</a> · <a href="score-ledger.csv">score ledger</a> ·
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">official public board</a>.</p>'''
    (docs / "leaderboard.html").write_text(_base("Public leaderboard — 2026-10-11 manual snapshot", body, "leaderboard.html"))

    body = _common_status(status) + '''<h2>Executive findings</h2>
<ol><li><b>c7653 stops.</b> The preregistered first test failed; no further experiment is authorized in this lane.
The pooled local HOLDOUT-DTI is 0.00213750 [0.00179003, 0.00251341], not a competition score.</li>
<li><b>Uniqueness and leakage clearance remain incomplete.</b> The six archived Spearman values compare final binary dot masks, not the pre-placement score surface; no full-registry coverage is documented. The old 0.50145 “AUC” was actually (Spearman rho + 1)/2, not ROC AUC, and no feature-by-feature canary table exists.</li>
<li><b>H33 score attribution is unresolved.</b> The 0.2778 claim is owner-reported; an archived report calls a same-named file 0.2708. No receipt reconciles the claims or ties either to bytes. Public ranks 23 and 36 are not file attributions.</li>
<li><b>The leaderboard was manually captured.</b> #1 xiaofanhu 0.4133; #8 DARD 0.3195; #23 extradr19 0.2778. No file attribution is available.</li></ol>
<h2>Metric decision rule</h2>
<p>For a candidate unit-mass dot with maximum kernel weight <code>q</code> and actual incremental weighted truth credit <code>ΔT</code>,
its general improvement condition is <code>ΔT(1−αs) &gt; αs(1−q)</code>. Only for the nonredundant special case
<code>ΔT = q = k</code> does this reduce to <code>k &gt; αs</code>. The coefficient <code>αs/(1−αs)</code> belongs to the
false-mass term in score inversion, not the general single-dot cutoff. Full derivation: <a href="research/score-ceiling-analysis.md">score-ceiling analysis</a>.</p>
<h2>Source-checked literature</h2><ul>
<li>Kirby &amp; Whipple (2012), <a href="https://doi.org/10.1016/j.jsg.2012.07.009">active tectonics in erosional landscapes</a>.</li>
<li>Perron &amp; Royden (2013), <a href="https://doi.org/10.1002/esp.3302">integral bedrock-river profile analysis</a>.</li>
<li>Royden &amp; Perron (2013), <a href="https://doi.org/10.1002/jgrf.20031">stream-power solutions and river profiles</a>.</li>
<li>Gailleton et al. (2019), <a href="https://doi.org/10.5194/esurf-7-211-2019">reproducible knickpoint segmentation</a>.</li>
<li>Barnes et al. (2014), <a href="https://doi.org/10.1016/j.cageo.2013.04.024">Priority-Flood</a>; Wobus et al. (2006), <a href="https://doi.org/10.1130/2006.2398(04)">tectonics from topography: procedures, promise and pitfalls</a>.</li></ul>
<p>Full evidence, trusted-source links and caveats: <a href="research/active-lane-review-2026-10-11.md">dated active-lane review</a>.</p>'''
    (docs / "research.html").write_text(_base("Research review — metric, evidence and stop status", body, "research.html"))

    hypothesis_rows = [
        (1, "Paired-basin ksn contrast across fault blocks", "High potential; very uncertain", "High", "Differential rock uplift expressed as a drainage-scale normalized-steepness contrast; SGMC lithology, runoff and outlet matching required."),
        (2, "Bedrock-channel confinement × ksn residual", "Medium-high potential; very uncertain", "High", "Joint reach-scale incision and valley confinement; resistant lithology is the named mimic; valid 10 m or finer terrain required."),
        (3, "Hydroclimate- and permanence-matched ksn residual", "Moderate potential; uncertain", "Medium–high", "Test steepness after matching precipitation and reach permanence; 3DHP permanence coverage must be checked before use."),
        (4, "Outlet/base-level-conditioned profile residual", "Moderate potential; uncertain", "Medium", "Match outlet class and censor playa/closed-basin/alluvial controls before scoring channel-profile residuals."),
    ]
    hrows = "".join(f"<tr><td>{n}</td><td><b>{_e(title)}</b></td><td>{_e(pot)}</td><td>{_e(cost)}</td><td>{_e(sig)}</td></tr>"
                    for n, title, pot, cost, sig in hypothesis_rows)
    body = _common_status(status) + f'''<h2>Four ranked candidates — all UNTESTED / DEFERRED</h2>
<p>The ordering is qualitative research priority, not predicted DTI improvement or a leaderboard forecast.
The c7653 NEGATIVE-STOP remains binding; this page does not authorize follow-up experiments, a new TIFF, or a slot.</p>
<table><tr><th>rank</th><th>hypothesis</th><th>potential (qualitative)</th><th>cost</th><th>physical signal and principal controls</th></tr>{hrows}</table>
<p>Every item is scoped to the active tectonic-geomorphology channel-steepness/χ/knickpoint lane, not scarp morphology.
The complete backlog specifies layers, physical mechanisms, off-catalogue rationale, novelty, mimics, data status and future gates:
<a href="research/next-chi-hypotheses-2026-10-11.md">read the full backlog</a>.</p>
<p>Trusted candidate sources: <a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP</a> ·
<a href="https://mrdata.usgs.gov/geology/state/">USGS SGMC</a> ·
<a href="https://prism.oregonstate.edu/">PRISM</a> ·
<a href="https://www.usgs.gov/3d-hydrography-program">USGS 3DHP</a>.</p>'''
    (docs / "hypotheses.html").write_text(_base("Untested hypotheses — explicitly deferred", body, "hypotheses.html"))

    # Focused source/provenance pages replace stale generated leaderboard assertions while retaining
    # the repository's dated registries and manual-review links.
    body = _common_status(status) + '''<h2>Official, trusted source set</h2>
<ul>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Official DrivenData problem, metric and submission-format page</a> — metric constants and format requirements.</li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Official public leaderboard</a> — manually captured on 2026-10-11; no automatic requests.</li>
<li><a href="https://doi.org/10.1016/j.jsg.2012.07.009">Kirby &amp; Whipple (2012)</a>; <a href="https://doi.org/10.1002/esp.3302">Perron &amp; Royden (2013)</a>; <a href="https://doi.org/10.1002/jgrf.20031">Royden &amp; Perron (2013)</a>.</li>
<li><a href="https://doi.org/10.5194/esurf-7-211-2019">Gailleton et al. (2019)</a>; <a href="https://doi.org/10.1016/j.cageo.2013.04.024">Barnes et al. (2014)</a>; <a href="https://doi.org/10.1130/2006.2398(04)">Wobus et al. (2006)</a>.</li>
<li><a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP</a>; <a href="https://mrdata.usgs.gov/geology/state/">USGS SGMC</a>; <a href="https://prism.oregonstate.edu/">PRISM Climate Group</a>; <a href="https://www.usgs.gov/3d-hydrography-program">USGS 3DHP</a>.</li>
</ul><p>Data sources are identified as candidates, not as datasets downloaded and validated in this run. The recorded 3DEP sample-tile probe succeeded; the full regional high-resolution DEM stack was not assembled. SGMC map-unit scales vary. PRISM grids were not downloaded. 3DHP permanence coverage must be checked before use.</p>
<p><a href="research/active-lane-review-2026-10-11.md">Full source-linked review</a> ·
<a href="research/next-chi-hypotheses-2026-10-11.md">Deferred hypothesis data requirements</a>.</p>'''
    (docs / "sources.html").write_text(_base("Trusted sources and data status", body, "sources.html"))

    body = _common_status(status) + '''<h2>Current irregularities / review limits</h2>
<table><tr><th>Issue</th><th>Status and consequence</th></tr>
<tr><td>H33-2-B2 score attribution</td><td>Current 0.2778 is owner-reported; an archived report calls a same-named file 0.2708. No organizer receipt reconciles either value or links it to exact bytes. Public rank-23 0.2778 (extradr19) and rank-36 0.2708 (smrtdoog5) are not file attributions. See <code>IR-60-H33-SCORE-20261011</code>.</td></tr>
<tr><td>c7653 E1 outcome</td><td>Placement and orientation-matched AUCs are below 0.5; preregistered result is NEGATIVE-STOP. No follow-up in the lane.</td></tr>
<tr><td>c7653 uniqueness scope</td><td>Six archived Spearman values compare final binary dot masks, not the pre-placement score surface; post-placement overlap is limited to those six rasters. Complete-registry uniqueness is not established. See <code>IR-60-UNIQUENESS-SURFACE-20261011</code>.</td></tr>
<tr><td>c7653 leakage audit</td><td>The legacy 0.50145 “AUC” is actually (Spearman rho + 1)/2, not ROC AUC; no feature-by-feature canary results are recorded. Full leakage clearance is not established. See <code>IR-60-CANARY-LABEL-20261011</code>.</td></tr>
<tr><td>DEM resolution / hydrography</td><td>Existing 100 m networks fail the recorded Hack-exponent and network-agreement checks. Full 10 m coverage has not been assembled; this is a data-quality warning, not a reason to override the failed first-test stop.</td></tr>
<tr><td>Public board freshness</td><td>Snapshot is a manual 2026-10-11 read and may become stale. No competition-host polling is performed.</td></tr>
<tr><td>Automated leaderboard fetch (fixed 2026-10-11)</td><td>A scheduled refresh script previously contained a direct leaderboard fetch. The fetch/parser is removed; the scheduled workflow now preserves manual board snapshots and probes only non-competition sources. See <code>IR-60-LB-AUTO-20261011</code>.</td></tr>
</table><p>The historical irregularity register remains at <a href="../registry/irregularities.json">registry/irregularities.json</a>; older entries are preserved as historical records. This page highlights only the current decision-relevant items.</p>
<p><a href="research/active-lane-review-2026-10-11.md">Full explanation and evidence links</a>.</p>'''
    (docs / "irregularities.html").write_text(_base("Current irregularities and evidence limits", body, "irregularities.html"))

    # Replace the rendered score-ceiling text with the corrected research note rather than leaving
    # generated HTML that contradicts the exact general condition.
    ceiling = root / "docs/research/score-ceiling-analysis.md"
    if ceiling.exists():
        markdown = _e(ceiling.read_text())
        body = _common_status(status) + f'''<h2>Corrected score-ceiling analysis (source note follows verbatim)</h2>
<p>The Markdown source is authoritative. This escaped rendering is intentionally plain to avoid silently
altering equations or claims during HTML conversion.</p><pre>{markdown}</pre>
<p><a href="research/score-ceiling-analysis.md">Open the Markdown source</a> ·
<a href="research/active-lane-review-2026-10-11.md">active-lane review</a></p>'''
        (docs / "score-ceiling.html").write_text(_base("Score-ceiling analysis — corrected algebra", body))

    # Keep a visible current status on the remaining historical reports, but remove the old injected
    # H61/registry-primary recommendation banner so it cannot be mistaken for today's choice.
    notice = _common_status(status)
    core = {"index.html", "executive-summary.html", "leaderboard.html", "research.html", "hypotheses.html", "sources.html", "irregularities.html", "score-ceiling.html"}
    for page in sorted(docs.glob("*.html")):
        if page.name in core:
            continue
        text = page.read_text()
        text = re.sub(r'<div class=wrap style="border:2px solid #0a7d33.*?</div>\s*', "", text, flags=re.S)
        text = re.sub(r'<div class=dlbtn[^>]*>\s*<b>Registry primary.*?</div>\s*', "", text, flags=re.S)
        text = re.sub(r'<div class="banner current-stop-notice">.*?</div>\s*', "", text, flags=re.S)
        research_button = (
            '<a class="btn" href="downloads/' + Path(art["path"]).name + '" download>'
            'Download c7653 — research only, DO NOT SUBMIT</a>'
        )
        text = re.sub(r'(<div class=dlbtn>).*?(</div>)',
                      lambda m: m.group(1) + research_button + m.group(2), text,
                      count=1, flags=re.S)
        notice_with_class = notice.replace('<div class="banner">', '<div class="banner current-stop-notice">', 1)
        text = re.sub(r'(<body[^>]*>\s*)', lambda m: m.group(1) + notice_with_class, text, count=1)
        page.write_text(text)

    # GitHub Pages in this repository publishes the root. Keep root landing/stubs aligned with the
    # research-only status rather than the legacy registry submission pointer.
    root_index = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>60GEMSDOE — STOP / research-only artifact</title><link rel="stylesheet" href="docs/assets/site.css">
<meta http-equiv="refresh" content="0; url=docs/index.html"></head><body><main class="wrap">
<h1>60GEMSDOE — current status: STOP</h1>{_common_status(status, prefix='docs/')}
<p><a href="docs/index.html">Open the current evidence site →</a></p></main></body></html>'''
    (root / "index.html").write_text(root_index)
    for page in sorted(root.glob("*.html")):
        if page.name == "index.html":
            continue
        target = page.name if (docs / page.name).exists() else "research.html"
        root_html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(target)} · 60GEMSDOE</title><link rel="canonical" href="docs/{_e(target)}"><link rel="stylesheet" href="docs/assets/site.css">
<meta http-equiv="refresh" content="0; url=docs/{_e(target)}"></head><body><main class="wrap">
<h1>Current status: STOP</h1>{_common_status(status, prefix='docs/')}
<p><a href="docs/{_e(target)}">Open current page →</a> · <a href="docs/index.html">Home</a></p></main></body></html>'''
        page.write_text(root_html)

    return {"status": status["status"], "artifact": art["path"], "leaderboard_rows": len(snapshot["rows"]), "pages_updated": True}


if __name__ == "__main__":
    print(json.dumps(render(), indent=2))
