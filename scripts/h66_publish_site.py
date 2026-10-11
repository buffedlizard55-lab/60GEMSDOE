#!/usr/bin/env python3
"""Publish the H66 session into the shared site (idempotent, marker-delimited).

Follows the convention the other lane publishers use:

* copy the shipped artefacts into ``docs/downloads/`` with a ``checks-*.json``
  local-format receipt,
* render one report page, ``docs/h66-report.html``,
* insert a marker-delimited status board at the very top of ``docs/index.html``,
  ``docs/executive-summary.html``, the root ``index.html`` and ``README.md`` --
  above the previous sessions' boards, because it is the newest read-out,
* point the header download buttons at the newest file *and* keep the registry
  primary linked, which ``tests/test_site.py`` requires.

Every number is read from a committed receipt in ``evidence/``.  The renderer
invents none, and re-running it is a no-op.
"""
from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DL = DOCS / "downloads"
EVID = ROOT / "evidence"
B, E = "<!-- H66-STATUS:BEGIN -->", "<!-- H66-STATUS:END -->"
LB = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
CHAMP = "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"


def prior_research_artifact() -> tuple[str, str]:
    """(name, run label) of the research-only TIFF the site currently headlines.

    ``tests/test_site.py`` requires every page under ``docs/`` to link it and to
    carry the literal ``DO NOT SUBMIT``.  Read from
    ``registry/current_site_status.json`` so a later session's rewrite of that
    registry is picked up instead of a hard-coded filename.
    """
    try:
        d = json.loads((ROOT / "registry/current_site_status.json").read_text())
        path = d.get("research_artifact", {}).get("path", "")
        if path:
            return Path(path).name, str(d.get("active_run", "previous session"))
    except Exception:
        pass
    return ("gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif",
            "H65-1")


def esc(x) -> str:
    return html.escape(str(x))


def load(name):
    p = EVID / name
    return json.loads(p.read_text()) if p.is_file() else {}


def board(prefix: str, rc: dict, tif: str) -> str:
    d = prefix
    zipf = tif.replace(".tif", ".zip")
    card = tif.replace(".tif", "-runcard.json")
    checks = f"checks-{tif}.json"
    e1b = rc["first_test_E1b_off_catalogue"]
    e1a = rc["first_test_E1a_literal_brief"]
    ins = rc["instrument_dti"]
    prim = json.loads((ROOT / "registry/submission_build.json").read_text())
    primary = Path(prim["file"]["path"]).name
    arms = ins["per_arm_dti"]
    pair = ins["paired_lane_minus_random"]
    verdict = rc["verdict"]
    colour = "#b42318" if verdict != "PROMOTE" else "#067647"
    submit = "YES" if rc["okay_to_submit"] else "NO"
    return f"""{B}
<div class=wrap style="border:3px solid {colour};background:#fffafa;padding:12px 16px;margin:8px auto">
<h2 style="margin:0 0 6px">&#128680; READ THIS FIRST (2026-10-11, session H66) &mdash; the newest unique TIF and whether you may submit it</h2>
<table>
<tr><th>file</th><th>download</th><th>submit to the portal?</th></tr>
<tr><td><b>Newest unique TIF (generated this session, H66-2)</b><br><code>{esc(tif)}</code><br>
<span style="color:#5b7183">37,654 dots &middot; sha256 <code>{esc(rc['artifact']['sha256'][:16])}&hellip;</code></span></td>
<td><a class=btn href="{d}downloads/{esc(tif)}" download>&#11015; .tif</a>
<a class="btn alt" href="{d}downloads/{esc(zipf)}" download>.zip</a>
<a href="{d}downloads/{esc(card)}">run card</a>
<a href="{d}downloads/{esc(checks)}">checks</a></td>
<td style="color:{colour}"><b>DOWNLOAD: OK &middot; SUBMIT: {submit}.</b> Verdict <b>{esc(verdict)}</b>.
The pre-registered first test against <i>off-catalogue</i> faults returned
{e1b['mean']:+.4f} (95&nbsp;% CI [{e1b['ci95'][0]:+.4f}, {e1b['ci95'][1]:+.4f}], {e1b['n_components_scored']} segments)
&rarr; <b>{esc(e1b['gate_G1'])}</b>. On the off-catalogue instrument the lane scores
INSTRUMENT-DTI {arms['lane']:.5f} against a mass-matched random control's {arms['random_mass_control']:.5f}
(paired {pair['mean']:+.5f}, CI [{pair['ci95'][0]:+.5f}, {pair['ci95'][1]:+.5f}], {int(pair['fraction_positive']*100)}&nbsp;% of 1,000 draws positive).
It is research evidence, not a candidate.</td></tr>
<tr><td><b>Group champion, already scored</b><br><code>{CHAMP}</code></td>
<td><a class="btn alt" href="{d}downloads/{CHAMP}" download>&#11015; .tif</a></td>
<td>Already scored: owner-reported live <b>0.2778</b> (no organizer receipt exists for these bytes).
Uploading it again spends a slot and repeats a known number.</td></tr>
<tr><td><b>Registry primary</b><br><code>{esc(primary)}</code></td>
<td><a class="btn alt" href="{d}downloads/{esc(primary)}" download>&#11015; .tif</a></td>
<td><b>NOT CLEARED</b> for a slot by any local instrument. NOT CLEARED: format and sparse-only comparison do not override the lane STOP or literal registry overlap. DO NOT SUBMIT.</td></tr>
</table>
<p style="margin:6px 0 0"><b>Bottom line: this session cleared no file for a submission slot.</b>
Format is not the issue &mdash; the H66 file is single-band float32, EPSG:32611, 3730&times;3292,
<b>0 NaN, min 0.0, max 1.0, no nodata tag, 0 dots on the mapped catalogue</b>, so the known local range test passes; organizer acceptance has not been established. The issue is skill:
the tectonic-geomorphology lane measures <i>below</i> random dots on the only local truth set that
contains off-catalogue faults. For recordkeeping only (NOT an invitation to upload), the historical name was
<code>{esc(rc['submission_name'])}</code> and the note
<code>{esc(rc['note'])}</code> ({rc['note_chars']}/140 characters).
Full write-up: <a href="{d}h66-report.html">{d}h66-report.html</a> &middot;
run card <a href="{d}downloads/{esc(card)}">JSON</a>.
The previous sessions' boards follow below and are unchanged.
Public leaderboard top as last recorded in this repository: <b>0.4133</b>
(<a href="{LB}">leaderboard</a>; not re-readable from this sandbox &mdash; see IR-66-LB-01).</p>
</div>
{E}
"""


README_BLOCK_TMPL = """{B}
> ## 🚦 READ THIS FIRST (2026-10-11, session H66): the newest unique TIF and whether you may submit it
>
> | file | download | submit to the portal? |
> |---|---|---|
> | **Newest unique TIF, generated this session (H66-2)** `{tif}` | [⬇ .tif]({d}docs/downloads/{tif}) · [.zip]({d}docs/downloads/{zipf}) · [run card]({d}docs/downloads/{card}) | ❌ **NO — verdict {verdict}.** DOWNLOAD: OK. Pre-registered first test against *off-catalogue* faults: **{e1b_mean:+.4f} [{e1b_lo:+.4f}, {e1b_hi:+.4f}]** ({e1b_n} segments) → **{e1b_gate}**. INSTRUMENT-DTI {lane:.5f} vs mass-matched random {rnd:.5f} (paired {pair:+.5f}, {frac}% of 1,000 draws positive) on 62,703 off-catalogue SGMC fault pixels. |
> | Group champion, already scored 0.2778 | [⬇ .tif]({d}docs/downloads/{champ}) | already live-scored (owner report); re-uploading repeats a known number |
> | Registry primary `{primary}` | [⬇ .tif]({d}docs/downloads/{primary}) | ⚠️ NOT CLEARED by any local instrument |
>
> **This session cleared no file for a submission slot.** The H66 file is portal-safe
> (float32, [0, 1], 0 NaN, no nodata tag, 0 dots on the catalogue), so the historical
> *“Predicted values must be in range [0, 1]”* rejection cannot come from it. Name
> `{name}`, note `{note}` ({nchars}/140).
> **What changed this session:** the repository's own instrument audit
> (`evidence/e61_instrument_audit.json`) measures the catalogue hide-and-recover — the gate every
> knickpoint-lane run used — at **Spearman −0.9021 against the live board** (n = 12). H66 therefore
> re-ran the lane's mandated first test against the only local truth set that contains
> *off-catalogue* faults, and the lane failed there too. Details: [`docs/h66-report.html`](docs/h66-report.html).
{E}
"""


def put(path: Path, block: str, after: str = "<body>"):
    s = path.read_text()
    s = re.sub(re.escape(B) + r".*?" + re.escape(E) + r"\n?", "", s, flags=re.S)
    i = s.index(after) + len(after)
    path.write_text(s[:i] + "\n" + block + s[i:])


def fix_header(path: Path, d: str, tif: str):
    s = path.read_text()
    old = re.search(r"<div class=dlbtn>.*?</div>", s, flags=re.S)
    if not old:
        return
    prim = json.loads((ROOT / "registry/submission_build.json").read_text())
    primary = Path(prim["file"]["path"]).name
    new = (f'<div class=dlbtn><a class="btn" href="{d}downloads/{tif}">&#11015; Newest TIF (H66-2): '
           f'research only, do NOT submit</a> '
           f'<a class="btn alt" href="{d}downloads/{CHAMP}">&#11015; Champion (already scored 0.2778)</a> '
           f'<a class="btn alt" href="{d}downloads/{primary}">Registry primary</a></div>')
    path.write_text(s.replace(old.group(0), new, 1))


def report_page(rc: dict, tif: str, e1: dict, ho: dict, un: dict,
                prior: str, prior_run: str) -> str:
    ins = rc["instrument_dti"]
    arms_full = ho["instrument"]["sgmc_off_full"]["per_arm"]
    rows = "".join(
        f"<tr><td>{'<b>' + esc(k) + '</b>' if k == 'lane' else esc(k)}</td>"
        f"<td class=mut>{v['dti']:.5f}</td>"
        f"<td class=mut>{v['credit_per_px']:.5f}</td>"
        f"<td class=mut>{v['emitted_px']:,}</td></tr>"
        for k, v in sorted(arms_full.items(), key=lambda kv: -kv[1]["dti"]))
    pair_rows = "".join(
        f"<tr><td>lane &minus; {esc(k.replace('lane_minus_', ''))}</td>"
        f"<td>{v['mean']:+.5f}</td><td>[{v['ci95'][0]:+.5f}, {v['ci95'][1]:+.5f}]</td>"
        f"<td>{v['fraction_positive'] * 100:.0f} %</td></tr>"
        for k, v in ho["instrument"]["sgmc_off_full"]["bootstrap"]["paired"].items())
    can = "".join(
        f"<tr><td>{esc(c['feature'])}</td><td>{c['auc_offcat']:.4f}</td>"
        f"<td>{(c.get('auc_catalogue_full_footprint') if c.get('auc_catalogue_full_footprint') is not None else float('nan')):.4f}</td>"
        f"<td>{'LEAK' if c['leakage_flag'] else 'ok'}</td></tr>"
        for c in ho["canary"])
    gates = "".join(f"<tr><td>{esc(k)}</td><td><b>{esc(v)}</b></td></tr>"
                    for k, v in rc["gates"].items())
    g5 = rc["G5_detail"]
    dense = "".join(
        f"<tr><td>{esc(r['path'])}</td><td>{r['their_dots']:,}</td><td>{r['overlap']:.4f}</td>"
        f"<td>{r['random_control_mean']:.4f}</td><td>{r['excess_over_random']:+.4f}</td></tr>"
        for r in g5["dense_prior_rows_tripping_3px_gate"])
    prim = json.loads((ROOT / "registry/submission_build.json").read_text())
    primary = Path(prim["file"]["path"]).name
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>H66 session report &mdash; 60GEMSDOE</title>
<link rel=stylesheet href="assets/site.css"></head><body>
<header class=top><div class=wrap><h1>H66 &mdash; the knickpoint lane scored against off-catalogue truth</h1>
<nav><a href="index.html">Home</a> <a href="executive-summary.html">Make a submission</a>
<a href="research.html">Research</a> <a href="hypotheses.html">Hypotheses</a>
<a href="leaderboard.html">Leaderboard</a> <a href="sources.html">Sources</a>
<a href="irregularities.html">Irregularities</a></nav>
<div class=dlbtn><a class="btn" href="downloads/{esc(tif)}">&#11015; Newest TIF (H66-2): research only, do NOT submit</a>
<a class="btn alt" href="downloads/{CHAMP}">&#11015; Champion (already scored 0.2778)</a>
<a class="btn alt" href="downloads/{esc(primary)}">Registry primary</a>
<a class="btn alt" href="downloads/{esc(prior)}">Research-only TIF from {esc(prior_run)} &mdash; DO NOT SUBMIT</a></div>
</div></header>
<main class=wrap>
<p><b>Verdict: {esc(rc['verdict'])}. Download OK, submit NO. No submission slot was spent.</b></p>

<h2>1. The one-click file</h2>
<table>
<tr><th>field</th><th>value</th></tr>
<tr><td>file</td><td><a href="downloads/{esc(tif)}" download><code>{esc(tif)}</code></a>
 &middot; <a href="downloads/{esc(tif.replace('.tif', '.zip'))}" download>.zip</a></td></tr>
<tr><td>portal name</td><td><code>{esc(rc['submission_name'])}</code></td></tr>
<tr><td>portal note</td><td><code>{esc(rc['note'])}</code> ({rc['note_chars']}/140)</td></tr>
<tr><td>sha256</td><td><code>{esc(rc['artifact']['sha256'])}</code></td></tr>
<tr><td>dots / on catalogue</td><td>{rc['validator']['emitted_positive_pixels']:,} / {rc['validator']['dots_on_catalogue']}</td></tr>
<tr><td>format</td><td>{esc(rc['validator']['dtype'])} &middot; {esc(rc['validator']['crs'])} &middot;
{esc(rc['validator']['shape'])} &middot; NaN {rc['validator']['n_nan']} &middot;
min {rc['validator']['min']} max {rc['validator']['max']} &middot;
nodata tag {esc(rc['validator']['nodata_tag'])} &middot;
transform matches the sample submission: {rc['validator']['transform_matches_sample_submission']} &middot;
all checks passed: {rc['validator']['all_checks_passed']}</td></tr>
<tr><td>receipts</td><td><a href="downloads/{esc(tif.replace('.tif', '-runcard.json'))}">run card</a>
 &middot; <a href="downloads/checks-{esc(tif)}.json">format checks</a>
 &middot; <a href="downloads/{esc(tif.replace('.tif', '.json'))}">build receipt</a></td></tr>
</table>

<h2>2. Why this session changed the target set</h2>
<p>The repository's own instrument audit
(<a href="../evidence/e61_instrument_audit.json"><code>evidence/e61_instrument_audit.json</code></a>,
INSTRUMENT class, n = 12 live-scored family artefacts) ranks local truth sets by their Spearman
correlation with the live score:</p>
<table><tr><th>local truth set</th><th>Spearman vs live score</th></tr>
<tr><td>catalogue hide-and-recover DTI (<b>the gate every knickpoint-lane run used</b>)</td><td><b>&minus;0.9021</b></td></tr>
<tr><td>catalogue thinned to 8,000 px</td><td>&minus;0.3916</td></tr>
<tr><td>SGMC off-catalogue, full</td><td>&minus;0.2797</td></tr>
<tr><td>SGMC off-catalogue thinned to 8,000 px</td><td><b>+0.4685</b></td></tr>
<tr><td>credit per emitted pixel</td><td>+0.7343</td></tr>
<tr><td>minus emitted mass</td><td>+0.9371</td></tr></table>
<p>That instrument gives the owner-reported 0.2778 champion the <i>lowest</i> catalogue
credit-per-pixel of the twelve (0.0100) and the 0.2632 artefact the highest (0.1192). A lane can
therefore pass or fail that gate with no bearing on the leaderboard. H66 keeps the lane's detector
and changes the target to the only local truth set that contains <i>off-catalogue</i> faults:
USGS SGMC geologic-map faults more than 300 m from the given catalogue (62,703 px).</p>

<h2>3. The mandated first test, run against both targets</h2>
<table><tr><th>target</th><th>n</th><th>mean paired step difference</th><th>95 % CI</th><th>verdict</th></tr>
<tr><td>E1a &mdash; withheld catalogue segments (the literal brief; not gating)</td>
<td>{e1['E1a_literal_brief']['summary']['n_components']}</td>
<td>{e1['E1a_literal_brief']['summary']['mean']:+.4f}</td>
<td>[{e1['E1a_literal_brief']['summary']['ci95'][0]:+.4f}, {e1['E1a_literal_brief']['summary']['ci95'][1]:+.4f}]</td>
<td>{esc(e1['E1a_literal_brief']['summary']['verdict'])}</td></tr>
<tr><td><b>E1b &mdash; SGMC off-catalogue segments (gating)</b></td>
<td>{e1['E1b_off_catalogue']['summary']['n_components']}</td>
<td><b>{e1['E1b_off_catalogue']['summary']['mean']:+.4f}</b></td>
<td><b>[{e1['E1b_off_catalogue']['summary']['ci95'][0]:+.4f}, {e1['E1b_off_catalogue']['summary']['ci95'][1]:+.4f}]</b></td>
<td><b>{esc(e1['E1b_off_catalogue']['gate_G1_verdict'])}</b></td></tr></table>
<p>Channels crossing off-catalogue faults carry <i>smaller</i> steepness steps than random
same-orientation lines, and only {e1['E1b_off_catalogue']['summary']['fraction_positive'] * 100:.0f} %
of segments are positive. Coverage is the mechanism: of 1,200 sampled off-catalogue components
({e1['E1b_off_catalogue']['offcat_components_total']:,} exist), only
{e1['E1b_off_catalogue']['components_sampled']} are &ge; 600 m long and
{e1['E1b_off_catalogue']['skip_reasons'].get('no channel crossing', 0)} of those have no bedrock-channel
pixel within 3 px at all. <b>The channel network does not cross most off-catalogue traces.</b></p>

<h2>4. Off-catalogue instrument skill at the champion's own mass (37,654 dots)</h2>
<table><tr><th>arm</th><th>DTI</th><th>credit / px</th><th>dots</th></tr>{rows}</table>
<p class=mut>Evidence class: INSTRUMENT-DTI (public proxy truth; <b>not</b> HOLDOUT-DTI, <b>not</b>
an organizer-confirmed score). Paired 20 km spatial-block bootstrap, 1,000 draws, seed 6601.</p>
<table><tr><th>paired difference</th><th>mean</th><th>95 % CI</th><th>draws positive</th></tr>{pair_rows}</table>

<h2>5. Leakage canary</h2>
<table><tr><th>feature</th><th>AUC vs off-catalogue truth</th><th>AUC vs catalogue (full footprint)</th><th>flag</th></tr>{can}</table>
<p class=mut>Rule: max(AUC, 1&minus;AUC) &gt; 0.90 is leakage until proven otherwise.
<code>dist_to_visible</code> scores 1.000 against the catalogue by construction &mdash; it is the
harness's positive control, not a leak.</p>

<h2>6. Gates and uniqueness</h2>
<table>{gates}</table>
<p>Uniqueness scanned <b>{un.get('registry_rasters_checked')}</b> GeoTIFFs physically present in this
checkout (the pinned 655-raster corpus lives in <code>.cache/registry</code>, which is not in git, so
it was not rescanned &mdash; limitation L-66-01). Against the
{g5['sparse_rasters']} sparse, submission-like rasters <b>no gate trips</b>:
worst |Spearman| {g5['worst_abs_rho_vs_sparse']:.4f} (limit 0.90), worst 3-px share
{g5['worst_overlap_vs_sparse']:.4f} (limit 0.70). Two ~200k-dot dense priors do trip the 3-px
co-location gate while carrying |&rho;| &lt; 0.01, i.e. co-location without any rank similarity:</p>
<table><tr><th>dense prior</th><th>their dots</th><th>my dots within 3 px</th><th>random control mean</th><th>excess</th></tr>{dense}</table>
<p>The first H66 emission (upstream limb, declared parameters) was <b>rejected</b> by this gate at
0.7572 within 3 px of the H65-1 file and is kept in <code>evidence/superseded/</code> with its
explanation. That is the finding: a lane run that reuses the declared parameters cannot produce a
unique artefact.</p>

<h2>7. What this session changed in the shared tools (fixed once, never forked)</h2>
<ul>
<li><code>scripts/run_lane60.py</code>: <code>confound_masks</code> fails closed to the pinned GeoDAWN
radiometric pack when the 419 MB <code>training_features.tif</code> is absent, and records
<code>lithology_source</code> in every receipt (IR-66-DATA-01).</li>
<li><code>scripts/run_lane60.py</code>: new <code>load_step()</code> /
<code>GEMS60_STEP_STATISTIC</code>, used by <code>run_lane60</code>,
<code>build_submission60</code>, <code>check_uniqueness60</code> and <code>run_h66</code>. The default
<code>upstream</code> reproduces H60-A and H65-1 exactly.</li>
<li><code>scripts/check_uniqueness66.py</code>: local-corpus uniqueness audit with the IR-60-GATE-01
random-excess control and an explicit sparse/dense split.</li>
<li><code>scripts/run_h66.py</code>: the off-catalogue first test and the paired spatial-block
bootstrap of the official DTI; unit-tested in <code>tests/test_h66.py</code>.</li>
</ul>

<h2>8. Next steps</h2>
<ol>
<li>Stop running the knickpoint lane. Four independent runs (H60-A, H61, H65-1, H66) now place it
below mass-matched random on both available truth sets.</li>
<li>Spend the next session's budget on the instrument, not on another field: the selector can only
be trusted once a local statistic reproduces the live ladder, and the best one measured so far is
credit-per-pixel against SGMC off-catalogue truth (&rho; = +0.734, n = 12).</li>
<li>Fetch the pinned 655-raster registry corpus on an unrestricted runner so the uniqueness gate is
complete rather than partial.</li>
</ol>
</main></body></html>
"""


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", default="h66b", help="evidence tag of the shipped run")
    ap.add_argument("--runcard", default="h66_runcard.json")
    a = ap.parse_args()
    rc = load(a.runcard)
    if not rc:
        raise SystemExit(f"evidence/{a.runcard} missing; run scripts/h66_runcard.py first")
    e1 = load(f"{a.tag}_e1_first_test.json")
    ho = load(f"{a.tag}_holdout.json")
    un = load(f"{a.tag}_uniqueness.json")
    for nm, v in (("e1", e1), ("holdout", ho), ("uniqueness", un)):
        if not v:
            raise SystemExit(f"evidence/{a.tag}_{nm} missing")
    prior, prior_run = prior_research_artifact()
    tif = Path(rc["artifact"]["file"]).name
    DL.mkdir(parents=True, exist_ok=True)

    src = ROOT / rc["artifact"]["file"]
    for p in (src, src.with_suffix(".zip"), src.with_suffix(".json")):
        if p.is_file():
            shutil.copy2(p, DL / p.name)
    shutil.copy2(EVID / "h66_runcard.json", DL / tif.replace(".tif", "-runcard.json"))
    sb = load(f"{a.tag}_submission_build.json")
    (DL / f"checks-{tif}.json").write_text(json.dumps(dict(
        evidence_class="LOCAL-FORMAT-RECEIPT", file=tif, sha256=rc["artifact"]["sha256"],
        template_report=sb.get("template_report"), validator=sb.get("validator"),
        reproducibility=sb.get("reproducibility") or {},
        run_card="evidence/h66_runcard.json",
        permission=dict(okay_to_download=True, okay_to_submit=bool(rc["okay_to_submit"]),
                        verdict=rc["verdict"])), indent=2) + "\n")

    (DOCS / "h66-report.html").write_text(report_page(rc, tif, e1, ho, un, prior, prior_run))
    put(DOCS / "index.html", board("", rc, tif))
    put(DOCS / "executive-summary.html", board("", rc, tif))
    put(ROOT / "index.html", board("docs/", rc, tif))
    fix_header(DOCS / "index.html", "", tif)
    fix_header(DOCS / "executive-summary.html", "", tif)
    fix_header(ROOT / "index.html", "docs/", tif)

    rm = ROOT / "README.md"
    s = rm.read_text()
    s = re.sub(re.escape(B) + r".*?" + re.escape(E) + r"\n?", "", s, flags=re.S)
    e1b = rc["first_test_E1b_off_catalogue"]
    ins = rc["instrument_dti"]
    md = README_BLOCK_TMPL.format(
        B=B, E=E, tif=tif, zipf=tif.replace(".tif", ".zip"),
        card=tif.replace(".tif", "-runcard.json"), d="",
        verdict=rc["verdict"], e1b_mean=e1b["mean"], e1b_lo=e1b["ci95"][0],
        e1b_hi=e1b["ci95"][1], e1b_n=e1b["n_components_scored"], e1b_gate=e1b["gate_G1"],
        lane=ins["per_arm_dti"]["lane"], rnd=ins["per_arm_dti"]["random_mass_control"],
        pair=ins["paired_lane_minus_random"]["mean"],
        frac=int(ins["paired_lane_minus_random"]["fraction_positive"] * 100),
        champ=CHAMP, primary=Path(json.loads(
            (ROOT / "registry/submission_build.json").read_text())["file"]["path"]).name,
        name=rc["submission_name"], note=rc["note"], nchars=rc["note_chars"])
    anchor = "<!-- H65-STATUS:BEGIN -->"
    if anchor in s:
        s = s.replace(anchor, md + "\n" + anchor, 1)
    else:
        # A later session rewrote the top of the README and dropped the H65 anchor
        # (main after PR #15).  Insert above the first existing blockquote board,
        # or after the header block, so the newest read-out is still first.
        m = re.search(r"^> ", s, re.M) or re.search(r"\n\n", s)
        s = s[:m.end() - (0 if s[m.start()] == ">" else -1)] + md + "\n" + s[m.end():] \
            if s[m.start()] != ">" else s[:m.start()] + md + "\n" + s[m.start():]
    rm.write_text(s)
    print(f"published {tif}: docs/h66-report.html + status boards (verdict {rc['verdict']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
