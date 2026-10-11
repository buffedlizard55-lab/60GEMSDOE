# H73 result and the 0.2778 H33 question

## Executive answer

The project cannot honestly claim that `h33-h33-2-b2` **organizer-confirmedly** scored 0.2778: the repository has no submission-page receipt linking that exact score to exact TIFF bytes. It is an **owner-reported / unverified** score claim. A manual 2026-10-11 public-board snapshot contains a participant row at 0.2778, but a public row does not identify a file. This distinction is recorded in `registry/current_site_status.json`, `registry/leaderboard_snapshot_2026-10-11.json` and `registry/irregularities.json` (`IR-32-SCORE-01`).

Conditional on the owner report being correct, H33-2-B2’s advantage is best explained by **emission economics on an already useful multi-physics field**, not by a new tectonic detector. The file emits 37,654 unit-valued cells. The earlier 0.2600 anchor emits about 44,090. Under the competition’s asymmetric Tversky metric (`alpha=0.2`, `beta=0.8`, 300 m triangular matching), removing low-credit mass can increase score because a false-positive unit costs `alpha=0.2`, while truth missed entirely costs `beta=0.8`. The repository’s measured removal ladder reports gains when catalogue-flank shells are removed. The H70 forensic inversion gives mean realised credit per emitted H33 cell 0.1022 versus 0.0893 for the 0.2600 anchor—about 14% greater credit at about 15% less mass. These are algebraic/instrument measurements, not organizer scores.

Could a new submission score above 0.2778? **Yes in principle, but this session did not validate one.** Repacking the same field is unlikely to close the gap to the current public leader. At H33’s 37,654-cell mass, the repository’s score-identity calculation says 0.4133 would require about 0.1522 realised credit per cell—roughly 49% above H33’s inferred 0.1022. That requires a materially better off-catalogue physical signal, not another small thinning change. H73 tested one such signal and returned negative.

## What H73 tested

H73’s top-ranked new hypothesis was a **paired-basin `ksn` contrast**:

- `log(1+ksn)` from the pinned USGS 3DEP ~10 m reduction was Gaussian ratio-smoothed over 800 m;
- the horizontal gradient measured high/low channel-steepness contrast across neighboring basins;
- positive upstream `Δksn` supplied local knickpoint support;
- candidates were required to align across at least three independent drainage branch signatures along visible-fault strike;
- low-`ksn` ephemeral channels, raised/playa cells and high K/Th radiometric contact gradients were masked;
- 40 km block standardization reduced broad regional gradients.

The implementation was fixed in `registry/preregistration-h73.json` before measurement and used the shared `gems57-pooled-hide-v2` evaluator and fail-closed writer.

## Results, with evidence class

| measurement | result | decision |
|---|---:|---|
| Catalogue-withheld same-orientation first test | **MEASUREMENT** +0.2841, 95% CI [+0.1439,+0.4205], n=186 | PROCEED |
| SGMC >300 m off-catalogue first test | **MEASUREMENT** −0.2909, 95% CI [−0.4757,−0.0947], n=70 | STOP under H73’s preregistered dual gate |
| H73 pooled score | **HOLDOUT-DTI** (`gems57-pooled-hide-v2`, 22,641 withheld positives) 0.085263, 95% CI [0.074915,0.096019] | below H68 0.171894; promotion gate failed |
| Matched distance-only control | **HOLDOUT-DTI** 0.086846, 95% CI [0.081937,0.091950] | H73 −0.001582, paired CI [−0.012609,+0.010218] |
| Matched random control | **HOLDOUT-DTI** 0.022822, 95% CI [0.020320,0.025282] | H73 +0.062441, paired CI [+0.052208,+0.073755] |
| Leakage canary | geological max AUC 0.6627; lane surface max AUC 0.6523 | PASS; deliberate distance positive control AUC 0.9085 is flagged and is not a geological feature |

Interpretation: the basin contrast recovers withheld active catalogue segments better than random geography, but it does not transfer to the mapped-off-catalogue SGMC population and does not beat a continuation-only control. The SGMC population itself is an imperfect target because it contains many old/inactive or contact-like traces; the dual gate was nevertheless fixed before measurement and cannot be discarded after seeing the sign flip.

## New GeoTIFF and uniqueness result

A newly computed TIFF was generated because the owner explicitly required a new artifact even if promotion failed:

- file: `gems60-h73-paired-basin-ksn-20000-20261011T200117Z-zeros.tif`
- SHA-256: `594e05573e5aca3e661ac48c71e27edc7dbe8030777992e60068a4b368903cb3`
- exact byte and decoded-array uniqueness: no match in 680 checked unique-SHA rasters
- exact full-footprint max |Spearman|: 0.1561 ≤ 0.90
- literal 3-pixel overlap: 1.000 > 0.70
- verdict: **negative / DO NOT SUBMIT**

The overlap failure is not hidden. The complete 655-raster pinned corpus contains multiple continuous rasters that are positive on every one of the 5,167,373 footprint cells. Under the repository’s literal definition `dot = value > 0`, every non-empty candidate has overlap 1.0 with those rasters. H73 therefore logs DUPLICATE-STOP even though its values and bytes are new. This is `IR-H73-LITERAL-OVERLAP-UNSAT-01`; no dense-field exception is invented.

## Three-pass review

1. **Implementation pass:** preregistered five hypotheses and H73’s parameters; built features; ran both first tests, canaries, pooled holdout and shared writer.
2. **Bug/edge pass:** expanded uniqueness from the local 76-raster set to all 655 pinned rasters; recovered four deleted-at-HEAD blobs by their Git object IDs; verified all 655 SHA-256 values; added 25 later local unique-SHA files; computed exact—not sampled—full-footprint rank correlation.
3. **Requirement pass:** re-read the final TIFF from disk; verified one band, float32, EPSG:32611, shape 3730×3292, transform `(100,0,243350,0,-100,4508550)`, all finite in [0,1], zero outside the footprint and zero on mapped catalogue cells. Added the one-click download, ≤140-character note, run card and explicit DO NOT SUBMIT decision to the site and README.

## Trusted links for manual review

- Competition overview/rules: https://www.drivendata.org/competitions/306/competition-doe-gems/
- Competition problem/metric: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
- Official reference solution: https://github.com/drivendataorg/gems-prize-reference-solution
- USGS 3DEP: https://www.usgs.gov/3d-elevation-program
- USGS GeoDAWN survey: https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and
- USGS SGMC: https://mrdata.usgs.gov/geology/state/ and https://doi.org/10.5066/F7WH2N65
- Kirby & Whipple (2012): https://doi.org/10.1016/j.jsg.2012.07.009
- Perron & Royden (2013): https://doi.org/10.1002/esp.3302
- Gailleton et al. (2019): https://doi.org/10.5194/esurf-7-211-2019

## Limitations and next work

- No DrivenData credentials or submission-page receipt are available in the repository, so the agent did not upload a file or spend a weekly slot.
- The full native 3DEP tiles, PRISM normals, 3DHP permanence and SGMC map-unit polygons are not present. H73 uses committed reductions and radiometric proxies; it does not claim direct climate/permanence/erodibility control.
- The literal overlap rule must be clarified prospectively. Keeping `value>0` as “dot” while retaining full-support continuous comparator rasters means no non-empty candidate can ever pass. A scientifically defensible future rule would compare like representations or threshold continuous fields before overlap—but changing that rule is an owner/protocol decision, not something this run does post hoc.
- The next geological experiment should not be a tuned H73 variant. Candidate 2 (multi-distance same-sign profile persistence) should be independently preregistered and should retain the catalogue-withheld test; whether SGMC remains a hard gate should be decided before any measurement, given the now-documented population mismatch.
