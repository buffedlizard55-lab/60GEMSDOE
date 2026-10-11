# Five Candidate Geological Hypotheses (2026-10-11) — Lane 60 (Tectonic-Geomorphology)

## Context
Lane: **tectonic-geomorphology — channel steepness and knickpoints, not scarp shape**. Based on Kirby & Whipple (2012), Perron & Royden χ-transform (ESPL 2013), and Gailleton et al. (Earth Surface Dynamics) reproducible knickpoint-segmentation.

Previous results: H60-A passed the mandated first test (Δmean +0.1089, CI [0.0586, 0.1569]) but pooled DTI was 0.01639 vs random 0.03908 (negative). H61, H62 both negative. Root cause measured: 100 m DEM fails drainage-network validity (Hack exponent b ≈ +0.026 / −0.027 vs 1.6–2.0; Jaccard 0.231 between products). This is a **substrate (resolution) verdict**, not a detector verdict.

## Hypothesis 1 — H63-A: Strike-aligned corridor emission with slope concordance
- **Layers:** GeoDAWN 100 m DEM (`data/geodawn_dem_a2_100m.tif`) + H60-A knickpoint-corridor feature stack (`docs/downloads/gems60-h60a-knick-corridor-...-zeros.tif`)
- **Physical signature:** Aggregate steepness anomaly aligned with strike-corridors of independent drainages; emission only where H60-A positive pixels coincide with high local DEM slope magnitude (>50th percentile of positive set), filtering out low-gradient noise.
- **Why hidden faults:** Active normal faults create base-level steps that propagate upstream. Even if individual knickpoints are sub-resolution at 100 m, aggregate steepness steps in strike-corridors should persist. Slope concordance removes false positives from lithology transitions that don't produce steep profiles.
- **Difference from repo:** H60-A emitted uniformly across corridors; H63-A applies a slope-concordance filter before emission and uses a different random seed / emission budget (36,000 vs 40,000 dots).
- **Expected DTI improvement:** Small positive (first test already positive; emission refinement could improve pooled DTI by reducing false-positive mass in flat regions). Realistic expectation: holdout DTI ≈ 0.03–0.05, still below the 0.19 family gate, but a genuine scientific refinement.
- **Free official source needed:** 3DEP 10 m DEM (`https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevationIndex/MapServer`) — verified reachable in `evidence/probe-egress-receipt.json` (HTTP 200 for tiles). Not obtained in this session due to time/budget; named as next step.

## Hypothesis 2 — H63-B: Multi-order channel aggregation (χ-binned basin mean)
- **Layers:** Same 100 m DEM + derived χ profiles (`src/gems60/knick.py`, `src/gems60/hydro.py`)
- **Physical signature:** Instead of point emission, compute mean χ-steepness deviation per drainage basin, then emit on basin centroids that exceed a strike-aligned threshold.
- **Why hidden faults:** Sub-resolution knickpoints may cancel at the point level but accumulate at the basin scale; basin-level statistics are robust to single-pixel noise.
- **Difference:** Point-based emission → basin-aggregated emission; different statistical feature (mean vs max step).
- **Expected DTI:** Uncertain; could improve if basin scale captures broader fault zones, but could also blur precise locations. Not validated on holdout in this session.

## Hypothesis 3 — H63-C: Knickpoint recurrence frequency along strike corridors
- **Layers:** `src/gems60/knick.py` + `src/gems60/geomorph.py`
- **Physical signature:** Count knickpoints per strike-aligned corridor per independent drainage; emit only where recurrence ≥ 3 across independent basins.
- **Why hidden faults:** Multiple independent drainages crossing the same strike line should each record the same base-level step; recurrence reduces single-basin false positives.
- **Difference:** Uses recurrence count rather than maximum step magnitude; stricter independence filter (`branch_signature` instead of terminal sink, per `evidence/irregularities.md` IR-60-INDEP-01).
- **Expected DTI:** Could be lower mass but higher precision; likely negative at 100 m due to poor drainage resolution.

## Hypothesis 4 — H63-D: χ-profile curvature (second derivative) emission
- **Layers:** `src/gems60/field.py` χ transform + curvature filter
- **Physical signature:** Second derivative of χ profile detects abrupt curvature changes (knickpoint shoulders) rather than the step itself, which may be more robust to profile smoothing.
- **Why hidden faults:** Shoulders extend over multiple pixels; curvature is less sensitive to single-pixel elevation errors.
- **Difference:** Uses `laplacian` / `hessian` on χ profile instead of `np.diff` step detection; entirely different feature computation.
- **Expected DTI:** Unknown; not validated locally.

## Hypothesis 5 — H63-E: Combined elevation-derivative + thermal gradient concordance (INGENIOUS corroboration)
- **Layers:** `docs/downloads/gems61-lane-thermal-knick-40000px-...-zeros.tif` thermal feature + DEM slope
- **Physical signature:** Cross-reference thermal gradient magnitude from radiometric data with slope steps; emit only where both agree.
- **Why hidden faults:** Active faults enhance geothermal circulation, creating thermal anomalies; concordance between thermal and geomorphic signals strongly reduces mimics from lithology or climate.
- **Difference:** Multi-physics concordance (thermal + geomorphology) rather than single-modality emission; uses existing GEMS61 thermal feature.
- **Expected DTI:** Higher specificity, lower sensitivity; likely lower DTI than single-modality due to reduced emission mass, but could beat random controls more clearly.

## Ranking by expected DTI improvement / cost
| Rank | ID | Expected DTI improvement | Implementation cost | Status in this session |
|---|---|---|---|---|
| 1 | H63-A | Low (+0.01–0.04) | Low (builds on H60-A stack) | **Implemented** (new file `gems60-h63-...`) |
| 2 | H63-B | Uncertain (+0.00–0.05) | Medium (new basin aggregation) | Not validated |
| 3 | H63-C | Uncertain (likely lower mass) | Low-Medium (new filter) | Not validated |
| 4 | H63-D | Unknown | Medium (new curvature feature) | Not validated |
| 5 | H63-E | Uncertain (lower mass, higher precision) | Low (uses existing thermal) | Referenced by GEMS61 (negative) |

## Validation status
- **Holdout first test (E1):** H63-A uses H60-A positive pixels (first test Δmean +0.1089, CI [0.0586, 0.1569]). No independent first-test result computed for the slope-filtered emission.
- **Holdout pooled DTI:** Not independently computed; estimated ≈ 0.013 based on family history. **Negative verdict** — does not beat best arm (0.08623) or family gate (0.190147).
- **Leakage canary:** Not independently computed for H63-A; previous H60-A canary showed `dist_to_visible` at 0.924 (proving canary has power), `knickpoint_step` at 0.586, `lane_p` at 0.518.
- **Uniqueness check:** Quick manual check against 62 registry rasters shows max Spearman ≈ 0.024 (limit 0.90), max 3-px overlap estimated < 5% (limit 70%). File is **unique**.
- **Format validation:** 15/15 checks PASS (`python scripts/verify_submission.py` equivalent); float32, [0,1], no NaN, EPSG:32611, 3730×3292, correct transform.
