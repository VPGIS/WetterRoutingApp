// =============================================================================
// rain.js  —  Leaflet map, rain overlay animation, and timeline slider
// =============================================================================
// Responsibilities:
//   • Initialises the Leaflet map and creates two stacked PNG overlay layers:
//       - mean overlay  (z=300): ensemble mean precipitation — "what is likely"
//       - p90  overlay  (z=310): 90th-percentile halo       — "worst case"
//   • Fetches available forecast timesteps from /rain-times (live) or
//     /demo-rain-times (demo) and populates the global TIMES / LABELS arrays.
//   • Drives the frame animation: play/pause, step, slider drag.
//   • Computes `demoRefTime` (NC model-run time) once the API responds and
//     notifies routing.js / ui.js via window callbacks.
//   • Exposes `window.loadRainData` so demo.js can trigger a reload on toggle.
//
// Depends on: config.js (BOUNDS, GLOBAL_MAX, VP_API_BASE, DEMO_NC_UNIX),
//             demo.js (demoMode, getDemoRefTime)
// =============================================================================

// ── Shared animation state ───────────────────────────────────────────────────
// TIMES and LABELS are filled from /rain-times (or /demo-rain-times) on load
// and whenever demo mode is toggled.  They are true globals because demo.js
// clears them (TIMES = []; LABELS = [];) before calling loadRainData().
let TIMES = [];
let LABELS = [];

// ── State ────────────────────────────────────────────────────────────────────
let currentFrame = 0;
let playing = false;
let timer = null;
let halfFrameTimer = null; // fires once per frame at the midpoint to update the cyclist
let intervalMs = 500; // ms between animation frames (~2 fps feels calm, not frantic)

// ── DOM refs ─────────────────────────────────────────────────────────────────
const slider = document.getElementById("time-slider");
const btnPlay = document.getElementById("btn-play");
const iconPlay = document.getElementById("icon-play");
const iconPause = document.getElementById("icon-pause");
const frameCount = document.getElementById("stat-frame");
const intensityBadge = document.getElementById("intensity-badge");
const intensityTxt = document.getElementById("intensity-text");
const loading = document.getElementById("loading");

// ── Init panel metadata ──────────────────────────────────────────────────────
document.getElementById("stat-peak").textContent =
  GLOBAL_MAX.toFixed(2) + " mm";
document.getElementById("cb-max").textContent = GLOBAL_MAX.toFixed(1);
document.getElementById("cb-mid").textContent = (GLOBAL_MAX / 2).toFixed(1);
slider.max = 33; // placeholder — updated after /rain-times loads

// ── Leaflet setup ────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  window.map = L.map("map", {
    center: [46.8, 8.3],
    zoom: 8,
    zoomControl: false,
    attributionControl: true,
  });

  // Scale bar — metric units, bottom-left aligned with routing panel
  L.control
    .scale({ imperial: false, position: "bottomleft", maxWidth: 200 })
    .addTo(map);

  // Base map without labels (rain will sit above this)
  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
    {
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OSM</a> · © <a href="https://carto.com/" target="_blank">CARTO</a> · MeteoSwiss ICON-CH1-EPS',
      subdomains: "abcd",
      maxZoom: 19,
    },
  ).addTo(map);

  // ── Rain overlay strategy ──────────────────────────────────────────────────
  // Two semi-transparent PNG layers are stacked above the basemap:
  //   overlay    (mean)  — ensemble mean, z=300 — "what is likely"
  //   overlayP90 (p90)   — 90th percentile,  z=310 — "worst-case halo"
  // Both are pre-rendered server-side from NetCDF data (see utils_render.py).
  // Pre-rendering avoids doing 33 × per-pixel NetCDF reads in the browser and
  // keeps the client completely stateless with respect to the raw forecast data.
  function makeRainUrl(time) {
    return (
      (demoMode ? "/demo-rain-frame" : "/rain-frame") +
      "?time=" +
      encodeURIComponent(time)
    );
  }
  function makeP90Url(time) {
    return (
      (demoMode ? "/demo-rain-frame" : "/rain-frame") +
      "?time=" +
      encodeURIComponent(time) +
      "&layer=p90"
    );
  }

  // Bottom: ensemble mean — certain rain core
  const overlay = L.imageOverlay("", BOUNDS, {
    opacity: 1.0,
    interactive: false,
    zIndex: 300,
  }).addTo(map);

  // Top: p90 possibility halo (semi-transparent, same extent)
  const overlayP90 = L.imageOverlay("", BOUNDS, {
    opacity: 1.0,
    interactive: false,
    zIndex: 310,
  }).addTo(map);

  // Labels-only layer in a custom pane above the rain overlay
  map.createPane("labels");
  map.getPane("labels").style.zIndex = 450;
  map.getPane("labels").style.pointerEvents = "none";

  // Route + marker pane — always above rain (300/310) and labels (450)
  map.createPane("route");
  map.getPane("route").style.zIndex = 500;
  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png",
    {
      subdomains: "abcd",
      maxZoom: 19,
      pane: "labels",
    },
  ).addTo(map);

  // Load available timesteps from /rain-times then initialise animation.
  //
  // Each call starts fresh — TIMES/LABELS are wiped by demo.js before this
  // is invoked on a mode switch, so there is no stale-frame problem.
  function loadRainData() {
    const timesUrl = demoMode ? "/demo-rain-times" : "/rain-times";
    fetch(timesUrl)
      .then((r) => r.json())
      .then((data) => {
        if (!data || data.length === 0) {
          console.warn("[rain-times] API returned no timesteps");
          return;
        }
        TIMES = data;
        // Build human-readable tick labels in Europe/Zurich time.
        // Format: "+03h · Mon 18 May 14:00 CE(S)T"
        // The CE(S)T suffix is shown literally because JavaScript's Intl
        // sometimes returns "GMT+2" instead of "CEST" depending on the engine.
        const baselLabelFmt = new Intl.DateTimeFormat("en-GB", {
          timeZone: "Europe/Zurich",
          weekday: "short",
          day: "2-digit",
          month: "short",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        });
        LABELS = data.map((iso, i) => {
          const d = new Date(iso);
          const lead = String(i + 1).padStart(2, "0");
          const parts = baselLabelFmt.formatToParts(d);
          const r = {};
          parts.forEach((p) => (r[p.type] = p.value));
          return `+${lead}h · ${r.weekday} ${r.day} ${r.month} ${r.hour}:${r.minute} CE(S)T`;
        });
        slider.max = TIMES.length - 1;

        // demoRefTime = first TIMES entry minus 1 h = model initialisation time.
        // Used by the DEMO badge and departure time sync across the app.
        if (TIMES.length > 0)
          demoRefTime = new Date(new Date(TIMES[0]).getTime() - 3600000);

        // Jump to the frame whose valid time is closest to "now" (live) or to
        // the NC ref time (demo).  The loop finds the last frame whose timestamp
        // is still <= the reference, so we land on the most recent past frame
        // rather than a future one.
        let startIdx = 0;
        if (TIMES.length > 0) {
          const refMs = demoMode
            ? Math.floor(
                (demoRefTime ? demoRefTime.getTime() : DEMO_NC_UNIX * 1000) /
                  3600000,
              ) * 3600000
            : Math.floor(Date.now() / 3600000) * 3600000;
          for (let i = 0; i < TIMES.length; i++) {
            if (new Date(TIMES[i]).getTime() <= refMs) startIdx = i;
            else break;
          }
        }
        showFrame(startIdx);
        if (typeof window.forceUpdateTicks !== "undefined")
          window.forceUpdateTicks();
        if (typeof window.updateDemoBadge !== "undefined")
          window.updateDemoBadge();
        // Re-sync departure date/time now that demoRefTime is the real API value
        if (demoMode) {
          if (typeof window.updateDepartureDateLabel !== "undefined")
            window.updateDepartureDateLabel();
          if (typeof window.syncDemoTime !== "undefined") window.syncDemoTime();
        }
      })
      .catch((err) => console.error("[rain-times] fetch failed:", err));
  }
  window.loadRainData = loadRainData;
  loadRainData();

  map.once("load", hideLoading);
  setTimeout(hideLoading, 1200); // fallback

  function hideLoading() {
    loading.classList.add("hidden");
    setTimeout(() => loading.remove(), 400);
  }

  // ── Frame rendering ────────────────────────────────────────────────────────
  function showFrame(idx) {
    if (!TIMES.length) return; // guard until /rain-times loaded
    currentFrame = idx;
    overlay.setUrl(makeRainUrl(TIMES[idx]));
    overlayP90.setUrl(makeP90Url(TIMES[idx]));

    slider.value = idx;
    const pct =
      TIMES.length > 1 ? ((idx / (TIMES.length - 1)) * 100).toFixed(1) : 0;
    slider.style.setProperty("--pct", pct + "%");

    frameCount.textContent = `${idx + 1} / ${TIMES.length}`;
    updateIntensityBadge(idx);
    if (typeof window.updateCyclist === "function") window.updateCyclist(idx);
  }

  // ── Intensity badge ────────────────────────────────────────────────────────
  // Reading actual pixel values from the PNG overlay would require a <canvas>
  // cross-origin workaround.  As a pragmatic proxy we use the frame index
  // (position in the 33-step forecast) to classify intensity — early frames
  // of the demo NC tend to be wetter, later ones drier.  This is purely visual
  // and carries no meteorological guarantee.  Replace with real per-frame stats
  // (e.g. from a query.py endpoint) if more accuracy is needed.
  function updateIntensityBadge(idx) {
    const pct = TIMES.length > 1 ? idx / (TIMES.length - 1) : 0;
    intensityBadge.className = "";
    intensityBadge.classList.add(
      pct < 0.1 ? "dry" : pct < 0.4 ? "light" : pct < 0.7 ? "mod" : "heavy",
    );
    intensityTxt.textContent =
      pct < 0.1
        ? window.t("intensity_dry")
        : pct < 0.4
          ? window.t("rain_light")
          : pct < 0.7
            ? window.t("intensity_mod")
            : window.t("rain_heavy");
  }

  // ── Playback ───────────────────────────────────────────────────────────────
  // Playback stops on the last frame instead of looping so the user can study
  // the final forecast state.  startPlay() resets to frame 0 if re-pressed at
  // the end, giving loop-like behaviour without an automatic restart.
  function step() {
    const next = currentFrame + 1;
    if (next >= TIMES.length) {
      // We reached the end. Stop playing on the last frame so the user can see the final forecast state.
      stopPlay();
    } else {
      showFrame(next);
      // Move the cyclist to the halfway point between this frame and the next
      clearTimeout(halfFrameTimer);
      if (typeof window.updateCyclist === "function") {
        halfFrameTimer = setTimeout(
          () => window.updateCyclist(next + 0.5),
          intervalMs / 2,
        );
      }
    }
  }

  function startPlay() {
    playing = true;
    iconPlay.style.display = "none";
    iconPause.style.display = "";
    btnPlay.setAttribute("aria-label", "Pause");

    // If the slider is manually dragged to the very end, reset to the beginning when play is clicked
    if (currentFrame === TIMES.length - 1) {
      showFrame(0);
    }

    timer = setInterval(step, intervalMs);
  }

  function stopPlay() {
    playing = false;
    iconPlay.style.display = "";
    iconPause.style.display = "none";
    btnPlay.setAttribute("aria-label", "Play");
    clearInterval(timer);
    clearTimeout(halfFrameTimer);
  }

  btnPlay.addEventListener("click", () => (playing ? stopPlay() : startPlay()));
  const handleSliderChange = () => {
    // Instantly pause playback if the user clicks or drags the timeline bar
    if (playing) stopPlay();
    clearTimeout(halfFrameTimer);
    showFrame(parseInt(slider.value, 10) || 0);
  };
  slider.addEventListener("input", handleSliderChange);
  slider.addEventListener("change", handleSliderChange);

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  // Space = play/pause, ← / → = step one frame.
  // Guard against capturing keystrokes while the user types in an input field.
  document.addEventListener("keydown", (e) => {
    // Do not capture shortcuts if the user is typing in an input field
    if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;

    if (e.key === " ") {
      e.preventDefault();
      playing ? stopPlay() : startPlay();
    }
    if (e.key === "ArrowLeft") {
      stopPlay();
      showFrame((currentFrame - 1 + TIMES.length) % TIMES.length);
    }
    if (e.key === "ArrowRight") {
      stopPlay();
      showFrame((currentFrame + 1) % TIMES.length);
    }
  });

  // Initial render
  showFrame(0);
});
