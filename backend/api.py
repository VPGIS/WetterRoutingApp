
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# Imports
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

# API Libaries
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Sonstige Libaries
import osmnx as ox
import xarray as xr
from pathlib import Path

# Utils
from backend.utils_graph import _parse_point, get_boundingbox_from_points, get_graph_cached
from backend.utils_nc_file import get_nc_file
from backend.utils_forecast import get_forecast, compute_rain_adjusted_cost

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# FastAPI
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

app = FastAPI()


# ---------------------------------------------------------------------------
# CORS konfigurieren
load_dotenv()
origins = "http://localhost"



app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['GET'],
    allow_headers=["*"],
    max_age= 5961600
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# API Endpoints 
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 


#-----------------------------------------------------------------------------
# Route Endpoint
@app.get("/WAPapi/v1/route")
def get_route(start_point, end_point, start_time, speed, routingmodel, sensibility):

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

    # Zeitstempel als integer vorbereiten
    start_time = int(start_time)
    nc_file_timestamp = int(Path(nc_filepath).stem)


    # ——————————————————————————————————————————————————————————————————————————
    # Routing anhand gewähltem Routingmodel durchführen
    # ——————————————————————————————————————————————————————————————————————————
    if routingmodel == 'einfach':

        for edge in G.edges(keys=True, data=True):
            u, v, k, data = edge
            data["forecast"] = get_forecast(G, ds, u, v, k, 
                                        file_timestamp=nc_file_timestamp, 
                                        target_timestamp=start_time,
                                        interpolate=False)
            
            data['cost'] = compute_rain_adjusted_cost(data['length'], data["forecast"], sensibility)

            data['travel_time'] = int(data['length'] / speed)

        route = ox.routing.shortest_path(G, start_node, end_node, weight='cost')
    
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
