# Active-lane review — 11 October 2026

## Executive decision

**The active channel-steepness / χ / knickpoint lane is stopped.** The preregistered first test for run `c7653` failed its stop rule: withheld-segment crossings were less extreme than the orientation-matched nulls. No further experiment was run in this continuation, no new GeoTIFF was made, and no weekly submission slot was used.

The existing `c7653` raster is available **for research download only; do not submit it**: [`gems60-knickpoint-lane-c7653-20261011T000000Z.tif`](../downloads/gems60-knickpoint-lane-c7653-20261011T000000Z.tif). Its local format receipt says it is single-band float32, EPSG:32611, 3292×3730 on the 100 m template, finite, in `[0,1]`, with 7,653 positive cells and no local validation problems. The receipt explicitly does **not** establish organizer acceptance or slot approval. This is an existing negative-result artifact, not a new or cleared submission.

The separate H60A run is not evidence that reverses this stop. H60A had a positive first-test result, but a separate later holdout and uniqueness outcome failed. Its run card, evaluator and scores must not be combined with c7653.

## Current official public-board read

A manual read of the official [DrivenData leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) on 2026-10-11 returned 50 public rows:

| Public rank | Participant | Best public DW-Tversky |
|---:|---|---:|
| 1 | xiaofanhu | 0.4133 |
| 8 | DARD | 0.3195 |
| 23 | extradr19 | 0.2778 |

The complete transcribed page is stored in [`registry/leaderboard_snapshot_2026-10-11.json`](../../registry/leaderboard_snapshot_2026-10-11.json), appended to [`registry/leaderboard_history.jsonl`](../../registry/leaderboard_history.jsonl), and included row-by-row in [`docs/score-ledger.csv`](../score-ledger.csv). The board is dynamic. These are public scores for listed participants; none is a score for this repository, and the page does not identify the prediction raster behind a row. The old README/site figures 0.3774 and “DARD 0.3195 is the leader” are stale.

The numerical equality between H33's owner-reported 0.2778 and extradr19's public 0.2778 at rank 23 is **not attribution**. No organizer receipt links that public row to the H33 raster. A separate archived `docs/lane-chi-report.html` calls a same-named `h33-h33-2-b2` file an owner-reported 0.2708 raster; the records do not establish byte identity or reconcile this with the current 0.2778 owner claim. On the same manual board, 0.2708 is smrtdoog5 at rank 36, also without file attribution. This conflict is logged as `IR-60-H33-SCORE-20261011`.

## What the H33-2-B2 0.2778 claim can—and cannot—be explained by

The score remains **OWNER-REPORTED / UNVERIFIED**. The local evidence in [`evidence/h33_validation.json`](../../evidence/h33_validation.json) supports a plausible mechanism, not a live-score verification:

- The reported H33-2-B2 operation removes 2,545 pixels within 2 px of the catalogue from a 40,199-pixel base, leaving 37,654.
- In a local, LM-calibrated instrument, the H33-2-B2 mean is 0.2679205 versus 0.2630510 for the base: a difference of +0.0048695, positive in 4/4 folds.
- That number is **not** an organizer DTI and is not a receipt for the claimed 0.2778. The instrument is calibrated on other owner-reported orderings and cannot identify the hidden faults or prove why a live score changed.

The operation could improve the official metric if the removed predictions had carried more false-positive mass than hidden-truth credit. It could instead hurt if removed pixels were close to hidden positives. The local instrument favors the first explanation within its calibration regime; the hidden truth, live receipt and causal attribution are absent. That is the limit of the evidence.

## c7653: the stopping result

The preregistered first test is recorded in [`evidence/e1_lane_test.json`](../../evidence/e1_lane_test.json) and summarized in [`evidence/runcard.json`](../../evidence/runcard.json):

- 78 withheld segments; 5,683 withheld pixels.
- Placement-null AUC **0.22436**; orientation-null AUC **0.25641**. The preregistered verdict is **NEGATIVE-STOP**.
- Pooled local **HOLDOUT-DTI**: **0.00213750**, 95% CI **[0.00179003, 0.00251341]**, 36,414 withheld positives, evaluator `gems52-pooled-hide-v1`.
- This holdout uses catalogue-derived truth and is not comparable to a public leaderboard score. It cannot score genuinely off-catalogue discoveries.

Two outstanding scope limits matter. The archived c7653 card lists six comparisons only; its Spearman values were computed on the final binary dot mask, not the pre-placement continuous score surface, and the listed rasters do not establish complete-registry coverage. Six post-placement 3-px overlaps were recorded, but the required surface-rank screen and global uniqueness clearance are **not established** (`IR-60-UNIQUENESS-SURFACE-20261011`). Separately, the old run card called 0.50145 a composite-field AUC, but the script actually computed `(Spearman rho + 1) / 2` (implied rho 0.0029023), not ROC AUC. No feature-by-feature ROC-AUC canary table is recorded, so leakage clearance is **not established** (`IR-60-CANARY-LABEL-20261011`). The negative result is still decisive for the preregistered first-test stop rule: neither gap licenses more experiments in this lane.

The separate H60A evidence is in [`evidence/h60a_e1_first_test.json`](../../evidence/h60a_e1_first_test.json) and [`evidence/h60a_holdout.json`](../../evidence/h60a_holdout.json). H60A's first-test result was +0.10889 (95% CI [+0.05862, +0.15695]) on its own instrument. Its later pooled HOLDOUT-DTI was 0.016393 (95% CI [0.012234, 0.020613]) versus 0.039080 for its random-mass control and 0.190730 for its distance-only control; its uniqueness gate failed. Those are H60A-only results, not a continuation or rescue of c7653.

## Exact marginal-credit correction

Write the official score as `s = T / D`, with `D = α(T + S − M) + βG`, `α=0.2`, `β=0.8`; `T` is weighted true-positive credit, `S` is emitted mass, `M` is the emitted mass's nearest-truth credit, and `G` is scored truth mass. For a new unit-mass dot, let `q` be its own maximum triangular-kernel weight to any truth point and let `ΔT` be the actual increase in `T` after the maxima are recomputed. Then `ΔD = α(ΔT + 1 − q)`, and it improves the score exactly when

```text
ΔT (1 − αs) > αs (1 − q).
```

For a nonredundant dot that adds its full weight to one previously uncovered truth point (`ΔT=q=k`), this simplifies to `k > αs`. The often-quoted `αs/(1−αs)` is not the single-new-truth-dot threshold: it is the coefficient on false-positive mass in the target-score inversion `T = sβG/(1−αs) + [αs/(1−αs)]F`. The complete derivation and corrected table are in [`score-ceiling-analysis.md`](score-ceiling-analysis.md). The implementation in `src/gems52/emit.py` uses the general gain/discount form; no emitter change is proposed by this review.

## Literature metadata corrected

The tectonic-geomorphology citations in the active source modules and lane reports were checked against publisher or USGS records. Incorrect title/journal/page/DOI combinations were replaced:

- Kirby & Whipple (2012), “Expression of active tectonics in erosional landscapes,” *Journal of Structural Geology* 44, 54–75, [DOI 10.1016/j.jsg.2012.07.009](https://doi.org/10.1016/j.jsg.2012.07.009).
- Perron & Royden (2013), “An integral approach to bedrock river profile analysis,” *Earth Surface Processes and Landforms* 38(6), 570–576, [DOI 10.1002/esp.3302](https://doi.org/10.1002/esp.3302).
- Royden & Perron (2013), “Solutions of the stream power equation and application to the evolution of river longitudinal profiles,” *Journal of Geophysical Research: Earth Surface* 118(2), 497–518, [DOI 10.1002/jgrf.20031](https://doi.org/10.1002/jgrf.20031).
- Gailleton et al. (2019), “A segmentation approach for the reproducible extraction and quantification of knickpoints from river long profiles,” *Earth Surface Dynamics* 7, 211–230, [DOI 10.5194/esurf-7-211-2019](https://doi.org/10.5194/esurf-7-211-2019).
- Barnes, Lehman & Mulla (2014), “Priority-flood: An optimal depression-filling and watershed-labeling algorithm for digital elevation models,” *Computers & Geosciences* 62, 117–127, [DOI 10.1016/j.cageo.2013.04.024](https://doi.org/10.1016/j.cageo.2013.04.024).
- Wobus et al. (2006), “Tectonics from topography: Procedures, promise, and pitfalls,” GSA Special Paper 398, 55–74, [DOI 10.1130/2006.2398(04)](https://doi.org/10.1130/2006.2398(04)).

Publisher/USGS manual-review links: [Kirby & Whipple](https://www.sciencedirect.com/science/article/abs/pii/S0191814112001691), [Perron & Royden](https://onlinelibrary.wiley.com/doi/10.1002/esp.3302), [Royden & Perron](https://agupubs.onlinelibrary.wiley.com/doi/10.1002/jgrf.20031), [Gailleton et al.](https://esurf.copernicus.org/articles/7/211/2019/), [Barnes et al.](https://www.sciencedirect.com/science/article/abs/pii/S0098300413001337), and [Wobus et al.](https://doi.org/10.1130/2006.2398(04)).

## Deferred, untested hypotheses

A ranked four-item research backlog—each explicitly marked **UNTESTED / DEFERRED**, with physical mechanism, layer requirements, confounds, trusted data links, costs and future gates—is in [`next-chi-hypotheses-2026-10-11.md`](next-chi-hypotheses-2026-10-11.md). Its qualitative ranking is not a numeric DTI forecast, and it does not override c7653's stop rule.

## Feed, site status, and workflow correction

The current homepage and submission page now place the c7653 negative stop above all download links; the only surfaced TIFF is labelled **research only — DO NOT SUBMIT**. `registry/current_site_status.json` is the machine-readable override, and `docs/data/feed.json` exposes that status with no active submission recommendation. The previous `registry/submission_build.json` remains a historical build record, not today's recommendation.

During the feed review, `scripts/refresh_feed.py` was found to contain a scheduled direct fetch/parser for the competition leaderboard, contrary to the manual-snapshot-only requirement. That fetch was removed, `.github/workflows/feed.yml` now describes a non-competition health refresh, and `IR-60-LB-AUTO-20261011` records the correction. Fail-closed guards were also added to the c7653 E1/E1b/E2/E3 experiment runners so the existing NEGATIVE-STOP prevents accidental reruns or TIFF writes. The official board remains a manual 2026-10-11 snapshot; the feed does not poll DrivenData.

## Sources and artifacts

- [Official competition metric and submission page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).
- [Official public leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) and dated [50-row snapshot](../../registry/leaderboard_snapshot_2026-10-11.json).
- [USGS 3DEP](https://www.usgs.gov/3d-elevation-program); egress/substrate records: [`evidence/probe-egress-receipt.json`](../../evidence/probe-egress-receipt.json), [`evidence/e62b_substrate.json`](../../evidence/e62b_substrate.json). The recorded sample-tile access succeeded, but the two 100 m networks failed the recorded Hack-exponent validity check (about +0.026 and −0.027 versus the cited ~1.6–2.0 range) and agreed at Jaccard 0.2312. This is a data-quality warning, not grounds to continue after the E1 stop.
- [USGS SGMC source and data release](https://mrdata.usgs.gov/geology/state/) · [DOI 10.5066/F7WH2N65](https://doi.org/10.5066/F7WH2N65).
- Full review card: [`evidence/runcard.json`](../../evidence/runcard.json). Local format receipt: [`docs/downloads/gems60-knickpoint-lane-c7653-20261011T000000Z.json`](../downloads/gems60-knickpoint-lane-c7653-20261011T000000Z.json).
