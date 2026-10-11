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
