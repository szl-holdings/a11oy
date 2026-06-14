/* SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 * ============================================================================
 * szl_codename_sanitizer.js - SHARED MODULE (byte-identical across both apps)
 * ----------------------------------------------------------------------------
 * Doctrine gate G5: 0 user-visible codenames. Internal route keys
 * (amaru_* / rosie_* / sentra / jarvis) are fine as JS keys, but EVERY
 * user-visible string must read its honest public role:
 *     amaru  -> YACHAY     (cortex / brain / OSINT ingest)
 *     rosie  -> Operator   (orchestrator)
 *     sentra -> CHAPAQ     (verdict / immune)
 *     jarvis -> Operator   (assistant / orchestrator)
 *
 * NO CDN. Vanilla JS. Browser + Node. This is the single mapping table so the
 * two apps never drift, plus a live rendered-DOM scanner used by the CI gate.
 *
 * Public API (window.SZLCodenames / module.exports):
 *   MAP                              - frozen {codename: publicRole}
 *   BANNED_RE                        - the canonical detector regex (global, i)
 *   sanitize(str)                    - replace banned tokens with public roles
 *   scan(str)                        - return [{token, index}] of banned hits
 *   scanDOM(rootNode?)               - scan rendered text + key attrs; returns hits[]
 *   guardedRender(el)                - sanitize textContent of a node in-place
 *   isClean(str)                     - boolean
 * ============================================================================ */
(function (root, factory) {
  var mod = factory();
  if (typeof module === "object" && module.exports) { module.exports = mod; }
  if (root) { root.SZLCodenames = mod; }
})(typeof self !== "undefined" ? self : (typeof window !== "undefined" ? window : null), function () {
  "use strict";

  // Case-preserving public-role mapping. Order: most-specific first.
  var MAP = {
    "amaru": "YACHAY",
    "rosie": "Operator",
    "sentra": "CHAPAQ",
    "jarvis": "Operator"
  };
  try { Object.freeze(MAP); } catch (e) {}

  // Word-ish boundary: catch amaru, rosie_digest, Sentra, JARVIS, amaru-feed.
  // We match the bare codename token wherever it appears as a visible word part.
  var TOKENS = ["amaru", "rosie", "sentra", "jarvis"];
  var BANNED_RE = new RegExp("(" + TOKENS.join("|") + ")", "ig");

  function _roleFor(tok) {
    var low = String(tok).toLowerCase();
    return MAP[low] || low;
  }

  // Replace a matched codename, preserving a leading capital if the source was
  // capitalized (so "Rosie" -> "Operator", "rosie" -> "Operator" both read well).
  function sanitize(str) {
    if (str == null) { return str; }
    return String(str).replace(BANNED_RE, function (m) { return _roleFor(m); });
  }

  function scan(str) {
    var out = [], s = String(str == null ? "" : str), m;
    BANNED_RE.lastIndex = 0;
    while ((m = BANNED_RE.exec(s)) !== null) {
      out.push({ token: m[0], index: m.index });
      if (m.index === BANNED_RE.lastIndex) { BANNED_RE.lastIndex++; }
    }
    return out;
  }

  function isClean(str) { return scan(str).length === 0; }

  /* Scan a rendered DOM subtree for visible banned tokens. Checks visible text
   * nodes + the human-visible attributes (title, aria-label, alt, placeholder,
   * value). Ignores id/class/data-* route keys (those are allowed internal keys).
   * Returns [{token, where, sample}]. */
  function scanDOM(rootNode) {
    var doc = (typeof document !== "undefined") ? document : null;
    var root = rootNode || (doc ? doc.body : null);
    if (!root) { return []; }
    var hits = [];
    var VISIBLE_ATTRS = ["title", "aria-label", "alt", "placeholder", "value"];

    // 1) text nodes
    if (doc && doc.createTreeWalker) {
      var walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
      var n;
      while ((n = walker.nextNode())) {
        var t = n.nodeValue || "";
        var sc = scan(t);
        for (var i = 0; i < sc.length; i++) {
          hits.push({ token: sc[i].token, where: "text", sample: t.slice(Math.max(0, sc[i].index - 12), sc[i].index + 16) });
        }
      }
    }
    // 2) visible attributes
    var all = root.querySelectorAll ? root.querySelectorAll("*") : [];
    for (var e = 0; e < all.length; e++) {
      for (var a = 0; a < VISIBLE_ATTRS.length; a++) {
        var av = all[e].getAttribute ? all[e].getAttribute(VISIBLE_ATTRS[a]) : null;
        if (av) {
          var sca = scan(av);
          for (var j = 0; j < sca.length; j++) {
            hits.push({ token: sca[j].token, where: "@" + VISIBLE_ATTRS[a], sample: av.slice(0, 40) });
          }
        }
      }
    }
    return hits;
  }

  function guardedRender(el) {
    if (!el) { return el; }
    if (typeof el.textContent === "string") { el.textContent = sanitize(el.textContent); }
    return el;
  }

  return {
    VERSION: "1.0.0",
    MAP: MAP,
    TOKENS: TOKENS.slice(),
    BANNED_RE: BANNED_RE,
    sanitize: sanitize,
    scan: scan,
    isClean: isClean,
    scanDOM: scanDOM,
    guardedRender: guardedRender
  };
});
