#!/usr/bin/env bash
# Autonomous Competition Data Placement & SHA-256 Verification Script
# Restores competition rasters, external USGS/DOE layers, and historical scored rasters
# into GEMS_DATA_DIR (defaulting to .cache/gems_data if present, or data/) and writes
# data/restore_receipt.json.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${GEMS_DATA_DIR:-$ROOT/.cache/gems_data}"
mkdir -p "$TARGET_DIR" "$ROOT/data"

echo "[GEMSDOE32] Verifying and restoring competition data into: $TARGET_DIR"
python3 "$ROOT/scripts/restore_data.py" --group all --target-dir "$TARGET_DIR"

python3 - "$ROOT" "$TARGET_DIR" <<'PY'
import json, os, sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
receipt = json.loads((root / "data" / "restore_receipt.json").read_text())

def link_if_missing(src: Path, dst: Path) -> None:
    if not src.exists() or dst.exists() or dst.is_symlink():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    rel = os.path.relpath(src, dst.parent)
    dst.symlink_to(rel)

for f in receipt.get("files", []):
    rel_dest = f["dest"]
    src = target / rel_dest
    link_if_missing(src, root / "data" / rel_dest)
    link_if_missing(src, root / "data" / "raw" / rel_dest)
    if rel_dest in ("training_features.tif", "labels.tif", "existing_faults.tif", "sample_submission.tif"):
        link_if_missing(src, root / "data" / "official" / rel_dest)

g28 = root / "registry" / "rasters" / "GEMSDOE28__h27-4-r1-solo-d2-8.tif"
link_if_missing(g28, root / "data" / "raw" / "scored" / "gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif")
link_if_missing(g28, root / "data" / "scored" / "gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif")
PY

echo "[GEMSDOE32] Competition data placement and SHA-256 verification succeeded."
