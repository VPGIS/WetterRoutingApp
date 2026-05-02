
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Imports
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# API Libaries
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Sonstige Libaries
import numpy as np
import osmnx as ox
import xarray as xr
from pathlib import Path
import sys
from pathlib import Path as SysPath
import re

# Utils
try:
    from backend.utils_graph import _parse_point, get_boundingbox_from_points, get_graph_cached
    from backend.utils_nc_file import get_nc_file
    from backend.utils_forecast import get_forecast, compute_rain_adjusted_cost
except ModuleNotFoundError:
    backend_dir = str(SysPath(__file__).resolve().parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from utils_graph import _parse_point, get_boundingbox_from_points, get_graph_cached
    from utils_nc_file import get_nc_file
    from utils_forecast import get_forecast, compute_rain_adjusted_cost

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# FastAPI
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

app = FastAPI()


# ---------------------------------------------------------------------------
# CORS konfigurieren
load_dotenv()
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]



app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^null$",
    allow_credentials=True,
    allow_methods=['GET', 'OPTIONS'],
    allow_headers=["*"],
    max_age= 5961600
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# API Endpoints 
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 


#-----------------------------------------------------------------------------
# Route Endpoint
@app.get("/WAPapi/v1/route")
def get_route(
    start_point: str,
    end_point: str,
    start_time: int,
    speed: float,
    routingmodel: str,
    sensibility: str,
):

    print("[route] request received")
    print(f"[route] start_point={start_point!r}, end_point={end_point!r}, start_time={start_time}, speed={speed}, routingmodel={routingmodel}, sensibility={sensibility}")

    if speed <= 0:
        raise HTTPException(status_code=400, detail="speed must be > 0")

    # ——————————————————————————————————————————————————————————————————————————
    # Sicherstellen, dass Start-/ Endpunkt im format lat, lon vorliegen
    # ——————————————————————————————————————————————————————————————————————————
    start_point = _parse_point(start_point)
    end_point = _parse_point(end_point)
    
    # ——————————————————————————————————————————————————————————————————————————
    # Speed von km/h in m/s
    # ——————————————————————————————————————————————————————————————————————————
    speed = speed / 3.6

    # ——————————————————————————————————————————————————————————————————————————
    # Aus Start-/ Endpunkt den richtigen Graphen aus dem Cache finden oder herunterladen
    # ——————————————————————————————————————————————————————————————————————————
    bbox = get_boundingbox_from_points(start_point, end_point)
    G = get_graph_cached(bbox)
    

    # ——————————————————————————————————————————————————————————————————————————
    # Aus Start-/ Endpunkt die richtige Node auswählen
    # ——————————————————————————————————————————————————————————————————————————
    lat_s, lon_s = start_point
    start_node = ox.distance.nearest_nodes(G, lon_s, lat_s)

    lat_e, lon_e = end_point
    end_node = ox.distance.nearest_nodes(G, lon_e, lat_e)


    # ——————————————————————————————————————————————————————————————————————————
    # Richtiges NC-File laden
    # ——————————————————————————————————————————————————————————————————————————
    nc_filepath = str(get_nc_file(start_time))
    ds = xr.open_dataset(nc_filepath)
    print(f"[route] nc_filepath={nc_filepath}")

    # Zeitstempel als integer vorbereiten
    start_time = int(start_time)
    nc_stem = Path(nc_filepath).stem
    nc_file_timestamp_match = re.search(r"(\d+)", nc_stem)
    if nc_file_timestamp_match:
        nc_file_timestamp = int(nc_file_timestamp_match.group(1))
        demo_mode = False
    else:
        nc_file_timestamp = start_time
        demo_mode = True

    print(f"[route] nc_stem={nc_stem!r}, nc_file_timestamp={nc_file_timestamp}, demo_mode={demo_mode}")

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


    # ——————————————————————————————————————————————————————————————————————————
    # Routing anhand gewähltem Routingmodel durchführen
    # ——————————————————————————————————————————————————————————————————————————
    if routingmodel == 'einfach':

        edges = list(G.edges(keys=True, data=True))
        print(f"[route] graph edges={len(edges)}")
        edge_cells_i = np.array([data["cell_i"] for _, _, _, data in edges], dtype=int)
        edge_cells_j = np.array([data["cell_j"] for _, _, _, data in edges], dtype=int)
        edge_lengths = np.array([data["length"] for _, _, _, data in edges], dtype=float)

        forecast_grid = ds["TOT_PREC"].isel(eps=0, ref_time=0, lead_time=lead_idx).values
        print(f"[route] forecast_grid shape={forecast_grid.shape}")
        edge_forecasts = forecast_grid[edge_cells_i, edge_cells_j]
        print(f"[route] forecast sample={edge_forecasts[:3].tolist() if len(edge_forecasts) else []}")

        for (u, v, k, data), forecast, length in zip(edges, edge_forecasts, edge_lengths):
            data["forecast"] = float(forecast)
            data['cost'] = compute_rain_adjusted_cost(length, float(forecast), sensibility)
            data['travel_time'] = int(length / speed)

        route = ox.routing.shortest_path(G, start_node, end_node, weight='cost')
        print(f"[route] route nodes={len(route) if route else 0}")
    
    # TODO
    elif routingmodel == 'advanced':
        print('todo')



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
    return route_gdf.to_json()

    # für debugging -> return G, route
