/*
 * A11oy Holo-Constellation v2.0.0
 * Experience convergence: one global navigation, contextual product controls,
 * deterministic route identity, and bounded decorative motion.
 * No fetch, tracking, storage, cookies, or copied design code.
 * SPDX-License-Identifier: Apache-2.0
 */
(() => {
  "use strict";

  if (window.__SZL_HOLO_V2__) return;
  window.__SZL_HOLO_V2__ = true;

  const VERSION = "2.1.0";
  const PRODUCT = "https://a-11-oy.com";
  const PROOF = "https://a11oy.net";
  const REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
  const FINE_POINTER = window.matchMedia("(pointer: fine)");
  const SAVE_DATA = Boolean(navigator.connection && navigator.connection.saveData);

  const PRIMARY_NAV = [
    ["Overview", `${PRODUCT}/`],
    ["Platform", `${PRODUCT}/console`],
    ["Portfolio", `${PRODUCT}/estate`],
    ["Proof", `${PROOF}/record/`],
    ["Investor", `${PRODUCT}/console?view=investor`],
  ];

  // SZL KANCHAY founder direction (kit 1.1.1): every surface shares one palette of
  // design-system tokens from /assets/szl/szl-design-system.css. Slots: background,
  // surface, foreground, muted, accent, accent-2. Both accents are silver linework;
  // coral stays with the page's one moment and teal with links and focus.
  const FOUNDER_PALETTE = Object.freeze([
    "var(--bg)", "var(--surface)", "var(--text)", "var(--text-sub)",
    "var(--color-silver-300)", "var(--color-silver-500)",
  ]);

  const PALETTES = [FOUNDER_PALETTE];

  const CURATED = {
    a11oy: {
      label: "A11oy Command",
      motif: "command-constellation",
      palette: FOUNDER_PALETTE,
    },
    proof: {
      label: "A11oy Proof Network",
      motif: "evidence-vault",
      palette: FOUNDER_PALETTE,
    },
    lyte: {
      label: "Lyte",
      motif: "signal-aurora",
      palette: FOUNDER_PALETTE,
    },
    vessels: {
      label: "Vessels",
      motif: "bathymetric-radar",
      palette: FOUNDER_PALETTE,
    },
    terra: {
      label: "Terra",
      motif: "topographic-parcels",
      palette: FOUNDER_PALETTE,
    },
    aegis: {
      label: "Aegis",
      motif: "threat-lattice",
      palette: FOUNDER_PALETTE,
    },
    "prism-counsel": {
      label: "PRISM Counsel",
      motif: "case-facets",
      palette: FOUNDER_PALETTE,
    },
    "carlota-jo": {
      label: "Carlota Jo",
      motif: "editorial-orbit",
      palette: FOUNDER_PALETTE,
    },
    nexus: {
      label: "Nexus",
      motif: "connection-field",
      palette: FOUNDER_PALETTE,
    },
    factory: {
      label: "A11oy Factory",
      motif: "assembly-circuit",
      palette: FOUNDER_PALETTE,
    },
    ouroboros: {
      label: "Ouroboros",
      motif: "recursive-ring",
      palette: FOUNDER_PALETTE,
    },
    khipu: {
      label: "KHIPU",
      motif: "woven-proof",
      palette: FOUNDER_PALETTE,
    },
    killinchu: {
      label: "Killinchu",
      motif: "agent-swarm",
      palette: FOUNDER_PALETTE,
    },
  };

  const ROUTE_HINTS = [
    ["prism-counsel", ["prism-counsel", "prism counsel", "/counsel", "/legal"]],
    ["carlota-jo", ["carlota-jo", "carlota jo", "/advisory"]],
    ["ouroboros", ["ouroboros", "/research", "/thesis"]],
    ["killinchu", ["killinchu", "/agents", "agent forge", "agent swarm"]],
    ["factory", ["a11oy-factory", "szl-factory", "/factory", "/forge", "artifact factory"]],
    ["vessels", ["vessels", "/maritime", "fleet command", "voyage"]],
    ["terra", ["terra", "/real-estate", "real estate", "parcel"]],
    ["aegis", ["aegis", "/security", "/defense", "threat"]],
    ["lyte", ["lyte", "/observability", "business observability", "signal"]],
    ["nexus", ["nexus", "/integration", "connection fabric"]],
    ["khipu", ["khipu", "/kernel", "woven proof"]],
  ];

  const MOTIFS = [
    "command-constellation",
    "signal-aurora",
    "bathymetric-radar",
    "topographic-parcels",
    "threat-lattice",
    "case-facets",
    "editorial-orbit",
    "connection-field",
    "assembly-circuit",
    "recursive-ring",
    "woven-proof",
    "agent-swarm",
  ];

  function slug(value) {
    return String(value || "")
      .normalize("NFKD")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 96);
  }

  function fnv1a(value) {
    let result = 0x811c9dc5;
    for (const character of String(value || "a11oy")) {
      result ^= character.charCodeAt(0);
      result = Math.imul(result, 0x01000193) >>> 0;
    }
    return result >>> 0;
  }

  function titleCase(value) {
    return String(value || "")
      .split("-")
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function huggingFaceSlug(host) {
    const match = host.match(/^(?:szlholdings|szl-holdings)-(.+)\.hf\.space$/i);
    return match ? slug(match[1]) : "";
  }

  function surfaceCandidate() {
    const host = location.hostname.toLowerCase();
    if (host === "a11oy.net" || host === "www.a11oy.net") return "proof";
    if (host === "a-11-oy.com" || host === "www.a-11-oy.com") {
      const path = location.pathname.toLowerCase();
      for (const [surface, hints] of ROUTE_HINTS) {
        if (hints.some((hint) => path.includes(hint.replace(" ", "-")))) return surface;
      }
      return "a11oy";
    }

    const hf = huggingFaceSlug(host);
    const path = location.pathname.toLowerCase();
    const title = document.title.toLowerCase();
    const bodyIdentity = `${document.body?.id || ""} ${document.body?.className || ""}`.toLowerCase();
    const haystack = `${host} ${hf} ${path} ${title} ${bodyIdentity}`;
    for (const [surface, hints] of ROUTE_HINTS) {
      if (hints.some((hint) => haystack.includes(hint))) return surface;
    }
    if (hf) return hf;
    return slug(path.split("/").filter(Boolean)[0]) || slug(host) || "a11oy";
  }

  function resolveTheme() {
    const id = surfaceCandidate();
    const curated = CURATED[id];
    if (curated) return { id, ...curated, source: "curated" };
    const seed = fnv1a(id);
    return {
      id,
      label: titleCase(id) || "A11oy Space",
      motif: MOTIFS[(seed >>> 8) % MOTIFS.length],
      palette: PALETTES[seed % PALETTES.length],
      source: "deterministic",
    };
  }

  function applyTheme(theme) {
    const [background, surface, foreground, muted, accent, accent2] = theme.palette;
    const root = document.documentElement;
    root.dataset.szlHolo = "v2";
    root.dataset.szlHoloSurface = theme.id;
    root.dataset.szlHoloMotif = theme.motif;
    root.dataset.szlHoloThemeSource = theme.source;
    root.style.setProperty("--szl-holo-bg", background);
    root.style.setProperty("--szl-holo-bg-deep", background);
    root.style.setProperty("--szl-holo-surface", surface);
    root.style.setProperty("--szl-holo-surface-2", surface);
    root.style.setProperty("--szl-holo-ink", foreground);
    root.style.setProperty("--szl-holo-muted", muted);
    root.style.setProperty("--szl-holo-accent", accent);
    root.style.setProperty("--szl-holo-accent-2", accent2);
  }

  function createElement(name, attributes = {}, text = null) {
    const node = document.createElement(name);
    for (const [key, value] of Object.entries(attributes)) {
      if (key === "className") node.className = value;
      else if (key === "dataset") Object.assign(node.dataset, value);
      else node.setAttribute(key, value);
    }
    if (text !== null) node.textContent = text;
    return node;
  }

  function addSkipLink() {
    if (document.querySelector(".szl-holo-skip, [data-szl-holo-skip]")) return;
    if (document.documentElement.dataset.szlShellOwner === "homepage" &&
        document.querySelector('.skip-link[href="#main"]')) return;
    const main = document.querySelector("main, [role='main'], .content");
    if (!main) return;
    if (!main.id) main.id = "szl-holo-main";
    document.body.prepend(createElement("a", {
      className: "szl-holo-skip",
      href: `#${main.id}`,
      dataset: { szlHoloSkip: "true" },
    }, "Skip to main content"));
  }

  function currentLink(href) {
    const target = new URL(href);
    const host = location.hostname.replace(/^www\./, "");
    if (target.hostname.replace(/^www\./, "") !== host) return false;
    if (target.searchParams.get("view")) {
      return new URLSearchParams(location.search).get("view") === target.searchParams.get("view");
    }
    if (target.pathname === "/") return location.pathname === "/";
    return location.pathname.startsWith(target.pathname.replace(/\/$/, ""));
  }

  function addPrimaryLinks(nav, className) {
    for (const [label, href] of PRIMARY_NAV) {
      const attributes = { className, href };
      if (currentLink(href)) attributes["aria-current"] = "page";
      nav.append(createElement("a", attributes, label));
    }
  }

  function hasProductCommandBar() {
    return Boolean(document.querySelector("[data-szl-command-bar], .szl-hbar"));
  }

  function buildRail(theme) {
    if (
      document.documentElement.dataset.szlShellOwner === "homepage" ||
      hasProductCommandBar() ||
      document.querySelector(".szl-holo-rail") ||
      document.documentElement.hasAttribute("data-szl-holo-no-rail")
    ) return;

    const rail = createElement("header", {
      className: "szl-holo-rail",
      dataset: { szlHoloRail: "v2" },
    });
    const identity = createElement("a", {
      className: "szl-holo-identity",
      href: `${PRODUCT}/`,
      "aria-label": "Open the A11oy overview",
    });
    identity.append(createElement("span", { className: "szl-holo-mark", "aria-hidden": "true" }));
    const copy = createElement("span", { className: "szl-holo-copy" });
    copy.append(createElement("span", { className: "szl-holo-eyebrow" }, "SZL · GOVERNED AI"));
    copy.append(createElement("span", { className: "szl-holo-label" }, theme.label));
    identity.append(copy);

    const controls = createElement("div", { className: "szl-holo-controls" });
    const menu = createElement("button", {
      className: "szl-holo-menu",
      type: "button",
      "aria-label": "Open primary navigation",
      "aria-expanded": "false",
      "aria-controls": "szl-holo-nav",
    }, "Menu");
    const nav = createElement("nav", {
      className: "szl-holo-nav",
      id: "szl-holo-nav",
      "aria-label": "Primary",
      dataset: { open: "false" },
    });
    addPrimaryLinks(nav, "szl-holo-link");
    controls.append(menu, nav);
    rail.append(identity, controls);
    document.body.prepend(rail);

    const close = ({ focus = false } = {}) => {
      nav.dataset.open = "false";
      menu.setAttribute("aria-expanded", "false");
      menu.setAttribute("aria-label", "Open primary navigation");
      menu.textContent = "Menu";
      if (focus) menu.focus();
    };
    menu.addEventListener("click", () => {
      const open = nav.dataset.open !== "true";
      nav.dataset.open = String(open);
      menu.setAttribute("aria-expanded", String(open));
      menu.setAttribute("aria-label", open ? "Close primary navigation" : "Open primary navigation");
      menu.textContent = open ? "Close" : "Menu";
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && nav.dataset.open === "true") close({ focus: true });
    });
    document.addEventListener("pointerdown", (event) => {
      if (nav.dataset.open === "true" && !rail.contains(event.target)) close();
    });
  }

  function addAmbient() {
    if (document.getElementById("szl-holo-ambient")) return;
    document.body.prepend(createElement("div", {
      id: "szl-holo-ambient",
      "aria-hidden": "true",
      dataset: { szlHoloDecorative: "true" },
    }));
  }

  function addProgress() {
    if (document.querySelector(".szl-holo-progress")) return;
    document.body.append(createElement("div", {
      className: "szl-holo-progress",
      "aria-hidden": "true",
      dataset: { szlHoloDecorative: "true" },
    }));
  }

  function enhancePanels() {
    if (document.documentElement.hasAttribute("data-szl-holo-no-auto-panels")) return;
    const selectors = [
      "main .card", "main .panel", "main .metric-card", "main .feature-card",
      "main [class*='glass-card']", "main [class*='holo-card']", "main [data-panel]",
    ];
    const seen = new Set();
    for (const node of document.querySelectorAll(selectors.join(","))) {
      if (seen.size >= 24) break;
      if (seen.has(node) || node.closest("nav, header, footer, table, pre, code, form, dialog")) continue;
      seen.add(node);
      node.setAttribute("data-szl-holo-panel", "auto");
    }
  }

  function installMotion() {
    const root = document.documentElement;
    let pointerFrame = 0;
    let scrollFrame = 0;
    let lastX = window.innerWidth / 2;
    let lastY = Math.min(window.innerHeight * 0.22, 240);

    const commitPointer = () => {
      pointerFrame = 0;
      root.style.setProperty("--szl-holo-pointer-x", `${Math.round((lastX / Math.max(window.innerWidth, 1)) * 1000) / 10}%`);
      root.style.setProperty("--szl-holo-pointer-y", `${Math.round((lastY / Math.max(window.innerHeight, 1)) * 1000) / 10}%`);
    };
    const pointer = (event) => {
      if (REDUCE_MOTION.matches || !FINE_POINTER.matches || SAVE_DATA || document.hidden) return;
      lastX = event.clientX;
      lastY = event.clientY;
      if (!pointerFrame) pointerFrame = requestAnimationFrame(commitPointer);
    };
    const commitScroll = () => {
      scrollFrame = 0;
      const maximum = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      const percentage = Math.max(0, Math.min(100, (window.scrollY / maximum) * 100));
      root.style.setProperty("--szl-holo-scroll", percentage.toFixed(2));
    };
    const scroll = () => {
      if (!scrollFrame) scrollFrame = requestAnimationFrame(commitScroll);
    };

    if (!SAVE_DATA) window.addEventListener("pointermove", pointer, { passive: true });
    window.addEventListener("scroll", scroll, { passive: true });
    window.addEventListener("resize", scroll, { passive: true });
    document.addEventListener("visibilitychange", () => {
      root.dataset.szlHoloPaused = String(document.hidden);
      if (!document.hidden) scroll();
    });
    REDUCE_MOTION.addEventListener?.("change", () => {
      root.dataset.szlHoloReducedMotion = String(REDUCE_MOTION.matches);
    });
    root.dataset.szlHoloReducedMotion = String(REDUCE_MOTION.matches);
    root.dataset.szlHoloSaveData = String(SAVE_DATA);
    commitPointer();
    commitScroll();
  }

  function boot() {
    if (!document.body || document.documentElement.hasAttribute("data-szl-holo-disabled")) return;
    const theme = resolveTheme();
    applyTheme(theme);
    addAmbient();
    addProgress();
    addSkipLink();
    buildRail(theme);
    enhancePanels();
    installMotion();

    window.SZLHolo = Object.freeze({
      version: VERSION,
      theme: Object.freeze({ ...theme, palette: [...theme.palette] }),
      resolveTheme,
      fnv1a,
      decorativeMotion: true,
      measuredTelemetry: false,
    });
    document.dispatchEvent(new CustomEvent("szl:holo-ready", {
      detail: { version: VERSION, surface: theme.id, motif: theme.motif, source: theme.source },
    }));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();

/* SZL FLUID ESTATE RAIL V4 */
(function (global) {
  "use strict";

  if (global.__SZL_FLUID_ESTATE_RAIL_V4__) return;
  global.__SZL_FLUID_ESTATE_RAIL_V4__ = true;

  var VERSION = "5.0.0";
  var SURFACES = [
    { id: "a11oy", label: "A11OY", href: "/console", paths: ["/", "/console", "/command", "/command-center"] },
    { id: "killinchu", label: "KILLINCHU", href: "/killinchu", paths: ["/killinchu", "/counter-uas", "/vessels"] },
    { id: "hatun", label: "HATUN", href: "/hatun-mcp", paths: ["/hatun-mcp", "/mcp"] },
    { id: "cockpit", label: "COCKPIT", href: "/cockpit", paths: ["/cockpit"] },
    { id: "brain", label: "SECOND BRAIN", href: "/brain", paths: ["/brain", "/brain-dual", "/brain-jack"], bind: "brain-anatomy", title: "Canonical second-brain knowledge surface" },
    { id: "anatomy", label: "ANATOMY", href: "/anatomy-v5", paths: ["/anatomy-v5", "/anatomy"], bind: "brain-anatomy", title: "Evidence-labelled digital twin wired to Brain pulse" },
    { id: "living-anatomy", label: "LIVING ANATOMY", href: "/living-anatomy", paths: ["/living-anatomy"], bind: "brain-anatomy", title: "Living organism view for A11oy and Killinchu" },
    { id: "khipu", label: "KHIPU", href: "/khipu", paths: ["/khipu", "/sovereign"] },
    { id: "immune", label: "IMMUNE", href: "/immune", paths: ["/immune"] },
    { id: "lyte", label: "LYTE", href: "/lyte", paths: ["/lyte", "/observability"] },
    { id: "estate", label: "ESTATE", href: "/estate", paths: ["/estate", "/spaces"] }
  ];

  var TOP_LINKS = [
    { id: "overview", label: "Overview", href: "/" },
    { id: "platform", label: "Platform", href: "/console" },
    { id: "portfolio", label: "Portfolio", href: "/estate" },
    { id: "proof", label: "Proof", href: "https://a11oy.net/record/" },
    { id: "investor", label: "Investor", href: "/console?view=investor" }
  ];

  function normalizedPath() {
    var path = global.location && global.location.pathname ? global.location.pathname : "/";
    if (path.length > 1) path = path.replace(/\/+$/, "");
    return path || "/";
  }

  function pathMatches(path, candidate) {
    if (candidate === "/") return path === "/";
    return path === candidate || path.indexOf(candidate + "/") === 0;
  }

  function isCurrent(surface, path) {
    if (surface.id === "investor") {
      try { return new URLSearchParams(global.location.search || "").get("view") === "investor"; }
      catch (e) { return false; }
    }
    return (surface.paths || [surface.href]).some(function (candidate) { return pathMatches(path, candidate); });
  }

  function makeAnchor(surface, path) {
    var link = document.createElement("a");
    link.className = "flag szl-estate-link";
    link.href = surface.href;
    link.textContent = surface.label;
    link.dataset.surface = surface.id;
    if (surface.bind) link.dataset.bind = surface.bind;
    if (surface.title) link.title = surface.title;
    if (isCurrent(surface, path)) link.setAttribute("aria-current", "page");
    return link;
  }

  function reducedMotion() {
    return Boolean(global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  function scrollBehavior() {
    return reducedMotion() ? "auto" : "smooth";
  }

  /* Compatibility scroller for long contextual collections; primary nav does not invoke it. */
  function bindScroller(shell, nav, previous, next) {
    var links = Array.prototype.slice.call(nav.querySelectorAll("a.szl-estate-link"));
    function bounds() {
      var max = Math.max(0, nav.scrollWidth - nav.clientWidth);
      return { max: max, start: nav.scrollLeft <= 2, end: nav.scrollLeft >= max - 2 };
    }
    function update() {
      var state = bounds();
      shell.classList.toggle("can-left", state.max > 2 && !state.start);
      shell.classList.toggle("can-right", state.max > 2 && !state.end);
      previous.disabled = state.max <= 2 || state.start;
      next.disabled = state.max <= 2 || state.end;
    }
    function step(direction) {
      nav.scrollBy({ left: direction * Math.max(190, Math.round(nav.clientWidth * .72)), behavior: scrollBehavior() });
    }
    previous.setAttribute("aria-label", "Scroll estate tabs left");
    next.setAttribute("aria-label", "Scroll estate tabs right");
    previous.addEventListener("click", function () { step(-1); });
    next.addEventListener("click", function () { step(1); });
    nav.addEventListener("scroll", update, { passive: true });
    nav.addEventListener("wheel", function (event) {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
      event.preventDefault();
      nav.scrollLeft += event.deltaY;
    }, { passive: false });
    nav.addEventListener("keydown", function (event) {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      var index = links.indexOf(document.activeElement);
      var target = event.key === "Home" ? links[0]
        : event.key === "End" ? links[links.length - 1]
        : event.key === "ArrowLeft" ? links[Math.max(0, index - 1)]
        : links[Math.min(links.length - 1, index + 1)];
      if (!target) return;
      event.preventDefault();
      target.focus();
      target.scrollIntoView({ block: "nearest", inline: "center", behavior: scrollBehavior() });
    });
    if ("ResizeObserver" in global) {
      var observer = new global.ResizeObserver(update);
      observer.observe(nav);
      shell.__szlResizeObserver = observer;
    }
    global.requestAnimationFrame(update);
  }

  function primaryAnchor(item, path) {
    var link = document.createElement("a");
    link.className = "flag szl-estate-link szl-primary-link";
    link.href = item.href;
    link.textContent = item.label;
    link.dataset.surface = item.id;
    if (isCurrent(item, path)) link.setAttribute("aria-current", "page");
    return link;
  }

  function addContextualMenu(menu) {
    if (!menu || menu.dataset.szlPortfolioReady === "true") return;
    var divider = document.createElement("span");
    divider.className = "szl-overflow-label";
    divider.textContent = "Product surfaces";
    menu.appendChild(divider);
    SURFACES.filter(function (surface) {
      return !["a11oy", "estate"].includes(surface.id);
    }).forEach(function (surface) {
      menu.appendChild(makeAnchor(surface, normalizedPath()));
    });
    menu.dataset.szlPortfolioReady = "true";
  }

  function simplifyScope(root) {
    var crumb = root.querySelector(".szl-hbar-crumb");
    if (!crumb || crumb.dataset.szlSimplified === "true") return;
    var surface = root.getAttribute("data-surface") || "Command";
    crumb.textContent = "";
    var product = document.createElement("span");
    product.className = "szl-command-product";
    product.textContent = "A11oy";
    var context = document.createElement("span");
    context.className = "szl-command-context";
    context.textContent = surface;
    crumb.appendChild(product);
    crumb.appendChild(context);
    crumb.dataset.szlSimplified = "true";
  }

  function enhanceCommandBar() {
    var root = document.querySelector(".szl-hbar");
    var nav = root && root.querySelector(".szl-estate");
    if (!root || !nav || nav.dataset.szlFluidEstate === "v5") return false;

    var path = normalizedPath();
    nav.dataset.szlFluidEstate = "v5";
    nav.dataset.version = VERSION;
    nav.setAttribute("aria-label", "Primary");
    nav.textContent = "";
    TOP_LINKS.forEach(function (item) { nav.appendChild(primaryAnchor(item, path)); });

    var origins = root.querySelector(".szl-origins");
    var investor = root.querySelector("#inv-toggle");
    if (origins) origins.hidden = true;
    if (investor) investor.hidden = true;

    simplifyScope(root);
    addContextualMenu(root.querySelector(".szl-overflow-menu"));
    root.dataset.szlNavigation = "converged";
    document.documentElement.dataset.szlBrainAnatomyNav = "bound";
    document.documentElement.dataset.szlPrimaryNavigation = "five";
    return true;
  }

  function enhanceHoloNav() {
    var nav = document.querySelector(".szl-holo-nav");
    if (!nav || nav.dataset.szlEstateLinks === "v5") return false;
    nav.dataset.szlEstateLinks = "v5";
    nav.setAttribute("aria-label", "Primary");
    return true;
  }

  function boot() {
    enhanceCommandBar();
    enhanceHoloNav();

    var observer = new MutationObserver(function () {
      var commandReady = enhanceCommandBar() || Boolean(document.querySelector('.szl-estate[data-szl-fluid-estate="v5"]'));
      var holoReady = enhanceHoloNav() || Boolean(document.querySelector('.szl-holo-nav[data-szl-estate-links="v5"]'));
      if (commandReady || holoReady) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    global.setTimeout(function () { observer.disconnect(); }, 15000);

    global.SZLNavigation = Object.freeze({
      version: VERSION,
      primary: TOP_LINKS.map(function (item) { return Object.freeze({ id: item.id, label: item.label, href: item.href }); }),
      contextual: SURFACES.map(function (item) { return Object.freeze({ id: item.id, label: item.label, href: item.href }); }),
      bindScroller: bindScroller
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})(window);
