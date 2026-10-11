# Active-lane review — 11 October 2026

## Executive decision

**The channel-steepness / χ / knickpoint lane is STOPPED. The latest recorded run is H65-1; c7653 is historical.** H65-1's preregistered first test was **INCONCLUSIVE**, not a positive result: the mean log-ksn step contrast for withheld-segment crossings versus same-orientation random transects was +0.03259 (95% CI [−0.01435, +0.07900]), median −0.00916, and 47.3% of 262 components were positive. The confidence interval crosses zero, so the preregistered PROCEED condition was not met. Per the written “if not, stop” rule, that is **INCONCLUSIVE → STOP**. The H65 report explicitly says not to rerun the knickpoint lane at any resolution. This integration/review ran no experiment, created no TIFF, and used no submission slot.

The existing [H65-1 GeoTIFF](../downloads/gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif) is **OK to download for research only; NOT OK to submit**. Its SHA-256 is `0728d1193d9ee9f31e800ea8f9167058a409e5e17bdb24c1127ae94f3225375e`. The local receipt reports one-band float32, EPSG:32611, 3292×3730 on the 100 m submission grid, finite values in [0,1], 40,000 positive cells and no listed validation problems. This is only local format/range preflight—not organizer acceptance, uniqueness clearance or slot approval. The run-card name is `60GEMSDOE-H65-1-DEM10-KNICK-40000`; the receipt has a separate filename id `gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b`. The 116-character artifact note is in the [final H65-1 JSON run card](../../evidence/h65_runcard.json). No organizer upload receipt or competition score is recorded for this TIFF.

H65-1 also **does not pass the user's raw uniqueness gate**. Its final-dot 3-px overlap reaches 1.00 against the 0.70 limit, and the pinned inventory scan checked 651/655 rasters. The byte/pixel-unique flags apply only to the checked items. A random-support-density diagnostic helps interpret the dense-raster overlap, but it does not waive the literal gate; the tool verdict is `unique=false`. A separate pre-placement score-surface rank-correlation check is not documented in the final record. Do not call the raster uniqueness-cleared.

The earlier `c7653` run is also a negative stop, not a fallback. Its first-test AUCs were 0.22436 (placement null) and 0.25641 (orientation-matched null), with diagnostic HOLDOUT-DTI 0.00213750 [0.00179003, 0.00251341]. Its feature-by-feature canary and full pre-/post-placement registry uniqueness review were not established. Neither run clears a submission slot.

## Latest evidence: H65-1

The full [H65-1 report](../h65-report.html), [runcard](../../evidence/h65_runcard.json), [first-test measurement](../../evidence/h65_e1_first_test.json), [holdout evidence](../../evidence/h65_holdout.json), [registry comparison](../../evidence/h65_uniqueness.json), and [overlap-control diagnostic](../../evidence/h65_overlap_control.json) are preserved from the already-recorded upstream run. They were not regenerated in this review.

### Preregistered test and diagnostic holdout

- First test: withheld-segment channel steepness-step contrast versus random transects matched by orientation; 262 components; mean +0.032591, median −0.009159, 95% CI [−0.014354, +0.078995], fraction positive 0.4733. **INCONCLUSIVE; does not pass PROCEED; STOP.**
- Diagnostic **HOLDOUT-DTI**: **0.01158**, 95% CI **[0.00840, 0.01462]**, 22,641 withheld positives, evaluator `gems57-pooled-hide-v2`. The random-mass control is 0.03908 [0.03568, 0.04231]; the ksn-only control is 0.01928 [0.01532, 0.02314]. The lane's holdout is below both. This conditional catalogue hide-and-recover result is not a public leaderboard or organizer score.
- The current 3DEP source stack consists of 18 pinned 1/3-arc-second (~10 m) tiles and covers 5,167,373/5,167,373 footprint pixels. The candidate is aligned to the 100 m competition grid. Full footprint coverage did not rescue the first-test rule.

### Confounds, feature canaries, and uniqueness

The named non-fault mimics are resistant-over-weak lithologic contacts, transient knickpoints detached from their source, channel-head/colluvial-to-fluvial transitions near the area threshold, and playa/pluvial-shoreline base levels. The runcard reports only weak enrichment of selected steps near mapped faults (within-300-m share divided by footprint share: 1.19 for steps ≥ ln 2 and 1.04 for knickpoints); step-defined channels sit at median local relief −16 m versus +7 m for the catalogue. This is evidence against assuming that the extracted steps are fault signals. The run records playa/basin-related exclusions, but does **not** establish a complete independent SGMC lithology, PRISM climate, or current 3DHP stream-permanence confound analysis. USGS says legacy NHD is retired; do not describe an old NHD layer as current 3DHP.

The feature-by-feature leakage canary records all four lane inputs below the 0.90 threshold under `max(AUC, 1−AUC)`: `knickpoint_step` 0.517, `ksn` 0.5134, `drainage_area` 0.5179, and `lane_p` 0.5167. The deliberate `dist_to_visible` positive control is 0.9243 and is not a lane input. This later H65-1 audit does not retroactively clear c7653.

Registry check: 651/655 pinned grid rasters checked (four unavailable items are recorded under `IR-60-CORPUS-01`); max reported absolute full-footprint Spearman is 0.0282; maximum final-dot within-3-px overlap is 1.00; the tool verdict remains `unique=false`. The [overlap-control study](../../evidence/h65_overlap_control.json) found that dense-support random controls also trip the literal overlap clause, but the registered ≤70% limit still fails. Byte uniqueness and pixel uniqueness are true only among the checked subset; complete registry coverage and pre-placement score-surface screening are not cleared.

The H65 runcard also records `IR-65-CACHE-01`: a scratch cache found after the run differed from its recorded hash; rebuilding from the SHA-pinned source TIFs matched all 11 feature arrays and reproduced the shipped raster. The cause of the stale scratch cache is unknown. The rebuilt reproducibility check does not change the STOP verdict.

## Earlier result: c7653

The preregistered first test is in [`evidence/e1_lane_test.json`](../../evidence/e1_lane_test.json), with its historical card in [`evidence/runcard.json`](../../evidence/runcard.json): 78 withheld segments; 5,683 withheld pixels; placement-null AUC **0.22436**; orientation-matched AUC **0.25641**; verdict **NEGATIVE-STOP**. Diagnostic pooled **HOLDOUT-DTI** was **0.00213750**, 95% CI **[0.00179003, 0.00251341]**, 36,414 withheld positives, evaluator `gems52-pooled-hide-v1`. This uses catalogue-derived truth and cannot score genuinely off-catalogue discoveries.

The c7653 card listed six comparisons only. Its reported Spearman values compare final binary-dot masks, not the pre-placement continuous score surface; six post-placement overlaps and incomplete raster coverage do not establish full-registry uniqueness. The old 0.50145 “AUC” was `(Spearman rho + 1) / 2` (implied rho 0.0029023), not ROC AUC, and no per-feature leakage table is recorded. These are unresolved audit gaps, not reasons to continue after the negative first test.

H60A is a separate historical run. It had a positive first test on its own instrument but later failed its holdout and uniqueness gates. Do not pool it with c7653 or H65-1, and do not use it to override either stop. H61/H62/H63 and their research TIFFs are archived results, not current candidates.

## H33-2-B2: what the reported 0.2778 does and does not establish

The score remains **OWNER-REPORTED / UNVERIFIED**. The local evidence in [`evidence/h33_validation.json`](../../evidence/h33_validation.json) supports a possible mechanism but not a live-score attribution:

- The reported H33-2-B2 operation removes 2,545 pixels within 2 px of the catalogue from a 40,199-pixel base, leaving 37,654.
- In a local LM-calibrated instrument, the H33-2-B2 mean is 0.2679205 versus 0.2630510 for the base: a difference of +0.0048695, positive in 4/4 folds.
- That local delta is not an organizer DTI, does not verify the claimed 0.2778, and does not show that the live score improved.
- An archived [`lane-chi-report.html`](../lane-chi-report.html) gives 0.2708 for a same-named artifact. There is no organizer receipt proving byte identity or reconciling that number with the 0.2778 owner claim. The public board's rank-23 0.2778 (extradr19) and rank-36 0.2708 (smrtdoog5) do not authenticate either file.

Removing predicted mass could improve the official metric if those cells carried more false-positive mass than hidden-truth credit; it could hurt if the removed cells were near hidden positives. The local instrument favors the first explanation only within its calibration regime. The hidden truth, a score receipt tied to exact bytes, and causal attribution are absent. Claims that deletion is proven to have caused a live 0.2708→0.2778 increase are unsupported and should not be repeated.

## Manual official public-board snapshot

The official [DrivenData leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) was read manually on 2026-10-11; 50 public rows are stored in [`registry/leaderboard_snapshot_2026-10-11.json`](../../registry/leaderboard_snapshot_2026-10-11.json), [`registry/leaderboard_history.jsonl`](../../registry/leaderboard_history.jsonl), and [`docs/score-ledger.csv`](../score-ledger.csv).

| Public rank | Participant | Public score |
|---:|---|---:|
| 1 | xiaofanhu | 0.4133 |
| 8 | DARD | 0.3195 |
| 23 | extradr19 | 0.2778 |
| 50 | MSU-Laskowski-GEMS | 0.2448 |

The leaderboard is dynamic. These values describe public participant rows only; they are not this repository's scores, private-test results, or file attributions. The feed skips automated requests to `drivendata.org`; future captures must remain manual and dated.

## Exact marginal-credit correction

The official score has `s = T / D`, where `D = α(T + S − M) + βG`, `α=0.2`, `β=0.8`, and the official triangular kernel reaches 300 m. Here `T` is weighted true-positive credit, `S` emitted mass, `M` the emitted mass's nearest-truth credit, and `G` scored truth mass. For a new unit-mass dot with maximum kernel weight `q` and actual increase `ΔT` after maxima are recomputed, `ΔD = α(ΔT + 1 − q)`. The exact improvement condition is:

```text
ΔT (1 − αs) > αs (1 − q)
```

Only for a nonredundant dot adding its full weight to one previously uncovered truth point (`ΔT=q=k`) does this reduce to `k > αs`. The coefficient `αs/(1−αs)` is the false-mass coefficient in the target-score inversion, not the general single-dot cutoff. Full derivation: [`score-ceiling-analysis.md`](score-ceiling-analysis.md).

## Ranked, untested hypotheses — not authorization

Four channel-steepness/χ hypotheses remain in [`next-chi-hypotheses-2026-10-11.md`](next-chi-hypotheses-2026-10-11.md), ranked qualitatively and explicitly **UNTESTED / DEFERRED**. They identify candidate physical mechanisms, off-catalogue signals, non-fault mimics, trusted layers, data gaps, costs, and first-test gates. They are research notes only. H65-1's STOP remains binding: no follow-up, resolution change, fresh TIFF, or slot is authorized by this list. Any later work would require a separate explicit authorization and a genuinely distinct first-test question; it must not simply retry this stopped lane.

## Literature and trusted source links

Metadata and mechanisms were checked against publisher, USGS, or official competition sources:

- Kirby & Whipple (2012), “Expression of active tectonics in erosional landscapes,” *Journal of Structural Geology* 44, 54–75, [DOI](https://doi.org/10.1016/j.jsg.2012.07.009) · [publisher record](https://www.sciencedirect.com/science/article/abs/pii/S0191814112001691).
- Perron & Royden (2013), “An integral approach to bedrock river profile analysis,” *Earth Surface Processes and Landforms* 38(6), 570–576, [DOI](https://doi.org/10.1002/esp.3302) · [publisher record](https://onlinelibrary.wiley.com/doi/10.1002/esp.3302).
- Royden & Perron (2013), “Solutions of the stream power equation and application to the evolution of river longitudinal profiles,” *Journal of Geophysical Research: Earth Surface* 118(2), 497–518, [DOI](https://doi.org/10.1002/jgrf.20031) · [publisher record](https://agupubs.onlinelibrary.wiley.com/doi/10.1002/jgrf.20031).
- Gailleton et al. (2019), “A segmentation approach for the reproducible extraction and quantification of knickpoints from river long profiles,” *Earth Surface Dynamics* 7, 211–230, [DOI](https://doi.org/10.5194/esurf-7-211-2019) · [journal page](https://esurf.copernicus.org/articles/7/211/2019/).
- Barnes, Lehman & Mulla (2014), “Priority-flood: An optimal depression-filling and watershed-labeling algorithm for digital elevation models,” *Computers & Geosciences* 62, 117–127, [DOI](https://doi.org/10.1016/j.cageo.2013.04.024) · [publisher record](https://www.sciencedirect.com/science/article/abs/pii/S0098300413001337).
- Wobus et al. (2006), “Tectonics from topography: Procedures, promise, and pitfalls,” GSA Special Paper 398, 55–74, [DOI](https://doi.org/10.1130/2006.2398(04)).
- [Official DrivenData metric/submission page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/); [USGS 3DEP](https://www.usgs.gov/3d-elevation-program); [USGS SGMC](https://mrdata.usgs.gov/geology/state/) and [data-release DOI](https://doi.org/10.5066/F7WH2N65); [PRISM Climate Group](https://prism.oregonstate.edu/); [USGS 3D Hydrography Program](https://www.usgs.gov/3d-hydrography-program).

## Site, feed and safety controls

[`registry/current_site_status.json`](../../registry/current_site_status.json) makes H65-1 the latest status and points to the research-only TIFF, evidence and run card; c7653 remains historical. The current site and feed show **STOP**, no recommended upload and no cleared submission. `registry/submission_build.json` is a historical build record, not a recommendation. The TIFF is directly accessible from the home and submission-status pages, explicitly labelled **research only — DO NOT SUBMIT**. Its local [format receipt](../downloads/gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.json) confirms the `[0,1]` range locally but is not portal acceptance.

The previous “Predicted values must be in range [0, 1]” message is a format/range rejection. For any separately authorized future artifact, use the shared template writer and validator to verify the official grid, CRS, transform, dimensions, finite values and `[0,1]` range before upload. That checklist does not override this stop.

The scheduled feed refresh skips `drivendata.org`; it preserves manual board snapshots and probes only non-competition sources. Fail-closed guards check the recorded negative stop before lane runners or submission writers proceed. The current report and four-candidate backlog have not changed that gate.
