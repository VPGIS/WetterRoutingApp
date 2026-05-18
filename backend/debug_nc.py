#!/usr/bin/env python3
"""
debug_nc.py  —  inspect VPRouting cache and NC files to diagnose regrid/render issues.

Run on the Pi (or anywhere) from the backend/ directory:

    python debug_nc.py               # newest NC in data/NC/ + all caches
    python debug_nc.py path/to.nc    # specific NC file + all caches

Output goes to stdout — pipe through `tee` to save a copy:
    python debug_nc.py | tee /tmp/debug_out.txt
"""

import sys
import numpy as np
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
NC_DIR      = BACKEND_DIR / "data" / "NC"
CACHE_DIR   = BACKEND_DIR / ".fetch_cache"
CLAT_CACHE  = CACHE_DIR / "icon_ch1_clat.npy"
CLON_CACHE  = CACHE_DIR / "icon_ch1_clon.npy"
IDX_CACHE   = CACHE_DIR / "icon_ch1_regrid_indices.npy"

SEP = "=" * 72


def _text_map(frame2d: np.ndarray, rows: int = 12, cols: int = 40) -> str:
    """Downsample a 2-D float array and render as a tiny ASCII map."""
    ny, nx = frame2d.shape
    sy = max(1, ny // rows)
    sx = max(1, nx // cols)
    sample = frame2d[::sy, ::sx]
    lines = []
    for row in sample:
        lines.append("".join(
            "." if v < 0.01 else
            "+" if v < 0.6  else
            "#" if v < 2.0  else
            "@"
            for v in row
        ))
    return "\n".join("  " + l for l in lines)


# ---------------------------------------------------------------------------
# 1.  Cache files
# ---------------------------------------------------------------------------
def check_caches():
    print(SEP)
    print("CACHE FILES")
    print(SEP)

    for label, path in [("CLAT", CLAT_CACHE), ("CLON", CLON_CACHE), ("INDICES", IDX_CACHE)]:
        if not path.exists():
            print(f"  {label}: MISSING  ({path})")
            continue
        arr = np.load(path)
        print(f"  {label}: {path.name}  shape={arr.shape}  dtype={arr.dtype}")
        if arr.ndim == 1:
            print(f"    min={arr.min():.6f}  max={arr.max():.6f}  "
                  f"mean={arr.mean():.6f}  std={arr.std():.6f}")
            unique = len(np.unique(arr))
            print(f"    unique values: {unique:,}  (out of {len(arr):,} entries)")
            if label == "INDICES":
                if unique < 1000:
                    print(f"    *** WARNING: only {unique} unique index values — "
                          "most pixels map to the same ICON grid point!")
                    print(f"    *** This means regrid output will be spatially UNIFORM.")
                    print(f"    *** DELETE .fetch_cache/ and re-fetch to rebuild.")
                else:
                    print(f"    OK: {unique:,} unique indices — regrid mapping looks healthy")
                # Show distribution of first 20 indices
                print(f"    First 10 indices: {arr[:10].tolist()}")
                print(f"    Last  10 indices: {arr[-10:].tolist()}")
            elif label in ("CLAT", "CLON"):
                expected_range = (40, 52) if label == "CLAT" else (-5, 22)
                lo, hi = expected_range
                if arr.min() < lo - 5 or arr.max() > hi + 5:
                    print(f"    *** WARNING: values outside expected range [{lo}..{hi}]°")
                    if arr.max() < 2.0:
                        print(f"    *** Values look like RADIANS — "
                              "cache was built with wrong unit conversion!")
                        print(f"    *** DELETE .fetch_cache/ and re-fetch to rebuild.")
                else:
                    print(f"    OK: values in expected degree range [{lo}..{hi}]")


# ---------------------------------------------------------------------------
# 2.  NC file
# ---------------------------------------------------------------------------
def check_nc(nc_path: Path):
    print()
    print(SEP)
    print(f"NC FILE: {nc_path}")
    print(SEP)
    print(f"  size: {nc_path.stat().st_size / 1e6:.1f} MB")

    try:
        import xarray as xr
    except ImportError:
        print("  xarray not available — skipping NC inspection")
        return

    ds = xr.open_dataset(nc_path)
    try:
        # Backend info
        store_cls = type(ds._store).__name__ if hasattr(ds, "_store") else "unknown"
        print(f"  xarray backend store: {store_cls}")

        # Coordinates
        print("\n  -- Coordinates --")
        for k, v in ds.coords.items():
            preview = ""
            if v.ndim == 1 and len(v) <= 6:
                preview = f"  values={v.values.tolist()}"
            elif v.ndim == 1:
                preview = f"  [{v.values[0]!r} .. {v.values[-1]!r}]"
            print(f"    {k}: dtype={v.dtype} shape={v.shape}{preview}")

        # lead_time sanity
        lt = ds.coords.get("lead_time")
        if lt is not None and np.issubdtype(lt.dtype, np.timedelta64):
            print("    *** lead_time is timedelta64 — legacy format, will be converted")

        # Variables
        print("\n  -- Variables --")
        for name, var in ds.data_vars.items():
            print(f"    {name}: dims={var.dims}  shape={var.shape}  dtype={var.dtype}")

        # Per-variable spatial statistics
        for var_name in ("hourly_rain", "hourly_rain_p90"):
            if var_name not in ds:
                print(f"\n  -- {var_name}: NOT PRESENT (legacy NC) --")
                continue
            da  = ds[var_name]
            arr = np.nan_to_num(da.values, nan=0.0)
            if arr.ndim < 2:
                print(f"\n  -- {var_name}: unexpected ndim={arr.ndim} --")
                continue

            # Flatten non-spatial axes to find lead-time index with max rain
            flat = arr.reshape(arr.shape[0], -1) if arr.ndim == 3 else arr.reshape(1, -1)
            peak_lt = int(flat.max(axis=1).argmax())
            frame   = flat[peak_lt].reshape(arr.shape[-2], arr.shape[-1]) if arr.ndim == 3 \
                      else flat[0].reshape(arr.shape[-2], arr.shape[-1])

            print(f"\n  -- {var_name} (peak frame lt_idx={peak_lt}) --")
            print(f"    shape={frame.shape}  min={frame.min():.4f}  "
                  f"max={frame.max():.4f}  mean={frame.mean():.4f}  "
                  f"std={frame.std():.6f}")
            nonzero = int((frame > 0.01).sum())
            print(f"    nonzero pixels: {nonzero:,}/{frame.size:,}  "
                  f"unique_rounded: {len(np.unique(frame.round(3))):,}")

            if frame.std() < 1e-4 and frame.mean() > 0.01:
                print(f"    *** SPATIALLY UNIFORM — data is not varying across the grid!")
                print(f"    *** Root cause is almost certainly a bad INDICES_CACHE.")
            else:
                print(f"    OK: spatial variation detected (std={frame.std():.4f})")

            print("    ASCII map (. <0.01  + <0.6mm/h  # <2mm/h  @ ≥2mm/h):")
            print(_text_map(frame))

        # TOT_PREC ensemble check
        if "TOT_PREC" in ds:
            tp = ds["TOT_PREC"]
            print(f"\n  -- TOT_PREC ensemble spread check --")
            print(f"    dims={tp.dims}  shape={tp.shape}")
            if "eps" in tp.dims:
                arr_tp = tp.squeeze("ref_time").values   # (eps, lead, y, x)
                mid_li = arr_tp.shape[1] // 2
                # max absolute difference between any two eps members at the mid lead time
                frame0 = arr_tp[0, mid_li]
                frame_last = arr_tp[-1, mid_li]
                diff_max  = float(np.abs(frame0 - frame_last).max())
                diff_mean = float(np.abs(frame0 - frame_last).mean())
                print(f"    eps[0] vs eps[-1] at lt_idx={mid_li}: "
                      f"max_diff={diff_max:.6f}  mean_diff={diff_mean:.6f}")
                if diff_max < 1e-6:
                    print("    *** ALL EPS MEMBERS ARE IDENTICAL — "
                          "ensemble data has zero spread!")
                    print("    *** Confirms regrid is mapping all pixels to same point.")
                else:
                    print("    OK: ensemble members differ — spread is non-zero")
                print(f"    eps[0] lt_idx={mid_li} spatial std: "
                      f"{frame0.std():.6f}  (0 = spatially uniform)")
            else:
                print("    'eps' dimension not found in TOT_PREC")

    finally:
        ds.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    check_caches()

    if len(sys.argv) > 1:
        nc_path = Path(sys.argv[1])
    else:
        nc_files = sorted(NC_DIR.glob("*.nc"))
        if not nc_files:
            print(f"\nNo NC files found in {NC_DIR}")
            sys.exit(0)
        nc_path = max(nc_files, key=lambda f: f.stat().st_mtime)
        print(f"\n(No NC path given — using newest: {nc_path.name})")

    check_nc(nc_path)
    print()
    print(SEP)
    print("Done.")
