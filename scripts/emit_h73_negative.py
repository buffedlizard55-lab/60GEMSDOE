#!/usr/bin/env python3
"""Emit the measured-negative H73 array with the shared fail-closed writer.

Run only after ``scripts/run_h73.py --allow-negative-artifact`` and the complete
registry audit. This script never approves a weekly slot; it exists so the new
research TIFF is reproducible rather than being a one-off shell command.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems57 import grid as G57  # noqa: E402
from gems57 import submission_writer as SW  # noqa: E402

STEM = "gems60-h73-paired-basin-ksn-20000-20261011T200117Z-zeros"
OUT = ROOT / "docs" / "downloads" / f"{STEM}.tif"


def main() -> int:
    e1 = json.loads((ROOT / "evidence" / "h73_e1_first_test.json").read_text())
    hold = json.loads((ROOT / "evidence" / "h73_holdout.json").read_text())
    uniq = json.loads((ROOT / "evidence" / "h73_preplacement_uniqueness.json").read_text())
    # Fail closed if evidence accidentally becomes promotable without a new selector decision.
    if e1["dual_gate_passed"] or hold["gate_G4_beats_recorded_h68_point"] or uniq["passes"]:
        raise SystemExit("evidence state changed; do not use the negative-artifact emitter")
    pred = np.load(ROOT / ".cache" / "features73" / "production_prediction.npy").astype(np.float32)
    grid = G57.load_grid()
    rec = SW.write_submission(
        OUT, pred, ROOT / "data" / "official" / "sample_submission.tif", grid.footprint,
        note="H73 paired-basin ksn, 20k weighted cells; holdout negative; unique bytes/pixels; DO NOT SUBMIT",
        name="60GEMSDOE-H73-PAIRED-BASIN-KSN-20000-20261011T200117Z",
        catalogue=grid.catalogue,
        metadata={"preregistration": "registry/preregistration-h73.json", "verdict": "negative",
                  "uniqueness": "pixel/byte unique across 680 checked; literal overlap gate failed"})
    print(json.dumps({"file": rec["file"], "sha256": rec["sha256"],
                      "validator_passed": rec["validator"]["all_checks_passed"],
                      "verdict": "negative", "submit": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
