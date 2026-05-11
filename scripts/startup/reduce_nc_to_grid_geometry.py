"""reduziert ein .nc im angegebenen Ordner auf lat/lon."""

from pathlib import Path
import sys

import xarray as xr


OUTPUT_NAME = "NC_for_Cellid.nc"
LAT_NAME = "lat"
LON_NAME = "lon"


def reduce_nc_to_grid_geometry(nc_folder):
    nc_folder = Path(nc_folder)
    output_file = nc_folder / OUTPUT_NAME

    if output_file.exists():
        return

    input_files = [f for f in nc_folder.glob("*.nc") if f.name != OUTPUT_NAME]

    if not input_files:
        raise RuntimeError(f"Keine .nc-Datei in {nc_folder} gefunden.")

    input_file = input_files[0]

    with xr.open_dataset(input_file, decode_times=False) as ds:
        ds[[LAT_NAME, LON_NAME]].to_netcdf(output_file)


if __name__ == "__main__":
    reduce_nc_to_grid_geometry(sys.argv[1])