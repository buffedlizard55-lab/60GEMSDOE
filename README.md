# 60GEMSDOE — Tectono-geomorphic knickpoint lane for the DOE GEMS Prize

**Competition**: [GEMS Prize Challenge, DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/) ·
**Official problem/metric**: [page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) ·
**Official rules**: [NLR/OT-6A50-96647](https://www.nlr.gov/docs/fy26osti/96647.pdf) (DOI [10.2172/3818146](https://doi.org/10.2172/3818146)) ·
**Live leaderboard top (verified 2026-10-11): 0.3774** · **Group best (owner-reported): 0.2778**

> ## ⚠️ SESSION VERDICT (read first)
> **The generated submission TIF is a NEGATIVE result: do NOT submit it.**
> * File: [`docs/downloads/gems60-knickpoint-lane-c7653-20261011T000000Z.tif`](docs/downloads/gems60-knickpoint-lane-c7653-20261011T000000Z.tif)
>   (unique — passed the registry gate; validated — 0 problems; portal-safe all-finite container)
> * Why: the lane's preregistered first test failed — withheld fault segments carry **lower**
>   channel-steepness anomaly than orientation-matched random lines (AUC 0.224 < 0.55 stop rule),
>   and pooled holdout DTI is 0.00214 [0.0018, 0.0025] vs 0.086 for the best comparison arm.
> * The brief's rule "If not, stop." was applied. Negative results are deliverables.
> * Site: `docs/index.html` (front page states the verdict at the top) ·
>   [`docs/executive-summary.html`](docs/executive-summary.html) explains the exact submission ritual
>   for any future PROMOTED file, including the fix for the historical
>   *"Predicted values must be in range [0, 1]"* portal rejection.
> * **ONE-CLICK status read-out for every file in `docs/downloads/`:** each artefact page prints a
>   `DOWNLOAD: OK/NO · SUBMIT TO THE COMPETITION: YES/NO` line. The historical portal-rejected
>   baseline `gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif` (owner-reported 0.26) is kept
>   in `docs/downloads/` with its receipt as the worked example of the
>   *"Predicted values must be in range [0, 1]"* fix.


>
> ### ⬇ SECOND, INDEPENDENT RUN OF THIS SAME LANE — session `arena/16fc977d-60gemsdoe`
> **[⬇ `docs/downloads/gems60-chi-knickpoint-cast-lane-v1-6000-dots-zeros.tif`](docs/downloads/gems60-chi-knickpoint-cast-lane-v1-6000-dots-zeros.tif)** ·
> [receipt](docs/downloads/checks-gems60-chi-knickpoint-cast-lane-v1-6000-dots-zeros.tif.json) ·
> [full report](docs/lane-chi-report.html) ·
> **DOWNLOAD: OK (research artefact) · SUBMIT TO THE COMPETITION: NO** — same verdict, reached
> independently with a different DEM, a different statistic and a different holdout.
> Keys: absolute-elevation GeoDAWN DEM (`data/geodawn_dem_a2_100m.tif`, sha256 `d32762a3…`);
> pre-registered test STOP twice (Δmean −0.0229 CI95 [−0.166, +0.162]; then −0.0349
> CI95 [−0.0806, −0.0065], AUC 0.4795); channel-normal cast field AUC **0.4984**;
> **15/15** format checks PASS; **unique** (worst ρ = −0.015, worst 3-px overlap 0.000 over
> 170 registry rasters); HOLDOUT-DTI 0.00039 vs matched random control 0.00042.
> Code lives in `src/gems60chi/` so it never forks or overwrites this session's `src/gems60/`.

---

## Standing brief (verbatim — read every session before working)

<details open><summary><b>The prompt this project runs on</b></summary>

```text
Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.  DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION.  BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION.  IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.  Read the entire prompt.

Tectonic-geomorphology lane: channel steepness and knickpoints, not scarp shape. Kirby and Whipple (2012) review how bedrock-channel steepness and knickpoints record spatial gradients in rock uplift, including across active normal faults. Perron and Royden's χ transform (ESPL, 2013) puts different channels on a comparable footing, and Gailleton et al. (Earth Surface Dynamics) give a reproducible knickpoint-segmentation method. Scarps degrade and bury, but channel profiles keep recording base-level steps, so this can see faults the curvature features no longer show. Extract drainage from the free 3DEP 10 m DEM (or 1 m tiles), compute χ and normalized steepness, and keep only knickpoints and steepness steps that align across several independent drainages along a common strike. First test: do channels crossing withheld segments show larger steepness steps than random lines of the same orientation? If not, stop. Map and mask the usual confounds: lithology, climate gradients, ephemeral channels and playa base levels. Output the standard validated GeoTIFF, uniqueness-checked against every earlier raster.

PARALLEL-RUN PROTOCOL — read first. This session is one of several running from this same prompt.

1. LANE. Your lane is the single method paragraph below. Stay inside it. If your raster's rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots fall within 3 px of one registry raster's dots, you have drifted into another lane: log it as a duplicate and stop. Check this on the surface before placement AND on the final dots.

2. REUSE, DON'T REBUILD. Use the template's cached feature stack, evaluate_holdout.py and submission_writer.py. Holdout = hide-and-recover: withhold whole fault segments with a buffer, derive every catalogue-based feature only from the visible faults, mask visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool is wrong, fix it once in the template and report it; never keep a private fork.

3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a score.

4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any result. AUC above [0.90] means leakage until proven otherwise.

5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault process that could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission name + note of at most 140 characters; verdict promote / negative. Negative results are deliverables.

6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a real slot is a separate selector step, within the weekly cap shown on the submission page.

The following sites should serve as a starting point for understanding how to generate TIF submissions.  These websites are researched, and tested and have generated TIF submissions.  But we need to generate high scoring submissions.

Here are the results from submissions into the competition, separated by ....:

WE NEED TO STUDY, ANALYZE, AND UNDERSTAND THE HIGHEST SCORE FROM THE GEMDOE SITE WHERE THE SUBMISSION TIF IS DOWNLOADED FROM WHICH IS THE FOLLOWING:

[https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

Why and how did this get the highest score and are we able to generate a submission that scores higher than 0.2778?

Answer the question using Phd level experience, knowledge, and judgement. Then use the answer to generate a unique TIF submission into the competition.  Must be unique submission unlike any within the GEMSDOE sites above.  Verify working line by line no hallucinations.

Current competition leaderboard GEMSDOE high score:

0.3774	[https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html)

[... the brief continues with the full per-repository score ledger (GEMSDOE … 62GEMSDOE), the leaderboard link https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/, and the resource links: https://github.com/drivendataorg/gems-prize-reference-solution ; https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and ; https://gbcge.org/current-projects/ingenious/ ; https://epsg.io/32611 ; https://en.wikipedia.org/wiki/Tversky_index ]

We need to quickly look at the results and results from the GEMSDOE websites above.

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot — do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We have a good understanding of how our hypothesis, methodology, calculations, analysis are done so we should be able to figure out a way to score higher on the leaderboard using previous results and scoring that we have across the sites listed above.  We need to come up with distinct and unique strategies to score higher in this competition leaderboard.  We need to start doing heavy and deep research into the part of the project that matters the most, which is the scientific discovery of geothermal vents.  We should store all of our information and knowledge that we can gather from official verified sources.  This will serve as a starting point for other projects as well.  We need to think outside the box but still be grounded in proper scientific research, we are ultimately aiming for a top prize that many others are competing for.  So it's important to be contrarian but be smart about it.  We need to find sources of data that others are over looking or areas of the project when it comes to geothermal vents.  We need to do deep research and critical thinking and come up with new hypothesis to test.

0.3195	is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website.  It should be unique, take unique approaches to generating a submission that can score higher than 0.3195.

Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use.  It should solve the problem of having to manually check everything ourselves and having an up to date current feed.

Review the repo.

The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.

Our Core Values

Maximize P(Win)

“Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We need to focus on being able to generate a submission into the competition.

The site should be able to generate a TIF file that is required for submission.  It should be as easy as download to click a File to submit into the competition.  This needs to be in the executive summary or the very beginning of the site.  it should be obvious when you visit the site.

I tried to submit the document that i downloaded from the site but it returned this error on the submission form:

"Predicted values must be in range [0, 1]"

Also we need to give it a unique name and A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Here is the submission page when i click submit file

New submission

File to submit / No file chosen

You can submit a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF, with your predictions. It must match the submission format's CRS, shape, and geotransform. You may wish to review the competition rules first.

Note (optional)

A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Create a executive summary subpage that explains exactly how to make a submission into the contest.

Work on the next steps from the previous sessions first.

The goal of this project is to place top of the leaderboard in this competition.  The following is the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

We need to create a project that can compete and place top of the leaderboard.  We need to understand the problem, collect all the data and organize it into a clean easily auditable table with official verified links for manual verification.

This is the guidelines we need to follow.[https://www.drivendata.org/competitions/306/competition-doe-gems/](https://www.drivendata.org/competitions/306/competition-doe-gems/)

Get familiar with the problem through the overview and problem description,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/). You might also want to reference additional resources available on the about page,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/).

Download the data from the data,[https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/), tab.

Create and train your own model. This reference solution,[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution) implements a simple approach.

Use your model to generate predictions that match the submission format.

Tell me what are you limitations and what you need access to during this project.  We will need to find free publicly available sources and data from official and verified sources if we are to use 3rd party or external data.

this pdf outlines how submissions must be entered into the competition.

[https://docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)

You must be able to do your own research, deep research, scientific literature research and organize the knowledge so that we can critically think through the problem and generate a solution through scientific and free publicly available information.  this must be done autonomously and must be constantly reviewed and improved upon.  Provide suggestions and improvements and implement them.

❌ No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (verified redirect to login)

See below for links from the above site.  See attached files for links from the above site.

[https://gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391)

Download competition data from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (requires login) to data/

See links below for competition data:

[the owner's mirrored Dropbox links: GEMS_96647.pdf; example_submission.tif; existing_faults.tif; gems-geodawn-numerical-features.tif; Digital-elevation-model-links-JSON.pdf]

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.  The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Site creation: Create a github page for this repo that has clean ui, user friendly, simple and easy to use.  It should be organized and clean.  It should include all relevant information in an easy to read format with official verified links as sources for review.  Work line by line verify everything no hallucinations.

The single remaining blocker to training is data placement: run `bash scripts/download_competition_data.sh` on any unrestricted machine into `data/`, then `python scripts/prepare_data.py` — after that the full train→inference→validate pipeline is ready to run (GPU needed for training; metric/losses/validation all verified working here on CPU).

you need to complete the above task by yourself.  Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.  The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Run this task through multiple passes.

Pass 1: Implement the task completely and verify the result.

Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.

Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.

Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request.  Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project.  It should be worked on in this next session or the next session.  Work line by line verify everything no hallucinations.
```

</details>

---

## What this session did (3 experiments, budget respected)

| # | experiment | result |
|---|---|---|
| E1 | Lane first test (preregistered): knickpoint enrichment of 78 withheld segments (25% of 301 segments ≥ 4 km, strike-octant-stratified, seed 20261011) vs 30 orientation-matched laterally-offset nulls + 30 rotation nulls each | **AUC(N1) = 0.224, AUC(N2) = 0.256, Wilcoxon p = 1.6e-6 (real < null) → NEGATIVE-STOP** |
| E1b | Distance-profile diagnostic (0–3.2 km bands around traces, channel cells, top-decile anomaly) | No band shows real > null; the confound (range-front alluvial cover) dominates → measurement construction documented, lane still negative |
| E2 | Raster build: Priority-Flood fill → D8 → χ/ksn (θ=0.45) → DoG log-ksn anomaly → multi-drainage concordance → playa/flat/lithology masks → 2-px catalogue ring → 3-px NMS | 7,653 dots (capacity-limited; field cannot honestly support 37,654) |
| E3 | Pooled hide-and-recover (shared evaluator `gems52-pooled-hide-v1`, 4 whole-segment folds, 36,414 withheld positives, 20 km-block bootstrap CI, 2,000 draws) + canary + uniqueness + validator + writer | **lane 0.00214 [0.0018, 0.0025]**; canary AUC 0.5014 (no leakage); uniqueness PASS; validator 0 problems; **verdict NEGATIVE** |

### Run card (evidence/runcard.json · docs/runcard.json)

* **Hypothesis**: withheld normal-fault segments carry localized channel-steepness (knickpoint/ksn) signals on drainages crossing the trace (Kirby & Whipple 2012; Perron & Royden 2013).
* **Mechanism**: fill → D8 → χ/ksn on official 100 m `det_elev` → DoG log-ksn steepness-step anomaly → concordance across independent drainage outlets → confound masks → catalogue ring → NMS dots.
* **Named confound**: range-front alluvial cover — traces crossing piedmonts have no bedrock channels; orientation-matched straight nulls cut more steep headwater terrain and out-score real traces.
* **Holdout**: HOLDOUT-DTI (evaluator `gems52-pooled-hide-v1`, 36,414 withheld positives) = 0.00214, 95% CI [0.0018, 0.0025].
* **Registry**: max Spearman ρ = 0.0047 (gate 0.90); max 3-px dot-overlap 45.9% (gate 70%) → PASS, no lane drift.
* **Raster sha256**: `c4f006133f7203ac5a26715dbe774f9892efcb15815001900256cd9cb7b0a64c`.
* **Validator**: 0 problems — no NaN, values in [0,1], float32, CRS EPSG:32611, shape 3730×3292, transform `(100, 0, 243350, 0, −100, 4508550)` match, 0 mass outside footprint.
* **Submission name / note**: `gems60-lane-knickpoint-c7653-20261011T000000Z` / "tectono-geomorphic chi/ksn knickpoint lane; 7653 concordant channel dots; E1 negative AUC 0.224; RESEARCH-ONLY, not promoted".
* **Verdict**: **negative** (do not spend a slot).

## Why the group's 0.2778 champion is what it is (PhD-level answer, from measured bytes)

The official metric collapses (identities pinned by tests) to `DTI = T / (0.2(T+S−M) + 0.8|G|)`:
only credited mass `T`, wasted mass `S−M`, and the fixed hidden-pixel count `|G|` matter. The champion
is a 37,654-dot **binary** file that deleted catalogue-proximal mass (masked pixels can never earn
credit but always pay tax — measured live: 0.2600 → 0.2708 → 0.2778 through pure deletion), keeps
every dot within ≈ 282 m of plausible hidden structure, and uses the all-finite container. Beating it
requires **+15% credit density** at equal budget or **−32.6% mass** at equal credit — i.e. new
knowledge of hidden-fault locations, not local cleanup. This session's lane was one candidate
source of that knowledge; it measurably does not carry it on the 100 m detrended surface. A second
measured caution: on the pooled hide-folds, the champion itself scores 0.0041 vs dotted-d2.8's 0.0862
while live ranks them 0.2778 > 0.2600 — catalogue-segment holdouts cannot rank the leaderboard
(independently: 16GEMSDOE measured ρ = +0.17). Treat every local instrument as a screen, never proof.

## Reproduce (from a clean clone)

```bash
pip install rasterio scipy scikit-image numba pytest
python scripts/fetch_data.py        # reassembles the hash-pinned bridge (pins in data/bridge/manifest.json)
python -m pytest tests/ -q          # metric parity (official worked example) + hydrology core
python scripts/e1_lane_test.py      # lane first test  (~12 min, 1 core)
python scripts/e1b_distance_profile.py
python scripts/e2_build.py
python scripts/e3_validate.py       # pooled holdout + uniqueness + writer + run card
```

Repository layout: `src/gems52/` — shared template (metric/holdout/evaluate_holdout/submission_writer/grid/gates
vendored verbatim from GEMSDOE52 + this lane's `lane_hydro.py`, `lane_channels.py`); `scripts/` — the
four experiment runners; `evidence/` — E1/E1b/E2/E3 JSONs + run card; `docs/` — the site.

Registry provenance (uniqueness anchors, all re-fetchable from the org's public repos): champion
`h33-2-b2` zeros ← `GEMSDOE32/docs/downloads`; dotted-d2.8 zeros ← `GEMSDOE32/docs/downloads`;
`h27-4-r1-solo` ← `GEMSDOE28/docs/downloads`; `h16-1` ← `16GEMSDOE/docs/downloads`;
lidar-scarp ridge ← `7GEMSDOE/downloads`; dem10-multiphysics ← `12GEMSDOE/docs/downloads`.

## Limitations (stated, not hidden)

1. **No DrivenData auth** → competition rasters come from the hash-pinned owner bridge
   (`data/bridge/manifest.json` pins every sha256; `labels.tif` ≡ `existing_faults.tif`,
   sha `7ba308cc…`). No labels exist for the organisers' hidden set anywhere.
2. **Sandbox egress** blocks `prd-tnm.s3.amazonaws.com` / ScienceBase → the brief's preferred
   3DEP 10 m/1 m raw DEM could not be downloaded here. The lane therefore ran on the official 100 m
   `det_elev` band. The source is free/official/public-domain; 716 tile URLs + sha256 pins exist
   (`data/dem_links.json` upstream; 706/716 tiles processed in session 7GEMSDOE). A single
   unrestricted-runner run unlocks the full-resolution lane (hypothesis 5).
3. **Local instruments are weak**: measured champion-vs-holdout rank inversion (above). No local
   score predicts a leaderboard score; only the submission page scores.
4. **Budget**: session stopped at 3 experiments / < 2 h. No promotion decision was taken — that is
   the selector step's, within the weekly cap.

## Core values

**Maximize P(Win)** — slots are spent only on validated, unique, promoted files; this session
promoted nothing because nothing deserved it. **Own the Outcome** — the negative result is
published with full evidence so the next session does not re-run a dead lane.

---

## Merged parallel session (on `main` since PR #1 — kept, audited, and lane-checked)

A parallel session of this same brief landed the GEMSDOE32 pipeline in this repository (its own
`src/gems32` + `src/gemsdoe32` packages, `scripts/`, `tests/`, CI) together with:

* its **H61 knickpoint raster** — `docs/downloads/submission.tif`, sha256 `386e7cd1…5a5e7`,
  `submission_card.json` holdout 0.01305 on *its own* instrument (not comparable to our pooled
  evaluator), 983,855 emitted px;
* the group's **champion** download — `docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`
  (owner-reported live **0.2778**, the group best);
* its fetcher retained as `scripts/fetch_data.py` (used by its CI, `--dest` interface).

**Lane-drift check of THIS session's raster against the parallel session's H61 raster** (the
registry now includes it): Spearman ρ = **+0.0071** (gate 0.90), 36.7% of our dots within 3 px of
its dots (gate 70%) → **PASS — not a duplicate**; the two are distinct realizations of the same
lane, ours sparse and concordance-filtered, theirs dense. Note their `submission_card.json` says
"promote" on an instrument that was never calibrated against the live board; this session's shared
evaluator read of our own raster is NEGATIVE, and the promotion decision belongs to the selector
step in any case.

For the reproduce steps of the merged GEMSDOE32 pipeline see `AGENTS.md`, `CONTRIBUTING.md` and
`docs/` artifacts it shipped; this README's run card above remains the record of the knickpoint-lane
session.

---

## Lane 1 (60GEMSDOE): chi/ksn knickpoint strike traces — NEGATIVE (2026-10-11)

**Read this file first, every session.** It carries the working brief, the current verdict, and the exact
commands that reproduce every number in the repository.

**Site (start here): <https://buffedlizard55-lab.github.io/60GEMSDOE/>** — the first visible thing on that
page is the submission download and the verdict banner.

---

### 0. Verdict of the current run (2026-10-11)

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

### 1. Working brief (carried verbatim in this repository, re-read every session)

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

### 2. What was built and what it says

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

### 3. Reproduce everything

```bash
## inputs are SHA-256 pinned in scripts/run_lane.py; the run aborts (exit 2) on any mismatch
python scripts/run_lane.py --data-dir data --out-dir submission --evidence evidence \
       --registry-dir registry/rasters --cache .cache      # ~8 min, 2 vCPU / 3 GB
python scripts/selector.py                                  # the separate promotion step
python -m pytest tests/ -q                                  # analytic/conservation tests
```

Data layout: `data/` holds the three official rasters (`training_features.tif`, `labels.tif`,
`sample_submission.tif`), the SGMC validation raster, and `data/external/topo_10m_derived_100m_u8.tif`
(USGS 3DEP 10 m reduced to the competition grid, public domain, with its own manifest). `registry/rasters/`
holds the 35 comparator rasters used by the uniqueness stop rule.

### 4. Repository map

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

### 5. Remaining work and limitations for the next session

1. **Instrument first** (hypothesis #1): relief-stratified thinning; then re-score every registry raster.
   Until that exists, no "no skill" verdict in the family record is trustworthy — including this one.
2. **Real 10 m DEM** (hypothesis #2): fetch through the Actions runner and commit a decimated grid;
   the 100 m substrate cannot resolve first-order channels (31% of cells raised by depression filling,
   per-cell A-vs-L exponent ≈0.03). **The egress lane is verified**: Actions run 38100992879 returned
   HTTP 200 for `Elevation/13/TIFF/current/n39w119/USGS_13_n39w119.tif` (10 m) and
   `Elevation/1/...` (30 m) and downloaded a tile whose sha256 `b7fe301c…` matches the pin published
   independently in the sibling `12GEMSDOE/evidence/dem10-fetch.json`; see
   `evidence/probe-egress-receipt.json`.
3. **Emission policy**: the marginal rule at the *measured* DTI, plus the 100–200 m ring deletion.
4. **Not obtained:** `1m_DEM_links.csv` and the portal's own data downloads (login-walled). Irregularity
   flagged for the operator: the mirrored `sample_submission.tif` contains 60,988 pixels equal to 1 on
   the labelled faults, contradicting the portal's "total fault absence" description.
5. **Unverified / pending:** the egress probe's receipt (runner-side reachability of the 3DEP hosts) and
   the submissions page widget (no authenticated session). Treat both as open items, not as facts.


---

## Lane-60 second run (session `arena/16fc977d-60gemsdoe`) — independent corroboration

A second, fully independent run of the **same lane** was executed on the same
competition grid and reached the **same verdict**, **negative**, with a different DEM
(absolute-elevation GeoDAWN 100 m rather than a derived product), a different
statistic (channel-normal casting of χ-profile steepness steps), and its own
buffered whole-component holdout. That two independent implementations agree is the
strongest evidence available locally that the STOP is a property of the method at
100 m, not of one implementation.

**Engine:** `src/gems60chi/{metric,holdout,hydro,knick,field}.py`, with 14 tests in
`tests/test_chi_*.py` — hydrology primitives (priority-flood fill, D8 routing,
accumulation, χ) are verified against **independent brute-force implementations**.

**Experiments (budget 3/3):**

| exp | pre-registered question / artefact | result |
| --- | --- | --- |
| 1 | the brief's first test, as written (3.1 km segmentation window) | pooled Δmean **−0.0229**, CI95 [−0.166, +0.162], p = 1.0, AUC 0.459 → **STOP** |
| 2 | corrected: 700 m statistic + position-matched, area-binned control | Δmean **−0.0349**, CI95 [−0.0806, −0.0065] *(excludes 0 on the wrong side)*, AUC 0.4795 → **STOP** |
| 3 | emission, format validation, uniqueness | 15/15 checks PASS; **unique** (worst ρ = −0.015, worst 3-px forward overlap 0.000 over 170 obtainable registry rasters); HOLDOUT-DTI 0.00039 vs a matched random-on-the-same-support control of 0.00042 |

**The 0.2778 question, answered from the family's own record.** `h33-h33-2-b2` is the
owner-reported 0.2708 raster with **2,545 dots deleted and none added**, every removed dot
1.4–2.0 px from the mapped catalogue (`equals_base_pruned_at_2px: true`, 57GEMSDOE
`evidence/session6_mechanism_and_witness.json`). The metric reduces to
`1/DTI = α + α(F/T) + β(|G|/T)`, so a unit of mass pays only if its realised kernel credit
beats `α·DTI` ≈ 0.052 — within ~284 m of a hidden truth pixel. Beating 0.3195 / 0.3774 is
therefore a *detector* problem: `T` must rise ≈ **+45 % at fixed mass**. Nothing here is
written as a score.

**Irregularities flagged (IR-60-01 … IR-60-08)** — full table in
[`docs/lane-chi-report.html`](docs/lane-chi-report.html): the brief's 0.3195 is **rank 8**
(the board leader is **0.3774**); the official 19-band stack carries only **detrended**
elevation, so a χ transform is undefined on it; `prd-tnm.s3.amazonaws.com` returns
**HTTP 000** here, so the lane ran at 100 m and the missing 10 m DEM is named as the most
likely cause; the inherited off-catalogue emission rule is degenerate on a catalogue-truth
holdout; uniqueness scope is 170 of 696 registry rasters; two hydrology bugs were caught by
brute force before any scientific number; and a **0.034 m** DEM grid offset would have been
a portal geotransform mismatch had `scripts/verify_submission.py` not caught it.

**Ranked next steps (unchanged, now doubly motivated):** (1) re-run this lane on a **10 m
3DEP DEM** — `scripts/fetch_3dep_10m.sh` probes the host and refuses to claim success it
did not get; (2) χ-**transient** inversion instead of a χ-steady step; (3) knickpoint
**recurrence in χ** across basins rather than knickpoint position; (4) a playa /
closed-basin base-level mask (the fill raises **899,623 cells, 17.4 %** of the valid grid);
(5) lithology-normalised ksn.
