# 60GEMSDOE — DOE GEMS geothermal exploration lane (DrivenData competition 306)

**Read this file first, every session.** It carries the working brief, the current verdict, and the exact
commands that reproduce every number in the repository.

**Site (start here): <https://buffedlizard55-lab.github.io/60GEMSDOE/>** — the first visible thing on that
page is the submission download and the verdict banner.

---

## 0. Verdict of the current run (2026-10-11)

| | |
|---|---|
| **Verdict** | **NEGATIVE — no submission slot spent** |
| Candidate raster | `docs/submission/gems60-candidate-3770px-zeros.tif` (validated, unique, 65,898 B, sha256 `d3c411f5…`) |
| First test (pre-registered) | 4/5 segment folds positive, 1/5 with 95% CI above zero → **fail** |
| Off-catalogue holdout (HOLDOUT-DTI, 14,089 withheld positives) | lane **0.0108** vs uniform-random **0.0268** at matched budget 12,000; lane beats random at **1 of 9** budgets |
| Submitted raster vs same truth | 0.0064, truth-side 95% CI [0.0053, 0.0074] (lower bound) |
| Leakage canary | max single-feature AUC 0.58 → no leakage |
| Uniqueness vs 35 registry rasters | worst naive 3 px overlap 83.1%, random control 83.7% → excess −0.7%; max \|Spearman\| 0.0025 → no duplication |
| Champion comparator `h33-2-b2` (0.2778, PUBLIC-BOARD) | S = 37,654 px, min 223.6 m from catalogue, strictly inside the 44,090-cell parent; HOLDOUT-DTI 0.0681 vs 0.0489 for random mass-matched dots |

The full write-up, including the metric algebra that explains 0.2778, is on the site
(`docs/executive-summary.html`); machine-readable evidence is in `evidence/` and `docs/submission/`.

---

## 1. Working brief (carried verbatim in this repository, re-read every session)

> Review the repo and produce a **unique** TIF submission for DrivenData competition 306 (DOE GEMS
> geothermal exploration, leaderboard `https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/`)
> that beats prior scores, with it being *obvious* whether the file is OK to download/submit. Do not copy
> a prior submission except for learning. Explain, at PhD level, why `h33-h33-2-b2-…-zeros` scored 0.2778
> (highest on the GEMSDOE sites) and whether something higher is achievable.
>
> **Lane** (parallel-run protocol, must stay inside it): tectonic geomorphology — channel steepness +
> knickpoints (Kirby & Whipple 2012; Perron & Royden 2013 χ transform; Gailleton et al. knickpoint
> segmentation); drainage from free 3DEP 10 m DEM; χ and normalized steepness; keep only
> knickpoints/steepness steps aligned across several independent drainages along a common strike;
> first test — do channels crossing withheld segments show larger steepness steps than random
> same-orientation lines, else stop; mask lithology, climate gradients, ephemeral channels, playa base
> levels; output validated GeoTIFF, uniqueness-checked against every earlier raster.
>
> **Protocol**: rank-correlation with any registry raster > 0.90, or >70% of dots within 3 px of one
> registry raster → log duplicate and stop (check both before placement and on final dots). Reuse the
> template's cached feature stack, `evaluate_holdout.py`, `submission_writer.py`; fix shared tools once in
> the template, never fork privately. Holdout = hide-and-recover whole fault segments with buffer;
> catalogue features derived only from visible faults; visible faults masked pixel-exactly; pooled DTI
> (α 0.2, β 0.8, 300 m triangular kernel). Label every number HOLDOUT-DTI (evaluator version, number of
> withheld positives, 95% CI) or ORGANIZER-CONFIRMED (submission-page receipt); a projection is never
> written as a score. Leakage canary: single-feature AUC > 0.90 = leakage until proven otherwise. End with
> one JSON run card (hypothesis; mechanism; named non-fault mimic process; holdout DTI + CI;
> correlation/overlap vs registry; raster sha256; validator output — no NaN inside footprint, values in
> [0,1], CRS/shape/transform match; submission name + ≤140-char note; verdict promote/negative — negatives
> are deliverables). Do not pick submissions; promotion is a separate selector step within the weekly cap.
>
> **Also required**: 3–5 new candidate geological hypotheses ranked by expected DTI improvement vs
> implementation cost (each naming specific layers, the physical signature, why it catches a fault missing
> from the USGS/INGENIOUS catalogue, and how it differs from prior work), top candidate validated on the
> spatially-blocked holdout before any submission slot is spent; free official sources only, verified
> obtainable; README must embed the brief and be re-read each session; clean GitHub Pages site whose first
> visible thing is the submission download + executive summary subpage; competition data organized into a
> clean auditable table with official links; apply "Maximize P(Win)" and "Own the Outcome".

**Standing constraints from the operator** (unchanged): the TIF must be unique and never a copy of a prior
submission except for learning; the file must be a single-band GeoTIFF (or a zip containing one) matching the
submission format's CRS/shape/geotransform with values in [0,1] (a prior download failed with *"Predicted
values must be in range [0, 1]"*); a unique name and a ≤140-character note are required; no hallucinations —
verify line by line from official sources and flag irregularities; work autonomously (no manual input from
the operator); run three passes (implement+verify, review for bugs/missing requirements, re-check against the
original request and improve) and do not stop after the first; finish by opening a pull request, merging it to
`main`, and listing remaining work and limitations for the next session; DrivenData authentication is
unavailable, so organizer rasters are restored from integrity-pinned mirrors and free official substitutes are
used; lane stop rules are hard; **budget: stop after 3 experiments or 2 hours, and never spend a submission
slot on anything that has not beaten the best promotable holdout in the family record (DTI 0.190147)**.

---

## 2. What was built and what it says

* **The lane, implemented honestly.** `src/gems60/drains.py` (priority-flood + ε, steepest-descent D8,
  exact D8 accumulation, Perron–Royden χ, per-link segmentation, first-order basins, strike/pair tools),
  `src/gems60/surface.py` (channel network, one knickpoint per first-order basin, **strike-trace
  detector** = chain of knickpoints from ≥3 independent basins along a common strike with
  non-maximum suppression and principal-axis refit, confound masks), `src/gems60/holdout.py`
  (whole-segment folds with buffer, tie-corrected AUC, pooled DTI, truth-side bootstrap),
  `src/gems60/nodes.py` (marginal-rule budget, hex lattice, emission with 3 px minimum separation,
  registry overlap), `src/gems60/metric.py` (the organizers' metric, byte-pinned from the sibling
  registry), `src/gems60/grid.py` (grid/template/validator).
* **Two experiments, the same answer.** Run 1 on the cube's detrended-elevation band (documented
  deviation): 5/5 folds positive, 1/5 with CI above zero, lane below random on the off-catalogue
  instrument. Run 2 on real elevation (USGS 3DEP 10 m reduced to 100 m — the substrate the lane is
  specified on): 4/5 folds positive, 1/5 with CI above zero, lane below random at 8 of 9 budgets.
  The negative is robust to the substrate, and it is a *placement* failure, not a leak: the canary is
  clean.
* **The instrument itself is now a finding.** The off-catalogue truth used by the whole family is
  anti-correlated with relief (AUC 0.90 for local relief, 0.90 for slope p90, 0.88 for absolute
  elevation), because maximal-separation thinning spreads the sample into basin floors. Every
  topography-based lane in the family has therefore been graded on a sample biased against it. Fixing
  the instrument is hypothesis #1 (see `docs/hypotheses.html`).
* **Why 0.2778.** Inverting the organizers' metric on the champion file with the published |G| pins
  implies it matched ≈5.1–5.6k of ≈12.4–14.3k hidden truth pixels (recall ≈39–41%) while paying the
  0.2 mass tax on 37.4k unmatched pixels. It is a mass/precision point on the metric's frontier, not a
  physical achievement: the family's own inversion fits 13 board-calibrated submissions with zero
  weight difference between physical bases (LOO MAE ≈0.020). The same recall at 6,000 px of mass is
  worth ≈0.40–0.42, and the board's best (0.3774) needs ≈54–57% recall at the same mass. Higher is
  achievable; the headroom is in recall on off-catalogue faults and in mass discipline, not in a
  cleverer basis. Details and arithmetic: `docs/executive-summary.html` §3.

---

## 3. Reproduce everything

```bash
# inputs are SHA-256 pinned in scripts/run_lane.py; the run aborts (exit 2) on any mismatch
python scripts/run_lane.py --data-dir data --out-dir submission --evidence evidence \
       --registry-dir registry/rasters --cache .cache      # ~8 min, 2 vCPU / 3 GB
python scripts/selector.py                                  # the separate promotion step
python -m pytest tests/ -q                                  # analytic/conservation tests
```

Data layout: `data/` holds the three official rasters (`training_features.tif`, `labels.tif`,
`sample_submission.tif`), the SGMC validation raster, and `data/external/topo_10m_derived_100m_u8.tif`
(USGS 3DEP 10 m reduced to the competition grid, public domain, with its own manifest). `registry/rasters/`
holds the 35 comparator rasters used by the uniqueness stop rule.

## 4. Repository map

| Path | Contents |
|---|---|
| `src/gems60/` | the lane: `drains.py`, `surface.py`, `holdout.py`, `nodes.py`, `metric.py`, `grid.py` |
| `scripts/run_lane.py`, `scripts/selector.py` | end-to-end run (9 steps) and the promotion decision |
| `tests/` | analytic tests (χ linearity, conservation, detector positive/negative controls) |
| `evidence/` | first test, instruments, budget curve, traces, canary, uniqueness, source pins, run card |
| `docs/` | the Pages site: download + verdict, executive summary, data table, hypotheses |
| `submission/` | emitted rasters (primary + NaN variant) |
| `data/external/` | committed external data with provenance (3DEP-derived pack + manifest) |
| `.github/workflows/probe-egress.yml` | runner-side egress probe + receipt (the sandbox cannot reach `prd-tnm.s3.amazonaws.com`) |

## 5. Remaining work and limitations for the next session

1. **Instrument first** (hypothesis #1): relief-stratified thinning; then re-score every registry raster.
   Until that exists, no "no skill" verdict in the family record is trustworthy — including this one.
2. **Real 10 m DEM** (hypothesis #2): fetch through the Actions runner and commit a decimated grid;
   the 100 m substrate cannot resolve first-order channels (31% of cells raised by depression filling,
   per-cell A-vs-L exponent ≈0.03).
3. **Emission policy**: the marginal rule at the *measured* DTI, plus the 100–200 m ring deletion.
4. **Not obtained:** `1m_DEM_links.csv` and the portal's own data downloads (login-walled). Irregularity
   flagged for the operator: the mirrored `sample_submission.tif` contains 60,988 pixels equal to 1 on
   the labelled faults, contradicting the portal's "total fault absence" description.
5. **Unverified / pending:** the egress probe's receipt (runner-side reachability of the 3DEP hosts) and
   the submissions page widget (no authenticated session). Treat both as open items, not as facts.
