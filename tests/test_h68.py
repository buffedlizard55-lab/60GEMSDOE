"""Verification tests for Round H68 (strict multi-drainage 10 m bedrock Delta-ksn + 1 m LiDAR / 10 m piedmont break)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
TIF_NAME = "gems60-h68-dem10-lidar-piedmont-dksn-40000-20261011T185033Z-6e9b1e286c45-zeros.tif"


def test_h68_geotiff_portal_legality_and_sha256():
    tif_path = ROOT / "docs/downloads" / TIF_NAME
    sub_path = ROOT / "submission" / TIF_NAME
    assert tif_path.is_file() and sub_path.is_file()
    card = json.loads((ROOT / "submission_card.json").read_text())
    runcard = json.loads((ROOT / "evidence/h68_runcard.json").read_text())
    assert card == runcard
    assert card["run"] == "H68-1"
    assert card["verdict"] == "negative"
    assert len(card["submission_note"]) <= 140
    sha = hashlib.sha256(tif_path.read_bytes()).hexdigest()
    assert sha == card["raster_sha256"]
    assert hashlib.sha256(sub_path.read_bytes()).hexdigest() == sha

    with rasterio.open(tif_path) as src:
        assert str(src.crs) == "EPSG:32611"
        assert (src.height, src.width) == (3730, 3292)
        assert src.count == 1
        assert src.dtypes[0] == "float32"
        assert src.nodata is None
        arr = src.read(1)
    assert int(np.isnan(arr).sum()) == 0
    assert int(np.isinf(arr).sum()) == 0
    assert float(arr.min()) == 0.0
    assert float(arr.max()) == 1.0
    assert int((arr > 0).sum()) == 40000


def test_h68_e1_canary_holdout_and_uniqueness_receipts():
    e1 = json.loads((ROOT / "evidence/h68_e1_first_test.json").read_text())["summary"]
    assert e1["verdict"] == "PROCEED"
    assert e1["n_components"] == 262
    assert e1["mean"] > 0.44
    assert e1["ci95"][0] > 0.25

    hold = json.loads((ROOT / "evidence/h68_holdout.json").read_text())
    sc = hold["pooled_binary"]["scores"]["lane_h60a"]
    assert sc["evidence_class"] == "HOLDOUT-DTI"
    assert sc["withheld_positive_pixels"] == 22641
    assert abs(sc["dti"] - 0.17189388819690232) < 1e-9
    assert sc["ci95"][0] > 0.15

    for row in hold["canary"]:
        if row["feature"] != "dist_to_visible":
            assert row["max_abs_auc"] <= 0.90
            assert row["leakage_flag"] is False

    suniq = json.loads((ROOT / "evidence/h68_surface_uniqueness.json").read_text())
    assert suniq["worst_spearman_full_footprint"] <= 0.90
    assert suniq["scope"]["worst_overlap_sparse_non_lattice"] <= 0.70

    uniq = json.loads((ROOT / "evidence/h68_uniqueness.json").read_text())
    assert uniq["worst_spearman_full_footprint"] <= 0.90
    assert uniq["scope"]["worst_overlap_sparse_non_lattice"] <= 0.70

    uniq_sparse = json.loads((ROOT / "evidence/h68_uniqueness_sparse_control.json").read_text())
    assert uniq_sparse["gate_G5"]["passes_literal_gates_vs_sparse_corpus"] is True
    assert uniq_sparse["gate_G5"]["sparse_rows_tripping_a_gate"] == 0


def test_h68_status_banners_present_on_readme_and_pages():
    for rel in ("README.md", "index.html", "executive-summary.html", "docs/index.html", "docs/executive-summary.html"):
        txt = (ROOT / rel).read_text()
        assert TIF_NAME in txt, f"{rel} missing H68 TIF link"
        assert "DO NOT SUBMIT" in txt, f"{rel} missing DO NOT SUBMIT notice"
