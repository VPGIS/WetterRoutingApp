// =============================================================================
// config.js  —  Shared compile-time constants
// =============================================================================
// The first script in the load chain (config → demo → rain → routing → i18n → ui).
// Defines every value that multiple scripts need: API origin, map bounds,
// colour-ramp normalisation maximum, and the demo-mode reference timestamp.
// Must not depend on any other script.
// =============================================================================

// ── Static config ────────────────────────────────────────────────────────────
// Loaded first in the script chain (config → demo → rain → routing → i18n → ui).
// All other scripts read these constants at parse time — no imports needed.

// Peak precipitation value (mm/h) found in the demo NC file.
// Used to normalise the colour ramp in the legend and intensity badge.
// Must match the scale used when the PNG overlays were pre-rendered.
const GLOBAL_MAX = 4.96;

// ── Map bounds ────────────────────────────────────────────────────────────────
// Must match the EXTENT written into fetch_data.py when the server-side PNGs
// were rendered.  lon/lat order in Python, but Leaflet expects [[lat,lon],[lat,lon]].
// extent (Python): (lon_min, lon_max, lat_min, lat_max) = (-0.817, 18.183, 41.183, 51.183)
const BOUNDS = [
  [41.183, -0.817], // SW corner [lat_min, lon_min]
  [51.183, 18.183], // NE corner [lat_max, lon_max]
];

// FastAPI backend — started via `uvicorn backend.api:app --reload`.
// In a deployed setup this would be replaced by the actual server hostname.
const VP_API_BASE = "http://127.0.0.1:8000";

// Fallback Unix timestamp (UTC) used for the departure time / date label before
// the async /demo-rain-times call resolves and sets the real demoRefTime.
// Value is the approximate model-run time of the bundled demo NC file.
// It is intentionally a rough constant — rain.js overwrites all consumers with
// the precise value once the API responds (see loadRainData callback).
const DEMO_NC_UNIX = 1779064720;
