#!/usr/bin/env python3
"""Deprecated H65 publisher entrypoint.

The original H65-only page publisher contained stale H33 score-attribution and submission-status
claims and could overwrite the current STOP review. It is intentionally reduced to a safe alias for
the authoritative site builder; it never edits pages directly, creates a TIFF, or recommends a slot.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        status = json.loads((ROOT / "registry/current_site_status.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"STOP: cannot read authoritative site status ({exc})") from exc
    if status.get("status") != "STOP" or status.get("recommended_competition_submission") is not None:
        raise SystemExit("STOP: legacy H65 publisher disabled; current status is not a non-promoted STOP")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/build_site.py")], cwd=ROOT, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
