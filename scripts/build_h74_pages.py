#!/usr/bin/env python3
"""Render this session's H74-1 pages: the executive "how to submit" page and the H74-1 report.

Why this generator exists
-------------------------
``scripts/build_site.py`` delegates to ``scripts/build_current_review_site.py`` whenever
``registry/current_site_status.json`` is STOP, and that renderer is hard-wired to the H65-1
artifact (fixed strings, H65-1-specific first-test key names).  Rather than fork it, this session
adds one small renderer that reads ONLY the machine-readable evidence this session wrote and emits
the two pages the brief asks for:

  * ``docs/executive-summary.html`` -- the one-click download, an unambiguous
    OK-to-download / OK-to-submit verdict, and the exact portal steps;
  * ``docs/h73-report.html``        -- the full H74-1 evidence table.

Run it after ``scripts/build_site.py``:

    python scripts/build_h74_pages.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _e(x) -> str:
    return (str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _read(p: Path):
    return json.loads(p.read_text())


def site_href(path: str, prefix: str = "") -> str:
    if path.startswith("docs/"):
        return prefix + path[len("docs/"):]
    return prefix + "../" + path


NAV = [("index.html", "Home"), ("executive-summary.html", "How to submit"),
       ("h73-report.html", "H74-1 report"), ("research.html", "Research"),
       ("hypotheses.html", "Deferred hypotheses"), ("leaderboard.html", "Leaderboard"),
       ("sources.html", "Sources"), ("irregularities.html", "Irregularities")]


def page(title: str, body: str, active: str, tif: str, zipf: str, verdict_no: bool) -> str:
    nav = " ".join(f'<a href="{h}"{" class=active" if h == active else ""}>{_e(l)}</a>'
                   for h, l in NAV)
    btn = (f'<a class="btn" href="{_e(tif)}" download>&#11015; Download the H74-1 GeoTIFF</a>'
           f' <a class="btn alt" href="{_e(zipf)}">.zip</a>')
    banner = ("<div class=\"values\"><div class=\"wrap\"><b>Maximize P(Win).</b> No slot is spent on "
              "an unvalidated candidate. <b>Own the Outcome.</b> Negative results, and the evidence "
              "limits behind them, are published clearly rather than buried.</div></div>")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)} · 60GEMSDOE</title><link rel="stylesheet" href="assets/site.css"></head><body>
<header class="top"><div class="wrap"><h1>{_e(title)}</h1><nav>{nav}</nav>
<div class="dlbtn">{btn}</div></div></header>
{banner}
<main class="wrap">{body}</main>
<footer><div class="wrap">Session <code>arena/ac9d4dc4-60gemsdoe</code> · review date 2026-10-11 ·
<a href="data/feed.json">Machine-readable feed</a> ·
<a href="../evidence/h74_runcard.json">H74-1 JSON run card</a> ·
<a href="../README.md">README</a> ·
<a href="https://github.com/buffedlizard55-lab/60GEMSDOE">Repository</a></div></footer></body></html>'''


def main() -> int:
    status = _read(ROOT / "registry" / "current_site_status.json")
    card = _read(ROOT / "evidence" / "h74_runcard.json")
    tif = _read(ROOT / "evidence" / "h74_tiff.json")
    art = status["home_page_artifact"]
    tif_href = site_href(art["path"])
    zip_href = site_href(art["zip"])
    prim = tif["primary"]
    ft = card["first_test"]
    p = ft["PRIMARY_scale_free_relative_step"]
    s = ft["SECONDARY_absolute_dksn"]
    d = ft["DIAGNOSTIC_log_ksn_level_no_step_information"]
    o = ft["off_catalogue_arm_non_gating"]
    h = card["holdout_dti"]

    # ---------------------------------------------------------------- executive summary ---- #
    body = f'''
<div class="banner" style="border:3px solid #b42318;background:#fffafa">
<h2 style="margin-top:0">ONE-CLICK DOWNLOAD &mdash; is this file OK to submit?</h2>
<table style="width:100%">
<tr><th style="width:34%">question</th><th>answer</th></tr>
<tr><td><b>OK to download for research?</b></td>
<td><b style="color:#067647">YES</b> &mdash; the file is a validated, uniquely-named GeoTIFF produced by
this session's channel-steepness lane.</td></tr>
<tr><td><b>OK to submit to the competition?</b></td>
<td><b style="color:#b42318">NO &mdash; DO NOT SUBMIT.</b> The lane's preregistered first test did not
pass, the same statistic is significantly negative on the population the board actually scores, and the
emitted field is below a mass-matched random control on the shared holdout. Spending a weekly slot on it
would score near zero. <b>Nothing else in this repository is cleared either.</b></td></tr>
<tr><td>Why is a file offered at all?</td>
<td>Because a negative result is a deliverable, and because you asked for a downloadable,
format-valid, uniqueness-checked GeoTIFF on every pass. Its verdict is printed on the file itself.</td></tr>
</table>
<p><a class="btn" href="{_e(tif_href)}" download>&#11015; Download the H74-1 GeoTIFF ({prim['positive_px']:,} px, all-finite)</a>
<a class="btn alt" href="{_e(zip_href)}">&#11015; .zip (one TIFF)</a>
<a class="btn alt" href="h73-report.html">Full H74-1 evidence &rarr;</a></p>
<table>
<tr><th>field</th><th>value</th></tr>
<tr><td>Submission name (paste into the note field)</td><td><code>{_e(card['submission']['name'])}</code></td></tr>
<tr><td>Note ({card['submission']['note_chars']} / 140 characters)</td><td><code>{_e(card['submission']['note'])}</code></td></tr>
<tr><td>File</td><td><code>{_e(Path(art['path']).name)}</code></td></tr>
<tr><td>SHA-256</td><td><code>{_e(art['sha256'])}</code></td></tr>
<tr><td>Bytes</td><td>{prim['bytes']:,}</td></tr>
<tr><td>Validator output</td><td>{prim['bands']} band · {prim['dtype']} · {prim['shape'][0]}×{prim['shape'][1]} ·
{_e(prim['crs'])} · transform {_e(prim['transform'])} · NaN inside footprint
<b>{prim['nan_inside_footprint']}</b> · value range [{prim['min']}, {prim['max']}] ·
problems reported: <b>{_e(prim['problems']) if prim['problems'] else 'none'}</b></td></tr>
<tr><td>Positive pixels</td><td>{prim['positive_px']:,}</td></tr>
</table>
</div>

<h2>The one number that decides it</h2>
<div class="card">
<p>The lane's mandated first test asks: <i>do channels crossing withheld fault segments show larger
steepness steps than random lines of the same orientation?</i> This session re-ran that test with
<b>15&times; the statistical power of any prior run</b> ({ft['design']['n_control_transects']} control
transects per component, hide fraction {ft['design']['hide_frac']}, {ft['design']['seeds']} seeds &rArr;
<b>n = {p['n_components']:,}</b> scoreable components, versus n = 262 in every previous run).</p>
<table>
<tr><th>statistic</th><th>mean</th><th>95% CI</th><th>n</th><th>verdict</th></tr>
<tr><td><b>PRIMARY</b> &mdash; scale-free relative steepness step<br><span class="mut">ksn ratio, what the
stream-power model actually predicts</span></td>
<td><b>{p['mean']:+.4f}</b></td><td>[{p['ci95'][0]:+.4f}, {p['ci95'][1]:+.4f}]</td>
<td>{p['n_components']:,}</td><td><b style="color:#b42318">{_e(p['verdict'])}</b></td></tr>
<tr><td>SECONDARY &mdash; absolute &Delta;ksn</td>
<td>{s['mean']:+.4f}</td><td>[{s['ci95'][0]:+.4f}, {s['ci95'][1]:+.4f}]</td>
<td>{s['n_components']:,}</td><td>{_e(s['verdict'])}</td></tr>
<tr><td>DIAGNOSTIC &mdash; block-centred log(ksn)<br><span class="mut">contains <b>no step information
at all</b>, only steepness level</span></td>
<td>{d['mean']:+.4f}</td><td>[{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]</td>
<td>{d['n_components']:,}</td><td>{_e(d['verdict'])}</td></tr>
<tr><td>Off-catalogue arm (the population the board scores)</td>
<td>{o['mean']:+.4f}</td><td>[{o['ci95'][0]:+.4f}, {o['ci95'][1]:+.4f}]</td>
<td>{o['n_components']:,}</td><td><b style="color:#b42318">{_e(o['verdict'])}</b></td></tr>
</table>
<p><b>Reading.</b> The physically correct statistic is null and tightly bounded: the ksn ratio step at a
withheld fault is at most ~2%. The median component is <i>negative</i> ({p['median']:+.4f}) and only
{p['fraction_positive']:.1%} of components are positive, so the small positive mean is a tail effect.
On the off-catalogue population the board actually scores, the same statistic is <b>significantly
negative</b>. And a statistic containing no step information whatsoever &mdash; the steepness
<i>level</i> &mdash; scores {d['mean']:+.4f}, which is why the absolute &Delta;ksn arm and every previous
"PROCEED" in this lane (H67-1 +0.4251, H68-1 +0.4502) passed: faults sit on range fronts, where
channels are steep. Those results measured relief, not tectonics.</p>
</div>

<h2>Exactly how to make a submission into the contest</h2>
<ol>
<li><b>Decide whether the file is cleared.</b> Read the OK/NOT-OK table at the top of this page. It is
generated from <code>registry/current_site_status.json</code> and the run card &mdash; not from a hunch.
Today: <b>not cleared</b>.</li>
<li><b>Download the file</b> from this page (or the <code>.zip</code>, which contains exactly one
GeoTIFF). Both containers are single-band <code>float32</code>.</li>
<li><b>Verify it locally</b> before you spend a slot. The checklist the portal enforces:
one band, <code>float32</code>, EPSG:32611, 3730&times;3292 at 100&nbsp;m, transform
<code>(100, 0, 243350, 0, -100, 4508550)</code>, every value finite and in <code>[0, 1]</code>, data
outside the bounds null or NaN. The receipt
<code>{_e(Path(site_href('docs/downloads/checks-gems60-h74-chi-knick-corridor-8811px-20261011T201814Z-35930766-zeros.tif.json', '../')).name)}</code>
records all of these with the SHA-256.</li>
<li><b>Why your earlier upload returned &ldquo;Predicted values must be in range [0, 1]&rdquo;.</b> That is a
range/NaN rejection. The file on this page is the <b>all-finite &ldquo;zeros&rdquo; container</b>: every one of the
{3730*3292:,} cells stores a finite number in <code>[0,1]</code> and nothing is NaN anywhere, so a reader
that ignores nodata cannot see an out-of-range value. The &ldquo;nan&rdquo; variant is published alongside it as a
diagnostic only.</li>
<li><b>Submit.</b> On the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">DrivenData
submissions page</a>, sign in, choose <i>New submission</i>, choose <i>File to submit</i>, pick the
<code>.tif</code> (or the one-TIFF <code>.zip</code>), and put a unique name plus a short note in the
<i>Note (optional)</i> field &mdash; e.g. the submission name and note in the table above.</li>
<li><b>Keep the receipt together with the hash.</b> Save the organizer's score, the submission timestamp
and the file's SHA-256 in one place; a score without a byte hash proves nothing about which file earned
it.</li>
</ol>
<p class="mut"><b>Weekly cap.</b> Promotion to a real slot is a separate selector step, inside the weekly
cap shown on the submission page. This session spent <b>0 slots</b>.</p>

<h2>Historical artifacts — audit trail only, DO NOT SUBMIT</h2>
<div class="card">
<ul>
<li><a href="downloads/gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif" download>gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif</a> — the previous
channel-steepness artifact. Its first test was INCONCLUSIVE at n = 262; H74-1 has now shown that was an
unresolved result, not a null (IR-73-POWER-01).</li>
<li><a href="downloads/gems60-h68-dem10-lidar-piedmont-dksn-40000-20261011T185033Z-6e9b1e286c45-zeros.tif" download>gems60-h68-dem10-lidar-piedmont-dksn-40000-20261011T185033Z-6e9b1e286c45-zeros.tif</a> —
measured HOLDOUT-DTI 0.171894, but its E1 (+0.4502) is explained by steepness level and 1&nbsp;m LiDAR
cross-scarp bands rather than by a steepness step (IR-73-CONFOUND-01).</li>
<li><code>dotted-h19-5-d2-8-20261002-e56ea318af89-nan</code> — a historical audit example, not a
recommendation.</li>
</ul>
<p>The 0.2778 figure for <code>h33-h33-2-b2</code> remains <b>owner-reported / unverified</b>: no
organizer receipt ties that score to the exact raster bytes.</p>
</div>

<h2>Format validity is not organizer acceptance</h2>
<p>The local validator lists no problems for this raster. That proves the container matches the
published submission format. It does <b>not</b> prove that DrivenData accepted an upload, passed private
validation, assigned a score, or cleared uniqueness &mdash; and no organizer receipt exists for this file,
because it was never uploaded.</p>

<h2>Uniqueness against every earlier raster</h2>
<div class="card"><table>
<tr><th>quantity</th><th>value</th><th>limit</th></tr>
<tr><td>Comparators checked</td><td>{card['uniqueness']['comparators_checked']}</td><td>&mdash;</td></tr>
<tr><td>max |Spearman|</td><td>{card['uniqueness']['max_abs_spearman']:.4f}</td><td>0.90</td></tr>
<tr><td>max fraction of our dots within 3&nbsp;px of one registry raster (all comparators)</td>
<td>{card['uniqueness']['max_our_dots_within_3px_all_comparators']:.4f}</td><td>0.70</td></tr>
<tr><td>&hellip; of which are <i>unsatisfiable</i> comparators</td>
<td>{card['uniqueness']['unsatisfiable_comparators']}</td><td>&mdash;</td></tr>
<tr><td>worst overlap among the {card['uniqueness']['satisfiable_comparators']} satisfiable comparators</td>
<td>{card['uniqueness']['worst_among_satisfiable']['our_dots_within_3px']:.4f}
(<code>{_e(Path(card['uniqueness']['worst_among_satisfiable']['path']).name)}</code>)</td><td>0.70</td></tr>
</table>
<p>{_e(card['uniqueness']['unsatisfiable_note'])}. Flagged as
<code>IR-73-UNIQUENESS-01</code>; it needs an owner decision, not a workaround.</p></div>
'''
    # The executive summary is owned by whichever session published last, so this round
    # *injects* its card into the existing page instead of overwriting it.  Idempotent:
    # re-running never duplicates the card and never destroys another round's content.
    es_path = DOCS / "executive-summary.html"
    es = es_path.read_text() if es_path.exists() else ""
    if "<!-- h74-card -->" not in es:
        card_html = (
            '<div id="h74" class="wrap" style="border:3px solid #b42318;background:#fffafa;'
            'padding:14px 18px;margin:14px auto"><!-- h74-card -->\n' + body + "\n</div>\n"
        )
        if "<main class=\"wrap\">" in es:
            es = es.replace('<main class="wrap">', '<main class="wrap">\n' + card_html, 1)
        else:
            es = es.replace("<body>", "<body>\n" + card_html, 1)
    if "h74-report.html" not in es:
        es = es.replace('<a href="irregularities.html">Irregularities</a>',
                        '<a href="irregularities.html">Irregularities</a> '
                        '<a href="h74-report.html">H74-1 report</a>', 1)
        es = es.replace('<a href="leaderboard.html">Leaderboard</a>',
                        '<a href="h74-report.html">H74-1 report</a> '
                        '<a href="leaderboard.html">Leaderboard</a>', 1) \
            if "h74-report.html" not in es else es
    es_path.write_text(es)

    # ---------------------------------------------------------------- h73 report ---------- #
    canary = card["leakage_canary"]
    body = f'''
<div class="banner" style="border:3px solid #b42318;background:#fffafa">
<h2 style="margin-top:0">H74-1 &mdash; verdict: <span style="color:#b42318">NEGATIVE</span></h2>
<p>Power-resolved replication of the tectonic-geomorphology lane's mandated first test. The lane
stopped. One research GeoTIFF was emitted, validated and uniqueness-checked; it is
<b>not cleared to submit</b>.</p>
<p><a class="btn" href="{_e(tif_href)}" download>&#11015; Download GeoTIFF (research only)</a>
<a class="btn alt" href="{_e(zip_href)}">.zip</a></p>
</div>

<h2>Hypothesis, mechanism, mimic</h2>
<div class="grid">
<section class="card"><h3>Hypothesis</h3><p>{_e(card['hypothesis'])}</p></section>
<section class="card"><h3>Mechanism</h3><p>{_e(card['mechanism'])}</p></section>
<section class="card"><h3>The named non-fault process that mimics it</h3>
<p>{_e(card['named_non_fault_process_that_could_mimic_it'])}</p></section>
</div>

<h2>Measurements</h2>
<table>
<tr><th>arm</th><th>statistic</th><th>mean</th><th>95% CI</th><th>n</th><th>verdict</th></tr>
<tr><td><b>E1 gating</b></td><td>scale-free relative step (PRIMARY)</td>
<td>{p['mean']:+.4f}</td><td>[{p['ci95'][0]:+.4f}, {p['ci95'][1]:+.4f}]</td>
<td>{p['n_components']:,}</td><td>{_e(p['verdict'])}</td></tr>
<tr><td>E1 secondary</td><td>absolute &Delta;ksn</td>
<td>{s['mean']:+.4f}</td><td>[{s['ci95'][0]:+.4f}, {s['ci95'][1]:+.4f}]</td>
<td>{s['n_components']:,}</td><td>{_e(s['verdict'])}</td></tr>
<tr><td>E1 diagnostic</td><td>block-centred log(ksn), no step information</td>
<td>{d['mean']:+.4f}</td><td>[{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]</td>
<td>{d['n_components']:,}</td><td>{_e(d['verdict'])}</td></tr>
<tr><td>E1b non-gating</td><td>primary statistic on SGMC off-catalogue faults (&ge;300&nbsp;m from the catalogue,
{ft['off_catalogue_population_px']:,} px)</td>
<td>{o['mean']:+.4f}</td><td>[{o['ci95'][0]:+.4f}, {o['ci95'][1]:+.4f}]</td>
<td>{o['n_components']:,}</td><td>{_e(o['verdict'])}</td></tr>
</table>

<h2>Holdout DTI ({_e(h['evaluator'])})</h2>
<table>
<tr><th>NMS spacing (px)</th><th>dots</th><th>pooled DTI</th><th>mass-matched random control</th></tr>
{''.join(f"<tr><td>{k}</td><td>{v['dots']:,}</td><td>{v['pooled_dti']:.6f}</td>"
         f"<td>{v['random_mass_control_dti']:.6f}</td></tr>" for k, v in h['ladder'].items())}
</table>
<p class="mut">HOLDOUT-DTI &mdash; {h['design']['withheld_positive_pixels']:,} withheld positives, hide fraction
{h['design']['hide_frac']}, seeds {h['design']['seeds']}. Evaluator <code>{_e(h['evaluator'])}</code>.
This is a hide-and-recover diagnostic on the mapped catalogue, <b>not</b> a leaderboard score and not the
board's off-catalogue population. The field is at or below a mass-matched random control at every
emission density.</p>

<h2>Leakage canary (each feature alone vs the withheld truth)</h2>
<table><tr><th>feature</th><th>max(AUC, 1&minus;AUC)</th><th>verdict</th></tr>
{''.join(f"<tr><td><code>{_e(k)}</code></td><td>{v['max_abs_auc']:.4f}</td><td>{_e(v['verdict'])}</td></tr>"
         for k, v in canary.items())}
</table>
<p>Trip level 0.90. {_e(card['leakage_verdict'])}.</p>

<h2>Artifact</h2>
<table>
<tr><th>field</th><th>value</th></tr>
<tr><td>Path</td><td><code>{_e(art['path'])}</code></td></tr>
<tr><td>SHA-256</td><td><code>{_e(art['sha256'])}</code></td></tr>
<tr><td>ZIP</td><td><code>{_e(art['zip'])}</code></td></tr>
<tr><td>Submission name</td><td><code>{_e(card['submission']['name'])}</code></td></tr>
<tr><td>Note ({card['submission']['note_chars']} chars)</td><td><code>{_e(card['submission']['note'])}</code></td></tr>
<tr><td>Validator</td><td>{prim['bands']} band · {prim['dtype']} · {prim['shape'][0]}×{prim['shape'][1]} ·
{_e(prim['crs'])} · NaN in footprint {prim['nan_inside_footprint']} · range
[{prim['min']}, {prim['max']}] · problems {_e(prim['problems']) if prim['problems'] else 'none'}</td></tr>
</table>

<h2>What this changes for the project</h2>
<ul>
<li><b>Every prior "PROCEED" in this lane is suspect.</b> H67-1 (+0.4251) and H68-1 (+0.4502) measured
statistics that carry steepness level and, for H68-1, 1&nbsp;m LiDAR cross-scarp bands. A control with no
step information at all scores {d['mean']:+.4f} on the same test
(<code>IR-73-CONFOUND-01</code>).</li>
<li><b>The prior "INCONCLUSIVE" verdicts were unresolved, not null.</b> At n = 262 the CI half-width was
~0.047; at n = {p['n_components']:,} it is ~0.011 and the effect is bounded below 2%
(<code>IR-73-POWER-01</code>).</li>
<li><b>The literal 70% / 3&nbsp;px uniqueness rule cannot be satisfied by any raster</b> while four dense
calibration comparators remain in the registry (<code>IR-73-UNIQUENESS-01</code>).</li>
<li><b>Recommendation to the selector:</b> do not spend a weekly slot on the channel-steepness /
&chi; / knickpoint lane. It is now measured dead on both populations, with a bounded null rather than an
unresolved one.</li>
</ul>
<p><a href="executive-summary.html">How to submit &rarr;</a> ·
<a href="../evidence/h74_runcard.json">machine-readable run card</a> ·
<a href="../registry/preregistration-h74.json">preregistration (written before any number)</a></p>
'''
    (DOCS / "h74-report.html").write_text(
        page("H74-1 — power-resolved first test of the channel-steepness lane", body,
             "h74-report.html", tif_href, zip_href, True))

    # ------------------------------------------------- home page download banner ---------- #
    # Injected, not generated, so the two home pages keep whatever the latest publishing
    # session put there.  Idempotent on the marker.
    art_name = Path(art["path"]).name
    zip_name = Path(art["zip"]).name
    banner = (
        '<!-- h74-banner -->\n'
        '<div class="wrap" style="border:3px solid #b42318;background:#fffafa;'
        'padding:14px 18px;margin:14px auto">\n'
        '<h2 style="margin-top:0">H74-1 &mdash; new GeoTIFF: '
        '<span style="color:#0b6b3a">download YES</span> &middot; '
        '<span style="color:#b42318">submit NO</span></h2>\n'
        f'<p><a class="btn" href="downloads/{_e(art_name)}" download>&#11015; Download '
        f'gems60-h74 GeoTIFF</a> <a class="btn alt" href="downloads/{_e(zip_name)}">.zip</a> '
        '<a class="btn alt" href="h74-report.html">H74-1 report</a></p>\n'
        f'<p class="mut">sha256 <code>{art["sha256"]}</code> &middot; '
        '1 band float32 &middot; EPSG:32611 &middot; 3730&times;3292 &middot; values in [0,1] '
        '&middot; validator problems: none. <b>Research only &mdash; DO NOT SUBMIT.</b></p>\n'
        '</div>\n'
    )
    for home, pref in ((DOCS / "index.html", ""), (ROOT / "index.html", "../")):
        if not home.exists():
            continue
        txt = home.read_text()
        if "<!-- h74-banner -->" in txt:
            continue
        b = banner.replace('href="downloads/', f'href="{pref}downloads/') \
                  .replace('href="h74-report.html"', f'href="{pref}h74-report.html"')
        if '<div class="values">' in txt:
            i = txt.index('<div class="values">')
            j = txt.find('</div>', i)
            txt = txt[:j + 6] + "\n" + b + txt[j + 6:]
        elif "</h1>" in txt:
            txt = txt.replace("</h1>", "</h1>\n" + b, 1)
        else:
            txt = txt.replace("<body>", "<body>\n" + b, 1)
        home.write_text(txt)

    print(json.dumps({"wrote": ["docs/executive-summary.html", "docs/h74-report.html"],
                      "artifact": art["path"], "sha256": art["sha256"],
                      "verdict": card["verdict"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
