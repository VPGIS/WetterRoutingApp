
# API Starten: uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
# Erreichbar unter: http://<Server-IP>:8000/



# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Imports
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# API Libaries
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi import Request
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from typing import Literal

# Sonstige Libaries
import subprocess
import numpy as np
import osmnx as ox
import xarray as xr
from pathlib import Path
import sys
from pathlib import Path as SysPath
import re
import json

# Utils
try:
    from backend.utils_graph import _parse_point, get_square_bbox_from_points, get_graph_cached
    from backend.utils_nc_file import get_nc_file
    from backend.utils_forecast import get_forecast, compute_rain_adjusted_cost
    from utils_routingmodels import static_djikstra, time_dependent_dijkstra
    from backend.utils_geoserver import check_geoserver_on_startup

except ModuleNotFoundError:
    backend_dir = str(SysPath(__file__).resolve().parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from utils_graph import _parse_point, get_square_bbox_from_points, get_graph_cached
    from utils_nc_file import get_nc_file
    from utils_forecast import get_forecast, compute_rain_adjusted_cost
    from utils_routingmodels import static_djikstra, time_dependent_dijkstra
    from utils_geoserver import check_geoserver_on_startup


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# FastAPI
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# ---------------------------------------------------------------------------
# Fetch-Daemon beim Start automatisch starten
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parent
NC_DIR = BACKEND_DIR / "data" / "NC"
FETCH_SCRIPT = BACKEND_DIR / "utils_fetch.py"

import requests as http_requests

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fetch-Daemon als Hintergrundprozess starten
    print("[startup] Starte Fetch-Daemon...")
    daemon = subprocess.Popen(
        [sys.executable, str(FETCH_SCRIPT)],
        cwd=BACKEND_DIR.parent,
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )
    print(f"[startup] Fetch-Daemon gestartet (PID {daemon.pid})")
    
    # GeoServer überprüfen/starten
    check_geoserver_on_startup()
    
    yield
    # Beim Herunterfahren der API den Daemon beenden
    print("[shutdown] Beende Fetch-Daemon...")
    daemon.terminate()

app = FastAPI(
    # API DOKU
    title="Wetter Routing API",
    description=(
        "API fuer wetterabhaengige Fahrradrouten. "
        "Die Route wird anhand von OpenStreetMap-Daten und "
        "NetCDF-Niederschlagsprognosen berechnet."
    ),
    version="1.0.0",
    lifespan=lifespan,
    )

# ---------------------------------------------------------------------------
# CORS konfigurieren
load_dotenv()
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Pfad zum Frontend-Verzeichnis (relativ zu diesem Skript)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # Erlaubt Anfragen von localhost und lokalen Netzwerk-IPs (192.168.x.x, 10.x.x.x, 172.x.x.x)
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.[0-9]+\.[0-9]+|10\.[0-9]+\.[0-9]+\.[0-9]+|172\.[0-9]+\.[0-9]+\.[0-9]+)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=['GET', 'OPTIONS'],
    allow_headers=["*"],
    max_age= 5961600
)

# ---------------------------------------------------------------------------
# Statische Dateien & Frontend
# ---------------------------------------------------------------------------

# Startseite: liefert direkt die HTML-Datei wenn jemand die IP eingibt
@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "vp_routing.html")


@app.get("/rain-times", include_in_schema=False)
def rain_times():
    """Return ISO timestamp strings from the latest GeoServer NetCDF."""
    gs_files = sorted(NC_DIR.glob("*_rainWMS_gs.nc"), key=lambda p: p.stat().st_mtime)
    if not gs_files:
        return []
    ds = xr.open_dataset(gs_files[-1])
    times = [str(t)[:19] + ".000Z" for t in ds["time"].values]
    ds.close()
    return times


@app.get("/wms", include_in_schema=False)
def wms_proxy(request: Request):
    """Proxy WMS tile requests to GeoServer to avoid browser CORS restrictions."""
    params = dict(request.query_params)
    r = http_requests.get(
        "http://localhost:8080/geoserver/vprouting/wms",
        params=params,
        timeout=15,
    )
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "image/png"),
    )



# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# API Endpoints 
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 


#-----------------------------------------------------------------------------
# Route Endpoint
@app.get(
        # Endpunkt DOKU
        "/WAPapi/v1/route",
        tags=["Routing"],
        summary="Wetterabhaengige Route berechnen",
        description=(
            "Berechnet eine Fahrradroute zwischen Start- und Zielpunkt. "
            "Je nach Routingmodell und Regenempfindlichkeit werden "
            "Kanten mit hoher Niederschlagsprognose staerker gewichtet."
        ),
        responses={
            200: {
                "description": "Route als GeoJSON",
                "content": {
                    "application/json": {
                        "example": {
                            "type": "FeatureCollection",
                            "features": [
                                {
                                    "type": "Feature",
                                    "properties": {
                                        "osmid": 123456789,
                                        "length": 185.4,
                                        "cost": 231.75,
                                        "travel_time": 33
                                    },
                                    "geometry": {
                                        "type": "LineString",
                                        "coordinates": [
                                            [7.642110, 47.534573],
                                            [7.643200, 47.535000],
                                            [7.645191, 47.522711]
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                },
            },
            400: {"description": "Ungueltige Eingabeparameter"},
            404: {"description": "Keine passende NetCDF-Wetterdatei gefunden"},
            500: {"description": "Interner Fehler bei Wetter- oder Routingdaten"},
        },
)


def get_route(
    start_point: str = Query(
        ...,
        description=(
            "Startpunkt der Route. "
            "Kann entweder als vollständige Adresse "
            "oder als WGS84-Koordinaten angegeben werden."
        ),
        openapi_examples={
            "address": {
                "summary": "Adresse",
                "value": "Hofackerstrasse 30, 4132 Muttenz",
            },
            "coordinates": {
                "summary": "Koordinaten",
                "value": "47.534573, 7.642110",
            },
        },
    ),

    end_point: str = Query(
        ...,
        description=(
            "Zielpunkt der Route. "
            "Kann als Adresse oder WGS84-Koordinaten angegeben werden."
        ),
        openapi_examples={
            "address": {
                "summary": "Adresse",
                "value": "Domplatz 16, 4144 Arlesheim",
            },
            "coordinates": {
                "summary": "Koordinaten",
                "value": "47.492048, 7.620853",
            },
        },
    ),

    start_time: int = Query(
        ...,
        description=(
            "Startzeit als Unix-Timestamp "
            "(Sekunden seit 1970-01-01 UTC)."
        ),
        examples=[1712345678],
    ),

    speed: float = Query(
        20,
        gt=0,
        description="Fahrgeschwindigkeit in km/h.",
        examples=[20],
    ),

    routingmodel: Literal["einfach", "advanced"] = Query(
        "einfach",
        description=(
            "Verwendetes Routingmodell.\n\n"
            "- einfach: Statisches Routing basierend auf Dijkstra.\n"
            "- advanced: Dynamisches Routing mit zeitabhängigen Bedingungen."
        ),
    ),

    sensibility: Literal["lowest", "low", "medium", "high", "highest"] = Query(
        "medium",
        description=(
            "Regenempfindlichkeit des Nutzers.\n\n"
            "- lowest: Regen hat keinen Einfluss auf die Kosten\n"
            "- low: Geringe Gewichtung von Regen\n"
            "- medium: Mittlere Gewichtung von Regen\n"
            "- high: Starke Gewichtung von Regen\n"
            "- highest: Kanten mit Regen werden vollständig vermieden"
        ),
    )

    ):

    print("[route] request received")
    print(f"[route] start_point={start_point!r}, end_point={end_point!r}, start_time={start_time}, speed={speed}, routingmodel={routingmodel}, sensibility={sensibility}")

    # ——————————————————————————————————————————————————————————————————————————
    # Speed von km/h in m/s
    # ——————————————————————————————————————————————————————————————————————————
    speed = speed / 3.6

    if speed <= 0:
        raise HTTPException(status_code=400, detail="speed must be > 0")

    # ——————————————————————————————————————————————————————————————————————————
    # Sicherstellen, dass Start-/ Endpunkt im format lat, lon vorliegen
    # ——————————————————————————————————————————————————————————————————————————
    start_point = _parse_point(start_point)
    end_point = _parse_point(end_point)
    
    

    # ——————————————————————————————————————————————————————————————————————————
    # Richtiges NC-File laden
    # ——————————————————————————————————————————————————————————————————————————
    try:
        nc_filepath = get_nc_file(int(start_time))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if nc_filepath is None:
        raise HTTPException(
            status_code=404,
            detail="Keine gültige Wetterdatei gefunden – Fetch-Daemon läuft noch oder Daten sind veraltet."
        )

    try:
        ds = xr.open_dataset(nc_filepath)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    print(f"[route] nc_filepath={nc_filepath}")

    # ——————————————————————————————————————————————————————————————————————————
    # Aus Start-/ Endpunkt den richtigen Graphen aus dem Cache finden oder herunterladen
    # ——————————————————————————————————————————————————————————————————————————
    bbox = get_square_bbox_from_points(start_point, end_point)
    G = get_graph_cached(bbox)

    # ——————————————————————————————————————————————————————————————————————————
    # Aus Start-/ Endpunkt die richtige Node auswählen
    # ——————————————————————————————————————————————————————————————————————————
    lat_s, lon_s = start_point
    start_node = ox.distance.nearest_nodes(G, lon_s, lat_s)

    lat_e, lon_e = end_point
    end_node = ox.distance.nearest_nodes(G, lon_e, lat_e)
    

    # Zeitstempel als integer vorbereiten
    start_time = int(start_time)
    nc_stem = Path(nc_filepath).stem

    '''------------------------TEMP-------------------------'''
    nc_file_timestamp_match = re.search(r"(\d+)", nc_stem)
    if not nc_file_timestamp_match:
        ds.close()
        raise HTTPException(status_code=500, detail=f"Could not parse timestamp from nc file name: {nc_stem}")

    nc_file_timestamp = int(nc_file_timestamp_match.group(1))

    print(f"[route] nc_stem={nc_stem!r}, nc_file_timestamp={nc_file_timestamp}")

    lead_hours = (start_time - nc_file_timestamp) / 3600.0
    lead_idx = int(round(lead_hours))
    print(f"[route] lead_hours={lead_hours}, initial lead_idx={lead_idx}")

    if lead_idx < 0:
        ds.close()
        raise HTTPException(status_code=400, detail="start_time is before the forecast file timestamp")

    max_lead_idx = int(ds["TOT_PREC"].sizes.get("lead_time", 0)) - 1
    if max_lead_idx < 0:
        ds.close()
        raise HTTPException(status_code=500, detail="forecast dataset has no lead_time dimension")

    if lead_idx > max_lead_idx:
        lead_idx = max_lead_idx
    print(f"[route] clamped lead_idx={lead_idx}, max_lead_idx={max_lead_idx}")
    '''------------------------TEMP-------------------------'''

    # ——————————————————————————————————————————————————————————————————————————
    # Routing anhand gewähltem Routingmodel durchführen
    # ——————————————————————————————————————————————————————————————————————————
    if routingmodel == 'einfach':

        route = static_djikstra(G=G,
                                start_node=start_node,
                                end_node=end_node,
                                start_time=start_time,
                                speed=speed,
                                ds=ds,
                                nc_file_timestamp=nc_file_timestamp,
                                sensibility=sensibility)

    elif routingmodel == 'advanced':
        route = time_dependent_dijkstra(G=G,
                                        start_node=start_node,
                                        end_node=end_node,
                                        start_timestamp=start_time,
                                        speed=speed,
                                        ds=ds,
                                        nc_file_timestamp=nc_file_timestamp,
                                        sensibility=sensibility)


    # ——————————————————————————————————————————————————————————————————————————
    # NC-File schliessen
    # ——————————————————————————————————————————————————————————————————————————
    ds.close()

    # ——————————————————————————————————————————————————————————————————————————
    # Ausgabe der Route als geojson
    # ——————————————————————————————————————————————————————————————————————————
    
    route_gdf = ox.routing.route_to_gdf(G, route, weight='cost')
    keep_cols = ["osmid", "length", "cost","travel_time", "geometry"]
    route_gdf = route_gdf[keep_cols]
    return json.loads(route_gdf.to_json())

    # für debugging -> return G, route


# Einzelne statische Dateien explizit ausliefern
# (app.mount("/") würde alle API-Routen blockieren)
@app.get("/style.css", include_in_schema=False)
def serve_css():
    return FileResponse(FRONTEND_DIR / "style.css", media_type="text/css")

@app.get("/logo.jpg", include_in_schema=False)
def serve_logo():
    return FileResponse(FRONTEND_DIR / "logo.jpg", media_type="image/jpeg")

