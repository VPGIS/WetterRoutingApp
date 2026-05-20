"""
query.py
Query functions for the ICON-CH1-EPS NetCDF output produced by fetch_data.py.

Usage examples
--------------
from query import open_dataset, query_point, query_points, find_heavy_rain
import pandas as pd

ds = open_dataset("total_0-33.nc")

# 1. Single point
print(query_point(ds, lat=47.56, lon=7.59, lead_hour=17))

# 2. Many points, each with its own lead_hour
locs = pd.DataFrame({
    "name":      ["Basel", "Zürich"],
    "lat":       [47.56,   47.37],
    "lon":       [7.59,    8.54],
    "lead_hour": [17,      30],
})
print(query_points(ds, locs))

# 3. Many points, all at the same lead_hour
print(query_points(ds, locs[["name","lat","lon"]], lead_hour=6))

# 4. Many points, ALL lead hours (no lead_hour specified, no column)
print(query_points(ds, locs[["name","lat","lon"]]))
"""

import numpy as np
import xarray as xr
import pandas as pd
from scipy.spatial import cKDTree

DEFAULT_FILE = "total_0-33.nc"
EPS_SLICE    = slice(1, 10)   # perturbed members used for probability

# ── helpers ───────────────────────────────────────────────────────────────────

def open_dataset(path: str = DEFAULT_FILE) -> xr.Dataset:
    return xr.open_dataset(path)


def _nearest_yx(da: xr.DataArray, lat: float, lon: float) -> tuple[int, int]:
    """Nearest grid cell for a single point."""
    dist = np.sqrt((da.lat - lat) ** 2 + (da.lon - lon) ** 2)
    iy, ix = np.unravel_index(dist.values.argmin(), dist.shape)
    return int(iy), int(ix)


def _nearest_yx_batch(da: xr.DataArray,
                      lats: np.ndarray,
                      lons: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Nearest-neighbour search using a KD-Tree for extreme speed and low memory.
    """
    grid_lat = da.lat.values
    grid_lon = da.lon.values
    
    # Flatten grid coordinates into shape (N_grid_points, 2)
    grid_coords = np.column_stack((grid_lat.ravel(), grid_lon.ravel()))
    target_coords = np.column_stack((lats, lons))
    
    # Build tree and query nearest neighbors
    tree = cKDTree(grid_coords)
    _, flat_idx = tree.query(target_coords)
    
    # Convert 1D indices back to 2D grid indices
    iy, ix = np.unravel_index(flat_idx, grid_lat.shape)
    return iy, ix


def sel_latlon(da: xr.DataArray, lat: float, lon: float) -> xr.DataArray:
    """Single-point cell selection."""
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
    Single (lat, lon, lead_hour) query.
    Returns dict with rainfall_mm and probability_pct.
    """
    da_all      = ds["TOT_PREC"]
    hourly_rain = ds["hourly_rain"]

    rain_pt = sel_latlon(hourly_rain, lat, lon)
    tot_pt  = sel_latlon(da_all,      lat, lon)

    rainfall = float(rain_pt.isel(lead_time=lead_hour - 1).squeeze())
    prob     = float(
        (
            (tot_pt.sel(eps=EPS_SLICE).isel(lead_time=lead_hour)
           - tot_pt.sel(eps=EPS_SLICE).isel(lead_time=lead_hour - 1))
            > 0.1
        ).mean("eps").squeeze() * 100
    )
    return {
        "lat":             lat,
        "lon":             lon,
        "lead_hour":       lead_hour,
        "rainfall_mm":     round(rainfall, 2),
        "probability_pct": round(prob, 0),
    }


def query_points(
    ds: xr.Dataset,
    locations: pd.DataFrame,
    lead_hour: int | None = None,
) -> pd.DataFrame:
    """
    Vectorised multi-point query. Handles three scenarios:

    Scenario A — single lead_hour for all rows (fastest):
        query_points(ds, locs, lead_hour=6)
        'locations' needs columns: lat, lon

    Scenario B — per-row lead_hour:
        query_points(ds, locs)
        'locations' needs columns: lat, lon, lead_hour

    Scenario C — all lead hours (1-33) for every location:
        query_points(ds, locs)         ← no lead_hour col, no lead_hour arg
        'locations' needs columns: lat, lon
        Returns N×33 rows.

    Any extra columns (name, id, …) are preserved in the output.
    Output adds columns: lead_hour (if expanded), rainfall_mm, probability_pct.
    """
    da_all      = ds["TOT_PREC"]
    hourly_rain = ds["hourly_rain"]
    all_hours   = list(range(1, len(hourly_rain.lead_time) + 1))  # 1-33

    # ── determine which lead hours to run ────────────────────────────────────
    has_col = "lead_hour" in locations.columns

    if lead_hour is not None:
        # Scenario A: single lead_hour for every row
        locs = locations.copy()
        locs["lead_hour"] = lead_hour
    elif has_col:
        # Scenario B: each row has its own lead_hour
        locs = locations.copy()
    else:
        # Scenario C: expand every location across all lead hours
        locs = locations.loc[locations.index.repeat(len(all_hours))].copy()
        locs["lead_hour"] = all_hours * len(locations)
        locs = locs.reset_index(drop=True)

    lats       = locs["lat"].values.astype(float)
    lons       = locs["lon"].values.astype(float)
    lead_hours = locs["lead_hour"].values.astype(int)
    n          = len(lats)

    # ── one nearest-neighbour pass for all N locations ────────────────────────
    iy, ix = _nearest_yx_batch(hourly_rain, lats, lons)

    # Pull all lead times for selected cells in one shot
    # hourly_rain: (lead_time, y, x)       → (lead_time, N)
    # TOT_PREC:    (eps, ref_time, lead_time, y, x) → squeeze ref_time
    rain_vals  = hourly_rain.values[:, iy, ix]                     # (lead_time, N)
    tot_vals   = da_all.sel(eps=EPS_SLICE).values[:, 0, :, :, :]  # (eps, lead_time, y, x)
    tot_at_pts = tot_vals[:, :, iy, ix]                            # (eps, lead_time, N)

    # ── index per-row lead_hour ───────────────────────────────────────────────
    idx     = np.arange(n)
    diff_i  = lead_hours - 1

    rainfall   = rain_vals[diff_i, idx]                            # (N,)
    hourly_eps = (tot_at_pts[:, lead_hours, idx]
                - tot_at_pts[:, lead_hours - 1, idx])              # (eps, N)
    probability = (hourly_eps > 0.1).mean(axis=0) * 100           # (N,)

    result = locs.copy()
    result["rainfall_mm"]     = np.round(rainfall, 2)
    result["probability_pct"] = np.round(probability, 0)
    return result


def find_heavy_rain(
    ds: xr.Dataset,
    threshold: float = 3.5,
) -> list[dict]:
    """
    Find all grid cells where ensemble-mean hourly rain exceeds threshold
    in any forecast hour. Returns list of dicts sorted by peak rainfall.
    """
    hourly_rain            = ds["hourly_rain"]
    heavy_mask             = (hourly_rain > threshold).any(dim="lead_time")
    iy_all, ix_all         = np.where(heavy_mask.values)

    results = []
    for iy, ix in zip(iy_all, ix_all):
        lat       = float(hourly_rain.lat.isel(y=iy, x=ix))
        lon       = float(hourly_rain.lon.isel(y=iy, x=ix))
        cell_rain = hourly_rain.isel(y=iy, x=ix)
        heavy_hours = [
            {"lead_hour": h + 1, "rainfall_mm": round(float(v), 2)}
            for h, v in enumerate(cell_rain.values)
            if v > threshold
        ]
        results.append({"lat": lat, "lon": lon, "heavy_hours": heavy_hours})

    results.sort(
        key=lambda r: max(h["rainfall_mm"] for h in r["heavy_hours"]),
        reverse=True,
    )
    return results


if __name__ == "__main__":
    ds = open_dataset()

    # single point
    print("Basel +17h:", query_point(ds, lat=47.56, lon=7.59, lead_hour=17))

    locs = pd.DataFrame({
        "name": ["Basel", "Zürich", "Bern"],
        "lat":  [47.56,   47.37,   46.95],
        "lon":  [7.59,    8.54,    7.44],
    })

    # Scenario A: all locations at lead_hour=6
    print("\nAll at +6h:")
    print(query_points(ds, locs, lead_hour=6))

    # Scenario B: per-row lead_hour
    locs_b = locs.copy()
    locs_b["lead_hour"] = [17, 30, 10]
    print("\nPer-row lead_hour:")
    print(query_points(ds, locs_b))

    # Scenario C: all lead hours for every location (N×33 rows)
    print("\nAll lead hours:")
    print(query_points(ds, locs))

    # heavy rain scan
    hits = find_heavy_rain(ds, threshold=3.5)
    print(f"\nFound {len(hits)} cells with >3.5 mm/h")
    for r in hits[:5]:
        hrs = ", ".join(f"+{h['lead_hour']:02d}h={h['rainfall_mm']}mm" for h in r["heavy_hours"])
        print(f"  lat={r['lat']:.2f} lon={r['lon']:.2f} → {hrs}")