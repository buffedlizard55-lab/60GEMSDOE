#!/usr/bin/env python3
"""H71 — union artifact: the live-scored champion plus the H71-A convergent-cover complement.

Preregistered in ``registry/preregistration-h71.json`` before this file was run.

Why this is the top candidate
-----------------------------
The champion's own mass ladder shows every *removal* of catalogue-flank mass paid
(+0.0108 for the d=1 px shell, +0.0070 for the d=2 px shell, owner-reported).  Removal is a spent
direction at the kernel edge.  The unexplored direction is *addition* of mass whose credit is
measured rather than assumed: the H71-A complement measured credit/dot 0.4018 on the
population-matched SGMC-off-catalogue instrument, against the algebra's break-even
``c > 0.2*s = 0.0556``.  This runner builds that union as one artifact and tests it with the same
gate set as H71.

Guard disclosure: ``scripts/stop_guard.py`` is imported, its verdict is printed and stored in the
run card verbatim, and it is deliberately not used as a gate (this runner is not a lane runner).
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

import build_h71_field as B71                      # noqa: E402  (import + reuse, no fork)
from gems57 import grid as G57                     # noqa: E402
from gems57 import holdout as HO                   # noqa: E402
from gems57 import metric as M                     # noqa: E402
from gems57 import submission_writer as SW         # noqa: E402
from gems61 import instruments as I                # noqa: E402
from gems57 import evaluate_holdout as EH          # noqa: E402
from gems57 import uniqueness as U                 # noqa: E402

STAMP = os.environ.get("H71_STAMP") or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
ROOT_EV = ROOT / "evidence"
DL = ROOT / "docs" / "downloads"
REG = ROOT / "registry"
EXT = ROOT / "data" / "external"

CHAMPION = DL / "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
CHAMPION_SHA = "c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9"
ADDEND = DL / "gems60-h71a-convcomp-6000-20261011T185116Z-zeros.tif"
ADDEND_SHA = "5c22c464a40e15bae84463f921a6c704d29b45c67dd334c08202320d7b7e68e0"

# Champion-family rasters: overlap with these is lineage by construction (see prereg IR-H71-LINE-01).
LINEAGE_PATTERNS = (
    "gemsdoe32-h33-h33-2-b2", "GEMSDOE32__h33-2-b2", "dotted_b2_prune_02778",
    "GEMSDOE28__h27-4-r1-solo", "dotted_d2_8_02600", "dotted_d2_8_02708",
    "GEMSDOE25__dotted-h19-5-d2-8", "gems25-dotted-h19-5-d2-8",
    "19GEMSDOE__h19-5-powerlaw-budget-multiline", "GEMSDOE24__h25-1-dotted-h19-5-d1-5",
    "gems32-probe-S1-ANCHOR", "gems60-h71a-convcomp-6000", "gems60-h69a-champ-half",
    "gems60-h69b-champ-nulladd",
)
RANDOM_SEEDS = (7101, 7102, 7103, 7104, 7105)
BREAK_EVEN_NOTE = "c > 0.2*s = 0.0556 at the champion's owner-reported 0.2778"
G_VALUES = (13000.0, 20300.0)
_RHO_IDX = np.random.default_rng(70).choice(12_279_160, size=400_000, replace=False)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_mask(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
    a[~np.isfinite(a)] = 0.0
    return a > 0


def terms(arm: np.ndarray, truth: np.ndarray) -> dict:
    """Per-20 km-block TP/FP/dot-count terms, exactly as B71.paired_block_bootstrap does them."""
    m = np.asarray(arm) > 0
    cover, q, _ = M.max_cover(m.astype(np.float64), truth)
    py, px = np.nonzero(m)
    fpw = 1.0 - q[py, px]
    h, w = truth.shape
    ncols = (w + B71.BLOCK_PX - 1) // B71.BLOCK_PX
    nb = ((h + B71.BLOCK_PX - 1) // B71.BLOCK_PX) * ncols
    ty, tx = np.nonzero(truth)
    tb = (ty // B71.BLOCK_PX) * ncols + (tx // B71.BLOCK_PX)
    pb = (py // B71.BLOCK_PX) * ncols + (px // B71.BLOCK_PX)
    return dict(tp=np.bincount(tb, weights=np.asarray(cover, np.float64), minlength=nb),
                fp=np.bincount(pb, weights=fpw, minlength=nb),
                n=np.bincount(pb, minlength=nb).astype(np.float64),
                ktruth=np.bincount(tb, minlength=nb).astype(np.float64),
                nb=nb, tpw=float(np.asarray(cover).sum()), fpw=float(fpw.sum()),
                dots=int(m.sum()))


def dti_from(T, F, K):
    den = T + M.ALPHA * F + M.BETA * np.maximum(K - T, 0.0)
    return np.divide(T, den, out=np.zeros_like(T, dtype=np.float64), where=den > 0)


def paired(a: dict, b: dict, draws: int, seed: int) -> dict:
    """Paired 20 km spatial-block bootstrap of DTI(a) - DTI(b) on the same blocks."""
    nb = a["nb"]
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, nb, size=(draws, nb))
    da = dti_from(a["tp"][picks].sum(1), a["fp"][picks].sum(1), a["ktruth"][picks].sum(1))
    db = dti_from(b["tp"][picks].sum(1), b["fp"][picks].sum(1), b["ktruth"][picks].sum(1))
    dd = da - db
    ca = np.divide(a["tp"][picks].sum(1), a["n"][picks].sum(1),
                   out=np.zeros(draws), where=a["n"][picks].sum(1) > 0)
    cb = np.divide(b["tp"][picks].sum(1), b["n"][picks].sum(1),
                   out=np.zeros(draws), where=b["n"][picks].sum(1) > 0)
    return dict(delta_dti=float(np.mean(dd)),
                delta_dti_ci95=[float(np.quantile(dd, 0.025)), float(np.quantile(dd, 0.975))],
                delta_credit_per_dot=float(np.mean(ca - cb)),
                delta_credit_per_dot_ci95=[float(np.quantile(ca - cb, 0.025)),
                                           float(np.quantile(ca - cb, 0.975))],
                draws=draws, seed=seed, n_blocks=int(nb))


def algebra_projection(c_per_dot: float, add: int, s1: float = 0.2778, n1: int = 37654) -> dict:
    """[MODEL] algebra on the official formula s = T/(0.2*S + 0.8*G) for a thin-dot emission."""
    out = {}
    for g in G_VALUES:
        # T1 = s1 * (0.2*S1 + 0.8*G) with S1 = champion mass; T1 is what the champion actually covers
        t1_g = s1 * (0.2 * n1 + 0.8 * g)
        t2_g = min(t1_g + c_per_dot * add, g)
        out[f"G_{int(g)}"] = dict(
            champion_T_implied=t1_g, champion_recall=t1_g / g,
            union_T=t2_g, union_score=t2_g / (0.2 * (37654 + add) + 0.8 * g),
            zero_credit_union_score=t1_g / (0.2 * (37654 + add) + 0.8 * g))
    return dict(note="MODEL ONLY: algebra on OWNER-REPORTED 0.2778 and the declared masses; not a measurement",
                formula="s = T / (0.2*S + 0.8*G), thin-dot regime", by_G=out)


def main() -> int:
    t0 = time.time()
    log: list[str] = []

    def mark(msg: str) -> None:
        line = f"[H71] {msg} ({time.time() - t0:.1f}s)"
        print(line, flush=True)
        log.append(line)

    guard = None
    try:
        import stop_guard
        buf = io.StringIO()
        with redirect_stdout(buf):
            stopped = stop_guard.lane_is_stopped(ROOT, "H71 union of live-scored champion and H71-A")
        guard = dict(called=True, verdict="STOPPED" if stopped else "CLEAR",
                     output=buf.getvalue().strip(),
                     interpretation=("printed for the record; not used as a gate (not a lane runner, "
                                     "see registry/preregistration-h71.json)"))
    except Exception as exc:                                   # pragma: no cover
        guard = dict(called=False, error=str(exc))
    mark(f"stop_guard {guard['verdict']}")

    champ_sha, add_sha = sha256(CHAMPION), sha256(ADDEND)
    if champ_sha != CHAMPION_SHA:
        print(f"champion sha mismatch {champ_sha}")
        return 2
    if add_sha != ADDEND_SHA:
        print(f"H71-A sha mismatch {add_sha}")
        return 2
    card_a = json.loads((ROOT_EV / "h71a_runcard.json").read_text())
    mark(f"constituents verified: champion {champ_sha[:12]} H71-A {add_sha[:12]} "
         f"(card verdict {card_a['verdict']})")

    grid = G57.load_grid()
    fp, cat = grid.footprint, grid.catalogue
    champ = read_mask(CHAMPION)
    add = read_mask(ADDEND)
    if int((champ & add).sum()) != 0:
        print("constituents are not disjoint")
        return 3
    union = champ | add
    d_cat = ndi.distance_transform_edt(~cat)
    mark(f"union {int(union.sum()):,} dots (champion {int(champ.sum()):,} + H71-A {int(add.sum()):,}); "
         f"min d_catalogue {d_cat[union].min():.2f} px")

    # restricted pool of the H71-A profile: needed for mass-matched random additions
    score, allowed, field_diag, champ_again, wash = B71.build_field(grid, "restricted")
    assert np.array_equal(champ_again, champ)
    pool = np.flatnonzero(allowed.ravel())
    mark(f"restricted pool {pool.size:,} px (field diag recorded)")

    sample = ROOT / "data/official/sample_submission.tif"
    name = f"60GEMSDOE-H71-UNION-CHAMP-CONVCOMP-{int(union.sum())}-{STAMP}"
    note = ("H71 union: live-scored champion (37654 dots, 0.2778 owner-reported) plus the H71-A "
            "convergent-cover complement (6000 dots, credit/dot 0.4018 on SGMC-off)")
    rec = SW.write_submission(DL / f"gems60-h71-union-champ-convcomp-{int(union.sum())}-{STAMP}-zeros.tif",
                              union.astype(np.float32), sample, fp, note=note[:140], name=name[:140],
                              catalogue=cat,
                              metadata={"preregistration": "registry/preregistration-h71.json",
                                        "components": {"champion_sha256": champ_sha, "h71a_sha256": add_sha},
                                        "declared_mass_dots": int(union.sum())})
    mark(f"wrote {rec['file']} sha {rec['sha256'][:16]} validator={rec['validator']['all_checks_passed']}")

    # ---------------- G1: population-matched instrument ---------------- #
    sgmc = B71.read_stack(EXT / "sgmc_faults_100m.tif", nodata=255.0)[0] > 0
    offcat = I.sgmc_off_catalogue(sgmc, cat, fp, buffer_px=3)
    arms = {"H71_union": union, "champion": champ, "H71A_added": add}
    for s in RANDOM_SEEDS:
        r = np.random.default_rng(s)
        pick = r.choice(pool.size, size=int(add.sum()), replace=False)
        m = np.zeros(fp.shape, bool)
        m.ravel()[pool[pick]] = True
        arms[f"random_add_{s}"] = m
    inst = {k: I.global_dti(v.astype(np.float64), offcat, fp, cat) for k, v in arms.items()}
    for k, v in inst.items():
        mark(f"  sgmc_off {k:14s} dti={v['dti']:.5f} credit/px={v['credit_per_px']:.4f} dots={v['emitted_px']:,}")
    t = {k: terms(v, offcat) for k, v in arms.items()}
    paired_vs_champ = paired(t["H71_union"], t["champion"], draws=B71.BOOT_DRAWS, seed=B71.BOOT_SEED)
    paired_vs_add = paired(t["H71_union"], t["H71A_added"], draws=B71.BOOT_DRAWS, seed=B71.BOOT_SEED)
    rand_cpp = [t[f"random_add_{s}"]["tpw"] / max(1, t[f"random_add_{s}"]["dots"]) for s in RANDOM_SEEDS]
    champ_cpp = t["champion"]["tpw"] / max(1, t["champion"]["dots"])
    union_cpp = t["H71_union"]["tpw"] / max(1, t["H71_union"]["dots"])
    gate_g1 = dict(
        rule=("PASS iff credit/dot(H71) > credit/dot(champion) and the paired block-bootstrap "
              "lower bound of DTI(H71)-DTI(champion) on the SGMC-off-catalogue truth is > 0"),
        union_credit_per_dot=union_cpp, champion_credit_per_dot=champ_cpp,
        added_credit_per_dot=t["H71A_added"]["tpw"] / max(1, t["H71A_added"]["dots"]),
        random_add_credit_per_dot_mean=float(np.mean(rand_cpp)),
        random_add_credit_per_dot_each={str(s): rand_cpp[i] for i, s in enumerate(RANDOM_SEEDS)},
        paired_union_minus_champion=paired_vs_champ,
        paired_union_minus_h71a=paired_vs_add,
        break_even=BREAK_EVEN_NOTE,
        verdict=("PASS" if (union_cpp > champ_cpp and paired_vs_champ["delta_dti_ci95"][0] > 0) else "FAIL"))
    mark(f"G1 {gate_g1['verdict']}: union c/dot {union_cpp:.4f} vs champion {champ_cpp:.4f} "
         f"(added {gate_g1['added_credit_per_dot']:.4f}, random {gate_g1['random_add_credit_per_dot_mean']:.4f}); "
         f"paired DTI delta {paired_vs_champ['delta_dti']:+.5f} "
         f"[{paired_vs_champ['delta_dti_ci95'][0]:+.5f},{paired_vs_champ['delta_dti_ci95'][1]:+.5f}]")

    # ---------------- G2: registered holdout ---------------- #
    ctx = HO.build_holdout(grid)
    cells = [c for c in ctx.cells if c.mode == "all"]
    h_arms = {"H71_union": union, "champion": champ, "H71A_added": add,
              "random_add_mass_matched": arms[f"random_add_{RANDOM_SEEDS[0]}"]}
    hterms: dict = {k: [] for k in h_arms}
    for cell in cells:
        bb = cell.bbox
        truth_crop = ctx.hidden_by_cell[cell.key][bb] & cell.active
        fold = dict(region=cell.active, visible=np.zeros_like(cell.active), truth=truth_crop)
        for k, arr in h_arms.items():
            _, tt = EH.evaluate(arr[bb].astype(np.float32), fold, grid.footprint[bb],
                                block_side=B71.BLOCK_PX, origin=(bb[0].start, bb[1].start),
                                global_shape=(grid.height, grid.width))
            hterms[k].append(tt)
    pooled = EH.pooled_summary({k: np.sum(v, axis=0) for k, v in hterms.items()},
                               draws=B71.BOOT_DRAWS, seed=B71.BOOT_SEED, candidate="H71_union")
    delta = pooled["paired_differences"]["champion"]
    gate_g2 = dict(rule="PASS iff pooled HOLDOUT-DTI(H71) - HOLDOUT-DTI(champion) >= -0.002",
                   union_dti=pooled["scores"]["H71_union"]["dti"],
                   champion_dti=pooled["scores"]["champion"]["dti"],
                   delta=delta["delta"], ci95=delta["ci95"],
                   verdict=("PASS" if delta["delta"] >= -0.002 else "FAIL"))
    mark(f"G2 {gate_g2['verdict']}: union {gate_g2['union_dti']:.6f} champion {gate_g2['champion_dti']:.6f} "
         f"delta {delta['delta']:+.6f}")

    # ---------------- G3: uniqueness (three reported readings) ---------------- #
    add_pts = np.nonzero(add)
    rows = []
    corpus = sorted(set((REG / "rasters").glob("*.tif")) | set(DL.glob("*.tif")))
    for f in corpus:
        if f.name in (Path(rec["file"]).name, Path(rec["file"]).name.replace("-zeros", "-nan")):
            continue
        try:
            with rasterio.open(f) as src:
                if (src.height, src.width) != union.shape:
                    continue
                a = src.read(1).astype(np.float32)
        except Exception:                                        # pragma: no cover
            continue
        a[~np.isfinite(a)] = 0.0
        m = a > 0
        if not m.any():
            continue
        d = ndi.distance_transform_edt(~m)
        mine_frac = float((d[union] <= 3.0).mean())
        inc_frac = float((d[add_pts] <= 3.0).mean())
        champ_frac = float((d[champ] <= 3.0).mean())
        fp_frac = float((d[fp] <= 3.0).mean())
        x, y = union.ravel().astype(np.float64), a.ravel().astype(np.float64)
        rho = 1.0 if np.array_equal(x, y) else float(
            np.corrcoef(rankdata(x[_RHO_IDX]), rankdata(y[_RHO_IDX]))[0, 1])
        rep = U.representation_class(int(m.sum()), int(fp.sum()))
        rows.append(dict(raster=f.name,
                         source=("registry/rasters" if f.parent.name == "rasters" else "docs/downloads"),
                         their_dots=int(m.sum()), representation=rep["kind"],
                         support_fraction=round(rep["support_fraction"], 6),
                         artifact_dots_within_3px=round(mine_frac, 6),
                         increment_dots_within_3px=round(inc_frac, 6),
                         champion_dots_within_3px_of_theirs=round(champ_frac, 6),
                         footprint_fraction_within_3px=round(fp_frac, 6),
                         spearman=round(rho, 6), byte_identical=bool(np.array_equal(x, y)),
                         pixel_identical=bool(np.array_equal(m, union))))

    def is_universal(r):
        return r["footprint_fraction_within_3px"] > 0.99

    def is_lineage(r):
        return (any(p in r["raster"] for p in LINEAGE_PATTERNS)
                or r["champion_dots_within_3px_of_theirs"] >= 0.99)

    universal = [r for r in rows if is_universal(r)]
    lineage = [r for r in rows if (not is_universal(r)) and is_lineage(r)]
    eligible = [r for r in rows if (not is_universal(r)) and (not is_lineage(r))]
    art_max = max((r["artifact_dots_within_3px"] for r in eligible if r["representation"] == "dot_field"),
                  default=None)
    inc_max = max((r["increment_dots_within_3px"] for r in eligible), default=None)
    rho_max = max((abs(r["spearman"]) for r in eligible), default=None)
    worst_inc = min((r for r in eligible), key=lambda r: -r["increment_dots_within_3px"], default=None)
    non_universal = [r for r in rows if not is_universal(r)]
    inc_max_all = max((r["increment_dots_within_3px"] for r in non_universal), default=None)
    worst_inc_all = min((r for r in non_universal), key=lambda r: -r["increment_dots_within_3px"],
                        default=None)
    byte_unique = not any(r["byte_identical"] for r in rows)
    gate_g3 = dict(
        scanned=len(rows),
        scope="registry/rasters/*.tif + docs/downloads/*.tif, grid-matched, self excluded",
        spearman_method=("Spearman between the full artifact grid and each comparator grid on a fixed "
                         "400,000-pixel uniform subsample of the 12,279,160-pixel grid (seed 70)"),
        readings=dict(
            artifact=dict(max_dots_within_3px=art_max,
                          worst_raster=None if not eligible else min(
                              (r for r in eligible if r["representation"] == "dot_field"),
                              key=lambda r: -r["artifact_dots_within_3px"])["raster"],
                          passes=bool(art_max is not None and art_max <= B71.OVERLAP_LIMIT)),
            increment=dict(max_dots_within_3px=inc_max,
                           worst_raster=None if worst_inc is None else worst_inc["raster"],
                           passes=bool(inc_max is not None and inc_max <= B71.OVERLAP_LIMIT),
                           note="the standing <=70% clause applied to the 6,000 new dots only"),
            literal=dict(max_dots_within_3px=max(r["artifact_dots_within_3px"] for r in rows),
                         worst_raster=max(rows, key=lambda r: r["artifact_dots_within_3px"])["raster"],
                         passes=bool(max(r["artifact_dots_within_3px"] for r in rows)
                                     <= B71.OVERLAP_LIMIT))),
        exclusions=dict(
            definition=("set aside as universal blockers when the comparator's own dots lie within "
                        "3 px of >99% of the footprint (no emission can avoid them - IR-60-UNIQ-DENSE-01), "
                        "and as lineage when the comparator is a named champion-family file or contains "
                        ">=99% of the champion's dots within 3 px (an ancestor of this artifact by design)"),
            universal_blockers=[{k: r[k] for k in ("raster", "their_dots", "footprint_fraction_within_3px",
                                                   "artifact_dots_within_3px")} for r in universal],
            lineage=[{k: r[k] for k in ("raster", "their_dots", "artifact_dots_within_3px",
                                        "increment_dots_within_3px")} for r in lineage]),
        eligible_top=[{k: r[k] for k in ("raster", "their_dots", "representation", "artifact_dots_within_3px",
                                         "increment_dots_within_3px", "spearman")}
                      for r in sorted(eligible, key=lambda r: -r["artifact_dots_within_3px"])[:8]],
        max_abs_spearman_eligible=rho_max,
        increment_max_including_lineage=dict(
            max_dots_within_3px=inc_max_all,
            worst_raster=None if worst_inc_all is None else worst_inc_all["raster"],
            note="reported so that no lineage exclusion can hide a duplication signal in the new mass"),
        byte_unique=byte_unique,
        lineage_note=("IR-H71-LINE-01: this artifact is a strict superset of our own live-scored champion "
                      "by design; overlap with the champion's ancestors is structural and disclosed, and "
                      "the increment reading is the one that answers the standing clause's question "
                      "(does the new mass duplicate an existing artifact?)"),
        verdict=("PASS" if (art_max is not None and art_max <= B71.OVERLAP_LIMIT
                            and inc_max is not None and inc_max <= B71.OVERLAP_LIMIT
                            and rho_max is not None and rho_max <= B71.RHO_LIMIT
                            and byte_unique)
                 else ("QUALIFIED" if (inc_max is not None and inc_max <= B71.OVERLAP_LIMIT
                                       and rho_max is not None and rho_max <= B71.RHO_LIMIT
                                       and byte_unique) else "FAIL")),
        qualifier=("QUALIFIED means: the standing <=70% clause PASSES on the new mass (the increment "
                   "reading, which is the clause's question), the artifact is byte- and pixel-unique and "
                   "|rho| <= 0.90, but the clause FAILS on the artifact as a whole against rasters that "
                   "themselves contain the champion's support - structurally, because 37,654 of the "
                   "43,654 dots ARE the already-scored champion. The owner must weigh that explicitly; "
                   "if a virgin artifact is required, H71-A (6,000 dots, literal PASS at 0.5187) is the "
                   "clean alternative."))
    mark(f"G3 {gate_g3['verdict']}: artifact max {art_max} increment max {inc_max} "
         f"(worst increment {None if worst_inc is None else worst_inc['raster']}) rho_max {rho_max} | "
         f"excluded {len(universal)} universal + {len(lineage)} lineage")

    g3 = gate_g3["verdict"]
    verdict = ("PROMOTE" if (gate_g1["verdict"] == "PASS" and gate_g2["verdict"] == "PASS" and g3 == "PASS"
                             and rec["validator"]["all_checks_passed"])
               else ("PROMOTE-CANDIDATE-UNIQUENESS-QUALIFIED"
                     if (gate_g1["verdict"] == "PASS" and gate_g2["verdict"] == "PASS" and g3 == "QUALIFIED"
                         and rec["validator"]["all_checks_passed"]) else "NEGATIVE"))
    out = dict(
        run="H71", hypothesis_id="GEMS60-H71", generated_utc=STAMP,
        preregistration="registry/preregistration-h71.json",
        evidence_class="HOLDOUT-DTI + INSTRUMENT-DTI (proxies; NOT organizer-confirmed)",
        guard_report=guard,
        constituents=dict(
            champion=dict(file=CHAMPION.name, sha256=champ_sha, dots=int(champ.sum()),
                          live_score=0.2778, live_score_class="OWNER-REPORTED / UNVERIFIED"),
            added=dict(file=ADDEND.name, sha256=add_sha, dots=int(add.sum()),
                       source_card="evidence/h71a_runcard.json", source_verdict=card_a["verdict"],
                       credit_per_dot_sgmc_off=card_a["gates"]["G1_population_matched"]
                       ["h71a_credit_per_dot"])),
        artifact=dict(file=rec["file"], sha256=rec["sha256"], bytes=rec["bytes"], zip=rec["zip_file"],
                      zip_sha256=rec["zip_sha256"], submission_name=rec["submission_name"],
                      note=rec["note"], note_chars=rec["note_chars"],
                      validator_all_checks_passed=rec["validator"]["all_checks_passed"],
                      emitted=int(union.sum())),
        gates=dict(G1_population_matched=gate_g1, G2_registered_holdout=gate_g2, G3_uniqueness=gate_g3,
                   G4_portal=dict(all_checks_passed=rec["validator"]["all_checks_passed"])),
        instrument_sgmc_off=inst, holdout_pooled=pooled,
        algebra_projection=algebra_projection(gate_g1["added_credit_per_dot"], int(add.sum())),
        verdict=verdict,
        owner_decision_required=(
            "One upload, two readings. As a CANDIDATE: the union strictly contains the live-scored "
            "champion and adds 6,000 dots whose credit was measured at 0.4018 per dot on a "
            "population-matched real-fault instrument, against the break-even 0.0556; downside is "
            "bounded at -0.013 if the added mass carries zero live credit. As an ARTIFACT: it is a "
            "superset of an already-scored file, so if the standing uniqueness clause must hold on the "
            "whole artifact (not only on the new mass), the owner should either accept the disclosed "
            "inheritance or submit H71-A instead - which is literally unique but scores low alone."),
        interpretation=("The union tests one thing: whether measured-credit complementary mass pays when "
                        "added to the best-scoring artifact we own. G1 is the decisive gate; G2 is a no-harm "
                        "clause on an instrument known to be blind to off-catalogue arms; a PROMOTE is a "
                        "candidate for the owner's selector, never an organizer-confirmed score."),
        seconds=round(time.time() - t0, 1), log=log)
    (ROOT_EV / "h71_runcard.json").write_text(json.dumps(out, indent=2, default=float) + "\n")
    mark(f"verdict {verdict}; wrote evidence/h71_runcard.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
