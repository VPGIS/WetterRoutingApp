import numpy as np
import xarray as xr


def compute_rain_adjusted_cost(length, forecast, sensitivity):
    rain_amount = max(float(forecast), 0.0)

    if rain_amount == 0.0:
        return length

    rain_amount = min(rain_amount, 10.0)

    if sensitivity in (None, '', 'none', 'off', 'no_rain'):
        multiplier = 2500.0
        exponent = 1.8
    elif sensitivity == 'low':
        multiplier = 25.0
        exponent = 1.0
    elif sensitivity == 'medium':
        multiplier = 100.0
        exponent = 1.2
    elif sensitivity == 'high':
        multiplier = 400.0
        exponent = 1.4
    else:
        raise ValueError("sensitivity must be 'low', 'medium', or 'high'")

    return length * (1.0 + multiplier * (rain_amount ** exponent))


def get_forecast(
    G, ds, u, v, k,
    file_timestamp,
    target_timestamp,
    eps_idx=0,
    ref_time_idx=0,
    var_name="TOT_PREC",
    interpolate=True
):
    """
    Extrahiert den Forecast-Wert für eine Edge im OSMnx-Graphen.

    Unterstützt:
    - lineare Interpolation über lead_time
    - oder diskrete Rundung auf den nächsten Zeitschritt
    """

    # ═══════════════════════════════════════════════
    # 1. Edge + Raster
    # ═══════════════════════════════════════════════
    edge = G.edges[u, v, k]

    if "cell_i" not in edge or "cell_j" not in edge:
        raise ValueError("Edge hat keine cell_i/cell_j")

    i = int(edge["cell_i"])
    j = int(edge["cell_j"])

    # ═══════════════════════════════════════════════
    # 2. Zeit → lead_time
    # ═══════════════════════════════════════════════
    lead_hours = (target_timestamp - file_timestamp) / 3600.0

    if lead_hours < 0:
        raise ValueError("target_timestamp liegt vor Modellstart")

    da = ds[var_name]

    if "lead_time" not in da.dims:
        raise KeyError(f"lead_time fehlt in {da.dims}")

    # ═══════════════════════════════════════════════
    # 3. Interpolation ODER Rundung
    # ═══════════════════════════════════════════════
    if interpolate:
        da_t = da.interp(lead_time=lead_hours)
    else:
        lead_idx = int(np.round(lead_hours))
        da_t = da.isel(lead_time=lead_idx)

    # ═══════════════════════════════════════════════
    # 4. Raum + Ensemble + Zeit extrahieren
    # ═══════════════════════════════════════════════
    value = da_t.isel(
        eps=eps_idx,
        ref_time=ref_time_idx,
        y=i,
        x=j
    ).item()

    return float(value)