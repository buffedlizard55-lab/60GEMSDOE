#!/usr/bin/env python3
"""Scheduled refresh of non-competition source health and the repository feed.

The DrivenData competition host is explicitly never fetched automatically. Public leaderboard
snapshots are transcribed manually through a permitted rendered-page read and committed with their
observed date, retrieval method, and attribution caveat. This script preserves the last manual
snapshot; it does not scrape or update leaderboard rows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems32 import feed as FEED  # noqa: E402


def main() -> None:
    health = FEED.refresh_sources(ROOT)
    print(f"probed {len(health['results'])} non-competition sources; DrivenData is marked not_probed")
    f = FEED.build(ROOT)
    print(json.dumps({
        "sources": f["source_count"],
        "leaderboard_rows": len(f["leaderboard"]),
        "leaderboard_observed_utc": f.get("leaderboard_observed_utc"),
        "leaderboard_policy": "manual snapshots only; no automated competition-host request",
        "active_site_status": f.get("active_site_status", {}).get("status"),
    }, indent=2))


if __name__ == "__main__":
    main()
