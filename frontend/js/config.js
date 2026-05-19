// ── Static config ────────────────────────────────────────────────────────────
const GLOBAL_MAX = 4.96;

// ── Map bounds (must match fetch_data.py EXTENT) ────────────────────────────
// extent = (lon_min, lon_max, lat_min, lat_max) = (-0.817, 18.183, 41.183, 51.183)
const BOUNDS = [
  [41.183, -0.817],
  [51.183, 18.183],
]; // [[lat_min,lon_min],[lat_max,lon_max]]

const VP_API_BASE = "http://127.0.0.1:8000";
const DEMO_NC_UNIX = 1779064720; // fallback Unix timestamp before API loads
