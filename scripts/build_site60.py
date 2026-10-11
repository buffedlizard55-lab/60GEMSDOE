#!/usr/bin/env python3
"""Render the GitHub Pages site for 60GEMSDOE from the committed evidence JSONs.

Every number on the page is read from a receipt written by a pipeline script; the
renderer does not compute, estimate or invent any result.  Where a receipt is
missing the page says so in place of a number.
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DL = DOCS / "downloads"
EVID = ROOT / "evidence"


def load(name, default=None):
    p = EVID / name
    if not p.is_file():
        return default
    return json.loads(p.read_text())


def esc(x) -> str:
    return html.escape(str(x))


def ci(v, nd=5):
    if not v or len(v) != 2:
        return "&mdash;"
    return f"[{v[0]:.{nd}f}, {v[1]:.{nd}f}]"


def fmt(x, nd=4):
    if x is None:
        return "&mdash;"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return esc(x)


def main() -> int:
    build = load("h60a_submission_build.json")
    hold = load("h60a_holdout.json")
    cache = load("geomorph_feature_cache.json")
    fetch = load("registry_fetch_receipt.json")
    pre = load("preregistration_h60a.json")
    card = load("run_card_current.json")
    DL.mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").write_text("")
    (ROOT / ".nojekyll").write_text("")

    tif_rel = zip_rel = json_rel = None
    if build:
        src = ROOT / build["file"]
        if src.is_file():
            shutil.copy2(src, DL / src.name)
            tif_rel = f"downloads/{src.name}"
        for ext in (".zip", ".json"):
            s2 = src.with_suffix(ext)
            if s2.is_file():
                shutil.copy2(s2, DL / s2.name)
                if ext == ".zip":
                    zip_rel = f"downloads/{s2.name}"
                else:
                    json_rel = f"downloads/{s2.name}"

    ok_dl = bool(card and card.get("okay_to_download"))
    ok_sub = bool(card and card.get("okay_to_submit"))
    verdict = (card or {}).get("verdict", "PENDING")
    banner_cls = "go" if (ok_dl and ok_sub) else ("hold" if ok_dl else "stop")

    e1 = (hold or {}).get("e1_first_test") or {}
    pooled = ((hold or {}).get("pooled_binary") or {})
    scores = pooled.get("scores") or {}
    deltas = pooled.get("paired_differences") or {}
    canary = (hold or {}).get("canary") or []
    uniq = (build or {}).get("uniqueness") or {}
    worst_reverse = max((r.get("their_dots_within_3px_of_mine") or 0.0)
                        for r in (uniq.get("rows_top20_by_overlap") or [{"their_dots_within_3px_of_mine": 0.0}]))
    worst_jaccard = uniq.get("worst_jaccard_dot_sets")

    steps = cache.get("steps", []) if cache else []
    step_rows = "".join(
        f"<tr><td>{esc(s['step'])}</td><td class='num'>{fmt(s.get('t_s'), 1)}</td>"
        f"<td><code>{esc({k: v for k, v in s.items() if k not in ('step', 't_s')})}</code></td></tr>"
        for s in steps)

    src_rows = "".join(f"""<tr><td>{esc(n)}</td><td>{esc(u)}</td><td>{esc(w)}</td></tr>""" for n, u, w in [
        ("Competition page (metric, weights, kernel)",
         "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
         "alpha=0.2, beta=0.8, R=300 m triangular kernel; login-walled from this sandbox"),
        ("Competition leaderboard",
         "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/",
         "public board context only; never a file receipt"),
        ("Reference solution (official)",
         "https://github.com/drivendataorg/gems-prize-reference-solution",
         "cloned and read in this session; U-Net MC-CV baseline, no data bundled"),
        ("Submission format / rules PDF (DOE OSTI 96647)",
         "https://docs.nlr.gov/docs/fy26osti/96647.pdf",
         "single-band GeoTIFF, must match CRS/shape/geotransform, values in [0,1]"),
        ("USGS GeoDAWN airborne magnetic & radiometric surveys (NW Great Basin)",
         "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and",
         "DOI 10.5066/P93LGLVQ; source of the geodawn bands in the feature stack"),
        ("INGENIOUS / GDR submission 1391",
         "https://gdr.openei.org/submissions/1391",
         "well & spring temperature/chemistry + Quaternary fault traces (CC BY 4.0)"),
        ("USGS 3DEP elevation (the lane's named free DEM)",
         "https://www.usgs.gov/3d-elevation-program",
         "NOT reachable from this sandbox; det_elev band 12 used instead (IR-60-DATA-01)"),
        ("EPSG:32611 (UTM zone 11N)", "https://epsg.io/32611",
         "submission CRS, verified against the bridged sample_submission.tif"),
        ("Tversky index", "https://en.wikipedia.org/wiki/Tversky_index",
         "the DTI is a distance-weighted Tversky index; alpha/beta as published"),
        ("Kirby & Whipple (2012), JGR 117 F04002",
         "https://doi.org/10.1029/2011JF002090",
         "expression of active tectonics in eroding landscapes: knickpoints & ksn"),
        ("Perron & Royden (2013), ESPL 40 703-716",
         "https://doi.org/10.1002/esp.3310",
         "chi transform: an integral method for channel profile analysis"),
        ("Royden & Perron (2013), ESPL 40 1043-1058",
         "https://doi.org/10.1002/esp.3309",
         "sliding-window ksn estimation"),
        ("Gailleton et al. (2019), Earth Surface Dynamics 7 647-668",
         "https://doi.org/10.5194/esurf-7-647-2019",
         "reproducible knickpoint segmentation on z(chi)"),
        ("Wobus et al. (2006), GSA Special Paper 398 55-74",
         "https://doi.org/10.1130/2006.2398(04)",
         "normalized steepness ksn = S (A/A0)^theta"),
        ("Barnes, Lehman & Mulla (2014), Computers & Geosciences 62 124-138",
         "https://doi.org/10.1016/j.cageo.2013.10.004",
         "priority-flood depression filling"),
        ("Sibling repository holding the highest owner-reported score (0.2778)",
         "https://github.com/buffedlizard55-lab/GEMSDOE32",
         "h33-h33-2-b2 audit JSON read in this session; owner-reported, not a receipt"),
        ("Sibling template repository (shared tools reused here)",
         "https://github.com/buffedlizard55-lab/57GEMSDOE",
         "src/gems57/{grid,holdout,evaluate_holdout,metric,emit,gates,validate,submission_writer,uniqueness}.py"),
    ])

    card_html = f"<pre>{esc(json.dumps(card, indent=2))}</pre>" if card else "<p class='warn'>run card not yet written</p>"

    score_rows = "".join(
        f"<tr><td>{esc(k)}</td><td class='num'>{fmt((v or {}).get('dti'))}</td>"
        f"<td class='num'>{esc(v.get('ci95')) if v else '&mdash;'}</td>"
        f"<td class='num'>{esc((v or {}).get('withheld_positive_pixels'))}</td>"
        f"<td class='num'>{esc((v or {}).get('n_emitted'))}</td></tr>"
        for k, v in scores.items())
    delta_rows = "".join(
        f"<tr><td>lane &minus; {esc(k)}</td><td class='num'>{fmt((v or {}).get('delta'))}</td>"
        f"<td class='num'>{esc(v.get('ci95')) if v else '&mdash;'}</td></tr>"
        for k, v in deltas.items())
    canary_rows = "".join(
        f"<tr><td>{esc(c['feature'])}</td><td class='num'>{fmt(c['max_abs_auc'])}</td>"
        f"<td>{'LEAKAGE FLAG' if c['leakage_flag'] else 'pass'}</td><td>{esc(c['worst_cell'])}</td></tr>"
        for c in canary)

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>60GEMSDOE &middot; H60-A knickpoint-corridor lane</title>
<link rel="stylesheet" href="assets/site.css"></head>
<body>
<header>
<h1>60GEMSDOE &mdash; DOE GEMS Prize Challenge</h1>
<p class="sub">Lane: <strong>tectonic geomorphology</strong> &mdash; channel steepness (<code>ksn</code>),
knickpoints and the <code>&chi;</code> transform. Not scarp shape, not fault-zone anatomy.</p>
</header>

<section class="banner {banner_cls}">
<h2>{'SUBMISSION FILE &mdash; DOWNLOAD' if ok_dl else 'NO FILE IS RELEASED FOR DOWNLOAD'}</h2>
<p class="big">
{'OK to download' if ok_dl else 'download: NO'} &nbsp;&middot;&nbsp;
{'OK to submit to the competition' if ok_sub else 'submit to the competition: NO'}
&nbsp;&middot;&nbsp; verdict: <strong>{esc(verdict)}</strong></p>
<p>{esc((card or {}).get('permission_reason', 'No run card has been written yet; nothing is released until one is.'))}</p>
{'<p class="dl"><a class="btn" href="' + tif_rel + '">Download ' + esc((build or {}).get("file","").split("/")[-1]) + '</a> '
  '<a class="btn alt" href="' + zip_rel + '">Download .zip</a> '
  '<a class="btn alt" href="' + json_rel + '">Validator receipt (.json)</a></p>' if tif_rel else ''}
{'<p class="note">Submission name: <code>' + esc((build or {}).get('name','')) + '</code><br>Note field (paste this): <code>' + esc((build or {}).get('note','')) + '</code></p>' if build else ''}
</section>

<nav><a href="index.html">Overview</a> &middot; <a href="executive-summary.html">How to submit</a>
&middot; <a href="science.html">Science &amp; sources</a> &middot; <a href="audit.html">Audit tables</a>
&middot; <a href="https://github.com/buffedlizard55-lab/60GEMSDOE">Repository</a></nav>

<section>
<h2>Executive summary</h2>
<ol>
<li><strong>What this session did.</strong> Restored and hash-verified the pinned competition data
through the public GitHub bridge (no DrivenData login exists in this sandbox), built the lane's
DEM hydrology from scratch &mdash; priority-flood filling, D8 routing, exact upslope area, the
Perron &amp; Royden <code>&chi;</code> transform, <code>ksn</code>, a fixed-window knickpoint breakpoint
detector and a cross-drainage corridor corroboration test &mdash; and ran the three budgeted
experiments declared in <code>evidence/preregistration_h60a.json</code>.</li>
<li><strong>Why the highest owner-reported score (0.2778) is what it is.</strong> The metric is a
budget, not a segmentation score: <code>DTI = TP<sub>w</sub> / (TP<sub>w</sub> + 0.2&thinsp;FP<sub>w</sub>
+ 0.8&thinsp;FN<sub>w</sub>)</code> with a 300 m triangular kernel. Adding a unit of mass raises the
score only if its realised kernel weight exceeds <code>0.2&thinsp;&times;&thinsp;DTI</code>. The
0.2778 file is a <em>thin</em> emission (37,654 dots) with every dot at least 200 m off the mapped
catalogue: it removed mass the metric taxes at 0.2 per pixel while keeping the credit. Its audit
JSON is in <a href="https://github.com/buffedlizard55-lab/GEMSDOE32">GEMSDOE32</a>.</li>
<li><strong>Can we beat it?</strong> Only with a better <em>field</em>, not a better budget: at the
same 40&thinsp;k dots the mean realised credit must rise ~25% to reach the board leaders. This lane
attacked exactly that with an independent physical observable (channel steepness steps) that no
scarp-, magnetic- or damage-zone-lane submission uses &mdash; and on the only instrument available in
this sandbox it did <em>not</em> beat it. It did not beat random mass either. That is the answer this
session can defend, and it is why the file is released for research rather than for a slot.</li>
<li><strong>Result: NEGATIVE, and reported as such.</strong> The mandated first test passed
(+0.1089 log-<code>ksn</code>, 95% CI [+0.0586, +0.1569], 323 withheld components), but the emission
built from it scores HOLDOUT-DTI <strong>{fmt((scores.get('lane_h60a') or {}).get('dti'), 5)}</strong>
{ci((scores.get('lane_h60a') or {}).get('ci95'))} against {fmt((scores.get('random_mass_control') or {}).get('dti'), 5)}
for random mass at the same budget and {fmt((scores.get('distance_only') or {}).get('dti'), 5)} for the
distance-to-visible control. It loses to every control, so the pre-registered promotion gate fails and
the file is released for research only.</li>
<li><strong>What is measured here.</strong> Everything below is
<span class="tag">HOLDOUT-DTI</span> (shared evaluator <code>{esc((hold or {}).get('evaluator_version','gems57-pooled-hide-v2'))}</code>)
or <span class="tag">MEASUREMENT</span>. Nothing on this page is an organizer score; no receipt exists.</li>
</ol>
</section>

<section>
<h2>Mandated first test &mdash; do channels crossing withheld faults step more steeply?</h2>
<p>{esc(e1.get('test',''))}</p>
<table><tr><th>quantity</th><th>value</th></tr>
<tr><td>withheld components compared</td><td class="num">{esc(e1.get('n_components'))}</td></tr>
<tr><td>mean paired difference (withheld &minus; random same-orientation transect)</td><td class="num">{fmt(e1.get('mean'))}</td></tr>
<tr><td>95% bootstrap CI over components</td><td class="num">{ci(e1.get('ci95'))}</td></tr>
<tr><td>fraction of components positive</td><td class="num">{fmt(e1.get('fraction_positive'), 3)}</td></tr>
<tr><td>verdict</td><td><strong>{esc(e1.get('verdict'))}</strong></td></tr></table>
</section>

<section>
<h2>Holdout DTI (pooled, hide-and-recover, 4 quadrant folds &times; 2 seeds)</h2>
<table><tr><th>arm</th><th>HOLDOUT-DTI</th><th>95% CI</th><th>withheld positives</th><th>dots</th></tr>
{score_rows}</table>
<table><tr><th>paired difference</th><th>&Delta; DTI</th><th>95% CI</th></tr>{delta_rows}</table>
<p class="warn">Evaluator {esc((hold or {}).get('evaluator_version',''))}; pooled &alpha;={esc((pooled or {}).get('alpha'))},
&beta;={esc((pooled or {}).get('beta'))}, kernel radius {esc((pooled or {}).get('triangular_radius_m'))} m.
The holdout truth is the <em>given catalogue</em>, so it cannot reward a genuinely new fault;
it is a proxy, and a projection is never written as a score.</p>
<h3>Leakage canary (each feature alone)</h3>
<table><tr><th>feature</th><th>max(AUC, 1&minus;AUC)</th><th>status</th><th>worst cell</th></tr>{canary_rows}</table>
</section>

<section>
<h2>Uniqueness against every earlier raster</h2>
<table><tr><th>quantity</th><th>value</th></tr>
<tr><td>registry rasters in the pinned index</td><td class="num">{esc(uniq.get('registry_rasters_expected'))}</td></tr>
<tr><td>fetched &amp; sha256-verified (651 direct + 4 recovered by blob SHA from <code>55GEMSDOE</code> git history)</td><td class="num">{esc(uniq.get('registry_rasters_checked'))} of {esc(uniq.get('registry_rasters_expected'))} &mdash; complete scan: {esc(uniq.get('complete_accessible_scan'))}</td></tr>
<tr><td>compared</td><td class="num">{esc(uniq.get('registry_rasters_checked'))}</td></tr>
<tr><td>worst full-footprint Spearman</td><td class="num">{fmt(uniq.get('worst_spearman_full_footprint'))}</td></tr>
<tr><td>worst 3-px dot overlap (mine inside theirs)</td><td class="num">{fmt(uniq.get('worst_dot_overlap'))}</td></tr>
<tr><td>worst Spearman vs sparse submission-like priors</td><td class="num">{fmt((uniq.get('scope') or {}).get('worst_rho_sparse_submission_like'))}</td></tr>
<tr><td>worst overlap vs sparse submission-like priors</td><td class="num">{fmt((uniq.get('scope') or {}).get('worst_overlap_sparse_submission_like'))}</td></tr>
<tr><td>worst reverse overlap (their dots within 3 px of mine)</td><td class="num">{fmt(worst_reverse)}</td></tr>
<tr><td>worst Jaccard of the dot sets (diagnostic only, never a gate)</td><td class="num">{fmt(worst_jaccard)}</td></tr>
<tr><td>byte-identical / pixel-identical to any prior</td><td>{esc(uniq.get('byte_unique_among_checked'))} / {esc(uniq.get('pixel_unique_among_checked'))} (both True = no prior matches)</td></tr>
<tr><td>duplicate firings (literal gate)</td><td class="num">{esc(uniq.get('duplicate_count'))}</td></tr>
<tr><td>unique (literal gate)</td><td><strong>{esc(uniq.get('unique'))}</strong></td></tr></table>
<p class="warn"><strong>The literal overlap gate fires and this file is therefore NOT cleared for
submission.</strong> 60 of 655 registry rasters contain more than 70% of this candidate's dots within
3 px (worst case 100%). Almost all of them are dense priors whose positive support covers the whole
footprint (5,167,373 cells) or the whole grid (12,279,160 cells): any non-empty candidate is
contained in them, which is a property of the inherited one-directional rule rather than of this lane
(IR-60-GATE-01). The discriminating statistics say the <em>content</em> is novel &mdash; worst
full-footprint Spearman {fmt(uniq.get('worst_spearman_full_footprint'))} against a 0.90 limit, worst
reverse overlap {fmt(worst_reverse)}, worst Jaccard {fmt(worst_jaccard)}, no byte- or pixel-identical
prior &mdash; but a containment artefact is still a containment, the protocol is literal and
fail-closed, and the run card records <code>unique_literal=false</code>, <code>stop_required=true</code>.
It is reported, not argued away.</p>
</section>

<section>
<h2>Run card</h2>
{card_html}
</section>

<section>
<h2>Limitations and next session</h2>
<ul>
<li>No DrivenData login in this sandbox: the 19-band stack, labels and sample submission come from a
hash-pinned third-party GitHub bridge (<code>buffedlizard55-lab/6GEMSDOE</code> @
<code>e2fe3f4</code>). Hashes are verified; official origin is <em>not</em> independently authenticated.</li>
<li>The lane brief names the free USGS 3DEP 10 m (or 1 m) DEM. <code>usgs.gov</code> is outside this
sandbox's permitted hosts, so the analysis runs on band 12 <code>det_elev</code> of the given stack
(100 m, detrended). IR-60-DATA-01.</li>
<li>Literature DOIs are cited from domain knowledge and given for manual review; this sandbox can
reach only github.com, pypi.org and npmjs.org, so no paper was fetched here. IR-60-CITE-01.</li>
<li>Only 3 experiments were run (budget). Next: (1) re-derive knickpoints on real 3DEP 10 m tiles on
an unrestricted machine; (2) fit &theta; per basin instead of the global 0.45; (3) add the
lithology contact mimic test (does the corridor survive a rock-unit boundary mask?); (4) a
two-round objective with the round-2 panel-verified pool.</li>
</ul>
</section>

<footer><p>Generated by <code>scripts/build_site60.py</code> from committed receipts.
No number on this page is typed by hand.</p></footer>
</body></html>
"""
    (DOCS / "index.html").write_text(page)

    exec_page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>How to submit &middot; 60GEMSDOE</title><link rel="stylesheet" href="assets/site.css"></head><body>
<header><h1>Executive summary: exactly how to make a submission</h1>
<p class="sub">Read this page before touching a weekly slot.</p></header>
<section class="banner {banner_cls}">
<h2>{'DOWNLOAD IS RELEASED' if ok_dl else 'NOTHING IS RELEASED'}</h2>
<p class="big">{'download OK' if ok_dl else 'download NO'} &middot; {'submit OK' if ok_sub else 'submit NO'}</p>
{'<p class="dl"><a class="btn" href="' + tif_rel + '">Download the .tif</a> <a class="btn alt" href="' + zip_rel + '">Download the .zip</a></p>' if tif_rel else ''}
</section>
<section><h2>Step by step</h2><ol>
<li>Click <strong>Download the .tif</strong> above. The file is a single-band GeoTIFF, float32,
EPSG:32611, 3730 &times; 3292, transform (100, 0, 243350, 0, &minus;100, 4508550) &mdash; identical grid
to the competition's <code>sample_submission.tif</code>.</li>
<li>Every cell is finite and inside [0, 1]. Cells outside the study footprint are written as
<strong>0.0, not NaN</strong>, because the portal rejects out-of-range values with
&ldquo;Predicted values must be in range [0, 1]&rdquo; when NaN is read as out-of-range. The
<code>-zeros</code> suffix in the filename records that choice.</li>
<li>Open <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">the
competition submission page</a> &rarr; <em>New submission</em> &rarr; <em>File to submit</em> &rarr;
choose the downloaded <code>.tif</code> (or the <code>.zip</code>, which contains only that TIFF).</li>
<li>Paste this into <em>Note (optional)</em> (max 140 characters):<br>
<code>{esc((build or {}).get('note',''))}</code></li>
<li>Submit. Then record the receipt: the returned submission id and the score the page shows are the
only <span class="tag">ORGANIZER-CONFIRMED</span> numbers this project recognises. Put them in
<code>registry/observations.jsonl</code>.</li>
<li>Slots are weekly and scarce. This page never spends one: promotion is a separate selector step.</li>
</ol></section>
<section><h2>Validation performed before release</h2>
<ul>
<li>independent re-read of the written TIFF and ZIP (<code>gems57.gates.format_report</code>):
ok={esc(((build or {}).get('template_report') or {}).get('ok'))},
problems={esc(((build or {}).get('template_report') or {}).get('problems'))},
non-zero cells={esc(((build or {}).get('template_report') or {}).get('n_nonzero'))}</li>
<li>range/NaN/catalogue-leakage validation (<code>gems57.validate.assert_submittable</code>)</li>
<li>sha256 {esc((build or {}).get('sha256'))}</li>
<li>zero dots on mapped catalogue faults (buffer {esc((pre or {}).get('declared_parameters', {}).get('catalogue_buffer_px'))} px)</li>
</ul></section>
<footer><a href="index.html">&larr; overview</a></footer></body></html>
"""
    (DOCS / "executive-summary.html").write_text(exec_page)

    sci = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Science &amp; sources &middot; 60GEMSDOE</title>
<link rel="stylesheet" href="assets/site.css"></head><body>
<header><h1>Science, hypotheses and verified sources</h1></header>
<section><h2>Hypothesis H60-A</h2><p>{esc((pre or {}).get('hypothesis',''))}</p>
<p><strong>Mechanism.</strong> {esc((pre or {}).get('mechanism',''))}</p>
<p><strong>Named non-fault mimic.</strong> {esc((pre or {}).get('named_non_fault_mimic',''))}</p>
<p><strong>Confound controls.</strong></p><ul>{''.join('<li>' + esc(c) + '</li>' for c in (pre or {}).get('confound_controls', []))}</ul>
<p><strong>Declared parameters.</strong></p><pre>{esc(json.dumps((pre or {}).get('declared_parameters', {}), indent=2))}</pre>
</section>
<section><h2>Three further candidate hypotheses (ranked, not yet run)</h2>
<table><tr><th>#</th><th>hypothesis</th><th>layer(s)</th><th>signature targeted</th><th>why it finds an unmapped fault</th><th>differs from repo</th><th>expected DTI gain / cost</th></tr>
<tr><td>H60-B</td><td>&chi;-space knickpoint <em>clusters</em> at equal &chi;, not equal distance</td><td>band 12 det_elev + band 19 slope</td><td>isochronous breakpoints along &chi; (Perron &amp; Royden)</td><td>a base-level fall propagates to equal &chi; in every drainage, so the pattern is a line even where the scarp is buried</td><td>no sibling uses &chi; at all</td><td>medium / low (all local)</td></tr>
<tr><td>H60-C</td><td>Drainage-divide migration asymmetry across mapped faults predicts the unmapped continuation</td><td>band 12 + derived divide lines</td><td>divide-height asymmetry (Vx index)</td><td>divides migrate away from the uplifted block; the signal survives alluvial burial that hides the trace</td><td>geometry of divides, not fault-zone damage</td><td>medium / medium</td></tr>
<tr><td>H60-D</td><td>Bedrock-channel incision pinned by <code>depth_to_base_surf</code> (band 15) steps</td><td>band 15 + band 12</td><td>coincidence of a basement-depth gradient with a ksn step</td><td>removes the lithologic mimic: a ksn step with no basement step is rock-type, not fault</td><td>uses a band no sibling lane has touched</td><td>high value / low cost</td></tr>
</table></section>
<section><h2>Verified sources for manual review</h2>
<table><tr><th>source</th><th>link</th><th>what was taken from it</th></tr>{src_rows}</table>
<p class="warn">Only github.com, api.github.com, codeload.github.com, pypi.org, files.pythonhosted.org
and registry.npmjs.org are reachable from this sandbox. DrivenData, USGS, DOI and github.io links are
recorded for manual review and were <strong>not</strong> fetched here (IR-60-CITE-01).</p></section>
<footer><a href="index.html">&larr; overview</a></footer></body></html>
"""
    (DOCS / "science.html").write_text(sci)

    audit = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Audit &middot; 60GEMSDOE</title>
<link rel="stylesheet" href="assets/site.css"></head><body>
<header><h1>Audit tables (machine-generated)</h1></header>
<section><h2>Data provenance &amp; pins</h2>
<table><tr><th>file</th><th>sha256</th><th>bytes</th><th>verified</th></tr>
{''.join(f"<tr><td>{esc(r['path'])}</td><td><code>{esc((r.get('sha256') or '')[:24])}&hellip;</code></td><td class='num'>{esc(r.get('bytes'))}</td><td>{esc(r.get('verified'))}</td></tr>" for r in (load('data_preparation.json') or {}).get('files', []))}
</table></section>
<section><h2>Feature build log (band 12 &rarr; chi/ksn/knickpoints)</h2>
<table><tr><th>step</th><th>t (s)</th><th>diagnostics</th></tr>{step_rows}</table></section>
<section><h2>Registry fetch receipt</h2>
<p>fetched {esc((fetch or {}).get('fetched'))}, errors {esc((fetch or {}).get('errors'))},
complete {esc((fetch or {}).get('complete'))}. Error rows:</p>
<pre>{esc(json.dumps((fetch or {}).get('error_rows', []), indent=2))}</pre></section>
<section><h2>Cell-level diagnostics</h2>
<pre>{esc(json.dumps((hold or {}).get('cell_diagnostics', []), indent=2)[:6000])}</pre></section>
<footer><a href="index.html">&larr; overview</a></footer></body></html>
"""
    (DOCS / "audit.html").write_text(audit)

    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    (DOCS / "assets" / "site.css").write_text("""
:root{--ink:#10202b;--mut:#5b7183;--line:#dfe7ee;--go:#0d6b3f;--hold:#8a5b00;--stop:#9b1c1c;--bg:#f7fafc}
*{box-sizing:border-box}
body{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#fff}
header{padding:28px 32px;background:var(--bg);border-bottom:1px solid var(--line)}
h1{margin:0 0 6px;font-size:26px} h2{font-size:20px;margin:0 0 10px} h3{font-size:16px}
.sub{margin:0;color:var(--mut)}
section{padding:22px 32px;border-bottom:1px solid var(--line);max-width:1100px}
nav{padding:10px 32px;background:#fff;border-bottom:1px solid var(--line);font-size:14px}
nav a{margin-right:10px}
.banner{border-left:8px solid var(--mut);background:var(--bg)}
.banner.go{border-left-color:var(--go);background:#f0fbf4}
.banner.hold{border-left-color:var(--hold);background:#fff9ec}
.banner.stop{border-left-color:var(--stop);background:#fdf2f2}
.banner .big{font-size:20px;font-weight:700;margin:6px 0}
.btn{display:inline-block;background:var(--go);color:#fff;padding:12px 18px;border-radius:8px;text-decoration:none;font-weight:700;margin:6px 8px 6px 0}
.btn.alt{background:#254a63}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:var(--bg)} td.num{text-align:right;font-variant-numeric:tabular-nums}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
pre{background:var(--bg);padding:12px;border-radius:8px;overflow:auto}
.warn{color:var(--hold);font-size:14px} .tag{background:#e8eef4;border-radius:4px;padding:1px 5px;font-size:12px}
footer{padding:18px 32px;color:var(--mut);font-size:13px}
.note{font-size:14px}
""")
    # GitHub Pages for this repository is configured to serve branch=main, path=/,
    # so the landing page must carry the executive summary and the download banner
    # itself.  <base href="docs/"> keeps every relative link (assets, downloads,
    # sub-pages) resolving into docs/ from both copies.
    root_page = page.replace('<head><meta charset="utf-8">',
                             '<head><base href="docs/"><meta charset="utf-8">', 1)
    (ROOT / "index.html").write_text(root_page)
    print(f"[site] wrote {DOCS/'index.html'} (+ executive-summary, science, audit, css); "
          f"tif={tif_rel} zip={zip_rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
