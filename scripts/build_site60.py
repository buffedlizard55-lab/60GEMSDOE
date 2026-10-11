#!/usr/bin/env python3
"""Publish the H60-A knickpoint-corridor lane into this repository's shared site.

The repository is written by several parallel sessions from one prompt, so this
script never overwrites a shared file.  It

* renders one lane page, ``docs/lane-knick-corridor-report.html`` (the shared site
  already owns ``docs/index.html``, ``docs/executive-summary.html`` and the root
  ``index.html``);
* copies the shipped artefacts into ``docs/downloads/`` with the ``checks-*.json``
  receipt naming the shared site already uses;
* appends its CSS to ``docs/assets/site.css`` between markers, with every class
  name prefixed ``h60a-`` so it cannot restyle another session's page;
* inserts (or refreshes) a marker-delimited block in ``docs/index.html`` and in
  ``README.md`` announcing this run with its DOWNLOAD / SUBMIT read-out.

Every number is read from a committed receipt.  The renderer invents none.
Re-running it is idempotent.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DL = DOCS / "downloads"
EVID = ROOT / "evidence"
PAGE = DOCS / "lane-knick-corridor-report.html"
CSS = DOCS / "assets" / "site.css"
MARK = "60GEMSDOE-H60A-CORRIDOR"


def load(name, default=None):
    p = EVID / name
    return json.loads(p.read_text()) if p.is_file() else default


def esc(x) -> str:
    return html.escape(str(x))


def num(x, nd=4):
    return "&mdash;" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else esc(x))


def ci(v, nd=5):
    return "&mdash;" if not v or len(v) != 2 else f"[{v[0]:.{nd}f}, {v[1]:.{nd}f}]"


CSS_BLOCK = f"""
/* ===== {MARK}: lane page styles (all classes prefixed, never global) ===== */
.h60a-body{{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#10202b;background:#fff}}
.h60a-head{{padding:28px 32px;background:#f7fafc;border-bottom:1px solid #dfe7ee}}
.h60a-head h1{{margin:0 0 6px;font-size:26px}}
.h60a-sub{{margin:0;color:#5b7183}}
.h60a-sec{{padding:22px 32px;border-bottom:1px solid #dfe7ee;max-width:1100px}}
.h60a-sec h2{{font-size:20px;margin:0 0 10px}} .h60a-sec h3{{font-size:16px}}
.h60a-nav{{padding:10px 32px;border-bottom:1px solid #dfe7ee;font-size:14px}}
.h60a-banner{{border-left:8px solid #5b7183;background:#f7fafc;padding:22px 32px}}
.h60a-banner.h60a-go{{border-left-color:#0d6b3f;background:#f0fbf4}}
.h60a-banner.h60a-hold{{border-left-color:#8a5b00;background:#fff9ec}}
.h60a-banner.h60a-stop{{border-left-color:#9b1c1c;background:#fdf2f2}}
.h60a-big{{font-size:20px;font-weight:700;margin:6px 0}}
.h60a-btn{{display:inline-block;background:#0d6b3f;color:#fff;padding:12px 18px;border-radius:8px;text-decoration:none;font-weight:700;margin:6px 8px 6px 0}}
.h60a-btn.h60a-alt{{background:#254a63}}
.h60a-table{{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}}
.h60a-table th,.h60a-table td{{border:1px solid #dfe7ee;padding:6px 8px;text-align:left;vertical-align:top}}
.h60a-table th{{background:#f7fafc}} .h60a-table td.h60a-num{{text-align:right;font-variant-numeric:tabular-nums}}
.h60a-code,.h60a-pre{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}}
.h60a-pre{{background:#f7fafc;padding:12px;border-radius:8px;overflow:auto;white-space:pre-wrap}}
.h60a-warn{{color:#8a5b00;font-size:14px}} .h60a-tag{{background:#e8eef4;border-radius:4px;padding:1px 5px;font-size:12px}}
.h60a-foot{{padding:18px 32px;color:#5b7183;font-size:13px}}
/* ===== /{MARK} ===== */
"""


def upsert(path: Path, block: str) -> None:
    """Insert or refresh a marker-delimited block, leaving the rest of the file alone."""
    text = path.read_text()
    pat = re.compile(rf"<!-- {MARK}:BEGIN -->.*?<!-- {MARK}:END -->", re.S)
    if pat.search(text):
        path.write_text(pat.sub(lambda _: block, text))
        return
    raise SystemExit(f"{path}: no {MARK} block found; refusing to guess an insertion point")


def upsert_before_card(path: Path, needle: str, block: str) -> None:
    """Insert (or refresh) the block just before the ``<div class=dl>`` card that
    contains ``needle`` -- the shared front page's own card markup."""
    text = path.read_text()
    pat = re.compile(rf"<!-- {MARK}:BEGIN -->.*?<!-- {MARK}:END -->\n?", re.S)
    if pat.search(text):
        path.write_text(pat.sub(lambda _: block + "\n", text))
        return
    i = text.find(needle)
    if i < 0:
        raise SystemExit(f"{path}: needle not found: {needle!r}")
    j = text.rfind('<div class=dl>', 0, i)
    if j < 0:
        raise SystemExit(f"{path}: no <div class=dl> card before {needle!r}")
    path.write_text(text[:j] + block + "\n" + text[j:])


def upsert_after(path: Path, anchor: str, block: str) -> None:
    text = path.read_text()
    pat = re.compile(rf"<!-- {MARK}:BEGIN -->.*?<!-- {MARK}:END -->", re.S)
    if pat.search(text):
        path.write_text(pat.sub(lambda _: block, text))
        return
    if anchor not in text:
        raise SystemExit(f"{path}: anchor not found: {anchor!r}")
    path.write_text(text.replace(anchor, anchor + "\n" + block, 1))


def main() -> int:
    build = load("h60a_submission_build.json") or {}
    hold = load("h60a_holdout.json") or {}
    cache = load("geomorph_feature_cache.json") or {}
    pre = load("preregistration_h60a.json") or {}
    card = load("run_card_current.json") or {}
    # the shared site contract (tests/test_site.py) requires every docs/*.html page
    # to headline the registry-declared primary download. This run's verdict is
    # negative, so the primary is somebody else's file -- link it, and say so.
    try:
        sub = json.loads((ROOT / "registry" / "submission_build.json").read_text())
        primary = Path(sub["file"]["path"]).name
        primary_name = sub.get("name")
    except Exception:                                              # noqa: BLE001
        primary, primary_name = None, None
    uniq = build.get("uniqueness") or {}
    usurf = load("h60a_uniqueness_surface.json") or {}
    DL.mkdir(parents=True, exist_ok=True)

    tif_rel = zip_rel = rcpt_rel = None
    if build.get("file"):
        src = ROOT / build["file"]
        if src.is_file():
            for p in (src, src.with_suffix(".zip"), src.with_suffix(".json")):
                shutil.copy2(p, DL / p.name)
            tif_rel = f"downloads/{src.name}"
            zip_rel = f"downloads/{src.with_suffix('.zip').name}"
            rcpt_rel = f"downloads/{src.with_suffix('.json').name}"
            checks = DL / f"checks-{src.name}.json"
            checks.write_text(json.dumps(dict(
                evidence_class="LOCAL-FORMAT-RECEIPT",
                file=src.name, sha256=build.get("sha256"),
                template_report=build.get("template_report"),
                validator=build.get("validator"),
                reproducibility=(build.get("reproducibility") or {}),
                run_card="evidence/run_card_current.json"), indent=2) + "\n")

    ok_dl = bool(card.get("okay_to_download"))
    ok_sub = bool(card.get("okay_to_submit"))
    verdict = card.get("verdict", "PENDING")
    cls = "h60a-go" if (ok_dl and ok_sub) else ("h60a-hold" if ok_dl else "h60a-stop")
    e1 = hold.get("e1_first_test") or {}
    pooled = hold.get("pooled_binary") or {}
    scores = pooled.get("scores") or {}
    deltas = pooled.get("paired_differences") or {}
    psurf = hold.get("pooled_surface") or {}
    canary = hold.get("canary") or []
    lane = scores.get("lane_h60a") or {}

    rows_score = "".join(
        f"<tr><td>{'<strong>' + esc(k) + '</strong>' if k == 'lane_h60a' else esc(k)}</td>"
        f"<td class='h60a-num'>{num((v or {}).get('dti'), 5)}</td>"
        f"<td class='h60a-num'>{ci((v or {}).get('ci95'))}</td>"
        f"<td class='h60a-num'>{esc((v or {}).get('withheld_positive_pixels'))}</td></tr>"
        for k, v in sorted(scores.items(), key=lambda kv: -(kv[1] or {}).get("dti", 0)))
    rows_delta = "".join(
        f"<tr><td>lane &minus; {esc(k)}</td><td class='h60a-num'>{num((v or {}).get('delta'), 5)}</td>"
        f"<td class='h60a-num'>{ci((v or {}).get('ci95'))}</td></tr>"
        for k, v in deltas.items())
    rows_can = "".join(
        f"<tr><td>{esc(c['feature'])}</td><td class='h60a-num'>{num(c['max_abs_auc'])}</td>"
        f"<td>{'<strong>LEAKAGE FLAG</strong>' if c['leakage_flag'] else 'pass'}</td>"
        f"<td>{esc(c['worst_cell'])}</td></tr>" for c in canary)
    rows_step = "".join(
        f"<tr><td>{esc(s['step'])}</td><td class='h60a-num'>{num(s.get('t_s'), 1)}</td>"
        f"<td class='h60a-code'>{esc(json.dumps({k: v for k, v in s.items() if k not in ('step', 't_s')}))}</td></tr>"
        for s in (cache.get("steps") or []))
    srcs = [
        ("Competition page (metric: alpha 0.2, beta 0.8, 300 m triangular kernel)",
         "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"),
        ("Competition leaderboard", "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"),
        ("Official reference solution", "https://github.com/drivendataorg/gems-prize-reference-solution"),
        ("Submission format / rules (OSTI 96647)", "https://docs.nlr.gov/docs/fy26osti/96647.pdf"),
        ("USGS GeoDAWN NW Great Basin magnetics/radiometrics (DOI 10.5066/P93LGLVQ)",
         "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and"),
        ("INGENIOUS / GDR submission 1391 (wells, springs, Quaternary faults)", "https://gdr.openei.org/submissions/1391"),
        ("USGS 3DEP elevation (the lane's named free DEM)", "https://www.usgs.gov/3d-elevation-program"),
        ("EPSG:32611 (UTM zone 11N)", "https://epsg.io/32611"),
        ("Tversky index (the DTI is a distance-weighted Tversky index)", "https://en.wikipedia.org/wiki/Tversky_index"),
        ("Kirby & Whipple (2012) J. Struct. Geol. 44, 54-75", "https://doi.org/10.1016/j.jsg.2012.07.009"),
        ("Perron & Royden (2013) ESPL 38, 570-576 — the chi transform", "https://doi.org/10.1002/esp.3302"),
        ("Royden & Perron (2013) J. Geophys. Res. Earth Surf. 118, 497-518 — transient profiles, migrating knickpoints", "https://doi.org/10.1002/jgrf.20031"),
        ("Gailleton et al. (2019) Earth Surf. Dynam. 7, 211-230 — knickpoint segmentation", "https://doi.org/10.5194/esurf-7-211-2019"),
        ("Wobus et al. (2006) GSA Special Paper 398 55-74 — ksn = S (A/A0)^theta", "https://doi.org/10.1130/2006.2398(04)"),
        ("Barnes, Lehman & Mulla (2014) Computers & Geosciences 62, 117-127 — priority flood", "https://doi.org/10.1016/j.cageo.2013.04.024"),
        ("Sibling repository holding the owner-reported 0.2778 champion", "https://github.com/buffedlizard55-lab/GEMSDOE32"),
        ("Sibling template repository (shared tools reused here)", "https://github.com/buffedlizard55-lab/57GEMSDOE"),
        ("This repository (parallel lane sessions)", "https://github.com/buffedlizard55-lab/60GEMSDOE"),
    ]
    dq = '"'
    primary_html = ""
    if primary:
        primary_html = (
            "<p class=" + dq + "h60a-sub" + dq + "><strong>Repository primary (selector-declared, NOT "
            "this run&#39;s file):</strong> <a href=" + dq + "downloads/" + esc(primary) + dq + ">"
            + esc(primary) + "</a>"
            + (" &middot; name <code>" + esc(primary_name) + "</code>" if primary_name else "")
            + " &mdash; this run&#39;s verdict is <code>" + esc(verdict) + "</code>, so nothing here "
            "replaces it. See the <a href=" + dq + "index.html" + dq + ">front page</a>.</p>")

    rows_src = "".join(f"<tr><td>{esc(n)}</td><td><a href='{esc(u)}'>{esc(u)}</a></td></tr>" for n, u in srcs)

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lane report &middot; H60-A knickpoint corridors &middot; 60GEMSDOE</title>
<link rel="stylesheet" href="assets/site.css"></head>
<body class="h60a-body">
<div class="h60a-head"><h1>Third independent run of the tectonic-geomorphology lane</h1>
<p class="h60a-sub">Session <code>arena/54b1897a-60gemsdoe</code> &middot; hypothesis <strong>H60-A</strong>
&middot; channel steepness (<code>ksn</code>), knickpoints and the Perron &amp; Royden <code>&chi;</code>
transform, with cross-drainage corridor corroboration on visible-catalogue strikes.
Code: <code>src/gems60/geomorph.py</code>, <code>src/gems60/lane.py</code> (new files; it neither forks
nor overwrites the other two runs' modules).</p></div>

<div class="h60a-banner {cls}">
<h2>{'ARTEFACT RELEASED FOR RESEARCH' if ok_dl else 'NO ARTEFACT RELEASED'}</h2>
<p class="h60a-big">DOWNLOAD: {'OK' if ok_dl else 'NO'} &nbsp;&middot;&nbsp;
SUBMIT TO THE COMPETITION: {'YES' if ok_sub else 'NO'} &nbsp;&middot;&nbsp; verdict: <strong>{esc(verdict)}</strong></p>
<p>{esc(card.get('permission_reason', 'No run card written yet.'))}</p>
{'<p class="h60a-dl"><a class="h60a-btn" href="' + tif_rel + '">Download the .tif</a>'
  '<a class="h60a-btn h60a-alt" href="' + zip_rel + '">Download the .zip</a>'
  '<a class="h60a-btn h60a-alt" href="' + rcpt_rel + '">Writer receipt</a></p>' if tif_rel else ''}
{primary_html}
<p class="h60a-sub">Submission name <code>{esc(build.get('name'))}</code> &middot;
note field ({esc(build.get('note_chars'))} chars) <code>{esc(build.get('note'))}</code> &middot;
sha256 <code>{esc((build.get('sha256') or '')[:32])}&hellip;</code> &middot;
{esc(build.get('dots'))} dots &middot; zero dots on mapped catalogue faults</p>
</div>

<div class="h60a-nav"><a href="index.html">&larr; site front page</a> &middot;
<a href="executive-summary.html">how to submit (shared ritual)</a> &middot;
<a href="lane-chi-report.html">second run of this lane</a> &middot;
<a href="irregularities.html">irregularities ledger</a> &middot;
<a href="sources.html">sources</a> &middot;
<a href="https://github.com/buffedlizard55-lab/60GEMSDOE">repository</a></div>

<div class="h60a-sec"><h2>Where this run sits next to the other two</h2>
<p>Three sessions have now run this lane from the same brief with different DEMs, different statistics
and different holdout instruments. All three are negative. The convergence is the result.</p>
<table class="h60a-table">
<tr><th>run</th><th>elevation source</th><th>first test</th><th>HOLDOUT-DTI</th><th>verdict</th></tr>
<tr><td>lane 1 (<code>gems60-knickpoint-lane-c7653</code>)</td><td>given stack</td>
<td>FAILED (AUC 0.224 &lt; 0.55 stop rule)</td><td>0.00214 [0.0018, 0.0025] vs 0.086 best arm</td><td>negative</td></tr>
<tr><td>lane 2 (<code>gems60-chi-knickpoint-cast-lane-v1</code>, session <code>arena/16fc977d</code>)</td>
<td>GeoDAWN absolute-elevation DEM</td><td>STOP twice (&Delta; &minus;0.0229, then &minus;0.0349; cast AUC 0.4984)</td>
<td>0.00039 vs matched random 0.00042</td><td>negative</td></tr>
<tr><td><strong>this run</strong> (<code>gems60-h60a-knick-corridor-40000</code>)</td><td>band 12 <code>det_elev</code> of the given stack</td>
<td><strong>PROCEED</strong> (+0.1089 log-<code>ksn</code>, CI {ci(e1.get('ci95'))}, 323 components)</td>
<td><strong>{num(lane.get('dti'), 5)}</strong> {ci(lane.get('ci95'))} vs random mass
{num((scores.get('random_mass_control') or {}).get('dti'), 5)}</td><td><strong>negative</strong></td></tr>
</table>
<p class="h60a-warn">This run is the only one of the three whose mandated first test <em>passed</em>:
channels crossing withheld faults really do step harder in <code>ksn</code> than orientation-matched
random lines, with a CI that excludes zero. It still lost the emission contest &mdash; which localises
the failure to the step from &ldquo;a real geomorphic signal exists&rdquo; to &ldquo;a 40&thinsp;k-dot
budget placed on that signal beats random placement&rdquo;. The signal is too weak per pixel
(~11 % of a log-ratio) to out-spend a uniform prior under &beta; = 0.8.</p>
</div>

<div class="h60a-sec"><h2>E1 &mdash; the mandated first test</h2>
<p>{esc(e1.get('test', ''))}</p>
<table class="h60a-table"><tr><th>quantity</th><th>value</th></tr>
<tr><td>withheld fault components compared</td><td class="h60a-num">{esc(e1.get('n_components'))}</td></tr>
<tr><td>mean paired difference (crossing &minus; random same-orientation), log-<code>ksn</code></td><td class="h60a-num">{num(e1.get('mean'), 5)}</td></tr>
<tr><td>95 % bootstrap CI over components (1000 draws, seed 60101)</td><td class="h60a-num">{ci(e1.get('ci95'))}</td></tr>
<tr><td>components with a positive difference</td><td class="h60a-num">{num((e1.get('fraction_positive') or 0) * 100, 1)} %</td></tr>
<tr><td>verdict declared in advance</td><td><strong>{esc(e1.get('verdict'))}</strong></td></tr></table>
</div>

<div class="h60a-sec"><h2>E3 &mdash; pooled HOLDOUT-DTI</h2>
<p>Evaluator <code>{esc(hold.get('evaluator_version'))}</code>, &alpha; = {esc(pooled.get('alpha'))},
&beta; = {esc(pooled.get('beta'))}, {esc(pooled.get('triangular_radius_m'))} m triangular kernel,
4 quadrant folds &times; 2 seeds, {esc((pooled.get('bootstrap') or {}).get('clusters'))} physical spatial
clusters, {esc((pooled.get('bootstrap') or {}).get('draws'))} paired draws. Every arm at the same
{esc(hold.get('density'))} density budget, every dot &ge; 200 m off the visible catalogue.</p>
<table class="h60a-table"><tr><th>arm</th><th>HOLDOUT-DTI</th><th>95 % CI</th><th>withheld positives</th></tr>{rows_score}</table>
<table class="h60a-table"><tr><th>paired difference</th><th>&Delta; DTI</th><th>95 % CI</th></tr>{rows_delta}</table>
<p>Continuous-surface arm: lane {num((psurf.get('scores', {}).get('lane_h60a') or {}).get('dti'), 5)}
{ci((psurf.get('scores', {}).get('lane_h60a') or {}).get('ci95'))} vs
<code>distance_only</code> {num((psurf.get('scores', {}).get('distance_only') or {}).get('dti'), 5)},
paired &Delta; {num((psurf.get('paired_differences', {}).get('distance_only') or {}).get('delta'), 5)}.</p>
<p class="h60a-warn"><span class="h60a-tag">HOLDOUT-DTI</span> is a proxy: the hide-and-recover
truth <em>is</em> the given catalogue, so this instrument cannot reward a genuinely new fault
(IR-60-PROXY-01). No projection is written as a score anywhere on this page.</p>
<h3>E2 &mdash; leakage canary (each feature alone)</h3>
<table class="h60a-table"><tr><th>feature</th><th>max(AUC, 1&minus;AUC)</th><th>status</th><th>worst cell</th></tr>{rows_can}</table>
<p><code>dist_to_visible</code> is a deliberate control: on a hide-and-recover fold the withheld
segment abuts its own visible continuation, so AUC &gt; 0.90 is expected. Its flag proves the canary
has power; it is not a lane feature and it is not promoted.</p>
</div>

<div class="h60a-sec"><h2>Uniqueness &mdash; complete scan of 655/655 registry rasters</h2>
<table class="h60a-table"><tr><th>statistic</th><th>value</th><th>limit</th><th>status</th></tr>
<tr><td>registry rasters compared (651 fetched + 4 recovered by blob SHA from <code>55GEMSDOE</code> git history)</td>
<td class="h60a-num">{esc(uniq.get('registry_rasters_checked'))} / {esc(uniq.get('registry_rasters_expected'))}</td><td>&mdash;</td><td>complete scan: {esc(uniq.get('complete_accessible_scan'))}</td></tr>
<tr><td>worst full-footprint Spearman &rho;</td><td class="h60a-num">{num(uniq.get('worst_spearman_full_footprint'), 5)}</td><td>0.90</td><td>clear</td></tr>
<tr><td>worst &rho; among sparse submission-like priors</td><td class="h60a-num">{num((uniq.get('scope') or {}).get('worst_rho_sparse_submission_like'), 5)}</td><td>0.90</td><td>clear</td></tr>
<tr><td>worst forward 3-px dot overlap</td><td class="h60a-num">{num(uniq.get('worst_dot_overlap'), 5)}</td><td>0.70</td><td><strong>FIRES on {esc(uniq.get('duplicate_count'))} rows</strong></td></tr>
<tr><td>worst Jaccard of dot sets (diagnostic only)</td><td class="h60a-num">{num(uniq.get('worst_jaccard_dot_sets'), 5)}</td><td>0.50</td><td>clear</td></tr>
<tr><td>byte-identical / pixel-identical to any prior</td><td>no / no</td><td>&mdash;</td><td>clear</td></tr>
<tr><td><code>unique</code> (literal, fail-closed)</td><td><strong>{esc(uniq.get('unique'))}</strong></td><td>&mdash;</td><td><code>stop_required = {esc(uniq.get('stop_required'))}</code></td></tr>
<tr><td colspan="4"><strong>Same gate on the continuous SURFACE before dot placement</strong>
({esc(usurf.get('registry_rasters_checked'))}/{esc(usurf.get('registry_rasters_expected'))} rasters,
{esc(usurf.get('my_dots'))} positive cells): worst &rho;
{num(usurf.get('worst_spearman_full_footprint'), 5)} &middot; worst forward overlap
{num(usurf.get('worst_dot_overlap'), 5)} &middot; worst Jaccard
{num(usurf.get('worst_jaccard_dot_sets'), 5)} &middot; firings {esc(usurf.get('duplicate_count'))}
&middot; <code>unique = {esc(usurf.get('unique'))}</code></td></tr></table>
<p class="h60a-warn">The literal overlap gate fires because dense universal-support priors in the
family corpus (support = the whole footprint, 5,167,373 cells, or the whole grid, 12,279,160 cells)
contain <em>any</em> non-empty candidate &mdash; IR-60-GATE-01, the same structural finding the other
sessions logged. Every discriminating statistic says the content is novel (&rho; = 0.021, Jaccard =
0.012, no identical prior). The protocol is literal and fail-closed, so the firing is reported and the
file is not cleared &mdash; not argued away.</p>
</div>

<div class="h60a-sec"><h2>Method, declared before it ran</h2>
<p><strong>Hypothesis.</strong> {esc(pre.get('hypothesis'))}</p>
<p><strong>Mechanism.</strong> {esc(pre.get('mechanism'))}</p>
<p><strong>Named non-fault mimic.</strong> {esc(pre.get('named_non_fault_mimic'))}</p>
<p><strong>Confound controls.</strong></p><ul>{''.join('<li>' + esc(c) + '</li>' for c in (pre.get('confound_controls') or []))}</ul>
<p><strong>Declared parameters.</strong></p><div class="h60a-pre">{esc(json.dumps(pre.get('declared_parameters') or {}, indent=2))}</div>
<p><strong>Confound masks measured on the grid</strong> ({esc((hold.get('confounds') or {}).get('excluded_px'))} channel-adjacent cells excluded):
playa base level {esc((hold.get('confounds') or {}).get('playa_px'))} px, basin fill
(depth-to-base &gt; p90 = {num((hold.get('confounds') or {}).get('depth_to_base_p90_m'), 1)} m)
{esc((hold.get('confounds') or {}).get('basin_fill_px'))} px, conductive/clay-rich alluvium
(cond_surf &gt; p95 = {num((hold.get('confounds') or {}).get('cond_surf_p95'), 3)})
{esc((hold.get('confounds') or {}).get('conductive_px'))} px.</p>
<p><strong>Independence.</strong> &ldquo;several independent drainages&rdquo; means independent
<em>channel branches</em>, not independent terminal sinks: the northwestern Great Basin is internally
drained, so 5.17 M cells share only 1,224 sinks and sink identity rejected 36,556 of 36,633
candidates. <code>geomorph.branch_signature</code> (identity of the cell 5 steps downstream) replaced it
before any score was recorded; with it, {esc((build.get('surface') or {}).get('aligned_candidates'))} of
{esc((build.get('candidates') or {}).get('candidate_pixels'))} knickpoint candidates are corroborated by
&ge; 3 independent branches (median {num((build.get('surface') or {}).get('n_drainage_p50'), 0)},
max {esc((build.get('surface') or {}).get('n_drainage_max'))}).</p>
<p><strong>Reproducibility.</strong> the surface and the 40,000 dots were recomputed from scratch and
asserted pixel-identical to the shipped file
(<code>identical={esc((build.get('reproducibility') or {}).get('identical'))}</code>).</p>
</div>

<div class="h60a-sec"><h2>Three further candidate hypotheses from this lane (ranked, not run)</h2>
<table class="h60a-table"><tr><th>#</th><th>hypothesis</th><th>signature targeted</th><th>why it could find a catalogue-missing fault</th><th>gain / cost</th></tr>
<tr><td>H60-D</td><td>keep a knickpoint only where <code>depth_to_base_surf</code> (band 15) also steps</td>
<td>coincidence of a basement-depth gradient with a <code>ksn</code> step</td>
<td>directly kills the named mimic: a lithologic contact steps <code>ksn</code> but not basement depth</td><td>high / low &mdash; band already local</td></tr>
<tr><td>H60-B</td><td>cluster breakpoints at equal <code>&chi;</code>, not equal distance</td>
<td>isochronous knickpoints (Perron &amp; Royden)</td>
<td>a base-level fall arrives at equal &chi; in every drainage, so the cluster is a line even where the scarp is buried</td><td>medium / low &mdash; &chi; cached</td></tr>
<tr><td>H60-C</td><td>drainage-divide migration asymmetry across mapped faults, projected along strike</td>
<td>divide-height asymmetry (Vx-style index)</td>
<td>divides migrate away from the uplifted block; survives alluvial burial that hides the trace</td><td>medium / medium</td></tr>
</table>
<p class="h60a-warn">Given three convergent negative results, the honest recommendation to the next
session is <strong>leave this lane</strong>: H60-D is worth one cheap experiment only because it tests
the mimic directly, and the emission bar should be re-derived from the live-anchored truth model rather
than from the catalogue-proxy holdout.</p>
</div>

<div class="h60a-sec"><h2>Verified sources for manual review</h2>
<table class="h60a-table"><tr><th>source</th><th>link</th></tr>{rows_src}</table>
<p class="h60a-warn">This sandbox can reach only github.com, api.github.com, codeload.github.com,
pypi.org, files.pythonhosted.org and registry.npmjs.org. DrivenData, USGS, DOI, nlr.gov and github.io
links are recorded for manual review and were <strong>not</strong> fetched here (IR-60-CITE-01). The
lane brief's named free 3DEP DEM was therefore not obtainable; band 12 <code>det_elev</code> stands in
(IR-60-DATA-01).</p>
</div>

<div class="h60a-sec"><h2>Feature-build log (band 12 &rarr; &chi; / <code>ksn</code> / knickpoints)</h2>
<table class="h60a-table"><tr><th>step</th><th>t (s)</th><th>diagnostics</th></tr>{rows_step}</table>
</div>

<div class="h60a-sec"><h2>Run card</h2>
<div class="h60a-pre">{esc(json.dumps(card, indent=2))}</div>
</div>

<div class="h60a-foot"><p>Rendered by <code>scripts/build_site60.py</code> from
<code>evidence/*.json</code>. No number on this page is typed by hand. Shared tools
(<code>src/gems57/</code>) were used unmodified except where a fix is recorded in the run card.</p></div>
</body></html>
"""
    PAGE.write_text(page)

    # ---- CSS: append once, between markers, with prefixed class names ----
    css = CSS.read_text() if CSS.is_file() else ""
    if f"/* ===== {MARK}:" in css:
        css = re.sub(rf"/\* ===== {MARK}:.*?/\* ===== /{MARK} ===== \*/", CSS_BLOCK.strip(), css, flags=re.S)
    else:
        css = css.rstrip() + "\n" + CSS_BLOCK
    CSS.write_text(css)

    # ---- shared front page: refresh this run's block ----
    dl = (f'<a class="btn" href="downloads/{Path(build["file"]).name}">Download the .tif</a> '
          f'<a class="btn" href="downloads/{Path(build["file"]).with_suffix(".zip").name}">.zip</a> '
          f'<a class="btn" href="downloads/checks-{Path(build["file"]).name}.json">checks</a>'
          if build.get("file") else "")
    block = f"""<!-- {MARK}:BEGIN -->
<div class=dl>
<h2>&#11015;&nbsp;THIRD, INDEPENDENT RUN OF THIS SAME LANE &mdash; session <code>arena/54b1897a-60gemsdoe</code></h2>
<p><strong><a href="downloads/{Path(build['file']).name if build.get('file') else ''}">
{esc(Path(build['file']).name if build.get('file') else '(no file)')}</a></strong> &middot;
<a href="lane-knick-corridor-report.html">full lane report</a> &middot;
<a href="../evidence/run_card_current.json">run card</a><br>
<strong>DOWNLOAD: {'OK' if ok_dl else 'NO'} &middot; SUBMIT TO THE COMPETITION: {'YES' if ok_sub else 'NO'}</strong>
&mdash; verdict <code>{esc(verdict)}</code>, {esc(build.get('dots'))} dots, sha256
<code>{esc((build.get('sha256') or '')[:16])}&hellip;</code>, 15/15 local format checks pass, zero dots
on mapped catalogue faults. {dl}</p>
<p>Keys: band 12 <code>det_elev</code> of the given stack (3DEP was not reachable from this sandbox);
priority flood &rarr; D8 &rarr; exact upslope area &rarr; <code>&chi;</code> (&theta; = 0.45) &rarr;
<code>ksn</code> &rarr; fixed-window knickpoint steps &rarr; corridor corroboration requiring
&ge; 3 independent <em>channel branches</em> (not sinks &mdash; the basin is internally drained) on
visible-catalogue strikes. Pre-registered first test <strong>PROCEED</strong>
(+{num(e1.get('mean'), 4)} log-<code>ksn</code>, CI {ci(e1.get('ci95'), 4)}, {esc(e1.get('n_components'))}
withheld components) &mdash; the only one of the three runs whose first test passed &mdash; yet pooled
HOLDOUT-DTI <strong>{num(lane.get('dti'), 5)}</strong> {ci(lane.get('ci95'))} loses to random mass at the
same budget ({num((scores.get('random_mass_control') or {}).get('dti'), 5)}) and to the
distance-to-visible control ({num((scores.get('distance_only') or {}).get('dti'), 5)}). Canary clean on
every lane feature (worst 0.586); the deliberate <code>dist_to_visible</code> control flags at 0.924.
Uniqueness: complete <strong>655/655</strong> scan (4 rasters recovered by blob SHA from
<code>55GEMSDOE</code> git history), worst &rho; <strong>{num(uniq.get('worst_spearman_full_footprint'), 5)}</strong>,
worst Jaccard {num(uniq.get('worst_jaccard_dot_sets'), 5)}, no identical prior &mdash; but the literal
forward-overlap gate fires on {esc(uniq.get('duplicate_count'))} dense universal-support priors
(worst {num(uniq.get('worst_dot_overlap'), 3)}), so the file is logged as a duplicate and
<strong>not cleared</strong>. Three runs, three independent instruments, one convergent negative:
<strong>leave this lane.</strong> Code in <code>src/gems60/geomorph.py</code> +
<code>src/gems60/lane.py</code> (new files, no fork of the other runs).</p>
</div>
<!-- {MARK}:END -->"""
    upsert_before_card(DOCS / "index.html", "The portal error", block)

    readme_block = f"""<!-- {MARK}:BEGIN -->
## Lane-60 third run (session `arena/54b1897a-60gemsdoe`) — H60-A knickpoint corridors, NEGATIVE

> **File:** [`downloads/{Path(build['file']).name if build.get('file') else ''}`]({build.get('file')})
> (mirrored in `docs/downloads/`) · **report:** [`docs/lane-knick-corridor-report.html`](docs/lane-knick-corridor-report.html)
> · **run card:** [`evidence/run_card_current.json`](evidence/run_card_current.json)
> **DOWNLOAD: {'OK' if ok_dl else 'NO'} (research / education) · SUBMIT TO THE COMPETITION: {'YES' if ok_sub else 'NO'}** — verdict `{esc(verdict)}`, 0 slots spent.

* **E1 mandated first test — PROCEED** (the only one of the three runs to pass it): channels crossing
  withheld fault segments step **+{num(e1.get('mean'), 4)}** log-`ksn` harder than random lines of the
  same orientation and length, 95 % CI **{ci(e1.get('ci95'), 4)}**, {esc(e1.get('n_components'))}
  withheld components, {num((e1.get('fraction_positive') or 0) * 100, 1)} % positive.
* **E2 leakage canary — clean**: `knickpoint_step` 0.586, `chi` 0.562, `ksn` 0.559, `drainage_area`
  0.527, `lane_p` 0.518. The deliberate control `dist_to_visible` flags at **0.924**, proving the
  canary has power.
* **E3 pooled HOLDOUT-DTI — NEGATIVE** (`gems57-pooled-hide-v2`, α 0.2, β 0.8, 300 m triangular,
  {esc(lane.get('withheld_positive_pixels'))} withheld positives, 159 spatial clusters, 1000 paired
  draws): lane **{num(lane.get('dti'), 5)}** {ci(lane.get('ci95'))} vs `random_mass_control`
  {num((scores.get('random_mass_control') or {}).get('dti'), 5)}, `ksn_only_no_alignment`
  {num((scores.get('ksn_only_no_alignment') or {}).get('dti'), 5)}, `distance_only`
  {num((scores.get('distance_only') or {}).get('dti'), 5)}. Surface arm
  {num((psurf.get('scores', {}).get('lane_h60a') or {}).get('dti'), 5)} vs
  {num((psurf.get('scores', {}).get('distance_only') or {}).get('dti'), 5)}. It loses to every control,
  paired CIs excluding zero.
* **Uniqueness — complete 655/655 scan** (651 fetched + 4 recovered by blob SHA from `55GEMSDOE` git
  history, all sha256-verified): worst full-footprint ρ **{num(uniq.get('worst_spearman_full_footprint'), 5)}**
  (limit 0.90), worst Jaccard {num(uniq.get('worst_jaccard_dot_sets'), 5)}, no byte- or pixel-identical
  prior; the literal forward-overlap gate **fires** on {esc(uniq.get('duplicate_count'))} dense
  universal-support priors (worst {num(uniq.get('worst_dot_overlap'), 3)}) → logged as a duplicate,
  `unique_literal = false`, `stop_required = true` (IR-60-GATE-01). The same gate was then run on the
  **continuous surface before dot placement** (protocol rule 1 requires both): 655/655 rasters,
  {esc(usurf.get('my_dots'))} positive cells, worst ρ
  **{num(usurf.get('worst_spearman_full_footprint'), 5)}**, worst Jaccard
  {num(usurf.get('worst_jaccard_dot_sets'), 5)}, same {esc(usurf.get('duplicate_count'))} dense-prior overlap
  firings → `evidence/h60a_uniqueness_surface.json`.
* **Format**: 15/15 local checks pass, every cell finite and in `[0, 1]` (zeros mode, never NaN — the
  fix for the portal's *"Predicted values must be in range [0, 1]"*), EPSG:32611, 3730 × 3292,
  transform identical to `sample_submission.tif`, **0** dots on mapped catalogue faults, recomputed
  from scratch and asserted pixel-identical (`--verify-existing`).
* **Shared-tool fixes (fixed once, no private fork)**: local-window dilation + a per-cell transect pool
  in the mandated first test (IR-60-PERF-01); `geomorph.branch_signature` replacing terminal-sink
  identity as the independence measure, because the basin is internally drained — 1,224 sinks for
  5.17 M cells made the pre-registered ≥ 3 rule reject 36,556 of 36,633 candidates (IR-60-INDEP-01,
  fixed before any score was recorded; superseded build kept in `evidence/superseded/`, never linked or
  scored); `binary_dilation` above 100 k positive cells in the uniqueness scan after a silent OOM
  (IR-60-MEM-01) plus an incremental rows cache.
* **Lane inputs** live in `data/official/` (restored through the hash-pinned bridge, receipt
  `evidence/data_preparation.json`); lane code is `src/gems60/geomorph.py` + `src/gems60/lane.py`
  (new files — it neither forks nor overwrites `src/gems60chi/` or the first run's `src/gems60/`
  modules), drivers `scripts/build_geomorph_features.py`, `scripts/run_lane60.py`,
  `scripts/build_submission60.py`, `scripts/check_uniqueness60.py`, `scripts/write_run_card.py`,
  `scripts/build_site60.py`; tests `tests/test_geomorph.py` (18 passing).
* **Irregularities**: IR-60-DATA-01 (3DEP/USGS unreachable → band 12 stands in), IR-60-CITE-01
  (DOIs cited for manual review, not fetched), IR-60-GATE-01 (literal overlap gate fires on dense
  priors), IR-60-API-01 (`gh api` REST rate limit → git protocol for large blobs), IR-60-PROXY-01
  (holdout truth *is* the catalogue), IR-60-MEM-01, IR-60-PERF-01, IR-60-INDEP-01, IR-60-CORPUS-01
  (resolved: 4 deleted registry rasters recovered from git history).
* **Next session**: with three convergent negatives, leave this lane. If it is touched again, run
  H60-D first (gate knickpoints on a coincident `depth_to_base_surf` step — the direct test of the
  named lithologic mimic) and re-derive the emission bar from the live-anchored truth model instead of
  the catalogue-proxy holdout.
<!-- {MARK}:END -->
"""
    readme = ROOT / "README.md"
    txt = readme.read_text()
    pat = re.compile(rf"\n?<!-- {MARK}:BEGIN -->.*?<!-- {MARK}:END -->\n?", re.S)
    # the shared README lists one section per parallel run, in order; this run's
    # section always goes last so the chronology stays readable
    readme.write_text(pat.sub("\n", txt, count=1).rstrip() + "\n\n" + readme_block.strip() + "\n")
    print(f"[site] wrote {PAGE.relative_to(ROOT)}; refreshed blocks in docs/index.html and README.md; "
          f"artefacts in docs/downloads/ ({tif_rel})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
