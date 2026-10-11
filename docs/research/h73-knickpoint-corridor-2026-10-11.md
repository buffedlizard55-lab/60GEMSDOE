# H73 — amplitude-coherent χ/k_sn corridor knickpoints, and the instrument that flattered them

Session `arena/7f9ca816-60gemsdoe`, 2026-10-11. Lane: tectonic geomorphology (channel steepness, knickpoints,
χ transform) — *not* scarp curvature. Every number below is copied from an evidence file named in the last column;
nothing is quoted from memory. Classes: **MEASUREMENT** (byte-measured here), **HOLDOUT-DTI** (protocol instrument,
conditional), **INSTRUMENT** (public proxy truth, never a score), **MODEL** (arithmetic on published quantities).

## 1. The question the brief asks, answered

> First test: do channels crossing withheld segments show larger steepness steps than random lines of the same
> orientation? If not, stop.

**Answer for the H73 statistic: yes, and the gate passes.** Withheld-segment corridor-amplitude contrast
**+0.203394**, 95 % CI **[+0.078017, +0.335036]**, n = 196 components, 10 same-orientation random transects per
component, 3 px crossing zone, 40 km blockwise de-trend, and the brief's confound masks (playa, clay/alluvial
radiometric cover, ephemeral wash k_sn < 10) applied to *both* arms (the IR-66-E1MASK-01 fix is inherited).
MEASUREMENT — `evidence/h73_e1_first_test.json`.

Two published caveats, not buried: the **median** contrast is −0.044143 and only **47.96 %** of components are
positive, so the effect is a right-skewed minority of strong corridors, not a uniform shift; and this is the
*catalogue-withheld* population, which the family's own audits show ranks live files backwards (§5).

For context, every earlier attempt at this lane's first test: H65-1 raw log-ratio +0.0326 [−0.0144, +0.0790]
(INCONCLUSIVE → the standing STOP); H66-6 masked +0.0404 [−0.0029, +0.0871]; H68-1 composite (Δksn + piedmont
curvature + LiDAR) +0.4502 [0.2510, 0.6491]; H70-1 paired-polarity −0.0347 [−0.0853, +0.0126]. H73 is the first run whose
statistic is the lane's own (corridor-amplitude χ/k_sn evidence, no curvature, no LiDAR) *and* that clears CI > 0.

## 2. What the field is (method, reproducible)

`scripts/run_h73.py --stage a`, 16 s, from the committed pinned reduction of the public-domain USGS 3DEP
1/3-arc-second DEM (18 tiles, sha256 in `data/external/dem10_chi_100m.manifest.json`):

1. per 100 m cell, recover the 10 m bedrock-channel steepness step `Δk_sn` from `step_max` and `ksn_max`
   (the H66/H68 shared recovery, `k_u`, `k_d = (k_u+0.5)·e^(−step) − 0.5`, log1p asymmetry);
2. keep cells with |Δk_sn| ≥ ln 1.25 = 0.223144 → **707,318** step-bearing cells of 786,299 channel cells
   (599,753 bedrock after the k_sn ≥ 10 wash filter);
3. **Radon-style corridor test**, 12 strikes × 2 half-bin staggers: bin cells across strike into 300 m corridors
   and along strike into 1 km bins; a corridor bin is retained only if it holds ≥3 step cells from **≥3 distinct
   drainages** (drainage identity = the pinned 10 m branch signature 500 m downstream), with **signed-polarity
   consistency ≥ 0.8** and amplitude **coefficient of variation ≤ 1.2**, and only if it sits inside a run of ≥3
   consecutive along-strike bins (≥2–3 km of persistence). Weight = mean |Δk_sn| × e^−CV × polarity;
4. per cell, the maximum over the 24 corridor orientations → **520,731 cells** survive the coherence test.

Why each piece is there: a base-level step thrown by one structure is recorded by every drainage that crosses it at
comparable magnitude, whereas a lithologic contact or a playa margin produces *incoherent* or *single-drainage*
steps. Amplitude coherence + polarity consistency is the discriminator; strike persistence is the scale filter that
removes isolated knickpoint noise. This is Kirby & Whipple's (2012) spatial-gradient argument and Perron & Royden's
(2013) comparability argument implemented as a testable statistic, with the segmentation discipline of Gailleton
et al. (2019, ESurf 7:211–230).

## 3. Emission, and the metric's own economics

Production domain (preregistered): footprint ∧ corridor-score > 0 ∧ >200 m from the mapped catalogue ∧ within 500 m
of an SGMC state-map trace that the Quaternary catalogue omits → 51,552 px, of which the 3.0 px NMS order holds
**12,204** dots (IR-73-MASSCAP-01: the 20k/30k/40k ladder arms could not be emitted).
Ranking key = **within-relief-quintile percentile** of the corridor score, which makes emitted mass proportional to
footprint area in each relief stratum — the instrument repair the registry ranked #1 and no earlier session
implemented. Realized stratum shares vs footprint shares: `evidence/h73_emission.json → relief_share_by_stratum`.

Selected arm by the preregistered economics rule (largest mass whose credit per dot ≥ the champion's measured
0.145568 on the same instrument): **lane_h73_12000**, credit/dot **0.670401**, proxy DTI 0.151384.

## 4. The finding that matters most: the flattering instrument is circular

INSTRUMENT — 12,000-dot arms scored against SGMC traces > 300 m off the catalogue (62,226 px)
(`evidence/h73_controls.json`, `scripts/h73_controls.py`):

| arm | credit per dot | what it isolates |
|---|---|---|
| uniform random over the footprint | 0.108646 | chance on the map |
| champion `h33-h33-2-b2` (37,654 dots) | 0.145568 | the family's live 0.2778 file |
| random **inside the H73 domain** | 0.566749 | the domain alone |
| **H73 lane-ranked inside the domain** | **0.670401** | domain + χ/k_sn ranking |
| random scatter on the off-catalogue corridor itself, no NMS/relief rules | 0.842515 | the corridor, maximally |

The instrument's truth set *is* the structure the domain mask was built from. So the confined arm's 4.6× edge over
the champion is arithmetic, not skill: the χ/k_sn ranking contributes **+0.103652** credit/dot over chance in the
same corridor, and pure corridor scatter beats the whole lane recipe. Stripped of the circular prior, the lane field
alone measures **0.120438** credit/dot (`evidence/h73_purelane_package.json`) — i.e. **below the champion**, exactly
as the eight earlier negative lane runs said. Logged as **IR-73-INSTR-CIRCULAR-01**.

## 5. The mandated instrument, reported as required

HOLDOUT-DTI, evaluator `gems57-pooled-hide-v2`, 8 cells, 22,641 withheld positives, α 0.2, β 0.8, 300 m triangular
kernel, 1,000 paired 20 km spatial-block bootstrap draws (seed 73001), mass basis identical to the recorded lane
table (`evidence/h73_holdout_prior.json`):

| arm | HOLDOUT-DTI | 95 % CI |
|---|---|---|
| lane_h73 (pure corridor ranking) | 0.053231 | [0.047186, 0.059637] |
| lane_h73, SGMC-confined (= shipped file's rule) | 0.064218 | [0.054156, 0.074476] |
| k_sn only, no alignment | 0.019806 | [0.016197, 0.023738] |
| mass-matched uniform random | 0.038590 | [0.035215, 0.041650] |
| distance-to-visible-catalogue control | 0.190730 | [0.181280, 0.199795] |

Paired: confined arm − random **+0.025628**, pure lane − random **+0.014641** [0.008830, 0.020774] (positive,
significant); lane arms are 2.7–3.2× their own k_sn-only ablation, which is the evidence that the *alignment and
coherence* filters do something on the catalogue population. The `distance_only` control at 0.190730 reproduces
H68-1's published 0.190730 to the last digit — the shared instrument is intact.

At production mass (12,000 total rather than the prior 40k basis): 0.013331 confined, 0.004697 pure, 0.002995
random (`evidence/h73_holdout.json`).

Leakage canaries, each feature alone (same file): corridor 0.6077, Δk_sn 0.6210, k_sn 0.6416, relief 0.5973,
SGMC-off mask 0.7387 — all < 0.90; the deliberate positive control `dist_to_visible` 0.9243 is not an input.

## 6. Uniqueness, and a gate that cannot be passed

REGISTRY-MEASUREMENT, 78 locally available rasters scanned (`evidence/h73_uniqueness.json`):
max |Spearman| against my *surface* 0.19409 (gate 0.90) → pass. Like-for-like dot overlap: max
0.349333 vs `h71b-convcomp-12000`, 0.331583 vs H68-1, 0.27725 vs H66-1, 0.153167 vs the c7653 lane file,
0.0515 vs H65-1 (gate 0.70) → pass: this file is not another lane's file.

The literal reading also names three comparators above 0.70 (0.999083, 0.86175, 0.778417). Those three are
space-filling lattice/calibration rasters, and the *live-scored champion* measures 0.99915, 0.88883, 0.771897
against them (`evidence/h73_dense_comparator_universality.json`) — as do H65-1 and H68-1. The clause is a property
of that registry, not of this candidate: no non-empty dot file in this footprint can satisfy it
(IR-73-GATE-UNSAT-01). Both readings are published; no exception is claimed.

## 7. Verdict and the operator's decision

* Physics gate: **PROCEED** (first time for the lane's own statistic).
* Field-quality claim beyond the structural prior: **not supported** — the lane alone is 0.120438 credit/dot, below
  the champion's 0.145568; the apparent advantage is instrument circularity.
* promotable-holdout gate (0.190147): **not met** (0.064218).
* Format/uniqueness/leakage: **met**.
* Shipped: `gems60-h73-chi-coherent-corridor-12000-20261011T195818Z-zeros.tif`,
  sha256 `7fcf455c549598be9002acdc2c0370f232e11616d1ea21cb84f96d8af82ab971`, 12,000 dots, validator 15/15,
  0 NaN, all values in [0, 1], 0 dots on the mapped catalogue. Plus the conservative pure-lane file, research only.
* MODEL (never a score): non-circular transfer ⇒ ≈0.10; if the panel verifies even a subset of the off-catalogue
  state-map structures the file sits between 0.1 and ~0.3 at a denominator cost of 2,400 units versus the
  champion's 7,531, so the *downside per slot is bounded and the information value is high*. That, not a score
  claim, is the argument for spending one weekly slot on it.

## 8. Ranked candidate hypotheses after H73 (3–5, with cost and data feasibility)

| # | hypothesis | layer(s) / signature | why it can see a fault the catalogue misses | differs from everything in this repo by | expected ΔDTI | cost |
|---|---|---|---|---|---|---|
| **H74** | hydrothermal outflow lineations: straight alignments of GDR spring/well points (≥5 sources, ≥2 km, ≥300 m off catalogue) | `data/external/gdr_wellspring_in_footprint.csv` (27,092 rows, already row/col georeferenced) — Radon linearity of a *point pattern*, not a raster transform | spring/well damage-zone permeability does not require a scarp, a Quaternary unit, or a visible offset; degraded or buried strands still leak | thermal data was used only as a *multiplicative corroboration* of the lane field (`evidence/e62_lane_thermal.json`, +0.00019) — never as an independent trace estimator | unknown; testable offline on both instruments in ~25 min | LOW — all data local |
| **H75** | break the circularity: off-catalogue corridors with a **split-map** instrument (build the domain from SGMC traces of one 1:750k sheet, score against another sheet's traces) + widen 500 m → 1 km to lift the 12,204-dot mass cap | same DEM stack + `sgmc_faults_100m.tif` | not a new geology claim — it converts today's PASS-but-void gate into a measurement, which is what every future candidate is graded on | no session has ever separated "domain" from "ranking" on a truth set disjoint from the domain | ~0 directly; unblocks everything | LOW (20–30 min) |
| **H76** | basement-step detection in up-continued magnetics: along-strike discontinuity in `TMI_up150` after 40 km de-trend, required to coincide with a DEM basement-surface step in cells where cover is thick | `data/external/geodawn_extensions_u8.tif` band 4 + `depth_to_base_surf` where the 19-band stack is available | where alluvium or volcanic cover buries the strand, optical/scarp methods are blind by construction, but the magnetic fabric of the basement is offset | GEMSDOE40/45 clustered *Euler depths of magnetic lineaments*; this tests *offsets across strike of a continuous de-trended surface*, and gates on cover thickness | medium; magnetics-driven files scored 0.0355–0.0984 in this family | MEDIUM |
| H77 | isochronous palaeo-shoreline/playa-highstand datums stepped across strike | needs Quaternary unit polygons (SGMC "units" pack) — **obtainability not verified from this sandbox** (egress allowlist has no `mrdata.usgs.gov`) | an isochronous datum offset is a fault measurement even where the fault never ruptures the modern surface | nothing in the family uses isochronous surfaces | — | blocked: verify the free official source first, then MEDIUM |
| H78 | seismicity lineations + geodetic strain-rate (ComCat / GeoNET) | hypocentre clusters ≥ ML 1.5, focal-plane azimuth coherence | active strain localizes on strands with no surface expression at all | `scripts/fetch_earthquake_catalog.sh` exists but no session has ever used the catalog as a *lineation* estimator | possibly high | blocked by egress: `earthquake.usgs.gov` is not reachable here → not viable as a proposal until a run on an unrestricted machine confirms fetchability |

Ranked by expected information per unit cost: **H75 > H74 > H76** (H75 first because every promotion decision in
this project currently rests on an instrument we have just proved circular for confined candidates). H77/H78 are
named with their data sources and are *not* proposed as viable until fetchability is confirmed, per the brief.

## 9. Sources for manual review (official)

* Metric, submission format, worked example: <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>
* Leaderboard (public rows): <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>
* Rules PDF (OSTI/NLR 96647, DOI 10.2172/3818146): <https://docs.nlr.gov/docs/fy26osti/96647.pdf>
* Reference solution (all-finite writer, no nodata tag): <https://github.com/drivendataorg/gems-prize-reference-solution>
* Known-fault masking during scoring (staff answer): <https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516>
* USGS 3DEP 10 m (public domain): <https://www.usgs.gov/3d-elevation-program>; tiles
  `https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/` (18 tiles sha256-pinned in
  `data/external/dem10_chi_100m.manifest.json`)
* GeoDAWN airborne magnetics/radiometrics: <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>
  (DOI <https://doi.org/10.5066/P93LGLVQ>)
* INGENIOUS springs/wells/geothermometry (GDR 1391): <https://gdr.openei.org/submissions/1391> · project page
  <https://gbcge.org/current-projects/ingenious/>
* USGS State Geologic Map Compilation (faults, 1:750k): <https://mrdata.usgs.gov/geology/state/>
* Kirby & Whipple 2012, *J. Struct. Geol.* 44:54–75: <https://doi.org/10.1016/j.jsg.2012.07.009>
* Perron & Royden 2013, *ESPL* 38:570–576 (χ): <https://doi.org/10.1002/esp.3302>
* Gailleton et al. 2019, *ESurf* 7:211–230 (knickpoint segmentation): <https://doi.org/10.5194/esurf-7-211-2019>
* Willett et al. 2014, *Science* 343:1126 (divide migration): <https://doi.org/10.1126/science.1248765>
* Forte & Whipple 2018, *EPSL* 493:102–117: <https://doi.org/10.1016/j.epsl.2018.04.026>
* CRS EPSG:32611: <https://epsg.io/32611> · Tversky index background: <https://en.wikipedia.org/wiki/Tversky_index>
