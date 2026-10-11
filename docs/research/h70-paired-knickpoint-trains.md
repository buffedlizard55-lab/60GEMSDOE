# H70-1 — Paired-polarity knickpoint trains (NEGATIVE), and the answer to "why 0.2778 and can we beat it"

**Session:** `arena/ccdca785-60gemsdoe` · 2026-10-11 · lane: tectonic geomorphology — channel steepness / χ / knickpoints
**Verdict: NEGATIVE at the mandated first test (G1 STOP). No new GeoTIFF was generated. No submission slot was spent.**
Run card: [`evidence/h70_runcard.json`](../../evidence/h70_runcard.json) · Preregistration (written before any number): [`registry/preregistration-h70.json`](../../registry/preregistration-h70.json) · Rows: [`evidence/h70_e1_first_test.json`](../../evidence/h70_e1_first_test.json)

> **What is OK to download and submit, plainly stated.**
> - A *new* H70 submission file: **does not exist — NEGATIVE gate, nothing was emitted.** That is the protocol working, not a missing file.
> - The incumbent validated lane artifact [`gems60-h66-dem10-bedrock-dksn-40000-20261011T162456Z-dbafa4373009-zeros.tif`](../downloads/gems60-h66-dem10-bedrock-dksn-40000-20261011T162456Z-dbafa4373009-zeros.tif): **format-validated, 0 NaN, all 12,279,160 cells in [0.0, 1.0], unique vs the local registry — OK to download: YES.** Whether to spend the weekly slot on it is the cross-lane selector's decision, not this lane's.
> - Everything in this page is labeled **HOLDOUT-DTI / MEASUREMENT / INSTRUMENT / OWNER-REPORT / VERIFIED-SNAPSHOT**. No local number is a leaderboard score.

---

## 1. Why `h33-h33-2-b2` scored 0.2778 — the mechanism, with the arithmetic checked

**Provenance (verified-here).** The file in this checkout (`registry/rasters/dotted_b2_prune_02778.tif` ≡ `docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`, byte-identical, sha256 `c55bafc4…`) contains **37,654 positive pixels** (counted). Its own build bundle (`evidence/h33_submission_bundles.json`) describes it as the *"catalogue-flank B=2 prune on the 0.2708 base"*. The public leaderboard snapshot verified 2026-10-11 shows the participant-row `extradr19` at rank 23 with **0.2778** ([snapshot](../../registry/leaderboard_snapshot_2026-10-11.json), source [leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)); the family ledger (*owner-report*, IR-32-SCORE-01) attributes that score to this file. **Byte-level attribution is not possible from public data — the value-to-file link remains an owner report.**

**The metric identity (measured-here, transcribed in `tests/test_metric.py` against the [official problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)):**

```
DTI = T / ( 0.2·(T + S − M) + 0.8·|G| )            (★)
```

with `T = Σ max p·k` (true-positive weight), `S` = emitted mass, `M` = credit-covering mass, `|G|` = hidden truth pixels, kernel `k(d)=max(1−d/300 m,0)`, α=0.2, β=0.8. Chasing through the family's two independently reported numbers for the d2.8 file (c = T/S = 0.0893, DTI 0.2600, S = 44,090 — counted) implies **|G| ≈ 7,905 px** of hidden truth (T≈M regime of a thin dotted file; the identity closes exactly: 3,937/(0.2·44,090 + 0.8·7,905) = 0.2600).

**Then why 0.2778?** Apply (★) to the b2 file with S = 37,654 dots, DTI 0.2778, same implied |G| = 7,905:

```
T = 0.2778 · (0.2·37,654 + 0.8·7,905) = 0.2778 · 13,855.1 = 3,849
credit per emitted px c = T/S = 3,849 / 37,654 = 0.1022        (vs 0.0893 for d2.8)
```

So the b2 file beat d2.8 by two levers that multiply inside (★): **(i) mean realised credit per pixel +14.4 %** (0.0893 → 0.1022 — better pixel choice: the catalogue-flank discriminant concentrates dots where hidden strands actually run), and **(ii) emitted mass −14.6 %** (44,090 → 37,654 — cutting pixels whose realised credit was below the metric's own break-even bar `0.2·DTI ≈ 0.0556`). Both move DTI the same direction; the field underneath is the same multi-physics H27/H33 family (magnetic/radiometric/DEM-lineament composite), **not a new detector**. The whole +0.018 is emission economics plus flank discrimination on a fixed field. (The same algebra at the original weights is documented in [`knowledge/01_why_0260_and_the_path_to_03195.md`](../../knowledge/01_why_0260_and_the_path_to_03195.md).)

## 2. Can we beat it? — what the same identity says, against today's verified board

The public top is now **0.4133** (xiaofanhu, verified snapshot 2026-10-11; the brief's quoted 0.3195/0.3774 figures are stale — IR-70-LB-01). Keeping S = 37,654 dots, the identity says the mean realised credit per pixel must be:

| target DTI | required c = T/S at S = 37,654 | vs b2's 0.1022 |
|---|---|---|
| 0.3195 (DARD, rank 8) | 0.1176 | **+15 %** |
| 0.3774 | 0.1389 | +36 % |
| **0.4133 (rank 1)** | **0.1522** | **+49 %** |

Two judgements follow with high confidence:

1. **No re-emission of the H19-5/H33 field closes +49 % at the same mass.** The family's measured credit per pixel has moved 0.0893 → 0.1022 across its entire two-week emission-optimisation campaign; +49 % more at fixed mass means the *pixels themselves* must come from a better field. This is a detector problem, not an emission problem — consistent with the repository's own ceiling analysis (`knowledge/02_the_ceiling_and_the_instrument.md`).
2. **The honest local compasses are the only defensible way to audition better fields**, and this repository measured that the catalogue hide-and-recover instrument inverts the live ordering (Spearman −0.90 vs live score; `evidence/e61_instrument_audit.json`, n = 12, INSTRUMENT class) while SGMC-off-catalogue truth is the least-bad positive compass (+0.47). Rounds 1–2 structure (final round re-scores top-5 against panel-verified **new** faults) is what makes off-catalogue skill the quantity that matters for the prize, per the [NREL GEMS report](https://docs.nlr.gov/docs/fy26osti/96647.pdf) and the [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).

**Answer: yes, beatable in principle — but only with a field that finds real faults the given catalogue lacks, validated on an instrument that at least weakly tracks live skill. Emission tuning alone is exhausted. That is precisely the lane hypothesis H70 tested, and the result is below.**

## 3. The candidate hypotheses considered this session (ranked at preregistration)

In-lane required: channel steepness / χ / knickpoints, not scarp shape. Each names layers, physical signature, why it catches *missing* faults, and what is new vs this repository.

| rank | hypothesis (#anchor) | layers | physical signature | why it should catch a catalogue-missing fault | expected DTI improvement vs cost (qualitative, registered upfront) |
|---|---|---|---|---|---|
| 1 (implemented) | **H70 paired-polarity knickpoint trains** | committed 3DEP-10 m χ/ksn reduction (`step_max`, `step_min`, `sig`), GeoDAWN K/Th | `pair_strength = min(crest, −step_min(500 m downstream))`: a migrating incision wave is two opposite-polarity χ-slope steps on one branch (Kirby & Whipple 2012; Berlin & Anderson 2007) | single-flank mimics (lithologic contacts, washes) are filtered *by the pairing itself*, so surviving aligned pairs should be tectonic | medium-high / low (all data committed). **Measured: NEGATIVE on the gate** |
| 2 | **H71 paired-basin ksn contrast across fault blocks** | 3DEP 10 m tiles (18, ~6.7 GB, fetchable – §6) + SGMC units | block-scale: median log-ksn residual contrast between catchments *paired* across the fault on area, outlet class, unit, cover | a whole-catchment tectonic response survives where a pixel crossing is ambiguous; E1b of H70 says the paired signal lives on mapped-but-uncatalogued structures, and basin scale is the next population | high / high (new substrate + preregistered E1a+E1b both gating) |
| 3 | **H74 cross-divide χ asymmetry (Gilbert metrics)** | same 10 m substrate | χ computed at drainage divides; divide asymmetry/migration under differential uplift (Willett et al. 2014, *Science* 343, 1248765, doi:10.1126/science.1248765) | divides re-equilibrate in front of moving faults; a migrating-divide signal marks active structures even where channels are masked | medium / medium-high (divide extraction needs the 10 m network; the committed 100 m drainage failed validity checks) |
| 4 | **H72 hydroclimate/permanence-matched ksn residual** | PRISM 1991–2020 normals + 3DHP permanence + committed χ/ksn | residual steepness after matching precipitation/runoff/permanence strata | removes the confound family the brief names explicitly; fault signal isolated from climate mimics | medium / medium-high (free official data, not yet fetched – §6) |
| 5 | **H73 outlet/base-level-conditioned profile residual** | 3DEP + closed-basin/playa outlines + committed χ/ksn | profile residuals compared only within matched outlet classes, downstream alluvial length censored | removes playa-pluvial knickpoints that dominate the raw knickpoint census | medium / medium |

## 4. H70 — what was measured (every number from evidence, labeled)

**First test G1 (GATING, withheld catalogue segments; identical kernel, draw and seeds to every prior lane run; MEASUREMENT):**
- `n = 241` components scored (85 skipped: no valid channel crossing within 3 px for the paired statistic)
- mean paired-step contrast **−0.0347**, median **+0.0491**, 95 % CI **[−0.0853, +0.0126]** (1,000 component-resample draws, seed 60101), 60.2 % of components positive
- verdict per the preregistered rule (PROCEED requires mean > 0 **and** CI lower bound > 0): **STOP**
- Distribution reading (descriptive only, no rescue): median positive with mean negative — a minority of withheld crossings shows a strong paired-step *deficit*; the skew kills the pooled contrast.

**Ablation / tool verification (MEASUREMENT).** The identical first test on the raw single-limb statistic (crest only) reproduces H65-1's published INCONCLUSIVE to ~1e-9 (mean 0.032591208 vs 0.032591209; CI [−0.0143535868, +0.0789952321] vs [−0.0143535845, +0.0789952332]) — the runner is the shared one, not a fork.

**E1b diagnostic — NON-GATING by preregistration (SGMC faults > 300 m off-catalogue; MEASUREMENT):**
- `n = 85`, mean **+0.0567**, median **+0.0530**, 95 % CI **[+0.0103, +0.1030]**, 62.4 % positive — would be PROCEED if it had been the gate. It wasn't. H66's single-limb dksn on this same population was **−0.113 (STOP)**; the sign flip (+0.17 of mean contrast) is recorded as research evidence for H71, and changes nothing about H70's verdict, because the gates were registered before any number existed.

**Downstream products per the protocol:** no surface, no emission, no holdout bench, no uniqueness scan (nothing exists to scan), no raster, no validator receipt. The budget ledger stands at **1 of 3 experiments used; the run stopped at the protocol's own stop condition.**

## 5. What H70 actually teaches (the honest scientific read)

1. **Knickpoint *pairing* is a different instrument from knickpoint *magnitude*.** On the off-catalogue population the paired statistic is the first in the lane's five-statistic history to come out clearly positive where the single-limb statistics were negative or null. On the catalogue-withheld population it fails. Conjunction: the paired signal exists on *older mapped* structure geometry but does not mark the *active* Quaternary strand population the given catalogue samples.
2. **Crossing-scale tests may be the wrong unit for a basin-scale phenomenon.** That motivates H71 (paired-basin contrast) as the next preregistered question, with E1a and E1b *both* gating, declared in advance — including the possibility that it too returns negative and the lane closes with a documented null.
3. **Governance hygiene matters as much as statistics.** The repository currently contains a STOP status and a later `promote` run card for the same lane (IR-70-GOV-01), and a five-statistic selection history across E1 (IR-70-SEL-01). Both are now logged in the ledger; this session added a measured result *without* editing either contested record.

## 6. External data obtainability check for the top next candidate (H71)

| source | what H71 needs | licence | obtainable? | check performed |
|---|---|---|---|---|
| [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) 1/3-arc-second DEM | 18 tiles (the committed manifest's URLs at `https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/…`, ~380–420 MB each, listed with sha256 in `data/external/dem10_chi_100m.manifest.json`) | public domain (USGS) | **YES** — the repository's own CI workflow already fetched them once (run id `38115164310`, manifest); NOT fetchable from this sandbox (host outside the allowed egress list) — must run on CI or any unrestricted machine, exactly like the competition-data step in the README | manifest URLs + byte sizes + sha256 committed |
| [USGS SGMC](https://mrdata.usgs.gov/geology/state/) ([DOI 10.5066/F7WH2N65](https://doi.org/10.5066/F7WH2N65)) | map units for erodibility pairing | public domain (USGS) | **YES** — raster already committed (`data/external/derived_sgmc_faults_100m_u8.tif`, pin-checked) | pin check passes |
| [PRISM Climate Group](https://prism.oregonstate.edu/) 1991–2020 normals | precipitation/runoff strata for H72 | free for research | plausible; not fetched, not needed for H71's gate | page describes public download; no fetch attempted here |
| [USGS 3DHP](https://www.usgs.gov/3d-hydrography-program) | flow permanence (H72/H73) | public domain | coverage/attribution for the footprint must be verified before preregistration — flagged, not assumed | program status page reviewed in prior session notes ([product access](https://www.usgs.gov/national-hydrography/access-national-hydrography-products)) |

Conclusion: **H71 is viable** — its required inputs are committed or fetchable from the documented official endpoints; no new login-gated data is needed.

## 7. Irregularities flagged this session (all written to `registry/irregularities.json`)

| id | severity | one-liner |
|---|---|---|
| IR-70-GOV-01 | medium | `current_site_status.json` (STOP) and `evidence/h67_runcard.json` (promote) coexist for one lane; reconciled by logging, not by editing either record |
| IR-70-SEL-01 | medium | five-statistic selection history across the lane's first test must travel with every E1 verdict (2 of 5 gated runs passed) |
| IR-70-DATA-01 | medium | H66-1's "piedmont profile curvature" reads topo band 4 `slope_std` (not band 6 `curv_prof_absmax`) in raw codes; features66 not rebuildable as committed (`training_features.tif` absent, IR-66-DATA-01) |
| IR-70-LB-01 | low | brief's 0.3195 / 0.3774 targets are stale; verified 2026-10-11 public top is 0.4133 |

## 8. Sources for manual review

- Competition: [overview & rules](https://www.drivendata.org/competitions/306/competition-doe-gems/) · [problem description & metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) · [about / data sources](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/) · [leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) · [data downloads (login)](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) · [reference solution](https://github.com/drivendataorg/gems-prize-reference-solution)
- Reports/data: [NREL GEMS report 96647](https://docs.nlr.gov/docs/fy26osti/96647.pdf) · [GDR submission 1391](https://gdr.openei.org/submissions/1391) · [GeoDAWN (USGS)](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) · [INGENIOUS (GBCGE)](https://gbcge.org/current-projects/ingenious/) · [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) · [USGS SGMC](https://mrdata.usgs.gov/geology/state/) + [DOI](https://doi.org/10.5066/F7WH2N65) · [PRISM](https://prism.oregonstate.edu/) · [USGS 3DHP](https://www.usgs.gov/3d-hydrography-program)
- Papers (all DOIs verified this session against the publishers' records): Kirby & Whipple 2012 [doi:10.1016/j.jsg.2012.07.009](https://doi.org/10.1016/j.jsg.2012.07.009) · Perron & Royden 2013 [doi:10.1002/esp.3302](https://doi.org/10.1002/esp.3302) · Gailleton et al. 2019 [doi:10.5194/esurf-7-211-2019](https://doi.org/10.5194/esurf-7-211-2019) · Wobus et al. 2006 [doi:10.1130/2006.2398(04)](https://doi.org/10.1130/2006.2398(04)) · Berlin & Anderson 2007 [doi:10.1029/2006JF000553](https://doi.org/10.1029/2006JF000553)
