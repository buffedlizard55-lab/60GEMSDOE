# Knowledge 04 — the knickpoint corridor, the mass economics, and the circular instrument

Durable notes for the next sessions (2026-10-11, H73). Facts are labelled MEASURED (reproducible here),
OFFICIAL (competition/publisher source), MODEL (algebra on published quantities) or OWNER-REPORT
(the group's own ledger, unverified). Read this before proposing any new emission or any new lane test.

## 1. The scoring function, in the only form that matters for decisions

OFFICIAL: `DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw + ε)`, `k(d) = max(1 − d/300 m, 0)`, α = 0.2 false-positive weight,
β = 0.8 false-negative weight
([page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/), worked example pinned by
`tests/test_metric.py`). MEASURED identity, verified against brute force (`src/gems57/metric.py`):

```
DTI = T / (0.2·(T + S − M) + 0.8·|G|)      T = credited mass, S = emitted mass,
                                           M = Σ p(x)·max_g k, |G| = hidden truth pixels
```

Four operational consequences, all confirmed again today:

1. **Mass on or beside a mapped fault is dead weight.** The organizer masks known faults, so those pixels earn
   nothing and cost 0.2 each (staff answer: [forum 11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516)).
2. **A dot only earns inside 3 px (300 m).** Credit per dot, not accuracy, is the currency.
3. **Marginal rule**: adding mass helps iff its realized credit > 0.2·DTI (≈0.055–0.065 in the live range). The
   champion family lived and died on this: 0.1922 → 0.2600 → 0.2708 → 0.2778 came from *deleting* low-credit mass.
4. **|G| ≈ 12.2k px** for the hidden set (inverted from the family's own live scores; MODEL). So a 12,000-dot file
   pays 2,400 denominator units and a 37,654-dot file pays 7,531: **sparse files are cheap to be wrong about.**

## 2. The champion is a budget point, not a discovery  (MEASURED, re-verified)

`h33-h33-2-b2` (37,654 dots, owner-report 0.2778) is the parent dotted-ridge field minus 6,436 dots that sat
100–200 m off mapped faults, its dots are ≥223.6 m from the catalogue, only 5.8 % of them within 300 m of it, and
its credit per dot on the off-catalogue instrument is **0.145568** (re-measured today in
`evidence/h73_emission.json`, identical to `evidence/h71_artifact_comparison.json` → the instrument is stable).
Nothing new was learned about geology in the last three promotion steps. **Consequence: to beat it you need either a
field with >0.1456 credit/dot at similar mass, or the same credit at a third of the mass.**

## 3. The lane's record, complete and honest (nine independent runs)

| run | statistic | first test | HOLDOUT-DTI (gems57-pooled-hide-v2, 22,641 withheld px) |
|---|---|---|---|
| 60GEMSDOE lane-1 | 100 m det_elev proxy | 4/5 folds positive | 0.0108 vs random 0.0268 |
| H60-A corridor | 100 m, ≥3-drainage corridor | +0.1089 [0.0586, 0.1569] | 0.0164 vs random 0.0391 |
| chi-cast | 100 m GeoDAWN elev | STOP (AUC 0.46) | 0.0004 vs 0.0004 |
| GEMS61 thermal | lane × INGENIOUS thermal | — | 0.0025 vs random 0.0391 |
| H65-1 | **10 m raw log-ratio** | +0.0326 [−0.0144, +0.0790] INCONCLUSIVE | 0.0116 vs 0.0391 |
| H66-1/H66-2 | 10 m both-limb Δksn | −0.0860 [−0.1372, −0.0220] | 0.0091 vs 0.0725 (instrument basis) |
| H66-6 | masked raw log-ratio | +0.0404 [−0.0029, +0.0871] | 0.0096 vs 0.0391 |
| H68-1 | Δksn + 10 m curvature + 1 m LiDAR piedmont | +0.4502 [0.2510, 0.6491] | 0.1719 vs 0.0391 |
| H70-1 | paired polarity (crest + base drop) | −0.0347 [−0.0853, +0.0126] → STOP | not run (gate first) |
| **H73** | **amplitude-coherent, strike-persistent corridor of 10 m Δk_sn** | **+0.2034 [0.0780, 0.3350] PROCEED** | **0.0532 pure / 0.0642 confined vs random 0.0386; k_sn-only 0.0198; distance-control 0.1907** |

OFFICIAL-grade lesson: a *statistic* can pass its physics test and still be worthless as a *placement rule*. H73
passes the first test on 196 withheld components and beats its own k_sn-only ablation 2.7×, yet its independent
value over "be near a mapped-but-uncatalogued structure" is +0.104 of 0.67 credit/dot.

## 4. The circularity trap — the single most transferable finding in this file

MEASURED (`evidence/h73_controls.json`). The population-matched off-catalogue instrument uses as truth: *SGMC
state-map fault pixels more than 300 m from the given catalogue* (62,226 px). If a candidate's **domain mask** is
built from those same traces, the instrument grades the candidate on its own home ground:

| 12,000-dot arm | credit/dot on that instrument |
|---|---|
| uniform random in footprint | 0.1086 |
| champion | 0.1456 |
| random **inside** the off-catalogue corridor | 0.5667 |
| H73 χ/k_sn ranking **inside** the same corridor | 0.6704 |
| random scatter **on** the corridor, no NMS, no relief rules | 0.8425 |

Any of these can be made to "beat the champion" by confining mass to the truth set. **Rule for the next sessions: an
instrument may not use a structure that also appears in the candidate's domain definition. Either (a) score against
a disjoint split (different map sheet, different catalogue vintage, held-out quadrants of the trace set), or (b)
report the confined arm as ungradeable.** Logged as IR-73-INSTR-CIRCULAR-01; the same trap is why
`catalogue-truth` instruments are anti-predictive of the live board (E1 instrument audit: emitted mass ρ = +0.94,
catalogue-full ρ = −0.90).

## 5. Gates that are properties of the registry, not of the candidate

MEASURED: the literal clause ">70 % of my dots within 3 px of a registry raster ⇒ duplicate" is unsatisfiable in
this footprint. Three space-filling comparators cover 99.9–100 % of any dot set; the live-scored champion measures
0.99915 / 0.88883 / 0.771897 against them, H73 measures 0.999083 / 0.86175 / 0.778417 (lower on two of three),
and the like-for-like reading against the 75 dot-field rasters is 0.4235 max (0.3493 vs the closest sibling).
**Use both readings, always, and never waive a gate by asserting intent** — publish the universality measurement
instead (`evidence/h73_dense_comparator_universality.json`, `scripts/h73_*`).

## 6. Data inventory that actually exists in this checkout (offline-usable, public domain / open)

| asset | file | notes |
|---|---|---|
| grid, footprint, catalogue | `data/bridge/sample_submission.tif`, `existing_faults.tif` | 3730×3292, 100 m, EPSG:32611, footprint 5,167,373 px, catalogue 60,988 px |
| 3DEP 10 m reduction: Δ-step, k_sn, log-area, elev | `data/external/dem10_chi_100m_i16.tif` | 5 int16 bands, nodata −32768, sha256-pinned |
| channel/knick/playa/valid counts | `data/external/dem10_chi_100m_u8.tif` | `raised_n ≥ 50` = playa/closed-basin mask |
| drainage identity (500 m downstream index) | `data/external/dem10_chi_100m_sig_i32.tif` | the "independent drainages" definition |
| 10 m topo derivatives | `data/external/topo_10m_derived_100m_u8.tif` | bands: slope_p90, slope_max, steep_frac, slope_std, **relief_local (5)**, curv_prof_absmax (6), aspect_coherence (7), hs_lineament (8), dem_mean (9); quantised, nodata 0 |
| 1 m LiDAR scarp set | `data/external/lidar_scarp_features_u8.tif` | 12 bands, incl. `strike` (11) and `valid` (12) |
| GeoDAWN magnetics/radiometrics | `geodawn_extensions_u8.tif` (ThK, UK, UTh, **TMI_up150**), `geodawn_rad_u8.tif` (K, Th, U, TC) | lithology/clay-cover mask when `training_features.tif` is absent |
| SGMC 1:750k faults on grid | `data/external/sgmc_faults_100m.tif`, `derived_sgmc_faults_100m.tif` | the off-catalogue structure prior (82,151 px here) |
| INGENIOUS springs/wells + geothermometry | `data/external/gdr_wellspring_in_footprint.csv` (27,092 rows), `gdr_volcanic_vents_in_footprint.csv`, `paleo_geothermal_regional.zip` | already row/col georeferenced — point-pattern geometry is free to run |
| QFaults attributes/traces | `qfault_attributes.csv`, `gdr_qfaults_traces.csv` | GDR QFaults v2 lies within 300 m of the given catalogue for 59,064/59,065 px — it adds nothing |

Not present and not fetchable here (egress allowlist is github/npm/PyPI only): `training_features.tif` (419 MB,
19 bands incl. `iso_grav_anom*`, `depth_to_base_surf`, `cond_surf`), the native 10 m DEM tiles, PRISM
precipitation, ComCat, ARIA/COMET InSAR. Any hypothesis that needs them must state the source and wait for a run on
an unrestricted machine (or the pinned `dem10-chi` GitHub Actions workflow, which *can* fetch 3DEP).

## 7. What to do next, ranked

1. **H75 (20–30 min)**: split-map / held-out-quadrant instrument so confined candidates can actually be graded; then
   re-grade every registry raster. This is worth more than any new field, because it decides whether the current
   submission bet is 0.10 or 0.30.
2. **H74 (LOW cost, new geology)**: Radon linearity of the 27,092 GDR spring/well points, ≥5 sources, ≥2 km,
   ≥300 m off catalogue — permeability structure, an independent evidence type that never needs a scarp.
3. **Widen the corridor** 500 m → 1 km to lift the 12,204-dot NMS cap (IR-73-MASSCAP-01), and pre-register the mass
   ladder *after* the cap is known, since the metric rewards mass while credit/dot > 0.2·DTI.
4. Sign-test / quantile variant of the first test: H73 passed on the mean with a negative median (IR-73-MEDIAN-NEG-01);
   a robustness gate makes the next "PROCEED" worth more.
5. Keep the discipline: never quote a local instrument as a score; the only organizer-confirmed numbers in this
   project's record are public leaderboard rows (0.4133 / 0.3418 / 0.3361 at the top on 2026-10-11, manual read).
