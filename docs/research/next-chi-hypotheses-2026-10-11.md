# Ranked channel-steepness / knickpoint hypotheses — untested and deferred

**Status on 2026-10-11: UNTESTED / DEFERRED. No experiment was run from this list.** The c7653 lane's preregistered E1 first test returned `NEGATIVE-STOP` (placement-null AUC 0.22436). The standing instruction says to stop if that test fails; this backlog is not permission to continue the lane, spend a slot, or create a submission. No numerical DTI improvement can be forecast from catalogue hide-and-recover data for genuinely off-catalogue faults.

The ranking below is a **qualitative research-priority ranking** (plausible signal relative to implementation cost), not an estimated DTI lift, calibrated probability, or leaderboard projection. All items use only visible catalogue faults when defining training/holdout examples; final candidate surfaces must not use hidden truth or catalogue-derived proximity as a predictive feature.

| Priority | Untested hypothesis / expected DTI potential (qualitative only) | Cost | Why it ranks here |
|---:|---|---|---|
| 1 | **Paired-basin ksn contrast across fault blocks** — potentially high signal; very uncertain | High | Tests a block-scale tectonic response rather than another local knickpoint detector; requires valid-resolution DEM hydrology and robust paired catchment construction. |
| 2 | **Bedrock-channel confinement × ksn residual** — medium-high potential; very uncertain | High | Could identify uplift-related incision where scarps are buried, but valley-width estimates and lithologic controls need finer terrain and careful validation. |
| 3 | **Hydroclimate- and permanence-matched ksn residual** — moderate potential; uncertain | Medium–high | Directly controls precipitation/runoff and ephemeral-channel mimics that can imitate steepness steps; climate and permanence data coverage must be checked regionally. |
| 4 | **Outlet/base-level-conditioned profile residual** — moderate potential; uncertain | Medium | Separates tectonic profile anomalies from playa, closed-basin and alluvial-base-level effects; the present masks are not a basin-outlet matched design. |

## 1. Paired-basin ksn contrast across fault blocks

- **Geological hypothesis:** differential rock uplift across an active normal-fault system produces a coherent drainage-scale normalized-steepness contrast between adjacent catchments on opposite sides of the fault, even where the surface fault trace is buried or absent from the public catalogue.
- **Layers:** high-resolution bare-earth elevation from [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) to derive flow routing, drainage area, χ and segmented `ksn`; visible catalogue traces used only for training-fold crossings; mapped rock units from the [USGS State Geologic Map Compilation (SGMC)](https://mrdata.usgs.gov/geology/state/) for matching/masking; existing `depth_to_base_surf` and `cond_surf` fields as secondary sediment-cover masks, not as lithology truth.
- **Physical signature:** paired, along-strike neighboring catchments with matched drainage area, outlet class, mapped unit, cover and climate show a repeatable difference in median log-`ksn` or profile residual across the mapped fault boundary. Use a signed contrast only where fault polarity/dip attributes are actually available; otherwise preregister an unsigned magnitude statistic. Fit and compare whole catchments, not isolated pixels.
- **Why it could generalize off-catalogue:** the target is a regional channel response to differential uplift, not distance from or reconstruction of a known trace. Train only on visible catalogue segments; hold out entire fault segments and buffer their full geometry before deriving any examples.
- **What is new relative to this repository:** c7653 asks whether a local channel-steepness/knickpoint anomaly occurs at withheld segment crossings; H60A uses strike-corridor corroboration. This is a **paired catchment / block-scale contrast**, with explicit lithology, runoff, area and outlet matching, rather than local breakpoint or strike-chain detection.
- **Named non-fault mimic:** contrasts in rock erodibility across a mapped contact. Secondary mimics are orographic rainfall, alluvial thickness, basin outlet/base level and DEM-derived flow-routing errors.
- **Data status:** 3DEP is an official, free USGS source. A recorded Actions egress probe obtained and hashed a sample tile (`evidence/probe-egress-receipt.json`), but the complete 10 m coverage was **not** assembled here. SGMC is a public USGS release (DOI [10.5066/F7WH2N65](https://doi.org/10.5066/F7WH2N65)); its constituent state maps vary in scale and age, so map-unit matching is an imperfect control, not ground truth for erodibility. Existing tests on 3DEP reduced to 100 m and the official 100 m network failed the recorded Hack-exponent check; that failure is a resolution/input warning, not positive evidence for this hypothesis.

## 2. Bedrock-channel confinement × ksn residual

- **Geological hypothesis:** active uplift localizes incision in confined bedrock reaches and raises channel steepness relative to adjacent, less-confined reaches; the joint channel signal may persist where a surface scarp has degraded or is covered.
- **Layers:** 3DEP-derived channel network and 10 m (or finer where available) elevation; valley-bottom width / local relief calculated from the DEM; `ksn` and χ profiles; SGMC unit and sediment-cover fields used to stratify or exclude non-bedrock reaches.
- **Physical signature:** cross-fault channel reaches have both anomalously high, area-normalized steepness and a narrow valley-bottom / high local-relief response over more than one independent catchment, after matching channel order, drainage area, lithology and local base level. The confinement term is a channel-valley measure, not scarp curvature.
- **Why it could generalize off-catalogue:** a channel response can span a buried trace without the fault itself appearing in a line catalogue. The model would learn the relationship on visible faults and evaluate it only on fully withheld fault segments.
- **What is new:** the existing c7653/H60A systems score knickpoint steps or strike-aligned corridors; this candidate tests the *joint reach-scale incision/confinement response*. It is not H60-C divide migration, nor a scarp-shape detector.
- **Named non-fault mimic:** resistant lithology can independently narrow a valley and steepen a channel. Landslides, resistant channel beds, alluvial narrowing and DEM smoothing are additional mimics.
- **Data status:** the source is USGS 3DEP as above. The required 10 m terrain tiles are not all locally present, and 100 m terrain is too coarse for a defensible valley-width measurement. **Do not treat this as data-ready until full-resolution coverage, vertical quality and pixel/grid alignment are verified.**

## 3. Hydroclimate- and permanence-matched ksn residual

- **Geological hypothesis:** after matching runoff regime and channel permanence, a residual cross-fault steepness/knickpoint signal reflects rock-uplift or incision differences rather than aridity, orographic precipitation or ephemeral flow.
- **Layers:** χ/`ksn` and drainage attributes from valid-resolution 3DEP; 1991–2020 precipitation/temperature normals from [PRISM Climate Group](https://prism.oregonstate.edu/); current USGS [3D Hydrography Program (3DHP)](https://www.usgs.gov/3d-hydrography-program) flowlines and permanence attributes where published and populated. Existing `cond_surf` is only a proxy and should not be represented as a measured permanence class.
- **Physical signature:** compare fault-crossing and control channels within matched precipitation, temperature/elevation, contributing-area, lithology and stream-permanence strata. The held-out statistic is the residual profile-step or normalized-steepness difference, not raw channel steepness across the whole region.
- **Why it could generalize off-catalogue:** it models a tectonic residual after explicitly removing hydrologic conditions that can create non-fault steps; it does not require a candidate line to coincide with known traces.
- **What is new:** existing H60A applies blockwise normalization and masks high-conductivity / alluvial proxies; this design directly matches climate normals and observed reach permanence, variables not tested feature-by-feature in c7653.
- **Named non-fault mimic:** precipitation/runoff and intermittent or ephemeral flow. Snowmelt seasonality and vegetation/land-cover effects are additional possible mimics.
- **Data status:** PRISM's official project page describes public, free climate grids and 1991–2020 normals. This review did **not** download or validate a regional PRISM raster. USGS says the NHD was retired in 2023 and that 3DHP is the current program; 3DHP permanence attribution is still being built out. See [USGS hydrography product access](https://www.usgs.gov/national-hydrography/access-national-hydrography-products). This candidate is viable only if the relevant 3DHP coverage and permanence fields can be checked before preregistration; do not silently substitute incomplete or legacy NHD labels.

## 4. Outlet/base-level-conditioned profile residual

- **Geological hypothesis:** a fault-related channel steepness or knickpoint anomaly remains detectable after comparing reaches only within similar outlet/base-level settings and removing reaches directly controlled by playas, closed basins or thick basin fill.
- **Layers:** 3DEP-derived elevation and drainage profiles; closed-basin and playa/waterbody outlines; SGMC surficial/bedrock units; existing `depth_to_base_surf` and `cond_surf` only as declared sediment-cover proxies; visible catalogue fault segments for spatially blocked training/holdout.
- **Physical signature:** compare segmented profile residuals or `ksn` anomalies among channels matched on outlet elevation, catchment relief, basin closure, downstream alluvial length and lithology; test whether the anomaly persists upstream of the outlet-controlled reach and across separate drainages.
- **Why it could generalize off-catalogue:** removing hydrologically imposed knickpoints should leave tectonic profile departures that extend across catchments without using the catalogue to place final predictions.
- **What is new:** earlier runs apply playa/closed-basin masks and H60-B proposed equal-χ clustering. This candidate is a **basin-outlet matched control / downstream censoring design**, not another equal-χ cluster detector and not simply the prior H60-D depth-to-base contact proposal.
- **Named non-fault mimic:** playa base-level fall, alluvial-fan toe, lake-level change or internal-drainage outlet capture.
- **Data status:** 3DEP is the required elevation source; the [USGS NHD/3DHP product-access page](https://www.usgs.gov/national-hydrography/access-national-hydrography-products) lists hydrography downloads and services. Dataset currency and coverage must be verified for the footprint before use. The existing 100 m drainage products failed the recorded validity check, so no result from them is treated as a positive screening result.

## Mandatory gates if a future continuation is separately authorized

These are validation requirements, **not** permission to continue the stopped c7653 lane:

1. Keep every feature derived from permitted visible data only. Build a feature-by-feature leakage canary before combining features; any AUC above 0.90 is a leakage flag until explained and cleared.
2. Use the shared template's cached stack and shared evaluator/writer. Hide complete fault segments with buffers, preserve pixel-exact masking, and use pooled DTI with the official α=0.2, β=0.8 and 300 m triangular kernel.
3. Check uniqueness of each continuous feature/surface **before placement** and of final dots **after placement**, against the full registry: absolute surface-rank correlation ≤0.90 and no more than 70% of final dots within 3 px of a registry raster. Record coverage, checksums and comparison scope; a partial list is not clearance.
4. Compare only like-for-like HOLDOUT-DTI runs with the same evaluator, truth mask, folds and bootstrap. A family record lists 0.190147 as a best promotable local holdout value; verify exact evaluator/mask compatibility before treating that number as a direct comparator. A local holdout is not the public or private competition score.
5. A weekly slot remains off limits unless the blocked holdout beats the current best under the registered rule and all leakage, uniqueness, validator and receipt requirements pass. The c7653 negative stop remains binding for this lane.

## Manual-review sources

- [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) — elevation program and public data access.
- [USGS SGMC](https://mrdata.usgs.gov/geology/state/) · [SGMC data-release DOI](https://doi.org/10.5066/F7WH2N65) — compiled bedrock/surficial geology; map scale and source age vary.
- [PRISM Climate Group](https://prism.oregonstate.edu/) — climate datasets / normals; project page describes public free access.
- [USGS 3DHP](https://www.usgs.gov/3d-hydrography-program) · [hydrography downloads/services](https://www.usgs.gov/national-hydrography/access-national-hydrography-products) — current hydrography program and product access; stream-permanence coverage must be checked.
- [USGS NHD status](https://www.usgs.gov/national-hydrography/national-hydrography-dataset) — NHD retired 2023; still available but no longer maintained.
- [Competition problem / metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) — official evaluator constants and format.
