import time
import numpy as np
import rasterio
from landlab import RasterModelGrid
from landlab.components import FlowAccumulator, ChiFinder

def test_full_grid():
    with rasterio.open("data/training_features.tif") as src:
        dem = src.read(13).astype(np.float32)
        
    t0 = time.time()
    dem = np.where(dem < -1e3, np.nan, dem)
    dem = np.where(np.isnan(dem), np.nanmin(dem), dem)
    
    # Downsample by 2 to save time if needed, or run full size
    # For speed let's just run full size and see
    # It has 12 million nodes... D8 flow routing might take 10-30 seconds
    mg = RasterModelGrid((dem.shape[0], dem.shape[1]), xy_spacing=100.0)
    z = mg.add_zeros('topographic__elevation', at='node')
    z[:] = dem.flatten()
    
    print("Routing flow...")
    fa = FlowAccumulator(mg, flow_director='D8')
    fa.run_one_step()
    
    print("Finding chi...")
    cf = ChiFinder(mg, min_drainage_area=100000.0, reference_concavity=0.5, use_true_dx=True)
    cf.calculate_chi()
    
    print(f"Done in {time.time() - t0:.1f}s")

if __name__ == "__main__":
    test_full_grid()