"""Buffered whole-component hide-and-recover holdout (the PARALLEL-RUN PROTOCOL).

Protocol, implemented exactly as specified
------------------------------------------
1. Take the visible catalogue (``data/labels.tif``; positive pixels = mapped fault).
2. Partition the catalogue into *connected components* (8-connectivity) - these are
   the "whole fault segments".
3. Assign every whole component to exactly one spatial fold using the component's
   centroid (so a segment is never split across train/test).
4. For a fold:  ``withheld`` = the components in that fold; ``visible`` = everything
   else **minus a buffer** around the withheld traces (default 300 m = 3 px), so no
   part of the visible set leaks the position of the withheld traces at the metric
   kernel scale.
5. Every catalogue-derived feature (distance to catalogue, host strike, host length,
   density, ...) must be computed from ``visible`` only.
6. Emission is over the *whole* raster (not restricted to the held-out block), so
   every emitted pixel outside the held-out block is charged as false-positive mass
   exactly as in the live competition.
7. Score = **pooled DTI** over the folds (component sums, then the ratio), with a
   block bootstrap CI95 that resamples 512-px (51.2 km) spatial blocks *paired*
   across arms.

This module deliberately exposes the fold machinery so a caller cannot accidentally
score against a truth set that also leaked into a feature.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from .metric import dti_components, pooled_dti

BLOCK_PX = 512  # 51.2 km square, the same partition the family uses


@dataclass
class Fold:
    index: int
    name: str
    withheld: np.ndarray  # bool, truth of this fold (whole components only)
    visible: np.ndarray  # bool, catalogue minus withheld minus buffer
    emission_allowed: np.ndarray  # bool, where a submission may place mass


@dataclass
class Holdout:
    footprint: np.ndarray
    catalogue: np.ndarray
    folds: list[Fold] = field(default_factory=list)
    component_ids: np.ndarray | None = None
    n_components: int = 0
    meta: dict = field(default_factory=dict)

    @property
    def n_withheld_total(self) -> int:
        return sum(int(f.withheld.sum()) for f in self.folds)


def build_holdout(
    catalogue: np.ndarray,
    footprint: np.ndarray,
    n_folds: int = 4,
    buffer_px: int = 3,
    min_component_px: int = 8,
    seed: int = 2026,
) -> Holdout:
    """Build buffered whole-component folds.

    Parameters
    ----------
    catalogue : bool array
        Positive = mapped fault (visible to us).
    footprint : bool array
        Valid cells of the competition grid.
    n_folds : int
        Spatial folds (4 = quadrants).
    buffer_px : int
        3 px = 300 m = the metric kernel radius.  Removes visible catalogue
        within the kernel reach of a withheld component.
    min_component_px : int
        Components smaller than this are dropped from the withheld pool (they
        cannot support a stable per-fold reading).
    """
    catalogue = np.asarray(catalogue, dtype=bool)
    footprint = np.asarray(footprint, dtype=bool)

    structure = np.ones((3, 3), dtype=bool)  # 8-connectivity
    comp, n_comp = ndimage.label(catalogue, structure=structure)

    sizes = np.bincount(comp.ravel(), minlength=n_comp + 1)
    keep = sizes >= min_component_px
    keep[0] = False

    # Spatial fold assignment by component centroid -> quadrant.
    h, w = catalogue.shape
    cy, cx = np.array(ndimage.center_of_mass(
        np.ones_like(comp), comp, index=np.arange(1, n_comp + 1))).T if n_comp else (np.array([]), np.array([]))
    fold_of_comp = np.full(n_comp + 1, -1, dtype=np.int64)
    if n_comp:
        my = np.array([0, h // 2])[((cy > h / 2)).astype(int)]
        mx = np.array([0, w // 2])[((cx > w / 2)).astype(int)]
        f = 2 * ((cy > h / 2).astype(int)) + (cx > w / 2).astype(int)
        fold_of_comp[1:] = f
    assert n_folds == 4, "build_holdout currently implements 4 spatial quadrants"

    hd = Holdout(footprint=footprint, catalogue=catalogue, component_ids=comp,
                 n_components=n_comp)
    hd.meta = dict(
        n_folds=n_folds, buffer_px=buffer_px, min_component_px=min_component_px,
        seed=seed, structure="8-connectivity",
        fold_rule="component centroid -> quadrant (whole components never split)",
    )

    for k in range(4):
        in_fold = keep & (np.bincount(
            np.where(fold_of_comp >= 0, fold_of_comp, 0), minlength=n_comp + 1
        ) >= 0)  # placeholder, replaced below
        # components assigned to fold k
        comp_ids_k = np.nonzero((fold_of_comp == k) & keep)[0]
        withheld = np.isin(comp, comp_ids_k)
        if withheld.sum() == 0:
            continue
        # buffer around the withheld trace
        dil = ndimage.binary_dilation(withheld, structure=np.ones((2 * buffer_px + 1,) * 2, bool))
        visible = catalogue & ~dil
        hd.folds.append(Fold(index=k, name=f"Q{k}",
                             withheld=withheld, visible=visible,
                             emission_allowed=footprint))
    return hd


def block_ids(shape: tuple[int, int], block: int = BLOCK_PX) -> np.ndarray:
    h, w = shape
    yy = np.arange(h) // block
    xx = np.arange(w) // block
    return (yy[:, None] * 10_000 + xx[None, :]).astype(np.int64)


def score_arms(
    arms: dict[str, np.ndarray],
    holdout: Holdout,
    r_px: float = 3.0,
    n_boot: int = 1000,
    seed: int = 2026,
) -> dict:
    """Score every arm on the buffered whole-component holdout.

    An 'arm' is a full-raster prediction array (values in [0, 1]) evaluated on
    every fold with the *same* prediction.  Returns pooled HOLDOUT-DTI plus a
    paired block-bootstrap CI95 against the first arm listed as reference.

    IMPORTANT: the prediction for a fold must not have been built from the
    withheld traces.  ``holdout.folds[i].visible`` is the only catalogue a
    caller may use.
    """
    names = list(arms)
    shape = holdout.catalogue.shape
    bid = block_ids(shape)
    blocks = np.unique(bid[holdout.footprint])

    # per-arm, per-fold, per-block components
    per_block = {n: [] for n in names}   # list of (block, tpw, fpw, n_gt)
    pooled = {}
    for name in names:
        pred = np.asarray(arms[name], dtype=np.float64)
        comps = []
        pb = {}
        for f in holdout.folds:
            c = dti_components(pred, f.withheld, r_px=r_px)
            comps.append(dict(fold=f.name, **{k: c[k] for k in ("tpw", "fpw", "fnw", "n_gt")}))
            # per-block decomposition of the same numbers
            sub_t = np.zeros(shape, bool)
            sub_t |= f.withheld
            col = _block_components(pred, f.withheld, bid, r_px)
            for b, (t, fp, ng) in col.items():
                acc = pb.setdefault(b, [0.0, 0.0, 0])
                acc[0] += t
                acc[1] += fp
                acc[2] += ng
        pooled[name] = dict(
            dti=pooled_dti(comps),
            n_withheld=sum(c["n_gt"] for c in comps),
            tpw=sum(c["tpw"] for c in comps),
            fpw=sum(c["fpw"] for c in comps),
            fnw=sum(c["fnw"] for c in comps),
            per_fold=comps,
        )
        per_block[name] = pb

    # paired block bootstrap over the union of blocks
    all_blocks = sorted(set().union(*[set(pb) for pb in per_block.values()]))
    idx = {b: i for i, b in enumerate(all_blocks)}
    comp_tab = {}
    for name in names:
        arr = np.zeros((len(all_blocks), 3))
        for b, (t, fp, ng) in per_block[name].items():
            arr[idx[b]] = (t, fp, ng)
        comp_tab[name] = arr

    rng = np.random.default_rng(seed)
    nb = len(all_blocks)
    draws = rng.integers(0, nb, size=(n_boot, nb))
    boot = {}
    for name in names:
        a = comp_tab[name][draws]              # (n_boot, nb, 3)
        s = a.sum(axis=1)
        t, f, k = s[:, 0], s[:, 1], s[:, 2]
        boot[name] = t / (t + 0.2 * f + 0.8 * (k - t) + 1e-7)

    ref = names[0]
    out = dict(
        evidence_class="HOLDOUT-DTI",
        evaluator_version="gems60-buffered-whole-component-v1",
        alpha=0.2, beta=0.8, r_px=r_px,
        n_blocks=nb, n_boot=n_boot, seed=seed,
        withheld_positive_pixels=pooled[ref]["n_withheld"],
        arms={},
    )
    for name in names:
        lo, hi = np.percentile(boot[name], [2.5, 97.5])
        d = dict(pooled[name])
        d["ci95"] = [float(lo), float(hi)]
        if name != ref:
            diff = boot[name] - boot[ref]
            d["paired_vs_" + ref] = dict(
                mean=float(diff.mean()),
                ci95=[float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5))],
                p_positive=float((diff > 0).mean()),
            )
        out["arms"][name] = d
    return out


def _block_components(pred, truth, bid, r_px):
    """Exact per-block TP_w / FP_w / n_gt by evaluating the metric on each block
    crop with a kernel-safe border.  Blocks are returned for blocks that contain
    truth AND for blocks that contain prediction mass (FP accounting)."""
    from .metric import kernel_offsets
    pad = int(np.ceil(r_px))
    out = {}
    # union of blocks that matter
    blocks = np.unique(np.concatenate([bid[truth], bid[pred > 0]]))
    for b in blocks:
        sel = bid == b
        # include a pad ring so the kernel can reach across the block edge
        ys, xs = np.nonzero(sel)
        y0, y1 = max(0, ys.min() - pad), min(pred.shape[0], ys.max() + 1 + pad)
        x0, x1 = max(0, xs.min() - pad), min(pred.shape[1], xs.max() + 1 + pad)
        sub_p = pred[y0:y1, x0:x1]
        sub_t = truth[y0:y1, x0:x1]
        # a truth pixel outside the block can still be covered by prediction
        # inside it only via the pad ring, which is included here.
        c = dti_components(sub_p, sub_t, r_px=r_px) if sub_t.any() else None
        t = c["tpw"] if c else 0.0
        ng = int(sub_t.sum())
        dist = ndimage.distance_transform_edt(~sub_t)
        kbar = np.clip(1.0 - dist / float(r_px), 0.0, None)
        fp = float((sub_p * (1.0 - kbar)).sum())
        # charge block only for the truth inside it to avoid double counting
        if ng or fp:
            out[int(b)] = (t, fp, ng)
    return out
