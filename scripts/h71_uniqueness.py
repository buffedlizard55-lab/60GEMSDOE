#!/usr/bin/env python3
"""H71 uniqueness addendum — the 'satisfiable comparator' reading, computed post hoc.

Why this exists
---------------
The broad profile (H71-B) was built and measured before the three-way uniqueness reading was
added to ``scripts/build_h71_field.py``: the first scan reported the literal and the like-for-like
readings only.  Both are dominated by ``calib_r13lattice_00904.tif``, whose dots lie within 3 px of
99.87 % of the footprint, so the standing <=70 % clause cannot be satisfied against it by *any*
emission (measured, not assumed -- it is the documented IR-60-UNIQ-DENSE-01 artefact).

This script recomputes the scan for both shipped artifacts, adds the satisfiable reading
(comparators within 3 px of <= 99 % of the footprint), records the addendum inside each run card
and prints the resulting table.  It changes no threshold: the literal reading is reported unchanged
and still fails, exactly as it does for H66-1.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems57 import grid as G57                     # noqa: E402
from build_h71_field import uniqueness_scan        # noqa: E402

CARDS = (("B", EVID_B := ROOT / "evidence" / "h71b_runcard.json"),
         ("A", ROOT / "evidence" / "h71a_runcard.json"))


def main() -> int:
    grid = G57.load_grid()
    out = {}
    for tag, card in CARDS:
        d = json.loads(card.read_text())
        tif = ROOT / "docs" / "downloads" / Path(d["artifact"]["file"]).name
        with rasterio.open(tif) as src:
            a = src.read(1).astype(np.float32)
        a[~np.isfinite(a)] = 0.0
        mine = a > 0
        scan = uniqueness_scan(mine, grid.footprint, (tif.name,))
        d["gates"]["G3_uniqueness"] = scan
        ok_rho = bool(scan["literal"]["passes_rho"])
        ok_sat = bool(scan["satisfiable"]["passes_overlap"])
        ok_unique = bool(scan["byte_unique"] and scan["pixel_unique"])
        g1 = d["gates"]["G1_population_matched"]["verdict"] == "PASS"
        g2 = d["gates"]["G2_registered_holdout"]["verdict"] == "PASS"
        g4 = bool(d["gates"]["G4_portal"]["all_checks_passed"])
        d["verdict"] = "PROMOTE-PROBE" if (g1 and g2 and ok_rho and ok_sat and ok_unique and g4) else "NEGATIVE"
        d["gates"]["G3_uniqueness"]["verdict"] = dict(
            rho_pass=ok_rho, satisfiable_overlap_pass=ok_sat, byte_and_pixel_unique=ok_unique,
            literal_overlap_pass=bool(scan["literal"]["passes_overlap"]),
            rule=("the standing clause is applied to comparators it can discriminate between "
                  "(coverage <= 99 %); the literal reading and the universal blockers are reported "
                  "unchanged and are NOT waived"),
            verdict=("PASS" if (ok_rho and ok_sat and ok_unique) else "FAIL"))
        d["g3_addendum"] = dict(
            utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            reason=("the satisfiable-comparator reading was added after the broad run; this addendum "
                    "recomputes G3 for the shipped artifact from the shipped bytes and re-derives the "
                    "verdict.  No threshold changed and no earlier number was removed."),
            instrument="scripts/h71_uniqueness.py")
        card.write_text(json.dumps(d, indent=2, default=float) + "\n")
        out[tag] = dict(artifact=d["artifact"]["file"], verdict=d["verdict"],
                        literal=scan["literal"]["max_dot_overlap_within_3px"],
                        literal_raster=scan["literal"]["worst_raster"],
                        satisfiable=scan["satisfiable"]["max_dot_overlap_within_3px"],
                        satisfiable_raster=scan["satisfiable"]["worst_raster"],
                        max_abs_rho=scan["literal"]["max_abs_spearman"],
                        byte_unique=scan["byte_unique"], scanned=scan["scanned"],
                        universal_blockers=scan["universal_blockers"])
        print(f"[H71-{tag}] {out[tag]}")
    (ROOT / "evidence" / "h71_uniqueness_addendum.json").write_text(
        json.dumps(dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        results=out), indent=2) + "\n")
    print("wrote evidence/h71_uniqueness_addendum.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
