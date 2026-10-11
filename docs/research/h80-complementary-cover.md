# H80 — convergent-cover emission: NEGATIVE, and the uniqueness clause measured to its frontier

Session `arena/3c52f2be-60gemsdoe` · 2026-10-11 · preregistration
[`registry/preregistration-h80.json`](../../registry/preregistration-h80.json) (written before any H80 number) ·
run card [`evidence/h80_runcard.json`](../../evidence/h80_runcard.json) ·
clause frontier [`evidence/h80_g3_frontier.json`](../../evidence/h80_g3_frontier.json) ·
report [docs/h80-report.html](../h80-report.html).

**Verdict: NEGATIVE — `SUBMIT: NO`.** The round spent 0 competition slots. Download of the emitted
GeoTIFF is fine for research; it is not cleared to submit.

## 1. What was asked and what was run

The hypothesis: mass placed in the **complement of the live-scored champion**, ranked by a convergent
field that requires strike-coherent steepness-step corroboration across **independent drainages**, carries
above-bar credit on the public off-catalogue fault population. Mechanism: a fault rotates several adjacent
catchments at once, so a step appears on channel cells whose downstream branch signature differs — a
conjunction that a single drainage cannot produce. Named non-fault mimic: erosional/constructional
lineaments, fan and pediment surfaces, playa margins, lithologic contacts.

Two profiles were run because the operator's clause 1 (a dense, image-like field) and clause 3
(no ≤70 % 3-px overlap with any earlier raster) pull in opposite directions:

* **broad** (the preregistered one): pool 3,666,787 px, mass ladder to
  48,000 dots — **measured but NOT emitted** (its union is a clause-1 duplicate of
  `r11_greedy_mp.tif` and it is unusable for submission, so emitting it would have produced a
  DO-NOT-SUBMIT artifact with no decision value).
* **restricted** (emitted): pool 265,134 px, ladder
  3,000, 6,000, 9,000, 12,000 dots, largest eligible mass
  **12,000** → union 49,654 dots
  (emitted `gems60-h80-convcomp-49654-20261011T202055Z-zeros.tif`, sha256 `ad25643354857a10…`).

## 2. E1 — the preregistered layer ablation (6000-dot, restricted pool, instrument = SGMC off-catalogue)

| arm | credit/dot [95% CI] | Δ vs baseline7 (candidate − baseline7) |
|---|---|---|
| baseline7 | 0.4018 [0.3431, 0.4727] | — |
| plus_L-A_facet | 0.4079 [0.3517, 0.4774] | +0.0007 |
| plus_L-B_front | 0.4047 [0.3456, 0.4759] | +0.0003 |
| plus_L-C_strike | 0.3339 [0.2776, 0.4052] | -0.0078 |

The candidate layers were a lithology-coloured **facet** field (71,868 steppy px,
max agreement 7, 6,400 strike cells,
mean independence 0.0514), a mountain-**front** field and a
**strike**-count field; no layer added a significant gain, so the ablation adopted **baseline7** (the H71 field) —
with `adopt_bar` 0.1, i.e. only the ladder mass moved after this point.

## 3. E2r — restricted ladder (instrument credit/dot and the union-vs-champion projection math)

| added dots | union dots | instrument credit/dot [95% CI] | union − champion HOLDOUT-DTI-free instrument delta |
|---|---|---|---|
| 3,000 | 40,654 | 0.4881 [0.4110, 0.5721] | +0.0236 |
| 6,000 | 43,654 | 0.4018 [0.3431, 0.4727] | +0.0380 |
| 9,000 | 46,654 | 0.3463 [0.2959, 0.4052] | +0.0481 |
| 12,000 | 49,654 | 0.2939 [0.2508, 0.3432] | +0.0532 |

All four masses were eligible (CI lower ≥ 0.10), so the registered rule took the largest: **12,000**.
The signal is real but decays with mass — that decay, plus §5, is why the score projection is not improved by
simply adding more dots.

For reference, the broad profile measured the same ladder at
6,000, 12,000, 24,000, 36,000, 48,000 dots:

| added dots | union dots | instrument credit/dot | union − champion ΔDTI | complement − random |
|---|---|---|---|---|
| 6,000 | 43,654 | 0.6497 | +0.0622 | +0.06314 |
| 12,000 | 49,654 | 0.5864 | +0.1091 | +0.10775 |
| 24,000 | 61,654 | 0.4881 | +0.1721 | +0.16395 |
| 36,000 | 73,654 | 0.4045 | +0.2036 | +0.18457 |
| 48,000 | 85,654 | 0.3517 | +0.2253 | +0.19346 |

## 4. E3c — uniqueness, measured to its frontier

| added dots | union dots | vs H72-union literal | vs H72-union matched | vs r11 literal | vs lattice literal |
|---|---|---|---|---|---|
| 12,000 | 49,654 | 0.8864 | 0.8792 | 0.6740 | 0.9984 |
| 18,000 | 55,654 | 0.7930 | 0.7844 | 0.6014 | 0.9983 |
| 24,000 | 61,654 | 0.7167 | 0.7080 | 0.5428 | 0.9983 |
| 30,000 | 67,654 | 0.6535 | 0.6453 | 0.4947 | 0.9982 |

* The emitted artifact fails like-for-like at **0.8864** (limit 0.70)
  against `gems60-h72-union-champ-convcomp-43654-…`; the literal reading is
  **0.9984** against `calib_r13lattice_00904.tif`,
  and max |ρ| = **0.9346** (limit 0.90).
* Four comparators lie within 3 px of ≥ 70 % of the footprint themselves (coverage 0.9987 / 0.9987 / 0.7397 / 0.7620):
  `calib_r13lattice_00904`, `r13_lattice_s5_00904`, `r11_greedy_mp`, `r14_union_tips10_lat6`. The clause's own limit
  is already exceeded by the comparator, so overlap against them is non-decidable; a mass-matched random emission
  scores 0.9987 literal against the lattice. The one discriminating comparator gives a random emission 0.0402.
* **The frontier:** against that discriminating comparator the limit is crossed between 24,000 (0.7167) and 30,000
  (0.6535) added dots — a union of roughly 62,000–68,000 dots, and the restricted pool holds 91,370 dots under
  2.8-px suppression, so compliance is mechanically reachable but *not* at the mass this round emitted. Furthermore
  the champion alone is 0.99915 inside the lattice,
  so under the literal reading **no** emission containing the champion can pass, and dropping the champion drops the
  only live-scored mass. Clause 1 and the literal clause 3 are jointly unsatisfiable.
* **And the parallel-run duplicate rule stops the round before any of that:** on the emitted artifact
  88.64 % of dots sit within 3 px of the H72-union artifact and
  its rank correlation with it is |ρ| 0.9346 > 0.90 — the protocol's own stop
  condition, logged here rather than waived. The overlap is structural: the union contains the champion
  (37,654 of 49,654 dots) and the 12,000-dot complement re-draws the restricted pool in the
  same field order as H71-A/H72, so its top 6,000 dots *are* H71-A's. The complement alone scores
  0.5299 like-for-like against the same
  comparator — the new mass is genuinely new; the **union** is what fails.
  [`evidence/h80_artifact_comparison.json`](../../evidence/h80_artifact_comparison.json) holds the reading for the
  union, the incumbent champion (1.00000 literal against the lattice,
  i.e. the incumbent fails the same clause) and the complement, in both the literal and the greedy one-to-one
  directions, over the full comparison set including `downloads/`, `submission/` and `evidence/`.
* **The bind this exposes (IR-H80-DUP-01).** The failure is inherited, not produced: the 12,000-dot complement alone
  reads 0.5299 like-for-like and
  |ρ| 0.6914, i.e. it passes the duplicate rule, while the
  incumbent is 1.0000 within 3 px of six earlier rasters and byte-identical to `registry/rasters/dotted_b2_prune_02778.tif`.
  So the choice is: keep the live-scored mass and inherit a duplicate-rule failure, or drop it and project far below the
  owner-reported 0.2778 (the complement alone projects to 0.053 at the metric bar, 0.096 at transfer 0.10 and 0.239 at
  0.25 under the metric identity). That is an owner decision; this round spent no slot and did not make it.

## 5. E3b — the registered holdout, and why it decides the verdict

Arm-for-arm on the shared hide-and-recover protocol (`gems57-pooled-hide-v2`,
22,641 withheld positives, triangular kernel radius
300 m, **HOLDOUT-DTI**):

| arm | HOLDOUT-DTI |
|---|---|
| champion | 0.004385 [0.003741, 0.005091] |
| restricted complement alone | 0.000000 |
| emitted union | 0.003844 [0.003279, 0.004466] |
| random mass-matched | 0.000883 |

Union − champion = **-0.0005** [-0.0006, -0.0005] → **G2 PASS only by the
registered -0.0020 tolerance**, and *below* the champion. For contrast, the same protect-the-champion
reading on the same protocol is 0.004097
(-0.0003 versus the champion) for H72's
43,654-dot union, i.e. **adding this restricted mass makes the holdout reading worse than H72's smaller union**,
and the only emission in this family that *improved* the holdout was the broad-profile union that clause 1
forbids (+0.000551 [+0.000018, +0.001113], H80's superseded broad run).

The canary is clean: 10 layers, flagged = [],
rule "AUC above 0.90 means leakage until proven otherwise".

## 6. PROJECTION (never a score)

Under the metric identity with an assumed true credit per added dot c, the emitted union projects to
0.0000 → 0.25259, 0.0556 → 0.28579, 0.1000 → 0.31234, 0.1460 → 0.33983, 0.2500 → 0.40197 for c ∈ 0.0000, 0.0556, 0.1000, 0.1460, 0.2500;
the broad profile would project 0.0000 → 0.18594, 0.0556 → 0.28368, 0.1000 → 0.36187, 0.1460 → 0.44279, 0.2500 → 0.55451.
The score bar per dot is α·0.2778 = 0.05556. These are projections; they are not a score and were
not used to select anything.

## 7. What this round establishes, and what it does not

1. **Establishes**: a convergent, drainage-independent complement field can be *built* and *measured*, and it is
   above the random control by a wide margin on the public off-catalogue proxy population (G1 PASS) — but the
   registered holdout prefers the champion without the added mass, and prefers H72's smaller union to this one.
2. **Establishes**: the operator's clause 1 and literal clause 3 cannot both hold for a dense field — the champion
   alone is 0.99915 inside the lattice comparator, and an
   emission that carries the champion (needed under clause 1) therefore fails before any new dot is placed. Under the
   like-for-like reading the compliant regime starts at roughly 62,000–68,000 dots, far above the mass the eligibility
   ladder chooses.
3. **Does not establish**: that no dense emission can beat the champion. The holdout protocol is a
   catalogue-withheld 8-cell hide-and-recover test; it has repeatedly inverted the live ordering in this project,
   and the one live-scored datum (owner-reported 0.2778) belongs to an artifacts family this round cannot test.
4. **Next (registered but NOT run, budget already at 3/3)**: a compliant-mass variant at M ≈ 26,000–30,000 to test
   whether a like-for-like-clear emission can also carry credit — expected to make the holdout worse, so it is
   proposed as a protocol experiment, not a score play; and the still-unfinished relief-stratified thinning of the
   off-catalogue emission (ranked step 1 in `knowledge/03`), which attacks the measured anti-correlation between the
   emission and relief (AUC 0.90).

All artifact files carry `SUBMIT: NO`; the download links are for research and review only.
