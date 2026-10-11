#!/usr/bin/env python3
"""Insert the H65-1 'read this first' status board (idempotent, marker-delimited)
at the very top of docs/index.html, docs/executive-summary.html, the root
index.html and README.md, and point the header download buttons at files whose
submit verdict is printed next to them.  Numbers come from evidence/h65_runcard.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RC = json.loads((ROOT / "evidence/h65_runcard.json").read_text())
TIF = Path(RC["artifact"]["file"]).name
ZIP = TIF.replace(".tif", ".zip")
CARD = TIF.replace(".tif", "-runcard.json")
CHAMP = "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
PRIMARY = Path(json.loads((ROOT / "registry/submission_build.json").read_text())["file"]["path"]).name
B, E = "<!-- H65-STATUS:BEGIN -->", "<!-- H65-STATUS:END -->"
h = RC["holdout_dti"]
lane, rnd, dist = h["lane"], h["random_mass_control"], h["distance_only_control"]
e1 = RC["first_test_E1"]
LB = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"


def board(prefix: str) -> str:
    d = prefix
    return f"""{B}
<div class=wrap style="border:3px solid #b42318;background:#fff5f5;padding:12px 16px;margin:8px auto">
<h2 style="margin:0 0 6px">Read this first (2026-10-11, H65-1): is a file here OK to submit?</h2>
<table>
<tr><th>file</th><th>download</th><th>submit to the portal?</th></tr>
<tr><td><b>Newest unique TIF (this session, H65-1)</b><br><code>{TIF}</code></td>
<td><a class=btn href="{d}downloads/{TIF}" download>&#11015; .tif</a> <a class="btn alt" href="{d}downloads/{ZIP}" download>.zip</a> <a href="{d}downloads/{CARD}">run card</a></td>
<td style="color:#b42318"><b>NO.</b> Verdict NEGATIVE: first test INCONCLUSIVE (mean {e1['mean']:+.4f}, 95% CI [{e1['ci95'][0]:+.4f}, {e1['ci95'][1]:+.4f}]) &rarr; stop.
HOLDOUT-DTI {lane['dti']:.5f} [{lane['ci95'][0]:.5f}, {lane['ci95'][1]:.5f}] vs random {rnd['dti']:.5f} (evaluator {h['evaluator_version']}, {h['n_withheld_positives']:,} withheld positives). Research only.</td></tr>
<tr><td><b>Group champion, already scored</b><br><code>{CHAMP}</code></td>
<td><a class="btn alt" href="{d}downloads/{CHAMP}" download>&#11015; .tif</a></td>
<td>Already scored: owner-reported live score 0.2778 (not visible to us as an organizer receipt). Uploading it again uses a slot and only repeats a known score.</td></tr>
<tr><td><b>Registry primary (H61-A XCRD, earlier session)</b><br><code>{PRIMARY}</code></td>
<td><a class="btn alt" href="{d}downloads/{PRIMARY}" download>&#11015; .tif</a></td>
<td><b>NOT CLEARED</b> for a slot. It is unique and portal-safe, and was offered as an explicit bounded-downside bet. No local holdout certifies that it beats the champion (see its own box below).</td></tr>
<tr><td>Every other 2026-10-11 file on this site</td><td>below</td><td><b>NO</b>. Each one is NEGATIVE or NOT CLEARED; its own box says why.</td></tr>
</table>
<p style="margin:6px 0 0"><b>Bottom line: no file in this repository is cleared by a holdout for a new submission slot.</b>
Format is not the problem: every file is float32, values in [0, 1], 0 NaN, so the portal error
<i>"Predicted values must be in range [0, 1]"</i> cannot come back. The problem is that none of them beat the
holdout best ({dist['dti']:.5f}, distance-only control). If you upload the H65-1 file anyway for research, use the name
<code>{RC['submission_name']}</code> and the note <code>{RC['note']}</code> ({RC['note_chars']} characters).
Full report: <a href="{d}h65-report.html">{d}h65-report.html</a>. Public leaderboard top, checked
2026-10-11: <b>0.4133</b> (<a href="{LB}">leaderboard</a>). Earlier pages say 0.3774, which is stale (see irregularities).</p>
</div>
{E}
"""


def put(path: Path, block: str, after: str):
    s = path.read_text()
    s = re.sub(re.escape(B) + r".*?" + re.escape(E) + r"\n?", "", s, flags=re.S)
    i = s.index(after) + len(after)
    s = s[:i] + "\n" + block + s[i:]
    path.write_text(s)


def fix_header(path: Path, d: str):
    s = path.read_text()
    old = re.search(r'<div class=dlbtn>.*?</div>', s, flags=re.S)
    if old:
        new = (f'<div class=dlbtn><a class="btn" href="{d}downloads/{TIF}">&#11015; Newest TIF (H65-1): research only, do NOT submit</a> '
               f'<a class="btn alt" href="{d}downloads/{CHAMP}">&#11015; Champion (already scored 0.2778)</a></div>')
        s = s.replace(old.group(0), new, 1)
        path.write_text(s)


def main():
    for rel, pre in (("docs/index.html", ""), ("docs/executive-summary.html", "")):
        p = ROOT / rel
        put(p, board(pre), "<body>")
        fix_header(p, pre)
    put(ROOT / "index.html", board("docs/"), "<body>")
    # README: markdown board right under the title block
    rm = ROOT / "README.md"
    s = rm.read_text()
    s = re.sub(re.escape(B) + r".*?" + re.escape(E) + r"\n?", "", s, flags=re.S)
    s = s.replace("**Live leaderboard top (verified 2026-10-11): 0.3774**",
                  "**Live leaderboard top (re-checked 2026-10-11, H65 session): 0.4133** (an earlier same-day reading said 0.3774; see IR-65-LB-01)")
    md = f"""{B}
> ## 🚦 READ THIS FIRST (2026-10-11, H65-1): is a file here OK to submit?
> | file | download | submit? |
> |---|---|---|
> | **Newest unique TIF, H65-1** (native 3DEP 10 m knickpoints) | [⬇ `{TIF}`](docs/downloads/{TIF}) · [zip](docs/downloads/{ZIP}) · [run card](docs/downloads/{CARD}) | ❌ **NO: NEGATIVE.** First test INCONCLUSIVE ({e1['mean']:+.4f} [{e1['ci95'][0]:+.4f}, {e1['ci95'][1]:+.4f}]) → stop; HOLDOUT-DTI {lane['dti']:.5f} [{lane['ci95'][0]:.5f}, {lane['ci95'][1]:.5f}] < random {rnd['dti']:.5f} ({h['evaluator_version']}, {h['n_withheld_positives']:,} withheld positives) |
> | Group champion, already scored 0.2778 | [⬇ `{CHAMP}`](docs/downloads/{CHAMP}) | already scored; re-uploading repeats a known score |
> | Registry primary, H61-A XCRD (earlier session) | [⬇ `{PRIMARY}`](docs/downloads/{PRIMARY}) | ⚠️ **NOT CLEARED**: unique bounded-downside bet; no local holdout certifies it beats the champion |
> | every other 2026-10-11 file below | see its box | ❌ NO (NEGATIVE or NOT CLEARED) |
>
> **No file in this repository is cleared by a holdout for a new slot.** All files are portal-safe (float32, [0, 1], 0 NaN). If the
> H65-1 file is uploaded for research: name `{RC['submission_name']}`, note `{RC['note']}` ({RC['note_chars']} chars).
> Details are in [H65-1 session](#h65-1-session-2026-10-11--native-3dep-10-m-knickpoint-lane-negative) and [`docs/h65-report.html`](docs/h65-report.html).
{E}
"""
    anchor = "> ## 📦 ONE-CLICK SUBMISSION DOWNLOADS (start here)"
    i = s.index(anchor)
    s = s[:i] + md + "\n" + s[i:]
    rm.write_text(s)
    print("ok")


if __name__ == "__main__":
    main()
