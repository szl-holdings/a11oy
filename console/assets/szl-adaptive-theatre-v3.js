/*
 * SZL Adaptive Theatre v3
 * Dependency-free viewport, performance, and progressive interaction controller.
 * No fetch, analytics, cookies, localStorage, sessionStorage, or fabricated telemetry.
 */
(function () {
  "use strict";

  if (window.__SZL_ADAPTIVE_THEATRE_V3__) return;
  window.__SZL_ADAPTIVE_THEATRE_V3__ = true;

  var root = document.documentElement;
  var mediaReduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  var mediaCoarse = window.matchMedia("(pointer: coarse)");
  var mediaContrast = window.matchMedia("(prefers-contrast: more)");
  var state = {
    mode: "",
    orientation: "",
    motion: "",
    raf: 0,
    observer: null,
    panels: [],
  };

  function connectionSaver() {
    var connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    return Boolean(connection && connection.saveData);
  }

  function lowResource() {
    var memory = Number(navigator.deviceMemory || 0);
    var cores = Number(navigator.hardwareConcurrency || 0);
    return (memory > 0 && memory <= 2) || (cores > 0 && cores <= 2);
  }

  function viewport() {
    var visual = window.visualViewport;
    return {
      width: Math.max(1, Math.round(visual ? visual.width : window.innerWidth)),
      height: Math.max(1, Math.round(visual ? visual.height : window.innerHeight)),
    };
  }

  function displayMode(width) {
    if (width < 640) return "mobile";
    if (width < 1024) return "tablet";
    if (width < 1680) return "desktop";
    return "theatre";
  }

  function motionTier() {
    if (mediaReduced.matches || connectionSaver() || lowResource()) return "quiet";
    if (mediaCoarse.matches || window.innerWidth < 900) return "balanced";
    return "full";
  }

  function emit(name, detail) {
    try {
      window.dispatchEvent(new CustomEvent(name, { detail: detail }));
    } catch (_) {
      return;
    }
  }

  function updateViewport() {
    state.raf = 0;
    var size = viewport();
    var mode = displayMode(size.width);
    var orientation = size.width >= size.height ? "landscape" : "portrait";
    var motion = motionTier();

    root.style.setProperty("--szl-vw", (size.width / 100).toFixed(3) + "px");
    root.style.setProperty("--szl-vh", (size.height / 100).toFixed(3) + "px");
    root.dataset.szlAdaptiveV3 = "ready";
    root.dataset.szlDisplayMode = mode;
    root.dataset.szlOrientation = orientation;
    root.dataset.szlMotion = motion;
    root.dataset.szlPointer = mediaCoarse.matches ? "coarse" : "fine";
    root.dataset.szlContrast = mediaContrast.matches ? "more" : "normal";

    if (mode !== state.mode || orientation !== state.orientation || motion !== state.motion) {
      state.mode = mode;
      state.orientation = orientation;
      state.motion = motion;
      emit("szl:displaymode", {
        mode: mode,
        orientation: orientation,
        motion: motion,
        width: size.width,
        height: size.height,
      });
    }
  }

  function scheduleViewport() {
    if (state.raf) return;
    state.raf = window.requestAnimationFrame(updateViewport);
  }

  function visible(element) {
    var style = window.getComputedStyle(element);
    var rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  }

  function normalizeTablesAndCode() {
    document.querySelectorAll("table").forEach(function (table) {
      if (table.parentElement && table.parentElement.matches(".szl-table-wrap,[data-szl-scrollable='table']")) return;
      var wrapper = document.createElement("div");
      wrapper.className = "szl-table-wrap";
      wrapper.dataset.szlScrollable = "table";
      wrapper.tabIndex = 0;
      wrapper.setAttribute("role", "region");
      wrapper.setAttribute("aria-label", table.getAttribute("aria-label") || "Scrollable data table");
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    });

    document.querySelectorAll("pre").forEach(function (pre) {
      pre.dataset.szlScrollable = "code";
      if (!pre.hasAttribute("tabindex")) pre.tabIndex = 0;
      if (!pre.hasAttribute("aria-label")) pre.setAttribute("aria-label", "Scrollable code or record");
    });
  }

  function labelIconControls() {
    document.querySelectorAll("button, [role='button'], a").forEach(function (control) {
      if (!visible(control)) return;
      var text = (control.textContent || "").trim();
      if (text || control.hasAttribute("aria-label") || control.hasAttribute("aria-labelledby")) return;
      var title = (control.getAttribute("title") || "").trim();
      if (title) control.setAttribute("aria-label", title);
    });
  }

  function installPanelObserver() {
    if (!("IntersectionObserver" in window) || mediaReduced.matches) return;
    var selectors = [
      ".szl-card",
      ".szl-panel",
      ".szl-holo-panel",
      "[data-szl-panel]",
      "main > section",
    ];
    var candidates = Array.prototype.slice.call(document.querySelectorAll(selectors.join(",")))
      .filter(visible)
      .slice(0, 48);
    state.panels = candidates;
    if (!candidates.length) return;

    state.observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        entry.target.dataset.szlInview = entry.isIntersecting ? "true" : "false";
        if (entry.isIntersecting) state.observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });

    candidates.forEach(function (panel) {
      panel.classList.add("szl-adaptive-enter");
      panel.dataset.szlInview = "false";
      state.observer.observe(panel);
    });
  }

  function handleAnchor(event) {
    var anchor = event.target.closest && event.target.closest("a[href^='#']");
    if (!anchor) return;
    var href = anchor.getAttribute("href");
    if (!href || href === "#") return;
    var target;
    try {
      target = document.querySelector(href);
    } catch (_) {
      return;
    }
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: mediaReduced.matches ? "auto" : "smooth", block: "start" });
    if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
    target.focus({ preventScroll: true });
    history.replaceState(null, "", href);
  }

  function closeOpenNavigation() {
    document.querySelectorAll("[aria-expanded='true']").forEach(function (control) {
      if (!control.matches("button,[role='button']")) return;
      control.click();
    });
  }

  function onKeydown(event) {
    if (event.key === "Escape") {
      closeOpenNavigation();
      return;
    }
    if ((event.key === "Home" || event.key === "End") && event.altKey) {
      event.preventDefault();
      window.scrollTo({ top: event.key === "Home" ? 0 : document.documentElement.scrollHeight, behavior: mediaReduced.matches ? "auto" : "smooth" });
    }
  }

  function maintainFocusVisibility() {
    document.addEventListener("focusin", function (event) {
      var target = event.target;
      if (!(target instanceof HTMLElement)) return;
      window.requestAnimationFrame(function () {
        var rect = target.getBoundingClientRect();
        var pad = 16;
        if (rect.top < pad || rect.bottom > window.innerHeight - pad) {
          target.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "auto" });
        }
      });
    });
  }

  function start() {
    if (!document.body) return;
    updateViewport();
    normalizeTablesAndCode();
    labelIconControls();
    installPanelObserver();
    maintainFocusVisibility();

    window.addEventListener("resize", scheduleViewport, { passive: true });
    window.addEventListener("orientationchange", scheduleViewport, { passive: true });
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", scheduleViewport, { passive: true });
      window.visualViewport.addEventListener("scroll", scheduleViewport, { passive: true });
    }
    [mediaReduced, mediaCoarse, mediaContrast].forEach(function (query) {
      if (query.addEventListener) query.addEventListener("change", scheduleViewport);
      else if (query.addListener) query.addListener(scheduleViewport);
    });
    document.addEventListener("click", handleAnchor);
    document.addEventListener("keydown", onKeydown);

    emit("szl:adaptive-ready", {
      version: "3.0.0",
      mode: state.mode,
      orientation: state.orientation,
      motion: state.motion,
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
}());
