"""
utils_fetch.py

Fetches ICON-CH1-EPS TOT_PREC from MeteoSwiss OGD using ONLY:
    requests  ??? HTTP / STAC search
    eccodes   ??? GRIB2 decoding  (C lib, ARM64 wheel on PyPI / conda-forge)
    eccodes-cosmo-resources-python ??? ICON grid definitions (pure Python)
    scipy     ??? nearest-neighbour regridding via KD-tree
    numpy, xarray, netcdf4 ??? array handling + NetCDF output

No meteodatalab. No eckitlib. No rasterio. Works on ARM64 (Raspberry Pi).

First run downloads + caches:
  - ICON CH1 grid constants (CLAT/CLON) from the STAC collection
  - Precomputed nearest-neighbour indices from ICON ??? regular lat/lon grid
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
    print(f"[fetch] All ref_times with TOT_PREC hits: {sorted(by_ref.keys())}")
    print(f"[fetch] Complete runs (all {len(LEAD_HOURS)} leads): {sorted(complete)}")
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
# ICON grid coordinates ??? read from horizontal constants GRIB2 (no shortName)
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

    Scans all messages in the horizontal_constants GRIB2 and identifies
    CLAT/CLON by their value content (Europe lat/lon ranges + high uniqueness),
    not by message position.  This is robust across eccodes versions and
    architectures (ARM64 vs x86).  Cache is validated on every load and
    auto-deleted if corrupt.
    """
    def _validate(clat: np.ndarray, clon: np.ndarray) -> bool:
        """True if arrays look like real ICON CH1 Europe coordinates."""
        return (
            len(clat) > 100_000
            and float(clat.min()) >= 35.0
            and float(clat.max()) <= 60.0
            and float(clon.min()) >= -15.0
            and float(clon.max()) <= 25.0
            and len(np.unique(clat.round(2))) > 100
        )

    def _to_degrees(arr: np.ndarray) -> np.ndarray:
        """Convert radians to degrees if values are in radian range."""
        if np.max(np.abs(arr)) <= np.pi + 0.01:
            return np.degrees(arr)
        return arr

    def _looks_like_lat(arr: np.ndarray) -> bool:
        # ICON CH1 lat domain: ~42–51 N. Require min >= 35 to reject fields
        # that start near 0 (corrupted/wrong fields), and use a low uniqueness
        # threshold because the regional domain has < ~900 unique values at
        # 0.01 deg precision (range only ~9 deg).
        d = _to_degrees(arr)
        return (
            len(d) > 100_000
            and float(d.min()) >= 35.0
            and float(d.max()) <= 60.0
            and len(np.unique(d.round(2))) > 100
        )

    def _looks_like_lon(arr: np.ndarray) -> bool:
        # ICON CH1 lon domain: ~-1 to 18 E. Require max <= 25 to reject
        # fields with wildly wrong values (max=254,392 on corrupted ARM64 cache).
        d = _to_degrees(arr)
        return (
            len(d) > 100_000
            and float(d.min()) >= -15.0
            and float(d.max()) <= 25.0
            and len(np.unique(d.round(2))) > 100
        )

    if CLAT_CACHE.exists() and CLON_CACHE.exists():
        clat, clon = np.load(CLAT_CACHE), np.load(CLON_CACHE)
        if _validate(clat, clon):
            print(f"[grid] Cache loaded: {len(clat):,} pts  "
                  f"lat=[{clat.min():.3f}..{clat.max():.3f}]  "
                  f"lon=[{clon.min():.3f}..{clon.max():.3f}]")
            return clat, clon
        print(f"[grid] Cache validation FAILED "
              f"(lat mean={clat.mean():.2f}, lon mean={clon.mean():.2f}, "
              f"unique lat={len(np.unique(clat.round(2)))}) -- rebuilding from GRIB2")
        CLAT_CACHE.unlink(missing_ok=True)
        CLON_CACHE.unlink(missing_ok=True)
        INDICES_CACHE.unlink(missing_ok=True)

    print("[grid] Downloading ICON CH1 horizontal grid constants (one-time ~200 MB)???")
    hc_url = _get_collection_asset_url("horizontal_constants")
    tmp = download_grib(hc_url)

    # Scan ALL messages; identify CLAT/CLON by paramId first (most reliable),
    # then fall back to value-range detection.
    # Known MeteoSwiss ICON CH1 paramIds: 250003 = CLAT, 250004 = CLON.
    _CLAT_PARAM_IDS = {250003}
    _CLON_PARAM_IDS = {250004}

    clat_candidate: np.ndarray | None = None
    clon_candidate: np.ndarray | None = None
    try:
        with open(tmp, "rb") as f:
            msg_idx = 0
            while True:
                gid = eccodes.codes_grib_new_from_file(f)
                if gid is None:
                    break
                try:
                    # np.asarray() ensures plain ndarray even if eccodes returns masked
                    vals = np.asarray(eccodes.codes_get_array(gid, "values")).copy()
                    try:
                        param = eccodes.codes_get(gid, "paramId")
                    except Exception:
                        param = "?"
                    d = _to_degrees(vals)
                    n_unique = len(np.unique(d.round(2)))

                    # --- Primary: identify by known paramId ---
                    by_id = False
                    if clat_candidate is None and param in _CLAT_PARAM_IDS:
                        clat_candidate = d
                        by_id = True
                        print(f"[grid] msg {msg_idx} (paramId={param}): "
                              f"CLAT by paramId  mean={d.mean():.3f} unique={n_unique:,}")
                    elif clon_candidate is None and param in _CLON_PARAM_IDS:
                        clon_candidate = d
                        by_id = True
                        print(f"[grid] msg {msg_idx} (paramId={param}): "
                              f"CLON by paramId  mean={d.mean():.3f} unique={n_unique:,}")

                    if not by_id:
                        # --- Fallback: identify by value range ---
                        if clat_candidate is None and _looks_like_lat(d):
                            clat_candidate = d
                            print(f"[grid] msg {msg_idx} (paramId={param}): "
                                  f"CLAT by range  mean={d.mean():.3f} unique={n_unique:,}")
                        elif clon_candidate is None and _looks_like_lon(d):
                            clon_candidate = d
                            print(f"[grid] msg {msg_idx} (paramId={param}): "
                                  f"CLON by range  mean={d.mean():.3f} unique={n_unique:,}")
                        else:
                            print(f"[grid] msg {msg_idx} (paramId={param}): skipped "
                                  f"size={len(vals)} min={d.min():.4f} max={d.max():.4f} "
                                  f"unique={n_unique}")
                except eccodes.CodesInternalError:
                    print(f"[grid] msg {msg_idx}: CodesInternalError (skipped)")
                finally:
                    eccodes.codes_release(gid)
                msg_idx += 1
                if clat_candidate is not None and clon_candidate is not None:
                    break  # found both — no need to read further
    finally:
        _safe_unlink(tmp)

    if clat_candidate is None or clon_candidate is None:
        raise RuntimeError(
            f"Could not identify CLAT/CLON in horizontal_constants GRIB2 "
            f"(clat={'found' if clat_candidate is not None else 'MISSING'}, "
            f"clon={'found' if clon_candidate is not None else 'MISSING'}). "
            "Check eccodes installation."
        )

    clat, clon = clat_candidate, clon_candidate
    if not _validate(clat, clon):
        raise RuntimeError(
            f"CLAT/CLON candidates failed final validation: "
            f"lat mean={clat.mean():.2f}, lon mean={clon.mean():.2f}"
        )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(CLAT_CACHE, clat)
    np.save(CLON_CACHE, clon)
    print(f"[grid] Cached {len(clat):,} ICON grid points -> {CACHE_DIR}")
    return clat, clon


# ---------------------------------------------------------------------------
# Regridding  (nearest-neighbour, KD-tree)
# ---------------------------------------------------------------------------

def _load_regrid_indices(clat: np.ndarray, clon: np.ndarray) -> np.ndarray:
    """
    Precomputed flat index array: for each target pixel (NY*NX,), which
    ICON native grid point is nearest. Cached after first build.
    Cache is validated on load; a corrupt cache (too few unique values)
    is deleted and rebuilt automatically.
    """
    if INDICES_CACHE.exists():
        indices = np.load(INDICES_CACHE)
        unique_idx = len(np.unique(indices))
        print(f"[regrid] Cache loaded: {len(indices):,} entries  "
              f"range=[{indices.min()}..{indices.max()}]  "
              f"unique={unique_idx:,}")
        if unique_idx >= 1000:
            return indices
        print(f"[regrid] Cache invalid (only {unique_idx} unique values) -- rebuilding...")
        INDICES_CACHE.unlink(missing_ok=True)

    print("[regrid] Building KD-tree (one-time, may take ~1 min on Pi)...")
    tree = cKDTree(np.column_stack([clat, clon]))
    _, indices = tree.query(TARGET_PTS, workers=-1)  # all CPU cores
    indices = indices.astype(np.int32)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDICES_CACHE, indices)
    print(f"[regrid] Indices cached ??? {INDICES_CACHE}")
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
    print("[fetch] Querying STAC for latest TOT_PREC???")
    url_map, ref_str = get_latest_urls()
    ref_dt = datetime.strptime(ref_str, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    print(f"[fetch] Reference time: {ref_dt.isoformat()}  ???  {len(LEAD_HOURS)} lead times")

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
        print(f"  ??? +{h:02d}h  ({len(raw)} members)")

    # ── debug: verify regrid output has spatial variation ──────────────────
    _h_sample  = LEAD_HOURS[len(LEAD_HOURS) // 2]
    _m_sample  = sorted(lead_data[_h_sample].keys())[0]
    _rg_sample = lead_data[_h_sample][_m_sample]
    print(f"[debug] regrid sample h={_h_sample} mem={_m_sample}: "
          f"min={_rg_sample.min():.4f} max={_rg_sample.max():.4f} "
          f"std={_rg_sample.std():.6f} "
          f"unique_rounded={len(np.unique(_rg_sample.round(3))):,}")
    if _rg_sample.std() < 1e-6:
        print("[debug] *** REGRID OUTPUT IS SPATIALLY UNIFORM — "
              "run python debug_nc.py to inspect cache files!")

    # 4. Assemble DataArray  shape: (eps, ref_time=1, lead_time, y, x)
    member_ids = sorted(all_members)
    n_eps  = len(member_ids)
    n_lead = len(LEAD_HOURS)

    data = np.empty((n_eps, 1, n_lead, NY, NX), dtype=np.float32)
    for li, h in enumerate(LEAD_HOURS):
        for ei, mem in enumerate(member_ids):
            data[ei, 0, li] = lead_data[h][mem]

    # ── debug: check assembled data has spatial + ensemble variation ────────
    _li_mid  = n_lead // 2
    _f0      = data[0, 0, _li_mid]
    _f_last  = data[-1, 0, _li_mid]
    _eps_diff = float(np.abs(_f0 - _f_last).max())
    print(f"[debug] data shape={data.shape} dtype={data.dtype}")
    print(f"[debug] eps[0] lt_idx={_li_mid}: "
          f"min={_f0.min():.4f} max={_f0.max():.4f} std={_f0.std():.6f}")
    print(f"[debug] max |eps[0] - eps[-1]| at lt_idx={_li_mid}: {_eps_diff:.6f}"
          + ("  *** ALL EPS IDENTICAL ***" if _eps_diff < 1e-6 else ""))

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

    # 5b. Hourly p90 — computed directly from the raw numpy array while it is still
    #     in memory.  axis=0 is unambiguously eps here (shape: n_eps, n_lead, NY, NX),
    #     so there is no architecture-specific NC-reading involved.  Storing the result
    #     in the NC file lets render_from_nc skip all heavy computation entirely.
    arr_eps    = data[:, 0, :, :, :]              # view: (eps, lead_time, y, x)
    arr_sorted = np.sort(arr_eps, axis=0)         # sorted copy along eps axis
    p90_idx    = min(int(np.floor(0.9 * n_eps)), n_eps - 1)
    p90_da     = xr.DataArray(
        arr_sorted[p90_idx],                      # shape (lead_time, y, x), float32
        dims=["lead_time", "y", "x"],
        coords={
            "lead_time": [float(h) for h in LEAD_HOURS],
            "lat": (["y", "x"], LAT_GRID.astype(np.float32)),
            "lon": (["y", "x"], LON_GRID.astype(np.float32)),
        },
    )
    hourly_rain_p90 = p90_da.diff("lead_time")    # (lead_time=33, y, x)
    hourly_rain_p90.values = np.where(
        hourly_rain_p90.values < 0.01, 0.0, np.round(hourly_rain_p90.values, 2)
    )
    hourly_rain_p90.attrs = {
        "long_name": "Hourly precipitation (90th percentile)",
        "units": "mm/m2",
    }

    # ── debug: spatial check before writing NC ────────────────────────────
    for _dname, _da in (("hourly_rain", hourly_rain), ("hourly_rain_p90", hourly_rain_p90)):
        _dvals = np.nan_to_num(_da.values, nan=0.0)
        _pk    = int(_dvals.reshape(_dvals.shape[0], -1).max(axis=1).argmax())
        _pf    = _dvals[_pk]
        print(f"[debug] {_dname} dims={_da.dims} shape={_da.shape}  "
              f"peak lt_idx={_pk}: min={_pf.min():.4f} max={_pf.max():.4f} "
              f"std={_pf.std():.6f} nonzero={int((_pf > 0.01).sum())}/{_pf.size}")

    # 6. Save with ref_time as Unix-timestamp filename (not download time).
    # The routing endpoint derives lead_hours = (departure_unix - filename_stem) / 3600,
    # so the stem must be the forecast reference time, not the wall-clock download time.
    ts = int(ref_dt.timestamp())
    output_file = output_dir / f"{ts}.nc"
    ds = xr.Dataset({"TOT_PREC": da_all, "hourly_rain": hourly_rain, "hourly_rain_p90": hourly_rain_p90})
    ds.to_netcdf(output_file)
    ds.close()
    print(f"[fetch] Saved -> {output_file}")

    # 6b. Render PNG overlays for frontend Leaflet map
    try:
        from utils_render import render_from_nc
        render_from_nc(output_file)
    except Exception as e:
        print(f"[fetch] Render PNGs skipped or failed: {e}")

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
        # Even if .nc is fresh, PNGs may be stale (e.g. after a restart).
        # Re-render if rain_layers is missing or older than the newest .nc.
        try:
            from utils_render import render_from_nc, RAIN_LAYERS_DIR
            nc_files = list(OUTPUT_DIR.glob("*.nc"))
            if nc_files:
                newest_nc = max(nc_files, key=lambda f: f.stat().st_mtime)
                png_files = list(RAIN_LAYERS_DIR.glob("rain_*.png")) if RAIN_LAYERS_DIR.exists() else []
                needs_render = (
                    not png_files
                    or max(f.stat().st_mtime for f in png_files) < newest_nc.stat().st_mtime
                )
                if needs_render:
                    print(f"[{ts}] PNGs missing or stale — re-rendering from {newest_nc.name}")
                    render_from_nc(newest_nc)
        except Exception as e:
            print(f"[{ts}] Re-render check failed: {e}")


def scheduler_loop():
    """Block forever, fetch at 00:05, 03:05, 06:05, ???, 21:05 UTC."""
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
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M UTC')}] Fetching???")
        fetch_and_save()


if __name__ == "__main__":
    check_fetch_on_startup()
    scheduler_loop()
