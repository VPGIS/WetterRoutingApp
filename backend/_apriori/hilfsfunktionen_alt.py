import osmnx as ox
import numpy as np

import os
import time
from pathlib import Path


import xarray as xr
import numpy as np
from scipy.spatial import cKDTree

def get_nc_file(start_time, parentfolder='nc_folder', valid_time=33*3600):
    """
    Gibt das gültige NC-File mit dem neuesten Zeitstempel zurück.
    
    Parameter
    ----------
    start_time : float
        Referenz-Zeitstempel (z.B. aktuelle Zeit mit time.time())
    parentfolder : str, optional
        Pfad zum Ordner mit den NC-Files (default: 'nc_folder')
    valid_time : int, optional
        Gültigkeitsdauer in Sekunden (default: 33 Stunden = 118800 Sekunden)
    
    Returns
    -------
    str or None
        Pfad zum neuesten gültigen NC-File, oder None wenn keines gültig ist
    """
    
    # Sicherstellen, dass der Ordner existiert
    if not os.path.exists(parentfolder):
        raise FileNotFoundError(f"Ordner '{parentfolder}' existiert nicht")
    valid_files = []
    
    # Alle .nc-Dateien im Ordner durchsuchen
    for filename in os.listdir(parentfolder):
        if filename.endswith('.nc'):

            # Zeitstempel aus dem Dateinamen extrahieren
            # Erwartet Format: "{timestamp}.nc" z.B. "1234567890.nc"
            try:
                # Alles vor .nc entfernen und zu Integer konvertieren
                timestamp_str = filename[:-3]  # Entfernt ".nc"
                file_timestamp = int(timestamp_str)
            except ValueError:
                # Wenn Zeitstempel nicht parsbar ist, Datei überspringen
                continue
        
            # Prüfen ob Datei noch gültig ist
            age = start_time - file_timestamp
            if 0 <= age <= valid_time:
                full_path = os.path.join(parentfolder, filename)
                valid_files.append((file_timestamp, full_path))
            
    
    # Neuste Datei oder None
    if not valid_files:
        return None
    else:
        newest_files = max(valid_files, key=lambda x: x[0])
        return newest_files[1]
    


def get_nearest_node(G, point):
    """
    Gibt die nächste Node zurück, egal ob der Point als Adresse oder Koordinate definiert wurde.

    Parameter
    ----------
    G : networkx.MultiDiGraph
        OSMnx-Graph
    point : str | tuple | list | np.ndarray
        Adresse (String) ODER Koordinaten im Format (lat, lon)

    Returns
    -------
    nearest_node : int
        ID der nächstgelegenen Node im Graph
    """

    # Fall 1: Adresse (String)
    if isinstance(point, str):
        lat, lon = ox.geocode(point)

    # Fall 2: Koordinaten
    elif isinstance(point, (list, tuple, np.ndarray)):
        if len(point) != 2:
            raise ValueError(f"{point} muss genau 2 Werte enthalten (lat, lon)")
        lat, lon = float(point[0]), float(point[1])

    else:
        raise ValueError(f"{point} muss eine Adresse oder Koordinaten (lat, lon) sein")

    # Sicherheitscheck
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Ungültige Koordinaten: ({lat}, {lon})")

    # Achtung: X = longitude, Y = latitude
    nearest_node = ox.distance.nearest_nodes(G, X=lon, Y=lat)

    return nearest_node


def get_cellid(G, nc_filepath, lat_name="lat", lon_name="lon"):
    """
    Ordnet jeder Edge eines OSMnx-Graphen eine Rasterzelle (cell_id) zu.

    Parameter
    ----------
    G : networkx.MultiDiGraph
        OSMnx-Graph
    nc_filepath: str
        Pfad zur NetCDF-Datei
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


def get_forecast(G, ds, u, v, k,
                      lead_idx=0,
                      eps_idx=0,
                      ref_time_idx=0,
                      var_name="TOT_PREC"):
    """
    Extrahiert den Forecast-Wert (z.B. Niederschlag) für eine einzelne Edge im OSMnx-Graphen.

    Diese Funktion verbindet:
    - OSMnx-Graph (Straßennetz)
    - Rasterdaten aus einem xarray NetCDF Dataset
    - vorher berechnetes Mapping (cell_i, cell_j)

    Parameter
    ----------
    G : networkx.MultiDiGraph
        OSMnx-Graph, bei dem jede Edge bereits eine Rasterzuordnung besitzt
        ('cell_i', 'cell_j')

    ds : xarray.Dataset
        Geladenes NetCDF-Dataset mit Wetterdaten

    u, v, k : int
        Eindeutige Edge-Identifikation im Graph:
        - u = Startknoten
        - v = Zielknoten
        - k = Edge-Key (bei parallelen Straßen)

    lead_idx : int
        Index der Vorhersagezeit (Lead Time), z.B. 0 = erste Stunde

    eps_idx : int
        Ensemble-Mitglied (falls vorhanden)

    ref_time_idx : int
        Startzeit-Index des Modelllaufs

    var_name : str
        Name der Wettervariablen im Dataset (z.B. "TOT_PREC")

    Returns
    -------
    float
        Wetterwert (z.B. Niederschlag) für diese Edge und Zeitkombination
    """

    # ═══════════════════════════════════════════════
    # 1. Edge aus dem Graphen holen
    # ═══════════════════════════════════════════════
    edge = G.edges[u, v, k]

    # Sicherheitscheck: wurde die Rasterzuordnung bereits berechnet?
    if "cell_i" not in edge or "cell_j" not in edge:
        raise ValueError(
            "Edge hat keine cell_i/cell_j. Bitte zuerst get_cellid() ausführen."
        )

    # Rasterposition der Straße im Wettergitter
    i = edge["cell_i"]  # y-Koordinate im Raster
    j = edge["cell_j"]  # x-Koordinate im Raster

    # ═══════════════════════════════════════════════
    # 2. Zugriff auf das Wetter-Dataset
    # ═══════════════════════════════════════════════
    data = ds[var_name]

    # ═══════════════════════════════════════════════
    # 3. Sauberes xarray Indexing über Dimensionen
    #    (robust, unabhängig von interner Reihenfolge)
    # ═══════════════════════════════════════════════
    value = data.isel(
        eps=eps_idx,
        ref_time=ref_time_idx,
        lead_time=lead_idx,
        y=i,
        x=j
    ).values

    # ═══════════════════════════════════════════════
    # 4. Rückgabe als Python float
    # ═══════════════════════════════════════════════
    return float(value)


def get_forecast_all(G, ds, u, v, k,
                     eps_idx=0,
                     ref_time_idx=0,
                     var_name="TOT_PREC"):
    """
    Gibt die komplette Zeitreihe (alle lead_times) für eine Edge zurück.

    Parameter
    ----------
    G : networkx.MultiDiGraph
        OSMnx-Graph mit 'cell_i' und 'cell_j'
    ds : xarray.Dataset
        Wetter-Dataset
    u, v, k : int
        Edge-Identifier im Graph
    eps_idx : int
        Ensemble-Mitglied
    ref_time_idx : int
        Modelllauf
    var_name : str
        Name der Wettervariable

    Returns
    -------
    np.ndarray
        1D Array: (lead_time,) → Zeitreihe der Regenwerte
    """

    # ═══════════════════════════════════════════════
    # 1. Edge holen
    # ═══════════════════════════════════════════════
    edge = G.edges[u, v, k]

    if "cell_i" not in edge or "cell_j" not in edge:
        raise ValueError("Edge hat keine cell_i/cell_j → zuerst get_cellid() ausführen")

    i = edge["cell_i"]
    j = edge["cell_j"]

    # ═══════════════════════════════════════════════
    # 2. Dataset auswählen
    # ═══════════════════════════════════════════════
    data = ds[var_name]

    # ═══════════════════════════════════════════════
    # 3. Alle lead_times extrahieren
    #    → Ergebnis: (lead_time,)
    # ═══════════════════════════════════════════════
    series = data.isel(
        eps=eps_idx,
        ref_time=ref_time_idx,
        y=i,
        x=j
    ).values

    return series


import numpy as np
import pandas as pd

def grid_to_table(ds, var_name="TOT_PREC", lead_idx=0, eps_idx=0, ref_time_idx=0):
    """
    Konvertiert ein 2D Raster (y, x) aus einem xarray Dataset
    in eine tabellarische Form mit cell_id.

    Parameter
    ----------
    ds : xarray.Dataset
        Wetter-Dataset
    var_name : str
        Name der Variable
    lead_idx : int
        Forecast-Zeitindex
    eps_idx : int
        Ensemble Index
    ref_time_idx : int
        Referenzzeit Index

    Returns
    -------
    pandas.DataFrame
        Tabelle mit:
        - cell_id
        - y
        - x
        - value
    """

    data = ds[var_name]

    # ═══════════════════════════════════════════════
    # 1. 2D Slice extrahieren
    # ═══════════════════════════════════════════════
    grid = data.isel(
        eps=eps_idx,
        ref_time=ref_time_idx,
        lead_time=lead_idx
    ).values  # shape (y, x)

    ny, nx = grid.shape

    # ═══════════════════════════════════════════════
    # 2. Indizes erzeugen
    # ═══════════════════════════════════════════════
    y_idx, x_idx = np.meshgrid(
        np.arange(ny),
        np.arange(nx),
        indexing="ij"
    )

    y_flat = y_idx.ravel()
    x_flat = x_idx.ravel()
    values = grid.ravel()

    # ═══════════════════════════════════════════════
    # 3. cell_id erzeugen
    # ═══════════════════════════════════════════════
    cell_id = np.char.add(y_flat.astype(str), "_")
    cell_id = np.char.add(cell_id, x_flat.astype(str))

    # ═══════════════════════════════════════════════
    # 4. DataFrame bauen
    # ═══════════════════════════════════════════════
    df = pd.DataFrame({
        "cell_id": cell_id,
        "y": y_flat,
        "x": x_flat,
        "value": values
    })

    return df