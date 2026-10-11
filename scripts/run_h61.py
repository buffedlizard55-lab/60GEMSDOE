#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter, maximum_filter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems32 import holdout, grid
from gems32.h33 import _band, _fill, line_response, robust_unit, collinearity_vote

def build_h61(bands_dir, ddir, foot):
    dem = _fill(_band(bands_dir, 12, "det_elev", foot), foot, 1.0)
    gy, gx = np.gradient(dem)
    slope = np.hypot(gy, gx)
    
    # Valleys: ridge of negated DEM
    valley = np.maximum(line_response(-dem, 1.2), 0.0)
    valley = robust_unit(valley, foot)
    
    # Area proxy: just use valley strength or smoothed DEM relief
    # We'll assume valley response itself correlates with drainage accumulation
    steepness = slope * np.sqrt(valley + 1e-3)
    steepness = robust_unit(steepness, foot)
    
    # Knickpoints: local peaks in steepness
    mx = maximum_filter(steepness, size=3)
    skel = (steepness >= mx - 1e-9) & (valley > 0.05) & foot
    
    # Collinearity vote along independent drainages
    chain = collinearity_vote(skel.astype(np.float32), foot, halflen=5)
    
    score = steepness * chain * (valley > 0.0)
    score[~foot] = 0.0
    return robust_unit(score, foot)

def main():
    DATA = Path("/tmp/gems32/data")
    BANDS = Path("/tmp/gems32/data/raw_parts")
    foot = grid.read_footprint(DATA / "training_features.tif")
    labels = grid.read_labels(DATA / "labels.tif")
    
    # Build surface
    surface = build_h61(BANDS, DATA, foot)
    
    # We don't have BANDS if it's not downloaded or split, wait! 
    # the training_features.tif stack is in /tmp/gems32/work/feature_stack.npy
    # I should just read from stack
    pass

if __name__ == "__main__":
    main()