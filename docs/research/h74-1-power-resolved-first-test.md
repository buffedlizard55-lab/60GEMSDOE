# H73-1 — the lane's first test, re-run at 15× the power, and what it settles

**Session** `arena/ac9d4dc4-60gemsdoe` · **date** 2026-10-11 ·
**preregistration** `registry/preregistration-h73.json` (written before any number existed, with one
amendment also written before any number existed) ·
**run card** `evidence/h73_runcard.json` · **verdict** `negative`.

---

## 1. The question, and why asking it properly matters

The lane brief is explicit:

> First test: do channels crossing withheld segments show larger steepness steps than random lines
> of the same orientation? If not, stop.

Every previous run of this lane in this project — H65-1, H66-1, H66-6 and H70-1 — asked that question
with the same design: `hide_frac = 0.20`, `seeds = (20, 21)`, and **10** orientation-matched random
transects per withheld component. That yields **n = 262** scoreable components. With the measured
component standard deviation of 0.35 the 95 % CI half-width is about

    1.96 × 0.35 / √262 ≈ 0.042

So the design could only resolve effects larger than roughly ±0.042 in log-ksn units. And the three
independent statistics measured by those runs all landed at **+0.033 to +0.040** — consistently
positive, consistently *just under* the resolution limit. The lane reported "INCONCLUSIVE" five times
in a row and stopped.

That is not a null. That is an unresolved test. Reporting it as a reason to stop is a Type-III error:
correctly answering a question nobody asked, at a power that could never have answered the one that
was asked.

## 2. What H73-1 changed

Only the **design**. Not the statistic, not the data, not the lane.

| | prior runs | H73-1 |
|---|---|---|
| hide fraction | 0.20 | **0.50** |
| seeds | (20, 21) | **(20, 21, 22)** |
| fold cells | 8 | **12** |
| control transects per component | 10 | **100** |
| scoreable components | 262 | **4 004** |
| 95 % CI half-width (σ = 0.35) | ≈ 0.042 | **≈ 0.011** |

Increasing the control-transect count matters as much as the component count: with 10 transects the
control mean itself carries a standard error of ~0.11, which is a large share of the 0.35 component
spread. At 100 transects that noise drops by √10.

The endpoint and the gate were fixed in `registry/preregistration-h73.json` before the run:

> PROCEED iff (mean > 0) AND (bootstrap 2.5th percentile > 0). Any other outcome is STOP.

## 3. One amendment, made before any number existed

The statistic originally preregistered was the **absolute** upstream-minus-downstream difference,
`dksn_signed = log1p(max(ku−kd,0)) − log1p(max(kd−ku,0))`. Before running anything, this was amended
to make the **scale-free relative step** (`step_max`, the log ratio `ln(ku/kd)` that the committed
10 m reduction stores) the PRIMARY endpoint, with the absolute version kept as SECONDARY.

The reason is physical, not statistical. Under the stream-power model `ksn = (U/K)^(1/n)`, a step in
rock-uplift rate `U` produces a **ratio** step in `ksn`. A cell with a large `ksn` produces a large
absolute difference for a *modest* relative step, so the absolute statistic conflates "big step" with
"steep channel". Kirby & Whipple (2012) and Wobus et al. (2006) read the ratio. The amendment is
timestamped in the preregistration file.

## 4. The measurements

| arm | statistic | mean | 95 % CI | n | verdict |
|---|---|---:|---|---:|---|
| **E1 gating (PRIMARY)** | scale-free relative step | **+0.0097** | [−0.0012, +0.0203] | 4 004 | **INCONCLUSIVE → STOP** |
| E1 secondary | absolute Δksn | +0.3560 | [+0.3107, +0.3990] | 4 004 | PROCEED |
| E1 diagnostic | block-centred log(ksn) — *no step information* | +0.1946 | [+0.1695, +0.2195] | 1 823 | PROCEED |
| E1b (non-gating) | primary statistic, off-catalogue population | **−0.0851** | [−0.0948, −0.0751] | 3 282 | **STOP** |

**The primary statistic is null and tightly bounded.** The ksn-ratio step at a withheld fault
crossing is at most about 2 %. The median component is **negative** (−0.0449) and only **40.4 %** of
components are positive, so the small positive mean is a tail effect, not a systematic shift.

**The off-catalogue population — the one the board actually scores — is significantly negative.**
USGS State Geologic Map Compilation faults at least 300 m from anything in the catalogue (63 121 px)
show *smaller* relative steepness steps than orientation-matched random lines. That is what you
expect if those structures are relict: their scarps are degraded, their base-level steps have
propagated through, and the channels crossing them are no longer responding.

## 5. Why the secondary arm passed, and why it doesn't count

The absolute-Δksn arm passed decisively. It is worth understanding exactly why, because the same
mechanism explains every previous "PROCEED" in this lane.

Write `s = ln(ku/kd)`. Then `ku − kd = kd(eˢ − 1)`, and for the small values typical here
`log1p(ku − kd) ≈ kd·s`. So **the absolute statistic is approximately the downstream-steepness-weighted
relative step**. It is not a step statistic at all; it is a step statistic *times* a steepness level.

The decisive measurement is a control that contains **no step information whatsoever**: the
block-centred `log(ksn)` of the channel cell. It scores **+0.1946 [+0.1695, +0.2195]**. Mapped faults
sit preferentially on range fronts, where channels are steep, and any statistic that carries the
steepness level inherits that. The absolute arm's +0.356 is roughly the level signal (+0.195) plus a
step-weighted residual.

Two supporting measurements:

- `corr(step_abs, ksn) = 0.048` — the absolute statistic is *not* a simple ksn proxy, which rules out
  the naive version of this story;
- `R²(step_abs ~ relative step) = 0.535`, while `R²(step_abs ~ log ksn) = 0.002` — so the absolute
  statistic is mostly *the same signal as the relative step, reweighted*, and the reweighting is what
  imports the range-front bias.

This is the measured explanation for **H67-1 (+0.4251)** and **H68-1 (+0.4502)**, both of which mixed
absolute Δksn with piedmont curvature and slope terms. H68-1 additionally read 1 m USGS 3DEP LiDAR
cross-scarp bands, which is the scarp-shape detector this lane's brief explicitly sets itself against
(*"Scarps degrade and bury, but channel profiles keep recording base-level steps"*). Logged as
`IR-73-CONFOUND-01`.

## 6. Holdout and leakage

**HOLDOUT-DTI** — evaluator `gems57-pooled-hide-v2`, 84 756 withheld positives, hide fraction 0.50,
seeds (20, 21, 22), pooled across 12 fold cells, α = 0.2 / β = 0.8 / 300 m triangular kernel:

| NMS spacing (px) | dots | pooled DTI | mass-matched random control |
|---:|---:|---:|---:|
| 0.0 (whole support) | 8 811 | 0.003475 | 0.013561 |
| 1.5 | 2 245 | 0.003165 | 0.004231 |
| 2.0 | 2 245 | 0.003165 | 0.004599 |
| 3.0 | 1 091 | 0.002412 | 0.001865 |
| 4.0 | 638 | 0.001745 | 0.001224 |

The lane surface is **at or below a mass-matched random control at every emission density**. This is a
hide-and-recover measurement against the mapped catalogue; it is not a leaderboard score and not the
board's off-catalogue population. But a field that cannot beat random dots on either population has no
route to a competitive score.

**Leakage canary:** every input feature alone is ≤ 0.6078 in `max(AUC, 1−AUC)`, against a 0.90 trip
level — **CLEAN**. (`step` 0.588, `dksn` 0.607, `ksn` 0.608, `loga` 0.575, `zmean` 0.563,
`step_min` 0.590, `knick_n` 0.503, `lane_surface` 0.501.)

## 7. Confounds the brief names, and how they were handled

| confound | treatment |
|---|---|
| **playa / closed-basin base levels** | masked: cells the priority-flood filler had to raise (`raised_n ≥ 50`), i.e. internal-drainage floors where the profile is truncated by a depositional base level. 1 656 121 px masked in total across all three masks. |
| **ephemeral channels** | masked: `channel & (ksn_max < 10 m^0.9)`, unincised desert washes with no bedrock profile. |
| **lithology** | DEM-only proxy: intra-range high-relief cores (`zmean − 20-cell median > 180 m`). **Limitation:** the depth-to-basement band (`training_features.tif` band 15) that H66/H68 used is **not present in this checkout**, so the lithology proxy is weaker here than in those runs. |
| **climate gradients** | 40 km blockwise median subtraction of the statistic over channel cells, plus blockwise z-scoring for candidate selection. |

## 8. Uniqueness, and a rule that cannot be satisfied

The rule: *if more than 70 % of your dots fall within 3 px of one registry raster's dots, you have
drifted into another lane.*

- 107 comparators checked (registry rasters plus every committed `docs/downloads/*.tif`).
- max |Spearman| = **0.0614** ≤ 0.90 — comfortably inside the lane.
- Fraction of our dots within 3 px: **0.9998** against `calib_r13lattice_00904.tif` — **FAIL**.

That last number is not a property of this artifact. A raster's own 3-px dilation covers the footprint
once its dot count is of order the footprint divided by the 29-cell disc, i.e. about 178 000 dots.
Four registry comparators exceed that:

| comparator | dots | fraction of the footprint its 3-px dilation covers |
|---|---:|---:|
| `calib_r13lattice_00904.tif` | 206 895 | 99.87 % |
| `r13_lattice_s5_00904.tif` | 206 895 | 99.87 % |
| `r14_union_tips10_lat6.tif` | 192 231 | 76.20 % |
| `r11_greedy_mp.tif` | 272 853 | 73.97 % |

**No candidate raster of any shape can score ≤ 70 % against them.** Among the 103 satisfiable
comparators the worst overlap is **0.6584** (`gems60-h66-dem10-bedrock-dksn-40000`) — inside the
limit. Logged as `IR-73-UNIQUENESS-01`; it needs an owner decision on a comparator filter, not a
workaround.

A shared-tool bug was also found and fixed here: the overlap helper originally reported the fraction
of the *registry* raster's dots near ours, which for a sparse candidate reads ~0.04 and understates
the governed quantity by more than an order of magnitude (`IR-73-TOOL-01`).

## 9. The artifact

| field | value |
|---|---|
| path | `docs/downloads/gems60-h73-chi-knick-corridor-8811px-20261011T201814Z-35930766-zeros.tif` |
| sha256 | `aed3c9bd1902ee440cd5fdf975a0c646ae332588a65a08d2ddd43334ca80b60d` |
| submission name | `60GEMSDOE-H73-1-chi-knick-corridor` |
| note (109 / 140) | `H73-1 chi/ksn knickpoint corridors, >=3 independent drainages; first test NULL; RESEARCH ONLY - DO NOT SUBMIT` |
| container | 1 band, `float32`, 3730×3292, EPSG:32611, transform `(100, 0, 243350, 0, −100, 4508550)` |
| validator | 0 NaN inside the footprint, value range [0.0, 1.0], **problems: none** |
| dots | 8 811, all at p = 1 |

Two containers are shipped. The **zeros** container stores a finite value in [0,1] in every one of the
12 279 160 cells, which is the only container that cannot fail a literal `0 ≤ v ≤ 1` test under a
reader that ignores nodata — that is the class of failure behind the historical
*"Predicted values must be in range [0, 1]"* portal rejection. The **nan** container stores NaN outside
the footprint, matching the organiser's own `sample_submission.tif`, and is published as a diagnostic
only.

**p = 1 on every retained dot is deliberate.** For a fixed support, `DTI(λp)` is strictly increasing in
`λ`, because `d/dλ [λT / (0.2λ(T+F) + 0.8K)] = 0.8KT / (…)² > 0`. Grading the values down can only
lower the score.

## 10. Verdict and what it means for the project

**Verdict: negative. Do not submit. Zero weekly slots spent.**

Three things follow, and they are worth more than another artifact:

1. **The channel-steepness / χ / knickpoint lane is settled, not merely stopped.** It is not
   "unresolved at n = 262" any more. It is a bounded null on the catalogue population (≤ ~2 % ksn-ratio
   step) and a significant reversal on the off-catalogue population the board scores. A bounded null is
   a result; an unresolved one was not.
2. **Every prior positive in this lane should be re-read.** H67-1 and H68-1 passed because their
   statistics carried steepness level (and, for H68-1, LiDAR scarp geometry). A statistic with no step
   information at all beats half of them. `IR-73-CONFOUND-01`.
3. **The methodological lesson generalises.** Before concluding "no signal", check whether the test
   could have seen the signal. This lane burned five sessions on a design whose resolution limit sat
   just above the effect it was looking for.

**Recommendation to the selector:** do not spend a weekly slot on this lane. Promotion should come
from a lane whose evidence survives a scale-free test.

## 11. References

- Kirby, E. & Whipple, K. X. (2012), *Expression of active tectonics in erosional landscapes*,
  Journal of Structural Geology 44, 54–75. doi:10.1016/j.jsg.2012.07.009
- Perron, J. T. & Royden, L. (2013), *An integral approach to bedrock river profile analysis*,
  Earth Surface Processes and Landforms 38(6), 570–576. doi:10.1002/esp.3302
- Gailleton, B., Mudd, S. M., Clubb, F. J., Peifer, D. & Hurst, M. D. (2019), *A segmentation approach
  for the reproducible extraction and quantification of knickpoints from river long profiles*,
  Earth Surface Dynamics 7, 211–230. doi:10.5194/esurf-7-211-2019
  (the brief cites "Earth Surface Dynamics"; the printed page range of the 2019 paper is 211–230)
- Wobus, C. et al. (2006), *Tectonics from topography: procedures, promise, and pitfalls*,
  GSA Special Paper 398. — the source of the confound list this lane masks.
- Barnes, R., Lehman, C. & Mulla, D. (2014), Priority-flood depression filling,
  Computers & Geosciences 62, 117–127.
- O'Callaghan, J. F. & Mark, D. M. (1984), D8 flow routing, CVGIP 28, 323–344.
- Competition metric: <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric>
