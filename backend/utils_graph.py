import numpy as np
import osmnx as ox

import math
import os
import json
import uuid

import xarray as xr
from scipy.spatial import cKDTree


def get_cellid(G, nc_filepath="nc_folder/NC_for_Cellid.nc", lat_name="lat", lon_name="lon"):
    """
    Ordnet jeder Edge eines OSMnx-Graphen eine Rasterzelle (cell_id) zu.

    Parameter
    ----------
    G : networkx.MultiDiGraph
        OSMnx-Graph
    nc_filepath: str
        Pfad zur NetCDF-Datei, Standard "backend/nc_folder/NC_for_Cellid.nc"
    lat_name : str
        Name der Latitude-Variable im Dataset
    lon_name : str
        Name der Longitude-Variable im Dataset

    Returns
    -------
    G : networkx.MultiDiGraph
        Graph mit neuen Edge-Attributen:
        - cell_i
        - cell_j
        - cell_id
    """

    # ═══════════════════════════════════════════════════════════════
    # 1. NetCDF laden
    # ═══════════════════════════════════════════════════════════════
    ds = xr.open_dataset(nc_filepath)

    lat = ds[lat_name].values
    lon = ds[lon_name].values

    # KD-Tree
    points = np.column_stack([lon.ravel(), lat.ravel()])
    tree = cKDTree(points)

    # Grid-Indizes
    flat_idx = np.arange(len(points))
    i_all, j_all = np.unravel_index(flat_idx, lat.shape)

    # ═══════════════════════════════════════════════════════════════
    # 2. Edges extrahieren
    # ═══════════════════════════════════════════════════════════════
    edges = list(G.edges(keys=True, data=True))

    valid_edges = [(u, v, k) for (u, v, k, d) in edges if "geometry" in d]
    geoms = [d["geometry"] for (_, _, _, d) in edges if "geometry" in d]

    if len(geoms) == 0:
        raise ValueError("Keine Edge-Geometrien im Graph gefunden.")

    # ═══════════════════════════════════════════════════════════════
    # 3. Mittelpunkte berechnen
    # ═══════════════════════════════════════════════════════════════
    midpoints = np.array([
        geom.interpolate(0.5, normalized=True).coords[0]
        for geom in geoms
    ])

    # ═══════════════════════════════════════════════════════════════
    # 4. KD-Tree Query
    # ═══════════════════════════════════════════════════════════════
    _, idx = tree.query(midpoints)

    cell_i = i_all[idx]
    cell_j = j_all[idx]

    # Vektorisierte cell_id
    cell_ids = np.char.add(cell_i.astype(str), "_")
    cell_ids = np.char.add(cell_ids, cell_j.astype(str))

    # ═══════════════════════════════════════════════════════════════
    # 5. Zurück in Graph schreiben
    # ═══════════════════════════════════════════════════════════════
    for (u, v, k), i, j, cid in zip(valid_edges, cell_i, cell_j, cell_ids):
        G.edges[u, v, k]["cell_i"] = int(i)
        G.edges[u, v, k]["cell_j"] = int(j)
        G.edges[u, v, k]["cell_id"] = str(cid)

    return G

def _parse_point(point):
    """Konvertiert Adresse oder Koordinaten in (lat, lon)."""

    # Fall 1: Adresse (String)
    if isinstance(point, str):
        lat, lon = ox.geocode(point)

    # Fall 2: Koordinaten
    elif isinstance(point, (list, tuple, np.ndarray)):
        lat, lon = float(point[0]), float(point[1])

    else:
        raise ValueError(f"{point} muss eine Adresse oder Koordinaten (lat, lon) sein")

    # Sicherheitscheck
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Ungültige Koordinaten: ({lat}, {lon})")

    return lat, lon

def get_boundingbox_from_points(point1, point2, buffer_km=0.0):
    """
    Erstellt eine Bounding Box aus zwei Punkten und erweitert sie um einen Puffer in Kilometern.
    
    Parameter
    ----------
    point1 : tuple
        Erster Punkt als (lat, lon)
    point2 : tuple
        Zweiter Punkt als (lat, lon)
    buffer_km : float, optional
        Erweiterung der Bounding Box in Kilometern in alle Richtungen (default: 0.0)
    
    Returns
    -------
    tuple
        Bounding Box im Format (north, south, east, west)
    """

    lat1, lon1 = point1
    lat2, lon2 = point2

    north = max(lat1, lat2)
    south = min(lat1, lat2)
    east = max(lon1, lon2)
    west = min(lon1, lon2)

    if buffer_km > 0:
        delta_lat = buffer_km / 111.0
        mean_lat = (north + south) / 2
        delta_lon = buffer_km / (111.0 * math.cos(math.radians(mean_lat)))

        north += delta_lat
        south -= delta_lat
        east += delta_lon
        west -= delta_lon

    # INTERNES FORMAT
    return (north, south, east, west)

def to_osmnx_bbox(bbox):
    """Konvertiert (north, south, east, west) → (west, south, east, north)"""
    north, south, east, west = bbox
    return (west, south, east, north)

def get_graph_cached(bbox, network_type="bike", size_threshold=0.5, precision=5,**kwargs):
    """
    Lädt einen OSMnx-Graphen aus dem Cache oder erstellt einen neuen basierend auf einer Bounding Box.
    
    Die Funktion prüft, ob bereits ein gespeicherter Graph existiert, dessen Bounding Box
    die angefragte Bounding Box vollständig enthält und dessen Größe innerhalb eines
    definierten Schwellenwerts liegt. Falls ein passender Graph gefunden wird, wird dieser geladen.
    Andernfalls wird ein neuer Graph von OSM heruntergeladen, gespeichert und im Index registriert.
    
    Parameter
    ----------
    bbox : tuple
        Bounding Box im Format (north, south, east, west)
    network_type : str, optional
        Typ des Straßennetzwerks (z.B. "drive", "walk", "bike") (default: "bike")
    size_threshold : float, optional
        Maximal erlaubte relative Größenabweichung zwischen gespeicherter und angefragter Bounding Box.
        Beispiel: 0.5 bedeutet, dass der gespeicherte Graph höchstens 50% größer sein darf (default: 0.5)
    precision : int, optional
        Anzahl Dezimalstellen zur Rundung der Bounding Box Koordinaten (default: 5)
    **kwargs : 
    
    Returns
    -------
    networkx.MultiDiGraph
        Geladener oder neu erstellter OSMnx-Graph
    """

    INDEX_FILE = "data/index.json"
    GRAPH_DIR = "data/graphs"

    os.makedirs(GRAPH_DIR, exist_ok=True)

    # Bounding Box runden (internes Format bleibt erhalten)
    north, south, east, west = [round(x, precision) for x in bbox]
    bbox = (north, south, east, west)

    requested_area = (north - south) * (east - west)

    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r") as f:
            index = json.load(f)
    else:
        index = []

    candidates = []

    for entry in index:
        if entry["network_type"] != network_type:
            continue

        N, S, E, W = entry["north"], entry["south"], entry["east"], entry["west"]

        if not (N >= north and S <= south and E >= east and W <= west):
            continue

        existing_area = (N - S) * (E - W)
        size_ratio = (existing_area - requested_area) / requested_area

        if size_ratio > size_threshold:
            continue

        candidates.append((entry, existing_area))

    if candidates:
        best_entry = min(candidates, key=lambda x: x[1])[0]
        return ox.load_graphml(best_entry["file"])

    else:
        G = ox.graph_from_bbox(to_osmnx_bbox(bbox),network_type=network_type,**kwargs)

        # Graph wird einmal in ein gpdf umgewandelt um die leeren edge Geometrien zu füllen (mit den Nodesgeometrien)
        # anschliessend wird er wieder zurückgenandelt
        gdf_graph = ox.graph_to_gdfs(G, nodes=True, edges=True, fill_edge_geometry=True)
        G = ox.graph_from_gdfs(gdf_graph[0], gdf_graph[1])
        
        G = get_cellid(G)

        filename = f"{uuid.uuid4().hex}.graphml"
        filename_light = f"{uuid.uuid4().hex}_light.graphml"

        filepath = os.path.join(GRAPH_DIR, filename)
        filepath_light = os.path.join(GRAPH_DIR, filename_light)


        ox.save_graphml(G, filepath)

        index.append({
            "north": north,
            "south": south,
            "east": east,
            "west": west,
            "network_type": network_type,
            "file": filepath,
            "file_light": filepath_light

        })

        with open(INDEX_FILE, "w") as f:
            json.dump(index, f, indent=2)

        return G