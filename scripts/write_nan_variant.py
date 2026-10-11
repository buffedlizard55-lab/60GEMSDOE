#!/usr/bin/env python3
"""Write the spec-literal ``-nan`` sibling of a shipped ``-zeros`` artifact.

The official sample submission sets everything outside the footprint to NaN; this repository's
current artifacts carry zeros there (the ``-zeros`` suffix).  Both are in [0, 1] everywhere, so both
pass the portal's range check; the difference is only the outside-of-footprint fill.  This script
takes a shipped ``-zeros`` file, sets every outside-footprint cell to NaN, writes the sibling as
``<name>-nan.tif``, validates it with the shared validator and appends the receipt to the run card
under ``artifact.nan_variant``.  No values inside the footprint are touched - the script asserts that.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems57 import grid as G57          # noqa: E402
from gems57 import validate as V        # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: write_nan_variant.py <shipped -zeros.tif> <run card json>")
        return 2
    src_path, card_path = Path(argv[1]), Path(argv[2])
    card = json.loads(card_path.read_text())
    assert card["artifact"]["file"] == src_path.name, "run card does not describe this file"
    assert sha256(src_path) == card["artifact"]["sha256"], "shipped sha does not match the card"

    grid = G57.load_grid()
    fp = grid.footprint
    with rasterio.open(src_path) as src:
        a = src.read(1)
        prof = src.profile.copy()
    assert a.shape == fp.shape, "grid mismatch"
    inside_before = a[fp].copy()
    out = a.copy()
    out[~fp] = np.nan
    assert np.array_equal(inside_before, out[fp]), "inside-footprint values must not change"
    assert np.isfinite(out[fp]).all() and (out[fp] >= 0).all() and (out[fp] <= 1).all()
    print(f"outside-footprint NaN cells: {int(np.isnan(out).sum()):,} of {out.size:,}; "
          f"positive dots {int((out[fp] > 0).sum()):,}")

    prof.update(nodata=float("nan"), compress="deflate")
    dst_path = src_path.with_name(src_path.name.replace("-zeros.tif", "-nan.tif"))
    with rasterio.open(dst_path, "w", **prof) as dst:
        dst.write(out, 1)
    rec = V.validate(dst_path) if callable(getattr(V, "validate", None)) else None
    receipt = dict(file=dst_path.name, sha256=sha256(dst_path), bytes=dst_path.stat().st_size,
                   fill_outside="NaN (spec-literal, matching the official sample submission)",
                   inside_footprint_unchanged=True,
                   validator_checks=rec["checks"] if isinstance(rec, dict) and "checks" in rec else rec,
                   note=("derived from the -zeros artifact; identical inside the footprint, NaN outside. "
                         "Use whichever the portal accepts; the historical rejection this project hit "
                         "was a range error, and both files are in [0,1] everywhere inside the footprint."))
    card.setdefault("artifact", {})["nan_variant"] = receipt
    card_path.write_text(json.dumps(card, indent=2, default=float) + "\n")
    print(json.dumps({k: receipt[k] for k in ("file", "sha256", "bytes")}, indent=1))
    print("card updated:", card_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
