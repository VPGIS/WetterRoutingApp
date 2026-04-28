def get_forecast_alt(G, ds, u, v, k,
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

