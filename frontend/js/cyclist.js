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

  // ── RAF smooth-playback state ───────────────────────────────────────────────
  let rafId          = null;  // rAF handle — non-null ↔ smooth play is active
  let rafFrameOrigin = 0;     // integer frame where the current segment began
  let rafFrameStart  = 0;     // performance.now() at that moment
  let rafIntervalMs  = 500;   // ms per frame, kept in sync with rain.js
  let departureFrame = 0;     // animation frame index at which the ride begins
  let hasArrived        = false; // true while cyclist is at or past the destination
  // One-shot guard — prevents cyclistArrived from firing more than once per route.
  // Reset only when setCyclistRoute / clearCyclist is called (i.e. a new route).
  // This stops the timeline from immediately re-pausing when play is pressed after
  // the cyclist has already reached the destination mid-animation.
  let cyclistArrivalDone = false;

  // Colours mirror the start / end circleMarker fillColors in routing.js
  const START_COLOR = "#ef4444";
  const DEST_COLOR  = "#10b981";

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

  // ── Halo state helpers ─────────────────────────────────────────────────────────

  function getHaloEl() {
    return cyclistMarker?.getElement()?.querySelector(".cyclist-halo");
  }

  // Updates the halo ring colour:
  //   elapsed ≤ 0   → at start    (green border, matches start pin)
  //   dist ≥ total  → arrived     (red border, matches end pin; fires event once)
  //   otherwise      → riding      (no border)
  function updateHaloState(elapsed, dist) {
    const halo = getHaloEl();
    if (!halo) return;
    if (elapsed <= 0) {
      // Cyclist is at / before the departure point — reset arrival state so
      // the RAF restarts correctly and the arrival event fires again on replay.
      hasArrived         = false;
      cyclistArrivalDone = false;
      halo.style.border    = `2.5px solid ${START_COLOR}`;
      halo.style.boxShadow = `0 0 10px rgba(239,68,68,0.5)`;
    } else if (dist >= totalDist) {
      halo.style.border    = `2.5px solid ${DEST_COLOR}`;
      halo.style.boxShadow = `0 0 12px rgba(16,185,129,0.55)`;
      hasArrived = true;
      // Only dispatch once per route so pressing play again doesn't re-trigger stopPlay
      if (!cyclistArrivalDone) {
        cyclistArrivalDone = true;
        document.dispatchEvent(new CustomEvent("cyclistArrived"));
      }
    } else {
      // Mid-route — reset arrival flags so the event fires again if the user
      // scrubs back and replays from here.
      hasArrived         = false;
      cyclistArrivalDone = false;
      halo.style.border    = "none";
      halo.style.boxShadow = "none";
    }
  }

  // ── Leaflet divIcon with a simple bike SVG ──────────────────────────────────
  function makeCyclistIcon() {
    return L.divIcon({
      html: `<div class="cyclist-icon-wrap">
               <span class="cyclist-halo"></span>
               <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
                    width="22" height="22" fill="none" stroke="#0d3a6e"
                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                 <circle cx="5.5"  cy="17.5" r="3.5"/>
                 <circle cx="18.5" cy="17.5" r="3.5"/>
                 <circle cx="15"   cy="5"    r="1"/>
                 <path d="M12 17.5 10 11 5 14"/>
                 <path d="M10 11 15 5 17 11 12.5 14"/>
               </svg>
             </div>`,
      className:  "cyclist-marker",
      iconSize:   [36, 36],
      iconAnchor: [18, 18],
    });
  }

  // ── RAF helpers ─────────────────────────────────────────────────────────────

  // Mark the start of a new interpolation segment from frameIdx.
  function resetRafSegment(frameIdx) {
    rafFrameOrigin = frameIdx;
    rafFrameStart  = performance.now();
  }

  // ── Public: start smooth playback via requestAnimationFrame ────────────────
  // Called by rain.js startPlay().  Drives the marker every browser paint
  // by interpolating between integer frames based on real elapsed time.
  window.startCyclistPlay = function (frameIdx, intervalMs) {
    if (!routeCoords.length || !cyclistMarker) return;
    rafIntervalMs = intervalMs;
    if (rafId) cancelAnimationFrame(rafId);
    // Cyclist already at destination — keep the marker there and let the
    // rain setInterval drive the remaining frames without re-running the RAF.
    if (hasArrived) return;
    resetRafSegment(frameIdx);
    function tick(now) {
      // frac ∈ [0,1]: how far through the current frame interval we are.
      const frac       = Math.min((now - rafFrameStart) / rafIntervalMs, 1);
      const fractional = rafFrameOrigin + frac;
      const elapsed    = Math.max(0, fractional - departureFrame) * 3600;  // seconds since departure
      const dist       = speedMs * elapsed;
      cyclistMarker.setLatLng(posAtDist(dist));
      updateHaloState(elapsed, dist);
      if (dist >= totalDist) {
        rafId = null;  // arrived — stop RAF naturally (rain.js reacts to cyclistArrived event)
        return;
      }
      rafId = requestAnimationFrame(tick);
    }
    rafId = requestAnimationFrame(tick);
  };

  // ── Public: stop smooth playback ────────────────────────────────────────────
  window.stopCyclistPlay = function () {
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  };

  // ── Public: initialise or update route ─────────────────────────────────────
  window.setCyclistRoute = function (geojson, speedKmh, depFrame) {
    routeCoords = extractCoords(geojson);
    if (routeCoords.length < 2) {
      window.clearCyclist();
      return;
    }

    cumDist            = buildCumDist(routeCoords);
    totalDist          = cumDist[cumDist.length - 1];
    speedMs            = (speedKmh || 20) / 3.6;
    departureFrame     = depFrame || 0;
    hasArrived         = false;
    cyclistArrivalDone = false;

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
    // Set initial halo to “at start” state
    updateHaloState(0, 0);
  };

  // ── Public: reposition marker for animation frame idx ──────────────────────
  // Called by rain.js showFrame() on every frame change (slider drag or step).
  // Snaps the marker to the exact integer-frame position AND, when RAF playback
  // is active, resets the interpolation segment so the next smooth pass starts
  // from the correct origin.
  window.updateCyclist = function (frameIdx) {
    if (!cyclistMarker || !routeCoords.length || speedMs <= 0) return;
    const elapsed = Math.max(0, frameIdx - departureFrame) * 3600;  // seconds since departure
    const dist    = speedMs * elapsed;
    cyclistMarker.setLatLng(posAtDist(dist));
    updateHaloState(elapsed, dist);
    if (rafId !== null) resetRafSegment(frameIdx);
  };

  // ── Public: update speed and reposition marker at current frame ────────────
  // Called by routing.js when the speed slider changes so the cyclist's
  // position updates immediately without a full route recalculation.
  window.updateCyclistSpeed = function (speedKmh, frameIdx) {
    if (!routeCoords.length) return;
    speedMs = (speedKmh || 20) / 3.6;
    // Speed change shifts the arrival point — reset so the arrival event
    // fires at the correct moment on the next playback.
    hasArrived         = false;
    cyclistArrivalDone = false;
    if (cyclistMarker && frameIdx !== undefined) {
      window.updateCyclist(frameIdx);
    }
  };

  // ── Public: remove marker and reset state ──────────────────────────────────
  window.clearCyclist = function () {
    window.stopCyclistPlay();  // cancel any running RAF loop first
    if (cyclistMarker) {
      if (window.map) window.map.removeLayer(cyclistMarker);
      cyclistMarker = null;
    }
    routeCoords        = [];
    cumDist            = [];
    totalDist          = 0;
    speedMs            = 0;
    departureFrame     = 0;
    hasArrived         = false;
    cyclistArrivalDone = false;
  };
})();
