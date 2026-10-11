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
    """Fail closed: historical positive holdout never overrules a STOP or literal overlap.

    The >70% co-location rule includes dense registry rasters: it does not contain
    an exception for calibration lattices. Format checks are not portal receipts.
    """
    status = json.loads((ROOT / "registry/current_site_status.json").read_text())
    if status.get("status") != "STOP":
        raise ValueError("Status changed: review lane gate before publishing")
    uniq = rc["uniqueness_vs_registry"]["final_dots"]
    if uniq["max_dot_overlap_within_3px_all_68_rasters_literal"] <= 0.70:
        raise ValueError("Uniqueness evidence changed: review before publishing")
    return f"""{B}
<div class="wrap current-stop-notice" style="border:3px solid #b42318;background:#fffafa;padding:12px 16px;margin:8px auto">
<h2>STOP — DOWNLOAD FOR RESEARCH ONLY; DO NOT SUBMIT</h2>
<p>The channel-steepness / χ / knickpoint lane is stopped by its registered first test.
The historical H66-1/H67-1 result has a positive catalogue <b>HOLDOUT-DTI</b>
({rc['holdout_dti']['dti']:.6f}, 95% CI {rc['holdout_dti']['ci95']},
{rc['holdout_dti']['withheld_positive_pixels']:,} withheld positives,
{esc(rc['holdout_dti']['evaluator_version'])}), but this is <b>not</b> a live score
and does not override the lane STOP. Moreover, its final dots overlap a registry raster by
{uniq['max_dot_overlap_within_3px_all_68_rasters_literal']:.1%} within 3 px,
above the literal 70% uniqueness ceiling. Excluding dense lattices after the fact is
not an exemption. Historical “promote” metadata is superseded: <b>verdict NEGATIVE</b>.
The claimed 0.2778 for H33 remains <b>owner-reported, not ORGANIZER-CONFIRMED</b>
for the exact raster bytes; the public leaderboard has no file-level attribution.</p>
<p><a class="btn" href="{prefix}downloads/{esc(TIF)}" download>Download existing H66-1 TIFF — research only</a>
<a href="{prefix}downloads/{esc(CHECKS)}">Local format checks</a> ·
<a href="{prefix}executive-summary.html">How to submit a future cleared TIFF</a> ·
<a href="{prefix}research/2026-10-11-lane-stop-audit.md">Audit and candidate hypotheses</a>.
Single-band float32 with finite [0,1] values on the local sample grid passed
preflight, <em>not</em> organizer acceptance. <b>No new file or submission slot is authorized.</b></p>
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
    rc = json.loads((ROOT / "evidence/h67_runcard.json").read_text())
    for p in (DOCS / "index.html", DOCS / "executive-summary.html"):
        inject(p, board("", rc))
    for p in (ROOT / "index.html", ROOT / "executive-summary.html"):
        inject(p, board("docs/", rc))
    print("Published fail-closed research-only H67 status; no new TIFF or submission slot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
