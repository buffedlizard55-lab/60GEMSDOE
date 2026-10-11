# Five ranked, untried hypotheses for the tectonic-geomorphology lane

Ranked by **expected DTI gain per unit of implementation cost**. Every row names the
specific layer(s) involved, the physical signature being targeted, why the hypothesis
should catch a fault that is *missing* from the USGS/INGENIOUS catalogue rather than one
already in it, and how it differs from everything already built in the family's
repositories.

A caution that applies to the whole table, measured in this session and by the family:
the only local truth available is the visible catalogue, and that instrument is
**anti-monotone** against the live ladder (family `IR-57-INSTR-01`, ρ = −0.93; this
session's Experiment 3 reproduces the mechanism). A hypothesis can therefore only be
*killed* locally, never *confirmed* locally. Rank 1 is the exception: it re-runs a test
whose failure mode at 100 m is a resolution artefact, so a local pass or fail is
informative in both directions.

---

## 1. Re-run **this exact lane** on a 10 m DEM (rank 1 — highest expected gain)

* **Layers.** 3DEP 10 m DEM (or the 1 m GeoDAWN LiDAR tiles the competition links in
  `1m_DEM_links.csv`). The official 19-band stack stays only as a confound/context layer.
* **Physical signature.** χ-profile segmentation and normalised channel steepness
  `ksn = d z / dχ`, exactly as implemented here — but with 10× finer sampling of the
  base-level step.
* **Why it should catch an *unmapped* fault.** The hypothesis has never actually been
  tested. At 100 m the channel is a 1-px line and the DEM's vertical noise is comparable
  to the step; at 10 m a 2–5 m base-level step is resolved. A degraded, buried scarp can
  keep a 10 m-resolved channel step after a curvature transform sees nothing.
* **Why it differs from existing work.** The family's entire topographic history is
  `det_elev` / `det_elev_slope` — a *detrended* grid, from which a χ transform cannot be
  computed at all. This session added the first absolute-elevation DEM the family has
  ever had (`22103_dem_a2.tif`), and this hypothesis is the same method one resolution
  step finer.
* **Measured basis for the rank.** Experiment 1 and Experiment 2 both returned STOP at
  100 m (AUC 0.4795 pooled, CI95 [−0.0806, −0.0065] — wrong sign). The single parameter
  that is most likely to be responsible is the grid spacing, and it has not been varied.
* **Cost.** Low: `src/gems60/*` runs unchanged; only the DEM path changes. One
  re-registered run of `scripts/exp1_first_test.py`.
* **Data needed.** Free and official: USGS 3DEP via the National Map bucket
  `prd-tnm.s3.amazonaws.com` (projects `CA_SierraNevada_B22`,
  `NV_WestCentral_EarthMRI_2020_D20`, `NV_Humboldt_2021_D21`, per the competition's own
  DEM-links JSON). **Obtainability in this sandbox: verified NOT available** — the host
  returns HTTP 000 (see `evidence/connectivity.json`). `scripts/fetch_3dep_10m.sh` is
  written and ready.

## 2. χ-transient inversion instead of a χ-steady step (rank 2)

* **Layers.** A DEM only (no magnetics, no radiometrics).
* **Physical signature.** Invert χ(z) for a *history* of uplift `U(t)` rather than a
  present-day step: a fault that started moving recently produces a knickpoint that has
  not yet propagated to the outlet, i.e. a χ-position that is diagnostic of its age, not
  of its existence (Pritchard et al. 2009; Fox et al. 2014).
* **Why *off*-catalogue.** Recently initiated faults are exactly the ones mapping missed —
  their scarps are young but short and disconnected. A steady-state `ksn` anomaly at a
  range front is what the catalogue already contains; a *transient* anomaly is what it
  does not.
* **Why it differs.** Nothing in any GEMSDOE repository has ever inverted a river profile
  for uplift history; the family has only ever used elevation as a static raster channel
  or a curvature filter.
* **Cost.** Medium (new solver, but a matrix-free 1-D inversion per channel).
* **Data needed.** None beyond the DEM already committed.

## 3. Knickpoint **recurrence in χ**, not knickpoint position (rank 3)

* **Layers.** DEM only.
* **Physical signature.** Instead of scoring where a knickpoint is, score where steps
  *recur at the same χ across independent drainages*. A lithologic step sits at a fixed
  elevation and therefore at a *different* χ in every basin; a base-level step sits at a
  fixed χ shared by every basin draining to the same base level.
* **Why *off*-catalogue.** This is a purely *relative* test between drainages, so it is
  blind to whether the fault is mapped; a mapped fault produces a step that the catalogue
  already explains, while an unmapped one produces a χ-recurrence with no map line to
  attribute it to.
* **Why it differs.** Experiment 2 measured the *position* of steps (AUC 0.4795,
  chance). Recurrence in χ was not tested: `channel_step_statistic` dedupes to one value
  per pixel and never compares χ across basins — the family's H33 "drainage-valley-chain"
  field also never compared χ.
* **Cost.** Low — the χ surface is already computed and cached.
* **Data needed.** None.

## 4. Closed-basin / playa base-level mask (rank 4)

* **Layers.** DEM only; optionally the climate and Quaternary-volcanics layers as
  confound controls.
* **Physical signature.** The priority-flood depression inventory. This session filled
  **899,623 cells (17.4 % of the valid grid)** — the Great Basin's internal drainage. A
  playa sets base level by evaporation, so it manufactures steps with no tectonic cause.
* **Why *off*-catalogue.** It removes false positives; it does not add discoveries. Its
  value is that it is the **named confound** in the brief and it is currently unmasked in
  every family artefact.
* **Why it differs.** No GEMSDOE repository masks internal-drainage base levels.
* **Cost.** Very low (`hydro.closed_basin_flats` is written; only a threshold is unset).
* **Data needed.** None.

## 5. Lithology-normalised ksn in the Great Basin (rank 5)

* **Layers.** DEM + `great_basin_q_volcanics` (publicly mirrored in the same GitHub tree
  already used for the DEM) + `det_elev_slope` as a relief control.
* **Physical signature.** `ksn` residual after regressing out an erodibility proxy:
  `ksn = (U/K)^(1/n)`, so a lithology contrast without an uplift contrast mimics a fault.
* **Why *off*-catalogue.** It converts a *tectonic* residual into the detection target, so
  a fault whose surface trace is buried under young volcanic cover — which mapping cannot
  see — can still appear as an uplift residual.
* **Why it differs.** The family's geology layers (`sgmc`, `qfaults`) have only ever been
  used as *catalogue* or as *distance features*, never as an erodibility normalisation of a
  topographic statistic.
* **Cost.** Medium (needs a lithology raster in the competition grid).
* **Data needed.** `great_basin_q_volcanics/great_basin_flows.shp` in
  <https://github.com/jklinck/geothermal_research> — public, free, already mirrored.
