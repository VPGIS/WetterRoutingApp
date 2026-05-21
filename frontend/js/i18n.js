// =============================================================================
// i18n.js  —  Internationalisation (de / en / fr / it)
// =============================================================================
// Responsibilities:
//   • Fetches i18n.json and exposes `window.t(key)` for on-demand translation.
//   • Applies translations to all `[data-i18n]`, `[data-i18n-ph]`, and
//     `[data-i18n-tip]` elements in the DOM.
//   • Re-runs translation and dynamic labels on language-select change.
//   • Updates the DEMO badge date in the selected locale via `updateDemoBadge`.
//   • Re-calls `updateDepartureDateLabel` after fetch resolves so the
//     departure date shows the correct "Heute" / "Today" text on first render.
//
// Depends on: routing.js (window.updateDepartureDateLabel),
//             demo.js (window.getDemoRefTime)
// =============================================================================
// ── Translation store ─────────────────────────────────────────────────────────────
// _i18nReady is a module-level Promise that resolves when i18n.json has been
// fetched and parsed.  Other scripts cannot await it directly (no ES modules),
// but any code that needs translations can chain .then() on it, or simply call
// window.t() after the DOMContentLoaded phase where it will already be settled.
let i18n = {};
const _i18nReady = fetch("i18n.json?v=" + Date.now())
  .then((r) => {
    if (!r.ok) throw new Error("i18n.json: " + r.status);
    return r.json();
  })
  .then((data) => {
    i18n = data;
  });

let currentLang = "de";

// Updates the DEMO badge text with the ref-time of the active demo NC,
// formatted in the current UI language and Basel/Zurich timezone.
window.updateDemoBadge = function () {
  const badge = document.getElementById("demo-badge");
  if (!badge || badge.style.display === "none") return;
  const refTime = window.getDemoRefTime ? window.getDemoRefTime() : null;
  if (!refTime) {
    badge.textContent = "DEMO";
    return;
  }
  const localeMap = {
    de: "de-CH",
    en: "en-GB",
    fr: "fr-CH",
    it: "it-CH",
  };
  const fmt = new Intl.DateTimeFormat(localeMap[currentLang] || "de-CH", {
    timeZone: "Europe/Zurich",
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  badge.textContent = "DEMO \u00b7 " + fmt.format(refTime);
};

// Looks up a translation key in the current language block.
// Returns the key itself (not an empty string) when a translation is missing,
// so untranslated strings remain readable as meaningful identifiers in dev.
window.t = function (key) {
  return (i18n[currentLang] && i18n[currentLang][key]) || key;
};

document.addEventListener("DOMContentLoaded", () => {
  const langSelect = document.getElementById("lang_select");

  const applyTranslations = () => {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const text = window.t(el.getAttribute("data-i18n"));
      // Walk child nodes to find the first text node and update only that.
      // This preserves sibling elements inside the same tag — for example,
      // a ctrl-info SVG icon that lives inside a <label data-i18n>.
      // Replacing el.textContent would wipe those child elements entirely.
      let textNode = null;
      for (const child of el.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) {
          textNode = child;
          break;
        }
      }
      if (textNode) {
        textNode.textContent = text;
      } else {
        el.textContent = text;
      }
    });
    document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
      el.placeholder = window.t(el.getAttribute("data-i18n-ph"));
    });
    document.querySelectorAll("[data-i18n-tip]").forEach((el) => {
      el.dataset.tip = window.t(el.getAttribute("data-i18n-tip"));
    });
    // The legend info tooltip is assembled from three separate translation keys
    // joined with newlines.  The CSS tooltip component supports multi-line text
    // via the data-tip attribute, so no HTML wrapping is needed.
    const legendInfoBtn = document.getElementById("legend-info-btn");
    if (legendInfoBtn) {
      legendInfoBtn.dataset.tip =
        window.t("legend_info_1") +
        "\n" +
        window.t("legend_info_2") +
        "\n" +
        window.t("legend_info_3");
    }
  };

  langSelect.addEventListener("change", (e) => {
    currentLang = e.target.value;
    applyTranslations();
    if (window.updateDepartureDateLabel) window.updateDepartureDateLabel();
    if (window.updateDemoBadge) window.updateDemoBadge();
    // Update calculate button specifically if it's not currently calculating
    const calcText = document.getElementById("calc_text");
    if (calcText.innerText !== window.t("calculating")) {
      calcText.innerText = window.t("calc");
    }
  });

  // Re-translate once the JSON has loaded.  updateDepartureDateLabel() is
  // called here too because it renders a dynamic string ("Heute DD.MM.YYYY")
  // that uses window.t("today") / window.t("tomorrow") but is NOT driven by a
  // data-i18n attribute — without this call the label would be blank on first
  // load (t() returns the key before i18n.json resolves).
  _i18nReady.then(() => {
    applyTranslations();
    if (window.updateDepartureDateLabel) window.updateDepartureDateLabel();
  });

  // Speed Slider visual update
  const speedInput = document.getElementById("ride_spd");
  const speedDisplay = document.getElementById("speed_display");
  speedInput.addEventListener("input", (e) => {
    speedDisplay.textContent = e.target.value;
  });
});
