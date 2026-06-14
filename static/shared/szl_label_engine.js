/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 * ============================================================================
 * szl_label_engine.js - SHARED MODULE (byte-identical across a11oy + killinchu)
 * ----------------------------------------------------------------------------
 * The single honest-label primitive for the SZL estate. Renders the canonical
 * doctrine badges. NO build step, NO CDN, vanilla ES5-safe JS, browser + Node.
 *
 * Doctrine gate G7 (honest labels) + G8 (the half-state is the only
 * unacceptable outcome). Every demo surface labels what is real; this module is
 * the one place the badge vocabulary, colors and semantics live so the two apps
 * never drift. Importing tabs MUST NOT invent their own pills.
 *
 * Canonical badge vocabulary (the ONLY allowed honest labels):
 *   LIVE          - real backend wired, data is genuinely live, honest
 *   SAMPLE        - honest sample / illustrative fixture (not live)
 *   FORECAST      - model-produced forward estimate (e.g. seismic pulse)
 *   OSINT         - open-source intelligence (sensed, unauthenticated claims)
 *   MODELED       - deterministic model output, labeled (e.g. RUL, ent. forecast)
 *   SIMULATED     - effector / decision simulation, human-on-the-loop (G6)
 *   CONNECT-READY - real schema, awaits OAuth; sample until connected
 *   EXPERIMENTAL  - CI-green Lean wave, not locked-8
 *   HEURISTIC     - rule/heuristic advisory, not proven
 *   PQC-ROADMAP   - post-quantum signing is roadmap, never shown deployed (G4)
 *   ILLUSTRATIVE  - explicitly illustrative (e.g. wow ROI)
 *
 * Public API (window.SZLLabels / module.exports):
 *   SCHEMES                          - frozen registry {KEY:{label,cls,title,...}}
 *   badge(key, opts?)                - returns an HTMLElement <span class="szl-pill ...">
 *   badgeHTML(key, opts?)            - returns a sanitized HTML string
 *   isHonestLabel(key)               - boolean: is this a canonical honest label?
 *   normalize(key)                   - canonicalizes aliases ("connect_ready" -> "CONNECT-READY")
 *   auditText(str)                   - returns [] of forbidden raw claims (e.g. "100%", "tamper-proof")
 *   ensureStyle(doc?)                - injects the <style> once (idempotent)
 * ============================================================================ */
(function (root, factory) {
  var mod = factory();
  if (typeof module === "object" && module.exports) { module.exports = mod; }
  if (root) { root.SZLLabels = mod; }
})(typeof self !== "undefined" ? self : (typeof window !== "undefined" ? window : null), function () {
  "use strict";

  /* Canonical registry. cls is a CSS modifier; colors are doctrine-fixed so the
   * two apps render identical pills. tone: ok|warn|info|sim|bad — drives color. */
  var SCHEMES = {
    "LIVE":          { label: "LIVE",          tone: "ok",   title: "Real backend wired - data is genuinely live and honest." },
    "SAMPLE":        { label: "SAMPLE",        tone: "info", title: "Honest sample / illustrative fixture - not a live feed." },
    "FORECAST":      { label: "FORECAST",      tone: "warn", title: "Model-produced forward estimate. Not an observation." },
    "OSINT":         { label: "OSINT",         tone: "info", title: "Open-source intelligence. Sensed, unauthenticated claims." },
    "MODELED":       { label: "MODELED",       tone: "warn", title: "Deterministic model output, labeled. Not measured." },
    "SIMULATED":     { label: "SIMULATED",     tone: "sim",  title: "Effector / decision simulation, human-on-the-loop. No live control." },
    "CONNECT-READY": { label: "CONNECT-READY", tone: "info", title: "Real schema, awaits OAuth. Sample data until connected." },
    "EXPERIMENTAL":  { label: "EXPERIMENTAL",  tone: "warn", title: "CI-green Lean wave - NOT part of the locked-8." },
    "HEURISTIC":     { label: "HEURISTIC",     tone: "warn", title: "Rule / heuristic advisory. Not a proven result." },
    "PQC-ROADMAP":   { label: "PQC-ROADMAP",   tone: "warn", title: "Post-quantum signing is roadmap. Never shown as deployed (G4)." },
    "ILLUSTRATIVE":  { label: "ILLUSTRATIVE",  tone: "info", title: "Explicitly illustrative figure (e.g. ROI)." }
  };
  // freeze so importing tabs cannot mutate the doctrine vocabulary
  try { Object.freeze(SCHEMES); for (var k in SCHEMES) { Object.freeze(SCHEMES[k]); } } catch (e) {}

  var ALIASES = {
    "CONNECT_READY": "CONNECT-READY", "CONNECTREADY": "CONNECT-READY",
    "PQC_ROADMAP": "PQC-ROADMAP", "PQCROADMAP": "PQC-ROADMAP", "PQC": "PQC-ROADMAP",
    "SIM": "SIMULATED", "EXP": "EXPERIMENTAL", "MODEL": "MODELED"
  };

  function normalize(key) {
    if (key == null) { return ""; }
    var u = String(key).trim().toUpperCase().replace(/\s+/g, "-");
    if (SCHEMES[u]) { return u; }
    var nodash = u.replace(/[-_]/g, "");
    if (ALIASES[u]) { return ALIASES[u]; }
    if (ALIASES[nodash]) { return ALIASES[nodash]; }
    return u; // unknown - caller decides
  }

  function isHonestLabel(key) { return Object.prototype.hasOwnProperty.call(SCHEMES, normalize(key)); }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /* Forbidden raw claims a tab must never render (doctrine G2/G3/G4/G7).
   * auditText() returns the list of violations found in a rendered string. */
  var FORBIDDEN = [
    { re: /\b100\s*%/,                              why: "trust is never 100% (Lambda capped < 1.0)" },
    { re: /\btamper-?proof\b/i,                     why: "use 'tamper-evident', not 'tamper-proof' (G3)" },
    { re: /\bunique\s+theorem\b/i,                  why: "Lambda uniqueness is Conjecture 1, not a theorem (G2)" },
    { re: /\bunconditional(ly)?\s+(unique|proven)\b/i, why: "Lambda uniqueness is conditional (Conjecture 1) (G2)" },
    { re: /\bSLSA\s*L3\b(?!\s*roadmap)/i,           why: "SLSA must read 'L1 honest / L2 attested / L3 roadmap' (G4)" },
    { re: /\b(FedRAMP|IronBank|CMMC|ATO)\b/i,       why: "never claim FedRAMP/IronBank/CMMC/ATO as achieved (G4)" },
    { re: /\blocked\s*=?\s*5\b/i,                   why: "locked-proven is EXACTLY 8, never 5 (G1)" }
  ];
  function auditText(str) {
    var out = [], s = String(str == null ? "" : str), i;
    for (i = 0; i < FORBIDDEN.length; i++) { if (FORBIDDEN[i].re.test(s)) { out.push(FORBIDDEN[i].why); } }
    return out;
  }

  var STYLE_ID = "szl-label-engine-style";
  var CSS =
    "." + "szl-pill{display:inline-flex;align-items:center;gap:6px;font:700 11px/1 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;" +
    "letter-spacing:.04em;padding:4px 9px;border-radius:7px;border:1px solid;text-transform:uppercase;white-space:nowrap;vertical-align:middle;}" +
    ".szl-pill .szl-dot{width:7px;height:7px;border-radius:50%;background:currentColor;flex:0 0 auto;}" +
    ".szl-pill.ok{color:#16c784;border-color:#16c78455;background:#16c7841a;}" +
    ".szl-pill.warn{color:#e0a106;border-color:#e0a10655;background:#e0a1061a;}" +
    ".szl-pill.info{color:#3aa0ff;border-color:#3aa0ff55;background:#3aa0ff1a;}" +
    ".szl-pill.sim{color:#b07cff;border-color:#b07cff55;background:#b07cff1a;}" +
    ".szl-pill.bad{color:#ff5c5c;border-color:#ff5c5c55;background:#ff5c5c1a;}" +
    ".szl-pill.unknown{color:#888;border-color:#88888855;background:#8888881a;}";

  function ensureStyle(doc) {
    var d = doc || (typeof document !== "undefined" ? document : null);
    if (!d || d.getElementById(STYLE_ID)) { return; }
    var st = d.createElement("style"); st.id = STYLE_ID; st.textContent = CSS;
    (d.head || d.documentElement).appendChild(st);
  }

  function resolve(key) {
    var nk = normalize(key);
    var s = SCHEMES[nk];
    if (s) { return { key: nk, label: s.label, tone: s.tone, title: s.title, known: true }; }
    return { key: nk, label: nk || "?", tone: "unknown", title: "Unknown / non-canonical label - not part of the honest vocabulary.", known: false };
  }

  function badgeHTML(key, opts) {
    opts = opts || {};
    var r = resolve(key);
    var label = opts.label != null ? String(opts.label) : r.label;
    var title = opts.title != null ? String(opts.title) : r.title;
    var extra = opts.className ? (" " + String(opts.className)) : "";
    var dot = opts.dot === false ? "" : '<span class="szl-dot" aria-hidden="true"></span>';
    return '<span class="szl-pill ' + esc(r.tone) + extra + '" data-szl-label="' + esc(r.key) +
      '" title="' + esc(title) + '" role="img" aria-label="data label: ' + esc(label) + '">' +
      dot + esc(label) + "</span>";
  }

  function badge(key, opts) {
    opts = opts || {};
    var doc = opts.document || (typeof document !== "undefined" ? document : null);
    if (!doc) { throw new Error("SZLLabels.badge requires a DOM document; use badgeHTML in Node."); }
    ensureStyle(doc);
    var tmp = doc.createElement("div");
    tmp.innerHTML = badgeHTML(key, opts);
    return tmp.firstChild;
  }

  return {
    VERSION: "1.0.0",
    SCHEMES: SCHEMES,
    badge: badge,
    badgeHTML: badgeHTML,
    isHonestLabel: isHonestLabel,
    normalize: normalize,
    auditText: auditText,
    ensureStyle: ensureStyle,
    keys: function () { var a = [], k; for (k in SCHEMES) { a.push(k); } return a; }
  };
});
