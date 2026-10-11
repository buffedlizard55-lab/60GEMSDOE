import numpy as np
import rasterio
from landlab import RasterModelGrid
from landlab.components import FlowAccumulator, FastscapeEroder, ChiFinder, Profiler

def test_chi():
    with rasterio.open("data/training_features.tif") as src:
        dem = src.read(13) # band 12 is 0-indexed 12, 1-indexed 13
        dem = dem[:500, :500] # take a subset

    # Filter NaN
    dem = np.where(dem < -1e3, np.nan, dem)
    dem = np.where(np.isnan(dem), np.nanmin(dem), dem)
    
    mg = RasterModelGrid((500, 500), xy_spacing=100.0)
    z = mg.add_zeros('topographic__elevation', at='node')
    z[:] = dem.flatten()
    
    # route flow
    fa = FlowAccumulator(mg, flow_director='D8')
    fa.run_one_step()
    
    # chi
    cf = ChiFinder(mg, min_drainage_area=100000.0, reference_concavity=0.5, use_true_dx=True)
    cf.calculate_chi()
    
    chi = mg.at_node['channel__chi_index'].reshape((500, 500))
    steepness = mg.at_node['channel__steepness_index'].reshape((500, 500))
    print("Chi max:", np.nanmax(chi))
    print("Steepness max:", np.nanmax(steepness))

if __name__ == "__main__":
    test_chi()