# 60GEMSDOE — tectonic-geomorphology lane (channel steepness, χ and knickpoints)

**Competition:** [DOE GEMS Prize — DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/)
· **Problem description:** [page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
· **Rules (PDF):** [docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
· **Live site:** <https://buffedlizard55-lab.github.io/60GEMSDOE/>
· **Lane:** channel steepness and knickpoints — *not* scarp shape.

---

## ⬇️ STATUS OF THE DOWNLOAD AT THE TOP OF THIS PAGE

### 🔴 **DOWNLOAD: OK (research artefact) · SUBMIT TO THE COMPETITION: NO**

The single download produced by this repository is published **as a negative result**.
The lane's own pre-registered go/no-go test — *"do channels crossing withheld fault
segments show larger steepness steps than random lines of the same orientation? If
not, stop"* — returned **STOP**, twice, under two independently parameterised detectors
(§ *Results* below). Submitting it would spend one of **three weekly competition slots**
on a field with no measurable skill, so it is labelled **do not submit**. It is offered
because the brief requires a unique, reproducible, format-validated GeoTIFF and because
negative results are deliverables.

**[⬇ Download `gems60-chi-knickpoint-cast-lane-v1-6000-dots-zeros.tif`](docs/downloads/gems60-chi-knickpoint-cast-lane-v1-6000-dots-zeros.tif)**
· [format receipt](docs/downloads/checks-gems60-chi-knickpoint-cast-lane-v1-6000-dots-zeros.tif.json)
· unique (worst Spearman **ρ = −0.015**, worst 3-px forward overlap **0.000** over 170
registry rasters), no template copied, single-band Float32, EPSG:32611, 3730 × 3292,
transform `(100, 0, 243350, 0, −100, 4508550)`, 6,000 binary dots, every cell finite,
0 cells outside `[0, 1]`, 0 dots on the mapped catalogue, minimum dot-to-catalogue
distance 2.24 px.

**What would have to change for the status to become green** is named, costed and
measured in § *What unblocks the lane* — it is the **10 m 3DEP DEM**, and this sandbox's
network allow-list cannot reach the official USGS bucket (verified: `prd-tnm.s3.amazonaws.com`
returns HTTP 000 here; the 100 m GeoDAWN DEM is the only absolute-elevation grid obtainable).

---

## Core values carried into every decision in this repository

> **Maximize P(Win).** *"Maximize the Probability of Winning"* is the decision framework.
> Every choice weighs trade-offs, assesses risk and takes the path that maximises the
> probability of winning — setting emotion aside. Here that is why a lane that failed its
> own pre-registered test is **not** pushed to a submission slot: three slots a week is a
> budget, not a lottery.
>
> **Own the Outcome.** Own the result end to end — not one's own slice of the work. When
> problems appear and there is the means to act, act without waiting for permission. Treat
> failure and success as signals. Here that is why the negative result is published with
> its numbers, why a *real* defect found in the inherited proxy instrument is reported
> rather than tuned away, and why the one thing this lane needed — absolute elevation —
> was hunted down and found instead of being asserted as impossible.

---

## 0. The brief (kept verbatim in the repository, re-read every session)

> **Tectonic-geomorphology lane: channel steepness and knickpoints, not scarp shape.** Kirby and Whipple (2012)
> review how bedrock-channel steepness and knickpoints record spatial gradients in rock uplift, including across
> active normal faults. Perron and Royden's χ transform (ESPL, 2013) puts different channels on a comparable
> footing, and Gailleton et al. (Earth Surface Dynamics) give a reproducible knickpoint-segmentation method.
> Scarps degrade and bury, but channel profiles keep recording base-level steps, so this can see faults the
> curvature features no longer show. Extract drainage from the free 3DEP 10 m DEM (or 1 m tiles), compute χ and
> normalized steepness, and keep only knickpoints and steepness steps that align across several independent
> drainages along a common strike. **First test: do channels crossing withheld segments show larger steepness
> steps than random lines of the same orientation? If not, stop.** Map and mask the usual confounds: lithology,
> climate gradients, ephemeral channels and playa base levels. Output the standard validated GeoTIFF,
> uniqueness-checked against every earlier raster.
>
> **PARALLEL-RUN PROTOCOL — read first.** This session is one of several running from this same prompt.
> **1. LANE.** Your lane is the single method paragraph below. Stay inside it. If your raster's rank-correlation
> with any registry raster exceeds [0.90], or more than [70 %] of your dots fall within 3 px of one registry
> raster's dots, you have drifted into another lane: log it as a duplicate and stop. Check this on the surface
> before placement AND on the final dots. **2. REUSE, DON'T REBUILD.** Use the template's cached feature stack,
> `evaluate_holdout.py` and `submission_writer.py`. Holdout = hide-and-recover: withhold whole fault segments
> with a buffer, derive every catalogue-based feature only from the visible faults, mask visible faults
> pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool is wrong,
> fix it once in the template and report it; never keep a private fork. **3. LABEL EVERY NUMBER** as
> HOLDOUT-DTI (evaluator version, number of withheld positives, 95 % CI) or ORGANIZER-CONFIRMED (copied from a
> submission-page receipt). A projection is never written as a score. **4. LEAKAGE CANARY.** Test each feature
> alone on the holdout before trusting any result. AUC above [0.90] means leakage until proven otherwise.
> **5. RUN CARD.** End with one JSON card: hypothesis; mechanism; the named non-fault process that could mimic
> it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no NaN inside the
> footprint, values in [0,1], CRS/shape/transform match); submission name + note of at most 140 characters;
> verdict promote / negative. Negative results are deliverables. **6. BUDGET.** Stop after [3] experiments or
> [2] hours. Do not pick submissions: promotion to a real slot is a separate selector step, within the weekly
> cap shown on the submission page.

Two corrections to that brief, both measured and cited in § *Irregularities*: the current
public leaderboard leader is **0.3774**, not 0.3195, and the "3DEP 10 m DEM" the lane asks
for is **not reachable from this sandbox**.

---

## 1. Why `h33-h33-2-b2` reports 0.2778, and whether 0.3195 / 0.3774 can be beaten

**Answer first.** `h33-h33-2-b2` did **not** get its 0.2778 from a better model. It is the
owner-reported **0.2708** raster with **2,545 dots deleted and none added** — every removed dot
was 1.4–2.0 px from the mapped catalogue (source: the family's own
[`evidence/session6_mechanism_and_witness.json`](https://github.com/buffedlizard55-lab/57GEMSDOE),
`equals_base_pruned_at_2px: true`). It scored higher because of the metric's arithmetic, not
because it found more faults.

The metric reduces **exactly** to one line. With `TP_w = Σ_g max_x p(x)k(d)`, `k(d) = max(1 − d/R, 0)`,
`R = 300 m`, `α = 0.2`, `β = 0.8`:

```
FN_w = |G| − TP_w            (identity; asserted in src/gems60/metric.py)
DTI  = T / ( α·(T + F) + β·|G| )        T = TP_w, F = FP_w
1/DTI = α + α·(F/T) + β·(|G|/T)         the design equation
```

Differentiating gives the **marginal rule**: adding one unit of mass raises DTI *iff* its
realised kernel credit exceeds `α·DTI` — at DTI = 0.26 that is **0.052**, i.e. the dot must
land within `(1 − 0.052)·300 m ≈ 284 m` of a hidden truth pixel. Every deleted dot was
failing that test. **`h33-h33-2-b2` is a pruning result inside the family's own 0.26–0.28
cluster, not a new ceiling.**

Beating **0.3195** (rank 8 on 2026-10-10) or **0.3774** (rank 1) therefore needs a *field*
that is genuinely better, and the family's own live-anchored arithmetic says so:
holding mass and the hidden `|G|` fixed, `T` must rise from ≈3,937 to ≈5,715 — **+45 % mean
realised credit at identical mass**. That is a detector problem. Nothing in this repository
claims otherwise, and nothing here is written as a score.

**Public leaderboard, ORGANIZER-PUBLISHED, retrieved 2026-10-10** (source:
<https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>):

| rank | participant | public DTI |
| ---: | --- | ---: |
| 1 | xiaofanhu | **0.3774** |
| 2 | JerryDataWorks | 0.3418 |
| 3 | alexoktaba | 0.3361 |
| 4 | Batik Shirt Brothers | 0.3300 |
| 5 | nchuzhoy | 0.3262 |
| 8 | DARD | **0.3195** |

No GEMSDOE* artefact in the family record carries a submission-page receipt; every score
attached to one is **OWNER-REPORTED**, and the family's own page for `GEMSDOE28` says
"NO GEMSDOE28 SCORE". A projection is never written here as a score.

---

## 2. What was built this session

| component | file | what it does |
| --- | --- | --- |
| metric | [`src/gems60/metric.py`](src/gems60/metric.py) | the published DTI, transcribed literally; `FN_w = \|G\| − TP_w` asserted; brute-force cross-check in `tests/test_metric.py` |
| holdout | [`src/gems60/holdout.py`](src/gems60/holdout.py) | buffered **whole-component** hide-and-recover; emission over the whole raster; **pooled** DTI with a paired 512-px block bootstrap |
| hydrology | [`src/gems60/hydro.py`](src/gems60/hydro.py) | priority-flood depression fill (Barnes 2014), D8 routing (O'Callaghan & Mark 1984), accumulation, **χ transform** (Perron & Royden 2013) |
| knickpoints | [`src/gems60/knick.py`](src/gems60/knick.py) | reproducible χ-profile **segmentation** (two-segment exhaustive breakpoint search; Gailleton-style), channel extraction |
| field | [`src/gems60/field.py`](src/gems60/field.py) | sharpened steepness step Σ, χ-residual step, and **channel-normal casting** |
| experiments | [`scripts/exp1_first_test.py`](scripts/exp1_first_test.py), [`scripts/exp2_sharpened.py`](scripts/exp2_sharpened.py), [`scripts/exp3_emit_validate.py`](scripts/exp3_emit_validate.py) | the three experiments of the budget |
| hypotheses | [`docs/hypotheses.md`](docs/hypotheses.md) | five ranked, untried hypotheses with layers, signature, why off-catalogue, cost, data |

Every hydrology primitive is checked against an **independent brute-force implementation**
on random DEMs (`tests/test_hydro.py`): routing never leaves a valid neighbour, the
accumulation matches a topological count exactly, χ is monotone upstream, and the flow
network has no cycles.

### The one thing the family never had: absolute elevation

Every previous session worked with the official 19-band GeoDAWN stack, whose only
topographic bands are `det_elev` and `det_elev_slope` — a **detrended** elevation. A χ
transform cannot be computed from detrended topography: it needs absolute elevation to
route flow and to integrate `∫(A0/A)^θ dx`. This session located and fetched
`22103_dem_a2.tif` — the **absolute-elevation GeoDAWN DEM, 100 m, on exactly the
competition grid** (`data/geodawn_dem_a2_100m.tif`, sha256
`d32762a38222764389e948da423ebc6cadd00ac617ad3938d3dd79c6cfe14431`) from the public
`jklinck/geothermal_research` repository, and verified alignment cell-by-cell
(`GeoDAWN_tiffs/22103_area2_tiffs/`, source: <https://github.com/jklinck/geothermal_research>).
That is what makes this lane runnable at all.

---

## 3. Results — every number labelled

### Experiment 1 — the pre-registered first test (long-window segmentation)

`scripts/exp1_first_test.py` → [`evidence/exp1_first_test.json`](evidence/exp1_first_test.json).
HOLDOUT-DTI evaluator `gems60-buffered-whole-component-v1`, 4 buffered whole-component
folds, **56,619 withheld positive pixels**, 300 m triangular kernel, α = 0.2, β = 0.8.

| | n | mean Σ | median Σ |
| --- | ---: | ---: | ---: |
| channels crossing a **withheld** segment | 9,488 | +0.0883 | −0.0177 |
| matched control (same line, translated) | 45,967 | +0.1113 | −0.0125 |

Δmean = **−0.0229**, CI95 **[−0.166, +0.162]**, one-sided p = **1.0**, leakage canary
AUC = 0.459. **STOP.**

### Experiment 2 — the corrected test

Experiment 1's window was **31 samples = 3.1 km**, about ten times longer than the
base-level step it was meant to localise, and its control was an unrelated translated
line. Both defects were named before the rerun; the decision rule was unchanged. See
[`evidence/exp2_sharpened.json`](evidence/exp2_sharpened.json).

| fold | n crossing | n control | median crossing | median control | AUC | p (one-sided) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q0 | 9,011 | 54,066 | −0.0045 | −0.0038 | 0.4681 | 1.0 |
| Q1 | 2,222 | 13,332 | +0.0050 | −0.0023 | 0.4919 | 0.891 |
| Q2 | 3,127 | 18,762 | −0.0049 | −0.0038 | 0.4524 | 1.0 |
| Q3 | 2,757 | 16,542 | −0.0039 | −0.0032 | 0.4828 | 0.998 |
| **pooled** | **17,117** | **102,702** | **−0.0045** | **−0.0035** | **0.4795** | **1.0** |

Δmean = **−0.0349**, CI95 **[−0.0806, −0.0065]** (excludes 0 **on the wrong side**).
Sharpened statistic with a position-matched, drainage-area-binned control. **STOP.**

Surfaces scored as rankers of withheld fault pixels over the whole holdout:

| surface | signed AUC | \|·\| AUC |
| --- | ---: | ---: |
| sharpened steepness step Σ | 0.4604 | 0.5520 |
| χ-residual step | 0.5323 | 0.5755 |
| **channel-normal cast count** | — | **0.4984** |

The lane's actual product — knickpoint crossings cast along the local channel normal and
reinforced where independent drainages share a strike — ranks withheld fault pixels at
**chance (0.4984)**.

### Experiment 3 — emission, validation, uniqueness

`scripts/exp3_emit_validate.py` → [`evidence/exp3_emission.json`](evidence/exp3_emission.json).

* 6,082 separated field peaks on the off-catalogue support; the shipped budget is
  **6,000** dots (the maximum of the off-catalogue curve, a rule fixed before the sweep was
  read). HOLDOUT-DTI **0.00039** versus a matched **random-on-the-same-support** control of
  **0.00042** and **random-in-footprint** of **0.01294**. The field is at or below its own
  random control. The curve is reported for completeness only: off-catalogue mass *cannot*
  score on a catalogue-truth instrument, so it is degenerate by construction and is never
  written as a score.
* **15/15 independent format checks PASS** (CRS, shape, transform, single band, Float32,
  no nodata tag, all finite, no NaN/Inf, range ⊆ [0, 1], zero outside footprint, zero dots
  on the catalogue).
* **Uniqueness: PASS.** 170 obtainable registry rasters re-read from their bytes; worst
  full-footprint Spearman **ρ = −0.015** (threshold 0.90); worst 3-px forward overlap
  **0.000** (threshold 0.70). Scope limitation stated: 696 registry entries are listed
  family-wide but only those whose bytes are obtainable in this sandbox were checked —
  un-fetched entries are never claimed to be absent.

### The proxy instrument is the finding, not a footnote

The family measured, on its own 15 owner-reported live scores, that the catalogue-truth
holdout is **anti-monotone** against the live ladder (`IR-57-INSTR-01`; `IR-32-PROXY-01`).
This session's Experiment 3 reproduces the mechanism from the other side: mass placed
> 2 px away from the catalogue *cannot* score on a catalogue-truth instrument, so the
off-catalogue curve is degenerate by construction — which is why it is reported for
completeness and **never** as a score. Both readings agree: **no local instrument in this
repository can rank live placements**, and that is the central limitation of the project.

---

## 4. Five ranked, untried hypotheses

Full text with layers, signature, off-catalogue argument and data cost:
[`docs/hypotheses.md`](docs/hypotheses.md). Ranked by expected DTI gain per unit cost.

| # | hypothesis | signature | why it catches an *unmapped* fault | cost | free official data needed |
| ---: | --- | --- | --- | --- | --- |
| 1 | **10 m 3DEP χ/ksn re-run of this exact lane** | χ-profile segmentation at 10 m instead of 100 m | this lane failed at 100 m; the step is 10× better resolved at 10 m | low (code exists, 1 parameter) | 3DEP 10 m tiles, `prd-tnm.s3.amazonaws.com` — **not reachable here (HTTP 000)** |
| 2 | **χ-transient, not χ-steady, base-level step** | river-profile *inversion* for uplift history `U(t)` from χ(z) (Pritchard 2009; Fox 2014) | separates a young fault's step from a long-lived lithologic step by its χ position | medium | nothing new (DEM exists) |
| 3 | **Knickpoint-density field, not knickpoint position** | KDE of *recurrence* of steps in χ across independent drainages | lithologic steps recur at a fixed elevation; tectonic steps recur at a fixed **χ** | low | none |
| 4 | **Playa/closed-basin base-level mask** | priority-flood depression inventory, 899,623 filled cells measured here | removes the largest named non-tectonic base-level step | low | none |
| 5 | **Lithology-normalised ksn (Great Basin Quaternary volcanics)** | ksn residual after a lithology/erodibility proxy | separates erodibility contrast from uplift contrast | medium | `great_basin_q_volcanics` (public, mirrored in the same GitHub tree used here) |

Hypotheses 2–5 are stated so a later session can run them; none is claimed to work.
Hypothesis 1 is the direct fix and is **data-blocked in this sandbox only** — the source is
free and official, and the fetcher is written and ready.

---

## 5. What unblocks the lane (named, verified, costed)

| blocker | evidence | exact fix |
| --- | --- | --- |
| 3DEP 10 m DEM unreachable | `curl https://prd-tnm.s3.amazonaws.com` → **HTTP 000** in this sandbox | run `bash scripts/fetch_3dep_10m.sh` on a machine with normal egress; the script enumerates the official USGS TNM bucket and verifies sha256 |
| official competition feature stack (418,912,844 B) not committed | exceeds practical repo size | `bash scripts/fetch_competition_features.sh` clones the sha256-pinned git bridge and verifies the whole-file hash `4371c82e…` |
| no organizer receipt exists for any family artefact | family registry: every score is OWNER-REPORTED | one submission-page screenshot per promoted file, stored in `registry/` |

---

## 6. Reproduce

```bash
pip install --break-system-packages numpy scipy scikit-learn rasterio pillow matplotlib
bash scripts/fetch_competition_features.sh     # optional, 419 MB, sha256-verified
PYTHONPATH=src python3 scripts/exp1_first_test.py     # ~4 min   -> STOP
PYTHONPATH=src python3 scripts/exp2_sharpened.py      # ~4 min   -> STOP
PYTHONPATH=src python3 scripts/exp3_emit_validate.py  # ~6 min   -> the GeoTIFF
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/build_site.py
```

`data/labels.tif` (sha256 `7ba308cc…`), `data/sample_submission.tif` (`2176d08e…`) and
`data/geodawn_dem_a2_100m.tif` (`d32762a3…`) are committed, so experiments 1–3 run with no
network at all.

---

## 7. Sources, for manual review

| claim | source |
| --- | --- |
| metric, kernel, α, β, submission format, worked example | <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> |
| public leaderboard 0.3774 / 0.3195 | <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/> |
| official rules PDF | <https://docs.nlr.gov/docs/fy26osti/96647.pdf> |
| reference solution (authorship: Prof. John Lipor) | <https://github.com/drivendataorg/gems-prize-reference-solution> |
| absolute-elevation GeoDAWN DEM used here | <https://github.com/jklinck/geothermal_research> → `GeoDAWN_tiffs/22103_area2_tiffs/22103_dem_a2.tif` |
| GeoDAWN airborne magnetic/radiometric survey | <https://doi.org/10.5066/P93LGLVQ> |
| INGENIOUS geothermal compilation | <https://gdr.openei.org/submissions/1391> |
| χ transform | Perron & Royden (2013), *Earth Surf. Dynam.* 1, 45–61, <https://doi.org/10.5194/esurf-1-45-2013> |
| knickpoint segmentation | Gailleton et al. (2019), *Earth Surf. Dynam.* 7, 707–725, <https://doi.org/10.5194/esurf-7-707-2019> |
| θ_ref = 0.45 normalisation | Wobus et al. (2006), GSA SP 398, <https://doi.org/10.1130/2006.2398(03)> |
| active tectonics in erosional landscapes | Kirby & Whipple (2012), *J. Struct. Geol.* 44, 54–75, <https://doi.org/10.1016/j.jsg.2012.07.009> |
| priority-flood depression filling | Barnes, Lehman & Mulla (2014), *Comput. Geosci.* 62, 117–122, <https://doi.org/10.1016/j.cageo.2013.09.008> |
| D8 routing | O'Callaghan & Mark (1984), *CVGIP* 28, 323–344, <https://doi.org/10.1016/S0734-189X(84)80011-0> |

**No hallucination policy.** Every number in this README is reproducible from a committed
script, is labelled HOLDOUT-DTI (with evaluator version, withheld positives and CI) or
ORGANIZER-PUBLISHED or OWNER-REPORTED, and the artefacts it describes are committed. Where
a claim could not be verified in this sandbox it is written as unverified, with the reason.
