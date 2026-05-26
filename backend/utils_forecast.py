import numpy as np


def compute_rain_adjusted_cost(length, forecast, rainresistence):
    # Regenmenge vorbereiten: negative Werte werden als 0 behandelt
    rain_amount = max(float(forecast), 0.0)

    # Wenn kein Regen vorhergesagt ist, bleibt die Strecke unverändert
    if rain_amount == 0.0:
        return length

    if rainresistence == "lowest":  # bei Regen wird die Strecke komplett vermieden
        return 99999999

    if rainresistence == "highest":  # Regen hat keinen Einfluss auf die Kosten
        return length

    # Je geringer die Regenresistenz, desto höher werden Regenmengen gewichtet
    if rainresistence == "high":
        multiplier = 25.0
        exponent = 1.0
    elif rainresistence == "medium":
        multiplier = 100.0
        exponent = 1.2
    elif rainresistence == "low":
        multiplier = 400.0
        exponent = 1.4
    else:
        raise ValueError("rainresistence must be 'lowest' 'low', 'medium', 'high' or 'highest'")

    # Dadurch bleiben die Kosten mindestens so hoch wie die ursprüngliche Länge.
    return length * (1.0 + multiplier * (rain_amount ** exponent))


def _get_lead_hours(file_timestamp, target_timestamp):
    lead_hours = (target_timestamp - file_timestamp) / 3600.0

    if lead_hours < 0:
        raise ValueError("target_timestamp liegt vor Modellstart")

    return lead_hours


def _clamp_lead_hours(da, lead_hours):
    lead_values = da["lead_time"].values.astype(float)
    return min(max(float(lead_hours), float(lead_values.min())), float(lead_values.max()))


def get_forecast_grid(
    ds,
    file_timestamp,
    target_timestamp,
    eps_idx=0,
    ref_time_idx=0,
    var_name="hourly_rain",
    interpolate=True,
):
    """
    Gibt das komplette Forecast-Raster als NumPy-Array zurück.

    Dadurch wird xarray nur einmal pro Zeitstufe verwendet. Einzelne Kanten
    können danach sehr schnell mit forecast_grid[cell_i, cell_j] gelesen werden.
    """
    da = ds[var_name]

    if "lead_time" not in da.dims:
        raise KeyError(f"lead_time fehlt in {da.dims}")

    lead_hours = _clamp_lead_hours(da, _get_lead_hours(file_timestamp, target_timestamp))

    if interpolate:
        da_t = da.interp(lead_time=lead_hours)
    else:
        lead_values = da["lead_time"].values.astype(float)
        lead_idx = int(np.abs(lead_values - lead_hours).argmin())
        da_t = da.isel(lead_time=lead_idx)

    if "eps" in da_t.dims:
        da_t = da_t.isel(eps=eps_idx)
    if "ref_time" in da_t.dims:
        da_t = da_t.isel(ref_time=ref_time_idx)

    return da_t.values


def get_forecast_from_grid(edge, forecast_grid):
    if "cell_i" not in edge or "cell_j" not in edge:
        raise ValueError("Edge hat keine cell_i/cell_j")

    i = int(edge["cell_i"])
    j = int(edge["cell_j"])
    return float(forecast_grid[i, j])

# deprecated
def get_forecast(
    G,
    ds,
    u,
    v,
    k,
    file_timestamp,
    target_timestamp,
    eps_idx=0,
    ref_time_idx=0,
    var_name="hourly_rain",
    interpolate=True,
):
    """
    Extrahiert den Forecast-Wert fuer eine Edge im OSMnx-Graphen.

    Diese Funktion bleibt für bestehende Aufrufe erhalten. Für schnelle
    Schleifen sollte get_forecast_grid einmalig aufgerufen und anschliessend
    get_forecast_from_grid verwendet werden.
    """
    forecast_grid = get_forecast_grid(
        ds,
        file_timestamp=file_timestamp,
        target_timestamp=target_timestamp,
        eps_idx=eps_idx,
        ref_time_idx=ref_time_idx,
        var_name=var_name,
        interpolate=interpolate,
    )
    return get_forecast_from_grid(G.edges[u, v, k], forecast_grid)
