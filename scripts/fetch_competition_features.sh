#!/usr/bin/env bash
# Reconstruct the official competition feature stack (418,912,844 B) into data/.
#
# The bytes are the ones printed on the DrivenData data tab. They are too large to
# commit (>100 MB GitHub blob limit) so the family transports them as sha256-pinned
# <=90 MiB parts in the git bridge of the sibling repositories, and this script
# verifies every part and the concatenated whole-file hash before placing them.
#
# Usage:  bash scripts/fetch_competition_features.sh [SIBLING_REPO]
set -euo pipefail
REPO="${1:-6GEMSDOE}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="${TMPDIR:-/tmp}/gems60_bridge"
EXPECT_FULL="4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5"
mkdir -p "$WORK"
[ -d "$WORK/$REPO/.git" ] || git clone --depth 1 \
  "https://github.com/buffedlizard55-lab/$REPO.git" "$WORK/$REPO"
cd "$WORK/$REPO/data/bridge"
python3 - "$ROOT" <<'PY'
import hashlib, json, pathlib, shutil, sys
root = pathlib.Path(sys.argv[1])
man = json.loads(pathlib.Path("manifest.json").read_text())
entry = [f for f in man["files"]
         if f["canonical"] == "training_features.tif"][0]
out = root / "data" / entry["canonical"]
with open(out, "wb") as fh:
    for part in entry["parts"]:
        b = pathlib.Path(part["name"]).read_bytes()
        assert len(b) == part["bytes"], f"{part['name']}: size drift"
        assert hashlib.sha256(b).hexdigest() == part["sha256"], f"{part['name']}: hash drift"
        fh.write(b)
h = hashlib.sha256()
with open(out, "rb") as fh:
    for c in iter(lambda: fh.read(1 << 20), b""):
        h.update(c)
assert h.hexdigest() == entry["sha256"], "whole-file sha256 drift"
assert out.stat().st_size == entry["bytes"], "whole-file size drift"
# copy the two small files too, so the repo is reproducible end to end
for src, dst in (("existing_faults.tif", "labels.tif"),
                 ("example_submission.tif", "sample_submission.tif")):
    shutil.copy2(src, root / "data" / dst)
print("PLACED + VERIFIED", out, out.stat().st_size, h.hexdigest())
PY
