# Submission-status audit — 2026-10-11

## Executive decision

**Download for research: YES. Submit to competition: NO. No new TIFF generated.**
This review respects the explicit first-test STOP rather than making a trivial byte-distinct
raster to satisfy the filename requirement. No weekly slot was used. The unique, promotable
submission requested by the brief has **not** been achieved.

[Existing research TIFF](../downloads/gems60-h65-dem10-knick-40000-20261011T051305Z-9406dc92098b-zeros.tif)
· [fresh format audit](../../evidence/submission_status_audit.json)
· [review run card](../../evidence/review_run_card.json)

## Findings and corrections

| Finding | Evidence / verification | Action |
|---|---|---|
| STOP and PROMOTE appeared simultaneously at the top of the site | `registry/current_site_status.json` versus H67 marker blocks and `submission_card.json` at base commit `79bba965c60db393010aa887a1031ef002c9b9ac` | Shared renderer suppresses archived banners when status is not explicitly active; README archives superseded advice |
| H67 excluded lattice rasters from its promotion decision | `evidence/h67_uniqueness.json`: raw dot overlap 0.998675; literal gate 0.70; `unique=false`, `stop_required=true` | Corrected published H67/root/download run-card verdicts to negative; preserved measured values |
| Legacy selector substituted excess-over-random for raw overlap | `scripts/selector.py` | Restored literal threshold and fail-closed coverage check; STOP guard runs before diagnostics |
| Active status without affirmative first-test evidence could pass guard | `scripts/stop_guard.py` | Missing, malformed, unknown, or non-PROCEED current evidence blocks execution |
| “Data placement is the only blocker” is obsolete | Cached DEM-derived channel files and official sample/label grids are present | Scientific signal, uniqueness coverage, confound validation and score provenance are the material blockers |
| H65 is not chronologically the latest artifact | H66/H67 records exist | Site now calls H65 the governing STOP record, not the latest experiment |

The raw uniqueness rule can reject a scientifically distinct surface when a registry raster
is dense. That is a protocol-design issue, not permission to delete dense comparisons.
No exception is applied here. Historical remote-scan coverage is inherited evidence;
this review did not independently fetch all earlier rasters.

## Why H33 might work, and what cannot be concluded

Freshly fetched GitHub source for [GEMSDOE32's page](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/docs/index.html)
(blob `8857c8f8c3a54859beaf9f87a82bb8638038b6d8`) names the H33-B2 file but describes it as
**UNSCORED**, with a projection. It is not a submission-page receipt for the owner's claimed
0.2778. Neither that source nor a leaderboard row proves which exact raster received a score.
The conflicting figures in the prompt and the inherited manual leaderboard snapshot must not
be treated as a fresh leaderboard observation.

There is a plausible *metric* explanation for the family's dotted outputs: a maximum-based
spatial tolerance rewards nearby coverage, while false-positive contributions accumulate.
Thinning redundant predictions may preserve much of that coverage while reducing false-positive
mass. Excluding known-fault neighborhoods may reduce wasted predictions, but can also remove
real hidden-fault signal. Two rounded reported scores cannot uniquely identify the hidden truth,
its size, or an organizer exclusion halo. Earlier exact “live inversion” language is not evidence
of those hidden quantities. A higher score is possible in principle, but neither the size nor even
the sign of a change can be forecast here.

This lane does not establish a direct geothermal-vent detector. Channel profiles can support
fault inference, and faults can influence permeability; geothermal resources also require heat,
fluids and suitable connectivity. A fault-prediction score is not verification of a vent.

## Scientific result and ranked hypotheses

Inherited **HOLDOUT-DTI** for H65-1 is 0.01158, 95% CI [0.00840, 0.01462], evaluator
`gems57-pooled-hide-v2`, 22,641 withheld-positive pixels. The first-test log-steepness contrast
is a **diagnostic, not DTI**: its confidence interval crosses zero. The registered positive-signal
gate therefore did not pass. These numbers were not recomputed in this review.

The [four ranked hypothesis designs](next-chi-hypotheses-2026-10-11.md) remain deferred:
paired-basin contrast; channel confinement and steepness; hydroclimate/permanence-matched residuals;
outlet-conditioned residuals. They already exist in the repository and are not presented as newly
invented or experimentally validated. Their expected DTI gains are unknown. They document layers,
physical signatures, differences from earlier implementations, mimics, and qualitative cost.
No new hypothesis was tested after the STOP.

Official free sources needed for stronger controls include [USGS SGMC](https://doi.org/10.5066/F7WH2N65),
[USGS 3DHP](https://www.usgs.gov/3d-hydrography-program),
[USGS 3DEP](https://www.usgs.gov/3d-elevation-program), and
[PRISM climate grids](https://prism.oregonstate.edu/).
This environment's allowed outbound hosts do not include these data services, DrivenData,
Dropbox or the literature publishers. Regional coverage and download integrity were not freshly
verified, so designs requiring those inputs are **not declared viable**. Existing tile manifests
are historical provenance, not fresh access checks.

Literature for manual review: [Kirby & Whipple 2012](https://doi.org/10.1016/j.jsg.2012.07.009),
[Perron & Royden 2013](https://doi.org/10.1002/esp.3302),
[Gailleton et al. 2019](https://doi.org/10.5194/esurf-7-211-2019).
These links describe the scientific basis recorded in the repository; no new full-text verification
is claimed in this review. Proxy masks are not direct measurements of lithology or stream permanence.

## Format audit and submission procedure

The shared `gems57.gates.format_report` freshly reread every TIFF in `docs/downloads`.
The receipt records per-file checksums, grid comparison and range/nonfinite errors. The all-finite
local export policy is stricter than the historical outside-footprint-NaN convention; an audit failure
under that policy is **not proof** of an organizer rejection. The active research artifact passes.
A file's correct range does not prove organizer acceptance or uniqueness.

For a future **separately cleared** candidate only:

1. Confirm the surface and dots pass the full registry gates, each feature passes the canary,
   and the compatible blocked holdout beats the registered best with the required uncertainty.
2. Have the separate selector approve a slot after checking the current official weekly cap.
   This review could not inspect that authenticated cap.
3. Use the shared writer, then reread the exact downloadable TIFF against the official sample:
   one band, matching CRS/shape/transform, finite footprint, values within [0,1].
4. Download the cleared `.tif` (not a report or JSON), select it on DrivenData's submission page,
   and use the run-card name and a note of at most 140 characters.
5. Preserve the organizer's receipt with the uploaded SHA-256. Only that receipt can support
   an ORGANIZER-CONFIRMED attribution. Do not upload any current lane artifact.

The [official reference README](https://github.com/drivendataorg/gems-prize-reference-solution/blob/aebe92f7c8a990f0e3443451b7a825d9afd6336b/README.md)
was fetched this review. It explicitly supports CPU-only environments as well as GPU acceleration;
“GPU needed for training” is not a universal requirement. This review did not train that model.

## Three-pass verification and next session

- **Pass 1:** repository, status, shared writer/evaluator locations, prior run cards and site audit;
  baseline unit suite passed. Found contradictory publication and literal-gate bypass.
- **Pass 2:** corrected the shared renderer, selector and guard; reread downloadable files with
  the shared validator; added regression tests for unknown evidence and contradictory banners.
- **Pass 3:** rerun complete tests, regenerate pages twice for stability, check local links,
  inspect the final diff and publish through a pull request. Exact test counts are in the PR.

Next work should reconcile the complete raster registry and organizer receipts, and audit fold
compatibility and confound coverage **without restarting the stopped experiment**. A genuinely
new scientific protocol needs separately documented authorization, not another threshold sweep.
No promised leaderboard improvement, claim of exhaustive line-by-line scientific verification,
or automatically current feed is justified by the available evidence.
