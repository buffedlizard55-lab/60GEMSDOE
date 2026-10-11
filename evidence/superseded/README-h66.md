# Superseded H66 artefacts (kept, never shipped)

`gems60-h66-offcat-knick-37654-20261011T160106Z-b37f96d829b7-zeros.{tif,zip,json}` was the
**first** H66 emission, built at the lane's declared parameters (upstream-steepening limb,
`step_max`) on the native-10 m cache with the radiometric confound substitution.

It was **rejected by the parallel-run protocol's uniqueness gate and never published to
`docs/downloads/`**:

| gate | value | limit | verdict |
|---|---|---|---|
| \|Spearman\| vs `docs/downloads/gems60-h65-dem10-knick-40000-…-zeros.tif` | 0.7141 | 0.90 | pass |
| share of its dots within 3 px of that same file | **0.7572** | 0.70 | **FAIL** |
| excess over 5 mass-matched random dot sets | +0.7285 | — | a real overlap, not a dense-prior artefact |

`evidence/superseded/h66_uniqueness.json` holds the full 68-raster scan.

Mechanism, stated plainly: the lane's emission is *determined* by its declared parameters, so
changing only the confound mask (radiometric K/Th in place of the unavailable
`depth_to_base`/`cond_surf` bands) and the dot budget (37,654 in place of 40,000) moved only
about a quarter of the dots. **A lane run that reuses the declared parameters cannot produce a
unique artefact.** That is the finding, and it is why the shipped H66 file uses the other limb of
the same two-segment statistic (`GEMS60_STEP_STATISTIC=abs`, `max(step_max, -step_min)`), which
changes 53,116 candidate pixels in place of 43,131 and is a physically distinct hypothesis
(H66-2, downstream-steepening limb in alluvial hanging-wall ground).
