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


def publish_nc(nc_path: Path):
    """
    Idempotent publish:
    - First run  : creates workspace + store + layer (full setup)
    - Later runs : updates store URL + reloads cache, skips existing layer
    GeoServer persists config across restarts, so no manual re-run needed.
    """
    # 1. Workspace — create only if missing
    if not _exists(f"{GS_URL}/rest/workspaces/{WS}"):
        _post(f"{GS_URL}/rest/workspaces",
              json={"workspace": {"name": WS}})
        print(f"[geoserver] Workspace '{WS}' created")

    # 2. Store — create if missing, update URL if exists (new .nc file)
    store_url  = f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}"
    store_body = {"coverageStore": {
        "name":      STORE,
        "type":      "NetCDF",
        "enabled":   True,
        "url":       f"file:{nc_path.resolve()}",
        "workspace": {"name": WS},
    }}
    if _exists(store_url):
        _put(store_url, json=store_body)
        print(f"[geoserver] Store '{STORE}' updated -> {nc_path.name}")
    else:
        _post(f"{GS_URL}/rest/workspaces/{WS}/coveragestores",
              json=store_body)
        print(f"[geoserver] Store '{STORE}' created -> {nc_path.name}")

    # 3. Layer — create only if missing (persisted across GeoServer restarts)
    layer_url = f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}/coverages/{LAYER}"
    if not _exists(layer_url):
        _post(
            f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}/coverages",
            json={"coverage": {
                "name":       LAYER,
                "nativeName": "hourly_rain",
                "title":      "Hourly Rain Forecast",
                "srs":        "EPSG:4326",
                "enabled":    True,
            }},
        )
        print(f"[geoserver] Layer '{WS}:{LAYER}' published")
    else:
        print(f"[geoserver] Layer '{WS}:{LAYER}' already exists, skipping")

    # 4. Reload store cache so GeoServer picks up the new file immediately
    requests.post(f"{store_url}/reset", auth=AUTH)
    print(f"[geoserver] Store cache reloaded")
    print(f"[geoserver] WMS ready at {GS_URL}/{WS}/wms")


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

    print(f"[geoserver] Not running — launching {GS_STARTUP}")
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
    Called by uvicorn lifespan. Ensures GeoServer is running (starts it if needed).
    NC file publish is NOT done here — it happens after each fetch cycle in utils_fetch.py.
    """
    ensure_geoserver_running()