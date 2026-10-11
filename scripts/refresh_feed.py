#!/usr/bin/env python3
"""Scheduled: probe every source, snapshot the public leaderboard once, rebuild feed.json.

The leaderboard snapshot is stored verbatim with the observed UTC timestamp and a `verified` flag;
if the page cannot be parsed (layout change, rate limit) *nothing* is written, so a stale row is
never presented as fresh.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems32 import feed as FEED  # noqa: E402

LB = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
UA = {"User-Agent": "GEMSDOE32-feed/1.0 (+https://buffedlizard55-lab.github.io/GEMSDOE32/)"}


def fetch(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse_leaderboard(html):
    """Rows are (rank, participant, score, submissions) in the public table."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = [re.sub(r"<[^>]+>", " ", c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        cells = [re.sub(r"\s+", " ", c).strip() for c in cells]
        if len(cells) >= 3 and re.fullmatch(r"\d+", cells[0]) and re.fullmatch(r"0\.\d+", cells[-2] if len(cells) > 3 else cells[-1]):
            rank = int(cells[0]); score = float(cells[-2] if len(cells) > 3 else cells[-1])
            out.append({"rank": rank, "participant": cells[1], "score": score,
                        "submissions": cells[2] if len(cells) > 3 else ""})
    return out


def main():
    health = FEED.refresh_sources(ROOT)
    print(f"probed {len(health['results'])} sources")
    # IR-66-FEED-01 (2026-10-11, session arena/b219bfe1): since the page started
    # client-side rendering the public table, parse_leaderboard silently returns
    # [] and the raw HTML was thrown away, so the feed's leaderboard rows froze
    # at 2026-10-04 while the site kept printing them.  Keep the raw page (first
    # 500 KB) as evidence on every run so the parser can be debugged/retargeted
    # offline, and say so loudly when it matches nothing.
    try:
        html = fetch(LB)
        page = ROOT / "evidence" / "leaderboard_page_latest.html"
        page.write_text(html[:500_000], encoding="utf-8")
        rows = parse_leaderboard(html)
        if not rows:
            print(f"WARNING: leaderboard page fetched ({len(html)} chars, kept "
                  f"at {page}) but parse_leaderboard matched 0 rows -- the page "
                  "layout has probably changed again; the feed keeps the LAST "
                  "verified snapshot rather than publishing a stale one")
    except Exception as exc:                                       # noqa: BLE001
        print(f"leaderboard read failed ({type(exc).__name__}: {exc}); nothing written")
        rows = []
    if rows:
        rec = {"observed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "url": LB,
               "verified": True, "rows": rows}
        with (ROOT / "registry" / "leaderboard_history.jsonl").open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"leaderboard snapshot: {len(rows)} rows, top {rows[0]['score']:.4f}")
    f = FEED.build(ROOT)
    print(json.dumps({"sources": f["source_count"], "leaderboard_rows": len(f["leaderboard"])}))


if __name__ == "__main__":
    main()
