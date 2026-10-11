"""H65 — the tectonic-geomorphology lane executed at the resolution it requires.

``dem10`` holds the numba kernels that run on a GitHub-hosted runner against the
official USGS 3DEP 1/3 arc-second (~10 m) DEM and reduce the 10 m channel
network to features on the 100 m competition grid.  Depression filling and
flow accumulation are the shared template kernels in ``gems52.lane_hydro``
(reused, not re-implemented).
"""
