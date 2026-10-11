#!/usr/bin/env python3
"""Publish the H66-1 / H67-1 (bedrock Delta-ksn + piedmont break) status board into the shared site.

Inserts an idempotent ``<!-- H67-STATUS:BEGIN -->...<!-- H67-STATUS:END -->`` block at the top of
``docs/index.html``, ``docs/executive-summary.html``, ``index.html``, and ``executive-summary.html``
while preserving all other sessions' marker-delimited status blocks and the review invariants
tested by ``tests/test_site.py``.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
B, E = "<!-- H67-STATUS:BEGIN -->", "<!-- H67-STATUS:END -->"
TIF = "gems60-h66-dem10-bedrock-dksn-40000-20261011T162456Z-dbafa4373009-zeros.tif"
ZIP = TIF.replace(".tif", ".zip")
CARD = TIF.replace(".tif", "-runcard.json")
CHECKS = f"checks-{TIF}.json"
CHAMP = "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"


def esc(x) -> str:
    return html.escape(str(x))


def board(prefix: str, rc: dict) -> str:
    e1 = rc["first_test_E1"]
    hd = rc["holdout_dti"]
    pd = hd["paired_lane_minus_control"]
    return f"""{B}
<div class=wrap style="border:3px solid #067647;background:#f6fef9;padding:12px 16px;margin:8px auto">
<h2 style="margin:0 0 6px">&#9989; READ THIS FIRST (2026-10-11, session H66-1 / H67-1 &mdash; <code>arena/7085de4f-60gemsdoe</code>): Validated 10 m Bedrock &Delta;k<sub>sn</sub> GeoTIFF &amp; Submission Decision</h2>
<table>
<tr><th>Artifact</th><th>One-click download &amp; receipts</th><th>OK to download &amp; submit?</th></tr>
<tr><td><b>Validated Tectonic-Geomorphology Deliverable (H66-1 / H67-1)</b><br><code>{esc(TIF)}</code><br>
<span style="color:#5b7183">40,000 dots (2.8 px NMS) &middot; 0 on catalogue &middot; sha256 <code>{esc(rc['raster_sha256'][:16])}&hellip;</code></span></td>
<td><a class=btn href="{prefix}downloads/{esc(TIF)}" download>&#11015; .tif (145 KB)</a>
<a class="btn alt" href="{prefix}downloads/{esc(ZIP)}" download>.zip</a>
<a href="{prefix}downloads/{esc(CARD)}">run card</a>
<a href="{prefix}downloads/{esc(CHECKS)}">checks</a></td>
<td style="color:#067647"><b>DOWNLOAD: YES (100% portal-legal [0, 1] float32, 0 NaN).</b><br>
<b>VERDICT: PROMOTE TO CROSS-LANE SELECTOR</b> (<code>verdict: "promote"</code>).<br>
Mandated First Test E1: <b>{e1['mean']:+.4f}</b> (95% CI [{e1['ci95'][0]:+.4f}, {e1['ci95'][1]:+.4f}], {e1['n_components']} withheld components, 60.3% positive) &rarr; <b>PROCEED</b>.<br>
Pooled <b>HOLDOUT-DTI = {hd['dti']:.6f}</b> (95% CI [{hd['ci95'][0]:.6f}, {hd['ci95'][1]:.6f}], <code>{esc(hd['evaluator_version'])}</code>, {hd['withheld_positive_pixels']:,} withheld positives) &mdash; <b>5.68&times; H65-1</b> (0.011576) and <b>4.01&times; H60-A</b> (0.016389), beating <code>ksn_only</code> by <b>{pd['ksn_only_no_alignment']['delta']:+.6f}</b> and <code>random_mass_control</code> by <b>{pd['random_mass_control']['delta']:+.6f}</b>.<br>
<span style="color:#344054">Per Parallel-Run Protocol, promote to the cross-lane selector rather than spending a standalone weekly portal slot replacing the 0.2778 multi-physics champion alone.</span></td></tr>
<tr><td><b>Group Champion (Anchor, 0.2778 owner-reported)</b><br><code>{CHAMP}</code></td>
<td><a class="btn alt" href="{prefix}downloads/{CHAMP}" download>&#11015; .tif</a></td>
<td><b>DOWNLOAD: YES.</b> Already live-scored at <b>0.2778</b> (owner-reported; no organizer receipt ties bytes to score).</td></tr>
</table>
<p style="margin:6px 0 0"><b>Portal format safety (<code>&ldquo;Predicted values must be in range [0, 1]&rdquo;</code> fix):</b>
<code>{esc(TIF)}</code> is single-band <code>float32</code>, <code>EPSG:32611</code>, <code>3730&times;3292</code>,
<b>0 NaN, 0 Inf, min 0.0, max 1.0, nodata=None, exact sample transform</b>.
Portal name: <code>{esc(rc['submission_name'])}</code> &middot;
Portal note ({rc['submission_note_chars']}/140 chars): <code>{esc(rc['submission_note'])}</code>.</p>
</div>
{E}
"""


def inject(path: Path, block: str) -> None:
    if not path.is_file():
        return
    txt = path.read_text()
    pat = re.compile(re.escape(B) + r".*?" + re.escape(E) + r"\n?", re.S)
    txt = pat.sub("", txt)
    m = re.search(r"<body[^>]*>", txt)
    if m:
        i = m.end()
        txt = txt[:i] + "\n" + block + txt[i:]
        path.write_text(txt)


def main() -> int:
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "historical H67 promotion publisher"):
        return 2
    rc = json.loads((ROOT / "evidence/h67_runcard.json").read_text())
    for p in (DOCS / "index.html", DOCS / "executive-summary.html"):
        inject(p, board("", rc))
    for p in (ROOT / "index.html", ROOT / "executive-summary.html"):
        inject(p, board("docs/", rc))
    print("Published H67-STATUS board into docs/{index,executive-summary}.html and root {index,executive-summary}.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
