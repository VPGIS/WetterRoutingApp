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
RAIN_BLUE_SLD = """\
<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xmlns="http://www.opengis.net/sld">
  <NamedLayer><Name>rain_blue</Name>
  <UserStyle><FeatureTypeStyle><Rule>
  <RasterSymbolizer>
    <ColorMap type="ramp">
      <ColorMapEntry color="#f7fafd" quantity="0.0"  opacity="0"/>
      <ColorMapEntry color="#f7fafd" quantity="0.01" opacity="0.82"/>
      <ColorMapEntry color="#c9dff2" quantity="0.5"  opacity="0.82"/>
      <ColorMapEntry color="#84b9e0" quantity="1.5"  opacity="0.82"/>
      <ColorMapEntry color="#3d87c1" quantity="3.0"  opacity="0.82"/>
      <ColorMapEntry color="#1d5f9a" quantity="6.0"  opacity="0.82"/>
      <ColorMapEntry color="#0d3a6e" quantity="12.0" opacity="0.82"/>
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

    # 4. Create store with configure=all - GeoServer auto-discovers the coverage
    store_body = {"coverageStore": {
        "name":      STORE,
        "type":      "NetCDF",
        "enabled":   True,
        "url":       f"file:{nc_path.resolve()}",
        "workspace": {"name": WS},
    }}
    r = requests.post(
        f"{GS_URL}/rest/workspaces/{WS}/coveragestores",
        auth=AUTH,
        params={"configure": "all"},
        json=store_body,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"[geoserver] POST store -> {r.status_code}: {r.text}")
    print(f"[geoserver] Store '{STORE}' created -> {nc_path.name}")

    # 5. Discover the actual coverage name GeoServer assigned
    cov_r = requests.get(
        f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}/coverages",
        auth=AUTH,
        headers={"Accept": "application/json"},
    )
    cov_name = LAYER  # fallback to expected name
    print(f"[geoserver] Coverage list HTTP {cov_r.status_code}: {cov_r.text[:300]}")
    try:
        if cov_r.status_code == 200:
            body = cov_r.json()
            cov_data = body.get("coverages", {}).get("coverage", [])
            print(f"[geoserver] cov_data type={type(cov_data).__name__} value={cov_data!r}")
            if isinstance(cov_data, list) and cov_data:
                first = cov_data[0]
                cov_name = first if isinstance(first, str) else first.get("name", LAYER)
            elif isinstance(cov_data, dict):
                cov_name = cov_data.get("name", LAYER)
            elif isinstance(cov_data, str) and cov_data:
                cov_name = cov_data
    except Exception as e:
        import traceback
        print(f"[geoserver] Coverage name parse failed ({e}), falling back to '{LAYER}'")
        traceback.print_exc()
    print(f"[geoserver] Using coverage name: '{cov_name}'")

    # If GeoServer gave it a different name, rename it to our expected LAYER name
    if cov_name != LAYER:
        requests.put(
            f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}/coverages/{cov_name}",
            auth=AUTH,
            headers={"Content-Type": "application/json"},
            json={"coverage": {"name": LAYER, "nativeName": cov_name}},
        )
        print(f"[geoserver] Coverage renamed '{cov_name}' -> '{LAYER}'")
        cov_name = LAYER

    layer_url = f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}/coverages/{cov_name}"

    # 6. Set rain_blue as the default style (idempotent)
    requests.put(
        f"{GS_URL}/rest/layers/{WS}:{cov_name}",
        auth=AUTH,
        json={"layer": {"defaultStyle": {"name": "rain_blue"}}},
    )
    print("[geoserver] Default style -> 'rain_blue'")

    # 7. Enable TIME dimension so GeoServer honours the TIME= WMS parameter
    requests.put(
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
    print("[geoserver] TIME dimension enabled")
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
