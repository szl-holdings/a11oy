/*
 * SZL Holographic Experience v2
 * Dependency-free progressive enhancement for A11oy product surfaces.
 * No analytics, network access, storage, cookies, or product-state mutation.
 * SPDX-License-Identifier: Apache-2.0
 */
(function () {
  "use strict";

  if (window.__SZL_HOLOGRAM_V2__) return;
  window.__SZL_HOLOGRAM_V2__ = true;

  var VERSION = "2.0.0";
  var ROUTES = [
    ["/static/viz/doctrine", "forensic"],
    ["/static/viz/router", "bridge"],
    ["/living-anatomy", "anatomy"],
    ["/anatomy", "anatomy"],
    ["/puriq-markets", "market"],
    ["/evaluations", "decision"],
    ["/assurance", "forensic"],
    ["/decision", "decision"],
    ["/console", "operator"],
    ["/command", "operator"],
    ["/estate", "atlas"],
    ["/immune", "sentinel"],
    ["/khipu", "weave"],
    ["/lyte", "observatory"],
    ["/nexus", "bridge"],
    ["/terra", "blueprint"],
    ["/aegis", "sentry"],
    ["/counsel", "counsel"],
    ["/vessels", "voyage"],
    ["/verify", "forensic"],
    ["/trust", "forensic"],
    ["/demo", "decision"],
    ["/", "conductor"]
  ];
  var PANEL_SELECTORS = [
    "main > section",
    "main > article",
    "main [class~='card']",
    "main [class$='-card']",
    "main [class*=' card-']",
    "main [class~='panel']",
    "main [class$='-panel']",
    "main [class*=' panel-']",
    "main [data-card]",
    "main [data-panel]"
  ];

  function pathNow() {
    var path = window.location.pathname || "/";
    if (path.length > 1) path = path.replace(/\/+$/, "");
    return path || "/";
  }

  function routeTheme() {
    var declared = document.body && document.body.dataset ? document.body.dataset.szlTheme : "";
    if (declared) return declared;
    var path = pathNow();
    for (var i = 0; i < ROUTES.length; i += 1) {
      var row = ROUTES[i];
      if (row[0] === "/" || path === row[0] || path.indexOf(row[0] + "/") === 0) return row[1];
    }
    return "conductor";
  }

  function element(name, className) {
    var node = document.createElement(name);
    if (className) node.className = className;
    return node;
  }

  function createStage() {
    if (document.querySelector(".szl-holo-v2-stage")) return document.querySelector(".szl-holo-v2-stage");
    var stage = element("div", "szl-holo-v2-stage");
    stage.setAttribute("aria-hidden", "true");
    stage.dataset.szlHologramVersion = VERSION;
    ["grid", "orbit", "beam", "scan", "prism", "cursor"].forEach(function (part) {
      stage.appendChild(element("span", "szl-holo-v2-" + part));
    });
    document.body.insertBefore(stage, document.body.firstChild);
    return stage;
  }

  function lowPowerMode() {
    var cores = Number(navigator.hardwareConcurrency || 8);
    var memory = Number(navigator.deviceMemory || 8);
    var saveData = Boolean(navigator.connection && navigator.connection.saveData);
    return saveData || cores <= 4 || memory <= 4;
  }

  function markPanels() {
    var found = [];
    PANEL_SELECTORS.forEach(function (selector) {
      try {
        document.querySelectorAll(selector).forEach(function (node) {
          if (found.indexOf(node) === -1) found.push(node);
        });
      } catch (_) {
        /* Invalid selectors must never block the application. */
      }
    });
    found.slice(0, 36).forEach(function (node, index) {
      if (node.closest(".szl-flow-rail, .szl-holo-v2-stage")) return;
      node.dataset.szlHoloPanel = String(index + 1);
      node.style.setProperty("--szl-holo-delay", Math.min(index * 28, 280) + "ms");
    });
    return found.slice(0, 36);
  }

  function revealPanels(panels, reducedMotion) {
    if (reducedMotion || !("IntersectionObserver" in window)) {
      panels.forEach(function (panel) { panel.dataset.szlHoloVisible = "true"; });
      return null;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.dataset.szlHoloVisible = "true";
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "80px 0px -6% 0px", threshold: 0.06 });
    panels.forEach(function (panel) { observer.observe(panel); });
    return observer;
  }

  function pointerEngine(reducedMotion) {
    var finePointer = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    if (reducedMotion || !finePointer) return function () {};
    var root = document.documentElement;
    var frame = 0;
    var latestX = window.innerWidth / 2;
    var latestY = window.innerHeight / 3;

    function draw() {
      frame = 0;
      var width = Math.max(window.innerWidth, 1);
      var height = Math.max(window.innerHeight, 1);
      var nx = (latestX / width - 0.5) * 2;
      var ny = (latestY / height - 0.5) * 2;
      root.style.setProperty("--szl-holo-x", latestX.toFixed(1) + "px");
      root.style.setProperty("--szl-holo-y", latestY.toFixed(1) + "px");
      root.style.setProperty("--szl-holo-nx", nx.toFixed(4));
      root.style.setProperty("--szl-holo-ny", ny.toFixed(4));
    }

    function move(event) {
      latestX = event.clientX;
      latestY = event.clientY;
      if (!frame) frame = window.requestAnimationFrame(draw);
    }

    function leave() {
      latestX = window.innerWidth / 2;
      latestY = window.innerHeight / 3;
      if (!frame) frame = window.requestAnimationFrame(draw);
    }

    window.addEventListener("pointermove", move, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave, { passive: true });
    draw();
    return function () {
      window.removeEventListener("pointermove", move);
      document.documentElement.removeEventListener("pointerleave", leave);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }

  function hookRouteChanges(update) {
    ["pushState", "replaceState"].forEach(function (name) {
      var original = history[name];
      if (typeof original !== "function" || original.__szlHoloWrapped) return;
      var wrapped = function () {
        var result = original.apply(this, arguments);
        window.dispatchEvent(new Event("szl:hologram-route"));
        return result;
      };
      wrapped.__szlHoloWrapped = true;
      history[name] = wrapped;
    });
    window.addEventListener("popstate", update);
    window.addEventListener("szl:hologram-route", update);
  }

  function boot() {
    if (!document.body) return;
    var root = document.documentElement;
    var reducedMotion = Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    root.dataset.szlHologramV2 = "true";
    root.dataset.szlHoloPower = lowPowerMode() ? "low" : "full";
    root.dataset.szlHoloState = document.hidden ? "paused" : "active";

    function updateTheme() {
      root.dataset.szlHoloTheme = routeTheme();
    }

    createStage();
    updateTheme();
    var panels = markPanels();
    revealPanels(panels, reducedMotion);
    var stopPointer = pointerEngine(reducedMotion);
    hookRouteChanges(updateTheme);

    document.addEventListener("visibilitychange", function () {
      root.dataset.szlHoloState = document.hidden ? "paused" : "active";
    });

    window.addEventListener("pagehide", stopPointer, { once: true });
    document.dispatchEvent(new CustomEvent("szl:hologram-ready", {
      detail: Object.freeze({
        version: VERSION,
        theme: routeTheme(),
        power: root.dataset.szlHoloPower,
        reducedMotion: reducedMotion,
        enhancedPanels: panels.length
      })
    }));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
}());
