document.addEventListener("DOMContentLoaded", () => {
  // ── Timeline ticks precision alignment ────────────────────────────────────
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
        // Thumb center goes from 8px to (100% - 8px).
        // So left offset of span center = 8px + (100% - 16px) * percent
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

      // Update timezone label (CEST / CET) based on actual data date
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

      // Remove existing basemaps
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

      // Ensure basemap sits at the bottom z-index so weather overlays remain visible
      if (activeLayer && typeof activeLayer.setZIndex === "function") {
        activeLayer.setZIndex(0);
      }
    });
  }
});

// ── Ctrl-info tooltips ────────────────────────────────────────────────────────
// Body-level tooltip to escape overflow clipping of the routing panel
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

// ── ABOUT PANEL ───────────────────────────────────────────────────────────────
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
