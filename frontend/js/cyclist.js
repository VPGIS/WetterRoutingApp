// =============================================================================
// cyclist.js  —  Animated cyclist marker that follows the calculated route
// =============================================================================
// Public API (all attached to window so other modules can call without import):
//   window.setCyclistRoute(geojson, speedKmh)
//       Called by routing.js after a successful route fetch.
//       Builds a flat coordinate array + cumulative-distance lookup table and
//       places the marker at the route start.
//
//   window.updateCyclist(frameIdx)
//       Called by rain.js showFrame(idx) on every frame change.
//       Repositions the marker to: distance = speedMs × (frameIdx × 3600 s).
//       Clamps at the destination once arrived.
//
//   window.clearCyclist()
//       Called by routing.js before a new route fetch.
//       Removes the marker and resets all internal state.
//
// The GeoJSON returned by the backend is a FeatureCollection of individual
// edge LineStrings that chain together — each feature's first coordinate
// equals the last coordinate of the previous one.  extractCoords() skips
// that shared junction point so the flat array has no duplicates.
// =============================================================================

(function () {
  "use strict";

  // ── Internal state ──────────────────────────────────────────────────────────
  let cyclistMarker = null;
  let routeCoords  = [];   // [[lon, lat], ...] flattened & deduplicated
  let cumDist      = [];   // cumulative metres, same length as routeCoords
  let totalDist    = 0;    // metres — total route length
  let speedMs      = 0;    // m/s — captured at route-calculation time

  // ── Haversine distance (metres) between two [lon, lat] points ──────────────
  function haversine(a, b) {
    const R     = 6_371_000;
    const toRad = (x) => (x * Math.PI) / 180;
    const dLat  = toRad(b[1] - a[1]);
    const dLon  = toRad(b[0] - a[0]);
    const h =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  // ── Extract flat [lon, lat] array from a FeatureCollection of LineStrings ──
  // The route GeoJSON is one Feature per OSM edge.  Adjacent edges share their
  // junction vertex, so we drop the duplicate first point of every feature
  // after the first.
  function extractCoords(geojson) {
    const features =
      geojson.type === "FeatureCollection" ? geojson.features : [geojson];
    const coords = [];
    for (const f of features) {
      const geom = f.geometry || f;
      if (!geom) continue;
      let pts = [];
      if      (geom.type === "LineString")      pts = geom.coordinates;
      else if (geom.type === "MultiLineString") pts = geom.coordinates.flat(1);
      const start = coords.length > 0 ? 1 : 0; // skip junction duplicate
      for (let i = start; i < pts.length; i++) coords.push(pts[i]);
    }
    return coords;
  }

  // ── Build cumulative distance lookup table ──────────────────────────────────
  function buildCumDist(coords) {
    const cum = [0];
    for (let i = 1; i < coords.length; i++)
      cum.push(cum[i - 1] + haversine(coords[i - 1], coords[i]));
    return cum;
  }

  // ── Interpolate [lat, lon] (Leaflet order) at distance d along the route ───
  function posAtDist(d) {
    if (d <= 0 || routeCoords.length === 0) {
      const [lon, lat] = routeCoords[0];
      return [lat, lon];
    }
    if (d >= totalDist) {
      const [lon, lat] = routeCoords[routeCoords.length - 1];
      return [lat, lon];
    }
    // Linear scan — typically < 1 000 points, fast enough
    for (let i = 1; i < cumDist.length; i++) {
      if (cumDist[i] >= d) {
        const t          = (d - cumDist[i - 1]) / (cumDist[i] - cumDist[i - 1]);
        const [lon0, lat0] = routeCoords[i - 1];
        const [lon1, lat1] = routeCoords[i];
        return [lat0 + t * (lat1 - lat0), lon0 + t * (lon1 - lon0)];
      }
    }
    const [lon, lat] = routeCoords[routeCoords.length - 1];
    return [lat, lon];
  }

  // ── Leaflet divIcon with a simple bike SVG ──────────────────────────────────
  function makeCyclistIcon() {
    return L.divIcon({
      html: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
                  width="26" height="26" fill="none" stroke="#0d3a6e"
                  stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
               <circle cx="5.5"  cy="17.5" r="3.5"/>
               <circle cx="18.5" cy="17.5" r="3.5"/>
               <circle cx="15"   cy="5"    r="1"/>
               <path d="M12 17.5 10 11 5 14"/>
               <path d="M10 11 15 5 17 11 12.5 14"/>
             </svg>`,
      className:  "cyclist-marker",
      iconSize:   [26, 26],
      iconAnchor: [13, 13],
    });
  }

  // ── Public: initialise or update route ─────────────────────────────────────
  window.setCyclistRoute = function (geojson, speedKmh) {
    routeCoords = extractCoords(geojson);
    if (routeCoords.length < 2) {
      window.clearCyclist();
      return;
    }

    cumDist   = buildCumDist(routeCoords);
    totalDist = cumDist[cumDist.length - 1];
    speedMs   = (speedKmh || 20) / 3.6;

    const [lon, lat] = routeCoords[0];
    if (!cyclistMarker) {
      cyclistMarker = L.marker([lat, lon], {
        icon:          makeCyclistIcon(),
        zIndexOffset:  500,
        interactive:   false,
      }).addTo(window.map);
    } else {
      cyclistMarker.setLatLng([lat, lon]);
    }
  };

  // ── Public: reposition marker for animation frame idx ──────────────────────
  // Each frame represents 1 hour of elapsed time from the route start.
  window.updateCyclist = function (frameIdx) {
    if (!cyclistMarker || !routeCoords.length || speedMs <= 0) return;
    const elapsed = frameIdx * 3600;          // seconds
    const dist    = speedMs * elapsed;        // metres
    cyclistMarker.setLatLng(posAtDist(dist));
  };

  // ── Public: remove marker and reset state ──────────────────────────────────
  window.clearCyclist = function () {
    if (cyclistMarker) {
      if (window.map) window.map.removeLayer(cyclistMarker);
      cyclistMarker = null;
    }
    routeCoords = [];
    cumDist     = [];
    totalDist   = 0;
    speedMs     = 0;
  };
})();
