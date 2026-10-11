"""Fail-closed guard for the stopped channel-steepness experiment lane."""
from __future__ import annotations

import json
from pathlib import Path


def lane_is_stopped(root: Path, runner: str) -> bool:
    """Block lane runners unless status and first-test evidence explicitly permit a run."""
    status_path = root / "registry" / "current_site_status.json"
    try:
        status = json.loads(status_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"STOP GUARD: {runner} not run — cannot read authoritative lane status ({exc}).")
        return True

    if "channel-steepness" not in status.get("active_lane", ""):
        print(f"STOP GUARD: {runner} not run — channel-steepness is not the registered active lane.")
        return True

    if status.get("status") == "STOP":
        print(f"STOP GUARD: {runner} not run — {status.get('stop_reason', 'lane status is STOP')}.")
        print("No experiment or GeoTIFF was generated. Do not override without separate authorization.")
        return True

    e1_path = root / "evidence" / "e1_lane_test.json"
    try:
        e1 = json.loads(e1_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"STOP GUARD: {runner} not run — cannot verify preregistered E1 result ({exc}).")
        return True

    if e1.get("verdict") == "NEGATIVE-STOP":
        print(f"STOP GUARD: {runner} not run — preregistered E1 result is NEGATIVE-STOP.")
        print("No follow-up experiment or GeoTIFF was generated. Separate authorization cannot erase the recorded stop.")
        return True

    if status.get("status") not in {"ACTIVE", "AUTHORIZED"}:
        print(f"STOP GUARD: {runner} not run — lane status {status.get('status')!r} is not ACTIVE/AUTHORIZED.")
        return True

    return False
