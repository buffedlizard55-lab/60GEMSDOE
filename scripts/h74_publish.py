"""Publish the H74-1 round onto whatever the site looks like *right now*.

Several sessions publish to this repository concurrently, and every one of them owns README.md,
the executive summary, the two home pages and the two registry files.  This round therefore never
*overwrites* any of them.  Instead it re-applies a small, declarative patch
(``evidence/h74_site_patch.json``) that is idempotent on markers:

  * README.md          -- the H74-1 lead is inserted after the ``<!-- h73b-lead -->`` block
                          (or after the first other round's lead, or at the very top).
  * registry/current_site_status.json
                       -- this round's record is stored under its own ``h74_1`` key; the
                          top-level keys are left to whichever session published last.
  * registry/irregularities.json
                       -- the ``IR-74-*`` items are merged by id, never duplicated.
  * docs/executive-summary.html, docs/index.html, index.html
                       -- an H74-1 card / banner is injected, never regenerated.
  * docs/h74-report.html -- owned outright by this round.

Running it twice changes nothing the second time.  Run:
    /home/user/.venv/bin/python scripts/h74_publish.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = json.loads((ROOT / "evidence" / "h74_site_patch.json").read_text())
MARK = "<!-- h74-lead -->"


def _read(p: Path) -> dict:
    return json.loads(p.read_text())


def _write(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, indent=1) + "\n")


# ----------------------------------------------------------------------------- README ---------- #
def publish_readme() -> str:
    p = ROOT / "README.md"
    txt = p.read_text()
    if MARK in txt:
        return "README: h74-lead already present"
    lead = PATCH["readme_lead"]
    if not lead.lstrip().startswith(MARK):
        lead = MARK + "\n" + lead
    anchor = PATCH.get("readme_anchor_after")
    if anchor and anchor in txt:
        # insert immediately after that round's lead block: at the next top-level heading
        i = txt.index(anchor)
        nxt = re.search(r"\n## ", txt[i + len(anchor):])
        pos = i + len(anchor) + (nxt.start() if nxt else 0)
        if nxt is None:
            pos = len(txt)
        txt = txt[:pos] + "\n" + lead + "\n" + txt[pos:]
        how = f"after {anchor}"
    else:
        m = re.search(r"\n## ", txt)
        pos = m.start() if m else len(txt)
        txt = txt[:pos] + "\n" + lead + "\n" + txt[pos:]
        how = "at the top of the body"
    p.write_text(txt)
    return f"README: h74-lead inserted {how} ({len(lead)} chars)"


# ----------------------------------------------------------------------------- registries ------ #
def publish_status() -> str:
    p = ROOT / "registry" / "current_site_status.json"
    cur = _read(p)
    key = PATCH["status_key"]
    block = json.loads(json.dumps(PATCH["status_block"]))  # deep copy
    cur[key] = block
    note = cur.get("post_review_note", "")
    add = PATCH["post_review_note_addendum"]
    if "H74-1 (session arena/ac9d4dc4-60gemsdoe)" not in note:
        cur["post_review_note"] = note.rstrip() + " " + add
    _write(p, cur)
    return f"registry/current_site_status.json: {key} written ({len(block)} keys)"


def publish_irregularities() -> str:
    p = ROOT / "registry" / "irregularities.json"
    cur = _read(p)
    have = {i.get("id") for i in cur["items"]}
    added = []
    for item in PATCH["irregularities"]:
        if item["id"] in have:
            continue
        cur["items"].append(json.loads(json.dumps(item)))
        have.add(item["id"])
        added.append(item["id"])
    _write(p, cur)
    return (f"registry/irregularities.json: {len(added)} IR-74-* item(s) present "
            f"({len(have)} total)")


# ----------------------------------------------------------------------------- pages ----------- #
def publish_pages() -> str:
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_h74_pages.py")],
                         cwd=str(ROOT), capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit("build_h74_pages.py failed:\n" + out.stderr[-3000:])
    return "pages: " + " ".join(out.stdout.split())


def main() -> int:
    for step in (publish_readme, publish_status, publish_irregularities, publish_pages):
        print(step())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
