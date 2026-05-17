"""
utils_render.py

Pre-renders all hourly-rain frames as PNGs into backend/data/rain_layers/.
Called by utils_fetch.py right after each successful fetch, BEFORE the
0.01 mm/h threshold is applied, so raw ensemble-mean diff values are used.

Rendering approach (matches frontend/render.py):
  - Regular 429x295 lat/lon grid (linspace bounds)
  - Haversine mask: only show rain within 350 km of Switzerland centre
  - Normalise colour to global max across all lead times
  - Blue-scale colormap (white -> mid-blue -> dark blue)
  - Gaussian blur (sigma=1.5) to smooth GRIB2 quantisation artefacts
  - plt.imsave on RGBA array (no figure/axes overhead)

PNG naming: rain_YYYYMMDDTHHMMSS.png  (UTC valid time)
"""

import io
import shutil
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from scipy.ndimage import gaussian_filter

BACKEND_DIR = Path(__file__).resolve().parent
RAIN_LAYERS_DIR = BACKEND_DIR / "data" / "rain_layers"

# --- Grid (must match utils_fetch.py constants) ---
_LONS = np.linspace(-0.817, 18.183, 429)
_LATS = np.linspace(41.183, 51.183, 295)
_LON, _LAT = np.meshgrid(_LONS, _LATS)

# --- Distance mask: within 350 km of Switzerland centre ---
_CH_LAT, _CH_LON = 46.8, 8.2
_RADIUS_KM = 350


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2
         + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
    return R * 2 * np.arcsin(np.sqrt(a))


_WITHIN_MASK = _haversine(_LAT, _LON, _CH_LAT, _CH_LON) <= _RADIUS_KM

# Yellow (light rain) -> orange -> red (heavy rain)
_CMAP = plt.cm.YlOrRd
_ALPHA_MAX = 0.82
_ALPHA_RAMP = 0.08       # rain rate (mm/h) at which alpha reaches _ALPHA_MAX
_SMOOTH_SIGMA = 2.0      # Gaussian blur to smooth GRIB2 quantisation steps


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------

def _iso_to_filename(iso: str) -> str:
    """'2026-05-17T10:00:00.000Z' -> 'rain_20260517T100000.png'"""
    clean = iso.replace("-", "").replace(":", "").replace(".000Z", "").replace("Z", "")
    return f"rain_{clean}.png"


def _filename_to_iso(name: str) -> str:
    """'rain_20260517T100000.png' -> '2026-05-17T10:00:00.000Z'"""
    ts = name.replace("rain_", "").replace(".png", "")  # '20260517T100000'
    return (
        f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        f"T{ts[9:11]}:{ts[11:13]}:{ts[13:15]}.000Z"
    )


# ---------------------------------------------------------------------------
# Core rendering
# ---------------------------------------------------------------------------

def render_all_frames(hourly_rain: xr.DataArray, ref_time_np) -> Path:
    """
    Render every lead-time slice in *hourly_rain* to a PNG and save into
    RAIN_LAYERS_DIR.  Old PNGs are cleared first.

    Pass the *raw* ensemble-mean diff (before any 0.01-threshold clean-up)
    so that the full value range is available for colour normalisation.

    Parameters
    ----------
    hourly_rain : xr.DataArray  shape (lead_time, y, x) – raw hourly diff
    ref_time_np : numpy.datetime64  model reference time
    """
    if RAIN_LAYERS_DIR.exists():
        shutil.rmtree(RAIN_LAYERS_DIR)
    RAIN_LAYERS_DIR.mkdir(parents=True)

    # Global max for consistent colour scale across all frames
    global_max = float(np.nanmax(hourly_rain.values))
    norm = mcolors.Normalize(vmin=0, vmax=max(global_max, 0.1))

    lead_times = hourly_rain.coords["lead_time"].values  # float hours
    ref_ts = int(ref_time_np) / 1e9                      # epoch seconds
    n = len(lead_times)

    for i, h in enumerate(lead_times):
        rain = np.nan_to_num(hourly_rain.isel(lead_time=i).values, nan=0.0)
        rain = np.maximum(rain, 0.0)           # clip any negative diff artefacts

        # Gaussian smooth to compensate for GRIB2 quantisation steps
        rain_smooth = gaussian_filter(rain, sigma=_SMOOTH_SIGMA)

        # Apply haversine mask: transparent outside 350 km radius
        rain_masked = np.where(_WITHIN_MASK, rain_smooth, np.nan)

        rgba = _CMAP(norm(np.nan_to_num(rain_masked)))          # (y, x, 4)
        # Proportional alpha: intensity drives both colour and transparency,
        # so Gaussian-smoothed gradients produce soft visible edges.
        # Ramp from 0 -> _ALPHA_MAX over the range [0, _ALPHA_RAMP] mm/h.
        alpha = np.where(
            _WITHIN_MASK,
            np.clip(rain_masked / _ALPHA_RAMP, 0.0, 1.0) * _ALPHA_MAX,
            0.0,
        )
        rgba[..., 3] = np.nan_to_num(alpha)

        frame_dt = datetime.fromtimestamp(ref_ts + h * 3600, tz=timezone.utc)
        fname = f"rain_{frame_dt.strftime('%Y%m%dT%H%M%S')}.png"

        buf = io.BytesIO()
        plt.imsave(buf, np.flipud(rgba), format="png")
        (RAIN_LAYERS_DIR / fname).write_bytes(buf.getvalue())
        print(f"  [render] {fname}  ({i + 1}/{n})")

    print(f"[render] {n} frames saved -> {RAIN_LAYERS_DIR}")
    return RAIN_LAYERS_DIR


def render_from_nc(nc_path: Path) -> Path:
    """
    Load *nc_path*, recompute the raw ensemble-mean hourly diff from TOT_PREC
    (bypassing the 0.01 threshold already baked into the saved hourly_rain),
    and call render_all_frames().
    """
    ds = xr.open_dataset(nc_path)
    try:
        mean_precip = ds["TOT_PREC"].mean("eps").squeeze("ref_time")  # (lead, y, x)
        raw_diff = mean_precip.diff("lead_time")
        return render_all_frames(raw_diff, ds.coords["ref_time"].values[0])
    finally:
        ds.close()


# ---------------------------------------------------------------------------
# FastAPI helpers
# ---------------------------------------------------------------------------

def get_rain_layer_path(time_str: str) -> Path:
    """
    Return the Path to the pre-rendered PNG for the given ISO timestamp.
    Raises FileNotFoundError if the file does not exist.
    """
    path = RAIN_LAYERS_DIR / _iso_to_filename(time_str)
    if not path.exists():
        raise FileNotFoundError(f"Pre-rendered frame not found: {path.name}")
    return path


def list_rain_times() -> list[str]:
    """Return sorted ISO timestamp strings for all available rain PNGs."""
    return [
        _filename_to_iso(f.name)
        for f in sorted(RAIN_LAYERS_DIR.glob("rain_*.png"))
    ]
