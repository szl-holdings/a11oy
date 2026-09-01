/* SZL Flow Shell v1 — shared navigation and route-aware product instruments. */
(function () {
  "use strict";

  if (window.__SZL_FLOW_SHELL__) return;
  window.__SZL_FLOW_SHELL__ = true;

  var PRODUCT = "https://a-11-oy.com";
  var PROOF = "https://a11oy.net";
  var ROUTES = [
    { prefix: "/static/viz/doctrine", theme: "forensic", journey: "kernels" },
    { prefix: "/static/viz/router", theme: "bridge", journey: "kernels" },
    { prefix: "/living-anatomy", theme: "anatomy", journey: "models" },
    { prefix: "/anatomy", theme: "anatomy", journey: "models" },
    { prefix: "/puriq-markets", theme: "market", journey: "products" },
    { prefix: "/evaluations", theme: "decision", journey: "proofs" },
    { prefix: "/assurance", theme: "forensic", journey: "proofs" },
    { prefix: "/decision", theme: "decision", journey: "products" },
    { prefix: "/console", theme: "operator", journey: "products" },
    { prefix: "/command", theme: "operator", journey: "products" },
    { prefix: "/estate", theme: "atlas", journey: "models" },
    { prefix: "/immune", theme: "sentinel", journey: "products" },
    { prefix: "/khipu", theme: "weave", journey: "kernels" },
    { prefix: "/lyte", theme: "observatory", journey: "products" },
    { prefix: "/nexus", theme: "bridge", journey: "kernels" },
    { prefix: "/terra", theme: "blueprint", journey: "products" },
    { prefix: "/aegis", theme: "sentry", journey: "products" },
    { prefix: "/counsel", theme: "counsel", journey: "products" },
    { prefix: "/vessels", theme: "voyage", journey: "products" },
    { prefix: "/verify", theme: "forensic", journey: "proofs" },
    { prefix: "/trust", theme: "forensic", journey: "proofs" },
    { prefix: "/demo", theme: "decision", journey: "products" },
    { prefix: "/", theme: "conductor", journey: "start" }
  ];

  var JOURNEYS = [
    { id: "start", label: "Start Here", href: PRODUCT + "/" },
    { id: "products", label: "Products & Demos", href: PRODUCT + "/console" },
    { id: "models", label: "Models & Data", href: PRODUCT + "/estate" },
    { id: "kernels", label: "Kernels & SDKs", href: PRODUCT + "/khipu" },
    { id: "proofs", label: "Proofs & Research", href: PROOF + "/record/" }
  ];

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

  function announce(message) {
    var box = document.querySelector(".szl-flow-announcement");
    if (!box) return;
    box.textContent = message;
    box.dataset.open = "true";
    window.clearTimeout(announce.timer);
    announce.timer = window.setTimeout(function () { box.dataset.open = "false"; }, 1800);
  }

  function setThemeAndCurrent() {
    var route = resolveRoute();
    document.body.dataset.szlTheme = route.theme;
    document.body.dataset.szlFlow = "product";
    document.documentElement.dataset.szlFlowReady = "true";
    document.querySelectorAll(".szl-flow-link").forEach(function (link) {
      if (link.dataset.journey === route.journey) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  function updateProgress() {
    var root = document.documentElement;
    var total = Math.max(1, root.scrollHeight - window.innerHeight);
    var pct = Math.max(0, Math.min(100, (window.scrollY / total) * 100));
    root.style.setProperty("--szl-flow-progress", pct.toFixed(2) + "%");
  }

  function build() {
    if (!document.body || document.querySelector(".szl-flow-rail")) return;

    var progress = el("div", { className: "szl-flow-progress", "aria-hidden": "true" });
    var rail = el("nav", {
      className: "szl-flow-rail",
      "aria-label": "SZL public-estate journeys",
      dataset: { open: "false" }
    });
    var origin = el("div", { className: "szl-flow-origin", title: "a-11-oy.com product origin" });
    origin.appendChild(el("span", {}, "Product"));

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

    document.body.appendChild(progress);
    document.body.appendChild(rail);
    document.body.appendChild(live);
    setThemeAndCurrent();
    updateProgress();

    var scheduled = false;
    window.addEventListener("scroll", function () {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(function () {
        scheduled = false;
        updateProgress();
      });
    }, { passive: true });
    window.addEventListener("resize", updateProgress, { passive: true });
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
    window.addEventListener("popstate", setThemeAndCurrent);
    window.addEventListener("szl:routechange", setThemeAndCurrent);
  }

  hookHistory();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build, { once: true });
  else build();
}());
