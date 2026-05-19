// ── GLOBALS SO MAP EVENTS WORK ──────────────────────────────────────────────
let vpStartMarker = null;
let vpEndMarker = null;
let vpRouteLayer = null;

document.addEventListener("DOMContentLoaded", () => {
  const routeStartInput = document.getElementById("route_start");
  const routeEndInput = document.getElementById("route_end");

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

  // Robust way to wait for Leaflet
  const initMapHooks = () => {
    if (typeof map === "undefined" || typeof L === "undefined") {
      setTimeout(initMapHooks, 200);
      return;
    }

    // 1. CLICKING THE MAP
    // No need to focus boxes first.
    // Keep track of the initial two-click map interaction phase
    // 0: Waiting for first click (Start)
    // 1: Waiting for second click (End)
    // 2: Done with initial phase. Relies entirely on `activeInputBox`.
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

    // 2. TYPING ADDRESSES MANUALLY
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

  const timeStartInput = document.getElementById("time_start");
  if (timeStartInput && !timeStartInput.value) {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, "0");
    const minutes = String(now.getMinutes()).padStart(2, "0");
    timeStartInput.value = `${hours}:${minutes}`;
  }

  // ── Heute / Morgen day toggle ─────────────────────────────────────────────
  let departureDayOffset = 0; // 0 = today, 1 = tomorrow
  const departureDateEl = document.getElementById("departure-date");

  window.updateDepartureDateLabel = function updateDepartureDateLabel() {
    if (!departureDateEl) return;
    const d = demoMode ? new Date(DEMO_NC_UNIX * 1000) : new Date();
    d.setDate(d.getDate() + departureDayOffset);
    const label =
      departureDayOffset === 0 ? window.t("today") : window.t("tomorrow");
    departureDateEl.textContent =
      label +
      ", " +
      String(d.getDate()).padStart(2, "0") +
      "." +
      String(d.getMonth() + 1).padStart(2, "0") +
      "." +
      d.getFullYear();
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
        const baseDate = demoMode ? new Date(DEMO_NC_UNIX * 1000) : new Date();
        if (!timeString) {
          return demoMode
            ? DEMO_NC_UNIX
            : Math.floor(baseDate.getTime() / 1000);
        }
        const [hours, minutes] = timeString
          .split(":")
          .map((v) => parseInt(v, 10) || 0);
        if (demoMode) {
          baseDate.setUTCHours(hours, minutes, 0, 0);
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
        : "einfach";

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

  // ── REGEN LEGENDE TOGGLE ─────────────────────────────────────────────────
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
