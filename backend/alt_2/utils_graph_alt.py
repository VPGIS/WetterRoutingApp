import numpy as np
import osmnx as ox

import math
import os
import json
import uuid
import time
from pathlib import Path

import xarray as xr
from scipy.spatial import cKDTree

from datetime import datetime, timezone


def get_cellid(G, lat_name="lat", lon_name="lon"):
    """
    Ordnet jeder Edge eines OSMnx-Graphen eine Rasterzelle (cell_id) zu.

    Parameter
    ----------
    G : networkx.MultiDiGraph
        OSMnx-Graph
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
    # 1. NetCDF laden   (Pfad relativ für uvicorn startup ändern, falls noch zeit)
    # ═══════════════════════════════════════════════════════════════
  
    NC_DIR = Path(__file__).resolve().parent / "data" / "NC"
    
    if not NC_DIR.exists():
        raise FileNotFoundError(f"Ordner '{NC_DIR}' existiert nicht")

    preferred_file = NC_DIR / "NC_for_Cellid.nc"
    if preferred_file.exists():
        nc_filepath = preferred_file
    else:
        nc_files = sorted(NC_DIR.glob("*.nc"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not nc_files:
            raise FileNotFoundError(f"Keine .nc Dateien in '{NC_DIR}' gefunden")
        nc_filepath = nc_files[0]

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

    # Fall 1: Adresse oder Koordinaten als String
    if isinstance(point, str):
        parts = [p.strip() for p in point.split(",")]
        if len(parts) == 2:
            try:
                lat, lon = float(parts[0]), float(parts[1])
            except ValueError:
                lat, lon = ox.geocode(point)
        else:
            lat, lon = ox.geocode(point)

    # Fall 2: Koordinaten als Liste
    elif isinstance(point, (list, tuple, np.ndarray)):
        lat, lon = float(point[0]), float(point[1])

    else:
        raise ValueError(f"{point} muss eine Adresse oder Koordinaten (lat, lon) sein")

    # Sicherheitscheck
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Ungültige Koordinaten: ({lat}, {lon})")

    return lat, lon

def get_square_bbox_from_points(point1, point2):
    """
    Erstellt eine Quadratische Bounding Box aus zwei Punkten und erweitert sie um einen Puffer in Kilometern.
    Bei kleinen sbbox wird ein grosse Buffer gegeben, bei grossen ein kleiner.
    
    Parameter
    ----------
    point1 : tuple
        Erster Punkt als (lat, lon)
    point2 : tuple
        Zweiter Punkt als (lat, lon)

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

    center_lat = (north + south) / 2

    # Umrechnung
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * math.cos(math.radians(center_lat))

    # Größe in km
    height_km = (north - south) * km_per_deg_lat
    width_km = (east - west) * km_per_deg_lon

    # Grundgröße der Box
    square_size_km = max(height_km, width_km)

    # dynamischer Buffer (automatisch kleiner bei großen Boxen)
    BASE = 0.3
    SCALE = 50.0
    factor = BASE / (1 + square_size_km / SCALE)

    square_size_km *= (1 + 2 * factor)

    # zurück in Grad
    half_lat = (square_size_km / 2) / km_per_deg_lat
    half_lon = (square_size_km / 2) / km_per_deg_lon

    center_lon = (east + west) / 2

    return (
        center_lat + half_lat,  # north
        center_lat - half_lat,  # south
        center_lon + half_lon,  # east
        center_lon - half_lon   # west
    )

def to_osmnx_bbox(bbox):
    """Konvertiert (north, south, east, west) → (west, south, east, north)"""
    north, south, east, west = bbox
    return (west, south, east, north)

def get_graph_cached(bbox, network_type="bike", size_threshold=0.5, precision=5):
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
    
    Returns
    -------
    networkx.MultiDiGraph
        Geladener oder neu erstellter OSMnx-Graph
    """

    # Standardspeicherorte relativ zum Backend, nicht zum aktuellen Arbeitsverzeichnis
    BACKEND_DIR = Path(__file__).resolve().parent
    GRAPH_DIR = BACKEND_DIR / "data" / "graphs"
    os.makedirs(GRAPH_DIR, exist_ok=True)

    INDEX_FILE = GRAPH_DIR / 'index.json'

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
        graph_file = Path(best_entry["file"])
        if not graph_file.is_absolute():
            graph_file = BACKEND_DIR / graph_file
        print(f"[route] graph cache hit: {graph_file}")
        return ox.load_graphml(graph_file)

    else:
        print(f"[route] graph cache miss: downloading OSM graph for bbox={bbox}, network_type={network_type}")
        download_started_at = time.perf_counter()
        G = ox.graph_from_bbox(to_osmnx_bbox(bbox),network_type=network_type)
        download_duration = time.perf_counter() - download_started_at
        print(
            f"[route] osm graph downloaded in {download_duration:.2f}s: "
            f"nodes={G.number_of_nodes()}, edges={G.number_of_edges()}"
        )

        # Graph wird einmal in ein gpdf umgewandelt um die leeren edge Geometrien zu füllen (mit den Nodesgeometrien)
        # anschliessend wird er wieder zurückgewandelt
        gdf_graph = ox.graph_to_gdfs(G, nodes=True, edges=True, fill_edge_geometry=True)
        G = ox.graph_from_gdfs(gdf_graph[0], gdf_graph[1])
        
        print("[route] assigning forecast grid cell ids to graph edges")
        G = get_cellid(G)

        filename = f"{uuid.uuid4().hex}.graphml"
        filename_light = f"{uuid.uuid4().hex}_light.graphml"

        filepath = GRAPH_DIR / filename
        filepath_light = GRAPH_DIR / filename_light


        ox.save_graphml(G, filepath)
        print(f"[route] graph saved to cache: {filepath}")

        index.append({
            "north": north,
            "south": south,
            "east": east,
            "west": west,
            "network_type": network_type,
            "file": str(filepath.relative_to(BACKEND_DIR)),
            "file_light": str(filepath_light.relative_to(BACKEND_DIR)),
            "created_at": str(datetime.now(timezone.utc).isoformat()),
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south]
                ]]
            }
        })

        with open(INDEX_FILE, "w") as f:
            json.dump(index, f, indent=2)

        return G
