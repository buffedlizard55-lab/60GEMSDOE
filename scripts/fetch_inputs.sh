#!/usr/bin/env bash
# Restore every input this repository reads, from the integrity-pinned mirrors, and verify the pins.
#
# Why mirrors: the competition portal is login-walled and there is no authenticated session in the
# sandbox.  The mirrors are the same public GitHub repositories the family has used throughout, and
# every file below is verified against the SHA-256 published in their own registry manifest, which
# this repository copies at registry/data_manifest.pins.json.  The sandbox may not be able to reach
# raw.githubusercontent.com -- run this on the Actions runner (or any host with GitHub access) and
# commit nothing but the derived products.
#
#   bash scripts/fetch_inputs.sh            # into ./data and ./data/external
set -euo pipefail
DAT="${1:-data}"
mkdir -p "$DAT" "$DAT/external"
RAW=https://raw.githubusercontent.com
FEAT_REPO=buffedlizard55-lab/GEMSDOE
FEAT_REF=c0c06ac82178f26b94fce3397036ef8f12a2f3a0
DATA_REPO=buffedlizard55-lab/GEMSDOE24
DATA_REF=07345ea0604953d7efb858d9cfbc21e20c7aca0b

# training_features.tif = 5 concatenated parts (concatenate in part order, then verify)
for i in 000 001 002 003 004; do
  curl -fL "$RAW/$FEAT_REPO/$FEAT_REF/data/bridge/gems-geodawn-numerical-features.tif.part-$i" \
       -o "$DAT/.part-$i"
done
cat "$DAT/.part-000" "$DAT/.part-001" "$DAT/.part-002" "$DAT/.part-003" "$DAT/.part-004" \
    > "$DAT/training_features.tif"
rm -f "$DAT"/.part-*

for spec in \
  "data/bridge/labels.tif:$DAT/labels.tif" \
  "data/bridge/sample_submission.tif:$DAT/sample_submission.tif" \
  "data/external/derived_sgmc_faults_100m_u8.tif:$DAT/derived_sgmc_faults_100m_u8.tif"
do
  src="${spec%%:*}"; dst="${spec##*:}"
  curl -fL "$RAW/$DATA_REPO/$DATA_REF/$src" -o "$dst"
done

python3 - <<'PY'
import hashlib, pathlib, sys
PINS = {
 "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
 "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
 "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
 "derived_sgmc_faults_100m_u8.tif": "643cbe992ef4ba37588fb469163ed8291e3ceb23d6c1f78a3cfaa462430c2da0",
}
bad = 0
for name, want in PINS.items():
    p = pathlib.Path("data") / name
    if not p.exists():
        print(f"MISSING {p}"); bad = 1; continue
    got = hashlib.sha256(p.read_bytes()).hexdigest()
    ok = got == want
    print(f"{'ok  ' if ok else 'FAIL'} {name} {got[:16]}… {p.stat().st_size} B")
    bad |= 0 if ok else 1
sys.exit(bad)
PY
echo "inputs restored and verified"
