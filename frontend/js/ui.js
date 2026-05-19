// =============================================================================
// ui.js  —  Timeline ticks, layer switcher, tooltips, about panel
// =============================================================================
// Responsibilities:
//   • Renders pixel-accurate timeline tick marks below the range slider,
//     accounting for Chrome's 16 px thumb geometry.  Alternates label / dot
//     style to avoid crowding.  Derives the timezone label (CEST / CET) from
//     the live data via Intl, so it flips automatically at the DST boundary.
//   • Provides the basemap layer switcher (streets / satellite / hybrid).
//     Removes stale TileLayer instances before adding the new one; guards
//     ImageOverlay layers so rain overlays are never accidentally removed.
//   • Renders ctrl-info tooltips into document.body (not the routing panel)
//     to escape the panel's `overflow: hidden` clipping.
//   • Animates the About panel with a two-phase CSS transition:
//     expand width → reveal content (open) / hide content → collapse width (close).
//
// Depends on: rain.js (TIMES, LABELS globals — polled until populated)
// =============================================================================

document.addEventListener("DOMContentLoaded", () => {
  // ── Timeline tick alignment ───────────────────────────────────────────────────
  // In Chrome the range-input thumb is ~16px wide and its centre travels from
  // 8px to (track_width − 8px).  The tick marks must follow the same geometry
  // or they visually lag behind the thumb at the edges.
  // Formula: left = calc(8px + (100% − 16px) × percent)
  //
  // Ticks at even indices get a full text label; odd indices get a shorter
  // dot-only style to prevent crowding at 30-min resolution.
  //
  // updateTicks() reschedules itself every 200 ms if LABELS hasn’t been filled
  // yet (rain.js is still waiting for the /rain-times API response).
  // forceUpdateTicks is exposed so rain.js can trigger an immediate re-render
  // once the data arrives instead of waiting for the next timeout cycle.
  const updateTicks = () => {
    if (typeof LABELS !== "undefined" && LABELS.length > 0) {
      const ticksContainer = document.getElementById("slider-ticks");
      if (!ticksContainer) return;

      ticksContainer.innerHTML = "";
      const totalHours = LABELS.length;

      for (let i = 0; i < totalHours; i++) {
        const span = document.createElement("span");
        const percent = i / (totalHours - 1);

        // Chrome range thumb width is ~16px.
        // Thumb centre goes from 8px to (100% - 8px), so:
        //   left = calc(8px + (100% - 16px) × percent)
        span.style.setProperty(
          "left",
          `calc(8px + calc(100% - 16px) * ${percent})`,
          "important",
        );
        span.style.setProperty("position", "absolute", "important");
        span.style.setProperty("transform", "translateX(-50%)", "important");

        const parts = LABELS[i].split(" · ");
        let timeText = "";
        if (parts.length > 1) {
          const timeStr = parts[1].replace(" CE(S)T", "");
          const timeParts = timeStr.split(" ");
          if (timeParts.length >= 4) timeText = timeParts[3];
        }

        span.textContent = timeText;

        if (i % 2 === 0) {
          span.classList.add("hour-label");
        } else {
          span.classList.add("hour-dot-only");
        }
        ticksContainer.appendChild(span);
      }

      // Derive the timezone abbreviation (CEST / CET) from the first frame’s
      // timestamp using Intl so it flips correctly at the DST boundary without
      // any hardcoded offset logic.
      const tzLabel = document.getElementById("tz-label");
      if (tzLabel && typeof TIMES !== "undefined" && TIMES.length > 0) {
        try {
          const refDate = new Date(TIMES[0]);
          const tzParts = new Intl.DateTimeFormat("en-GB", {
            timeZone: "Europe/Zurich",
            timeZoneName: "short",
          }).formatToParts(refDate);
          const tzName = tzParts.find((p) => p.type === "timeZoneName");
          tzLabel.textContent = tzName ? tzName.value : "CE(S)T";
        } catch (_) {
          tzLabel.textContent = "CE(S)T";
        }
      }
    } else {
      setTimeout(updateTicks, 200);
    }
  };
  updateTicks();
  window.forceUpdateTicks = updateTicks;

  // ── Advanced Settings Toggle ───────────────────────────────────────────────
  const btnAdv = document.getElementById("btn_toggle_advanced");
  const advContainer = document.getElementById("advanced_options");
  if (btnAdv && advContainer) {
    btnAdv.addEventListener("click", () => {
      advContainer.classList.toggle("hidden");
      btnAdv.classList.toggle("active");
    });
  }

  // ── Layer control ──────────────────────────────────────────────────────────
  // Wait until map is definitely initialized
  const checkMap = setInterval(() => {
    if (typeof window.map !== "undefined" && window.map !== null) {
      clearInterval(checkMap);
      initLayerControl();
    }
  }, 200);

  function initLayerControl() {
    const standardLayer = L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      {
        attribution: "© OSM · © CARTO",
        subdomains: "abcd",
        maxZoom: 19,
      },
    );

    const satLayer = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        attribution: "Tiles © Esri",
        maxZoom: 19,
      },
    );

    const hybridLayer = L.layerGroup([
      L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        {
          attribution: "Tiles © Esri",
          maxZoom: 19,
        },
      ),
      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png",
        {
          attribution: "© CARTO",
          subdomains: "abcd",
          maxZoom: 19,
          pane: "labels",
        },
      ),
    ]);

    document.getElementById("layer_select").addEventListener("change", (e) => {
      const val = e.target.value;

      // Remove ALL TileLayer instances before switching basemap.
      // Also removes any LayerGroup that wraps only TileLayers (the hybrid
      // group), but guards ImageOverlay instances so the rain animation
      // layers (mean / p90) are never accidentally removed.
      window.map.eachLayer((layer) => {
        if (layer instanceof L.TileLayer) {
          window.map.removeLayer(layer);
        }
        if (
          layer instanceof L.LayerGroup &&
          !layer.getLayers().some((l) => l instanceof L.ImageOverlay)
        ) {
          window.map.removeLayer(layer); // Safe removal of our hybrid group
        }
      });

      // Add the selected basemap
      let activeLayer;
      if (val === "streets") activeLayer = standardLayer;
      if (val === "satellite") activeLayer = satLayer;
      if (val === "hybrid") activeLayer = hybridLayer;

      if (activeLayer) activeLayer.addTo(window.map);

      // setZIndex(0) pins the basemap below rain overlays (z=300/310) and the
      // Nominatim labels pane (z=450) regardless of insertion order.
      if (activeLayer && typeof activeLayer.setZIndex === "function") {
        activeLayer.setZIndex(0);
      }
    });
  }
});

// ── Ctrl-info tooltips ─────────────────────────────────────────────────────────────
// The tooltip div is appended to document.body rather than to the routing
// panel because the panel has `overflow: hidden` for its slide animation.
// A child element positioned outside the panel’s bounding box would be
// clipped.  Body-level placement avoids this entirely.
// Positioning differs between panel tooltips (appear to the right of the
// panel) and legend tooltips (appear to the right of the legend popup).
(function () {
  const tip = document.createElement("div");
  tip.id = "ctrl-tooltip-popup";
  document.body.appendChild(tip);

  document.querySelectorAll(".ctrl-info").forEach((el) => {
    const trigger = el.closest("label") || el;
    trigger.addEventListener("mouseenter", () => {
      const panel = document.getElementById("routing-panel");
      const panelRect = panel ? panel.getBoundingClientRect() : null;
      const triggerRect = trigger.getBoundingClientRect();
      tip.textContent = el.getAttribute("data-tip");
      const inPanel = panel && panel.contains(trigger);
      const legendPopup = document.getElementById("rain-legend-popup");
      const inLegend = legendPopup && legendPopup.contains(el);
      if (inLegend) {
        const legendRect = legendPopup.getBoundingClientRect();
        tip.style.left = legendRect.right + 12 + "px";
        tip.style.top = legendRect.top + "px";
        tip.style.transform = "none";
      } else {
        tip.style.left =
          (inPanel ? panelRect.right : triggerRect.right) + 12 + "px";
        tip.style.top = triggerRect.top + triggerRect.height / 2 + "px";
        tip.style.transform = "translateY(-50%)";
      }
      tip.classList.add("visible");
    });
    trigger.addEventListener("mouseleave", () => {
      tip.classList.remove("visible");
    });
  });
})();

// ── About panel ──────────────────────────────────────────────────────────────────
// Two-phase CSS transition so the width and the body content animate cleanly:
//   Open:  expand width → wait for "width" transitionend → reveal content
//   Close: hide content → setTimeout(400) to match content-hide duration →
//          collapse width
// The width matches the title box so the panel never wraps text during the
// expand animation.
(() => {
  const panel = document.getElementById("about-panel");
  const toggle = document.getElementById("about-toggle");
  const titleBox = document.getElementById("top-right-title");

  toggle.addEventListener("click", () => {
    const isExpanded = panel.classList.contains("expanded");

    if (isExpanded) {
      // Phase 1: hide body content
      panel.classList.remove("content-visible");
      toggle.classList.remove("active");
      // Phase 2: collapse width after content transition finishes
      setTimeout(() => {
        panel.style.width = "56px";
        panel.classList.remove("expanded");
      }, 400);
    } else {
      // Phase 1: expand width to match title box
      panel.style.width = titleBox.offsetWidth + "px";
      panel.classList.add("expanded");
      toggle.classList.add("active");
      // Phase 2: reveal body after width transition ends
      const onWidthEnd = (e) => {
        if (e.propertyName === "width") {
          panel.classList.add("content-visible");
          panel.removeEventListener("transitionend", onWidthEnd);
        }
      };
      panel.addEventListener("transitionend", onWidthEnd);
    }
  });
})();
