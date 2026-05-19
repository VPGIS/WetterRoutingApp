let i18n = {};
const _i18nReady = fetch("i18n.json")
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

window.t = function (key) {
  return (i18n[currentLang] && i18n[currentLang][key]) || key;
};

document.addEventListener("DOMContentLoaded", () => {
  const langSelect = document.getElementById("lang_select");

  const applyTranslations = () => {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const text = window.t(el.getAttribute("data-i18n"));
      // Find the first text node and update only that, so child elements
      // (e.g. ctrl-info SVG icons inside <label>) are not destroyed.
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
