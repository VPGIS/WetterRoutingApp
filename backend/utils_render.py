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
DEMO_RAIN_LAYERS_DIR = BACKEND_DIR / "data" / "rain_layers_demo"

# --- Grid (must match utils_fetch.py constants) ---
_LONS = np.linspace(-0.817, 18.183, 429)
_LATS = np.linspace(41.183, 51.183, 295)
_LON, _LAT = np.meshgrid(_LONS, _LATS)

# --- Distance mask: fade from fully opaque (inside) to transparent (outside) ---
_CH_LAT, _CH_LON = 46.8, 8.2
_RADIUS_KM = 350       # hard outer limit
_FEATHER_KM = 80       # fade zone: full opacity at (RADIUS-FEATHER), zero at RADIUS


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2
         + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
    return R * 2 * np.arcsin(np.sqrt(a))


_DIST_KM = _haversine(_LAT, _LON, _CH_LAT, _CH_LON)
_WITHIN_MASK = _DIST_KM <= _RADIUS_KM
# Smooth fade weight: 1.0 inside core, cosine falloff through feather zone, 0.0 outside
_inner = _RADIUS_KM - _FEATHER_KM
_EDGE_WEIGHT = np.where(
    _DIST_KM <= _inner,
    1.0,
    np.where(
        _DIST_KM <= _RADIUS_KM,
        0.5 * (1.0 + np.cos(np.pi * (_DIST_KM - _inner) / _FEATHER_KM)),
        0.0,
    ),
)

# Discrete rain intensity classes — boundaries and colours follow SRF/MeteoSwiss legend.
# Below _MIN_RAIN → fully transparent.  Above: one solid colour per class.
_MIN_RAIN = 0.2          # mm/h — cutoff; sub-drizzle noise ignored

# Class boundaries (mm/h): 0.2–0.6, 0.6–2, 2–8, 8–30, 30–100, ≥100
_BOUNDS = [_MIN_RAIN, 0.6, 2.0, 8.0, 30.0, 100.0, 9999.0]
_COLORS = [
    "#A8DCFF",   # <1   mm/h  – hellblau        (SRF light blue)
    "#4DB3FF",   # 1–3  mm/h  – mittelblau       (SRF medium blue)
    "#1A5FD4",   # 3–10 mm/h  – königsblau       (SRF royal blue)
    "#002090",   # 10–30 mm/h – dunkelblau        (SRF dark blue)
    "#FF8800",   # 30–100 mm/h – orange           (SRF orange)
    "#CC1100",   # ≥100 mm/h  – rot               (SRF red)
]
_CMAP = mcolors.ListedColormap(_COLORS)
_NORM = mcolors.BoundaryNorm(_BOUNDS, len(_COLORS))

_SMOOTH_SIGMA = 0.4      # very light blur — sharp spatial edges


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------

def _iso_to_mean_filename(iso: str) -> str:
    """'2026-05-17T10:00:00.000Z' -> 'rain_mean_20260517T100000.png'"""
    clean = iso.replace("-", "").replace(":", "").replace(".000Z", "").replace("Z", "")
    return f"rain_mean_{clean}.png"


def _iso_to_p90_filename(iso: str) -> str:
    """'2026-05-17T10:00:00.000Z' -> 'rain_p90_20260517T100000.png'"""
    clean = iso.replace("-", "").replace(":", "").replace(".000Z", "").replace("Z", "")
    return f"rain_p90_{clean}.png"


def _mean_filename_to_iso(name: str) -> str:
    """'rain_mean_20260517T100000.png' -> '2026-05-17T10:00:00.000Z'"""
    ts = name.replace("rain_mean_", "").replace(".png", "")
    return (
        f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        f"T{ts[9:11]}:{ts[11:13]}:{ts[13:15]}.000Z"
    )


# ---------------------------------------------------------------------------
# Core rendering
# ---------------------------------------------------------------------------

def render_all_frames(
    hourly_rain_mean: xr.DataArray,
    hourly_rain_p90: xr.DataArray,
    ref_time_np,
    output_dir: Path = None,
) -> Path:
    """
    Render two sets of PNGs per lead-time frame:

    Layer 1 — ``rain_layers/rain_mean_*.png``  (bottom)
        Colour: ensemble mean → shows "most-likely" intensity class
        Opacity: high (0.80–0.95), scaled by certainty (mean/p90)
        Purpose: the solid, confident rain core

    Layer 2 — ``rain_layers_p90/rain_p90_*.png``  (top)
        Colour: p90 → shows upper-bound intensity class
        Opacity: low (0.30–0.50), only where p90 > mean class boundary
        Purpose: translucent "possibility halo" around the core

    Parameters
    ----------
    hourly_rain_mean : xr.DataArray  shape (lead_time, y, x) – ensemble mean diff
    hourly_rain_p90  : xr.DataArray  shape (lead_time, y, x) – 90th-pct diff
    ref_time_np : numpy.datetime64  model reference time
    """
    target_dir = output_dir if output_dir is not None else RAIN_LAYERS_DIR
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    lead_times = hourly_rain_mean.coords["lead_time"].values
    ref_ts = int(ref_time_np) / 1e9
    n = len(lead_times)

    for i, h in enumerate(lead_times):
        mean_rain = np.nan_to_num(hourly_rain_mean.isel(lead_time=i).values, nan=0.0)
        p90_rain  = np.nan_to_num(hourly_rain_p90.isel(lead_time=i).values,  nan=0.0)
        mean_rain = np.maximum(mean_rain, 0.0)
        p90_rain  = np.maximum(p90_rain,  0.0)

        mean_smooth = gaussian_filter(mean_rain, sigma=_SMOOTH_SIGMA)
        p90_smooth  = gaussian_filter(p90_rain,  sigma=_SMOOTH_SIGMA)

        mean_val = np.nan_to_num(np.where(_WITHIN_MASK, mean_smooth, np.nan))
        p90_val  = np.nan_to_num(np.where(_WITHIN_MASK, p90_smooth,  np.nan))

        safe_p90 = np.where(p90_val > _MIN_RAIN, p90_val, 1.0)
        certainty = np.clip(mean_val / safe_p90, 0.0, 1.0)  # 1 = all agree

        frame_dt = datetime.fromtimestamp(ref_ts + h * 3600, tz=timezone.utc)
        ts_str = frame_dt.strftime('%Y%m%dT%H%M%S')

        # ── Layer 1: mean — solid core ────────────────────────────────────────
        rgba_mean = _CMAP(_NORM(mean_val)).copy()
        above_mean = _WITHIN_MASK & (mean_val >= _MIN_RAIN)
        alpha_mean = np.where(
            above_mean,
            np.clip(0.80 + 0.15 * certainty, 0.0, 1.0) * _EDGE_WEIGHT,
            0.0,
        )
        rgba_mean[..., 3] = alpha_mean
        buf = io.BytesIO()
        plt.imsave(buf, np.flipud(rgba_mean), format="png")
        (target_dir / f"rain_mean_{ts_str}.png").write_bytes(buf.getvalue())

        # ── Layer 2: p90 — possibility halo ──────────────────────────────────
        rgba_p90 = _CMAP(_NORM(p90_val)).copy()
        # Only show halo where p90 is meaningfully higher than mean class
        above_p90 = _WITHIN_MASK & (p90_val >= _MIN_RAIN)
        # Halo opacity: strong where uncertainty is high (1 - certainty), fades at edges
        halo_strength = np.clip(1.0 - certainty, 0.0, 1.0)
        alpha_p90 = np.where(
            above_p90,
            np.clip(0.20 + 0.30 * halo_strength, 0.0, 1.0) * _EDGE_WEIGHT,
            0.0,
        )
        rgba_p90[..., 3] = alpha_p90
        buf = io.BytesIO()
        plt.imsave(buf, np.flipud(rgba_p90), format="png")
        (target_dir / f"rain_p90_{ts_str}.png").write_bytes(buf.getvalue())

        print(f"  [render] {ts_str}  ({i + 1}/{n})")

    print(f"[render] {n} frames ({n} mean + {n} p90) saved -> {target_dir}")
    return target_dir


def render_from_nc(nc_path: Path) -> Path:
    """
    Load *nc_path*, compute ensemble-mean and p90 hourly diffs from TOT_PREC,
    and call render_all_frames() with Option 1 dual-layer logic.
    """
    ds = xr.open_dataset(nc_path)
    try:
        if np.issubdtype(ds["lead_time"].dtype, np.timedelta64):
            ds["lead_time"] = (ds["lead_time"] / np.timedelta64(1, 'h')).astype(float)
        precip = ds["TOT_PREC"].squeeze("ref_time")                     # (eps, lead, y, x)
        mean_diff = precip.mean("eps").diff("lead_time")                 # colour class
        p90_diff  = precip.quantile(0.9, dim="eps").diff("lead_time")    # opacity
        return render_all_frames(mean_diff, p90_diff, ds.coords["ref_time"].values[0])
    finally:
        ds.close()


def render_demo_nc(nc_path: Path) -> Path:
    """Render the demo NC file into DEMO_RAIN_LAYERS_DIR."""
    ds = xr.open_dataset(nc_path)
    try:
        if np.issubdtype(ds["lead_time"].dtype, np.timedelta64):
            ds["lead_time"] = (ds["lead_time"] / np.timedelta64(1, 'h')).astype(float)
        precip = ds["TOT_PREC"].squeeze("ref_time")
        mean_diff = precip.mean("eps").diff("lead_time")
        p90_diff  = precip.quantile(0.9, dim="eps").diff("lead_time")
        return render_all_frames(mean_diff, p90_diff, ds.coords["ref_time"].values[0],
                                 output_dir=DEMO_RAIN_LAYERS_DIR)
    finally:
        ds.close()


# ---------------------------------------------------------------------------
# FastAPI helpers
# ---------------------------------------------------------------------------

def get_rain_layer_path(time_str: str) -> Path:
    """Return the Path to the pre-rendered mean PNG for the given ISO timestamp."""
    path = RAIN_LAYERS_DIR / _iso_to_mean_filename(time_str)
    if not path.exists():
        raise FileNotFoundError(f"Pre-rendered mean frame not found: {path.name}")
    return path


def get_rain_layer_p90_path(time_str: str) -> Path:
    """Return the Path to the pre-rendered p90 PNG for the given ISO timestamp."""
    path = RAIN_LAYERS_DIR / _iso_to_p90_filename(time_str)
    if not path.exists():
        raise FileNotFoundError(f"Pre-rendered p90 frame not found: {path.name}")
    return path


def list_rain_times() -> list[str]:
    """Return sorted ISO timestamp strings for all available rain PNGs."""
    return [
        _mean_filename_to_iso(f.name)
        for f in sorted(RAIN_LAYERS_DIR.glob("rain_mean_*.png"))
    ]


def get_demo_rain_layer_path(time_str: str) -> Path:
    """Return the Path to the pre-rendered demo mean PNG for the given ISO timestamp."""
    path = DEMO_RAIN_LAYERS_DIR / _iso_to_mean_filename(time_str)
    if not path.exists():
        raise FileNotFoundError(f"Pre-rendered demo mean frame not found: {path.name}")
    return path


def get_demo_rain_layer_p90_path(time_str: str) -> Path:
    """Return the Path to the pre-rendered demo p90 PNG for the given ISO timestamp."""
    path = DEMO_RAIN_LAYERS_DIR / _iso_to_p90_filename(time_str)
    if not path.exists():
        raise FileNotFoundError(f"Pre-rendered demo p90 frame not found: {path.name}")
    return path


def list_demo_rain_times() -> list[str]:
    """Return sorted ISO timestamp strings for all available demo rain PNGs."""
    return [
        _mean_filename_to_iso(f.name)
        for f in sorted(DEMO_RAIN_LAYERS_DIR.glob("rain_mean_*.png"))
    ]
