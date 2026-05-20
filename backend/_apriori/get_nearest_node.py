import osmnx as ox
import numpy as np

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