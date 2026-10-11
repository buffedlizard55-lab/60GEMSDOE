# 60GEMSDOE — DOE GEMS Prize Challenge · tectonic-geomorphology lane

**Read this README at the start of every session.** It contains the standing request (verbatim), the
current permission status, the reproduced method, the verified data provenance, and what the next
session must do.

---

## 0. Permission banner (unmistakable, mirrors the site)

| question | answer (from `evidence/run_card_current.json`, rendered on the site) |
|---|---|
| Is a generated GeoTIFF present in this repo? | **YES** — `downloads/gems60-h60a-knick-corridor-40000-20261011T011509Z-372c9d7dd204-zeros.tif` (40,000 dots, sha256 `e9dbbb64e1d52b3b2786df53b79699af098222f4a99d9dcc73e658de15ca88cc`) |
| OK to **download** for research / education? | **YES** — format-valid, every cell finite and in [0, 1], zero dots on mapped catalogue faults |
| OK to **submit** to the competition? | **NO** — verdict `negative`. Two independent pre-registered gates fail (see §2) |
| Weekly slots spent by this session | **0** — promotion is a separate selector step |

The two failing gates, both declared in `evidence/preregistration_h60a.json` *before* any experiment
ran:

1. `beats_best_control_paired_ci` — HOLDOUT-DTI 0.01639 [0.01223, 0.02061] **loses** to random mass
   (0.03908) and to the distance-to-visible control (0.19073) at the same budget.
2. `uniqueness_literal_or_sparse_clear` — the literal gate fires: 60 of 655 registry rasters contain
   > 70 % of this candidate's dots within 3 px (worst 1.0). The content is nevertheless novel by every
   discriminating statistic (worst ρ = 0.0209, worst reverse overlap = 0.1728, worst Jaccard = 0.0116,
   no byte- or pixel-identical prior); the firing is one-directional containment by denser priors
   (IR-60-GATE-01). The protocol is literal and fail-closed, so it is logged as a duplicate and the
   file is **not** cleared.

The site renders those two permissions **from the run card**, never from prose, so a page cannot
advertise a decision its receipt does not record.

---

## 1. Standing request (verbatim, preserved as the project's definition of done)

> Review the repo.
>
> THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!
>
> MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. DO NOT COPY A PREVIOUS SUBMISSION UNLESS
> IT'S FOR LEARNING AND EDUCATION. BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION. IT MUST BE OBVIOUS
> WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.
>
> There should be an easy to download submission tif file as described by the prompt. Read the entire
> prompt.
>
> Tectonic-geomorphology lane: channel steepness and knickpoints, not scarp shape. Kirby and Whipple
> (2012) review how bedrock-channel steepness and knickpoints record spatial gradients in rock uplift,
> including across active normal faults. Perron and Royden's χ transform (ESPL, 2013) puts different
> channels on a comparable footing, and Gailleton et al. (Earth Surface Dynamics) give a reproducible
> knickpoint-segmentation method. Scarps degrade and bury, but channel profiles keep recording
> base-level steps, so this can see faults the curvature features no longer show. Extract drainage from
> the free 3DEP 10 m DEM (or 1 m tiles), compute χ and normalized steepness, and keep only knickpoints
> and steepness steps that align across several independent drainages along a common strike. First
> test: do channels crossing withheld segments show larger steepness steps than random lines of the
> same orientation? If not, stop. Map and mask the usual confounds: lithology, climate gradients,
> ephemeral channels and playa base levels. Output the standard validated GeoTIFF, uniqueness-checked
> against every earlier raster.
>
> PARALLEL-RUN PROTOCOL — read first. This session is one of several running from this same prompt.
>
> 1. LANE. Your lane is the single method paragraph below. Stay inside it. If your raster's
>    rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots fall
>    within 3 px of one registry raster's dots, you have drifted into another lane: log it as a
>    duplicate and stop. Check this on the surface before placement AND on the final dots.
> 2. REUSE, DON'T REBUILD. Use the template's cached feature stack, `evaluate_holdout.py` and
>    `submission_writer.py`. Holdout = hide-and-recover: withhold whole fault segments with a buffer,
>    derive every catalogue-based feature only from the visible faults, mask visible faults
>    pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool
>    is wrong, fix it once in the template and report it; never keep a private fork.
> 3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or
>    ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a
>    score.
> 4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any result. AUC above
>    [0.90] means leakage until proven otherwise.
> 5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault process that could
>    mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no
>    NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission name + note of
>    at most 140 characters; verdict promote / negative. Negative results are deliverables.
> 6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a real
>    slot is a separate selector step, within the weekly cap shown on the submission page.
>
> Also required by the owner: 3–5 new candidate geological hypotheses ranked by expected DTI
> improvement and implementation cost; validate the top candidate on the spatially-blocked holdout
> before touching a weekly submission slot; work line by line from official verified trusted sources
> with links for manual review; no manual input; flag irregularities; no hallucinations; an easy
> GitHub Pages site whose executive summary explains exactly how to submit; a unique submission name
> and a ≤140-character note; three implementation/review passes; then open a pull request and merge it,
> with suggestions for the next session and the limitations in the way.
>
> Core values: **Maximize P(Win)** — weigh tradeoffs, assess risk, choose the path that maximizes the
> probability of winning. **Own the Outcome** — own results end to end, act without waiting for
> permission, treat failure and success as signals, stay accountable to the final outcome.

Owner-reported context quoted in the request (public board / sibling sites, **not** receipts):
group best 0.2778 (`h33-h33-2-b2`, GEMSDOE32), board leaders quoted at 0.3195 and 0.3774. Every
one of those numbers is `OWNER-REPORTED` or public-board context in this repository's records; this
session produced **no** organizer receipt.

---

## 2. What this session did (three experiments, budget respected)

| # | experiment | script | receipt |
|---|---|---|---|
| E1 | **Mandated first test** — do channels crossing *withheld* fault segments show larger `ksn` steps than random lines of the same orientation and length? | `scripts/run_lane60.py` | `evidence/h60a_e1_first_test.json`, `evidence/h60a_holdout.json` |
| E2 | **Leakage canary** — each feature alone, `max(AUC, 1−AUC) > 0.90` ⇒ leakage | `scripts/run_lane60.py` | `evidence/h60a_holdout.json` → `canary` |
| E3 | **Pooled HOLDOUT-DTI** of the lane emission vs three controls, paired spatial-block bootstrap | `scripts/run_lane60.py` | `evidence/h60a_holdout.json` → `pooled_binary`, `pooled_surface` |

Production build + uniqueness audit: `scripts/build_submission60.py`, `scripts/check_uniqueness60.py`
→ `evidence/h60a_submission_build.json`, `evidence/h60a_uniqueness.json`,
`evidence/uniqueness_rows.jsonl` (one row per registry raster), `evidence/run_card_current.json`.

### E1 — the mandated first test (receipt: `evidence/h60a_e1_first_test.json`)

Do channels crossing **withheld** fault segments show larger steepness steps than random lines of the
same orientation and length, measured inside the same hide-and-recover fold, with visible faults
masked pixel-exactly and the whole transect kept ≥ 3 px away from any withheld or visible fault?

| quantity | value |
|---|---|
| withheld fault components compared | **323** |
| mean paired difference (crossing − random same-orientation), log-units of `ksn` | **+0.1089** |
| 95 % bootstrap CI over components (1000 draws, seed 60101) | **[+0.0586, +0.1569]** |
| components with a positive difference | **59.4 %** |
| verdict declared in advance | **PROCEED** (CI excludes zero) |

A ~11 % higher `ksn` step on channels that cross a withheld fault than on random lines of the same
orientation is a real but *modest* signal: it is large enough to keep the lane alive and far too small
to carry a submission on its own. That asymmetry is the honest reading, and it is why the emission is
built from corroborated knickpoints (≥ 3 independent channel branches along a common strike) rather
than from the raw step field.

### E3 — pooled HOLDOUT-DTI, 4 quadrant folds × 2 seeds (receipt: `evidence/h60a_holdout.json`)

Evaluator `gems57-pooled-hide-v2`, α = 0.2, β = 0.8, 300 m triangular kernel, 159 physical spatial
clusters, 1000 paired bootstrap draws (seed 60101), **22,641 withheld positive pixels**, every arm at
the same 40 k/5.17 M density budget, every dot ≥ 200 m off the visible catalogue.

| arm | HOLDOUT-DTI | 95 % CI | paired Δ vs lane |
|---|---|---|---|
| `distance_only` (control) | **0.19073** | [0.18200, 0.19965] | −0.17434 [−0.18319, −0.16583] |
| `random_mass_control` | 0.03908 | [0.03568, 0.04231] | −0.02269 [−0.02740, −0.01768] |
| `ksn_only_no_alignment` | 0.03118 | [0.02602, 0.03576] | −0.01479 [−0.02061, −0.00860] |
| **`lane_h60a` (this session)** | **0.01639** | [0.01223, 0.02061] | — |

Continuous-surface arm (same folds, mass not dots): lane 0.01377 [0.01075, 0.01683] vs
`distance_only` 0.05942 [0.05625, 0.06264], paired Δ −0.04566 [−0.04922, −0.04228].

**Verdict: NEGATIVE.** The lane loses to *every* control, including uniformly random mass at the same
budget, on both the dot arm and the surface arm, with paired 95 % CIs that exclude zero. This is a
deliverable, not a failure to report: the pre-registered promotion gate ("must beat the best
comparable control") is not met, so `okay_to_submit = false` and the file is released for research and
education only. Note also that `distance_only` is **not** a submittable alternative — the leakage
canary flags it at AUC 0.924 (below), and a distance-to-catalogue prior is what every sibling
repository already ships.

**Why the first test passed and the emission still lost.** E1 says channels crossing a withheld fault
step ~11 % harder in `ksn` than random same-orientation lines — a real, CI-clean effect. But 11 % of a
log-ratio is a *weak* per-pixel signal, and the hide-and-recover holdout's truth is withheld
**catalogue** segments, which sit next to their own visible continuations. Any field that concentrates
mass in steep bedrock reaches therefore spends its budget away from the truth this instrument can see,
while a distance-to-visible prior spends it exactly on the truth. The lane's own field is also nearly
undiscriminating on this instrument (`lane_p` canary AUC 0.518 ≈ chance). Two readings are consistent
with the data and they cannot be separated inside this sandbox: (a) knickpoint corridors genuinely do
not predict the catalogue's own gaps, or (b) they predict *off-catalogue* structure that this proxy
holdout is blind to (IR-60-PROXY-01). Reading (b) is the lane's whole premise and it is untestable
here without an organizer receipt.

### E2 — leakage canary (each feature alone, `max(AUC, 1−AUC) > 0.90` ⇒ leakage)

| feature | worst AUC | status |
|---|---|---|
| `knickpoint_step` (the lane signal) | 0.5861 | pass |
| `chi` | 0.5625 | pass |
| `ksn` | 0.5593 | pass |
| `drainage_area` | 0.5268 | pass |
| `lane_p` (final surface) | 0.5181 | pass |
| `dist_to_visible` (deliberate control) | **0.9243** | **LEAKAGE FLAG** |

The control was included on purpose: on a hide-and-recover fold the withheld segment abuts its own
visible continuation, so a distance-to-visible feature *must* leak. Its flag proves the canary has
power, and it is the reason the `distance_only` control's 0.19073 is reported as an upper bound of the
instrument, never as a candidate.

### Uniqueness against every earlier raster (receipts: `evidence/h60a_uniqueness.json`, `evidence/uniqueness_rows.jsonl`)

Complete scan: **655 of 655** pinned registry rasters from 56 sibling repositories, every row
sha256-verified (651 fetched over HTTPS, 4 recovered by blob SHA from `55GEMSDOE`'s git history).

| statistic | value | limit | status |
|---|---|---|---|
| worst full-footprint Spearman ρ | **0.02088** | 0.90 | clear by a factor of 43 |
| worst ρ among sparse submission-like priors (606 rows) | 0.01802 | 0.90 | clear |
| worst forward 3-px dot overlap | **1.00000** (60 rows fire) | 0.70 | **FIRES** |
| worst reverse overlap (their dots within 3 px of mine) | 0.17284 | — | diagnostic |
| worst Jaccard of dot sets | 0.01158 | 0.50 (diagnostic only) | clear |
| byte-identical / pixel-identical to any prior | no / no | — | clear |
| `unique` (literal, fail-closed) | **false** | — | `stop_required = true` |

Method note: ρ is screened on a fixed 400,000-cell sample (seed 6060, same sample for every raster)
and recomputed exactly on all 5,167,373 footprint cells whenever the screen exceeds |0.70|; the fast
overlap path is asserted equal to the shared `gems57.uniqueness.dot_overlap` on 12 rasters
(max absolute difference **0.0**).

### Method, line by line

1. **Data.** `scripts/prepare_data.py` (shared tool, reused unmodified) verifies eight hash pins. The
   19-band stack was re-assembled from five hash-pinned parts of the public bridge
   `buffedlizard55-lab/6GEMSDOE@e2fe3f4` and its digest matched the pin
   `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5`
   (`evidence/data_preparation.json`). Grid: EPSG:32611, 3730 × 3292, transform
   `(100, 0, 243350, 0, −100, 4508550)`, footprint 5,167,373 cells, catalogue 60,988 cells.
2. **Hydrology on band 12 `det_elev`** (`src/gems60/geomorph.py`, 17 unit tests in
   `tests/test_geomorph.py`): local NaN repair (3,061 cells) → priority-flood depression filling with
   an ε-gradient on flats → D8 steepest descent (out-of-footprint = wall, footprint edge = outlet) →
   exact topological upslope area → **χ = Σ ds·(A₀/A)^θ** (Perron & Royden 2013, θ = 0.45, A₀ = 1 m²)
   → **ksn = S·(A/A₀)^θ** (Wobus et al. 2006).
3. **Knickpoints.** Fixed-window breakpoint detector: `step = log((ksn_up + c)/(ksn_down + c))` with
   `c = 0.5` and winsorisation at `log 10`, `ksn_up/ksn_down` averaged over 5 cells (500 m) of the
   main stem upstream and downstream. Declared as a deliberately simple, reproducible stand-in for the
   statistical segmentation of Gailleton et al. (2019) — **not** presented as their method.
4. **Confounds masked** (pre-registered, `evidence/preregistration_h60a.json`): climate/regional
   gradient → magnitude z-scored inside 40 km blocks; playa / closed-basin base level → priority-flood
   raise > 20 m (542,309 px); lithology / basin fill → `depth_to_base_surf` > p90 (516,432 px);
   ephemeral / clay-rich alluvium → `cond_surf` > p95 (257,039 px); channel-hood → contributing area
   ≥ 20 cells (0.20 km²).
5. **Cross-drainage corroboration along a common strike.** Strike comes from the structure tensor of
   the **visible** catalogue only (σ = 600 m; regional modal strike as fallback). A candidate is kept
   only if its corridor (±600 m along strike, ±200 m across) contains knickpoints from **≥ 3
   independent channel branches**. Corroborated knickpoints are then re-expressed as strike corridors,
   because the predicted object is a fault *trace*.
6. **Emission.** 40,000 dots (the pre-registered budget), top-ranked inside the footprint with every
   dot ≥ 2 px (200 m) off the mapped catalogue, ties broken by a seeded RNG so no raster-order
   artefact can enter. Written by the shared fail-closed `gems57.submission_writer` as a finite
   `[0,1]` float32 GeoTIFF (`-zeros` mode) plus a single-TIFF ZIP and a validator receipt.

### One shared-tool bug found and fixed here (rule 2: fix once, report)

`_dilate_window` in `scripts/run_lane60.py`: the mandated first test dilated a whole 3 M-cell fold
crop for every one of ~30,000 random transects, which made E1 two orders of magnitude slower than the
science requires. Fixed once in the shared lane driver (local-window dilation), not forked.

### One science bug found and fixed before any score was recorded

Independence was first implemented as *terminal-sink identity*. The northwestern Great Basin is
**internally drained**: 5.17 M cells share only 1,224 terminal sinks, so almost every candidate in a
corridor looked like "one drainage" and only 64 of 36,633 candidates passed the ≥ 3 rule. Independence
is now the **branch signature** (`geomorph.branch_signature`, identity of the cell 5 steps downstream):
same flow path within the corridor's own length scale ⇒ dependent. With the fix, 32,980 of 36,620
candidates are corroborated (median 6 independent branches, max 27). The superseded build
(`evidence/superseded/`, 35,107 dots) was never linked, never scored and is kept for audit only.

---

## 3. Reproduce

```bash
python3 scripts/prepare_data.py --fetch        # hash-verify pins, assemble the 19-band stack
python3 scripts/build_geomorph_features.py     # stage A: hydrology, chi, ksn, knickpoints (~65 s)
python3 scripts/run_lane60.py                  # stage B: E1 first test, canary, pooled HOLDOUT-DTI
python3 scripts/build_submission60.py          # stage C: surface -> dots -> validated GeoTIFF
python3 scripts/check_uniqueness60.py --candidate downloads/<file>.tif   # literal registry audit
python3 scripts/build_site60.py                # render docs/ from the receipts
python3 -m pytest tests -q                     # 17 geomorphology tests + shared template tests
```

Requirements: `numpy`, `scipy`, `rasterio`, `pytest` (CPU only; no GPU needed). Large rasters are
restored by hash into `.cache/` and are **never committed**.

---

## 4. Verified data provenance (manual review links)

| input | sha256 (first 16) | source | status |
|---|---|---|---|
| `training_features.tif` (19 bands) | `4371c82e3b8339b8` | bridge `buffedlizard55-lab/6GEMSDOE@e2fe3f4`, 5 parts, each hash-verified | hash-verified third-party bridge; **official origin not independently authenticated** |
| `labels.tif` / `existing_faults.tif` | `7ba308ccdc4418b3` | same bridge; byte-identical to each other | the public "labels" raster **is** the mapped-fault catalogue |
| `sample_submission.tif` | `2176d08e485aa2cd` | same bridge | grid/footprint template only |
| registry corpus (**655 of 655** rasters) | per-row pins | `evidence/registry_full_index.json` from `buffedlizard55-lab/57GEMSDOE` | 651 fetched by `scripts/fetch_registry_rasters.py` + 4 recovered by blob SHA from `55GEMSDOE` git history; every row sha256-verified |

External references for manual review (competition page, leaderboard, reference solution, OSTI 96647
PDF, USGS GeoDAWN DOI 10.5066/P93LGLVQ, GDR 1391, EPSG:32611, Tversky index, and the five
geomorphology papers) are tabulated on <a href="docs/science.html">docs/science.html</a>.

---

## 5. Irregularities flagged for review

| id | irregularity | consequence |
|---|---|---|
| IR-60-DATA-01 | The lane brief names the free USGS 3DEP 10 m / 1 m DEM. `usgs.gov` is **not** reachable from this sandbox (permitted hosts: github.com, api.github.com, codeload.github.com, pypi.org, files.pythonhosted.org, registry.npmjs.org). | The lane ran on band 12 `det_elev` of the given stack (100 m, detrended). A 3DEP-based re-run needs an unrestricted machine. |
| IR-60-CITE-01 | Literature DOIs and all competition/USGS pages could not be fetched here. | Citations are given for manual review and are labelled as not machine-verified in this session. |
| IR-60-GATE-01 | The inherited literal uniqueness rule ("`>70%` of my dots within 3 px of one registry raster's dots") fires trivially against **dense universal-support priors** in the family corpus: a prior whose positive support covers essentially every allowed cell overlaps any non-empty candidate. | Both the literal result and the sparse-submission-like subset are reported; the run card states which gate fired and why. Same structural finding the sibling session logged. |
| IR-60-API-01 | `gh api` REST calls hit the shared token's rate limit ("API rate limit exceeded for user ID 309556078"), so `prepare_data.py --fetch` could not download the feature parts. | Worked around with the git protocol (`--filter=blob:none` + sparse checkout of `data/bridge/`), which does not consume REST quota. Hashes verified after assembly. |
| IR-60-PROXY-01 | The hide-and-recover holdout's truth **is** the given catalogue, so by construction it cannot reward a genuinely new fault. | HOLDOUT-DTI numbers are a proxy; no projection is written as a score. |
| IR-60-MEM-01 | The first stage-C run died silently (no traceback) inside the uniqueness loop: a dense prior with millions of positive cells made the coordinate-stamping dilation allocate ~2 GB in a 3 GB sandbox. | `scripts/check_uniqueness60.py` now switches to `binary_dilation` above 100,000 positive cells and asserts equivalence with the shared `dot_overlap` on a sample. |
| IR-60-CORPUS-01 *(resolved)* | 4 of the 655 pinned registry rasters were unreachable at `HEAD` of `buffedlizard55-lab/55GEMSDOE` (two `audit-h55-160k` TIFFs and two `h56-multiscale-tensor-persistence` TIFFs had been moved/deleted), so the literal uniqueness gate would have had to fail closed on an incomplete scan. | Recovered all four by blob SHA from the repository's git history (`git clone --filter=blob:none` + `git cat-file blob <sha>`); every recovered file's sha256 matches its pinned digest. The corpus is now **655/655 complete** and the gate can certify instead of failing closed. |
| IR-60-PERF-01 | Two silent performance traps in the mandated first test: per-draw `np.nonzero` over a 3 M-cell crop, and a full-crop `binary_dilation` per transect. Together they made E1 hours instead of ~2 minutes. | Fixed once in the shared lane driver (`scripts/run_lane60.py`): the transect-start pool is built once per cell and dilation happens in a local window that callers slice. |
| IR-60-INDEP-01 *(resolved)* | "Several independent drainages" was first implemented as terminal-sink identity. The northwestern Great Basin is internally drained — 5.17 M cells share only 1,224 terminal sinks — so the rule rejected 36,556 of 36,633 candidates. | Replaced with `geomorph.branch_signature` (identity of the cell 5 steps downstream: same flow path within the corridor's own length scale ⇒ dependent). Fixed **before any score was recorded**; the superseded build in `evidence/superseded/` was never linked or scored. |

---

## 6. Limitations and next session

**Limitations of this sandbox** (what is needed and cannot be obtained here)

* No DrivenData login → cannot download `training_features.tif`, `labels.tif`, `sample_submission.tif`
  or `1m_DEM_links.csv` from the competition data page (verified redirect to login in earlier
  sessions). The hash-pinned GitHub bridge is the only route available, and it proves *bridge
  integrity*, not organizer provenance.
* No `usgs.gov`, no `drivendata.org`, no `*.github.io` → no 3DEP tiles, no live leaderboard read, no
  sibling site scrape. Everything external was read through `github.com` repository contents.
* No GPU, 2 CPU, 3 GB RAM, 19 GB disk → deep-detector training is out of scope; this lane is CPU-only
  by design.
* No organizer receipt exists for anything in this repository. Scores on the public board are context,
  not evidence about our files.

**Next session (ordered by expected DTI gain per unit of cost)**

1. **H60-D** (highest value, lowest cost): gate every knickpoint on a coincident step in
   `depth_to_base_surf` (band 15). This is the direct test of the named mimic — a lithologic
   contact/basin-fill boundary also steps `ksn`, but it does not step *basement depth* the way a
   fault does. Band 15 is already local and untouched by any sibling lane.
2. **H60-B**: knickpoint *isochrones* — cluster breakpoints at equal χ rather than equal distance
   (Perron & Royden). A base-level fall arrives at equal χ in every drainage, so the cluster is a
   line even where the scarp is buried. All inputs are cached.
3. **H60-C**: drainage-divide migration asymmetry (Vx-style divide height asymmetry) across mapped
   faults, projected along strike to predict unmapped continuations.
4. Re-run the whole lane on real 3DEP 10 m (or 1 m) tiles on an unrestricted machine, and fit θ per
   basin instead of the global 0.45 — this is the single largest source of systematic error in `ksn`.
5. Two-round objective: with the round-2 panel-verified pool, the correct emission bar for a *novel*
   candidate is `0.2·DTI/(1+ρ)`; ρ is currently assumed 0 here and should be estimated.

---

## 7. Site

`docs/index.html` is the GitHub Pages entry point (root `index.html` redirects to it). The executive
summary and the download/permission banner are the first thing on the page; `docs/executive-summary.html`
is the step-by-step submission guide, including the fix for the portal error
*"Predicted values must be in range [0, 1]"* (export finite zeros outside the footprint, never NaN).
