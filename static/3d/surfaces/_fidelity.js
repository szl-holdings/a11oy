// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/_fidelity.js — shared HONESTY-LABEL BADGE for the holographic surfaces.
//
// One job: ask the server what this surface's fidelity actually is RIGHT NOW and show
// that answer VERBATIM. The label is never computed, upgraded, or guessed client-side.
//   GET /api/a11oy/v1/surface/fidelity/<surface_id>   (szl_surface_fidelity.py)
// The server recomputes the label per request from a REAL read (its organ's in-request
// compute, a node probe, an eval run, the brain graph, or the fleet joule meter) and
// attaches provenance; a surface with no real signal stays STRUCTURAL-ONLY and says why.
//
// DEFAULT-PESSIMISTIC: until the server answers, the badge reads STRUCTURAL-ONLY. On a
// 404/500/offline it says UNAVAILABLE (fidelity endpoint unreachable) — never a green or
// optimistic label. MEASURED is only ever shown because the server said MEASURED.
// 0 RUNTIME CDN. No purple. Additive: it appends one chip and removes it on stop().
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1 (advisory, never green).

const FID_BASE = "/api/a11oy/v1/surface/fidelity";

// gray = structural/unknown, blue = modeled, teal = measured. Purple BANNED.
const TONE = {
  "MEASURED": "#3af4c8",
  "MODELED": "#5b8dee",
  "STRUCTURAL-ONLY": "#9aa3af",
  "UNAVAILABLE": "#9aa3af",
};

function _chip(text, tone, title) {
  const el = document.createElement("span");
  el.className = "szl-fidelity-chip";
  el.textContent = text;
  el.title = title || "";
  el.style.cssText =
    "display:inline-flex;align-items:center;gap:4px;padding:1px 7px;border-radius:9px;" +
    "font:500 10px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.02em;" +
    "border:1px solid " + tone + "55;color:" + tone + ";background:" + tone + "14;";
  return el;
}

/**
 * Attach the server-authoritative fidelity chip for `id`.
 * Returns { stop() } — always call it from the surface's unmount().
 */
export function attachFidelityBadge(id, ctx) {
  let stopped = false;
  const chip = _chip(
    "fidelity: STRUCTURAL-ONLY",
    TONE["STRUCTURAL-ONLY"],
    "awaiting the server's honest fidelity label; STRUCTURAL-ONLY until then",
  );

  // Prefer the showcase pill row this surface already renders; else a corner overlay.
  let host = null;
  try {
    const pills = document.querySelectorAll(".szl-show__pills");
    host = pills.length ? pills[pills.length - 1] : null;
  } catch (_) { host = null; }
  if (!host) {
    host = document.createElement("div");
    host.style.cssText = "position:fixed;left:10px;bottom:10px;z-index:40;pointer-events:none";
    try { document.body.appendChild(host); } catch (_) {}
    chip.dataset.ownHost = "1";
  }
  try { host.appendChild(chip); } catch (_) {}

  function render(label, note) {
    if (stopped) return;
    const tone = TONE[label] || TONE["STRUCTURAL-ONLY"];
    chip.textContent = "fidelity: " + label;          // VERBATIM from the server
    chip.title = note || "";
    chip.style.borderColor = tone + "55";
    chip.style.color = tone;
    chip.style.background = tone + "14";
  }

  fetch(FID_BASE + "/" + encodeURIComponent(id), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
    .then((j) => {
      const label = (j && typeof j.label === "string") ? j.label : "UNAVAILABLE";
      const bits = [];
      if (j && j.basis) bits.push("basis: " + j.basis);
      if (j && j.structural_only_reason) bits.push("why: " + j.structural_only_reason);
      if (j && j.upgrade_condition) bits.push("to upgrade: " + j.upgrade_condition);
      if (j && j.measured_gap) bits.push("not measured: " + j.measured_gap);
      render(label, bits.join("\n"));
      if (ctx && typeof ctx.onFidelity === "function") {
        try { ctx.onFidelity(j); } catch (_) {}
      }
    })
    .catch((e) => render("UNAVAILABLE",
      "fidelity endpoint unreachable (" + (e && e.message ? e.message : "error") +
      ") — no label claimed"));

  return {
    stop() {
      stopped = true;
      try {
        if (chip.dataset.ownHost && chip.parentNode && chip.parentNode.parentNode) {
          chip.parentNode.parentNode.removeChild(chip.parentNode);
        } else if (chip.parentNode) {
          chip.parentNode.removeChild(chip);
        }
      } catch (_) {}
    },
  };
}

export default { attachFidelityBadge };
