#!/usr/bin/env python3
"""Generate the static site in docs/ from the committed evidence JSON."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"

CSS = """
:root{--bg:#0f1117;--card:#171a23;--ink:#e8ecf3;--mut:#98a2b3;--acc:#4da3ff;
--ok:#2ecc71;--bad:#ff5c6c;--warn:#f5a623;--line:#242a36}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:28px 20px 90px}
header{border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:26px}
h1{font-size:1.7rem;margin:0 0 6px;letter-spacing:-.015em}
h2{font-size:1.25rem;margin:38px 0 12px;letter-spacing:-.01em}
h3{font-size:1.03rem;margin:24px 0 8px;color:#cbd5e1}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.sub{color:var(--mut);font-size:.94rem}
nav a{margin-right:14px;font-size:.93rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:16px 0}
.status{border-radius:14px;padding:20px 22px;margin:20px 0;border:2px solid}
.stop{border-color:var(--bad);background:#2a1519}
.go{border-color:var(--ok);background:#12241a}
.warn{border-color:var(--warn);background:#2a2312}
.status h2{margin:0 0 6px;font-size:1.2rem}
.pill{display:inline-block;padding:3px 11px;border-radius:999px;font-size:.78rem;
font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.pill.bad{background:#4a1b22;color:#ff9aa5;border:1px solid #7a2a35}
.pill.ok{background:#12351f;color:#7ee2a8;border:1px solid #1f6b3d}
.pill.mut{background:#20242e;color:#9aa4b2;border:1px solid #333a48}
.dl{display:inline-block;background:var(--acc);color:#04121f;font-weight:700;
padding:12px 20px;border-radius:10px;margin:8px 14px 8px 0}
.dl:hover{text-decoration:none;filter:brightness(1.08)}
.dl.dead{background:#3a404d;color:#8b93a1;pointer-events:none}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:.92rem}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:#1d222c;font-weight:600}
code,pre{background:#11141c;border:1px solid var(--line);border-radius:7px;
font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.86rem}
code{padding:2px 6px}pre{padding:14px;overflow-x:auto}
.mut{color:var(--mut)}.ok{color:var(--ok)}.bad{color:var(--bad)}
.foot{margin-top:60px;padding-top:18px;border-top:1px solid var(--line);
color:var(--mut);font-size:.86rem}
"""

NAV = [("index.html", "Home"), ("executive-summary.html", "How to submit"),
       ("method.html", "Method"), ("hypotheses.html", "Hypotheses"),
       ("results.html", "Results"), ("sources.html", "Sources"),
       ("irregularities.html", "Irregularities")]


def page(title: str, body: str, active: str = "index.html") -> str:
    nav = "".join(
        f'<a href="{h}"{" style=color:#e8ecf3" if h == active else ""}>{t}</a>'
        for h, t in NAV)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - 60GEMSDOE</title>
<link rel="stylesheet" href="assets/site.css"></head><body><div class="wrap">
<header><h1>60GEMSDOE &middot; tectonic-geomorphology lane</h1>
<div class="sub">Channel steepness, &chi; and knickpoints &mdash; DOE GEMS Prize
(DrivenData #306). Lane 60 of the parallel run.</div>
<nav style="margin-top:12px">{nav}</nav></header>
{body}
<div class="foot">Every number on this site is labelled <b>HOLDOUT-DTI</b> (evaluator
version, number of withheld positives, 95&nbsp;% CI),
<b>ORGANIZER-PUBLISHED</b>, <b>OWNER-REPORTED</b> or <b>MEASURED</b>.
A projection is never written as a score. Nothing here has been submitted to the
competition by this project.</div></div></body></html>"""


def load(name, default=None):
    p = EV / name
    return json.loads(p.read_text()) if p.exists() else (default or {})


def main() -> None:
    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    (DOCS / "assets" / "site.css").write_text(CSS)
    (DOCS / ".nojekyll").write_text("")

    e1 = load("exp1_first_test.json")
    e2 = load("exp2_sharpened.json")
    e3 = load("exp3_emission.json")
    conn = load("connectivity.json")

    tif = e3.get("file", "gems60-chi-knickpoint-cast-lane-v1-6000-dots-zeros.tif")
    sha = e3.get("sha256", "")

    # ---------------------------------------------------------------- index
    status = f"""
<div class="status stop">
<h2>🔴 Download: OK (research artefact) &nbsp;·&nbsp; Submit to the competition: NO</h2>
<p>The lane's own <b>pre-registered go / no-go test</b> &mdash; <i>&ldquo;do channels
crossing withheld fault segments show larger steepness steps than random lines of the
same orientation? If not, stop&rdquo;</i> &mdash; returned <b>STOP</b>, twice, under two
independently parameterised detectors. The emission also scores
<b>below its own random control</b> on the only holdout available here.
Submitting it would spend one of <b>three weekly competition slots</b> on a field with no
measurable skill, so the status is <b>do not submit</b>. It is published because the brief
requires a unique, reproducible, format-validated GeoTIFF and because
<b>negative results are deliverables</b>.</p>
<p style="margin-bottom:0">The exact thing that would turn this green is named, costed and
verified in <a href="#unblock">What unblocks the lane</a>.</p>
</div>"""

    dl = f"""
<h2>⬇️ The download</h2>
<div class="card">
<p><span class="pill mut">research artefact</span>
<span class="pill bad">not cleared for a submission slot</span></p>
<p><b>{tif}</b><br>
<span class="mut">{e3.get('bytes', 0):,} bytes &middot; sha256
<code>{(sha or '')[:32]}…</code> &middot; {e3.get('n_positive', 0):,} binary dots</span></p>
<p><a class="dl" href="downloads/{tif}">⬇ Download the GeoTIFF</a>
<a class="dl" style="background:#2a3140;color:#cfd6e2"
href="downloads/checks-{tif}.json">format + uniqueness receipt</a></p>
<table>
<tr><th>property</th><th>value</th></tr>
<tr><td>CRS / shape / transform</td><td>EPSG:32611 &middot; 3730 × 3292 &middot;
<code>(100, 0, 243350, 0, -100, 4508550)</code> — matches the submission format</td></tr>
<tr><td>dtype / band</td><td>Float32 &middot; single band &middot; no nodata tag</td></tr>
<tr><td>value range</td><td>all cells finite, 0 NaN, 0 Inf, every value in [0, 1]</td></tr>
<tr><td>outside the footprint</td><td>0 (zero-filled — the validated pattern)</td></tr>
<tr><td>dots on the mapped catalogue</td><td><b>0</b>; minimum distance 2.24 px</td></tr>
<tr><td>local format checks</td><td><b>15 / 15 PASS</b></td></tr>
<tr><td>uniqueness</td><td>worst Spearman <b>ρ = {e3.get('uniqueness', {}).get('worst_spearman_full_footprint', float('nan')):.3f}</b>,
worst 3-px forward overlap <b>{e3.get('uniqueness', {}).get('worst_forward_overlap', float('nan')):.3f}</b>
&rarr; <b>unique</b></td></tr>
<tr><td>built from</td><td>the GeoDAWN 100 m absolute-elevation DEM only. <b>No previous
submission and no template raster was copied, read or reused as input.</b></td></tr>
</table>
<p class="mut">Suggested <i>note</i> field, if you submit it anyway against this advice
({len(e3.get('note', ''))}/140 characters):</p>
<pre>{e3.get('note', '')}</pre>
</div>"""

    body = status + dl + """
<h2>Why the highest GEMSDOE score is 0.2778</h2>
<div class="card">
<p><b>It is a pruning result, not a model result.</b> <code>h33-h33-2-b2</code> is the
owner-reported <b>0.2708</b> raster with <b>2,545 dots deleted and none added</b>; every
removed dot was 1.4&ndash;2.0 px from the mapped catalogue. Source: the family's own
<code>evidence/session6_mechanism_and_witness.json</code>
(<code>equals_base_pruned_at_2px: true</code>).</p>
<p>The metric reduces exactly to
<code>1/DTI = &alpha; + &alpha;&middot;(F/T) + &beta;&middot;(|G|/T)</code>, so adding one
unit of mass raises DTI <i>iff</i> its realised kernel credit exceeds
<code>&alpha;&middot;DTI</code> &mdash; <b>0.052</b> at DTI = 0.26, i.e. the dot must land
within <b>~284 m</b> of a hidden truth pixel. Every deleted dot failed that test.</p>
<p>Beating the leader is therefore a <i>field</i> problem: holding mass and the hidden
|G| fixed, the retained credit <code>T</code> has to rise about <b>+45 %</b>. This
repository does not claim to have done that, and nothing here is written as a score.</p>
</div>
<h2>Public leaderboard (ORGANIZER-PUBLISHED, retrieved 2026-10-10)</h2>
<div class="card"><table>
<tr><th>rank</th><th>participant</th><th>public DTI</th></tr>
<tr><td>1</td><td>xiaofanhu</td><td><b>0.3774</b></td></tr>
<tr><td>2</td><td>JerryDataWorks</td><td>0.3418</td></tr>
<tr><td>3</td><td>alexoktaba</td><td>0.3361</td></tr>
<tr><td>5</td><td>nchuzhoy</td><td>0.3262</td></tr>
<tr><td>8</td><td>DARD</td><td><b>0.3195</b></td></tr>
</table>
<p class="mut">Source:
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">competition
leaderboard</a>. The session brief said the highest score was 0.3195 &mdash; that is rank
8. Recorded as an irregularity.</p></div>

<h2 id="unblock">What unblocks the lane</h2>
<div class="card">
<p>The lane asks for a <b>3DEP 10 m DEM</b>. This sandbox cannot reach the official USGS
bucket: <code>curl https://prd-tnm.s3.amazonaws.com</code> returns
<b>HTTP """ + conn.get("hosts", {}).get("https://prd-tnm.s3.amazonaws.com", {}).get("http_code", "000") + """</b>
(measured, see <code>evidence/connectivity.json</code>). The only absolute-elevation grid
obtainable here is the GeoDAWN 100 m DEM, and at 100 m the base-level step the method
looks for is not resolved — which is the most likely cause of the STOP verdict.</p>
<p><code>scripts/fetch_3dep_10m.sh</code> is written, probes the host, and refuses to
claim success it did not get. Run it where egress is normal; the rest of the lane
(<code>src/gems60/*</code>) then runs unchanged.</p>
</div>"""

    (DOCS / "index.html").write_text(page("Home", body, "index.html"))

    # ------------------------------------------------------ executive summary
    n_ok = sum(1 for v in e3.get("format_checks", {}).values() if v is True)
    ex = f"""
<div class="status stop">
<h2>Executive summary &mdash; read this before uploading anything</h2>
<p><b>Download: OK. Submit to the competition: NO.</b> The file below is a
<b>negative result</b>. It is format-perfect and unique, but this lane failed its own
pre-registered test, so the honest, P(Win)-maximising instruction is: <b>do not spend a
weekly slot on it.</b></p>
</div>

<h2>1. What to download</h2>
<div class="card">
<p><a class="dl" href="downloads/{tif}">⬇ {tif}</a></p>
<p class="mut">{e3.get('bytes', 0):,} bytes &middot; sha256
<code>{sha}</code></p>
</div>

<h2>2. How a submission is actually made (DrivenData #306)</h2>
<div class="card">
<ol>
<li>Open
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">the
submissions page</a> and choose <b>New submission</b>.</li>
<li>Choose the GeoTIFF above (a <code>.tif</code>, or a <code>.zip</code> containing
exactly one GeoTIFF). <b>Do not upload</b> this HTML page, a JSON receipt, or a ZIP of
the repository.</li>
<li>Give it a unique name, e.g. <code>GEMS60-CHI-6000</code>, and paste the
<b>note</b> so you can tell the file apart later (max 140 characters):
<pre>{e3.get('note', '')}</pre></li>
<li>Press submit. The file must match the submission format's CRS, shape and geotransform.</li>
</ol>
<p><b>The error you saw before</b> &mdash; <i>&ldquo;Predicted values must be in range
[0,&nbsp;1]&rdquo;</i> &mdash; happens when a raster carries values outside [0,&nbsp;1]
(NaN, negatives, or a fill such as &minus;9999). <b>This file cannot trigger it:</b> all
cells are finite, there is no nodata tag, every value is exactly 0 or 1, and
<b>{n_ok} / {len(e3.get('format_checks', {}))} independent format checks pass</b>.</p>
</div>

<h2>3. Format checks actually run on this file (re-read from the bytes on disk)</h2>
<div class="card"><table><tr><th>check</th><th>result</th></tr>
""" + "".join(
        f"<tr><td><code>{k}</code></td><td>{'<b class=ok>PASS</b>' if v is True else ('<b class=bad>FAIL</b>' if v is False else v)}</td></tr>"
        for k, v in e3.get("format_checks", {}).items()) + f"""
</table>
<p class="mut"><code>finite_footprint_equals_labels: false</code> is expected and
intentional: this file is zero-filled outside the footprint rather than NaN-filled.
Zero-fill is the pattern used by the family's accepted submissions; NaN-fill is what the
official template does.</p>
</div>

<h2>4. Why the answer is &ldquo;no&rdquo;</h2>
<div class="card"><table>
<tr><th>measurement</th><th>value</th><th>source</th></tr>
<tr><td>Experiment 1 (pre-registered), pooled</td><td>Δmean −0.0229, CI95 [−0.166, +0.162],
p = 1.0, AUC 0.459</td><td><code>evidence/exp1_first_test.json</code></td></tr>
<tr><td>Experiment 2 (corrected), pooled</td><td>Δmean −0.0349,
CI95 [−0.0806, −0.0065], AUC 0.4795</td><td><code>evidence/exp2_sharpened.json</code></td></tr>
<tr><td>channel-normal cast field, holdout AUC</td><td>0.4984 (chance)</td>
<td><code>evidence/exp2_sharpened.json</code></td></tr>
<tr><td>emission vs its own random control, HOLDOUT-DTI</td>
<td>{e3.get('holdout_dti_at_chosen_budget', 0):.5f} vs
{e3.get('controls_at_chosen_budget', {}).get('random_on_offcatalogue_support', 0):.5f}</td>
<td><code>evidence/exp3_emission.json</code></td></tr>
</table>
<p class="mut">Evaluator <code>gems60-buffered-whole-component-v1</code>; 4 buffered
whole-component folds; <b>{e3.get('withheld_positive_pixels', 0):,} withheld positive
pixels</b>; α = 0.2, β = 0.8, 300 m triangular kernel. These are <b>HOLDOUT-DTI</b>
values against the visible catalogue, not competition scores.</p>
</div>

<h2>5. Caveat you must read before drawing a conclusion</h2>
<div class="card warn">
<p>The only truth available locally is the <b>visible catalogue</b>, and that instrument is
<b>anti-monotone against the live leaderboard</b> (the family measured Spearman
ρ = −0.93 between its proxy and 15 owner-reported live scores). So the numbers above
<b>cannot</b> prove the χ lane is worthless on the hidden set — but they also
<b>cannot</b> license a submission. With three slots a week, an unlicensed bet is the
wrong decision.</p>
</div>"""
    (DOCS / "executive-summary.html").write_text(
        page("How to submit", ex, "executive-summary.html"))

    # ----------------------------------------------------------- irregularities
    irr = """
<div class="status warn"><h2>Irregularities flagged for review</h2>
<p>Each item was found while verifying this session's work line by line. None is smoothed
over.</p></div>
<div class="card"><table>
<tr><th>id</th><th>finding</th><th>evidence</th></tr>
<tr><td>IR-60-01</td><td>The session brief states the highest competition score is
<b>0.3195</b>. The organizer-published public leaderboard retrieved 2026-10-10 puts
<b>0.3774</b> at rank 1 and 0.3195 at rank 8.</td>
<td>family snapshot <code>docs/data/leaderboard_snapshot.json</code> (retrieved
2026-10-10T20:40:27Z)</td></tr>
<tr><td>IR-60-02</td><td>The brief's lane requires the <b>3DEP 10 m DEM</b>. That host is
unreachable from this sandbox: <code>prd-tnm.s3.amazonaws.com</code> → HTTP 000
(measured). The lane was therefore run at 100 m, and this is named as the most likely
cause of the negative verdict &mdash; not hidden.</td>
<td><code>evidence/connectivity.json</code></td></tr>
<tr><td>IR-60-03</td><td>The brief's summary attribute <code>h33-h33-2-b2: 0.2778</code>
to the GEMSDOE32 site. That repository's own README states <b>no organizer score exists</b>
for it (projected 0.2747). The number <b>0.2778</b> is present on the public board at rank
22, participant <code>extradr19</code>.</td>
<td>GEMSDOE32 README + leaderboard snapshot</td></tr>
<tr><td>IR-60-04</td><td>The official 19-band feature stack contains only
<b>detrended</b> elevation (<code>det_elev</code>, <code>det_elev_slope</code>). A χ
transform is undefined on it. Every previous family session that claimed a "drainage" or
"valley chain" feature was working without absolute elevation.</td>
<td>band descriptions read from
<code>data/bridge/gems-geodawn-numerical-features.tif</code> (sha256 4371c82e…)</td></tr>
<tr><td>IR-60-05</td><td>The off-catalogue emission rule inherited from the family
(<b>0 dots within 2 px of the catalogue</b>) is <b>degenerate on a catalogue-truth
holdout</b>: mass placed there is forbidden from being near the very truth it is scored
against. Both readings (family ρ = −0.93; this session's Experiment 3) agree that the
proxy cannot rank placements. Reported, not tuned away.</td>
<td><code>evidence/exp3_emission.json</code></td></tr>
<tr><td>IR-60-06</td><td>Uniqueness could only be checked against the
<b>170</b> registry rasters whose bytes are obtainable in this sandbox, not all 696 listed
family-wide. This is a stated <b>scope limitation</b>, never a claim of absence.</td>
<td><code>evidence/exp3_emission.json → uniqueness.scope_note</code></td></tr>
<tr><td>IR-60-07</td><td>Two bugs were found by brute-force verification while building
this lane and are fixed in the committed code: (a) D8 routing was allowed to flow into
nodata cells, which made <b>100 %</b> of flow paths terminate after one step; (b) the
CSR gather in the breadth-first flow sweep mixed two coordinate systems. Both were caught
by <code>tests/test_hydro.py</code> before any scientific number was produced.</td>
<td><code>tests/test_hydro.py</code> (14 tests, all passing)</td></tr>
</table></div>"""
    (DOCS / "irregularities.html").write_text(
        page("Irregularities", irr, "irregularities.html"))

    # ---------------------------------------------------------------- sources
    rows = [
        ("metric, kernel, α, β, submission format, worked example",
         "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"),
        ("competition data tab (login required)",
         "https://www.drivendata.org/competitions/306/competition-doe-gems/data/"),
        ("public leaderboard 0.3774 / 0.3195",
         "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"),
        ("official rules PDF", "https://docs.nlr.gov/docs/fy26osti/96647.pdf"),
        ("reference solution (author: Prof. John Lipor)",
         "https://github.com/drivendataorg/gems-prize-reference-solution"),
        ("absolute-elevation GeoDAWN DEM used here (22103_dem_a2.tif)",
         "https://github.com/jklinck/geothermal_research/tree/main/GeoDAWN_tiffs/22103_area2_tiffs"),
        ("GeoDAWN airborne magnetic & radiometric survey",
         "https://doi.org/10.5066/P93LGLVQ"),
        ("INGENIOUS geothermal compilation (GDR 1391)",
         "https://gdr.openei.org/submissions/1391"),
        ("USGS 3DEP / National Map downloader",
         "https://apps.nationalmap.gov/downloader/"),
        ("Perron & Royden (2013) χ transform, Earth Surf. Dynam. 1, 45–61",
         "https://doi.org/10.5194/esurf-1-45-2013"),
        ("Gailleton et al. (2019) knickpoint segmentation, Earth Surf. Dynam. 7, 707–725",
         "https://doi.org/10.5194/esurf-7-707-2019"),
        ("Wobus et al. (2006) θ_ref = 0.45, GSA SP 398",
         "https://doi.org/10.1130/2006.2398(03)"),
        ("Kirby & Whipple (2012) active tectonics in erosional landscapes",
         "https://doi.org/10.1016/j.jsg.2012.07.009"),
        ("Barnes, Lehman & Mulla (2014) priority-flood",
         "https://doi.org/10.1016/j.cageo.2013.09.008"),
        ("O'Callaghan & Mark (1984) D8 routing",
         "https://doi.org/10.1016/S0734-189X(84)80011-0"),
        ("Tversky index (context for DTI)",
         "https://en.wikipedia.org/wiki/Tversky_index"),
        ("EPSG:32611 (UTM 11N, the competition CRS)", "https://epsg.io/32611"),
        ("family repository that documents the pruning mechanism behind 0.2778",
         "https://github.com/buffedlizard55-lab/57GEMSDOE"),
        ("family repository of the 0.2778 artefact", "https://github.com/buffedlizard55-lab/GEMSDOE32"),
    ]
    src = "<h2>Sources, for manual review</h2><div class='card'><table>" \
          "<tr><th>claim</th><th>source</th></tr>" + "".join(
              f'<tr><td>{c}</td><td><a href="{u}">{u}</a></td></tr>' for c, u in rows) \
          + "</table></div>"
    (DOCS / "sources.html").write_text(page("Sources", src, "sources.html"))

    # ---------------------------------------------------------------- method
    method = """
<h2>The method, in one page</h2>
<div class="card">
<h3>1. Absolute elevation (the thing the family never had)</h3>
<p>The official 19-band stack carries a <b>detrended</b> elevation only. A χ transform
cannot be computed from it. This session obtained the GeoDAWN absolute DEM
(<code>22103_dem_a2.tif</code>, 100 m, the same 3730 × 3292 grid as the competition
rasters) from the public <code>jklinck/geothermal_research</code> repository and verified
alignment cell by cell. sha256
<code>d32762a38222764389e948da423ebc6cadd00ac617ad3938d3dd79c6cfe14431</code>.</p>
<h3>2. Hydrology</h3>
<p>Priority-flood depression filling (Barnes et al. 2014) then D8 routing
(O'Callaghan &amp; Mark 1984), then drainage accumulation. Verified against independent
brute-force implementations on random DEMs. Measured here: maximum accumulation
1,287,069 px, 899,623 cells filled (17.4 % of the valid grid — the Great Basin's internal
drainage, the named playa confound).</p>
<h3>3. χ and normalised steepness</h3>
<p><code>χ(x) = ∫<sub>x_b</sub><sup>x</sup> (A₀/A(x′))<sup>θ</sup> dx′</code> with
θ = 0.45 (Wobus et al. 2006). In χ–z space the profile slope <i>is</i> the normalised
channel steepness <code>ksn = (U/K)^(1/n)</code> (Perron &amp; Royden 2013). A fault
crossing a channel puts a base-level step there: a break in the χ-profile.</p>
<h3>4. Knickpoints by reproducible segmentation</h3>
<p>For every candidate breakpoint in the middle of a sliding window, fit two lines and
compare with one line. The <b>segment contrast</b>
<code>C = (SSE₁ − SSE₂)/SSE₁</code> is maximised over the breakpoint; local maxima above a
declared threshold are knickpoints, with declared window and separation. This is the
explicit, parameter-declared form of the Gailleton et al. (2019) segmentation.</p>
<h3>5. Multi-drainage alignment: channel-normal casting</h3>
<p>A fault trace crosses a channel roughly <b>perpendicular</b> to it. Each candidate
crossing therefore casts a short segment along the local channel <b>normal</b>, weighted
by its step magnitude. Where several <b>independent drainages</b> cast across one common
strike, the casts reinforce and a continuous fault trace emerges. Crossings that belong to
no common strike cancel out. This is the operational form of the lane's requirement.</p>
<h3>6. Holdout</h3>
<p>Buffered <b>whole-component</b> hide-and-recover: the catalogue is split into 8-connected
components, each assigned whole to one spatial quadrant, visible catalogue within 3 px
(300 m) of a withheld component removed, emission over the <i>whole</i> raster, and the
score <b>pooled</b> over folds with a paired 512-px block bootstrap. 56,619 withheld
positive pixels.</p>
<h3>7. Emission</h3>
<p>The metric's own optimum: peaks of the field at ≥ 2 px separation, taken in decreasing
order of value up to the budget that maximises the pooled HOLDOUT-DTI.</p>
</div>"""
    (DOCS / "method.html").write_text(page("Method", method, "method.html"))

    # ------------------------------------------------------------ hypotheses
    hyp = (ROOT / "docs" / "hypotheses.md")
    rows_h = [
        ("1", "Re-run this exact lane on a 10 m 3DEP DEM",
         "χ-profile segmentation at 10 m; the step is 10× better resolved",
         "low", "3DEP 10 m — NOT reachable here (HTTP 000)"),
        ("2", "χ-transient inversion (uplift history) instead of a χ-steady step",
         "χ(z) inverted for U(t); a young fault's step has a diagnostic χ position",
         "medium", "none — DEM already committed"),
        ("3", "Knickpoint recurrence in χ across basins, not knickpoint position",
         "a tectonic step recurs at a fixed χ; a lithologic step does not",
         "low", "none"),
        ("4", "Closed-basin / playa base-level mask", "the priority-flood depression inventory",
         "very low", "none"),
        ("5", "Lithology-normalised ksn (Great Basin Quaternary volcanics)",
         "ksn residual after an erodibility proxy", "medium",
         "great_basin_q_volcanics — public, already mirrored"),
    ]
    hy = ("<h2>Five ranked, untried hypotheses</h2>"
          "<div class='card'><p class='mut'>Ranked by expected DTI gain per unit cost. "
          "Full text with the why-off-catalogue argument: "
          "<a href='https://github.com/buffedlizard55-lab/60GEMSDOE/blob/main/docs/hypotheses.md'>"
          "docs/hypotheses.md</a>.</p><table>"
          "<tr><th>#</th><th>hypothesis</th><th>signature</th><th>cost</th>"
          "<th>free official data needed</th></tr>"
          + "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td><td>{e}</td></tr>"
                    for a, b, c, d, e in rows_h) + "</table></div>")
    hy += ("<div class='card warn'><p><b>Caution.</b> The only local truth is the visible "
           "catalogue, and that instrument is anti-monotone against the live ladder "
           "(family ρ = −0.93). A hypothesis can only be <i>killed</i> locally, never "
           "<i>confirmed</i> locally — except rank 1, whose failure mode at 100 m is a "
           "resolution artefact.</p></div>")
    (DOCS / "hypotheses.html").write_text(page("Hypotheses", hy, "hypotheses.html"))

    # --------------------------------------------------------------- results
    def fmt_pf(pf):
        return "".join(
            f"<tr><td>{r['fold']}</td><td>{r['n_crossing']:,}</td><td>{r['n_control']:,}</td>"
            f"<td>{r['median_crossing']:+.4f}</td><td>{r['median_control']:+.4f}</td>"
            f"<td>{r.get('auc', float('nan')):.4f}</td><td>{r['p_one_sided']:.3g}</td></tr>"
            for r in pf)

    res = f"""
<h2>Experiment 1 &mdash; the pre-registered first test</h2>
<div class="card">
<p>Evaluator <code>{e1.get('evaluator_version')}</code>, 4 buffered whole-component folds,
<b>{e1.get('withheld_positive_pixels', 0):,} withheld positive pixels</b>, α = 0.2,
β = 0.8, 300 m triangular kernel.</p>
<table><tr><th>fold</th><th>n crossing</th><th>n control</th><th>median Σ crossing</th>
<th>median Σ control</th><th>AUC</th><th>p (one-sided)</th></tr>
{fmt_pf(e1.get('per_fold', []))}
</table>
<p>Pooled: n crossing {e1.get('pooled', {}).get('n_crossing', 0):,},
n control {e1.get('pooled', {}).get('n_control', 0):,},
Δmean <b>{e1.get('pooled', {}).get('delta_mean', 0):+.4f}</b>,
CI95 <b>[{e1.get('pooled', {}).get('ci95_delta', [0, 0])[0]:+.4f},
{e1.get('pooled', {}).get('ci95_delta', [0, 0])[1]:+.4f}]</b>,
p = <b>{e1.get('pooled', {}).get('p_one_sided', 1):.3g}</b>,
leakage canary AUC = {e1.get('pooled', {}).get('leakage_canary_auc', float('nan')):.4f}.
<b>Verdict: {e1.get('verdict', '').upper()}.</b></p>
</div>

<h2>Experiment 2 &mdash; corrected statistic and matched control</h2>
<div class="card">
<p><b>Why a second run.</b> Experiment 1's segmentation window was 31 samples = 3.1 km,
about ten times longer than the base-level step it was supposed to localise, and its
control was an unrelated translated line. Both defects were named <i>before</i> the rerun;
the decision rule was unchanged.</p>
<table><tr><th>fold</th><th>n crossing</th><th>n control</th><th>median Σ crossing</th>
<th>median Σ control</th><th>AUC</th><th>p (one-sided)</th></tr>
{fmt_pf(e2.get('armA_vs_control', {}).get('per_fold', []))}
</table>
<p>Pooled: Δmean
<b>{e2.get('armA_vs_control', {}).get('delta_mean', 0):+.4f}</b>,
CI95 <b>[{e2.get('armA_vs_control', {}).get('ci95_delta', [0, 0])[0]:+.4f},
{e2.get('armA_vs_control', {}).get('ci95_delta', [0, 0])[1]:+.4f}]</b>,
AUC {e2.get('armA_vs_control', {}).get('auc', float('nan')):.4f}.
<b>Verdict: {e2.get('verdict', '').upper()}.</b> The interval excludes zero on the
<b>wrong side</b>.</p>
<h3>Surfaces scored as rankers of withheld fault pixels</h3>
<table><tr><th>surface</th><th>signed AUC</th><th>|·| AUC</th></tr>
<tr><td>sharpened steepness step Σ</td>
<td>{e2.get('holdout_auc_surfaces', {}).get('sigma', {}).get('auc_signed', float('nan')):.4f}</td>
<td>{e2.get('holdout_auc_surfaces', {}).get('sigma', {}).get('auc_abs', float('nan')):.4f}</td></tr>
<tr><td>χ-residual step</td>
<td>{e2.get('holdout_auc_surfaces', {}).get('resid', {}).get('auc_signed', float('nan')):.4f}</td>
<td>{e2.get('holdout_auc_surfaces', {}).get('resid', {}).get('auc_abs', float('nan')):.4f}</td></tr>
<tr><td><b>channel-normal cast count</b></td><td>—</td>
<td><b>{e2.get('cast_field', {}).get('auc', float('nan')):.4f}</b></td></tr>
</table>
</div>

<h2>Experiment 3 &mdash; emission, format, uniqueness</h2>
<div class="card">
<table><tr><th>n dots</th><th>HOLDOUT-DTI, off-catalogue support</th>
<th>HOLDOUT-DTI, unrestricted support</th></tr>
""" + "".join(
        f"<tr><td>{k}</td><td>{e3.get('budget_curve_offcatalogue', {}).get(k, float('nan')):.5f}</td>"
        f"<td>{e3.get('budget_curve_unrestricted', {}).get(k, float('nan')):.5f}</td></tr>"
        for k in sorted(e3.get("budget_curve_offcatalogue", {}),
                        key=lambda x: int(x))) + f"""
</table>
<p>Chosen budget <b>{e3.get('chosen_budget', 0):,}</b> dots
(max of the off-catalogue curve, a rule fixed before the sweep was read).
Holdout DTI <b>{e3.get('holdout_dti_at_chosen_budget', 0):.5f}</b> against matched
controls: random-on-the-same-support <b>{e3.get('controls_at_chosen_budget', {}).get('random_on_offcatalogue_support', 0):.5f}</b>,
random-in-footprint <b>{e3.get('controls_at_chosen_budget', {}).get('random_in_footprint', 0):.5f}</b>.
The field is at or below its own random control.</p>
<p><b>Uniqueness</b> (thresholds ρ ≤ 0.90, forward overlap ≤ 0.70): worst Spearman
<b>{e3.get('uniqueness', {}).get('worst_spearman_full_footprint', 0):.4f}</b>, worst 3-px
forward overlap <b>{e3.get('uniqueness', {}).get('worst_forward_overlap', 0):.4f}</b>
over {e3.get('uniqueness', {}).get('rasters_checked', 0)} obtainable registry rasters
&rarr; <b>unique = {e3.get('uniqueness', {}).get('unique')}</b>.
<i>Scope limitation:</i> {e3.get('uniqueness', {}).get('scope_note', '')}</p>
</div>"""
    (DOCS / "results.html").write_text(page("Results", res, "results.html"))

    print("site written to", DOCS)


if __name__ == "__main__":
    main()
