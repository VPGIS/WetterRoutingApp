"""
query.py
Query functions for the ICON-CH1-EPS NetCDF output produced by fetch_data.py.

Usage example
-------------
    from query import open_dataset, query_point, find_heavy_rain

    ds = open_dataset("total_0-33.nc")
    print(query_point(ds, lat=47.56, lon=7.59, lead_hour=17))
    find_heavy_rain(ds, threshold=3.5)
"""

import numpy as np
import xarray as xr

DEFAULT_FILE = "total_0-33.nc"
EPS_SLICE = slice(1, 10)  # perturbed members used for probability


# ── helpers ──────────────────────────────────────────────────────────────────

def open_dataset(path: str = DEFAULT_FILE) -> xr.Dataset:
    return xr.open_dataset(path)


def _nearest_yx(da: xr.DataArray, lat: float, lon: float) -> tuple[int, int]:
    """Return (iy, ix) of the grid cell nearest to (lat, lon)."""
    dist = np.sqrt((da.lat - lat) ** 2 + (da.lon - lon) ** 2)
    iy, ix = np.unravel_index(dist.values.argmin(), dist.shape)
    return int(iy), int(ix)


def sel_latlon(da: xr.DataArray, lat: float, lon: float) -> xr.DataArray:
    """Select the grid cell nearest to (lat, lon)."""
    iy, ix = _nearest_yx(da, lat, lon)
    return da.isel(y=iy, x=ix)


# ── public API ────────────────────────────────────────────────────────────────

def query_point(
    ds: xr.Dataset,
    lat: float,
    lon: float,
    lead_hour: int,
) -> dict:
    """
    Return ensemble-mean hourly rainfall and rain probability for a single
    (lat, lon, lead_hour) combination.

    Parameters
    ----------
    ds : xr.Dataset
        Dataset as returned by open_dataset().
    lat, lon : float
        Target coordinates (WGS-84).
    lead_hour : int
        Forecast lead time in hours (1 – 33; index 0 not available for
        hourly_rain because it is a diff of cumulative totals).

    Returns
    -------
    dict with keys: lat, lon, lead_hour, rainfall_mm, probability_pct
    """
    da_all = ds["TOT_PREC"]
    hourly_rain = ds["hourly_rain"]

    rain_pt = sel_latlon(hourly_rain, lat, lon)
    tot_pt = sel_latlon(da_all, lat, lon)

    # hourly_rain diff index i corresponds to the interval [+i h … +(i+1) h]
    diff_idx = lead_hour - 1
    rainfall = float(rain_pt.isel(lead_time=diff_idx))

    # Probability: fraction of perturbed members with >0.1 mm in that hour
    prob = float(
        (
            (
                tot_pt.sel(eps=EPS_SLICE).isel(lead_time=lead_hour)
                - tot_pt.sel(eps=EPS_SLICE).isel(lead_time=lead_hour - 1)
            )
            > 0.1
        ).mean("eps")
        * 100
    )

    return {
        "lat": lat,
        "lon": lon,
        "lead_hour": lead_hour,
        "rainfall_mm": round(rainfall, 2),
        "probability_pct": round(prob, 0),
    }


def find_heavy_rain(
    ds: xr.Dataset,
    threshold: float = 3.5,
) -> list[dict]:
    """
    Find all grid cells where ensemble-mean hourly rain exceeds *threshold*
    in any forecast hour.

    Returns a list of dicts sorted by peak rainfall (descending).
    """
    hourly_rain = ds["hourly_rain"]
    heavy_mask = (hourly_rain > threshold).any(dim="lead_time")
    iy_all, ix_all = np.where(heavy_mask.values)

    results = []
    for iy, ix in zip(iy_all, ix_all):
        lat = float(hourly_rain.lat.isel(y=iy, x=ix))
        lon = float(hourly_rain.lon.isel(y=iy, x=ix))
        cell_rain = hourly_rain.isel(y=iy, x=ix)
        heavy_hours = [
            {"lead_hour": h + 1, "rainfall_mm": round(float(v), 2)}
            for h, v in enumerate(cell_rain.values)
            if v > threshold
        ]
        results.append({"lat": lat, "lon": lon, "heavy_hours": heavy_hours})

    results.sort(
        key=lambda r: max(h["rainfall_mm"] for h in r["heavy_hours"]), reverse=True
    )
    return results


if __name__ == "__main__":
    ds = open_dataset()
    print("Basel +17h:", query_point(ds, lat=47.56, lon=7.59, lead_hour=17))
    print("Zürich +30h:", query_point(ds, lat=47.37, lon=8.54, lead_hour=30))
    hits = find_heavy_rain(ds, threshold=3.5)
    print(f"\nFound {len(hits)} cells with >3.5 mm/h")
    for r in hits[:5]:
        hrs = ", ".join(f"+{h['lead_hour']:02d}h={h['rainfall_mm']}mm" for h in r["heavy_hours"])
        print(f"  lat={r['lat']:.2f} lon={r['lon']:.2f} → {hrs}")
