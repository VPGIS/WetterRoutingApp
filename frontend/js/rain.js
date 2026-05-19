// Runtime data — filled from API on load
let TIMES = [];
let LABELS = [];

// ── State ───────────────────────────────────────────────────────────────────
let currentFrame = 0;
let playing = false;
let timer = null;
let intervalMs = 500;

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

  // Rain overlays — pre-rendered PNGs served from the backend
  // Layer 1 (mean): solid core — "what's likely"
  // Layer 2 (p90):  semi-transparent halo — "what's possible"
  // Both sit above the basemap but below the label layer.
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

  // Load available timesteps from /rain-times then initialise animation
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

        // Capture ref-time (first frame − 1 h = model reference time)
        if (TIMES.length > 0)
          demoRefTime = new Date(new Date(TIMES[0]).getTime() - 3600000);

        // In live mode, jump to the frame matching the current floored hour
        let startIdx = 0;
        if (!demoMode && TIMES.length > 0) {
          const nowHour = Math.floor(Date.now() / 3600000) * 3600000;
          for (let i = 0; i < TIMES.length; i++) {
            if (new Date(TIMES[i]).getTime() <= nowHour) startIdx = i;
            else break;
          }
        }
        showFrame(startIdx);
        if (typeof window.forceUpdateTicks !== "undefined")
          window.forceUpdateTicks();
        if (typeof window.updateDemoBadge !== "undefined")
          window.updateDemoBadge();
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
  }

  // ── Intensity badge ────────────────────────────────────────────────────────
  // We can't query pixel values without canvas; use frame index as proxy
  // for the label — replace with real per-frame data if available via query.py
  function updateIntensityBadge(idx) {
    const pct = TIMES.length > 1 ? idx / (TIMES.length - 1) : 0;
    intensityBadge.className = "";
    intensityBadge.classList.add(
      pct < 0.1 ? "dry" : pct < 0.4 ? "light" : pct < 0.7 ? "mod" : "heavy",
    );
    intensityTxt.textContent =
      pct < 0.1
        ? "No rain"
        : pct < 0.4
          ? "Light rain"
          : pct < 0.7
            ? "Moderate"
            : "Heavy rain";
  }

  // ── Playback ───────────────────────────────────────────────────────────────
  function step() {
    const next = currentFrame + 1;
    if (next >= TIMES.length) {
      // We reached the end. Stop playing on the last frame so the user can see the final forecast state.
      stopPlay();
    } else {
      showFrame(next);
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
  }

  btnPlay.addEventListener("click", () => (playing ? stopPlay() : startPlay()));
  const handleSliderChange = () => {
    // Instantly pause playback if the user clicks or drags the timeline bar
    if (playing) stopPlay();
    showFrame(parseInt(slider.value, 10) || 0);
  };
  slider.addEventListener("input", handleSliderChange);
  slider.addEventListener("change", handleSliderChange);

  // Keyboard shortcuts
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
