// ── Demo state ────────────────────────────────────────────────────────────────
let demoMode = false;
let demoRefTime = null;
window.getDemoRefTime = () => demoRefTime;

function showDemoToast(entering) {
  const toast = document.getElementById("demo-toast");
  if (!toast) return;
  toast.textContent = entering ? "🔧 Demo-Modus aktiv" : "Demo-Modus beendet";
  toast.classList.remove("hidden");
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => toast.classList.add("hidden"), 3000);
}

function toggleDemoMode() {
  demoMode = !demoMode;
  const badge = document.getElementById("demo-badge");
  if (badge) badge.style.display = demoMode ? "block" : "none";
  showDemoToast(demoMode);
  TIMES = [];
  LABELS = [];
  window.loadRainData();
  if (window.updateDepartureDateLabel) window.updateDepartureDateLabel();
  if (demoMode && window.syncDemoTime) window.syncDemoTime();
  else if (!demoMode && window.resetLiveTime) window.resetLiveTime();
}

document.addEventListener("DOMContentLoaded", () => {
  // 5-click Easter egg on logo
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
