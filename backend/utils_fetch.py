"""
utils_fetch.py

Fetches ICON-CH1-EPS TOT_PREC from MeteoSwiss OGD using ONLY:
    requests  — HTTP / STAC search
    eccodes   — GRIB2 decoding  (C lib, ARM64 wheel on PyPI / conda-forge)
    eccodes-cosmo-resources-python — ICON grid definitions (pure Python)
    scipy     — nearest-neighbour regridding via KD-tree
    numpy, xarray, netcdf4 — array handling + NetCDF output

No meteodatalab. No eckitlib. No rasterio. Works on ARM64 (Raspberry Pi).

First run downloads + caches:
  - ICON CH1 grid constants (CLAT/CLON) from the STAC collection
  - Precomputed nearest-neighbour indices from ICON → regular lat/lon grid
Both are stored in backend/.fetch_cache/ and reused on subsequent runs.
"""

import re
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# UTF-8 stdout so Unicode characters work on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import eccodes
import numpy as np
import requests
import xarray as xr
from scipy.spatial import cKDTree


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STAC_BASE = "https://data.geo.admin.ch/api/stac/v1"
COLLECTION = "ch.meteoschweiz.ogd-forecasting-icon-ch1"

LON_MIN, LON_MAX = -0.817, 18.183
LAT_MIN, LAT_MAX = 41.183, 51.183
NX, NY = 429, 295
LEAD_HOURS = list(range(34))

TARGET_LONS = np.linspace(LON_MIN, LON_MAX, NX)
TARGET_LATS = np.linspace(LAT_MIN, LAT_MAX, NY)
LON_GRID, LAT_GRID = np.meshgrid(TARGET_LONS, TARGET_LATS)   # (NY, NX)
TARGET_PTS = np.column_stack([LAT_GRID.ravel(), LON_GRID.ravel()])  # (NY*NX, 2)

BACKEND_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BACKEND_DIR / "data" / "NC"
CACHE_DIR  = BACKEND_DIR / ".fetch_cache"

CLAT_CACHE    = CACHE_DIR / "icon_ch1_clat.npy"
CLON_CACHE    = CACHE_DIR / "icon_ch1_clon.npy"
INDICES_CACHE = CACHE_DIR / "icon_ch1_regrid_indices.npy"

SCHEDULED_HOURS = [0, 3, 6, 9, 12, 15, 18, 21]


# ---------------------------------------------------------------------------
# STAC helpers
# ---------------------------------------------------------------------------

def _cutoff_range() -> str:
    """Open-ended datetime range covering the last 48 h (OGD 'latest' logic)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ") + "/.."


def _stac_post_all(body: dict) -> list[dict]:
    """POST /search, follow pagination, return all features."""
    features: list[dict] = []
    url = f"{STAC_BASE}/search"
    while url:
        r = requests.post(url, json=body, timeout=60)
        r.raise_for_status()
        data = r.json()
        features.extend(data.get("features", []))
        url = None
        for link in data.get("links", []):
            if link["rel"] == "next":
                url = link["href"]
                if link.get("merge") and link.get("body"):
                    body = {**body, **link["body"]}
                break
    return features


def get_latest_urls() -> tuple[dict[int, str], str]:
    """
    Query STAC for the latest complete TOT_PREC perturbed run.
    Returns ({lead_hour: signed_grib2_url}, ref_time_str).
    ref_time_str format: 'YYYYMMDDHHMM'
    """
    body = {
        "collections": [COLLECTION],
        "forecast:variable": "TOT_PREC",
        "forecast:perturbed": True,
        "forecast:reference_datetime": _cutoff_range(),
    }
    features = _stac_post_all(body)

    # URL pattern:  icon-ch1-eps-YYYYMMDDHHMM-{lead}-tot_prec-perturb.grib2
    pat = re.compile(r"icon-ch1-eps-(\d{12})-(\d+)-tot_prec")

    url_map: dict[tuple[str, int], str] = {}
    for feat in features:
        for asset in feat["assets"].values():
            m = pat.search(asset["href"])
            if m:
                url_map[(m.group(1), int(m.group(2)))] = asset["href"]

    # Find latest ref_time that has ALL requested lead hours
    by_ref: dict[str, set[int]] = defaultdict(set)
    for ref, lead in url_map:
        by_ref[ref].add(lead)

    required = set(LEAD_HOURS)
    complete = [r for r, leads in by_ref.items() if required.issubset(leads)]
    if not complete:
        raise RuntimeError(
            f"No complete ICON CH1 forecast found with all {len(LEAD_HOURS)} lead times. "
            f"Available ref_times: {sorted(by_ref)}"
        )

    latest = max(complete)
    return {h: url_map[(latest, h)] for h in LEAD_HOURS}, latest


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def _safe_unlink(path: Path) -> None:
    """Delete a temp file, retrying on Windows file-lock from eccodes C lib."""
    for attempt in range(6):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt < 5:
                time.sleep(0.3)


def download_grib(url: str) -> Path:
    """Stream-download a GRIB2 from a signed S3 URL to a temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".grib2", delete=False)
    try:
        with requests.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            for chunk in r.iter_content(1 << 20):  # 1 MB chunks
                tmp.write(chunk)
        tmp.flush()
    finally:
        tmp.close()  # must close before unlink on Windows
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# ICON grid coordinates — read from horizontal constants GRIB2 (no shortName)
# ---------------------------------------------------------------------------

def _get_collection_asset_url(key_fragment: str) -> str:
    """Fetch the STAC collection and return the href for the matching asset."""
    r = requests.get(f"{STAC_BASE}/collections/{COLLECTION}", timeout=30)
    r.raise_for_status()
    assets = r.json().get("assets", {})
    for key, val in assets.items():
        if key_fragment in key:
            return val["href"]
    raise RuntimeError(f"No asset matching '{key_fragment}' found in STAC collection")


def _load_icon_grid_coords() -> tuple[np.ndarray, np.ndarray]:
    """
    Return (clat_deg, clon_deg) for every ICON CH1 native grid point.

    Reads the first two messages from the STAC horizontal_constants GRIB2
    positionally — message 0 = CLAT, message 1 = CLON — using only the
    standard 'values' key, so no COSMO definitions are required.
    Auto-detects degrees vs radians from value range.
    Cached after first download.
    """
    if CLAT_CACHE.exists() and CLON_CACHE.exists():
        return np.load(CLAT_CACHE), np.load(CLON_CACHE)

    print("[grid] Downloading ICON CH1 horizontal grid constants (one-time ~200 MB)…")
    hc_url = _get_collection_asset_url("horizontal_constants")
    tmp = download_grib(hc_url)

    messages: list[np.ndarray] = []
    try:
        with open(tmp, "rb") as f:
            while len(messages) < 2:  # only need first two messages
                gid = eccodes.codes_grib_new_from_file(f)
                if gid is None:
                    break
                try:
                    messages.append(eccodes.codes_get_array(gid, "values").copy())
                except eccodes.CodesInternalError:
                    pass
                finally:
                    eccodes.codes_release(gid)
    finally:
        _safe_unlink(tmp)

    if len(messages) < 2:
        raise RuntimeError(
            f"Expected ≥2 messages in horizontal_constants GRIB2, got {len(messages)}."
        )

    clat, clon = messages[0], messages[1]

    # ICON stores coords in radians if abs-max ≤ π; convert to degrees
    if np.max(np.abs(clat)) <= np.pi + 0.01:
        clat = np.degrees(clat)
        clon = np.degrees(clon)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(CLAT_CACHE, clat)
    np.save(CLON_CACHE, clon)
    print(f"[grid] Cached {len(clat):,} ICON grid points → {CACHE_DIR}")
    return clat, clon


# ---------------------------------------------------------------------------
# Regridding  (nearest-neighbour, KD-tree)
# ---------------------------------------------------------------------------

def _load_regrid_indices(clat: np.ndarray, clon: np.ndarray) -> np.ndarray:
    """
    Precomputed flat index array: for each target pixel (NY*NX,), which
    ICON native grid point is nearest. Cached after first build.
    """
    if INDICES_CACHE.exists():
        return np.load(INDICES_CACHE)

    print("[regrid] Building KD-tree (one-time, may take ~1 min on Pi)…")
    tree = cKDTree(np.column_stack([clat, clon]))
    _, indices = tree.query(TARGET_PTS, workers=-1)  # all CPU cores
    indices = indices.astype(np.int32)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDICES_CACHE, indices)
    print(f"[regrid] Indices cached → {INDICES_CACHE}")
    return indices


def regrid(values: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Remap flat ICON values array to (NY, NX) regular lat/lon grid."""
    return values[indices].reshape(NY, NX)


# ---------------------------------------------------------------------------
# GRIB2 reading
# ---------------------------------------------------------------------------

def read_grib_data(path: Path) -> dict[int, np.ndarray]:
    """
    Read all GRIB2 messages from a perturbed ICON file.
    Returns {perturbation_number: flat_values_array}.
    """
    members: dict[int, np.ndarray] = {}
    with open(path, "rb") as f:
        while True:
            gid = eccodes.codes_grib_new_from_file(f)
            if gid is None:
                break
            try:
                mem = eccodes.codes_get(gid, "perturbationNumber", ktype=int)
            except eccodes.CodesInternalError:
                mem = 0
            members[mem] = eccodes.codes_get_array(gid, "values").copy()
            eccodes.codes_release(gid)
    return members


# ---------------------------------------------------------------------------
# Main fetch
# ---------------------------------------------------------------------------

def fetch_and_save(output_dir: Path = OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Grid setup (cached after first run)
    clat, clon = _load_icon_grid_coords()
    indices = _load_regrid_indices(clat, clon)

    # 2. STAC query
    print("[fetch] Querying STAC for latest TOT_PREC…")
    url_map, ref_str = get_latest_urls()
    ref_dt = datetime.strptime(ref_str, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    print(f"[fetch] Reference time: {ref_dt.isoformat()}  —  {len(LEAD_HOURS)} lead times")

    # 3. Download + decode each lead time
    lead_data: dict[int, dict[int, np.ndarray]] = {}  # {lead: {member: (NY,NX)}}
    all_members: set[int] | None = None

    for h in LEAD_HOURS:
        tmp = download_grib(url_map[h])
        try:
            raw = read_grib_data(tmp)
        finally:
            _safe_unlink(tmp)

        if all_members is None:
            all_members = set(raw.keys())

        lead_data[h] = {mem: regrid(vals, indices) for mem, vals in raw.items()}
        print(f"  ✓ +{h:02d}h  ({len(raw)} members)")

    # 4. Assemble DataArray  shape: (eps, ref_time=1, lead_time, y, x)
    member_ids = sorted(all_members)
    n_eps  = len(member_ids)
    n_lead = len(LEAD_HOURS)

    data = np.empty((n_eps, 1, n_lead, NY, NX), dtype=np.float32)
    for li, h in enumerate(LEAD_HOURS):
        for ei, mem in enumerate(member_ids):
            data[ei, 0, li] = lead_data[h][mem]

    # lead_time stored as float hours so da.interp(lead_time=float_hours) works directly
    da_all = xr.DataArray(
        data,
        dims=["eps", "ref_time", "lead_time", "y", "x"],
        coords={
            "eps":       member_ids,
            "ref_time":  [np.datetime64(ref_dt.replace(tzinfo=None), "ns")],
            "lead_time": [float(h) for h in LEAD_HOURS],  # float hours
            "lat": (["y", "x"], LAT_GRID.astype(np.float32)),
            "lon": (["y", "x"], LON_GRID.astype(np.float32)),
        },
        name="TOT_PREC",
        attrs={"long_name": "Total precipitation (cumulative)", "units": "mm"},
    )

    # 5. Hourly rain from ensemble mean
    mean_precip = da_all.mean("eps").squeeze("ref_time")      # (lead_time, y, x)
    hourly_rain = mean_precip.diff("lead_time")                # (lead_time=33, y, x)
    hourly_rain.values = np.where(
        hourly_rain.values < 0.01, 0.0, np.round(hourly_rain.values, 2)
    )
    hourly_rain.attrs = {
        "long_name": "Hourly precipitation (ensemble mean)",
        "units": "mm/m2",
    }

    # 6. Save with Unix-timestamp filename
    ts = int(datetime.now(timezone.utc).timestamp())
    output_file = output_dir / f"{ts}.nc"
    ds = xr.Dataset({"TOT_PREC": da_all, "hourly_rain": hourly_rain})
    ds.to_netcdf(output_file)
    ds.close()
    print(f"[fetch] Saved → {output_file}")
    

    # 7. Publish fresh data to GeoServer
    try:
        from utils_geoserver import publish_nc
        publish_nc(output_file)
    except Exception as e:
        print(f"[fetch] GeoServer publish skipped: {e}")

    return output_file

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def check_fetch_on_startup():
    """Fetch immediately if newest .nc predates the last scheduled update."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    latest_scheduled = max(
        (now.replace(hour=h, minute=5, second=0, microsecond=0)
         for h in SCHEDULED_HOURS
         if now.replace(hour=h, minute=5, second=0, microsecond=0) <= now),
        default=None,
    )

    nc_files = list(OUTPUT_DIR.glob("*.nc"))
    needs_fetch = True
    if nc_files and latest_scheduled:
        newest_mtime = max(f.stat().st_mtime for f in nc_files)
        needs_fetch = newest_mtime < latest_scheduled.timestamp()

    ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
    if needs_fetch:
        print(f"[{ts}] Data outdated — fetching…")
        fetch_and_save()
    else:
        print(f"[{ts}] Data is up-to-date")


def scheduler_loop():
    """Block forever, fetch at 00:05, 03:05, 06:05, …, 21:05 UTC."""
    while True:
        now = datetime.now(timezone.utc)
        next_times = [
            now.replace(hour=h, minute=5, second=0, microsecond=0)
            + (timedelta(days=1)
               if now.replace(hour=h, minute=5, second=0, microsecond=0) <= now
               else timedelta(0))
            for h in SCHEDULED_HOURS
        ]
        nxt = min(next_times)
        wait = (nxt - datetime.now(timezone.utc)).total_seconds()
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] "
              f"Next fetch at {nxt.strftime('%H:%M UTC')}")
        time.sleep(max(wait, 1))
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] Fetching…")
        fetch_and_save()


if __name__ == "__main__":
    check_fetch_on_startup()
    scheduler_loop()
