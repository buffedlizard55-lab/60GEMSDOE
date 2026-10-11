# Why the 0.2778 champion scores what it scores — and what it takes to beat it

Session H66 (2026-10-11, `arena/b219bfe1-60gemsdoe`). Every number below is either
**byte-measured in this repository** (file + sha256 given) or **ORGANIZER-CONFIRMED**
(a public leaderboard row) or **algebra from the published metric** (pinned by
`tests/test_metric.py`). Nothing here is a projection presented as a score.

## 1. The metric (verified, pinned by test)

Source of truth: [competition page 967 — Performance metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
(read twice 2026-10-04; the published worked example TPw=3.00, FPw=1.89, FNw=2.00 → 0.60 is
reproduced bit-for-bit in `tests/test_metric.py`). Rules PDF:
[NLR OT-6A50-96647](https://docs.nlr.gov/docs/fy26osti/96647.pdf), DOI 10.2172/3818146.

With R = 300 m, α = 0.2 (false positive), β = 0.8 (false negative), triangular kernel
k(d) = max(1 − d/R, 0):

    DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw)

and the identity checked against brute force in `src/gems60/metric.py`:

    DTI = T / (0.2·(T + S − M) + 0.8·|G|)          (T = credited mass, S = total mass,
                                                   M = Σ p(x)·max_g k, |G| = hidden truth pixels)
    1/DTI = 0.2 + 0.2·(S−M)/T + 0.8·|G|/T

Three consequences do all the work:

1. **Mass next to the mapped catalogue can never earn credit.** The hidden truth is, by
   competition design, faults *not* in the USGS/INGENIOUS catalogue, and the evaluator masks
   the visible faults. A dot on or beside a mapped fault pays the 0.2 false-positive tax on
   every pixel it wastes and collects nothing.
2. **A dot earns credit only within 300 m (3 px) of a hidden truth pixel**, with credit
   1 − d/300 m. The whole game is credit per unit of mass.
3. **Break-even bar**: an added dot with credit c and wasted mass f helps iff
   `c·(1 − 0.2·DTI) > 0.2·DTI·f` (module docstring). At DTI = 0.2778 the bar is ≈ 0.0556
   credit/dot. The group measured the same bar live at **0.05416**
   (`evidence/h33_validation.json` → `tau_live_credit_per_added_dot`). Two independent
   routes, one number.

## 2. What the champion file actually is (byte-measured, this session)

File: `docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`,
sha256 `c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9`
(re-measured 2026-10-11, H66).

| property | measured value |
|---|---|
| container | single band, float32, **no nodata tag**, all 12,279,160 cells finite |
| values | min 0.0, max 1.0; positive cells are all exactly 1.0 (binary dots) |
| grid | EPSG:32611, 3730×3292, transform (100, 0, 243350, 0, −100, 4508550) — matches the submission format |
| dots | **37,654** |
| outside footprint | 0 |
| distance to mapped catalogue | min **223.6 m**, median **1,964.7 m**, only **5.8 %** within 300 m |
| relation to parent d2-8 (44,090 dots, owner-reported 0.2600) | **6,436 dots removed, 0 added**; every removed dot 100–200 m from the catalogue (median 100 m) |

The live ladder (ORGANIZER-CONFIRMED where a public board row matches; the group's rows are
identifiable on the public board — `registry/leaderboard_history.jsonl`, snapshot 2026-10-04):

| step | file | dots | live score | board corroboration |
|---|---|---|---|---|
| 1 | d2-8 | 44,090 | 0.2600 (owner-reported) | board rows `wbg1` 0.26 and `SDCF9` 0.26 |
| 2 | h27-4-r1-solo | 40,199 | 0.2708 (owner-reported) | board row `smashi34` 0.2708 |
| 3 | **h33-2-b2** | 37,654 | **0.2778** (owner-reported; no matching board row in the 10-04 snapshot — file built 10-04T22:00Z, after the snapshot) | — |

Each step is **pure deletion of catalogue-adjacent mass**. No new information was added;
the score rose 0.2600 → 0.2708 → 0.2778 (+0.0070 over ~10,300 deleted dots).

## 3. Why that is a high score

Inverting the metric on the measured pair D2.8 → H27-4 (GEMSDOE32 forensics,
`evidence/h33_validation.json`, with the family's |G| pins 12,226 / 12,691 hidden-truth
pixels): TPw = 5,073.3, mean credit per dot **0.1262**, implied weighted recall
**≈ 0.415** at |G| = 12,226. The same inversion on h33-2-b2 (DTI 0.2778, S = 37,654) gives
T ≈ 4.8–5.1k credited mass, i.e. **≈ 39–41 % weighted recall of the hidden truth** at a
cost of 37.6k dots. Every marginal dot earns ≈ 0.127 credit against a 0.0556 break-even —
the file sits on the metric's mass/precision frontier: it covers ~40 % of the hidden
faults, it wastes nothing on the catalogue, and each dot is ~2.3× above break-even.

So: **0.2778 is not a physical discovery; it is a budget point.** The detector underneath
(the "dotted h19-5" lineage: multi-line structural corroboration with a power-law dot
budget, GEMSDOE19/24/25/31/32 sites) is good; the last 0.018 of the score came from
*deleting* mass the metric taxes.

## 4. Can it be beaten — exactly what is required

The algebra (`1/DTI = 0.2 + 0.2F/T + 0.8|G|/T`) fixes the requirements at the champion's
operating point (|G| ≈ 12.2–12.7k, S = 37.6k):

| target | requirement at fixed mass | requirement at fixed credit |
|---|---|---|
| 0.30 | recall ≈ 45 % | ~31k dots |
| 0.38 (board top 2026-10-04: 0.3262/0.3222) | recall ≈ 55 % | ~25k dots |
| 0.4133 (board top, manual rendered-page read 2026-10-11 by session arena/970443fc: public row #1 xiaofanhu, 16 submissions — no file attribution) | recall ≈ 58–60 % | ~23k dots |

So beating 0.2778 requires **new information about where unmapped faults are** (recall up)
or a far sparser file with equally productive dots (mass down). Neither is achievable by
thinning, rescaling or post-hoc optimisation of the existing files — the family exhausted
that ladder live (0.26 → 0.2778), and every H32/H33 addition arm scored below the base on
the LM instrument (`evidence/h33_validation.json`).

**Why no local instrument can certify a win (measured, not asserted):**

1. The catalogue hide-and-recover holdout *inverts* live orderings: on the pooled
   catalogue folds the champion scores **0.0041** while dotted-d2.8 scores **0.0862**, yet
   live ranks 0.2778 > 0.2600. The holdout truth is the visible catalogue; the leaderboard
   truth is off-catalogue faults. A catalogue-segment holdout rewards proximity to mapped
   faults — the exact region where mass must *not* go.
2. 16GEMSDOE measured **ρ = +0.17** between its off-catalogue instrument and the live board.
3. The family's off-catalogue emission sample is **anti-correlated with relief** (AUC 0.90
   for local relief / slope p90): maximal-separation thinning spreads dots into basin
   floors, so every topography-based lane has been graded on a sample biased against it.
   Repair (relief-stratified thinning) is the family's ranked next step, not yet done.

## 5. The ranked path (registry, with the honest costs)

1. **Instrument repair first** (hypothesis #1, `docs/hypotheses.html`): relief-stratified
   thinning of the off-catalogue sample, then re-score every registry raster. Until then no
   "no skill" verdict — including the knickpoint lane's — is fully trustworthy.
2. **H65-2 mountain-front piedmont junction at 10 m** (Bull & McFadden 1977): the
   hillslope/fan slope break is where range-bounding faults sit *even when the scarp is
   buried*; weight by front sinuosity. One new reduction band in the committed `dem10-chi`
   runner (~minutes of runner time). Registered as the next session's first experiment.
3. **H65-3 fan-apex alignment + fan-head trenching** (confinement jump ≥ 3×, ≥ 3 apices on
   one strike).
4. **H65-4 divide asymmetry of tilted blocks** (χ across divides; Willett et al. 2014,
   Science 343, doi:10.1126/science.1248765; Forte & Whipple 2018, EPSL 493, 102–117,
   doi:10.1016/j.epsl.2018.04.026) — needs a global-datum χ.
5. **H64-A three-slot identification experiment**: anchor + λ=0.5 rescale + null-add
   measures T, K and F *exactly* (1/DTI(λ) is linear in 1/λ). Costs two slots, gains no
   score directly — it replaces every projection in this family with a measurement.
   Operator decision required.
6. **H65-5 knickpoint recurrence in χ** (Crosby & Whipple 2006, Geomorphology 82, 16–38) —
   ranked low: H65-1 measured 10 m knickpoint support only 1.04× enriched near mapped
   faults and 1.19× for large steps.

## 6. The knickpoint lane, closed out honestly (this session's lane)

Five independent implementations of the brief's first test, all on the record:

| run | substrate | first test | pooled holdout (evaluator, n withheld) | verdict |
|---|---|---|---|---|
| 60GEMSDOE lane-1 | 100 m det_elev proxy | 4/5 folds positive, 1/5 CI>0 | 0.0108 vs random 0.0268 (14,089) | NEGATIVE |
| H60-A corridor | 100 m 3DEP-reduced | **+0.1089 [0.0586, 0.1569]** (323 components) | 0.01639 vs random 0.03908 (gems57-pooled-hide-v2, 22,641) | NEGATIVE |
| chi-cast | 100 m GeoDAWN abs. elev | STOP twice (AUC 0.459 / 0.4795) | 0.00039 vs matched random 0.00042 | NEGATIVE |
| GEMS61 thermal | 100 m + INGENIOUS thermal | — | 0.002495 [0.0015, 0.0035] (36,439); loses to mass-matched random | NEGATIVE |
| **H65-1** | **10 m native 3DEP** | **+0.0326 [−0.0144, +0.0790] INCONCLUSIVE** (262) | 0.01158 [0.0084, 0.0146] vs random 0.03908 (22,641) | NEGATIVE (stop) |
| **H66-6 (this session)** | 10 m, **brief-mandated confound masks applied to the statistic** + litho arm split | **+0.0404 [−0.0029, +0.0871] INCONCLUSIVE** (239; arms T +0.0030 n=174, L +0.0696 n=14, both INCONCLUSIVE) | **0.00960 [0.00654, 0.01307]** vs random 0.03908, paired −0.02948 [−0.0339, −0.0249] (gems57-pooled-hide-v2, 22,641) | **NEGATIVE (stop)** |
| H66-1/H66-2 (parallel, `arena/970443fc`) | 10 m chi/ksn, both-limb variant | **−0.0860 [−0.1372, −0.0220]** vs off-catalogue truth (86 segments) | INSTRUMENT-DTI 0.00913 vs random 0.07253 (paired −0.06339) | **NEGATIVE (stop)** |
| H67-1 (`arena/7085de4f`, PR #17) | 10 m bedrock-subtracted Δksn step + 4-confound mask | **claims +0.4251 [+0.2253, +0.6273] PROCEED** (262) | **claims 0.065739 [0.055715, 0.076201]** (22,641) | **claimed PASS/promote — contradicted the STOP file (flagged IR-H66C-STOPCONFLICT-01 by session arena/b219bfe1); promotion REVERSED (promoted=False) by arena/a856d257, PRs #19/#20; remains a research artifact, not a cleared submission** |

The lane's named confounds are measured to dominate: step-bearing 10 m channels are only
1.19× (steps ≥ ln2) / 1.04× (knickpoints) enriched within 300 m of the catalogue
(`evidence/h65_diagnostics.json`) and sit *lower* in local relief (median −16 m vs a
20 km median) than the catalogue (+7 m) — the signature of lithologic contacts,
channel-head transitions and playa base levels, not fault crossings.
**H66-6 was the last mandated step of the lane method (mask the confounds, then test);
its result — masked first test still INCONCLUSIVE (+0.0404, CI straddles 0) and the pooled
holdout (0.00960) still below the mass-matched random control (0.03908) — is recorded in
`evidence/h66c_runcard.json`. Masking the confounds moved the first-test mean only from
+0.0326 (H65-1) to +0.0404: the confounds did not create the (non-)signal, and the lane is
closed: every independently confirmed run is negative (8/8); the sole positive claim — H67-1 of session `arena/7085de4f` — contradicted the STOP registration (IR-H66C-STOPCONFLICT-01) and its promotion was reversed by PRs #19/#20, so it stands as an uncorroborated research artifact.**

## 7. Irregularities carried forward

* **IR-66-E1MASK-01**: `run_lane60.py`'s first test never applied the confound masks to its
  statistic (they only entered candidate preparation). Fixed once in the shared tool
  (backward-compatible flags); H66-6 is the first masked first test.
* **IR-66-FEED-01**: the scheduled feed refresh runs succeed but the public leaderboard
  table no longer parses (client-side rendering); the feed's board rows froze at 2026-10-04
  while the site kept printing them. Resolution (session arena/970443fc, merged as PRs
  #15/#16): the feed now makes **no automated request to the competition host**; the board
  top was re-read by manual rendered-page fetch and pinned as
  `registry/leaderboard_snapshot_2026-10-11.json` (public rows only, no file attribution:
  #1 xiaofanhu 0.4133, #2 JerryDataWorks 0.3418, #3 alexoktaba 0.3361), which corroborates
  H65's same-day 0.4133 read.
* **IR-66-CLIM-01**: the brief's climate-gradient confound (Sierra orographic rain shadow)
  could not be masked — no free official gridded precipitation product is reachable from
  the sandbox egress allowlist. The 40 km blockwise z-score de-trends part of it. Named
  source for a future session: PRISM (https://www.prism.oregonstate.edu/), free academic
  access.
* **IR-65-LB-01** (carried): the brief's "0.3774" and "0.3195" board-top figures are stale
  or mid-board values; 0.3195 was rank #3 on 2026-10-04 (DARD).

## 8. Manual-review links (official)

* Problem + metric: <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>
* Leaderboard: <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>
* Rules PDF: <https://docs.nlr.gov/docs/fy26osti/96647.pdf> (DOI <https://doi.org/10.2172/3818146>)
* Reference solution: <https://github.com/drivendataorg/gems-prize-reference-solution>
* 3DEP 10 m (public domain): <https://www.usgs.gov/3d-elevation-program>, tiles
  `https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/` (18 tiles
  sha256-pinned in `data/external/dem10_chi_100m.manifest.json`)
* GeoDAWN geophysics: <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>
* INGENIOUS catalogue: <https://gbcge.org/current-projects/ingenious/>
* Kirby & Whipple 2012 (tectonic inferences from fluvial incision): <https://doi.org/10.1016/j.jsg.2012.07.009> (J. Struct. Geol. 44:54–75)
* Perron & Royden 2013 (χ transform): <https://doi.org/10.1002/esp.3302> (ESPL 38:570–576)
* Gailleton et al. (knickpoint segmentation): <https://doi.org/10.5194/esurf-7-211-2019> (ESurf 7:211–230 — citation as corrected in-repo 2026-10-11; DOI to be re-checked at the publisher by a human with egress)
* Tversky index background: <https://en.wikipedia.org/wiki/Tversky_index>
* CRS: <https://epsg.io/32611>
