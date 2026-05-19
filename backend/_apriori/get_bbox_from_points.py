def get_bbox_from_points(point1, point2, buffer_km=0.0): # ALT
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