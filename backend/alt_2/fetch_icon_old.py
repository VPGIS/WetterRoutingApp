"""
Fetch ICON-CH1 from meteoswiss OGD, regrid to a regular lat/lon grid,
compute hourly precipitation from the cumulative forecast, and save the
result to a timestamped NetCDF file in backend/nc_folder.
"""

import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import xarray as xr
from earthkit.data import config
from meteodatalab import ogd_api
from meteodatalab.operators import regrid
from rasterio.crs import CRS

config.set("cache-policy", "temporary")

# --- Grid definition ---
EXTENT = (-0.817, 18.183, 41.183, 51.183)
NX, NY = 429, 295
DESTINATION = regrid.RegularGrid(CRS.from_epsg(4326), NX, NY, *EXTENT)

LEAD_HOURS = range(0, 34)
OUTPUT_DIR = Path(__file__).resolve().parent / "nc_folder"


def clean_attrs(attrs: dict) -> dict:
    """Strip non-serializable attributes so xarray can write NetCDF."""
    valid_types = (str, int, float, bytes, list, tuple)
    return {k: v for k, v in attrs.items() if isinstance(v, valid_types)}


def build_output_path(output_dir: Path = OUTPUT_DIR) -> Path:
    """Return a timestamped NetCDF path using the current Unix time."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return output_dir / f"{timestamp}.nc"


def fetch_and_save(output_dir: Path = OUTPUT_DIR) -> Path:
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

    da_all.attrs = clean_attrs(da_all.attrs)
    for coord in da_all.coords:
        da_all[coord].attrs = clean_attrs(da_all[coord].attrs)

    mean_precip = da_all.mean("eps").squeeze("ref_time")
    hourly_rain = mean_precip.diff("lead_time")
    hourly_rain = hourly_rain.drop_vars("valid_time", errors="ignore")
    hourly_rain.values = np.where(
        hourly_rain.values < 0.01,
        0.0,
        np.round(hourly_rain.values, 2),
    )
    hourly_rain.attrs = {
        "long_name": "Hourly precipitation (ensemble mean)",
        "units": "mm/m2",
    }

    ds = xr.Dataset({
        "TOT_PREC": da_all,
        "hourly_rain": hourly_rain,
    })

    output_file = build_output_path(output_dir)
    ds.to_netcdf(output_file)
    print(f"Saved → {output_file}")

    try:
        ds.close()
    except Exception:
        pass

    return output_file


def check_fetch_on_startup():
    """On startup: if newest .nc is older than latest scheduled time, fetch immediately."""
    now = datetime.now(timezone.utc)
    scheduled_hours = [0, 3, 6, 9, 12, 15, 18, 21]
    
    # Find the latest scheduled time (00:05, 03:05, etc.) before now
    latest_scheduled = max(
        (now.replace(hour=h, minute=5, second=0, microsecond=0)
         for h in scheduled_hours
         if now.replace(hour=h, minute=5, second=0, microsecond=0) <= now),
        default=None
    )
    
    # Check if we need to fetch
    nc_files = list(OUTPUT_DIR.glob("*.nc"))
    needs_fetch = True
    
    if nc_files and latest_scheduled:
        newest_mtime = max(f.stat().st_mtime for f in nc_files)
        needs_fetch = newest_mtime < latest_scheduled.timestamp()
    
    if needs_fetch:
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] Data outdated, fetching...")
        fetch_and_save()
    else:
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] Data up-to-date")


def scheduler_loop():
    """Background loop: fetch at 00:05, 03:05, 06:05, ..., 21:05 UTC."""
    scheduled_hours = [0, 3, 6, 9, 12, 15, 18, 21]
    
    while True:
        now = datetime.now(timezone.utc)
        next_times = [
            now.replace(hour=h, minute=5, second=0, microsecond=0)
            + (timedelta(days=1) if now.replace(hour=h, minute=5, second=0, microsecond=0) <= now else timedelta(0))
            for h in scheduled_hours
        ]
        
        next_fetch_time = min(next_times)
        wait_seconds = (next_fetch_time - datetime.now(timezone.utc)).total_seconds()
        
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] Next fetch at {next_fetch_time.strftime('%H:%M UTC')}")
        time.sleep(max(wait_seconds, 1))
        
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] Fetching...")
        fetch_and_save()


if __name__ == "__main__":
    check_fetch_on_startup()
    scheduler_loop()