"""
utils_geoserver.py

Publishes the latest hourly_rain NetCDF to GeoServer as a WMS layer.
Call after utils_fetch.py writes a new .nc file.
"""
import requests
from pathlib import Path

GS_URL  = "http://localhost:8080/geoserver"
AUTH    = ("admin", "geoserver")   # change password here too
WS      = "vprouting"
STORE   = "rain_forecast"
LAYER   = "hourly_rain"


def _put(url, **kwargs):
    r = requests.put(url, auth=AUTH, **kwargs)
    r.raise_for_status()
    return r


def _post(url, **kwargs):
    r = requests.post(url, auth=AUTH, **kwargs)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"POST {url} → {r.status_code}: {r.text}")
    return r


def ensure_workspace():
    r = requests.get(f"{GS_URL}/rest/workspaces/{WS}", auth=AUTH)
    if r.status_code == 404:
        _post(f"{GS_URL}/rest/workspaces",
              json={"workspace": {"name": WS}})
        print(f"[geoserver] Workspace '{WS}' created")


def publish_nc(nc_path: Path):
    """Register nc_path as a GeoServer coverage store and publish hourly_rain."""
    ensure_workspace()

    # Create/update the coverage store pointing at the file
    store_body = {"coverageStore": {
        "name": STORE,
        "type": "NetCDF",
        "enabled": True,
        "url": f"file:{nc_path.resolve()}",
        "workspace": {"name": WS},
    }}
    r = requests.post(
        f"{GS_URL}/rest/workspaces/{WS}/coveragestores",
        json=store_body, auth=AUTH
    )
    if r.status_code == 409:  # already exists — update it
        _put(
            f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}",
            json=store_body,
        )
    elif r.status_code not in (200, 201):
        raise RuntimeError(f"Store create failed {r.status_code}: {r.text}")
    print(f"[geoserver] Store '{STORE}' -> {nc_path.name}")

    # Publish the hourly_rain variable as a layer (idempotent: delete+recreate)
    del_url = f"{GS_URL}/rest/workspaces/{WS}/coveragestores/{STORE}/coverages/{LAYER}"
    requests.delete(del_url, auth=AUTH)  # ignore 404

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
    print(f"[geoserver] WMS: {GS_URL}/{WS}/wms?SERVICE=WMS&VERSION=1.1.1"
          f"&REQUEST=GetMap&LAYERS={WS}:{LAYER}&..."
    )