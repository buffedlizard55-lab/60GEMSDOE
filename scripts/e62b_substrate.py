#!/usr/bin/env python3
"""E2b: is the lane's 100 m negative a *method* result or a *substrate* result?

The lane's first test compares channel steepness across fault traces with orientation-matched
nulls.  That test can only mean anything if the D8 network on the substrate is a real drainage
network.  Two published validity diagnostics are computed for BOTH 100 m elevation products
available in this repository:

  * ``filled_raised_fraction`` -- share of interior footprint cells the Priority-Flood filler had to
    raise.  A real DEM has a tiny fraction; a noisy or under-resolved one has a large fraction.
  * ``hack_exponent_A_vs_L``  -- slope of log10(A) against log10(L) along channel cells.  Hack's law
    (Hack 1957; Rigon et al. 1996) gives A ~ L^b with b ~ 1.6-2.0 for real drainage networks, and
    b ~ 0 when flow accumulation carries no information about how far down-flow a cell is, i.e. when
    the "network" is a filling artefact.

If both products fail both diagnostics, the lane's negative verdict is a statement about 100 m
substrates, not about knickpoint physics; the fix is resolution (the brief names free 3DEP 10 m or
1 m tiles), not a new detector.

Usage: PYTHONPATH=src python3 scripts/e62b_substrate.py
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
from gems60 import surface as S      # noqa: E402  shared lane detector
from gems61 import dataio            # noqa: E402

OUT = ROOT / "evidence" / "e62b_substrate.json"


def main() -> int:
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "E62b substrate diagnostic"):
        return 0
    t0 = time.time()
    valid, cat = dataio.load_footprint_and_labels()
    dems = {
        "3dep_10m_reduced_to_100m": dataio.dequantise_u8(
            ROOT / "data/external/topo_10m_derived_100m_u8.tif", 9),
        "official_det_elev_100m": dataio.read_band(ROOT / "data/training_features.tif", band=12),
    }
    rep = {"experiment": "E2b substrate validity for the chi/ksn lane",
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "citation": "Hack (1957) USGS Prof. Paper 294-B; Rigon et al. (1996) Water Resources "
                       "Research 32, 3189-3194 (b ~ 1.6-2.0 for real networks)",
           "products": {}}
    channels = {}
    for name, dem in dems.items():
        z = np.where(valid & np.isfinite(dem), dem, np.nan)
        z = np.where(valid, np.nan_to_num(z, nan=float(np.nanmedian(z))), np.nan)
        fields = S.build(z, valid, cell_m=100.0, theta=0.45, ac_m2=1.0e6, knick_window=4,
                         knick_ratio=1.6, min_drop_m=20.0, corridor_px=12, azimuth_bins=18)
        st = fields["stats"]
        rep["products"][name] = {
            "sha256_of_source": dataio.sha256(ROOT / ("data/external/topo_10m_derived_100m_u8.tif"
                                                      if "3dep" in name else "data/training_features.tif")),
            "filled_raised_fraction": st["filled_raised_fraction"],
            "hack_exponent_A_vs_L": st["hack_exponent_A_vs_L"],
            "n_channel_px": st["n_channel_px"], "n_links_first_order": st["n_links"],
            "n_knickpoints": st["n_knickpoints"], "flow_distance_max_km": st["flow_distance_max_km"],
            "acc_max_px": st["acc_max_px"], "acc_median_channel_px": st["acc_median_channel_px"],
        }
        channels[name] = fields["channel"]
        print(f"{name}: {json.dumps(rep['products'][name], default=str)[:400]}", flush=True)
    a, b = list(channels.values())
    inter = int((a & b).sum())
    rep["channel_network_agreement"] = {
        "px_in_both": inter, "union": int((a | b).sum()),
        "jaccard": round(inter / max(1, int((a | b).sum())), 4),
        "interpretation": "independent 100 m elevation products agreeing on the channel network is "
                          "what would license treating the network as data rather than artefacts"}
    rep["seconds"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(rep, indent=1) + "\n")
    print("wrote", OUT, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
