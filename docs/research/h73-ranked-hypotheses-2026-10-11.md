# H73 pre-implementation review — ranked channel-steepness hypotheses

**Written before H73 measurements.** Ranking is qualitative; no DTI lift is projected. This project stays in the tectonic-geomorphology lane: channel steepness, χ-profile breaks and knickpoints—not scarp-shape detection. “Missing fault” means absent from the competition’s provided fault raster, not absent from every public map.

| rank | candidate (layers) | physical signature | why it can find a catalogue-missing fault | difference from this repository | expected potential / cost |
|---:|---|---|---|---|---|
| **1** | **Paired-basin `ksn` contrast with persistent knickpoint support** (`dem10_chi_100m_i16`: `ksn_max`, `step_max`; `sig_i32`: 500 m downstream pointer; `u8`: channel/raised counts; GeoDAWN K/Th) | A block-scale gradient in drainage-area-normalized channel steepness, supported by positive upstream `Δksn`, that repeats in ≥3 independent drainages along strike. | Differential uplift can alter whole transverse channel profiles even if alluvium buries the trace. The detector is derived without the fault catalogue; visible faults supply fold-specific strike context only. | H65/H66/H68 score local steps plus a piedmont/scarp proxy; H70 pairs opposite-polarity steps on one branch. H73 tests a **smoothed cross-basin `log(1+ksn)` gradient** and requires both catalogue-withheld and SGMC-off-catalogue gates. | high / medium; all required reduced data are committed and hash-pinned. |
| 2 | **Multi-distance profile-step persistence** (same 3DEP χ reduction and downstream pointers) | A same-sign `ksn` step persists at 0.5, 1.0 and 1.5 km downstream instead of appearing as a one-window spike. | A base-level/uplift step should persist over a reach; boulders and routing noise should decorrelate with distance. | H70 requires opposite polarities at one fixed separation; no repository run tests same-sign persistence at multiple separations. | medium-high / medium; viable with committed pointers, but repeated pointers need a dedicated cache. |
| 3 | **Outlet/base-level-conditioned χ residual** (3DEP χ/`ksn`, `raised_n`, elevation, official closed-basin/playa boundaries) | Profile residuals are compared only among channels with the same outlet class and censored downstream alluvial length. | Suppressing playa and pluvial-base-level knickpoints should leave buried range-front tectonic steps. | Existing runs mask high `raised_n`; none constructs matched outlet classes. | medium / medium-high; the committed `raised_n` proxy is available, but authoritative lake/playa polygons should come from USGS National Hydrography Dataset/3DHP before full implementation. |
| 4 | **Bedrock-channel confinement × `ksn` residual** (native 3DEP DEM, valley-width transform, SGMC units) | High residual `ksn` co-occurs with narrow bedrock valleys in several adjacent drainages. | Incision/confinement can remain after the fault scarp degrades. | No current lane run measures channel-valley width; H68’s LiDAR bands are scarp/piedmont features and are not this transform. | medium / high; requires re-fetching the pinned native 10 m tiles and validating valley widths before it is viable. |
| 5 | **Hydroclimate/permanence-matched `ksn` residual** (PRISM 1991–2020 normals, USGS 3DHP permanence, 3DEP χ/`ksn`) | Residual steepness after matching precipitation, elevation, drainage area and stream permanence. | It directly removes regional climate and ephemeral-channel mimics without requiring a known trace. | Existing runs use 40 km block normalization and a `ksn<10` wash mask, not observed climate/permanence strata. | medium / high; viable only after regional PRISM/3DHP coverage and attribution are downloaded and audited. |

## Top-candidate decision

H73 implements candidate 1 because every required raster is already committed, the 3DEP reduction manifest pins all source hashes, and H70’s preregistered non-gating SGMC-off-catalogue test was positive for a related paired signal. That H70 observation motivates the test; it does **not** count as H73 validation. H73’s two populations are gated before seeing its statistic:

1. catalogue-withheld segments versus random same-orientation transects; and
2. SGMC traces more than 300 m from the competition catalogue versus matched random transects.

Both 95% confidence-interval lower bounds must exceed zero. The feature-alone leakage canary must remain ≤0.90. The pooled hide-and-recover DTI must beat the recorded H68 lane best (0.171894) before the file can be recommended for a weekly slot. A generated file remains a negative research artifact if any promotion gate fails.

## Official/source links for manual review

- USGS 3DEP: https://www.usgs.gov/3d-elevation-program
- USGS State Geologic Map Compilation (SGMC): https://mrdata.usgs.gov/geology/state/ and DOI https://doi.org/10.5066/F7WH2N65
- USGS GeoDAWN survey: https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and
- USGS 3D Hydrography Program: https://www.usgs.gov/3d-hydrography-program
- PRISM Climate Group: https://prism.oregonstate.edu/
- Kirby & Whipple (2012): https://doi.org/10.1016/j.jsg.2012.07.009
- Perron & Royden (2013): https://doi.org/10.1002/esp.3302
- Gailleton et al. (2019): https://doi.org/10.5194/esurf-7-211-2019

## Obtainability and limitations

- **Available now:** the 18-tile 3DEP reduction, topo reduction, LiDAR-derived pack, GeoDAWN radiometrics, SGMC fault raster, competition labels and sample grid are committed. `data/external/dem10_chi_100m.manifest.json` records the official 3DEP URLs, byte counts and SHA-256 pins.
- **Not available in this sandbox:** native ~10 m tiles (~6.7 GB), PRISM normals, a verified 3DHP permanence layer, and SGMC map-unit polygons. Candidate 1 does not require those downloads. Candidate 4 or 5 must not be represented as validated until those inputs are obtained from their official sources.
- **Confound limitation:** H73 masks radiometric contact gradients, low-`ksn` ephemeral washes and raised/playa cells and uses 40 km standardization, but these are proxies—not direct lithologic erodibility, precipitation or permanence observations.
