"""
config.py
---------
Single source of truth for all shared paths and constants.
Import this in fetch_data.py, query.py, and render.py instead of
hardcoding values in each file.

Layout assumption
-----------------
  meteodata-lab-env/
  ├── config.py          ← this file
  ├── total_0-33.nc      ← written by fetch_data.py
  ├── backend/
  │   ├── fetch_data.py
  │   └── query.py
  └── frontend/
      ├── render.py
      ├── rain.html
      └── style.css
"""

from pathlib import Path

# ── Root of the project (directory containing this file) ─────────────────────
ROOT = Path(__file__).resolve().parent


# ── File paths ────────────────────────────────────────────────────────────────
NC_FILE  = ROOT / "total_0-33.nc"       # NetCDF written by fetch_data.py
HTML_TEMPLATE = ROOT / "frontend" / "rain.html"
HTML_OUT      = ROOT / "frontend" / "rain_out.html"


# ── OGD API / forecast parameters ────────────────────────────────────────────
COLLECTION        = "ogd-forecasting-icon-ch1"
VARIABLE          = "TOT_PREC"
REFERENCE_DATETIME = "latest"
LEAD_HOURS        = range(0, 34)        # +00h … +33h inclusive
EPS_SLICE         = slice(1, 10)        # perturbed members for probability


# ── Grid definition (must match the regridded NetCDF) ────────────────────────
# Extent: (lon_min, lon_max, lat_min, lat_max)  —  WGS-84 / EPSG:4326
EXTENT  = (-0.817, 18.183, 41.183, 51.183)
NX, NY  = 429, 295

# Derived convenience unpacking used by regrid.RegularGrid and Leaflet bounds
LON_MIN, LON_MAX, LAT_MIN, LAT_MAX = EXTENT

# Leaflet [[lat_min, lon_min], [lat_max, lon_max]]
LEAFLET_BOUNDS = [[LAT_MIN, LON_MIN], [LAT_MAX, LON_MAX]]


# ── Visualisation ─────────────────────────────────────────────────────────────
# Distance mask: only render pixels within RADIUS_KM of CH_CENTER
CH_CENTER  = (46.8, 8.2)    # (lat, lon) — centre of Switzerland
RADIUS_KM  = 350

COLORMAP   = "YlOrRd"
RAIN_MIN_DISPLAY = 0.01     # mm — values below this are rendered transparent
PRECIP_THRESHOLD = 0.1      # mm — threshold for rain-probability calculation
HEAVY_THRESHOLD  = 3.5      # mm — default for find_heavy_rain()
