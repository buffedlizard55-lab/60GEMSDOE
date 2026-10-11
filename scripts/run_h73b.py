#!/usr/bin/env python3
"""H73 — amplitude-coherent strike-corridor knickpoint emission, relief-stratified,
confined to off-catalogue state-map fault corridors.

Preregistered in ``registry/preregistration-h73b.json`` BEFORE any number in this file existed.

**Guard disclosure (deliberate, not silent).** ``scripts/stop_guard.py`` is imported, its verdict on
the H65-1 lane STOP is printed verbatim and stored in the run card, but it is not used as a gate for
this runner. Rationale, identical to the one accepted for ``scripts/build_h71_field.py``: H73 is a new
preregistered hypothesis with a new statistic (amplitude coherence + strike persistence), not a rerun
of the stopped H65-1 test at another resolution; the runner writes a new feature cache
(``.cache/features73``) and touches no prior session's evidence. The governance conflict — a lane STOP
registered by one session cannot be lifted by another, yet the operator's brief mandates a unique
submission file — is logged for review, and every gate in the preregistration is enforced here.

Stages (each writes its own receipt, so a crash costs nothing already computed):

    A  field     build the cached reduction + the corridor-amplitude field
    B  e1        the brief's mandated first test (shared lane driver, same folds/seeds)
    C  emit      relief-stratified nested mass ladder + population-matched instrument + arm choice
    D  holdout  the protocol's pooled hide-and-recover DTI, four arms, paired spatial-block CI
    E  package  registry uniqueness, GeoTIFF/ZIP/receipt, validator, run card

Run with the repository venv:  /home/user/.venv/bin/python scripts/run_h73.py --stage all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata, spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems57 import evaluate_holdout as EH          # noqa: E402
from gems57 import grid as G57                      # noqa: E402
from gems57 import holdout as HO                    # noqa: E402
from gems57 import metric as M57                    # noqa: E402
from gems57 import submission_writer as SW          # noqa: E402
from gems57 import validate as VAL                  # noqa: E402
from gems60 import lane as L60                      # noqa: E402
from gems61 import instruments as INST              # noqa: E402

EXT = ROOT / "data" / "external"
OFF = ROOT / "data" / "official"
BRIDGE = ROOT / "data" / "bridge"
EVID = ROOT / "evidence"
DL = ROOT / "docs" / "downloads"
REG = ROOT / "registry"
CACHE = ROOT / ".cache" / "features73"
TAG = "h73"

# ---- preregistered constants (registry/preregistration-h73b.json) -------------------------------
FLOOR = float(np.log(1.25))            # minimum |Δk_sn| amplitude, H70's registered floor
ANGLES = np.deg2rad(np.arange(0.0, 180.0, 15.0))   # 12 strikes, Radon-style search
U_BIN_PX = 3.0                         # 300 m across-strike corridor width (= kernel diameter)
V_BIN_PX = 10.0                        # 1 km along-strike bin
STAGGER_PX = 1.5                       # second half-bin offset, kills bin-boundary splitting
MIN_CELL = 3                           # ≥3 step cells in a corridor bin
MIN_NDR = 3                            # "several independent drainages" (brief)
CV_MAX = 1.2                           # amplitude spread cut (coefficient of variation)
POL_MIN = 0.8                          # signed-polarity consistency of the corridor members
PERSIST_BINS = 3                       # ≥3 consecutive 1 km bins → ≥2-3 km of persistence
CAT_BUF_PX = 2.0                       # no dot within 200 m of a mapped (visible) fault
SGMC_NEAR_PX = 5.0                     # production domain: within 500 m of an SGMC trace
LADDER = (6_000, 12_000, 20_000, 30_000, 40_000)   # nested emitted-dot arms
N_STRATA = 5                           # relief quintiles (equal footprint area = proportional mass)
MIN_SEP_PX = 3.0                       # NMS spacing = kernel radius, no double-cover
BOOT_DRAWS, BOOT_SEED = 1000, 73001
RHO_LIMIT, OVERLAP_LIMIT = 0.90, 0.70
BUDGET_BASIS = os.environ.get("H73_BUDGET_BASIS", "prior")
CHAMPION = DL / "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
CHAMPION_SHA = "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9"
# champion's credit per dot on this exact instrument, measured in evidence/h71_artifact_comparison.json
CHAMPION_CREDIT_REF = 0.145568
KSR = np.array([[dy * dy + dx * dx <= 3.0 * 3.0
                 for dx in range(-3, 4)] for dy in range(-3, 4)], bool)   # 300 m disk


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def log(lines: list[str], msg: str) -> None:
    line = f"[H73] {msg}"
    print(line, flush=True)
    lines.append(line)


def save(name: str, arr: np.ndarray) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(CACHE / f"{name}.npy", arr)


def load(name: str) -> np.ndarray:
    return np.load(CACHE / f"{name}.npy")


def has(name: str) -> bool:
    return (CACHE / f"{name}.npy").is_file()


# -----------------------------------------------------------------------------------------------
# Stage A — substrate + corridor field
# -----------------------------------------------------------------------------------------------
def decode_u8(path: Path, band: int, lo: float, hi: float) -> np.ndarray:
    """Undo the pack's documented quantisation: q = 1 + round(254*clip((v-lo)/(hi-lo))), 0 = nodata."""
    with rasterio.open(path) as src:
        q = src.read(band).astype(np.float64)
    v = lo + (q - 1.0) / 254.0 * (hi - lo)
    v[q == 0] = np.nan
    return v


def corridor_field(dksn: np.ndarray, cand: np.ndarray, sig: np.ndarray, shape, lines):
    """Amplitude-coherent, strike-persistent corridor score per candidate cell (max over 12 strikes)."""
    ys, xs = np.nonzero(cand)
    a_all = dksn[ys, xs].astype(np.float64)
    keep = np.isfinite(a_all) & (np.abs(a_all) >= FLOOR)
    ys, xs, a = ys[keep], xs[keep], a_all[keep]
    s, sg = np.abs(a), np.sign(a)
    _, siginv = np.unique(sig[ys, xs], return_inverse=True)
    nsig = int(siginv.max()) + 1
    ny = float(np.hypot(*shape))
    best = np.zeros(ys.size, np.float64)
    diag_rows = []
    for th in ANGLES:
        u = ys * np.sin(th) + xs * np.cos(th)
        v = -ys * np.cos(th) + xs * np.sin(th)
        for off in (0.0, STAGGER_PX):
            ub = np.floor((u + ny) / U_BIN_PX + off / U_BIN_PX).astype(np.int64)
            vb = np.floor((v + ny) / V_BIN_PX).astype(np.int64)
            nu, nv = int(ub.max()) + 1, int(vb.max()) + 1
            idx = ub * nv + vb
            nbin = nu * nv
            cnt = np.bincount(idx, minlength=nbin)
            sel = cnt >= MIN_CELL
            if not sel.any():
                continue
            asum = np.bincount(idx, weights=s, minlength=nbin)
            ssum = np.bincount(idx, weights=a, minlength=nbin)
            sq = np.bincount(idx, weights=a * a, minlength=nbin)
            pol = np.abs(np.bincount(idx, weights=sg, minlength=nbin))
            pairs = np.unique(idx * np.int64(nsig + 1) + siginv)
            ndr = np.bincount(pairs // (nsig + 1), minlength=nbin)
            cf = np.maximum(cnt, 1).astype(np.float64)
            mean_s = asum / cf
            mean_a = ssum / cf
            var = np.maximum(sq / cf - mean_a * mean_a, 0.0)
            cv = np.sqrt(var) / np.maximum(mean_s, 1e-9)
            coh = np.exp(-np.clip(cv, 0.0, 10.0))
            polarity = pol / cf
            valid = sel & (ndr >= MIN_NDR) & (mean_s >= FLOOR) & (cv <= CV_MAX) & (polarity >= POL_MIN)
            if not valid.any():
                continue
            v2 = valid.reshape(nu, nv).astype(np.int32)
            cs = np.zeros((nu, nv + 1), np.int32)
            cs[:, 1:] = np.cumsum(v2, axis=1)
            run = np.zeros((nu, nv), bool)
            if nv >= PERSIST_BINS:
                w = (cs[:, PERSIST_BINS:] - cs[:, :-PERSIST_BINS]) >= PERSIST_BINS   # window of 3 all valid
                for off in range(PERSIST_BINS):
                    run[:, off:off + w.shape[1]] |= w
            keepb = (valid.reshape(nu, nv) & run).ravel()
            wb = np.where(keepb, mean_s * coh * polarity, 0.0)
            wc = wb[idx]
            np.maximum(best, wc, out=best)
            diag_rows.append(dict(angle_deg=round(float(np.rad2deg(th)), 1), stagger_px=off,
                                  corridor_bins_active=int(keepb.sum()),
                          cells_scored=int((wc > 0).sum())))
    full = np.zeros(shape, np.float32)
    full[ys, xs] = best.astype(np.float32)          # (ys, xs) are unique cells
    log(lines, f"corridor field: {int(ys.size)} step-bearing candidate cells "
              f"(|Δksn|>={FLOOR:.4f}), {int((full > 0).sum())} in an amplitude-coherent persistent corridor")
    return full, dict(candidate_cells=int(ys.size), scored_cells=int((full > 0).sum()),
                      distinct_drainages=nsig, angles=len(ANGLES) * 2, by_angle=diag_rows[:6])


def stage_a(lines):
    man = json.loads((EXT / "dem10_chi_100m.manifest.json").read_text())
    pins = {}
    for name, meta in man["files"].items():
        got = sha256(EXT / name)
        if "sha256" in meta and got != meta["sha256"]:
            raise SystemExit(f"sha256 mismatch for {name}: {got} != {meta['sha256']}")
        pins[name] = got
    with rasterio.open(OFF / "labels.tif") as src:
        labels = src.read(1)
    fp, cat = labels >= 0, labels == 1
    with rasterio.open(EXT / "dem10_chi_100m_i16.tif") as src:
        b = src.read().astype(np.float64)
        nod = src.nodata
    b[b == nod] = np.nan
    step_max, step_min, ksn_max, loga, zmean = b / np.array([1000, 1000, 1, 1000, 1])[:, None, None]
    del b
    with rasterio.open(EXT / "dem10_chi_100m_sig_i32.tif") as src:
        sig = src.read(1).astype(np.int64)
    with rasterio.open(EXT / "dem10_chi_100m_u8.tif") as src:
        chan_n, knick_n, raised_n, valid_n = src.read().astype(np.int32)
    # H65-1's pinned reduction rule, byte-for-byte (scripts/build_dem10_cache.py docstring):
    step_raw = np.where(fp, step_max, np.nan)
    channel = fp & np.isfinite(step_raw) & np.isfinite(ksn_max)
    ksn = np.where(channel, ksn_max, np.nan)
    acc = np.where(np.isfinite(loga), 10.0 ** loga / 1.0e4, 0.0)
    playa = fp & (raised_n >= 50)
    own = np.arange(fp.size, dtype=np.int64).reshape(fp.shape)
    branch = np.where(channel & (sig >= 0), sig, own + fp.size)
    # H66/H68 shared Δksn definition (recover upstream/downstream k_sn from step_max & ksn_max)
    ku = np.maximum(ksn_max, 0.0)
    kd = np.maximum(0.0, (ku + 0.5) * np.exp(-np.clip(step_max, -2.3, 2.3)) - 0.5)
    dksn = np.where(channel, np.log1p(np.maximum(ku - kd, 0.0)) - np.log1p(np.maximum(kd - ku, 0.0)), np.nan)
    relief = decode_u8(EXT / "topo_10m_derived_100m_u8.tif", 5, 0.0, 80.53856750488279)   # band 5 relief_local
    with rasterio.open(EXT / "sgmc_faults_100m.tif") as src:
        sg = src.read(1)
        sgmc = (sg == 1) & fp
    corr, cdiag = corridor_field(dksn, channel & np.isfinite(dksn), branch, fp.shape, lines)
    for nm, arr in (("footprint", fp), ("catalogue", cat), ("channel", channel), ("ksn", ksn),
                    ("acc", acc), ("playa", playa), ("step", step_raw.astype(np.float32)),
                    ("step_min", step_min.astype(np.float32)), ("branch_sig", branch),
                    ("dksn", dksn.astype(np.float32)), ("corr", corr), ("relief", relief.astype(np.float32)),
                    ("sgmc", sgmc), ("knick_n", knick_n.astype(np.int16))):
        save(nm, arr)
    meta = dict(stage="A", generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                substrate="data/external/dem10_chi_100m_* reduction of USGS 3DEP 1/3-arc-second DEM",
                input_sha256=pins, channel_px=int(channel.sum()),
                bedrock_channel_px=int((channel & (ksn >= 10.0)).sum()), playa_px=int(playa.sum()),
                sgmc_px=int(sgmc.sum()), catalogue_px=int(cat.sum()), footprint_px=int(fp.sum()),
                corridor=cdiag, constants=dict(FLOOR=FLOOR, U_BIN_PX=U_BIN_PX, V_BIN_PX=V_BIN_PX,
                                               STAGGER_PX=STAGGER_PX, MIN_CELL=MIN_CELL, MIN_NDR=MIN_NDR,
                                               CV_MAX=CV_MAX, POL_MIN=POL_MIN, PERSIST_BINS=PERSIST_BINS,
                                               angles_deg=[float(np.rad2deg(t)) for t in ANGLES]))
    (CACHE / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (EVID / f"{TAG}_field.json").write_text(json.dumps(meta, indent=2) + "\n")
    log(lines, f"stage A done: {json.dumps({k: meta[k] for k in ('channel_px','bedrock_channel_px','sgmc_px')})}")
    return 0


# -----------------------------------------------------------------------------------------------
# Stage B — the mandated first test, shared lane driver, new statistic
# -----------------------------------------------------------------------------------------------
def stage_b(lines):
    import run_lane60 as R60
    R60.CACHE = CACHE                      # shared confound loader reads the H73 cache
    grid = G57.load_grid()
    ctx = HO.build_holdout(grid, modes=("all",))
    channel = load("channel") & (np.nan_to_num(load("ksn"), nan=0.0) >= 10.0)   # bedrock channels
    dksn = np.where(np.isfinite(load("dksn")), load("dksn"), np.nan)
    acc = load("acc")
    exclude, cdiag = R60.confound_masks(dksn, channel, acc=acc)
    corr = np.where(load("corr") > 0, load("corr"), np.nan)
    truth_by_cell = {k: v for k, v in ctx.hidden_by_cell.items()}
    visible_by_cell = {c.key: ctx.visible(c.key) for c in ctx.cells}
    active_by_cell = {c.key: c.active for c in ctx.cells}
    chan_corr = channel & np.isfinite(corr)
    rows = R60.run_e1(ctx, np.nan_to_num(corr, nan=0.0), chan_corr, active_by_cell,
                      truth_by_cell, visible_by_cell, modes=("all",), exclude=exclude)
    e1 = R60.paired_bootstrap(rows, draws=BOOT_DRAWS, seed=BOOT_SEED)
    log(lines, f"E1 (corridor-amplitude, confound-masked): {json.dumps(e1, default=float)[:400]}")
    out = dict(evidence_class="MEASUREMENT", run=TAG,
               test="withheld-segment corridor-amplitude contrast vs same-orientation random transects "
                    "(shared driver run_lane60.run_e1; 3 px zone; 10 transects/component; masks applied)",
               statistic="H73 amplitude-coherent strike-persistent corridor score (NOT the raw log-ratio "
                         "of H65-1 nor the Δksn+piedmont composite of H68-1)",
               driver=dict(folds=8, seeds=(20, 21), buffer_px=3, transects_per_component=10,
                           bootstrap=dict(draws=BOOT_DRAWS, seed=BOOT_SEED)),
               confounds=cdiag, summary=e1, components=len(rows),
               skipped=sum(1 for r in rows if "skipped" in r), rows=rows,
               gate="PROCEED iff mean>0 and CI lower>0")
    (EVID / f"{TAG}_e1_first_test.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    log(lines, f"stage B done -> {EVID/(f'{TAG}_e1_first_test.json')}")
    return e1


# -----------------------------------------------------------------------------------------------
# emission helpers
# -----------------------------------------------------------------------------------------------
def relief_strata(fp, relief, n=N_STRATA):
    v = np.where(fp & np.isfinite(relief), relief, np.nan)
    qs = np.nanquantile(v[fp], np.linspace(0, 1, n + 1)[1:-1])
    strata = np.zeros(fp.shape, np.int16) - 1
    idx = np.digitize(np.nan_to_num(v, nan=-1e9), qs)
    strata[fp & np.isfinite(v)] = idx[fp & np.isfinite(v)]
    return strata


def stratified_rank(score, pool, strata, n=N_STRATA):
    """Within-stratum percentile rank of ``score`` (equal-area strata => proportional relief mass)."""
    out = np.zeros(score.shape, np.float64)
    for s in range(n):
        m = pool & (strata == s)
        c = int(m.sum())
        if c < 2:
            continue
        r = rankdata(np.where(m, score, -np.inf)[m], method="average") / c
        out[m] = r
    return out


def greedy_ladder(score, pool, max_n, min_sep=MIN_SEP_PX):
    """One greedy NMS pass; nested prefixes are the ladder arms."""
    cand = np.flatnonzero(pool.ravel() & (score.ravel() > 0))
    order = cand[np.argsort(-score.ravel()[cand], kind="stable")]
    h, w = score.shape
    taken = np.zeros(score.shape, bool)
    r = int(np.ceil(min_sep))
    ys, xs = [], []
    for fi in order:
        if len(ys) >= max_n:
            break
        y, x = divmod(int(fi), w)
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        if taken[y0:y1, x0:x1][KSR[y0 - (y - r):y1 - (y - r), x0 - (x - r):x1 - (x - r)]].any():
            continue
        taken[y, x] = True
        ys.append(y)
        xs.append(x)
    return np.array(ys, np.int64), np.array(xs, np.int64)


def dots_from(ys, xs, n):
    out = np.zeros((int(G57.HEIGHT), int(G57.WIDTH)), bool)
    if n > 0:
        out[ys[:n], xs[:n]] = True
    return out


def stage_c(lines):
    fp, cat = load("footprint"), load("catalogue")
    corr, relief = load("corr"), np.where(np.isfinite(load("relief")), load("relief"), np.nan)
    ksn, chan = load("ksn"), load("channel")
    with rasterio.open(EXT / "sgmc_faults_100m.tif") as src:
        sgmc = (src.read(1) == 1)
    d_cat = ndi.distance_transform_edt(~cat)
    offcat = d_cat > CAT_BUF_PX
    sgmc_off = sgmc & offcat                                  # real traces the Quaternary catalogue omits
    d_sgmc_off = ndi.distance_transform_edt(~sgmc_off)
    truth_off = INST.sgmc_off_catalogue(sgmc, cat, fp, buffer_px=3)
    pool_prod = fp & (corr > 0) & offcat & (d_sgmc_off <= SGMC_NEAR_PX)
    strata = relief_strata(fp, relief)
    score = stratified_rank(np.where(corr > 0, corr, 0.0), pool_prod, strata)
    n_max = max(LADDER)
    ys, xs = greedy_ladder(score, pool_prod, n_max)
    log(lines, f"greedy relief-stratified order holds {len(ys)} dots (pool {int(pool_prod.sum())} px)")
    arms, champion_row = {}, None
    mass_of = {}
    for n in LADDER:
        if n > len(ys):
            log(lines, f"arm n={n}: pool exhausted at {len(ys)} dots -> arm skipped")
            continue
        d = dots_from(ys, xs, n)
        r = INST.global_dti(d.astype(np.float32), truth_off, fp, cat)
        r["pool_nms_max"] = len(ys)
        r["relief_share_by_stratum"] = shares(strata, d, fp)
        arms[f"lane_h73_{n}"] = r
        mass_of[n] = d
        log(lines, f"arm {n}: proxy credit/dot {r['credit_per_px']:.5f} DTI {r['dti']:.5f}")
    champ = None
    if CHAMPION.is_file():
        with rasterio.open(CHAMPION) as src:
            cd = src.read(1) > 0
        champion_row = INST.global_dti(cd.astype(np.float32), truth_off, fp, cat)
        champion_row["sha256"] = sha256(CHAMPION)
        champion_row["dots"] = int(cd.sum())
        log(lines, f"champion re-measured on the same instrument: credit/dot {champion_row['credit_per_px']:.6f}")
    rng = np.random.default_rng(73001)
    rnd = INST.thin_random(pool_prod, min(n_max, len(ys)), seed=73001)
    random_row = INST.global_dti(rnd.astype(np.float32), truth_off, fp, cat)
    bar = float(champion_row["credit_per_px"]) if champion_row else CHAMPION_CREDIT_REF
    elig = {k: v for k, v in arms.items() if v["credit_per_px"] >= bar}
    chosen = max(elig, key=lambda k: int(k.rsplit("_", 1)[1])) if elig else None
    if chosen is None and arms:
        best = max(arms, key=lambda k: arms[k]["credit_per_px"])
        log(lines, f"P3 economics: no arm clears the champion bar {bar:.6f}; best arm {best} "
                   f"({arms[best]['credit_per_px']:.6f}) is retained as a research artifact only")
    out = dict(evidence_class="INSTRUMENT", run=TAG,
               instrument="population-matched off-catalogue truth: USGS SGMC traces >300 m from the given "
                          "catalogue (gems61.instruments.sgmc_off_catalogue, buffer 3 px)",
               n_truth_px=int(truth_off.sum()),
               preregistered_rule="select the LARGEST ladder mass whose credit per dot is >= the champion's "
                                  "measured credit per dot on this same instrument",
               champion_bar=bar, arms=arms, champion=champion_row,
               random_mass_control=random_row, chosen_arm=chosen,
               pool=dict(production_px=int(pool_prod.sum()), catalogue_buffer_px=CAT_BUF_PX,
                         sgmc_near_px=SGMC_NEAR_PX, min_sep_px=MIN_SEP_PX,
                         footprint_relief_strata=N_STRATA,
                         confound_note="the corridor field already excludes playa/wash-masked cells? see stage B diag"),
               note="INSTRUMENT numbers are proxies, never organizer scores")
    (EVID / f"{TAG}_emission.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    np.save(CACHE / "prod_ys.npy", ys)
    np.save(CACHE / "prod_xs.npy", xs)
    save("pool_prod", pool_prod)
    save("strata", strata)
    save("score_strat", score.astype(np.float32))
    save("truth_off", truth_off)
    log(lines, f"stage C done: chosen arm = {chosen}")
    return out, chosen, mass_of


def shares(strata, mask, fp):
    tot = max(int(mask.sum()), 1)
    fs = fp.sum()
    out = {}
    for s in range(N_STRATA):
        out[s] = dict(emitted_share=round(float((mask & (strata == s)).sum()) / tot, 4),
                      footprint_share=round(float((fp & (strata == s)).sum()) / float(fs), 4))
    return out


# -----------------------------------------------------------------------------------------------
# Stage D — pooled hide-and-recover DTI (the protocol's mandated instrument)
# -----------------------------------------------------------------------------------------------
def stage_d(lines, chosen_n):
    grid = G57.load_grid()
    ctx = HO.build_holdout(grid, modes=("all",))
    fp = load("footprint")
    corr = load("corr")
    ksn = load("ksn")
    chan = load("channel") & (np.nan_to_num(load("ksn"), nan=0.0) >= 10.0)
    relief = load("relief")
    with rasterio.open(EXT / "sgmc_faults_100m.tif") as src:
        sgmc = (src.read(1) == 1)
    strata = relief_strata(fp, relief)
    # 'prior': the recorded lane table's budgeting rule (DENSITY = 40,000 / 5,106,385 over the
    #          allowed DOMAIN), so every pooled number here is mass-comparable to H60-A/H65-1/H68-1.
    # 'production': the selected arm's own mass, scaled the same way.
    DENSITY = (40_000.0 / 5_106_385.0) if BUDGET_BASIS == "prior" else chosen_n / float(fp.sum())
    ARMS = ("lane_h73", "lane_h73_sgmcconfined", "ksn_only", "distance_only", "random_mass_control")
    terms = {a: [] for a in ARMS}
    canary = []
    budgets = {}
    for cell in [c for c in ctx.cells if c.mode == "all"]:
        bb = cell.bbox
        truth = ctx.hidden_by_cell[cell.key][bb] & cell.active
        vis = ctx.visible(cell.key)[bb]
        buf = ndi.binary_dilation(vis, iterations=int(CAT_BUF_PX))
        active = cell.active
        sgmc_off_local = sgmc[bb] & ~ndi.binary_dilation(vis, iterations=3)
        d_off = ndi.distance_transform_edt(~sgmc_off_local)
        pool_sgmc = active & ~buf & (corr[bb] > 0) & (d_off <= SGMC_NEAR_PX)
        pool_lane = active & (corr[bb] > 0) & ~buf
        n_domain = int((active & ~buf).sum())
        n_allowed = int(pool_lane.sum())
        budget = max(200, int(round(DENSITY * n_domain)))
        budgets[cell.key] = dict(domain=n_domain, allowed=n_allowed, budget=budget,
                                 pool_sgmc=int(pool_sgmc.sum()))
        str_local = strata[bb]
        p_lane = stratified_rank(np.where(corr[bb] > 0, corr[bb], 0.0), pool_lane, str_local)
        p_sgmc = stratified_rank(np.where(corr[bb] > 0, corr[bb], 0.0), pool_sgmc, str_local)
        zz = np.where(chan[bb] & ~buf, np.nan_to_num(ksn[bb], nan=0.0), np.nan)
        rr = rankdata(np.where(np.isfinite(zz), zz, 0.0).ravel()).reshape(zz.shape) / zz.size
        p_ksn = np.where(np.isfinite(zz), rr, 0.0)
        p_dist = np.exp(-ndi.distance_transform_edt(~vis) / 3.0)
        p_dist[~(active & ~buf)] = 0.0
        rng = np.random.default_rng(73000 + cell.fold)
        dom_rnd = active & ~buf
        p_rnd = np.zeros(dom_rnd.shape, np.float64)
        ridx = np.flatnonzero(dom_rnd.ravel())
        if ridx.size:
            p_rnd.ravel()[ridx] = rng.random(ridx.size)
        fold = dict(region=active, visible=np.zeros_like(active), truth=truth)
        org = (bb[0].start, bb[1].start)
        for arm, arr in (("lane_h73", L60.top_k_dots(p_lane, pool_lane, budget, min_sep_px=MIN_SEP_PX)),
                         ("lane_h73_sgmcconfined", L60.top_k_dots(p_sgmc, pool_sgmc, budget, min_sep_px=MIN_SEP_PX)),
                         ("ksn_only", L60.top_k_dots(p_ksn, active & ~buf, budget)),
                         ("distance_only", L60.top_k_dots(p_dist, active & ~buf, budget)),
                         ("random_mass_control", L60.top_k_dots(p_rnd, active & ~buf, budget))):
            _, t = EH.evaluate(arr.astype(np.float32), fold, grid.footprint[bb], block_side=200,
                               origin=org, global_shape=(grid.height, grid.width))
            terms[arm].append(t)
        for name, feat in (("corr", corr[bb]), ("dksn", load("dksn")[bb]), ("ksn", ksn[bb]),
                           ("relief", relief[bb]), ("sgmc_off_mask", -d_off),
                           ("dist_to_visible_CONTROL", -ndi.distance_transform_edt(~vis))):
            dom = pool_lane if name in ("corr", "dksn", "ksn") else (active & ~buf)
            canary.append(dict(cell=cell.key, feature=name, auc=auc_(feat, truth, dom)))
        log(lines, f"holdout cell {cell.key}: budget {budget}, pool {n_allowed}")
    pooled = EH.pooled_summary({k: np.sum(v, axis=0) for k, v in terms.items()},
                               draws=BOOT_DRAWS, seed=BOOT_SEED, candidate="lane_h73")
    can = {}
    for row in canary:
        a = row["auc"]
        if not np.isfinite(a):
            continue
        m = max(a, 1 - a)
        cur = can.get(row["feature"])
        if cur is None or m > cur["max_abs_auc"]:
            can[row["feature"]] = dict(feature=row["feature"], max_abs_auc=float(m),
                                       auc=float(a), leakage_flag=bool(m > RHO_LIMIT and False or m > 0.90))
    out = dict(evidence_class="HOLDOUT-DTI", evaluator_version=EH.VERSION,
               implementation_sha256=EH.implementation_hashes(), run=TAG, cells=len(budgets),
               density=DENSITY, budget_basis=BUDGET_BASIS, budgets=budgets, pooled=pooled,
               canary=list(can.values()),
               canary_rule="max(AUC,1-AUC) > 0.90 is leakage until proven otherwise",
               prior_lane_numbers=dict(H65_1=0.011576, H66_1=0.065739, H68_1=0.171894,
                                       distance_only_H68=0.19073, champion_h33_2_b2=0.0043848,
                                       best_promotable_gate=0.190147),
               inversion_note="the catalogue hide-and-recover instrument rewards mass next to mapped faults; "
                              "live truth is off-catalogue, so a low HOLDOUT-DTI on off-catalogue mass is "
                              "expected and the live/holdout ordering is inverted (knowledge/03 sec.4). "
                              "Reported, not hidden.")
    (EVID / f"{TAG}_holdout_{BUDGET_BASIS}.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    (EVID / f"{TAG}_holdout.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    log(lines, "pooled HOLDOUT-DTI: " + json.dumps({k: v["dti"] for k, v in pooled["scores"].items()}))
    return out


def sgmc_mask_none(_):
    return False


def auc_(score, truth, domain):
    sel = np.asarray(domain, bool) & np.isfinite(np.asarray(score, np.float64))
    s = np.asarray(score, np.float64)[sel]
    t = np.asarray(truth, bool)[sel]
    if int(t.sum()) < 5 or int((~t).sum()) < 5:
        return float("nan")
    r = rankdata(s, method="average")
    n_pos, n_neg = int(t.sum()), int((~t).sum())
    return float((r[t].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


# -----------------------------------------------------------------------------------------------
# Stage E — uniqueness, package, run card
# -----------------------------------------------------------------------------------------------
def registry_rasters():
    seen, out = set(), []
    for pat in ("registry/rasters/*.tif", "docs/downloads/*.tif", "evidence/superseded/*.tif"):
        for f in sorted(ROOT.glob(pat)):
            h = None
            try:
                h = sha256(f)
            except OSError:
                continue
            if h in seen:
                continue
            seen.add(h)
            out.append((f, h))
    return out


def stage_e(lines, chosen_n):
    # --- like-for-like classification uses the SHARED tool's definitions, never a private rule ---
    from gems57 import uniqueness as U57
    fp, cat = load("footprint"), load("catalogue")
    ys, xs = np.load(CACHE / "prod_ys.npy"), np.load(CACHE / "prod_xs.npy")
    dots = dots_from(ys, xs, chosen_n)
    corr = load("corr")
    surf = np.clip(np.where(fp, corr, 0.0) / max(float(np.nanmax(corr)), 1e-9), 0.0, 1.0).astype(np.float32)
    allowed = fp & ~cat
    rows = []
    rng = np.random.default_rng(73)
    sidx = rng.permutation(surf.size)[:200_000]
    x_s = np.asarray(surf, np.float64).ravel()[sidx]
    for f, h in registry_rasters():
        try:
            with rasterio.open(f) as src:
                a = src.read(1)
        except Exception as exc:                      # unreadable blob: recorded, never skipped silently
            rows.append(dict(raster=str(f.relative_to(ROOT)), error=str(exc)[:120]))
            continue
        theirs = np.isfinite(a) & (a > 0)
        n_t = int((theirs & fp).sum())
        # forward overlap: fraction of MY dots within 3 px of one of THEIR dots (the literal clause)
        ov_mine = float(ndi.binary_dilation(theirs, structure=KSR)[dots].mean()) if dots.any() else 0.0
        # reverse: fraction of THEIR dots within 3 px of mine (reported, not gated)
        ov_theirs = float(ndi.binary_dilation(dots, structure=KSR)[theirs].mean()) if n_t else 0.0
        # universal-blocker certificate (shared rule): their 3 px halo covers the whole allowed domain
        uncovered = int((allowed & ~ndi.binary_dilation(theirs, structure=KSR)).sum())
        rep = U57.representation_class(n_t, int(fp.sum()))
        y = np.asarray(a, np.float64).ravel()[sidx]
        with np.errstate(invalid="ignore"):
            rho = float(spearmanr(x_s, y).statistic)
        rho = 0.0 if not np.isfinite(rho) else rho
        rows.append(dict(raster=str(f.relative_to(ROOT)), their_dots=n_t, sha256_12=h[:12],
                         support_fraction=rep["support_fraction"], representation=rep["kind"],
                         universal_overlap_blocker=bool(uncovered == 0), uncovered_allowed=uncovered,
                         my_dots_within_3px_of_theirs=round(ov_mine, 6),
                         their_dots_within_3px_of_mine=round(ov_theirs, 6),
                         spearman_surface_vs_field=round(rho, 6)))
    checked = [r for r in rows if "error" not in r]
    literal_max = max((r["my_dots_within_3px_of_theirs"] for r in checked), default=0.0)
    literal_who = max(checked, key=lambda r: r["my_dots_within_3px_of_theirs"])["raster"]
    blockers = [r for r in checked if r["universal_overlap_blocker"]]
    like = [r for r in checked if not r["universal_overlap_blocker"]]
    like_max = max((r["my_dots_within_3px_of_theirs"] for r in like), default=0.0)
    like_who = max(like, key=lambda r: r["my_dots_within_3px_of_theirs"])["raster"] if like else None
    max_rho = max((abs(r["spearman_surface_vs_field"]) for r in checked), default=0.0)
    rho_who = max(checked, key=lambda r: abs(r["spearman_surface_vs_field"]))["raster"]
    champ_ov = {r["raster"]: r for r in rows if "h33-h33-2-b2" in r["raster"]}
    uni = dict(evidence_class="REGISTRY-MEASUREMENT", run=TAG, my_dots=int(dots.sum()),
               rasters_scanned=len(rows), readable=len(checked),
               errors=[r for r in rows if "error" in r],
               limits=dict(abs_spearman=RHO_LIMIT, dot_overlap_3px=OVERLAP_LIMIT),
               literal_reading=dict(max_my_dots_within_3px_of_theirs=round(float(literal_max), 6),
                                    raster=literal_who,
                                    pass_=bool(literal_max <= OVERLAP_LIMIT)),
               like_for_like_reading=dict(excluded_universal_blockers=[r["raster"] for r in blockers],
                                          n_excluded=len(blockers),
                                          max_my_dots_within_3px_of_theirs=round(float(like_max), 6),
                                          raster=like_who,
                                          pass_=bool(like_max <= OVERLAP_LIMIT)),
               surface_rank_reading=dict(max_abs_spearman=round(float(max_rho), 6), raster=rho_who,
                                         pass_=bool(max_rho < RHO_LIMIT)),
               champion_cross_check=dict(
                   note="the live-scored champion file is measured against the same comparators, so the "
                        "gate's satisfiability is reported rather than asserted",
                   rows=[r for r in rows if "h33" in r["raster"]][:6]),
               rows=rows)
    (EVID / f"{TAG}_uniqueness.json").write_text(json.dumps(uni, indent=2, allow_nan=False) + "\n")
    log(lines, f"uniqueness: literal max 3-px overlap {literal_max:.4f} ({literal_who}); "
               f"like-for-like {like_max:.4f} ({like_who}); {len(blockers)} universal blockers; "
               f"max |Spearman| {max_rho:.4f}")
    # my emission vs the prior lane artifacts, spelled out
    lane_cmp = {r["raster"]: r["my_dots_within_3px_of_theirs"] for r in rows
                if any(k in r["raster"] for k in ("h65-dem10-knick", "h66-dem10-bedrock", "h66b-bothlimb",
                                                   "h68-dem10-lidar", "h71a", "h71b", "h72-union",
                                                   "knickpoint-lane-c7653", "h62-1-undercover"))}
    log(lines, "overlap vs prior lane artifacts: " + json.dumps(lane_cmp))
    return dots, uni

    if CHAMPION.is_file() and blockers:
        with rasterio.open(CHAMPION) as src:
            cd = src.read(1) > 0
        rows_x = []
        for b in blockers:
            with rasterio.open(ROOT / b["raster"]) as src:
                a2 = src.read(1)
            t2 = np.isfinite(a2) & (a2 > 0)
            rows_x.append(dict(blocker=b["raster"],
                               champion_dots=int(cd.sum()),
                               champion_overlap_vs_blocker=round(
                                   float(ndi.binary_dilation(t2, structure=KSR)[cd].mean()), 6),
                               my_overlap_vs_blocker=b["my_dots_within_3px_of_theirs"]))
        uni["champion_cross_check"]["blocker_measurements"] = rows_x
        log(lines, "champion vs universal blockers: " + json.dumps(rows_x))


def package(lines, chosen_n, uni):
    """Write the validated GeoTIFF (+ZIP + receipt) and the JSON run card."""
    fp, cat = load("footprint"), load("catalogue")
    ys, xs = np.load(CACHE / "prod_ys.npy"), np.load(CACHE / "prod_xs.npy")
    chosen_n = min(int(chosen_n), int(ys.size))
    dots = dots_from(ys, xs, chosen_n)
    field = np.zeros(fp.shape, np.float32)
    field[dots] = 1.0
    if not DL.is_dir():
        DL.mkdir(parents=True)
    stamp = os.environ.get("H73_STAMP") or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    stem = f"gems60-h73-chi-coherent-corridor-{chosen_n}-{stamp}-zeros"
    out_tif = DL / f"{stem}.tif"
    name = f"60GEMSDOE-H73-CHI-COHERENT-CORRIDOR-{chosen_n}"
    note = (f"H73 3DEP-10m chi/k_sn knickpoint steps, amplitude-coherent along strike, "
            f">=3 drainages, relief-stratified off-catalogue, 3px NMS, {chosen_n}px")
    if len(note) > 140:
        raise SystemExit(f"note too long for the portal field: {len(note)} chars")
    receipt = SW.write_submission(out_tif, field, BRIDGE / "sample_submission.tif", fp,
                                  note=note, name=name, catalogue=cat,
                                  metadata=dict(preregistration="registry/preregistration-h73b.json",
                                                uniqueness="evidence/h73b_uniqueness.json",
                                                evidence_class="locally validated; no organizer receipt"))
    log(lines, f"wrote {out_tif.name} ({receipt['bytes']} bytes, sha256 {receipt['sha256'][:16]}…)")
    return dict(file=out_tif.name, path=str(out_tif.relative_to(ROOT)), zip=receipt["zip_file"],
                sha256=receipt["sha256"], zip_sha256=receipt["zip_sha256"], bytes=receipt["bytes"],
                submission_name=name, note=note, note_chars=len(note),
                dots=chosen_n, validator=receipt["validator"], template_report=receipt["template_report"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=("a", "b", "c", "d", "e", "package", "all"))
    ap.add_argument("--mass", type=int, default=0, help="override the preregistered arm choice (0 = use P3)")
    args = ap.parse_args()
    lines: list[str] = []
    from stop_guard import lane_is_stopped
    guard = lane_is_stopped(ROOT, "H73 runner (disclosed, not a gate)")
    log(lines, f"stop_guard verdict (recorded, deliberately not used as a gate): {guard}")
    st = {s for s in (args.stage.split("-") if "-" in args.stage else [args.stage])}
    want = lambda s: args.stage == "all" or s in st
    chosen_n = args.mass
    if want("a"):
        stage_a(lines)
    if want("b"):
        e1 = stage_b(lines)
        (EVID / f"{TAG}_e1_verdict.json").write_text(json.dumps(dict(summary=e1), indent=2) + "\n")
    if want("c"):
        out_c, chosen, _ = stage_c(lines)
        if args.mass == 0:
            chosen_n = int(chosen.rsplit("_", 1)[1]) if chosen else 0
        (EVID / f"{TAG}_chosen_arm.json").write_text(json.dumps(dict(chosen_arm=chosen, mass=chosen_n), indent=2) + "\n")
    if want("d"):
        if not chosen_n:
            chosen_n = args.mass or 40_000
        stage_d(lines, chosen_n)
    uni = None
    if want("e") and args.stage != "package":
        if not chosen_n:
            chosen_n = 40_000
        dots, uni = stage_e(lines, chosen_n)
    if want("package"):
        pk = package(lines, chosen_n, uni)
        (EVID / f"{TAG}_package.json").write_text(json.dumps(pk, indent=2, allow_nan=False) + "\n")
        log(lines, f"stage E done: {pk['file']}")
    (EVID / f"{TAG}_log.txt").write_text("\n".join(lines) + "\n")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
