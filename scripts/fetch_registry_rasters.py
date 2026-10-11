#!/usr/bin/env python3
"""Fetch every prior grid raster named in the family registry index (uniqueness corpus).

Source of truth: ``evidence/registry_full_index.json`` as published by the sibling
template repository ``buffedlizard55-lab/57GEMSDOE`` (Session 6/7 audit of all 56
sibling repositories, 655 unique grid rasters, shape 3730x3292, EPSG:32611).

Method: for each owner repository, a *treeless* partial clone
(``--filter=blob:none --no-checkout --depth 1``) is made against ``github.com``
and only the blobs listed in the index are checked out, in batches.  Every byte
stream is hash-verified against the index's pinned ``sha256`` before it is
accepted; a raster that cannot be fetched or whose hash does not match is
recorded as an error and never silently dropped.

Outputs
-------
``.cache/registry/<sha256[:16]>.tif``  -- fetched, hash-verified rasters (git-ignored)
``evidence/registry_fetch_receipt.json`` -- per-raster fetch/verify receipt (fail-closed)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "buffedlizard55-lab"
CACHE = ROOT / ".cache" / "registry"
WORK = ROOT / ".cache" / "registry_work"
RECEIPT = ROOT / "evidence" / "registry_fetch_receipt.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", default=str(ROOT / "evidence" / "registry_full_index.json"))
    ap.add_argument("--limit-repos", type=int, default=0)
    a = ap.parse_args()

    index = json.loads(Path(a.index).read_text())
    rows = index["rasters"]
    by_repo: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        src = row["sources"][0]
        repo, _, path = src.partition(":")
        by_repo[repo].append(dict(row=row, path=path, repo=repo))
    repos = sorted(by_repo)
    if a.limit_repos:
        repos = repos[: a.limit_repos]

    CACHE.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    fetched: list[dict] = []
    errors: list[dict] = []
    already = {p.name[:16] for p in CACHE.glob("*.tif")}

    for n, repo in enumerate(repos, 1):
        want = [r for r in by_repo[repo] if r["row"]["sha256"][:16] not in already]
        have = [r for r in by_repo[repo] if r["row"]["sha256"][:16] in already]
        for r in have:
            fetched.append(dict(repo=repo, path=r["path"], sha256=r["row"]["sha256"],
                                bytes=r["row"]["bytes"], status="cached"))
        if not want:
            print(f"[{n}/{len(repos)}] {repo}: all {len(have)} cached", flush=True)
            continue
        wd = WORK / repo
        if wd.exists():
            shutil.rmtree(wd)
        clone = run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth", "1",
                     f"https://github.com/{OWNER}/{repo}.git", str(wd)], timeout=1200)
        if clone.returncode:
            for r in want:
                errors.append(dict(repo=repo, path=r["path"], sha256=r["row"]["sha256"],
                                   error=f"clone failed: {clone.stderr.strip()[:300]}"))
            print(f"[{n}/{len(repos)}] {repo}: CLONE FAILED", flush=True)
            continue
        paths = [r["path"] for r in want]
        ok = False
        for batch_start in range(0, len(paths), 40):
            batch = paths[batch_start:batch_start + 40]
            co = run(["git", "checkout", "HEAD", "--"] + batch, cwd=wd, timeout=1800)
            if co.returncode:
                # fall back to one-by-one so a single moved path cannot kill the batch
                for p in batch:
                    one = run(["git", "checkout", "HEAD", "--", p], cwd=wd, timeout=600)
                    if one.returncode:
                        pass  # recorded below by the hash check
        for r in want:
            src_file = wd / r["path"]
            dest = CACHE / f"{r['row']['sha256'][:16]}.tif"
            if not src_file.is_file():
                errors.append(dict(repo=repo, path=r["path"], sha256=r["row"]["sha256"],
                                   error="path not present at HEAD"))
                continue
            got = sha256(src_file)
            if got != r["row"]["sha256"]:
                errors.append(dict(repo=repo, path=r["path"], sha256=r["row"]["sha256"],
                                   error=f"hash mismatch: got {got}"))
                continue
            shutil.move(str(src_file), dest)
            fetched.append(dict(repo=repo, path=r["path"], sha256=got,
                                bytes=dest.stat().st_size, status="fetched"))
        print(f"[{n}/{len(repos)}] {repo}: fetched {len(want)} (errors so far {len(errors)})", flush=True)
        shutil.rmtree(wd, ignore_errors=True)

    receipt = dict(evidence_class="REGISTRY-MEASUREMENT",
                   purpose="uniqueness corpus for the 60GEMSDOE tectonic-geomorphology lane",
                   index_source=str(a.index),
                   index_rows=len(rows), index_unique_grid_rasters=index["n_unique_grid_rasters"],
                   repos_scanned=len(repos), fetched=len(fetched), errors=len(errors),
                   complete=(len(errors) == 0 and len(fetched) >= len(rows)),
                   rows=fetched, error_rows=errors)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(f"[registry] fetched={len(fetched)} errors={len(errors)} complete={receipt['complete']}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
