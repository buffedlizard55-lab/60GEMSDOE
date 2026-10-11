#!/usr/bin/env python3
"""Render the dated current STOP review without promoting a registry artifact.

The legacy builder still renders prior experimental runs. This narrow post-render pass replaces
its recommendation surfaces with the latest reviewed result (H65-1), labels its TIFF as research
only, and injects a current stop notice into archived pages. It never creates or changes a GeoTIFF
and never treats a public leaderboard row as a project score.
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


def _site_href(root_path: str, *, root_prefix: str = "") -> str:
    """Map a repository-relative path to a URL from a docs page or the published root."""
    path = Path(root_path)
    if path.parts and path.parts[0] == "docs":
        return root_prefix + "/".join(path.parts[1:])
    return root_prefix + "../" + path.as_posix()


def _base(title: str, body: str, active: str = "", *, root_prefix: str = "", status: dict) -> str:
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
    artifact = status["research_artifact"]
    tif = _site_href(artifact["path"], root_prefix=root_prefix)
    review = f'{root_prefix}research/active-lane-review-2026-10-11.md'
    btn = (f'<a class="btn" href="{tif}" download>Download H65-1 GeoTIFF — research only, DO NOT SUBMIT</a> '
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
    tif = _site_href(art["path"], root_prefix=prefix)
    receipt = _site_href(art["validator_receipt"], root_prefix=prefix)
    report = prefix + "research/active-lane-review-2026-10-11.md"
    card = _site_href(status["final_run_card"], root_prefix=prefix)
    snapshot = _site_href(status["leaderboard_snapshot"], root_prefix=prefix)
    first = status["latest_first_test"]
    hold = status["latest_holdout"]
    ci = first["ci95"]
    mean_text = f"{first['mean_log_ksn_step_contrast']:+.4f}"
    hold_text = f"{hold['mean']:.5f}"
    return f'''<div class="banner current-stop-notice"><h2>STOP — no competition submission is cleared</h2>
<p><b>Governing STOP record:</b> H65-1, channel-steepness / χ / knickpoints. Its preregistered first test was
<strong>INCONCLUSIVE → STOP</strong>: mean log-ksn contrast {mean_text},
95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}] (262 components). Because the interval crosses zero, the test did not pass the PROCEED gate.
The earlier c7653 run also stopped. Later H66/H67/H68 artifacts do not lift this STOP; their literal uniqueness clearance failed against the dense calibration lattice corpus. No follow-up experiment is authorized; this review created no TIFF and used no slot.</p>
<p><a class="btn" href="{tif}" download>Download the existing H65-1 GeoTIFF for research only</a>
<a class="btn alt" href="{prefix}downloads/gems60-h68-dem10-lidar-piedmont-dksn-40000-20261011T185033Z-6e9b1e286c45-zeros.tif" download>Download H68-1 GeoTIFF (research only)</a>
<strong>DO NOT SUBMIT.</strong> The local format preflight is not organizer acceptance or uniqueness clearance.</p>
<p>H65-1 diagnostic <b>HOLDOUT-DTI</b>: {hold_text} [{hold['ci95'][0]:.5f}, {hold['ci95'][1]:.5f}],
{hold['withheld_positive_pixels']:,} withheld positives (`{_e(hold['evaluator'])}`); H68-1 diagnostic <b>HOLDOUT-DTI</b>: 0.171894 [0.157848, 0.183994] (2.61× H66-1, 14.85× H65-1, E1 +0.4502 [+0.2510, +0.6491], max non-lattice 3-px overlap 0.6234 ≤ 0.70, literal 70-raster overlap 0.9985 &gt; 0.70 → verdict NEGATIVE, <a href="{prefix}downloads/gems60-h68-dem10-lidar-piedmont-dksn-40000-20261011T185033Z-6e9b1e286c45-zeros-runcard.json">H68-1 run card</a> · <a href="{prefix}downloads/checks-gems60-h68-dem10-lidar-piedmont-dksn-40000-20261011T185033Z-6e9b1e286c45-zeros.tif.json">H68-1 format checks</a>); not a leaderboard score.
<a href="{receipt}">Local format receipt</a> · <a href="{report}">Full review</a> ·
<a href="{card}">final JSON run card</a> · <a href="{snapshot}">manual 50-row public-board snapshot</a></p></div>'''


def _write_page(path: Path, text: str) -> None:
    """Write a rendered page, re-inserting any marker-delimited status boards it carried.

    Parallel lane sessions publish ``<!-- X-STATUS:BEGIN/END -->`` boards into the shared
    pages.  Without this the current-review renderer deletes every other session's
    read-out, which is the same defect ``build_site.preserve_status_blocks`` fixes for the
    normal rendering path (IR-66-SITE-01).  Single implementation, imported, not forked.
    """
    from build_site import preserve_status_blocks
    path.write_text(preserve_status_blocks(path, text))

def _post_review_artifacts_html(status: dict) -> str:
    """Render the post-STOP research-artifact boards recorded in the status file.

    Parallel lane sessions used to hand-edit ``docs/index.html`` to publish their boards; the
    next regeneration then deleted every one of them, because a renderer-owned page cannot
    carry hand HTML.  The boards are data now (``post_review_artifacts``), so a render is
    lossless, the STOP wording travels with every artifact, and no session has to choose
    between publishing and being reproducible (IR-H80-SITE-01).
    """
    items = status.get("post_review_artifacts") or []
    if not items:
        return ""
    rows = []
    for a in items:
        files = []
        for f in a.get("files", []):
            cls = "btn alt" if files else "btn"
            label = f.get("variant") or Path(f["file"]).name
            files.append(f'<a class="{cls}" href="{_site_href(f["file"])}" download>&#11015; {_e(label)}</a>')
        links = " ".join(f'<a href="{_site_href(l["href"])}">{_e(l["label"])}</a>'
                         for l in a.get("links", []))
        rows.append(
            f"<tr><td><b>{_e(a['id'])}</b><br><code>{_e(a.get('short_name', ''))}</code><br>"
            f"<span style=\"color:#5b7183\">{_e(a.get('detail', ''))}</span></td>"
            f"<td>{' '.join(files)}</td><td>{links}</td></tr>")
    return (
        '<div class="wrap" style="border:3px solid #b42318;background:#fffafa;padding:12px 16px;margin:8px auto">'
        '<h2 style="margin:0 0 6px">&#9940; Additional research artifacts added under this STOP '
        '&mdash; DOWNLOAD for research: YES &middot; SUBMIT: <b>NO &mdash; DO NOT SUBMIT</b></h2>'
        f'<p style="margin:4px 0">{_e(status.get("post_review_artifacts_note", ""))}</p>'
        '<table><tr><th>artifact</th><th>download (research only)</th><th>measured evidence</th></tr>'
        f'{"".join(rows)}</table></div>')


def _post_review_artifacts_summary(status: dict) -> str:
    """Compact list of the post-STOP artifact boards for the submission-status page."""
    items = status.get("post_review_artifacts") or []
    if not items:
        return ""
    rows = []
    for a in items:
        first = a["files"][0] if a.get("files") else None
        dl = (f' · <a href="{_site_href(first["file"])}" download>download .tif (research only)</a>'
              if first else "")
        rows.append(f'<li><b>{_e(a["id"])}</b> — {_e(a.get("detail", ""))}{dl}</li>')
    return ('<h2>Post-STOP research artifacts — none of them is cleared to submit</h2><ul>'
            + "".join(rows) + "</ul>"
            '<p>Every entry above is <b>research only</b>: download is fine, submission is not. '
            'The board with the download buttons is on the <a href="index.html">home page</a>.</p>')


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

    active_href = _site_href(art["path"])
    card_href = _site_href(status["final_run_card"])
    receipt_href = _site_href(art["validator_receipt"])
    first = status["latest_first_test"]
    hold = status["latest_holdout"]
    unique = status["registry_uniqueness_review"]
    leak = status["leakage_review"]
    h33 = status["h33_claim"]
    previous = status["previous_run_c7653"]
    post_runs = status.get("post_review_runs") or []

    # Runs recorded in other sessions after the STOP review. Rendered factually:
    # negative results corroborate the stop; any positive claim is shown as a
    # claim, with its irregularity flag, never as an endorsement.
    if post_runs:
        rows = []
        for r in post_runs:
            flagged = "CONTRADICT" in r["verdict"].upper()
            badge = ("⚠️ <b>claimed positive — contradicted this STOP file</b>; "
                     "flagged IR-H66C-STOPCONFLICT-01 and promotion reversed by PRs #19/#20"
                     if flagged else "corroborates the STOP")
            card = (f'<a href="{_site_href(r["run_card"])}">run card</a>'
                    if r.get("run_card") else "")
            dl = (f' · <a href="{_site_href(r["download"])}" download>⬇ TIF</a>'
                  if r.get("download") else "")
            rows.append(
                f"<tr><td>{_e(r['session'])}</td><td>{_e(r['id'])}</td>"
                f"<td>{_e(r['verdict'])}</td><td>{_e(r['artifact'])} {dl} {card}</td>"
                f"<td>{badge}</td></tr>")
        # Hard-code no head-count here: sessions append post_review_runs rows later, and a
        # fixed "three runs / two negative" sentence silently goes stale (H70-1 found this on
        # 2026-10-11).  Count from the data instead.
        _NUM = {0: "No", 1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
               6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}
        n_all, n_flag = len(post_runs), sum("CONTRADICT" in r["verdict"].upper() for r in post_runs)
        n_neg = n_all - n_flag
        post_html = f'''<h2>Lane runs recorded after this review (other sessions, same day)</h2>
<div class="card"><p>{_NUM.get(n_all, str(n_all))} tectonic-geomorphology runs were recorded on 2026-10-11 after the
review above. {_NUM.get(n_neg, str(n_neg))} are <b>negative and corroborate the STOP</b>; one <b>claimed a pass
and promote</b> while the stop file was in force — it was flagged as
<code>IR-H66C-STOPCONFLICT-01</code> and its promotion was <b>reversed</b> by session
<code>arena/a856d257</code> (PRs #19/#20), so it remains a research artifact, not a
cleared submission. No submission slot has been spent by any of them.</p>
<table><tr><th>session</th><th>id</th><th>result (as recorded by that session)</th><th>artifact</th><th>relation to STOP</th></tr>
{''.join(rows)}
</table></div>
'''
    else:
        post_html = ""

    # Home: never surface registry/submission_build.json as a recommendation while the stop applies.
    body = _common_status(status) + _post_review_artifacts_html(status) + f'''<h2>Current research state</h2>
<div class="grid"><section class="card"><h3>H65-1 — latest 10 m result</h3>
<p><b>First test:</b> 262 withheld components; mean log-ksn step contrast
{first['mean_log_ksn_step_contrast']:+.4f}, 95% CI [{first['ci95'][0]:+.4f}, {first['ci95'][1]:+.4f}],
median {first['median']:+.4f}, {first['fraction_positive']:.1%} positive. The interval crosses zero;
INCONCLUSIVE fails the preregistered PROCEED gate, so the lane stops.</p>
<p><b>Diagnostic HOLDOUT-DTI:</b> {hold['mean']:.5f}, 95% CI [{hold['ci95'][0]:.5f}, {hold['ci95'][1]:.5f}],
{hold['withheld_positive_pixels']:,} withheld positives, evaluator <code>{_e(hold['evaluator'])}</code>.
The matched random-mass control is {hold['random_mass_control']:.5f} [{hold['random_mass_control_ci95'][0]:.5f}, {hold['random_mass_control_ci95'][1]:.5f}].
This conditional catalogue hide-and-recover diagnostic is not a public or organizer score.</p>
<p>All four recorded lane-feature canaries are below the 0.90 leakage threshold. The deliberate
<code>dist_to_visible</code> positive control is 0.9243 and is not a lane input; see the run card.</p></section>
<section class="card"><h3>Uniqueness — NOT CLEARED</h3>
<p>Registry comparison checked {unique['checked_registry_rasters']}/{unique['expected_registry_rasters']} rasters;
max recorded |Spearman| {unique['max_abs_spearman_reported']:.4f}. The final-dot 3-px overlap reaches
{unique['max_final_dot_overlap_within_3px']:.0%}, above the {unique['limits']['dot_overlap']:.0%} limit;
the scan is incomplete and the tool verdict is <code>unique=false</code>. A density-matched random diagnostic
does not override the literal gate. A distinct pre-placement surface screen is not documented.</p>
<p><a href="h65-report.html">Full H65-1 run report →</a></p></section></div>
<div class="grid"><section class="card"><h3>Earlier c7653 result — archived</h3>
<p>Its first-test AUCs were 0.22436 (placement null) and 0.25641 (orientation-matched null), a NEGATIVE-STOP.
Its diagnostic HOLDOUT-DTI was {previous['holdout_dti']['mean']:.8f}
[{previous['holdout_dti']['ci95'][0]:.8f}, {previous['holdout_dti']['ci95'][1]:.8f}],
{previous['holdout_dti']['withheld_positives']:,} withheld positives. The c7653 canary audit and full registry uniqueness
clearance were not established; H65-1 is the newer result.</p>
<p><a href="{_site_href(previous['artifact'])}">c7653 TIFF — historical research only</a> ·
<a href="../evidence/runcard.json">c7653 run card</a></p></section>
<section class="card"><h3>H33-2-B2 score attribution</h3>
<p>The reported 0.2778 remains <b>owner-reported / unverified</b>. No organizer receipt ties the exact raster bytes
to 0.2778. An archived report assigns 0.2708 to a same-named artifact; byte identity and attribution remain unresolved.
The local LM-calibrated delta (+0.0048695) is instrument evidence only. Public ranks 23 and 36 do not authenticate files.</p>
<a href="research/active-lane-review-2026-10-11.md">Evidence and score algebra →</a></section></div>
<h2>Official public leaderboard — manual read 2026-10-11</h2>
<p class="mut">50 rows captured manually from the official page. Public ranks/scores only; not project scores,
private-test performance, or file attribution.</p>
<table><tr><th>rank</th><th>participant</th><th>public score</th></tr>
<tr><td>1</td><td>xiaofanhu</td><td>0.4133</td></tr>
<tr><td>8</td><td>DARD</td><td>0.3195</td></tr>
<tr><td>23</td><td>extradr19</td><td>0.2778</td></tr></table>
<p><a href="leaderboard.html">Open all 50 rows →</a> · <a href="data/feed.json">Current repository feed</a></p>
{post_html}
<h2>Research paths</h2><ul>
<li><a href="research/active-lane-review-2026-10-11.md">Executive review, H65-1 / c7653 results, H33 evidence limits and citations</a></li>
<li><a href="research/next-chi-hypotheses-2026-10-11.md">Four ranked hypotheses — explicitly UNTESTED / DEFERRED; no experiment authorized</a></li>
<li><a href="h65-report.html">Detailed H65-1 report</a> · <a href="{card_href}">H65-1 final JSON run card</a> · <a href="{receipt_href}">local format receipt</a></li>
</ul>
<p class="mut">The historical portal message “Predicted values must be in range [0, 1]” is a format/range rejection.
H65-1 passed local format/range checks but is <b>not submit-cleared</b>. For any separately authorized future artifact,
use the shared writer and validator to check the official grid, CRS, transform, dimensions, finite values and [0,1] range.
This informational checklist does not authorize an experiment or upload. The historical <code>gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan</code>
file remains an audit example, not a recommendation.</p>'''
    _write_page((docs / "index.html"), _base("60GEMSDOE — current status and evidence", body, "index.html", status=status))

    # Submission/executive page: disclose why the correct file is research-only and distinguish
    # format validity from organizer acceptance and uniqueness clearance.
    body = _common_status(status) + f'''<h2>Download / submission decision</h2>
<p><a href="research/submission-status-review.md">Latest repository audit and H66/H67 decision erratum</a> · <a href="../evidence/review_run_card.json">Review run card</a> · <a href="../evidence/submission_status_audit.json">Fresh format audit</a></p>
<p><a class="btn" href="{_site_href(art['path'])}" download>Download H65-1 GeoTIFF (research only)</a>
<a class="btn alt" href="{receipt_href}">Local format receipt</a></p>
<ul><li><b>OK to download for research:</b> yes.</li><li><b>OK to submit to DrivenData:</b> <b>no</b> — the first-test stop and failed raw-overlap gate prohibit promotion.</li>
<li><b>Weekly slots used in this review:</b> 0. No TIFF was created by this review.</li>
<li><b>Recorded run-card name (not a portal receipt):</b> <code>{_e(art['submission_name'])}</code>.</li>
<li><b>Artifact filename id:</b> <code>{_e(art['artifact_filename_id'])}</code>.</li>
<li><b>Note ({art['note_chars']} characters):</b> <code>{_e(art['note'])}</code>.</li>
<li><b>SHA-256:</b> <code>{art['sha256']}</code>.</li></ul>
<h2>How to submit a future <em>cleared</em> file (not one of these research TIFFs)</h2>
<ol><li>First require the first-test, leakage, full registry uniqueness, and spatially blocked holdout gates to pass; a separate selector must approve a weekly slot. <strong>None is approved now.</strong></li>
<li>Download the selected <code>.tif</code> from its own run-card link (or a ZIP containing exactly one TIFF). Verify its SHA-256 and use the shared writer/validator: one <code>float32</code> band, exact sample CRS/shape/transform, no NaN/Inf anywhere, every value in [0,1], no nodata tag.</li>
<li>On the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">DrivenData submissions page</a>, sign in with your own account, choose <em>New submission</em>, choose that exact file, and paste the run-card's unique name and ≤140-character note into the available fields. Do not upload a research-only artifact to test the portal.</li>
<li>Submit only after the selector approves the slot; preserve the organizer receipt, score and file hash together. Until then, a local PASS says only that the TIFF passes <em>local</em> format checks.</li></ol>
{_post_review_artifacts_summary(status)}
<h2>Local format receipt is not an organizer receipt</h2>
<p>The local validator reports single-band float32, EPSG:32611, 3292×3730 on the 100 m grid, values in [0,1],
no NaN/Inf, and 40,000 positive cells; it lists no problems. That does <b>not</b> prove that DrivenData accepted
an upload, passed private validation, assigned a score, or cleared uniqueness. No organizer receipt is recorded for this raster.</p>
<p>The historical portal message “Predicted values must be in range [0, 1]” is a format/range failure.
For any separately authorized future file, use the shared submission writer and verify the complete official grid,
CRS, transform, dimensions, finite values and [0,1] range with the shared validator before upload.
That checklist does not override H65-1's negative stop or authorize submitting H65-1.</p>
<p><a href="research/active-lane-review-2026-10-11.md">Read full review</a> ·
<a href="research/next-chi-hypotheses-2026-10-11.md">Deferred hypothesis backlog</a> ·
<a href="h65-report.html">Detailed H65-1 evidence</a></p>'''
    _write_page((docs / "executive-summary.html"), _base("Submission status — research only", body, "executive-summary.html", status=status))

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
    _write_page((docs / "leaderboard.html"), _base("Public leaderboard — 2026-10-11 manual snapshot", body, "leaderboard.html", status=status))

    body = _common_status(status) + f'''<h2>Executive findings</h2>
<ol><li><b>H65-1 is the governing STOP record.</b> The first-test mean was {first['mean_log_ksn_step_contrast']:+.5f}
(95% CI [{first['ci95'][0]:+.5f}, {first['ci95'][1]:+.5f}]); it is inconclusive and therefore fails the preregistered PROCEED gate.
The diagnostic HOLDOUT-DTI was {hold['mean']:.5f} [{hold['ci95'][0]:.5f}, {hold['ci95'][1]:.5f}], not a competition score.</li>
<li><b>H65-1 is not uniqueness-cleared.</b> The reported max |Spearman| is {unique['max_abs_spearman_reported']:.4f},
but final-dot overlap reaches {unique['max_final_dot_overlap_within_3px']:.0%} against a 70% limit;
651/655 rasters were checked, and a separate pre-placement surface screen is not documented. The matched random-control diagnostic
does not override this literal gate.</li>
<li><b>H65-1 feature canaries:</b> the four recorded lane inputs have max(AUC,1-AUC) ≤0.518. The deliberate
<code>dist_to_visible</code> positive control is 0.9243 and is not an input. This later audit does not retroactively clear c7653.</li>
<li><b>c7653 is an earlier independent negative stop.</b> Its placement/orientation AUCs were 0.22436/0.25641;
its incomplete uniqueness and leakage reviews remain incomplete.</li>
<li><b>H33 score attribution is unresolved.</b> The 0.2778 claim remains owner-reported; a same-named archived file is reported as
0.2708. No organizer receipt reconciles the numbers or ties either to exact bytes. Public ranks 23 and 36 are not file attributions.</li>
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
    _write_page((docs / "research.html"), _base("Research review — metric, evidence and stop status", body, "research.html", status=status))

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
H65-1's STOP remains binding: no follow-up, resolution change, new TIFF, or slot is authorized by this backlog.</p>
<table><tr><th>rank</th><th>hypothesis</th><th>potential (qualitative)</th><th>cost</th><th>physical signal and principal controls</th></tr>{hrows}</table>
<p>Every item is scoped to the active tectonic-geomorphology channel-steepness/χ/knickpoint lane, not scarp morphology.
They are dormant research ideas only; the complete backlog specifies layers, physical mechanisms, off-catalogue rationale,
novelty, mimics, data status and validation gates:
<a href="research/next-chi-hypotheses-2026-10-11.md">read the full backlog</a>.</p>
<p>Trusted candidate sources: <a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP</a> ·
<a href="https://mrdata.usgs.gov/geology/state/">USGS SGMC</a> ·
<a href="https://prism.oregonstate.edu/">PRISM</a> ·
<a href="https://www.usgs.gov/3d-hydrography-program">USGS 3DHP</a>.</p>'''
    _write_page((docs / "hypotheses.html"), _base("Untested hypotheses — explicitly deferred", body, "hypotheses.html", status=status))

    # Focused source/provenance pages replace stale generated leaderboard assertions while retaining
    # the repository's dated registries and manual-review links.
    body = _common_status(status) + '''<h2>Official, trusted source set</h2>
<ul>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Official DrivenData problem, metric and submission-format page</a> — metric constants and format requirements.</li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Official public leaderboard</a> — manually captured on 2026-10-11; no automatic requests.</li>
<li><a href="https://doi.org/10.1016/j.jsg.2012.07.009">Kirby &amp; Whipple (2012)</a>; <a href="https://doi.org/10.1002/esp.3302">Perron &amp; Royden (2013)</a>; <a href="https://doi.org/10.1002/jgrf.20031">Royden &amp; Perron (2013)</a>.</li>
<li><a href="https://doi.org/10.5194/esurf-7-211-2019">Gailleton et al. (2019)</a>; <a href="https://doi.org/10.1016/j.cageo.2013.04.024">Barnes et al. (2014)</a>; <a href="https://doi.org/10.1130/2006.2398(04)">Wobus et al. (2006)</a>.</li>
<li><a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP</a>; <a href="https://mrdata.usgs.gov/geology/state/">USGS SGMC</a>; <a href="https://prism.oregonstate.edu/">PRISM Climate Group</a>; <a href="https://www.usgs.gov/3d-hydrography-program">USGS 3DHP</a>.</li>
</ul><p>H65-1 used a pinned 18-tile USGS 3DEP 1/3-arc-second (~10 m) DEM stack with 5,167,373/5,167,373 footprint pixels covered.
The SGMC, PRISM climate and 3DHP permanence layers were not assembled into matched confound masks for this run; those remain
requirements for any separately authorized research. USGS says legacy NHD is retired; do not treat an old NHD layer as current 3DHP.</p>
<p><a href="h65-report.html">H65-1 processing and source record</a> ·
<a href="research/active-lane-review-2026-10-11.md">Full source-linked review</a> ·
<a href="research/next-chi-hypotheses-2026-10-11.md">Deferred hypothesis data requirements</a>.</p>'''
    _write_page((docs / "sources.html"), _base("Trusted sources and data status", body, "sources.html", status=status))

    body = _common_status(status) + f'''<h2>Current irregularities / review limits</h2>
<table><tr><th>Issue</th><th>Status and consequence</th></tr>
<tr><td>H65-1 first test</td><td>Mean log-ksn step contrast {first['mean_log_ksn_step_contrast']:+.5f}, 95% CI [{first['ci95'][0]:+.5f}, {first['ci95'][1]:+.5f}]; inconclusive means STOP under the registered rule. No rerun at another resolution.</td></tr>
<tr><td>H65-1 registry uniqueness</td><td>651/655 rasters checked; max |Spearman| {unique['max_abs_spearman_reported']:.4f}; final 3-px dot overlap {unique['max_final_dot_overlap_within_3px']:.0%} exceeds the 70% threshold; tool verdict unique=false. Pre-placement screen is not documented, so no clearance. See <code>IR-60-GATE-01</code> / <code>IR-60-CORPUS-01</code>.</td></tr>
<tr><td>H65-1 DEM cache</td><td>The first local cache did not match its recorded hash; a rebuild from pinned input TIFs matched all 11 arrays and reproduced the shipped raster. Root cause of the stale scratch cache is unknown. See <code>IR-65-CACHE-01</code>.</td></tr>
<tr><td>H80-1 uniqueness clause</td><td>The operator's clause 1 (dense field) and the literal clause 3 (≤70 % of dots within 3 px of any earlier raster) are jointly unsatisfiable: the already-scored champion is 0.99915 inside the 3-px neighbourhood of <code>calib_r13lattice_00904.tif</code>, and a mass-matched random emission scores 0.9987 literal / 0.8746 matched against it, so four comparators (<code>calib_r13lattice_00904</code>, <code>r13_lattice_s5_00904</code>, <code>r11_greedy_mp</code>, <code>r14_union_tips10_lat6</code>) are non-decidable. Measured frontier: the like-for-like limit is crossed only at 24,000–30,000 added dots (union ≈62,000–68,000). See <code>IR-H80-PROFILE-01</code>, <code>IR-H80-G3-UNSAT-01</code>, <code>evidence/h80_g3_frontier.json</code>.</td></tr>
<tr><td>H80-1 shared scan tool</td><td><code>scripts/build_h71_field.py::uniqueness_scan</code> could not be reused as published (relative <code>extra_dirs</code> crashed the <code>source</code> label; the emitted-field distance transform was recomputed per comparator). Fixed in place; re-scan 121 rasters in 219 s at a 1.04 GB peak. See <code>IR-H80-TOOL-04</code>.</td></tr>
<tr><td>H80-1 post-STOP boards</td><td>Post-STOP artifact boards were hand HTML in <code>docs/index.html</code> and would be deleted by the next <code>build_current_review_site.py</code> render; they are now data (<code>registry/current_site_status.json → post_review_artifacts</code>) and the renderer renders them. See <code>IR-H80-SITE-01</code>.</td></tr>
<td>Earlier placement/orientation AUCs were 0.22436/0.25641, a negative stop. Its six final-mask comparisons did not establish full-registry or pre-placement uniqueness; no feature-by-feature canary audit was recorded.</td></tr>
<tr><td>H33-2-B2 score attribution</td><td>0.2778 remains owner-reported/unverified. A same-named artifact was elsewhere reported as 0.2708; no organizer receipt reconciles either value or links it to exact bytes. Local LM diagnostics and public ranks do not establish attribution.</td></tr>
<tr><td>Public board freshness</td><td>Snapshot is a manual 2026-10-11 read and may become stale. No competition-host polling is performed.</td></tr>
<tr><td>Automated leaderboard fetch (fixed 2026-10-11)</td><td>The scheduled refresh preserves manual board snapshots and probes only non-competition sources; it makes no request to the DrivenData host. See <code>IR-60-LB-AUTO-20261011</code>.</td></tr>
</table><p>The historical irregularity register remains at <a href="../registry/irregularities.json">registry/irregularities.json</a>; older entries are preserved as historical records. This page highlights only the current decision-relevant items.</p>
<p><a href="research/active-lane-review-2026-10-11.md">Full explanation and evidence links</a>.</p>'''
    # The curated table above is hand-written, so a finding registered by a parallel session
    # can be invisible on the site even when it invalidates an instrument this page cites.
    # Render every high-severity register entry that the curated rows do not already name,
    # from the registry itself rather than from a second hand-written list (IR-66-SITE-01).
    try:
        _reg = _read(root / "registry/irregularities.json").get("items", [])
    except (OSError, json.JSONDecodeError):
        _reg = []
    _extra = "".join(
        f'<tr><td><code>{_e(it.get("id", ""))}</code></td>'
        f'<td>{_e(it.get("statement", ""))}<br><i>Mitigation:</i> {_e(it.get("mitigation", ""))}</td></tr>'
        for it in _reg
        if str(it.get("severity", "")).lower() == "high" and it.get("id") not in body)
    if _extra:
        body = body.replace(
            "<p>The historical irregularity register remains",
            f"<h2>Also registered at high severity (rendered from the registry)</h2>"
            f"<table><tr><th>Issue</th><th>Statement and mitigation</th></tr>{_extra}</table>"
            f"<p>The historical irregularity register remains", 1)
    _write_page((docs / "irregularities.html"), _base("Current irregularities and evidence limits", body, "irregularities.html", status=status))

    # Replace rendered score-ceiling text with the corrected research note.
    ceiling = root / "docs/research/score-ceiling-analysis.md"
    if ceiling.exists():
        markdown = _e(ceiling.read_text())
        body = _common_status(status) + f'''<h2>Corrected score-ceiling analysis (source note follows verbatim)</h2>
<p>The Markdown source is authoritative. This escaped rendering is intentionally plain to avoid silently
altering equations or claims during HTML conversion.</p><pre>{markdown}</pre>
<p><a href="research/score-ceiling-analysis.md">Open the Markdown source</a> ·
<a href="research/active-lane-review-2026-10-11.md">active-lane review</a></p>'''
        _write_page((docs / "score-ceiling.html"), _base("Score-ceiling analysis — corrected algebra", body, status=status))

    # Keep a visible current status on remaining historical reports, but remove any stale injected
    # H61/registry-primary recommendation banner before inserting the latest H65-1 notice.
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
            '<a class="btn" href="' + _site_href(art["path"]) + '" download>'
            'Download H65-1 — research only, DO NOT SUBMIT</a>'
        )
        text = re.sub(r'(<div class=dlbtn>).*?(</div>)',
                      lambda m: m.group(1) + research_button + m.group(2), text,
                      count=1, flags=re.S)
        notice_with_class = notice.replace('<div class="banner current-stop-notice">', '<div class="banner current-stop-notice">', 1)
        text = re.sub(r'(<body[^>]*>\s*)', lambda m: m.group(1) + notice_with_class, text, count=1)
        _write_page(page, text)

    # GitHub Pages publishes the repository root; keep root landing/stubs aligned with STOP.
    root_status = _common_status(status, prefix="docs/")
    root_index = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>60GEMSDOE — STOP / research-only artifact</title><link rel="stylesheet" href="docs/assets/site.css">
<meta http-equiv="refresh" content="0; url=docs/index.html"></head><body><main class="wrap">
<h1>60GEMSDOE — current status: STOP</h1>{root_status}
<p><a href="docs/index.html">Open the current evidence site →</a></p></main></body></html>'''
    _write_page((root / "index.html"), root_index)
    for page in sorted(root.glob("*.html")):
        if page.name == "index.html":
            continue
        target = page.name if (docs / page.name).exists() else "research.html"
        root_html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(target)} · 60GEMSDOE</title><link rel="canonical" href="docs/{_e(target)}"><link rel="stylesheet" href="docs/assets/site.css">
<meta http-equiv="refresh" content="0; url=docs/{_e(target)}"></head><body><main class="wrap">
<h1>Current status: STOP</h1>{_common_status(status, prefix="docs/")}
<p><a href="docs/{_e(target)}">Open current page →</a> · <a href="docs/index.html">Home</a></p></main></body></html>'''
        _write_page((root / page.name), root_html)

    return {"status": status["status"], "run": status["active_run"], "artifact": art["path"], "leaderboard_rows": len(snapshot["rows"]), "pages_updated": True}


if __name__ == "__main__":
    print(json.dumps(render(), indent=2))
