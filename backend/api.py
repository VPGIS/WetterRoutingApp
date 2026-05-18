
# API Starten: uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
# Erreichbar unter: http://<Server-IP>:8000/



# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Imports
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# API Libaries
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from contextlib import asynccontextmanager

from typing import Literal

# Sonstige Libaries
import subprocess
import requests as http_requests
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
    from backend.utils_render import list_rain_times, get_rain_layer_path, get_rain_layer_p90_path, RAIN_LAYERS_DIR, \
        list_demo_rain_times, get_demo_rain_layer_path, get_demo_rain_layer_p90_path, render_demo_nc, DEMO_RAIN_LAYERS_DIR

except ModuleNotFoundError:
    backend_dir = str(SysPath(__file__).resolve().parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from utils_graph import _parse_point, get_square_bbox_from_points, get_graph_cached
    from utils_nc_file import get_nc_file
    from utils_forecast import get_forecast, compute_rain_adjusted_cost
    from utils_routingmodels import static_djikstra, time_dependent_dijkstra
    from utils_render import list_rain_times, get_rain_layer_path, get_rain_layer_p90_path, RAIN_LAYERS_DIR, \
        list_demo_rain_times, get_demo_rain_layer_path, get_demo_rain_layer_p90_path, render_demo_nc, DEMO_RAIN_LAYERS_DIR


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# FastAPI
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# ---------------------------------------------------------------------------
# Fetch-Daemon beim Start automatisch starten
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parent
NC_DIR = BACKEND_DIR / "data" / "NC"
FETCH_SCRIPT = BACKEND_DIR / "utils_fetch.py"
DEMO_NC_PATH = NC_DIR / "demo_1779064720.nc"
DEMO_NC_UNIX = 1779064720

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Demo rain layers vorrendern (einmalig beim Start)
    try:
        if DEMO_NC_PATH.exists() and not DEMO_RAIN_LAYERS_DIR.exists():
            print("[startup] Rendere Demo-Regenebenen...")
            render_demo_nc(DEMO_NC_PATH)
            print("[startup] Demo-Regenebenen fertig.")
    except Exception as e:
        print(f"[startup] Demo-Render fehlgeschlagen: {e}")

    # Fetch-Daemon als Hintergrundprozess starten
    print("[startup] Starte Fetch-Daemon...")
    daemon = subprocess.Popen(
        [sys.executable, str(FETCH_SCRIPT)],
        cwd=BACKEND_DIR.parent,
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )
    print(f"[startup] Fetch-Daemon gestartet (PID {daemon.pid})")
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
    """Return ISO timestamp strings for all available rain PNGs."""
    return list_rain_times()


@app.get("/rain-frame", include_in_schema=False)
def get_rain_frame(time: str = Query(...), layer: str = Query("mean")):
    """Return a pre-rendered PNG frame. layer=mean (default) or layer=p90."""
    try:
        if layer == "p90":
            png_path = get_rain_layer_p90_path(time)
        else:
            png_path = get_rain_layer_path(time)
        return FileResponse(png_path, media_type="image/png")
    except Exception:
        return Response(status_code=404)


@app.get("/nc-info", include_in_schema=False)
def nc_info():
    """Return the Unix timestamp (filename) of the newest .nc file."""
    import re
    files = sorted(
        [p for p in NC_DIR.glob("*.nc") if re.fullmatch(r"\d+", p.stem)],
        key=lambda p: int(p.stem),
    )
    if not files:
        return {"downloaded_unix": None}
    return {"downloaded_unix": int(files[-1].stem)}


# ---------------------------------------------------------------------------
# Demo endpoints — serve pre-rendered frames from the demo NC file
# ---------------------------------------------------------------------------

@app.get("/demo-rain-times", include_in_schema=False)
def demo_rain_times():
    """Return ISO timestamp strings for all available demo rain PNGs."""
    return list_demo_rain_times()


@app.get("/demo-rain-frame", include_in_schema=False)
def get_demo_rain_frame(time: str = Query(...), layer: str = Query("mean")):
    """Return a pre-rendered demo PNG frame. layer=mean (default) or layer=p90."""
    try:
        if layer == "p90":
            png_path = get_demo_rain_layer_p90_path(time)
        else:
            png_path = get_demo_rain_layer_path(time)
        return FileResponse(png_path, media_type="image/png")
    except Exception:
        return Response(status_code=404)


@app.get("/demo-nc-info", include_in_schema=False)
def demo_nc_info():
    """Return info about the demo NC file."""
    if DEMO_NC_PATH.exists():
        return {"downloaded_unix": DEMO_NC_UNIX, "demo": True}
    return {"downloaded_unix": None}



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
    ),

    demo: bool = Query(
        False,
        description="Demo-Modus: Verwendet die Demo-NC-Datei statt der aktuellen Wetterdaten.",
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
    if demo:
        nc_filepath = str(DEMO_NC_PATH)
        if not DEMO_NC_PATH.exists():
            raise HTTPException(status_code=404, detail="Demo-NC-Datei nicht gefunden.")
    else:
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

