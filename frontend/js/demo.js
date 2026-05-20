// =============================================================================
// demo.js  —  Demo mode toggle and state
// =============================================================================
// Manages the boolean `demoMode` flag and the `demoRefTime` Date that other
// scripts use as a fake "now" when demo mode is active.  Exposes both via
// `window.getDemoRefTime()` so downstream scripts have a clean read-only
// interface without direct variable access across script files.
//
// Entry point: a hidden Easter egg — 5 rapid clicks on the header logo.
// Depends on: config.js (DEMO_NC_UNIX, TIMES, LABELS), rain.js (loadRainData),
//             routing.js (updateDepartureDateLabel, syncDemoTime, resetLiveTime)
// =============================================================================

// ── Demo mode ─────────────────────────────────────────────────────────────────
// Demo mode swaps the live MeteoSwiss forecast for a bundled NC file so the
// app works without an active API connection (e.g. during a presentation).
// Activated by clicking the logo 5 times rapidly (see Easter egg below).
//
// These module-level variables are true globals — all scripts in the page share
// them implicitly because the scripts load sequentially without ES modules.

let demoMode = false;

// Populated asynchronously by rain.js once /demo-rain-times responds.
// Starts as null so consumers can distinguish "not yet loaded" from a real date.
// Exposed via getDemoRefTime() rather than accessed directly to keep the API
// surface explicit across script files.
let demoRefTime = null;
window.getDemoRefTime = () => demoRefTime;

// Shows a brief top-right toast when demo mode is toggled on or off.
function showDemoToast(entering) {
  const toast = document.getElementById("demo-toast");
  if (!toast) return;
  toast.textContent = entering ? "🔧 Demo-Modus aktiv" : "Demo-Modus beendet";
  toast.classList.remove("hidden");
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => toast.classList.add("hidden"), 3000);
}

// Toggles demo mode and fully reloads rain data from the matching endpoint.
//
// Timing note: loadRainData() is async.  updateDepartureDateLabel() and
// syncDemoTime() are called immediately using DEMO_NC_UNIX as a fallback so
// the UI is not blank during the fetch.  rain.js calls them again once
// demoRefTime is populated from the real API (see loadRainData callback),
// so the displayed date/time converges to the actual NC ref time shortly after.
function toggleDemoMode() {
  demoMode = !demoMode;
  const badge = document.getElementById("demo-badge");
  if (badge) badge.style.display = demoMode ? "block" : "none";
  showDemoToast(demoMode);
  // Wipe cached frame data so loadRainData fetches a clean set from the
  // correct endpoint (/demo-rain-times vs /rain-times).
  TIMES = [];
  LABELS = [];
  window.loadRainData();
  if (window.updateDepartureDateLabel) window.updateDepartureDateLabel();
  // Snap time input to NC ref time when entering, restore real clock on exit.
  if (demoMode && window.syncDemoTime) window.syncDemoTime();
  else if (!demoMode && window.resetLiveTime) window.resetLiveTime();
}

document.addEventListener("DOMContentLoaded", () => {
  // ── Easter egg: 5 rapid clicks on the logo activates demo mode ───────────
  // Not advertised in the UI — intended for live demos and project reviews.
  // A 2-second idle window resets the counter so accidental clicks don't trigger it.
  let clickCount = 0;
  let clickTimer = null;
  const logoEl = document.getElementById("header-logo");
  if (logoEl) {
    logoEl.style.cursor = "pointer";
    logoEl.addEventListener("click", () => {
      clickCount++;
      clearTimeout(clickTimer);
      clickTimer = setTimeout(() => {
        clickCount = 0;
      }, 2000);
      if (clickCount >= 5) {
        clickCount = 0;
        toggleDemoMode();
      }
    });
  }
});
