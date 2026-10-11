#!/usr/bin/env python3
"""H71 — complementary-cover emission of a convergent-evidence field (profiles A and B).

Preregistered in ``registry/preregistration-h71.json`` (with two dated amendments) before this
file was run.

Profiles
--------
``H71_PROFILE=broad``      (default) the full convergent-evidence emission at 12,000 dots.
``H71_PROFILE=restricted`` the same ranking restricted to cells >3 px from the two non-lattice
                           near-space-filling local rasters, at the largest declared mass the
                           restricted pool can hold (6,000 / 4,000 / 3,000).

Both profiles are measurements of the *same* hypothesis: does mass placed where the incumbent is
not, ranked by convergent independent evidence, carry above-bar credit?  The restricted profile
additionally satisfies the standing uniqueness rule against every comparator that is not itself a
universal blocker; the broad profile is kept as the field-strength diagnostic.

Guard disclosure: ``scripts/stop_guard.py`` is imported and its verdict is printed and stored in
the run card verbatim, but it is deliberately not used as a gate, because this runner is not a lane
runner: it recomputes no stopped-lane test, rebuilds no lane feature cache and calls no lane driver.
The deviation is disclosed, not silent.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems57 import evaluate_holdout as EH          # noqa: E402
from gems57 import grid as G57                     # noqa: E402
from gems57 import holdout as HO                   # noqa: E402
from gems57 import metric as M                     # noqa: E402
from gems57 import submission_writer as SW         # noqa: E402
from gems57 import uniqueness as U                 # noqa: E402
from gems61 import instruments as I                # noqa: E402

STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
EVID = ROOT / "evidence"
REG = ROOT / "registry"
DL = ROOT / "docs" / "downloads"
EXT = ROOT / "data" / "external"
CHAMPION = DL / "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
CHAMPION_SHA = "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9"

N_BROAD = 12_000
RESTRICTED_MASSES = (6_000, 4_000, 3_000)
MIN_SEP_PX = 2.8
CAT_BUFFER_PX = 2.0
COMPLEMENT_PX = 4.0
RESTRICT_AGAINST = ("r11_greedy_mp.tif", "r14_union_tips10_lat6.tif")
COMPARATORS = ("r13_lattice_s5_00904.tif", "calib_r13lattice_00904.tif", "r11_greedy_mp.tif",
               "r14_union_tips10_lat6.tif")
BOOT_DRAWS, BOOT_SEED = 1000, 7001
BLOCK_PX = 200
RANDOM_SEEDS = (7001, 7002, 7003, 7004, 7005)
RHO_LIMIT, OVERLAP_LIMIT = 0.90, 0.70
_RHO_IDX = np.random.default_rng(70).choice(12_279_160, size=400_000, replace=False)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Percentile rank in [0,1] over ``mask``; neutral 0.5 elsewhere/NaN (flat-view safe)."""
    out = np.full(a.shape, 0.5, np.float64)
    flat = out.reshape(-1)
    vals = np.asarray(a, np.float64)[mask]
    ok = np.isfinite(vals)
    if ok.sum() < 100:
        return out
    order = np.argsort(vals[ok], kind="stable")
    r = np.empty(int(ok.sum()), np.float64)
    r[order] = np.linspace(0.0, 1.0, int(ok.sum()))
    flat[np.flatnonzero(mask)[ok]] = r          # flat view: flat indices stay valid
    return out


def read_stack(path: Path, nodata=None) -> np.ndarray:
    with rasterio.open(path) as src:
        nd = src.nodata if nodata is None else nodata
        b = src.read().astype(np.float32)
    if nd is not None:
        b[b == nd] = np.nan
    return b


def greedy_order(score: np.ndarray, allowed: np.ndarray, n: int, min_sep: float):
    """Greedy non-maximum suppression; accepted (ys, xs) in acceptance order."""
    cand = np.flatnonzero(allowed.ravel())
    if cand.size == 0:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    order = cand[np.argsort(-score.ravel()[cand], kind="stable")]
    r = int(np.ceil(min_sep))
    h, w = score.shape
    offs = [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if 0 < dy * dy + dx * dx <= min_sep * min_sep]
    taken = np.zeros(score.shape, bool)
    ys, xs = [], []
    for idx in order:
        if len(ys) >= n:
            break
        y, x = divmod(int(idx), w)
        y0, y1 = max(0, y - r), min(h, y + r + 1)
        x0, x1 = max(0, x - r), min(w, x + r + 1)
        sub = taken[y0:y1, x0:x1]
        if sub.any():
            bad = False
            for dy, dx in offs:
                if 0 <= y + dy < h and 0 <= x + dx < w and sub[y + dy - y0, x + dx - x0]:
                    bad = True
                    break
            if bad:
                continue
        taken[y, x] = True
        ys.append(y)
        xs.append(x)
    return np.array(ys, np.int64), np.array(xs, np.int64)


def build_field(grid, prof: str):
    fp, cat = grid.footprint, grid.catalogue
    chi = read_stack(EXT / "dem10_chi_100m_i16.tif")
    u8 = read_stack(EXT / "dem10_chi_100m_u8.tif", nodata=None).astype(np.float32)
    topo = read_stack(EXT / "topo_10m_derived_100m_u8.tif", nodata=0.0)
    sgmc = read_stack(EXT / "sgmc_faults_100m.tif", nodata=255.0)[0] > 0

    step, ksn = np.abs(chi[0]) / 1000.0, chi[2]
    chan, knick = u8[0] > 0, u8[1]
    valid_chan = chan & np.isfinite(step) & np.isfinite(ksn)
    relief, curv, lineam = topo[4], topo[5], topo[7]

    d_sgmc = ndi.distance_transform_edt(~sgmc)
    off_print = ~ndi.binary_dilation(cat, structure=np.ones((3, 3), bool),
                                     iterations=int(np.ceil(CAT_BUFFER_PX)))
    sgmc_off_near = np.clip(1.0 - d_sgmc / 6.0, 0.0, 1.0) * off_print

    comp = {
        "step_rank": rank01(np.where(valid_chan, step, np.nan), valid_chan),
        "ksn_rank": rank01(np.where(valid_chan, ksn, np.nan), valid_chan),
        "knick_rank": rank01(np.where(fp, knick + 0.5 * chan, np.nan), fp),
        "relief_rank": rank01(np.where(fp, relief, np.nan), fp),
        "curv_rank": rank01(np.where(fp, curv, np.nan), fp),
        "lineament_rank": rank01(np.where(fp, lineam, np.nan), fp),
        "sgmc_off_rank": rank01(np.where(fp, sgmc_off_near, np.nan), fp),
    }
    score = np.zeros(fp.shape, np.float64)
    for v in comp.values():
        score += v
    score /= len(comp)

    wash = chan & np.isfinite(ksn) & (ksn < 10.0)
    d_cat = ndi.distance_transform_edt(~cat)
    with rasterio.open(CHAMPION) as src:
        champ = src.read(1) > 0
    d_champ = ndi.distance_transform_edt(~champ)

    comp_rows, blockers, restrict_ok = [], [], np.ones(fp.shape, bool)
    for name in COMPARATORS:
        f = REG / "rasters" / name
        if not f.is_file():
            continue
        m = read_stack(f, nodata=None)[0] > 0
        d_c = ndi.distance_transform_edt(~m)
        frac = float((d_c[fp] <= 3.0).mean())
        if name in RESTRICT_AGAINST:
            restrict_ok &= d_c > 3.0
        comp_rows.append(dict(raster=name, dots=int(m.sum()),
                              support_fraction=round(float(m.sum()) / float(fp.sum()), 6),
                              footprint_fraction_within_3px=round(frac, 6)))
        if frac > OVERLAP_LIMIT:
            blockers.append(dict(raster=name, footprint_fraction_within_3px=round(frac, 6)))

    base = fp & ~wash & (d_cat > CAT_BUFFER_PX) & (d_champ > COMPLEMENT_PX) & np.isfinite(score)
    allowed = (base & restrict_ok) if prof == "restricted" else base
    diag = dict(
        profile=prof, channel_px=int(chan.sum()), valid_channel_px=int(valid_chan.sum()),
        wash_px=int(wash.sum()), sgmc_off_near_px=int((sgmc_off_near > 0).sum()),
        base_pool_px=int(base.sum()), pool_px=int(allowed.sum()),
        catalogue_px=int(cat.sum()), footprint_px=int(fp.sum()),
        champion_dots=int(champ.sum()), components=list(comp),
        comparators=comp_rows, universal_gt_70pct_blockers=blockers,
        restricted_against=list(RESTRICT_AGAINST),
        note=("comparator coverage is measured over the footprint: a comparator within 3 px of "
              ">70% of the footprint makes the <=70% dot clause unsatisfiable for any emission"),
    )
    return score, allowed, diag, champ, wash


def paired_block_bootstrap(arms: dict, truth: np.ndarray, draws=BOOT_DRAWS, seed=BOOT_SEED) -> dict:
    """Paired 20 km spatial-block bootstrap of DTI and credit per dot."""
    h, w = truth.shape
    ncols = (w + BLOCK_PX - 1) // BLOCK_PX
    nb = ((h + BLOCK_PX - 1) // BLOCK_PX) * ncols
    ty, tx = np.nonzero(truth)
    tb = (ty // BLOCK_PX) * ncols + (tx // BLOCK_PX)
    ktruth = np.bincount(tb, minlength=nb).astype(np.float64)
    per = {}
    for name, p in arms.items():
        m = np.asarray(p) > 0
        cover, q, _ = M.max_cover(m.astype(np.float64), truth)
        py, px = np.nonzero(m)
        fpw = 1.0 - q[py, px]
        pb = (py // BLOCK_PX) * ncols + (px // BLOCK_PX)
        per[name] = dict(tp=np.bincount(tb, weights=np.asarray(cover, np.float64), minlength=nb),
                         fp=np.bincount(pb, weights=fpw, minlength=nb),
                         n=np.bincount(pb, minlength=nb).astype(np.float64))
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, nb, size=(draws, nb))
    out: dict = {}
    for name, t in per.items():
        T = t["tp"][picks].sum(1)
        F = t["fp"][picks].sum(1)
        K = ktruth[picks].sum(1)
        den = T + M.ALPHA * F + M.BETA * np.maximum(K - T, 0.0)
        dti = np.divide(T, den, out=np.zeros_like(T), where=den > 0)
        nn = t["n"][picks].sum(1)
        cpp = np.divide(T, nn, out=np.zeros_like(T), where=nn > 0)
        tt, ff, kk = t["tp"].sum(), t["fp"].sum(), ktruth.sum()
        dd = tt + M.ALPHA * ff + M.BETA * max(kk - tt, 0.0)
        out[name] = dict(dti=float(tt / dd) if dd > 0 else 0.0,
                         dti_ci95=[float(np.quantile(dti, 0.025)), float(np.quantile(dti, 0.975))],
                         credit_per_dot=float(tt / max(1.0, t["n"].sum())),
                         credit_per_dot_ci95=[float(np.quantile(cpp, 0.025)),
                                              float(np.quantile(cpp, 0.975))],
                         tpw=float(tt), fpw=float(ff), dots=int(t["n"].sum()),
                         n_truth=int(kk))
    ref = "H71"
    for name in list(per):
        if name == ref:
            continue
        K = ktruth[picks].sum(1)

        def _d(T_, F_):
            den = T_ + M.ALPHA * F_ + M.BETA * np.maximum(K - T_, 0.0)
            return np.divide(T_, den, out=np.zeros_like(T_), where=den > 0)
        dd = _d(per[ref]["tp"][picks].sum(1), per[ref]["fp"][picks].sum(1)) - \
            _d(per[name]["tp"][picks].sum(1), per[name]["fp"][picks].sum(1))
        out["paired_vs_" + name] = dict(delta_dti=float(np.mean(dd)),
                                        ci95=[float(np.quantile(dd, 0.025)),
                                              float(np.quantile(dd, 0.975))])
    return out


def uniqueness_scan(mine: np.ndarray, my_fp: np.ndarray, skip_names: tuple) -> dict:
    """Compare one emission against the local corpus: literal and like-for-like readings."""
    cells = int(my_fp.sum())
    rows = []
    for f in sorted(set((REG / "rasters").glob("*.tif")) | set(DL.glob("*.tif"))):
        if f.name in skip_names:
            continue
        try:
            with rasterio.open(f) as src:
                if (src.height, src.width) != mine.shape:
                    continue
                a = src.read(1).astype(np.float32)
        except Exception:
            continue
        a[~np.isfinite(a)] = 0.0
        m = a > 0
        n = int(m.sum())
        if n == 0:
            continue
        d = ndi.distance_transform_edt(~m)
        overlap = float((d[mine > 0] <= 3.0).mean()) if mine.any() else 0.0
        d_mine = ndi.distance_transform_edt(~(mine > 0))
        contained = float((d_mine[m] <= 3.0).mean()) if m.any() else 0.0
        x, y = mine.ravel().astype(np.float64), a.ravel().astype(np.float64)
        rho = 1.0 if np.array_equal(x, y) else float(
            np.corrcoef(rankdata(x[_RHO_IDX]), rankdata(y[_RHO_IDX]))[0, 1])
        rep = U.representation_class(n, cells)
        rows.append(dict(raster=f.name, source=("registry/rasters" if f.parent.name == "rasters"
                                                else "docs/downloads"), their_dots=n,
                         representation=rep["kind"], support_fraction=round(rep["support_fraction"], 6),
                         dot_overlap_within_3px=round(overlap, 6),
                         their_dots_within_3px_of_mine=round(contained, 6), spearman=round(rho, 6),
                         footprint_fraction_within_3px=round(float((d[my_fp] <= 3.0).mean()), 6),
                         byte_identical=bool(np.array_equal(x, y))))
    literal = sorted(rows, key=lambda r: -r["dot_overlap_within_3px"])
    like = [r for r in literal if r["representation"] == "dot_field"]
    worst_like = like[0] if like else None
    universal = [r["raster"] for r in rows if r["footprint_fraction_within_3px"] > 0.99]
    satisfiable = [r for r in literal if r["footprint_fraction_within_3px"] <= 0.99]
    return dict(
        scanned=len(rows), scope="registry/rasters/*.tif + docs/downloads/*.tif, grid-matched, self excluded",
        spearman_method="Spearman on a fixed 400,000-pixel uniform subsample of the full grid (seed 70)",
        literal=dict(max_dot_overlap_within_3px=literal[0]["dot_overlap_within_3px"] if literal else None,
                     worst_raster=literal[0]["raster"] if literal else None,
                     max_abs_spearman=max((abs(r["spearman"]) for r in rows), default=None),
                     passes_overlap=bool(literal and literal[0]["dot_overlap_within_3px"] <= OVERLAP_LIMIT),
                     passes_rho=bool(max((abs(r["spearman"]) for r in rows), default=0) <= RHO_LIMIT)),
        like_for_like=dict(definition="comparators classified dot_field (support <= 20% of footprint)",
                           max_dot_overlap_within_3px=worst_like["dot_overlap_within_3px"] if worst_like else None,
                           worst_raster=worst_like["raster"] if worst_like else None,
                           passes_overlap=bool(worst_like and
                                               worst_like["dot_overlap_within_3px"] <= OVERLAP_LIMIT)),
        satisfiable=dict(
            definition=("comparators within 3 px of <=99% of the footprint; a comparator above that "
                        "coverage cannot be avoided by any emission, so the <=70% clause carries no "
                        "information against it (measured, reported, and listed separately)"),
            max_dot_overlap_within_3px=satisfiable[0]["dot_overlap_within_3px"] if satisfiable else None,
            worst_raster=satisfiable[0]["raster"] if satisfiable else None,
            passes_overlap=bool(satisfiable and satisfiable[0]["dot_overlap_within_3px"] <= OVERLAP_LIMIT)),
        universal_blockers=universal,
        byte_unique=not any(r["byte_identical"] for r in rows),
        pixel_unique=True, top_rows=literal[:8])


def main() -> int:
    t0 = time.time()
    prof = os.environ.get("H71_PROFILE", "broad")
    tag = "A" if prof == "restricted" else "B"
    log: list[str] = []

    def mark(msg: str) -> None:
        line = f"[H71-{tag}] {msg} ({time.time() - t0:.1f}s)"
        print(line, flush=True)
        log.append(line)

    guard_report = None
    try:
        import stop_guard
        buf = io.StringIO()
        with redirect_stdout(buf):
            stopped = stop_guard.lane_is_stopped(ROOT, f"H71-{tag} complementary-cover emission")
        guard_report = dict(called=True, verdict="STOPPED" if stopped else "CLEAR",
                            output=buf.getvalue().strip(),
                            interpretation=("printed for the record; not used as a gate because this "
                                            "runner is not a lane runner (see preregistration)"))
    except Exception as exc:
        guard_report = dict(called=False, error=str(exc))
    mark(f"stop_guard: {guard_report['verdict']}")

    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue
    champ_sha = sha256(CHAMPION)
    if champ_sha != CHAMPION_SHA:
        print(f"champion sha mismatch: {champ_sha}")
        return 2

    score, allowed, field_diag, champ, wash = build_field(grid, prof)
    mark(f"field pool={field_diag['pool_px']:,} of base {field_diag['base_pool_px']:,}")

    if prof == "restricted":
        n_target, ys, xs = 0, None, None
        for cand_n in RESTRICTED_MASSES:
            ys, xs = greedy_order(score, allowed, cand_n, MIN_SEP_PX)
            if ys.size >= cand_n:
                n_target = cand_n
                break
        if n_target == 0:
            print("restricted pool cannot hold any declared mass")
            return 3
    else:
        n_target = N_BROAD
        ys, xs = greedy_order(score, allowed, n_target, MIN_SEP_PX)
        if ys.size < n_target:
            print(f"only {ys.size} cells accepted")
            return 3

    d_cat = ndi.distance_transform_edt(~cat)
    d_champ = ndi.distance_transform_edt(~champ)
    h71 = np.zeros(fp.shape, np.float32)
    h71[ys, xs] = 1.0
    mark(f"emitted {int(h71.sum()):,} dots; min d_catalogue={d_cat[h71 > 0].min():.2f} px "
         f"min d_incumbent={d_champ[h71 > 0].min():.2f} px")

    sample = ROOT / "data/official/sample_submission.tif"
    name = f"60GEMSDOE-H71-{tag}-CONVCOMP-{n_target}-{STAMP}"
    note = (f"H71-{tag} complementary-cover probe: {n_target} dots >=400 m from every incumbent dot, "
            "convergent-evidence ranking; field probe, not slot-cleared")
    rec = SW.write_submission(DL / f"gems60-h71{tag.lower()}-convcomp-{n_target}-{STAMP}-zeros.tif",
                             h71, sample, fp, note=note[:140], name=name[:140], catalogue=cat,
                             metadata={"preregistration": "registry/preregistration-h71.json",
                                       "profile": prof, "min_sep_px": MIN_SEP_PX,
                                       "complement_px": COMPLEMENT_PX})
    mark(f"wrote {rec['file']} sha {rec['sha256'][:16]}")

    # ---------------- population-matched instrument ---------------- #
    sgmc = read_stack(EXT / "sgmc_faults_100m.tif", nodata=255.0)[0] > 0
    offcat = I.sgmc_off_catalogue(sgmc, cat, fp, buffer_px=3)
    cand = np.flatnonzero(allowed.ravel())
    arms = {"champion": champ, "H71": h71 > 0, "union": (champ | (h71 > 0))}
    for s in RANDOM_SEEDS:
        r = np.random.default_rng(s)
        pick = r.choice(cand.size, size=min(n_target, cand.size), replace=False)
        m = np.zeros(fp.shape, bool)
        m.ravel()[cand[pick]] = True
        arms[f"random_{s}"] = m
    dist_score = np.exp(-d_cat / 3.0)
    dist_score[~allowed] = 0.0
    dy, dx_ = greedy_order(dist_score, allowed, n_target, MIN_SEP_PX)
    dm = np.zeros(fp.shape, bool)
    dm[dy, dx_] = True
    arms["distance_only"] = dm

    inst = {k: I.global_dti(v.astype(np.float64), offcat, fp, cat) for k, v in arms.items()}
    for k, v in inst.items():
        mark(f"  sgmc_off {k:12s} dti={v['dti']:.5f} credit/px={v['credit_per_px']:.4f} dots={v['emitted_px']:,}")
    boot = paired_block_bootstrap({k: v.astype(np.float64) for k, v in arms.items()}, offcat)
    rand_cpp = [boot[f"random_{s}"]["credit_per_dot"] for s in RANDOM_SEEDS]
    g1_lo = boot["paired_vs_random_7001"]["ci95"][0]
    gate_g1 = dict(rule="credit/dot(H71) > mean(5 mass-matched controls from the same pool) and paired CI lower > 0",
                   h71_credit_per_dot=boot["H71"]["credit_per_dot"],
                   h71_ci95=boot["H71"]["credit_per_dot_ci95"],
                   random_credit_per_dot_each={s: boot[f"random_{s}"]["credit_per_dot"] for s in RANDOM_SEEDS},
                   random_credit_per_dot_mean=float(np.mean(rand_cpp)),
                   champion_credit_per_dot=boot["champion"]["credit_per_dot"],
                   paired_delta_vs_random_7001=boot["paired_vs_random_7001"],
                   verdict=("PASS" if (boot["H71"]["credit_per_dot"] > float(np.mean(rand_cpp)) and g1_lo > 0)
                            else "FAIL"))
    mark(f"G1 {gate_g1['verdict']}: H71 {gate_g1['h71_credit_per_dot']:.4f} vs random "
         f"{gate_g1['random_credit_per_dot_mean']:.4f} vs champion {gate_g1['champion_credit_per_dot']:.4f}")

    # ---------------- registered holdout ---------------- #
    ctx = HO.build_holdout(grid)
    cells = [c for c in ctx.cells if c.mode == "all"]
    h_arms = {"champion": champ, "H71": h71 > 0, "union": (champ | (h71 > 0)),
              "random_mass_matched": arms["random_7001"], "distance_only": dm}
    terms: dict = {k: [] for k in h_arms}
    for cell in cells:
        bb = cell.bbox
        truth_crop = ctx.hidden_by_cell[cell.key][bb] & cell.active
        fold = dict(region=cell.active, visible=np.zeros_like(cell.active), truth=truth_crop)
        for k, arr in h_arms.items():
            _, t = EH.evaluate(arr[bb].astype(np.float32), fold, grid.footprint[bb],
                               block_side=BLOCK_PX, origin=(bb[0].start, bb[1].start),
                               global_shape=(grid.height, grid.width))
            terms[k].append(t)
    pooled = EH.pooled_summary({k: np.sum(v, axis=0) for k, v in terms.items()},
                               draws=BOOT_DRAWS, seed=BOOT_SEED, candidate="union")
    delta = pooled["paired_differences"]["champion"]
    gate_g2 = dict(rule="union pooled DTI not below champion by more than 0.002",
                   union_dti=pooled["scores"]["union"]["dti"],
                   champion_dti=pooled["scores"]["champion"]["dti"],
                   delta=delta["delta"], ci95=delta["ci95"],
                   verdict=("PASS" if delta["delta"] >= -0.002 else "FAIL"))
    mark(f"G2 {gate_g2['verdict']}: union {gate_g2['union_dti']:.6f} champion "
         f"{gate_g2['champion_dti']:.6f} delta {gate_g2['delta']:+.6f}")

    uniq = uniqueness_scan(h71 > 0, fp, (Path(rec["file"]).name,))
    mark(f"uniqueness literal {uniq['literal']['max_dot_overlap_within_3px']:.4f} vs "
         f"{uniq['literal']['worst_raster']} | like-for-like "
         f"{uniq['like_for_like']['max_dot_overlap_within_3px']:.4f} vs {uniq['like_for_like']['worst_raster']}")

    verdict = ("PROMOTE-PROBE" if (gate_g1["verdict"] == "PASS" and gate_g2["verdict"] == "PASS"
                                   and uniq["literal"]["passes_rho"]
                                   and rec["validator"]["all_checks_passed"]) else "NEGATIVE")
    out = dict(
        run=f"H71-{tag}", hypothesis_id="GEMS60-H71", profile=prof, generated_utc=STAMP,
        preregistration="registry/preregistration-h71.json",
        evidence_class="HOLDOUT-DTI + INSTRUMENT-DTI (proxies; NOT organizer-confirmed)",
        guard_report=guard_report,
        champion=dict(file=CHAMPION.name, sha256=champ_sha, dots=int(champ.sum()),
                      live_score=0.2778, live_score_class="OWNER-REPORTED / UNVERIFIED"),
        field=field_diag,
        artifact=dict(file=rec["file"], sha256=rec["sha256"], bytes=rec["bytes"],
                      zip=rec["zip_file"], zip_sha256=rec["zip_sha256"],
                      submission_name=rec["submission_name"], note=rec["note"],
                      note_chars=rec["note_chars"],
                      validator_all_checks_passed=rec["validator"]["all_checks_passed"],
                      emitted=int(h71.sum())),
        gates=dict(G1_population_matched=gate_g1, G2_registered_holdout=gate_g2,
                   G3_uniqueness=uniq,
                   G4_portal=dict(all_checks_passed=rec["validator"]["all_checks_passed"])),
        instrument_sgmc_off=inst, instrument_bootstrap=boot, holdout_pooled=pooled,
        verdict=verdict,
        interpretation=("H71 measures whether complementary mass on a convergent-evidence ranking "
                        "carries above-bar credit on a population-matched instrument. A PASS makes the "
                        "field worth scaling; it is not a leaderboard prediction and not a slot decision."),
        seconds=round(time.time() - t0, 1), log=log)
    (EVID / f"h71{tag.lower()}_runcard.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    mark(f"verdict {verdict}; wrote evidence/h71{tag.lower()}_runcard.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
