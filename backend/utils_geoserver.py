"""
utils_geoserver.py

Publishes the latest hourly_rain NetCDF to GeoServer as a WMS layer.
Fully idempotent: safe to call on every fetch and on uvicorn startup.
Creates what is missing, updates what exists, skips what is already correct.
"""
import glob
import subprocess
import time
import requests
from pathlib import Path

GS_URL = "http://localhost:8080/geoserver"
AUTH   = ("admin", "geoserver")
WS     = "vprouting"
STORE  = "rain_forecast"
LAYER  = "hourly_rain"

BACKEND_DIR = Path(__file__).resolve().parent
NC_DIR      = BACKEND_DIR / "data" / "NC"

# Path to GeoServer startup script on the Raspberry Pi
GS_STARTUP       = Path("/home/calgon/geoserver/bin/startup.sh")
GS_STARTUP_WAIT  = 60   # max seconds to wait for GeoServer to come up

# SLD for rain_blue style (no ChannelSelection - works reliably with NetCDF)
# High-contrast debug palette: any value > 0.01 shows solid red/orange/yellow.
# Once rendering is confirmed, swap back to the subtle blue ramp.
RAIN_BLUE_SLD = """\
<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xmlns="http://www.opengis.net/sld">
  <NamedLayer><Name>rain_blue</Name>
  <UserStyle><FeatureTypeStyle><Rule>
  <RasterSymbolizer>
    <Opacity>1.0</Opacity>
    <ColorMap type="ramp">
      <ColorMapEntry color="#ffffff" quantity="0.0"  opacity="0"/>
      <ColorMapEntry color="#ff0000" quantity="0.01" opacity="1"/>
      <ColorMapEntry color="#ff6600" quantity="0.5"  opacity="1"/>
      <ColorMapEntry color="#ffcc00" quantity="1.5"  opacity="1"/>
      <ColorMapEntry color="#00cc00" quantity="3.0"  opacity="1"/>
      <ColorMapEntry color="#0000ff" quantity="6.0"  opacity="1"/>
      <ColorMapEntry color="#cc00cc" quantity="12.0" opacity="1"/>
    </ColorMap>
  </RasterSymbolizer>
  </Rule></FeatureTypeStyle></UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
"""


def _put(url, **kwargs):
    r = requests.put(url, auth=AUTH, **kwargs)
    r.raise_for_status()
    return r


def _post(url, **kwargs):
    r = requests.post(url, auth=AUTH, **kwargs)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"POST {url} -> {r.status_code}: {r.text}")
    return r


def _exists(url):
    return requests.get(url, auth=AUTH).status_code == 200


def _ensure_style():
    """Create or update the rain_blue SLD style in GeoServer."""
    style_url = f"{GS_URL}/rest/styles/rain_blue"
    sld_bytes = RAIN_BLUE_SLD.encode("utf-8")
    headers = {"Content-Type": "application/vnd.ogc.sld+xml"}
    if _exists(style_url):
        requests.put(style_url, auth=AUTH, headers=headers, data=sld_bytes)
        print("[geoserver] Style 'rain_blue' updated")
    else:
        requests.post(
            f"{GS_URL}/rest/styles",
            auth=AUTH,
            headers=headers,
            params={"name": "rain_blue"},
            data=sld_bytes,
        )
        print("[geoserver] Style 'rain_blue' created")


def publish_nc(nc_path: Path):
    """
    Publish (or re-publish) a NetCDF file as a WMS layer in GeoServer.

    Strategy: delete the old store+layer (recurse=true) and recreate fresh on
    every call using configure=all.  This lets GeoServer scan the file itself
    and register the correct coverage name, which avoids the notorious
    'geotools_coverage not available' error that occurs when coverage names
    are set manually and do not match the internal reader mapping.
    """
    # 1. Ensure rain_blue style exists
    _ensure_style()

    # 2. Workspace - create only if missing
    if not _exists(f"{GS_URL}/rest/workspaces/{WS}"):
        _post(f"{GS_URL}/rest/workspaces", json={"workspace": {"name": WS}})
        print(f"[geoserver] Workspace '{WS}' created")

    # 3. Delete existing store (cascade-deletes all layers) so we start clean
    store_url = f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}"
    if _exists(store_url):
        requests.delete(f"{store_url}?recurse=true", auth=AUTH)
        print(f"[geoserver] Old store '{STORE}' removed")

    # 4. Register external NetCDF via REST file API
    #    external.netcdf properly initialises the NetCDF reader so that
    #    ?list=available works and variable names are discoverable.
    r = requests.put(
        f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}/external.netcdf",
        auth=AUTH,
        headers={"Content-Type": "text/plain"},
        params={"configure": "none"},
        data=str(nc_path.resolve()),
    )
    print(f"[geoserver] external.netcdf PUT HTTP {r.status_code}: {r.text[:200]}")
    if r.status_code not in (200, 201):
        raise RuntimeError(f"[geoserver] Store registration failed {r.status_code}: {r.text}")
    print(f"[geoserver] Store '{STORE}' registered -> {nc_path.name}")

    # 5. Discover the variable names GeoServer sees in the file.
    #    GeoServer scans the file asynchronously after external.netcdf PUT,
    #    so retry for up to ~15 seconds until the list is non-empty.
    avail_names = []
    for attempt in range(5):
        avail_r = requests.get(
            f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}/coverages",
            auth=AUTH,
            headers={"Accept": "application/json"},
            params={"list": "available"},
        )
        raw = avail_r.text[:300]
        print(f"[geoserver] Available (attempt {attempt+1}) HTTP {avail_r.status_code}: {raw}")
        try:
            if avail_r.status_code == 200:
                body = avail_r.json()
                # Response shapes seen in the wild:
                #   {"list":{"string":"hourly_rain"}}
                #   {"coverages":{"coverage":[{"name":"hourly_rain",...}]}}
                #   {"coverages":""}  <- empty store, treat as no results
                cov_section = body.get("coverages", {})
                if isinstance(cov_section, dict):
                    entries = (
                        body.get("list", {}).get("string")
                        or cov_section.get("coverage")
                    )
                else:
                    entries = None  # empty string or unexpected type
                if isinstance(entries, str):
                    avail_names = [entries]
                elif isinstance(entries, list):
                    avail_names = [
                        (e["name"] if isinstance(e, dict) else e) for e in entries
                    ]
                elif isinstance(entries, dict):
                    avail_names = [entries.get("name", "")]
        except Exception as e:
            print(f"[geoserver] Available parse error: {e}")
        if avail_names:
            break
        time.sleep(3)

    # Prefer our expected name; fall back to first seen; last resort hardcode
    cov_name = LAYER if LAYER in avail_names else (avail_names[0] if avail_names else LAYER)
    print(f"[geoserver] Publishing coverage: '{cov_name}' (available: {avail_names})")

    # 6. Publish coverage with explicit nativeName (required by GeoServer NetCDF plugin)
    pub_r = requests.post(
        f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}/coverages",
        auth=AUTH,
        json={"coverage": {
            "name":       cov_name,
            "nativeName": cov_name,
            "title":      "Hourly Rain Forecast",
            "srs":        "EPSG:4326",
            "enabled":    True,
        }},
    )
    print(f"[geoserver] Coverage POST HTTP {pub_r.status_code}: {pub_r.text[:300]}")
    if pub_r.status_code not in (200, 201):
        print(f"[geoserver] WARNING: coverage publish failed")

    layer_url = f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}/coverages/{cov_name}"

    # 7. Set rain_blue as the default style (idempotent)
    r = requests.put(
        f"{GS_URL}/rest/layers/{WS}:{cov_name}",
        auth=AUTH,
        json={"layer": {"defaultStyle": {"name": "rain_blue"}}},
    )
    print(f"[geoserver] Default style -> 'rain_blue' (HTTP {r.status_code})")

    # 8. Enable TIME dimension so GeoServer honours the TIME= WMS parameter
    r = requests.put(
        layer_url,
        auth=AUTH,
        headers={"Content-Type": "application/json"},
        json={"coverage": {
            "metadata": {
                "entry": [{
                    "@key": "time",
                    "dimensionInfo": {
                        "enabled": True,
                        "presentation": "LIST",
                        "nearestMatchEnabled": False,
                        "defaultValue": {"strategy": "MAXIMUM"},
                    },
                }],
            },
        }},
    )
    print(f"[geoserver] TIME dimension enabled (HTTP {r.status_code})")
    print(f"[geoserver] WMS ready -> {GS_URL}/{WS}/wms?LAYERS={WS}:{cov_name}")


def ensure_geoserver_running() -> bool:
    """
    Check if GeoServer is reachable. If not, launch the startup script and
    wait up to GS_STARTUP_WAIT seconds for it to come up.
    Returns True if GeoServer is up, False if it could not be started.
    The NC publish happens separately after each fetch cycle completes.
    """
    def _is_up() -> bool:
        try:
            r = requests.get(f"{GS_URL}/rest/workspaces", auth=AUTH, timeout=5)
            return r.status_code == 200
        except requests.exceptions.ConnectionError:
            return False

    if _is_up():
        print("[geoserver] Already running")
        return True

    if not GS_STARTUP.exists():
        print(f"[geoserver] Not reachable and startup script not found at {GS_STARTUP}")
        return False

    print(f"[geoserver] Not running - launching {GS_STARTUP}")
    subprocess.Popen(
        [str(GS_STARTUP)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + GS_STARTUP_WAIT
    while time.time() < deadline:
        time.sleep(5)
        if _is_up():
            print("[geoserver] GeoServer is now up")
            return True

    print(f"[geoserver] GeoServer did not respond within {GS_STARTUP_WAIT}s")
    return False


def check_geoserver_on_startup():
    """
    Called by uvicorn lifespan.
    1. Ensures GeoServer is running (starts it if needed).
    2. If a _gs.nc already exists, publishes it.
    3. If no _gs.nc but a routing .nc exists, rebuilds the _gs.nc from it and publishes.
    4. If nothing exists yet, skips - will publish after first fetch cycle.
    """
    if not ensure_geoserver_running():
        return

    gs_files = sorted(NC_DIR.glob("*_rainWMS_gs.nc"), key=lambda p: p.stat().st_mtime)
    if gs_files:
        newest = gs_files[-1]
        print(f"[geoserver] Found existing {newest.name} - publishing to GeoServer")
        try:
            publish_nc(newest)
        except Exception as e:
            print(f"[geoserver] Startup publish failed: {e}")
        return

    # No _gs.nc - try to rebuild from the newest timestamped routing .nc
    # Only match files whose stem is all digits (Unix timestamp), e.g. 1778600617.nc
    import re as _re
    routing_files = sorted(
        [p for p in NC_DIR.glob("*.nc") if _re.fullmatch(r"\d+", p.stem)],
        key=lambda p: p.stat().st_mtime,
    )
    if not routing_files:
        print("[geoserver] No .nc files found - will publish after first fetch")
        return

    source = routing_files[-1]
    print(f"[geoserver] No _gs.nc found - rebuilding from {source.name}")
    try:
        import xarray as xr
        from utils_fetch import write_geoserver_nc
        ds = xr.open_dataset(source)
        hourly_rain = ds["hourly_rain"]
        ref_time_val = ds["ref_time"].values[0]
        gs_path = source.with_name(source.stem + "_rainWMS_gs.nc")
        write_geoserver_nc(hourly_rain, ref_time_val, gs_path)
        ds.close()
        publish_nc(gs_path)
    except Exception as e:
        print(f"[geoserver] Rebuild from routing .nc failed: {e}")
