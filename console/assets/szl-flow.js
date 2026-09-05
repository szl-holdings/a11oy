/* SZL Flow Shell v2 — shared journeys, distinct holographic instruments. */
(function () {
  "use strict";

  if (window.__SZL_FLOW_SHELL__) return;
  window.__SZL_FLOW_SHELL__ = true;

  var VERSION = "2.0.0";
  var PRODUCT = "https://a-11-oy.com";
  var PROOF = "https://a11oy.net";
  var SPECTRAL_STYLE = "/assets/szl-spectral-v2.css";
  var ROUTES = [
    { prefix: "/static/viz/doctrine", theme: "forensic", journey: "kernels", label: "Doctrine Lattice", mode: "Policy instrument" },
    { prefix: "/static/viz/router", theme: "bridge", journey: "kernels", label: "Router Mesh", mode: "Connection instrument" },
    { prefix: "/living-anatomy", theme: "anatomy", journey: "models", label: "Living Anatomy", mode: "Organism instrument" },
    { prefix: "/anatomy", theme: "anatomy", journey: "models", label: "System Anatomy", mode: "Organism instrument" },
    { prefix: "/puriq-markets", theme: "market", journey: "products", label: "Puriq Markets", mode: "Market instrument" },
    { prefix: "/evaluations", theme: "decision", journey: "proofs", label: "Evaluation Field", mode: "Evidence instrument" },
    { prefix: "/assurance", theme: "forensic", journey: "proofs", label: "Assurance Record", mode: "Proof instrument" },
    { prefix: "/decision", theme: "decision", journey: "products", label: "Decision Kernel", mode: "Adjudication instrument" },
    { prefix: "/console", theme: "operator", journey: "products", label: "Command Console", mode: "Operations instrument" },
    { prefix: "/command", theme: "operator", journey: "products", label: "Command Plane", mode: "Operations instrument" },
    { prefix: "/estate", theme: "atlas", journey: "models", label: "Estate Atlas", mode: "Topology instrument" },
    { prefix: "/immune", theme: "sentinel", journey: "products", label: "Immune", mode: "Admission instrument" },
    { prefix: "/khipu", theme: "weave", journey: "kernels", label: "KHIPU", mode: "Memory instrument" },
    { prefix: "/lyte", theme: "observatory", journey: "products", label: "Lyte", mode: "Signal instrument" },
    { prefix: "/nexus", theme: "bridge", journey: "kernels", label: "Nexus", mode: "Connection instrument" },
    { prefix: "/terra", theme: "blueprint", journey: "products", label: "Terra", mode: "Property instrument" },
    { prefix: "/aegis", theme: "sentry", journey: "products", label: "Aegis", mode: "Security instrument" },
    { prefix: "/counsel", theme: "counsel", journey: "products", label: "PRISM Counsel", mode: "Matter instrument" },
    { prefix: "/vessels", theme: "voyage", journey: "products", label: "Vessels", mode: "Maritime instrument" },
    { prefix: "/verify", theme: "forensic", journey: "proofs", label: "Receipt Verify", mode: "Proof instrument" },
    { prefix: "/trust", theme: "forensic", journey: "proofs", label: "Trust Record", mode: "Proof instrument" },
    { prefix: "/demo", theme: "decision", journey: "products", label: "Guided Demo", mode: "Procedure instrument" },
    { prefix: "/", theme: "conductor", journey: "start", label: "A11oy Command", mode: "Governed execution fabric" }
  ];

  var JOURNEYS = [
    { id: "start", label: "Start Here", href: PRODUCT + "/" },
    { id: "products", label: "Products & Demos", href: PRODUCT + "/console" },
    { id: "models", label: "Models & Data", href: PRODUCT + "/estate" },
    { id: "kernels", label: "Kernels & SDKs", href: PRODUCT + "/khipu" },
    { id: "proofs", label: "Proofs & Research", href: PROOF + "/record/" }
  ];

  var state = {
    route: null,
    active: !document.hidden,
    pointerX: 50,
    pointerY: 42,
    targetX: 50,
    targetY: 42,
    velocity: 0,
    lastPointerX: 50,
    lastPointerY: 42,
    raf: 0
  };

  function normalizedPath() {
    var path = window.location.pathname || "/";
    if (path.length > 1) path = path.replace(/\/+$/, "");
    return path || "/";
  }

  function resolveRoute() {
    var path = normalizedPath();
    for (var i = 0; i < ROUTES.length; i += 1) {
      var row = ROUTES[i];
      if (row.prefix === "/" || path === row.prefix || path.indexOf(row.prefix + "/") === 0) {
        return row;
      }
    }
    return ROUTES[ROUTES.length - 1];
  }

  function el(name, attrs, text) {
    var node = document.createElement(name);
    Object.keys(attrs || {}).forEach(function (key) {
      if (key === "className") node.className = attrs[key];
      else if (key === "dataset") Object.keys(attrs.dataset).forEach(function (d) { node.dataset[d] = attrs.dataset[d]; });
      else node.setAttribute(key, attrs[key]);
    });
    if (text != null) node.textContent = text;
    return node;
  }

  function ensureSpectralStyle() {
    if (document.querySelector('link[data-szl-spectral-v2="true"]')) return;
    var link = el("link", {
      rel: "stylesheet",
      href: SPECTRAL_STYLE,
      dataset: { szlSpectralV2: "true" }
    });
    document.head.appendChild(link);
  }

  function performanceTier() {
    var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var saveData = Boolean(navigator.connection && navigator.connection.saveData);
    var memory = Number(navigator.deviceMemory || 8);
    var cores = Number(navigator.hardwareConcurrency || 8);
    if (reduced || saveData || memory <= 2 || cores <= 2) return "quiet";
    if (window.innerWidth <= 820 || memory <= 4 || cores <= 4) return "balanced";
    return "full";
  }

  function announce(message) {
    var box = document.querySelector(".szl-flow-announcement");
    if (!box) return;
    box.textContent = message;
    box.dataset.open = "true";
    window.clearTimeout(announce.timer);
    announce.timer = window.setTimeout(function () { box.dataset.open = "false"; }, 1800);
  }

  function markSpectralCards() {
    if (!document.body) return;
    var candidates = document.querySelectorAll(
      "main .card, main .panel, main .tile, main article, main [data-card], main [data-panel]"
    );
    Array.prototype.slice.call(candidates, 0, 120).forEach(function (node) {
      if (node.closest(".szl-flow-rail")) return;
      node.dataset.szlSpectralCard = "true";
    });
    Array.prototype.slice.call(document.querySelectorAll("main > section, main > article"), 0, 80).forEach(function (node) {
      node.dataset.szlReveal = "true";
    });
  }

  function buildSpectralField() {
    if (document.querySelector(".szl-spectral-field")) return;
    var field = el("div", {
      className: "szl-spectral-field",
      "aria-hidden": "true",
      dataset: { version: VERSION }
    });
    ["mesh", "orbit", "nodes", "beam", "scan", "bloom"].forEach(function (name) {
      field.appendChild(el("span", { className: "szl-spectral-layer szl-spectral-" + name }));
    });
    document.body.appendChild(field);
  }

  function setThemeAndCurrent() {
    var route = resolveRoute();
    state.route = route;
    document.body.dataset.szlTheme = route.theme;
    document.body.dataset.szlFlow = "product";
    document.body.dataset.szlSpectral = "product";
    document.body.dataset.szlInstrument = route.label;
    document.documentElement.dataset.szlFlowReady = "true";
    document.documentElement.dataset.szlSpectralV2 = "true";
    document.documentElement.dataset.szlPerformance = performanceTier();
    document.querySelectorAll(".szl-flow-link").forEach(function (link) {
      if (link.dataset.journey === route.journey) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    var context = document.querySelector(".szl-flow-context");
    var mode = document.querySelector(".szl-flow-mode");
    if (context) context.textContent = route.label;
    if (mode) mode.textContent = route.mode;
  }

  function updateProgress() {
    var root = document.documentElement;
    var total = Math.max(1, root.scrollHeight - window.innerHeight);
    var pct = Math.max(0, Math.min(100, (window.scrollY / total) * 100));
    var progress = pct / 100;
    root.style.setProperty("--szl-flow-progress", pct.toFixed(2) + "%");
    root.style.setProperty("--szl-spectral-scroll", progress.toFixed(4));
    root.style.setProperty("--szl-spectral-mesh-shift-y", (-progress * 18).toFixed(2) + "px");
    root.style.setProperty("--szl-spectral-node-shift-y", (-progress * 12).toFixed(2) + "px");
    root.style.setProperty("--szl-spectral-orbit-rotate", (progress * 16).toFixed(2) + "deg");
  }

  function flushPointer() {
    state.raf = 0;
    if (!state.active) return;
    state.pointerX += (state.targetX - state.pointerX) * .18;
    state.pointerY += (state.targetY - state.pointerY) * .18;
    state.velocity *= .82;
    var root = document.documentElement;
    var velocity = Math.min(1, state.velocity / 18);
    root.style.setProperty("--szl-spectral-pointer-x", state.pointerX.toFixed(2) + "%");
    root.style.setProperty("--szl-spectral-pointer-y", state.pointerY.toFixed(2) + "%");
    root.style.setProperty("--szl-spectral-tilt-x", ((state.pointerX - 50) * .055).toFixed(2) + "deg");
    root.style.setProperty("--szl-spectral-tilt-y", ((50 - state.pointerY) * .045).toFixed(2) + "deg");
    root.style.setProperty("--szl-spectral-mesh-shift-x", ((50 - state.pointerX) * .72).toFixed(2) + "px");
    root.style.setProperty("--szl-spectral-orbit-shift-x", ((state.pointerX - 50) * .82).toFixed(2) + "px");
    root.style.setProperty("--szl-spectral-orbit-shift-y", ((state.pointerY - 50) * .62).toFixed(2) + "px");
    root.style.setProperty("--szl-spectral-node-position-x", (50 + (state.pointerX - 50) * .12).toFixed(2) + "%");
    root.style.setProperty("--szl-spectral-node-position-y", (50 + (state.pointerY - 50) * .12).toFixed(2) + "%");
    root.style.setProperty("--szl-spectral-beam-shift-x", ((50 - state.pointerX) * 1.02).toFixed(2) + "px");
    root.style.setProperty("--szl-spectral-beam-shift-y", ((50 - state.pointerY) * .78).toFixed(2) + "px");
    root.style.setProperty("--szl-spectral-velocity", velocity.toFixed(3));
    root.style.setProperty("--szl-spectral-bloom-opacity", (.44 + velocity * .16).toFixed(3));
    root.style.setProperty("--szl-spectral-bloom-scale", (1 + velocity * .025).toFixed(4));
    if (
      Math.abs(state.targetX - state.pointerX) > .08 ||
      Math.abs(state.targetY - state.pointerY) > .08 ||
      state.velocity > .3
    ) schedulePointer();
  }

  function schedulePointer() {
    if (!state.raf) state.raf = window.requestAnimationFrame(flushPointer);
  }

  function onPointer(event) {
    if (document.documentElement.dataset.szlPerformance === "quiet") return;
    var nextX = Math.max(0, Math.min(100, (event.clientX / Math.max(1, window.innerWidth)) * 100));
    var nextY = Math.max(0, Math.min(100, (event.clientY / Math.max(1, window.innerHeight)) * 100));
    var dx = nextX - state.lastPointerX;
    var dy = nextY - state.lastPointerY;
    state.velocity = Math.min(28, state.velocity + Math.sqrt(dx * dx + dy * dy));
    state.lastPointerX = nextX;
    state.lastPointerY = nextY;
    state.targetX = nextX;
    state.targetY = nextY;
    schedulePointer();
  }

  function build() {
    if (!document.body || document.querySelector(".szl-flow-rail")) return;
    var ownsShell = document.documentElement.dataset.szlShellOwner === "homepage";

    ensureSpectralStyle();
    buildSpectralField();

    var progress = el("div", { className: "szl-flow-progress", "aria-hidden": "true" });
    var rail = el("nav", {
      className: "szl-flow-rail",
      "aria-label": "SZL public-estate journeys",
      dataset: { open: "false", version: VERSION }
    });
    var origin = el("div", { className: "szl-flow-origin", title: "a-11-oy.com product origin" });
    origin.appendChild(el("span", {}, "Product"));
    origin.appendChild(el("span", { className: "szl-flow-context" }, "A11oy Command"));
    origin.appendChild(el("span", { className: "szl-flow-mode" }, "Governed execution fabric"));

    var links = el("div", { className: "szl-flow-links", id: "szl-flow-links" });
    JOURNEYS.forEach(function (journey) {
      links.appendChild(el("a", {
        className: "szl-flow-link",
        href: journey.href,
        dataset: { journey: journey.id }
      }, journey.label));
    });

    var actions = el("div", { className: "szl-flow-actions" });
    var toggle = el("button", {
      className: "szl-flow-toggle",
      type: "button",
      "aria-controls": "szl-flow-links",
      "aria-expanded": "false",
      "aria-label": "Open journey navigation"
    }, "Menu");
    toggle.addEventListener("click", function () {
      var open = rail.dataset.open !== "true";
      rail.dataset.open = String(open);
      toggle.setAttribute("aria-expanded", String(open));
      toggle.textContent = open ? "Close" : "Menu";
      if (open) announce("Journey navigation opened");
    });

    var switcher = el("a", {
      className: "szl-flow-switch",
      href: PROOF + "/",
      title: "Open the independent proof and research origin"
    });
    switcher.appendChild(el("span", {}, "Open"));
    switcher.appendChild(el("strong", {}, "Proof record"));

    actions.appendChild(toggle);
    actions.appendChild(switcher);
    rail.appendChild(origin);
    rail.appendChild(links);
    rail.appendChild(actions);

    var live = el("div", {
      className: "szl-flow-announcement",
      role: "status",
      "aria-live": "polite",
      dataset: { open: "false" }
    });

    if (!ownsShell) {
      document.body.appendChild(progress);
      document.body.appendChild(rail);
      document.body.appendChild(live);
    }
    markSpectralCards();
    setThemeAndCurrent();
    updateProgress();
    schedulePointer();

    var scheduled = false;
    window.addEventListener("scroll", function () {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(function () {
        scheduled = false;
        updateProgress();
      });
    }, { passive: true });
    window.addEventListener("resize", function () {
      document.documentElement.dataset.szlPerformance = performanceTier();
      updateProgress();
    }, { passive: true });
    if (window.matchMedia && window.matchMedia("(pointer: fine)").matches) {
      window.addEventListener("pointermove", onPointer, { passive: true });
    }
    document.addEventListener("visibilitychange", function () {
      state.active = !document.hidden;
      if (state.active) schedulePointer();
    });
    document.addEventListener("click", function (event) {
      if (rail.dataset.open !== "true" || rail.contains(event.target)) return;
      rail.dataset.open = "false";
      toggle.setAttribute("aria-expanded", "false");
      toggle.textContent = "Menu";
    });
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" || rail.dataset.open !== "true") return;
      rail.dataset.open = "false";
      toggle.setAttribute("aria-expanded", "false");
      toggle.textContent = "Menu";
      toggle.focus();
    });

    document.dispatchEvent(new CustomEvent("szl:spectral-ready", {
      detail: { version: VERSION, theme: state.route.theme, instrument: state.route.label }
    }));
  }

  function routeChanged() {
    setThemeAndCurrent();
    window.requestAnimationFrame(function () {
      markSpectralCards();
      updateProgress();
    });
  }

  function hookHistory() {
    ["pushState", "replaceState"].forEach(function (name) {
      var original = history[name];
      if (typeof original !== "function") return;
      history[name] = function () {
        var result = original.apply(this, arguments);
        window.dispatchEvent(new Event("szl:routechange"));
        return result;
      };
    });
    window.addEventListener("popstate", routeChanged);
    window.addEventListener("szl:routechange", routeChanged);
  }

  hookHistory();
  ensureSpectralStyle();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build, { once: true });
  else build();
}());
