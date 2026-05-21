// =============================================================================
// routing.js  —  Geocoding, map interaction, departure time, route calculation
// =============================================================================
// Responsibilities:
//   • Reverse- and forward-geocodes locations via the Nominatim API.
//   • Manages a two-phase map-click state machine (click 1 = start,
//     click 2 = end, subsequent = active input box).
//   • Handles the departure date/time picker: date label, day offset toggle,
//     CEST→UTC parsing, and snap-to-NC-ref-time in demo mode.
//   • Calls /WAPapi/v1/route with the selected parameters and renders the
//     returned GeoJSON route as a coloured polyline on the Leaflet map.
//   • Provides GPX import (/data_import) and export (/data_export) via the
//     backend (no client-side GPX parsing).
//   • Exposes `window.updateDepartureDateLabel`, `window.syncDemoTime`, and
//     `window.resetLiveTime` so demo.js / rain.js can trigger UI updates.
//
// Depends on: config.js (VP_API_BASE, DEMO_NC_UNIX, BOUNDS),
//             demo.js (demoMode, getDemoRefTime), i18n.js (window.t)
// =============================================================================

// ── Route layer globals ────────────────────────────────────────────────────────
// These must be module-level (not inside DOMContentLoaded) so the map click
// handler can remove/replace them even after the initial setup phase is over.
let vpStartMarker = null;
let vpEndMarker = null;
let vpRouteLayer = null;

document.addEventListener("DOMContentLoaded", () => {
  const routeStartInput = document.getElementById("route_start");
  const routeEndInput = document.getElementById("route_end");

  // ── Geocoding helpers ───────────────────────────────────────────────────────────
  // Both functions use the public Nominatim API (OpenStreetMap).  No API key
  // is required, but the usage policy requires a valid User-Agent and limits
  // to 1 req/s — acceptable for a single-user local deployment.

  // Converts lat/lon to a display address (street + house number + city).
  // Falls back to "lat, lon" string if Nominatim returns nothing useful.
  const reverseGeocode = async (lat, lon) => {
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=18&addressdetails=1`,
      );
      const data = await res.json();
      if (data && data.address) {
        const street = data.address.road || "";
        const house = data.address.house_number || "";
        const city =
          data.address.city || data.address.town || data.address.village || "";
        let addr = `${street} ${house}, ${city}`
          .trim()
          .replace(/^,/, "")
          .replace(/,$/, "")
          .trim();
        if (!addr || addr === ",")
          addr = data.display_name.split(",").slice(0, 2).join(", ");
        return addr;
      }
    } catch (e) {
      console.error(e);
    }
    return `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  };

  // Converts a text query to {lat, lon}.
  // Detects raw "lat, lon" strings first to avoid an unnecessary network
  // round-trip for coordinates pasted from other tools.
  const forwardGeocode = async (query) => {
    const coordsMatch = query.match(
      /^\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*$/,
    );
    if (coordsMatch)
      return {
        lat: parseFloat(coordsMatch[1]),
        lon: parseFloat(coordsMatch[2]),
      };
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`,
      );
      const data = await res.json();
      if (data && data.length > 0)
        return {
          lat: parseFloat(data[0].lat),
          lon: parseFloat(data[0].lon),
        };
    } catch (e) {
      console.error(e);
    }
    return null;
  };

  // Waits for Leaflet to be available before attaching map event handlers.
  // Leaflet is loaded via CDN with `defer`, so it may not be ready at
  // DOMContentLoaded.  Polling is simpler than a custom event here.
  const initMapHooks = () => {
    if (typeof map === "undefined" || typeof L === "undefined") {
      setTimeout(initMapHooks, 200);
      return;
    }

    // ── Map click – click-phase state machine ─────────────────────────────────
    // The first two map clicks after load are guided (click 1 = start,
    // click 2 = end) so new users don't have to select an input box first.
    // After both points are set, subsequent clicks fill whichever input box
    // was last focused (activeInputBox).  Focusing an input box at any time
    // fast-forwards directly to phase 2.
    //
    //  clickPhase 0 → waiting for start click
    //  clickPhase 1 → waiting for end click
    //  clickPhase 2 → guided phase complete; rely on activeInputBox
    let clickPhase = 0;
    let activeInputBox = "start";

    routeStartInput.addEventListener("focus", () => {
      activeInputBox = "start";
      clickPhase = 2;
    });
    routeEndInput.addEventListener("focus", () => {
      activeInputBox = "end";
      clickPhase = 2;
    });
    routeStartInput.addEventListener("click", () => {
      activeInputBox = "start";
      clickPhase = 2;
    });
    routeEndInput.addEventListener("click", () => {
      activeInputBox = "end";
      clickPhase = 2;
    });

    const updateUIMarkers = () => {
      const startUI = document.getElementById("start-marker-ui");
      const endUI = document.getElementById("end-marker-ui");
      if (startUI)
        startUI.style.display = routeStartInput.value.trim() ? "block" : "none";
      if (endUI)
        endUI.style.display = routeEndInput.value.trim() ? "block" : "none";
    };
    window.updateUIMarkers = updateUIMarkers;

    // CLICKING THE MAP
    window.zoomToMarker = (type) => {
      if (type === "start" && vpStartMarker) {
        map.flyTo(vpStartMarker.getLatLng(), 14, {
          animate: true,
          duration: 1,
        });
      } else if (type === "end" && vpEndMarker) {
        map.flyTo(vpEndMarker.getLatLng(), 14, {
          animate: true,
          duration: 1,
        });
      }
    };
    map.on("click", async (e) => {
      const { lat, lng } = e.latlng;

      let isStart;
      if (clickPhase === 0) {
        isStart = true;
        clickPhase = 1;
        activeInputBox = "end"; // Automatically switch active box to End for the next click
      } else if (clickPhase === 1) {
        isStart = false;
        clickPhase = 2; // Phase complete
        activeInputBox = "end"; // Leave it at end, or require them to click boxes from now on
      } else {
        // Phase complete. Strictly use whichever box they focused last.
        isStart = activeInputBox === "start";
      }

      // Keep highlight in sync with the box being filled by this click
      if (typeof setActiveHighlight !== "undefined")
        setActiveHighlight(isStart ? "start" : "end");

      const targetInput = isStart ? routeStartInput : routeEndInput;

      targetInput.value = window.t("resolving");

      const address = await reverseGeocode(lat, lng);
      targetInput.value = address;
      targetInput.dataset.lat = lat;
      targetInput.dataset.lon = lng;

      if (isStart) {
        if (vpStartMarker) map.removeLayer(vpStartMarker);
        vpStartMarker = L.circleMarker([lat, lng], {
          color: "#000",
          weight: 1,
          fillColor: "#10b981",
          radius: 6,
          fillOpacity: 0.9,
          pane: "route",
        }).addTo(map);
      } else {
        if (vpEndMarker) map.removeLayer(vpEndMarker);
        vpEndMarker = L.circleMarker([lat, lng], {
          color: "#000",
          weight: 1,
          fillColor: "#ef4444",
          radius: 6,
          fillOpacity: 0.9,
          pane: "route",
        }).addTo(map);
      }

      updateUIMarkers();
    });

    // ── Address text entry ───────────────────────────────────────────────────
    // Fires on `change` (blur after edit) or Enter key to avoid spamming
    // Nominatim on every keystroke.  Clears the stored lat/lon on empty input
    // so the validation check in calculate can catch missing points.
    const handleTextEntry = async (e) => {
      const inputEl = e.target;
      const query = inputEl.value.trim();
      const isStart = inputEl === routeStartInput;

      if (!query) {
        inputEl.dataset.lat = "";
        inputEl.dataset.lon = "";
        if (isStart && vpStartMarker) {
          map.removeLayer(vpStartMarker);
          vpStartMarker = null;
        }
        if (!isStart && vpEndMarker) {
          map.removeLayer(vpEndMarker);
          vpEndMarker = null;
        }
        window.updateUIMarkers();
        return;
      }

      const coords = await forwardGeocode(query);
      if (coords) {
        inputEl.dataset.lat = coords.lat;
        inputEl.dataset.lon = coords.lon;

        if (isStart) {
          if (vpStartMarker) map.removeLayer(vpStartMarker);
          vpStartMarker = L.circleMarker([coords.lat, coords.lon], {
            color: "#000",
            weight: 1,
            fillColor: "#10b981",
            radius: 6,
            fillOpacity: 0.9,
            pane: "route",
          }).addTo(map);
        } else {
          if (vpEndMarker) map.removeLayer(vpEndMarker);
          vpEndMarker = L.circleMarker([coords.lat, coords.lon], {
            color: "#000",
            weight: 1,
            fillColor: "#ef4444",
            radius: 6,
            fillOpacity: 0.9,
            pane: "route",
          }).addTo(map);
        }
        map.setView([coords.lat, coords.lon], 13, { animate: true });
      }
      updateUIMarkers();
    };

    const handleEnterKey = (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        e.target.blur(); // Trigger 'change' event
      }
    };

    routeStartInput.addEventListener("change", handleTextEntry);
    routeEndInput.addEventListener("change", handleTextEntry);
    routeStartInput.addEventListener("keyup", handleEnterKey);
    routeEndInput.addEventListener("keyup", handleEnterKey);
  };

  // Boot Map Hooks
  initMapHooks();

  // ── OTHER UI BINDINGS ──────────────────────────────────────────────────────

  // Initialise the time input to the current local time if the browser
  // didn't restore a previous value (e.g. on a fresh page load).
  const timeStartInput = document.getElementById("time_start");
  if (timeStartInput && !timeStartInput.value) {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, "0");
    const minutes = String(now.getMinutes()).padStart(2, "0");
    timeStartInput.value = `${hours}:${minutes}`;
  }

  // ── Departure date label ─────────────────────────────────────────────────────
  // Shows "Heute / Today / Aujourd’hui, DD.MM.YYYY" next to the time picker.
  // In demo mode the base date comes from demoRefTime (the real NC ref time
  // once the API has responded) so the label matches the DEMO badge exactly.
  // Europe/Zurich timezone is used via Intl so the date is correct regardless
  // of where the browser is running.
  let departureDayOffset = 0; // 0 = today, 1 = tomorrow
  const departureDateEl = document.getElementById("departure-date");

  window.updateDepartureDateLabel = function updateDepartureDateLabel() {
    if (!departureDateEl) return;
    let baseMs;
    if (demoMode) {
      const ref = window.getDemoRefTime && window.getDemoRefTime();
      baseMs = ref ? ref.getTime() : DEMO_NC_UNIX * 1000;
    } else {
      baseMs = Date.now();
    }
    const d = new Date(baseMs + departureDayOffset * 86400000);
    const zurichFmt = new Intl.DateTimeFormat("de-CH", {
      timeZone: "Europe/Zurich",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
    const parts = {};
    zurichFmt.formatToParts(d).forEach((p) => (parts[p.type] = p.value));
    const label =
      departureDayOffset === 0 ? window.t("today") : window.t("tomorrow");
    departureDateEl.textContent =
      label + ", " + parts.day + "." + parts.month + "." + parts.year;
  };

  document.querySelectorAll("#day-toggle .day-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document
        .querySelectorAll("#day-toggle .day-btn")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      departureDayOffset = Number(btn.dataset.offset);
      updateDepartureDateLabel();
    });
  });
  updateDepartureDateLabel();

  // Exposed so demo.js can snap the time input to the NC ref time in Europe/Zurich
  window.syncDemoTime = function syncDemoTime() {
    if (!timeStartInput) return;
    const ref =
      (window.getDemoRefTime && window.getDemoRefTime()) ||
      new Date(DEMO_NC_UNIX * 1000);
    const zurichFmt = new Intl.DateTimeFormat("de-CH", {
      timeZone: "Europe/Zurich",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
    const parts = {};
    zurichFmt.formatToParts(ref).forEach((p) => (parts[p.type] = p.value));
    timeStartInput.value = parts.hour + ":" + parts.minute;
  };

  // Exposed so demo.js can restore the time input to current local time on exit
  window.resetLiveTime = function resetLiveTime() {
    if (!timeStartInput) return;
    const now = new Date();
    timeStartInput.value =
      String(now.getHours()).padStart(2, "0") +
      ":" +
      String(now.getMinutes()).padStart(2, "0");
  };

  document.querySelectorAll("#routing_model_toggle .day-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document
        .querySelectorAll("#routing_model_toggle .day-btn")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  // ── Active input highlight ────────────────────────────────────────────────
  // Highlight persists on the last-used field — cleared only when another
  // field takes over. route_start is highlighted on load.
  const highlightInputs = {
    start: document.getElementById("route_start"),
    end: document.getElementById("route_end"),
    time: timeStartInput,
  };

  function setActiveHighlight(key) {
    Object.values(highlightInputs).forEach(
      (el) => el && el.classList.remove("input-active"),
    );
    if (key && highlightInputs[key])
      highlightInputs[key].classList.add("input-active");
  }

  // Mirror activeInputBox changes into the highlight
  highlightInputs.start &&
    highlightInputs.start.addEventListener("focus", () =>
      setActiveHighlight("start"),
    );
  highlightInputs.end &&
    highlightInputs.end.addEventListener("focus", () =>
      setActiveHighlight("end"),
    );
  highlightInputs.time &&
    highlightInputs.time.addEventListener("focus", () =>
      setActiveHighlight("time"),
    );
  highlightInputs.time &&
    highlightInputs.time.addEventListener("blur", () => {
      // Return highlight to whichever start/end was active
      setActiveHighlight(activeInputBox === "end" ? "end" : "start");
    });

  // Initial highlight
  setActiveHighlight("start");

  // ── GPX import / export ────────────────────────────────────────────────────────
  // Both operations are delegated entirely to the backend (/data_import and
  // /data_export).  No GPX parsing happens in the browser — the backend writes
  // the last computed route to disk so export doesn’t need the GeoJSON layer.
  document
    .getElementById("btn_import")
    .addEventListener("click", () =>
      document.getElementById("data_import").click(),
    );
  document
    .getElementById("data_import")
    .addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      try {
        await fetch("/data_import", { method: "POST", body: formData });
        console.log("GPX Imported");
      } catch (err) {
        console.error("Import error:", err);
      }
    });

  document.getElementById("btn_export").addEventListener("click", async () => {
    try {
      const response = await fetch("/data_export");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "vp_route.gpx";
      a.click();
    } catch (err) {
      console.error("Export error:", err);
    }
  });

  document
    .getElementById("btn_calculate")
    .addEventListener("click", async () => {
      const btn = document.getElementById("btn_calculate");
      const spinner = document.getElementById("calc_spinner");
      const text = document.getElementById("calc_text");

      const parseTimeToUnix = (timeString) => {
        // In demo mode, base the date on demoRefTime (actual NC ref time from
        // the API) so the routing request targets the correct day even if the
        // demo NC spans a different calendar day than today.
        // Fall back to DEMO_NC_UNIX only if demoRefTime hasn’t loaded yet.
        const demoRef =
          (demoMode && window.getDemoRefTime && window.getDemoRefTime()) ||
          (demoMode && new Date(DEMO_NC_UNIX * 1000));
        const baseDate = demoRef ? new Date(demoRef) : new Date();
        if (!timeString) {
          return Math.floor(baseDate.getTime() / 1000);
        }
        const [hours, minutes] = timeString
          .split(":")
          .map((v) => parseInt(v, 10) || 0);
        if (demoMode) {
          // The input is displayed in Europe/Zurich (CEST = UTC+2).
          // setUTCHours handles underflow automatically (e.g. 00:xx → previous
          // day at 22:xx UTC) so no manual date rollback is needed.
          baseDate.setUTCHours(hours - 2, minutes, 0, 0);
          baseDate.setUTCDate(
            baseDate.getUTCDate() +
              (typeof departureDayOffset !== "undefined"
                ? departureDayOffset
                : 0),
          );
        } else {
          baseDate.setHours(hours, minutes, 0, 0);
          baseDate.setDate(
            baseDate.getDate() +
              (typeof departureDayOffset !== "undefined"
                ? departureDayOffset
                : 0),
          );
        }
        return Math.floor(baseDate.getTime() / 1000);
      };

      // Maps the 1–5 rain-sensitivity slider to the string the API expects.
      const sensibilityBySlider = {
        1: "lowest",
        2: "low",
        3: "medium",
        4: "high",
        5: "highest",
      };

      const rainSensitivity =
        sensibilityBySlider[document.getElementById("rain_resistance").value] ||
        "medium";

      const activeModelBtn = document.querySelector(
        "#routing_model_toggle .day-btn.active",
      );
      const selectedRoutingModel = activeModelBtn
        ? activeModelBtn.dataset.model
        : "rain";

      // Validate that both points have been geocoded before submitting.
      // dataset.lat/lon are written by the map-click and text-entry handlers.
      const startEl = document.getElementById("route_start");
      const endEl = document.getElementById("route_end");
      if (
        !startEl.dataset.lat ||
        !startEl.dataset.lon ||
        !endEl.dataset.lat ||
        !endEl.dataset.lon
      ) {
        alert(window.t("err_no_points"));
        return;
      }
      const startPoint = `${startEl.dataset.lat}, ${startEl.dataset.lon}`;
      const endPoint = `${endEl.dataset.lat}, ${endEl.dataset.lon}`;

      btn.disabled = true;
      spinner.style.display = "block";
      text.innerText = window.t("calculating");
      try {
        // Append `demo=true` so the backend serves routes from the cached
        // demo graph instead of trying to fetch live OSM data.
        const query = new URLSearchParams({
          start_point: startPoint,
          end_point: endPoint,
          start_time: String(
            parseTimeToUnix(document.getElementById("time_start").value),
          ),
          speed: String(
            parseFloat(document.getElementById("ride_spd").value) || 20,
          ),
          routingmodel: selectedRoutingModel,
          rainresistence: rainSensitivity,
          ...(demoMode ? { demo: "true" } : {}),
        });

        const response = await fetch(
          `${VP_API_BASE}/WAPapi/v1/route?${query.toString()}`,
        );
        if (!response.ok) {
          const responseText = await response.text();
          throw new Error(
            `Route request failed with status ${response.status}: ${responseText}`,
          );
        }

        // The API returns either a GeoJSON object or a JSON-stringified GeoJSON
        // string depending on the routing model.  Normalise both to an object.
        const raw = await response.json();
        const geojson = typeof raw === "string" ? JSON.parse(raw) : raw;

        if (!geojson || !geojson.type) {
          throw new Error(
            `Invalid GeoJSON payload: ${JSON.stringify(geojson).slice(0, 200)}`,
          );
        }

        if (vpRouteLayer) {
          map.removeLayer(vpRouteLayer);
        }

        if (typeof L === "undefined") {
          throw new Error("Leaflet is not ready");
        }

        if (typeof map === "undefined" || !map) {
          throw new Error("Map is not ready");
        }

        vpRouteLayer = L.geoJSON(geojson, {
          style: {
            color: "#0d3a6e",
            weight: 5,
            opacity: 0.9,
          },
          pane: "route",
        }).addTo(map);

        if (vpRouteLayer.getBounds && vpRouteLayer.getBounds().isValid()) {
          map.fitBounds(vpRouteLayer.getBounds(), { padding: [30, 30] });
        }
      } catch (err) {
        console.error("Route calculation failed:", err);
        alert(
          window.t("err_routing_failed") +
            " " +
            (err && err.message ? err.message : err),
        );
      } finally {
        btn.disabled = false;
        spinner.style.display = "none";
        text.innerText = window.t("calc");
      }
    });

  // ── Rain legend toggle ────────────────────────────────────────────────────────
  // stopPropagation prevents the click from reaching a document-level
  // outside-click handler that would immediately close the popup.
  const legendBtn = document.getElementById("btn-toggle-legend");
  const legendPopup = document.getElementById("rain-legend-popup");
  if (legendBtn && legendPopup) {
    legendBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      legendPopup.classList.toggle("hidden");
      legendBtn.classList.toggle("active");
    });
  }
});
