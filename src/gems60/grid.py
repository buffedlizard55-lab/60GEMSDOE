"""Grid, footprint and submission I/O for the 60GEMSDOE lane.

Everything here is pinned to the organiser's own artifacts, never to a transcription:

  * shape 3292 x 3730, cell 100 m, EPSG:32611, transform origin (243350.0, 4508550.0);
  * footprint = the 5,167,373 finite cells of ``sample_submission.tif``
    (equivalently the cells of ``labels.tif`` that are not nodata``-1``);
  * the catalogue = the 60,988 cells of ``labels.tif`` equal to 1.

The writer emits a single-band float32 GeoTIFF with

  * no NaN anywhere (the competition validator that rejected a downloaded file with
    "Predicted values must be in range [0, 1]" is satisfied by construction when every stored
    value is finite and in [0, 1]),
  * values in [0, 1],
  * the organiser's CRS / shape / transform.

The organiser's own ``sample_submission.tif`` stores NaN outside the footprint and declares
``nodata = nan``.  Both containers are accepted upstream (the reported champion file is a
zero-filled all-finite container).  We ship the all-finite container as PRIMARY because it is the
only one that cannot fail a literal ``0 <= v <= 1`` range test under a reader that ignores nodata,
and we ship the NaN-outside container as a clearly-labelled diagnostic variant.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# ----------------------------------------------------------------------------------------------
# Pins.  These are the observed values in this checkout; ``registry/source_pins.json`` records the
# sha256 of every input file actually used, computed with hashlib at read time (never quoted).
# ----------------------------------------------------------------------------------------------
SHAPE = (3730, 3292)          # (height, width)
CELL_M = 100.0
CRS_EPSG = 32611
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
FOOTPRINT_PX = 5_167_373
CATALOGUE_PX = 60_988


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


@dataclass(frozen=True)
class Grid:
    shape: tuple[int, int]
    transform: tuple[float, ...]
    crs_epsg: int
    footprint: np.ndarray     # bool, True inside the scored region

    @property
    def n_footprint(self) -> int:
        return int(self.footprint.sum())


def read_template(sample_submission: str | Path) -> tuple[Grid, np.ndarray]:
    """Return the grid and the raw sample-submission array (validated against the pins)."""
    with rasterio.open(sample_submission) as ds:
        arr = ds.read(1)
        if (ds.height, ds.width) != SHAPE:
            raise ValueError(f"shape {ds.height}x{ds.width} != pinned {SHAPE}")
        if ds.crs is None or ds.crs.to_epsg() != CRS_EPSG:
            raise ValueError(f"crs {ds.crs} != EPSG:{CRS_EPSG}")
        got = tuple(round(v, 6) for v in tuple(ds.transform)[:6])
        if got != TRANSFORM:
            raise ValueError(f"transform {got} != pinned {TRANSFORM}")
    footprint = np.isfinite(arr)
    if int(footprint.sum()) != FOOTPRINT_PX:
        raise ValueError(f"footprint {int(footprint.sum())} != pinned {FOOTPRINT_PX}")
    return Grid(SHAPE, TRANSFORM, CRS_EPSG, footprint), arr


def read_labels(labels_path: str | Path) -> np.ndarray:
    """The supplied USGS+INGENIOUS fault catalogue as a boolean mask (values equal to 1)."""
    with rasterio.open(labels_path) as ds:
        lab = ds.read(1)
    cat = lab == 1
    if int(cat.sum()) != CATALOGUE_PX:
        raise ValueError(f"catalogue {int(cat.sum())} != pinned {CATALOGUE_PX}")
    return cat


def write_submission(pred: np.ndarray, out_path: str | Path, grid: Grid, *,
                     outside: str = "zeros") -> dict:
    """Write the deliverable GeoTIFF and return a validator report.

    ``outside="zeros"`` writes 0.0 outside the footprint (all-finite container; PRIMARY).
    ``outside="nan"``   writes NaN outside the footprint with nodata declared (diagnostic only).
    """
    if pred.shape != grid.shape:
        raise ValueError(f"prediction shape {pred.shape} != grid {grid.shape}")
    p = np.asarray(pred, dtype=np.float32)
    if not np.isfinite(p[grid.footprint]).all():
        raise ValueError("non-finite prediction values inside the footprint")
    if p[grid.footprint].min() < 0.0 or p[grid.footprint].max() > 1.0:
        raise ValueError("prediction values inside the footprint outside [0, 1]")
    full = np.zeros(grid.shape, dtype=np.float32)
    full[grid.footprint] = p[grid.footprint]
    if outside == "nan":
        full[~grid.footprint] = np.nan
    elif outside != "zeros":
        raise ValueError("outside must be 'zeros' or 'nan'")
    profile = dict(driver="GTiff", height=grid.shape[0], width=grid.shape[1], count=1,
                   dtype="float32", crs=f"EPSG:{grid.crs_epsg}", transform=grid.transform,
                   nodata=(np.nan if outside == "nan" else None), compress="deflate",
                   tiled=True, blockxsize=256, blockysize=256)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as ds:
        ds.write(full, 1)
        ds.update_tags(AREA_OR_POINT="Area")
    return validate_submission(out_path)


def validate_submission(path: str | Path) -> dict:
    """Re-open the written file and check the four portal requirements literally."""
    with rasterio.open(path) as ds:
        arr = ds.read(1)
        finite_vals = arr[np.isfinite(arr)]
        nodata = ds.nodata
        rep = {
            "file": Path(path).name,
            "sha256": None,
            "bytes": Path(path).stat().st_size,
            "width": ds.width, "height": ds.height, "count": ds.count,
            "dtype": ds.dtypes[0],
            "crs": (ds.crs.to_string() if ds.crs else None),
            "crs_epsg": (ds.crs.to_epsg() if ds.crs else None),
            "transform": [round(v, 6) for v in tuple(ds.transform)[:6]],
            "nodata": (None if nodata is None else (float(nodata) if np.isfinite(nodata) else "nan")),
            "n_finite": int(np.isfinite(arr).sum()),
            "n_nonfinite": int((~np.isfinite(arr)).sum()),
            "min_finite": float(finite_vals.min()) if finite_vals.size else None,
            "max_finite": float(finite_vals.max()) if finite_vals.size else None,
            "n_values_outside_0_1": int(((finite_vals < 0.0) | (finite_vals > 1.0)).sum()),
            "n_positive": int((finite_vals > 0).sum()),
            "mass": float(finite_vals.sum()),
            "n_distinct_positive_values": int(np.unique(finite_vals[finite_vals > 0]).size),
        }
    rep["sha256"] = sha256(path)
    checks = {
        "single_band_float32": rep["count"] == 1 and rep["dtype"] == "float32",
        "crs_epsg_32611": rep["crs_epsg"] == CRS_EPSG,
        "shape_matches": (rep["height"], rep["width"]) == SHAPE,
        "transform_matches": tuple(rep["transform"]) == TRANSFORM,
        "all_values_in_0_1": rep["n_values_outside_0_1"] == 0,
        "no_nan_in_finite_container": rep["n_nonfinite"] == 0,
    }
    rep["checks"] = checks
    rep["passes_portal_range_test"] = bool(checks["all_values_in_0_1"])
    rep["passes_all_literal_checks"] = bool(all(checks.values()))
    return rep


def write_json(path: str | Path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")
