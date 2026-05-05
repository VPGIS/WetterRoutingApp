import xarray as xr

infile = "backend/nc_folder/NC_for_Cellid.nc"
outfile = "backend/nc_folder/mesh_slim.nc"

ds = xr.open_dataset(infile)

keep_vars = [
    "clon", "clat",
    "elon", "elat",
    "vlon", "vlat",
    "edge_of_cell",
    "adjacent_cell_of_edge",
    "cell_area",
    "edge_length",
    "dual_edge_length",
]

keep_vars = [v for v in keep_vars if v in ds.variables]

slim = ds[keep_vars]

# Zeitkoordinaten entfernen, falls sie noch als unnötige Koordinaten hängen bleiben
for coord in list(slim.coords):
    if "time" in slim[coord].dims or coord.lower() in ["time", "time_counter"]:
        slim = slim.drop_vars(coord)

slim.to_netcdf(outfile)