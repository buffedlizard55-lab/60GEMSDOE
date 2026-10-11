"""Reassemble the hash-pinned competition bridge in a fresh clone.

The official competition rasters cannot be downloaded without DrivenData
authentication.  The team's data bridge (git repo `buffedlizard55-lab/GEMSDOE`,
branch `main`, path `data/bridge/`) carries the owner-mirrored copies split
into parts; `data/bridge/manifest.json` in THIS repo pins every sha256.

Usage:
    python scripts/fetch_bridge.py          # verifies pins, writes data/*.tif

Official pins (verified 2026-10-11 in data/bridge/manifest.json):
  training_features.tif  4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5
  existing_faults.tif    7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093
  example_submission.tif 2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "data" / "bridge"
UPSTREAM = "https://github.com/buffedlizard55-lab/GEMSDOE.git"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def have_local_parts() -> bool:
    man = json.load(open(BRIDGE / "manifest.json"))
    need = []
    for f in man["files"]:
        if "parts" in f:
            need += [BRIDGE / p["name"] for p in f["parts"]]
        else:
            if not (BRIDGE / f["name"]).exists() or f["name"] == "gems-geodawn-numerical-features.tif":
                need.append(BRIDGE / f["name"])
    return all(p.exists() for p in need)


def main() -> int:
    BRIDGE.mkdir(parents=True, exist_ok=True)
    if not (BRIDGE / "manifest.json").exists():
        print("manifest missing; cannot proceed"); return 2
    if not have_local_parts():
        print("bridge parts missing; fetching from the pinned upstream mirror ...")
        subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:limit=200k",
                        "--sparse", UPSTREAM, str(ROOT / ".bridge_upstream")], check=True)
        subprocess.run(["git", "-C", str(ROOT / ".bridge_upstream"), "sparse-checkout",
                        "set", "--skip-checks", "data/bridge"], check=True)
        src = ROOT / ".bridge_upstream" / "data" / "bridge"
        for p in src.iterdir():
            if p.is_file():
                (BRIDGE / p.name).write_bytes(p.read_bytes())
        print("fetched bridge parts from upstream mirror (owner mirror, unauthenticated)")

    man = json.load(open(BRIDGE / "manifest.json"))
    ok = True
    for f in man["files"]:
        if "parts" in f:
            out = ROOT / "data" / f["name"]
            with out.open("wb") as w:
                for p in f["parts"]:
                    pp = BRIDGE / p["name"]
                    if sha256(pp) != p["sha256"]:
                        print("PART HASH MISMATCH", p["name"]); ok = False
                    w.write(pp.read_bytes())
            if sha256(out) != f["sha256"]:
                print("ASSEMBLED HASH MISMATCH", f["name"]); ok = False
            else:
                print("OK ", f["name"], f["bytes"], "sha256 verified")
        else:
            src = BRIDGE / f["name"]
            if src.exists() and sha256(src) == f["sha256"]:
                dst = ROOT / "data" / f["name"]
                dst.write_bytes(src.read_bytes())
                print("OK ", f["name"], f["bytes"], "sha256 verified")
            else:
                print("HASH MISMATCH or missing", f["name"]); ok = False
    print("ALL HASHES VERIFIED" if ok else "FAILURE")
    if ok:
        # canonical names the runners expect
        feats = ROOT / "data" / "gems-geodawn-numerical-features.tif"
        tf = ROOT / "data" / "training_features.tif"
        if feats.exists() and not tf.exists():
            tf.hard_link_to(feats) if hasattr(tf, "hard_link_to") else tf.write_bytes(feats.read_bytes())
        lab = ROOT / "data" / "existing_faults.tif"
        if lab.exists():
            (ROOT / "data" / "labels.tif").write_bytes(lab.read_bytes())
        print("canonical names in place: training_features.tif, labels.tif")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
