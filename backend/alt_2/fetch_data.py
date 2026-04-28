"""
fetch_data.py
Fetches ICON-CH1-EPS TOT_PREC from OGD API, regrids to a regular lat/lon grid,
computes hourly precipitation and saves everything to total_0-33.nc.
"""

import xarray as xr
import numpy as np
from meteodatalab import ogd_api
from meteodatalab.operators import regrid
from rasterio.crs import CRS
from datetime import timedelta
from earthkit.data import config

config.set("cache-policy", "temporary")

# --- Grid definition ---
EXTENT = (-0.817, 18.183, 41.183, 51.183)  # (lon_min, lon_max, lat_min, lat_max)
NX, NY = 429, 295
DESTINATION = regrid.RegularGrid(CRS.from_epsg(4326), NX, NY, *EXTENT)

LEAD_HOURS = range(0, 34)
OUTPUT_FILE = "total_0-33.nc"


def clean_attrs(attrs: dict) -> dict:
    """Strip non-serialisable attributes so xarray can write NetCDF."""
    valid_types = (str, int, float, bytes, list, tuple)
    return {k: v for k, v in attrs.items() if isinstance(v, valid_types)}


def fetch_and_save(output_file: str = OUTPUT_FILE) -> xr.Dataset:
    das = []
    for h in LEAD_HOURS:
        req = ogd_api.Request(
            collection="ogd-forecasting-icon-ch1",
            variable="TOT_PREC",
            reference_datetime="latest",
            perturbed=True,
            horizon=timedelta(hours=h),
        )
        da_h = ogd_api.get_from_ogd(req)
        da_h_geo = regrid.iconremap(da_h, DESTINATION)
        das.append(da_h_geo)
        print(f"✓ +{h:02d}h")

    da_all = xr.concat(das, dim="lead_time")
    da_all = da_all.assign_coords(lead_time=[timedelta(hours=h) for h in LEAD_HOURS])

    # Clean attributes
    da_all.attrs = clean_attrs(da_all.attrs)
    for coord in da_all.coords:
        da_all[coord].attrs = clean_attrs(da_all[coord].attrs)

    # Compute hourly precipitation from cumulative total
    mean_precip = da_all.mean("eps").squeeze("ref_time")  # (lead_time, y, x)
    hourly_rain = mean_precip.diff("lead_time")
    hourly_rain = hourly_rain.drop_vars("valid_time", errors="ignore")
    hourly_rain.values = np.where(
        hourly_rain.values < 0.01, 0.0, np.round(hourly_rain.values, 2)
    )
    hourly_rain.attrs = {
        "long_name": "Hourly precipitation (ensemble mean)",
        "units": "mm/m2",
    }

    ds = xr.Dataset({"TOT_PREC": da_all, "hourly_rain": hourly_rain})
    ds.to_netcdf(output_file)
    print(f"Saved → {output_file}")
    try:
        ds.close()
    except Exception:
        pass
    return ds


if __name__ == "__main__":
    fetch_and_save()
