"""
render.py
Fills rain.html with real frame data produced by fetch_data.py.

Usage
-----
    python render.py                           # uses total_0-33.nc
    python render.py --demo                    # uses RAINY_DATA_DEMO_icon_ch1_TOT_PREC_all_lead_times.nc
    python render.py --nc /path/to/file.nc     # explicit NetCDF path
    python render.py --out /tmp/rain.html      # explicit output path
    python render.py --demo --out demo_out.html

From a notebook
---------------
    from render import build_html
    html_str = build_html(frames, labels, global_max, run_label)
    with open("rain_out.html", "w") as f:
        f.write(html_str)
"""

import argparse
import base64
import io
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

# ── Paths (all resolved relative to this script's location) ──────────────────
_HERE = Path(__file__).resolve().parent
ROOT  = _HERE.parent   # one level up: meteodata-lab-env/

TEMPLATE = _HERE / "rain.html"
NC_FILE  = ROOT / "total_0-33.nc"
NC_DEMO  = ROOT / "RAINY_DATA_DEMO_icon_ch1_TOT_PREC_all_lead_times.nc"
OUT_FILE = _HERE / "rain_out.html"

# ── Map / mask constants ──────────────────────────────────────────────────────
CH_LAT, CH_LON = 46.8, 8.2
RADIUS_KM = 350


# ── Helpers ───────────────────────────────────────────────────────────────────

def _haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat / 2) ** 2
         + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2)
    return R * 2 * np.arcsin(np.sqrt(a))


def render_frames(hourly_rain: "xr.DataArray") -> tuple[list[str], float]:
    """
    Convert each lead-time slice to a base64 PNG data-URI.
    Returns (frames, global_max).
    """
    lons = np.linspace(-0.817, 18.183, 429)
    lats = np.linspace(41.183, 51.183, 295)
    LON, LAT = np.meshgrid(lons, lats)
    within_mask = _haversine(LAT, LON, CH_LAT, CH_LON) <= RADIUS_KM

    global_max = float(hourly_rain.max())
    norm = mcolors.Normalize(vmin=0, vmax=max(global_max, 0.1))
    cmap = plt.cm.YlOrRd

    frames = []
    n = hourly_rain.shape[0]
    for h in range(n):
        rain_h      = hourly_rain.isel(lead_time=h).values
        rain_masked = np.where(within_mask, rain_h, np.nan)
        rgba        = cmap(norm(np.nan_to_num(rain_masked)))
        rgba[..., 3] = np.where(within_mask & (rain_masked >= 0.01), 1.0, 0.0)
        buf = io.BytesIO()
        plt.imsave(buf, np.flipud(rgba), format="png")
        buf.seek(0)
        frames.append("data:image/png;base64," + base64.b64encode(buf.read()).decode())
        print(f"  rendered +{h+1:02d}h")

    return frames, global_max


def build_labels(ref_time: pd.Timestamp, n_hours: int) -> list[str]:
    labels = []
    for h in range(1, n_hours + 1):
        valid = ref_time + pd.Timedelta(hours=h)
        labels.append(f"+{h:02d}h · {valid.strftime('%a %d %b %H:%M')} UTC")
    return labels


def build_html(
    frames: list[str],
    labels: list[str],
    global_max: float,
    run_label: str,
    template_path: Path = TEMPLATE,
) -> str:
    """Return the filled HTML string (does not write to disk)."""
    template = template_path.read_text()
    frames_js = "[" + ",".join(f'"{f}"' for f in frames) + "]"
    labels_js = "[" + ",".join(f'"{l}"' for l in labels) + "]"
    return (
        template
        .replace("{{FRAMES_JS}}",  frames_js)
        .replace("{{LABELS_JS}}",  labels_js)
        .replace("{{GLOBAL_MAX}}", str(round(global_max, 2)))
        .replace("{{RUN_LABEL}}",  run_label)
    )


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Render rain.html from NetCDF")
    parser.add_argument(
        "--demo",
        action="store_true",
        help=f"Use the demo NetCDF ({NC_DEMO.name})",
    )
    parser.add_argument(
        "--nc",
        default=None,
        help="Path to NetCDF file (overrides --demo and the default)",
    )
    parser.add_argument(
        "--out",
        default=str(OUT_FILE),
        help="Output HTML path (default: rain_out.html next to this script)",
    )
    args = parser.parse_args()

    # Resolve which .nc to use: --nc > --demo > default
    if args.nc:
        nc_path = Path(args.nc)
    elif args.demo:
        nc_path = NC_DEMO
        print("🟡 DEMO mode — using", nc_path.name)
    else:
        nc_path = NC_FILE

    print(f"Opening {nc_path} …")
    ds = xr.open_dataset(nc_path)
    hourly_rain = ds["hourly_rain"]
    ref_time    = pd.to_datetime(ds["ref_time"].values[0])
    run_label   = ref_time.strftime("%Y-%m-%d %H:%M UTC")
    if args.demo:
        run_label = "[DEMO] " + run_label
    print(f"Model run: {run_label}")

    frames, global_max = render_frames(hourly_rain)
    labels = build_labels(ref_time, len(frames))

    print(f"\nAll {len(frames)} frames ready. Global max: {global_max:.2f} mm/m²")

    html = build_html(frames, labels, global_max, run_label)
    out_path = Path(args.out)
    out_path.write_text(html)
    print(f"Saved → {out_path}")


if __name__ == "__main__":
    main()
