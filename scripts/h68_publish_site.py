#!/usr/bin/env python3
"""Publish the H68-1 status board into the shared site when authorized; fails closed on STOP."""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B, E = "<!-- H68-STATUS:BEGIN -->", "<!-- H68-STATUS:END -->"
TIF = "gems60-h68-dem10-lidar-piedmont-dksn-40000-20261011T185033Z-6e9b1e286c45-zeros.tif"
CHECKS = f"checks-{TIF}.json"


def esc(x) -> str:
    return html.escape(str(x))


def board(prefix: str, rc: dict) -> str:
    status = json.loads((ROOT / "registry/current_site_status.json").read_text())
    if status.get("status") != "STOP":
        raise ValueError("Status changed: review lane gate before publishing")
    uniq = rc["uniqueness_vs_registry"]["final_dots"]
    return f"""{B}
<div class="wrap current-stop-notice" style="border:3px solid #b42318;background:#fffafa;padding:12px 16px;margin:8px auto">
<h2>STOP — DOWNLOAD FOR RESEARCH ONLY; DO NOT SUBMIT (H68-1)</h2>
<p><b>H68-1 artifact:</b> <code>{esc(TIF)}</code> (40,000 dots at 3.0 px NMS, strict &ge;3 drainages).
<b>OK to download for research: YES. OK to submit to competition: NO (DO NOT SUBMIT; verdict NEGATIVE).</b>
Measured catalogue <b>HOLDOUT-DTI = {rc['holdout_dti']['dti']:.6f}</b> (95% CI {rc['holdout_dti']['ci95']},
{rc['holdout_dti']['withheld_positive_pixels']:,} withheld positives, <code>{esc(rc['holdout_dti']['evaluator_version'])}</code> —
2.61&times; H66-1, 14.85&times; H65-1, 10.49&times; H60-A) and E1 = {rc['first_test_E1']['mean']:+.4f} ({rc['first_test_E1']['ci95']}).
Across all 65 non-lattice rasters max 3-px dot overlap is {uniq['max_dot_overlap_within_3px_non_lattice_65_rasters']:.4f} (&le; 0.70),
but in the literal 70-raster scan (including space-filling lattice <code>calib_r13lattice_00904.tif</code>) raw 3-px overlap is
{uniq['max_dot_overlap_within_3px_all_70_rasters_literal']:.1%} (&gt; 0.70) and the governing H65-1 lane STOP remains binding.</p>
<p><a class="btn" href="{prefix}downloads/{esc(TIF)}" download>Download H68-1 TIFF — research only</a>
<a href="{prefix}downloads/{esc(CHECKS)}">Local format checks</a></p>
</div>
{E}
"""


def main() -> int:
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "H68 site publisher"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
