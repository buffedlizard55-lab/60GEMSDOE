"""H73 negative artifact: new bytes, honest gates and fail-closed portal format."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
STEM = "gems60-h73-paired-basin-ksn-20000-20261011T200117Z-zeros"
TIF = ROOT / "docs" / "downloads" / f"{STEM}.tif"
CARD = json.loads((ROOT / "evidence" / "h73_runcard.json").read_text())


def test_h73_is_a_new_valid_negative_artifact():
    assert TIF.is_file()
    digest = hashlib.sha256(TIF.read_bytes()).hexdigest()
    assert digest == "594e05573e5aca3e661ac48c71e27edc7dbe8030777992e60068a4b368903cb3"
    assert digest == CARD["raster_sha256"]
    assert CARD["verdict"] == "negative"
    assert CARD["submit_to_competition"] is False
    assert CARD["submission_note_chars"] <= 140
    assert CARD["validator_output"]["all_checks_passed"] is True


def test_h73_disk_values_are_finite_in_range_and_on_template():
    with rasterio.open(TIF) as src, rasterio.open(ROOT / "data" / "official" / "sample_submission.tif") as sample:
        a = src.read(1)
        assert src.count == 1 and src.dtypes == ("float32",)
        assert src.crs == sample.crs
        assert src.shape == sample.shape == (3730, 3292)
        assert src.transform == sample.transform
        assert src.nodata is None
    assert np.isfinite(a).all()
    assert float(a.min()) == 0.0 and float(a.max()) == 1.0
    assert int((a > 0).sum()) == 20_000
    np.testing.assert_allclose(np.unique(a), [0.0, 0.05, 1.0], rtol=0, atol=1e-7)


def test_h73_run_card_carries_required_negative_evidence():
    hold = CARD["holdout_dti"]
    assert hold["evidence_class"] == "HOLDOUT-DTI"
    assert hold["evaluator_version"] == "gems57-pooled-hide-v2"
    assert hold["withheld_positive_pixels"] == 22641
    assert hold["dti"] < hold["recorded_h68_best"]["dti"]
    assert CARD["dual_first_test_gate"]["passed"] is False
    uniq = CARD["correlation_overlap_vs_registry"]
    assert uniq["pinned_registry_complete"] is True
    assert uniq["checked_unique_sha_rasters"] == 680
    assert uniq["surface_before_placement"]["byte_unique"] is True
    assert uniq["surface_before_placement"]["pixel_unique"] is True
    assert uniq["surface_before_placement"]["max_abs_spearman"] <= 0.90
    assert uniq["surface_before_placement"]["max_overlap_within_3px"] > 0.70
    assert uniq["surface_before_placement"]["passes"] is False


def test_home_page_makes_download_and_no_submit_decision_obvious():
    html = (ROOT / "docs" / "index.html").read_text()
    assert TIF.name in html
    assert "NEW BYTE/PIXEL-UNIQUE H73 GeoTIFF" in html
    assert "COMPETITION SUBMISSION: NO" in html
    assert "DO NOT SUBMIT" in html
