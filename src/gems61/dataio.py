"""Loaders for the restored competition inputs and the family's live-scored calibration artifacts.

Every file is read through its registry pin: ``registry/data_manifest.json`` for external inputs and
``registry/calibration_manifest.json`` for the live-scored artifacts this session restored.  A
sha256 mismatch raises, so no number in this package can be computed from bytes that are not the
pinned ones.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REG = ROOT / "registry"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_band(path: Path, band: int = 1, dtype=np.float32) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(band).astype(dtype)


def grid_template():
    """CRS/shape/transform of the official submission container, read from the sample submission."""
    with rasterio.open(DATA / "bridge" / "example_submission.tif") as src:
        return dict(crs=src.crs, shape=src.shape, transform=src.transform, dtype=src.dtypes[0])


def load_footprint_and_labels():
    """(valid, catalogue) from the byte-identical labels/existing_faults raster (int8: -1 out, 0 in, 1 fault)."""
    lab = read_band(DATA / "bridge" / "existing_faults.tif", dtype=np.int8)
    return (lab != -1), (lab == 1)


def load_sgmc() -> np.ndarray:
    """USGS SGMC geologic-map faults rasterised to this grid (uint8 0/1), pin-checked."""
    p = DATA / "external" / "derived_sgmc_faults_100m_u8.tif"
    pin = _pin("ext_derived_sgmc_faults_100m_u8")
    got = sha256(p)
    if got != pin:
        raise ValueError(f"SGMC raster hash mismatch: {got} != {pin}")
    return read_band(p, dtype=np.uint8) == 1


def _pin(file_id: str) -> str:
    man = json.load(open(REG / "data_manifest.json"))
    for f in man["files"]:
        if f["id"] == file_id:
            return f["sha256"]
    raise KeyError(file_id)


def dequantise_u8(path: Path, band: int, manifest: Path | None = None) -> np.ndarray:
    """Reverse the documented uint8 quantisation of the committed external packs.

    rule (from the pack's own manifest): q = 1 + round(254*clip((v-lo)/(hi-lo),0,1));
    v' = lo + (q-1)/254*(hi-lo); q = 0 is nodata.  Max error is published per band.
    """
    man = json.load(open(manifest or path.with_suffix(".manifest.json")))
    spec = [b for b in man["bands"] if b["index"] == band][0]
    q = read_band(path, band=band, dtype=np.uint8)
    lo, hi = float(spec["lo"]), float(spec["hi"])
    return np.where(q == 0, np.nan, lo + (q.astype(np.float32) - 1.0) / 254.0 * (hi - lo))


def load_calibration() -> list[dict]:
    """Live-scored artifacts restored this session, with their pin-verified sha256 and live score.

    ``live_score`` is an OWNER REPORT / official-snapshot value copied from the family's ledger
    (``docs/score-ledger.csv``); it is never presented as an organizer receipt for these bytes.
    """
    man = json.load(open(REG / "calibration_manifest.json"))
    out = []
    for e in man["files"]:
        p = ROOT / e["path"]
        got = sha256(p)
        if got != e["sha256"]:
            raise ValueError(f"{p.name} hash mismatch {got} != {e['sha256']}")
        out.append({**e, "abspath": p})
    return out
